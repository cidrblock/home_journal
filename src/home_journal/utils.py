"""Helper utilities."""
import logging
import re
import shutil
import subprocess
import unicodedata

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from mmap import mmap
from pathlib import Path
from collections.abc import Iterator

import cmarkgfm
import jinja2
import magic
import yaml

from cmarkgfm.cmark import Options as cmarkgfmOptions
from flask.wrappers import Request
from frontmatter import load as frontmatter_load
from PIL import Image
from PIL import ImageOps


jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
)

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class BasePost:
    """Base class for post metadata."""

    # pylint: disable=too-many-instance-attributes

    # The date the post was created
    date: datetime
    # The post directory on the file system
    fs_post_directory: Path
    # The markdown content of the post
    md_content: str
    # The post id
    post_id: str
    # A list of tags for the post
    tags: list[str]
    # The title of the post
    title: str

    # The author of the post
    author: str = ""
    # The next post url
    next: Path | None = None
    # The previous post url
    previous: Path | None = None

    def __post_init__(self) -> None:
        """Post init."""
        if not self.author:
            self.author = "Unknown"

    @property
    def fs_media_dir(self) -> Path:
        """Get the full path to the image directory.

        Returns:
            The full path to the image directory.
        """
        return self.fs_post_directory / "media"

    @property
    def fs_post_full_html_path(self) -> Path:
        """Get the full path to the post html file.

        Returns:
            The full path to the post html file.
        """
        return self.fs_post_directory / "index.html"


@dataclass(kw_only=True)
class ExistingPost(BasePost):
    """Metadata for an existing post."""

    # The image to use on the index
    index_image: str | None = None
    # The good url for the post
    post_url: Path | None = None
    # The url for the thumbnail image
    thumbnail_parent_url: Path | None = None
    # The url for the thumbnail image
    thumbnail_url: Path | None = None

    @property
    def author_index(self) -> str:
        """Get the author index url.

        Returns:
            The author index url.
        """
        return f"{_slugify(self.author)}.html"

    def write_html(self) -> None:
        """Write the post to an HTML file."""
        template = jinja_env.get_template("post.html.j2")
        html_content = _render_markdown(self.md_content)
        rendered = template.render(post=self, content=html_content)
        self.fs_post_full_html_path.write_text(rendered, encoding="utf-8")


@dataclass(kw_only=True)
class NewPost(BasePost):
    """Metadata for a post."""

    # The filename for each attachment
    media_file_names: list[str]

    @property
    def fs_post_full_md_path(self) -> Path:
        """Get the full path to the post md file.

        Returns:
            The full path to the post md file.
        """
        return self.fs_post_directory / "post.md"

    @property
    def md_header(self) -> str:
        """Convert the post metadata to a dictionary.

        This is needed when markdown and html files are generated.

        Returns:
            The post metadata as a dictionary.
        """
        include = {
            "author": self.author,
            "date": str(self.date),
            "media_file_names": self.media_file_names,
            "post_id": self.post_id,
            "tags": self.tags,
            "title": self.title,
        }
        return yaml.dump(include, default_flow_style=False)  # type: ignore[no-any-return]

    @property
    def relative_media_path(self) -> Path:
        """Get the relative path to the image directory.

        Returns:
            The relative path to the image directory.
        """
        return self.fs_media_dir.relative_to(self.fs_post_directory)

    @property
    def relative_media_paths(self) -> list[Path]:
        """Get the relative paths to the images.

        Returns:
            The relative paths to the images.
        """
        return [self.relative_media_path / media for media in self.media_file_names]

    def write_md(self) -> None:
        """Write the post to a markdown file."""
        self.fs_post_full_md_path.write_text(self.md_content, encoding="utf-8")


def _slugify(value: str, allow_unicode: bool = False) -> str:
    """Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.

    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.

    Args:
        value: The string to be converted.
        allow_unicode (bool): Whether to allow unicode characters.

    Returns:
        str: The converted string.
    """
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
        value = re.sub(r"[^\w\s-]", "", value, flags=re.U).strip().lower()
        return re.sub(r"[-\s]+", "-", value, flags=re.U)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def _extract_tags(request: Request) -> list[str]:
    """Extract tags from flask request.

    Args:
        request: The Markdown content to extract tags from.

    Returns:
        The tags.
    """
    form_keys = request.form.keys()  # type: ignore[no-untyped-call]
    selected_tags = [key.split("-", 1)[1] for key in form_keys if key.startswith("tag-")]
    form_tags = request.form.get("tags", "")
    tag_list = [tag.strip() for tag in form_tags.split(",")] + selected_tags
    if not tag_list:
        tag_list = ["random"]
    tag_list = [tag.lower() for tag in tag_list if tag]
    return tag_list


def _extract_images(post: NewPost, request: Request) -> None:
    """Extract images from flask request.

    Args:
        post: The post to extract images for.
        request: The Markdown content to extract images from.

    Raises:
        ValueError: If the image directory is not set.
    """
    # pylint: disable=too-many-locals
    if not post.fs_media_dir:
        raise ValueError("fs_media_dir is not set")
    post.fs_media_dir.mkdir(exist_ok=True, parents=True)

    all_media = request.files.getlist("media")

    logger.debug(all_media)
    logger.debug(len(all_media))

    for media in all_media:
        logger.debug(media)
        if not media:
            continue
        if not isinstance(media.filename, str):
            continue

        # Make minimal changes to the filename
        filename = media.filename.replace(" ", "_")
        media_path = post.fs_media_dir / filename
        media.save(media_path)

        logger.debug(media)
        mimetype = magic.from_file(media_path, mime=True)
        logger.debug(mimetype)
        if mimetype.startswith("image/"):
            eop = b"\x66\x74\x79\x70\x69\x73\x6F\x6D"
            with media_path.open("r+b") as image:
                mem_map = mmap(image.fileno(), 0)
                file_size = mem_map.size()
                place = mem_map.find(eop)
                place_lim = file_size - len(eop)
                if place in (-1, place_lim):
                    post.media_file_names.append(filename)
                    continue
                offset = place - 4

                mem_map.seek(0)
                jpeg = mem_map.read(offset)

                mem_map.seek(offset)
                mp4 = mem_map.read(file_size)

                file_base = media_path.stem
                jpeg_path = post.fs_media_dir / ("ex_" + file_base + ".jpg")
                with jpeg_path.open("w+b") as jpeg_file:
                    jpeg_file.write(jpeg)
                post.media_file_names.append(jpeg_path.name)

                mp4_orig_path = post.fs_media_dir / ("ex_orig_" + file_base + ".mp4")
                with mp4_orig_path.open("w+b") as mp4_file:
                    mp4_file.write(mp4)
                mp4_h264_path = post.fs_media_dir / ("ex_h264_" + file_base + ".mp4")

                _subproc = subprocess.run(
                    [
                        "ffmpeg",
                        "-i",
                        str(mp4_orig_path),
                        "-map",
                        "0:0",
                        "-c:v",
                        "libx264",
                        "-crf",
                        "18",
                        "-c:a",
                        "copy",
                        str(mp4_h264_path),
                    ],
                    check=False,
                )
                logger.debug(_subproc.stderr)
                logger.debug(_subproc.stdout)
                post.media_file_names.append(mp4_h264_path.name)

        else:
            post.media_file_names.append(filename)


def _media_groups(post: NewPost, names: list[str]) -> dict[str, list[tuple[Path, str]]]:
    """Group media files by major MIME type.

    Args:
        post: The post that owns the media directory.
        names: Media file names to include.

    Returns:
        A mapping of major MIME type to relative path and full MIME type.
    """
    mimes: dict[str, list[tuple[Path, str]]] = {}
    for media in names:
        path = post.fs_media_dir / media
        if not path.is_file():
            logger.warning("Skipping missing media file %s", path)
            continue
        mime = magic.from_file(path, mime=True)
        mime_type, _mime_subtype = mime.split("/")
        if mime_type not in mimes:
            mimes[mime_type] = []
        mimes[mime_type].append((post.relative_media_path / media, mime))
    return mimes


_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_TRAILING_IMAGE = re.compile(
    r"[ \t]*!\[\]\(media/([^)\s]+)\)[ \t]*(?:\r?\n)?\Z",
)
_TRAILING_VIDEO = re.compile(
    r"[ \t]*<div class=\"video\">\s*"
    r"<video[^>]*>\s*"
    r"<source src=\"media/([^\"]+)\"[^>]*>\s*"
    r"</video>\s*"
    r"</div>[ \t]*(?:\r?\n)?\Z",
    re.IGNORECASE | re.DOTALL,
)


def catalog_media_names(metadata: dict[str, object]) -> list[str]:
    """Return media file names from post frontmatter.

    Args:
        metadata: Parsed post frontmatter.

    Returns:
        Names from media_file_names, or image_file_names for older posts.
    """
    names = metadata.get("media_file_names") or metadata.get("image_file_names") or []
    return [str(name) for name in names]


def strip_media_appendix(content: str, media_names: list[str]) -> str:
    """Remove a trailing generated media appendix from markdown content.

    Only strips trailing image/video blocks whose files are in media_names.
    Inline images in the prose are left alone.

    Args:
        content: Full markdown body.
        media_names: Catalog of attached media file names.

    Returns:
        Prose with the generated appendix removed.
    """
    known = set(media_names)
    text = content.replace("\r\n", "\n")
    while text:
        trimmed = text.rstrip()
        image_match = _TRAILING_IMAGE.search(trimmed)
        if image_match and image_match.group(1) in known:
            text = trimmed[: image_match.start()]
            continue
        video_match = _TRAILING_VIDEO.search(trimmed)
        if video_match and video_match.group(1) in known:
            text = trimmed[: video_match.start()]
            continue
        break
    return text.rstrip()


def edit_prose(post: ExistingPost) -> str:
    """Return the post body without a generated media appendix.

    Args:
        post: The post to edit.

    Returns:
        Prose suitable for the edit form.
    """
    md_path = post.fs_post_directory / "post.md"
    parsed_post = frontmatter_load(md_path)
    return strip_media_appendix(post.md_content, catalog_media_names(parsed_post.metadata))


def media_names_in_content(content: str) -> set[str]:
    """Return media file names referenced in markdown or video HTML.

    Args:
        content: Markdown body.

    Returns:
        File names that appear as media/... references.
    """
    return set(re.findall(r"media/([^)\s\"]+)", content))


def _index_image_name(metadata: dict[str, object], content: str) -> str | None:
    """Pick the index thumbnail file name for a post.

    Args:
        metadata: Parsed post frontmatter.
        content: Markdown body.

    Returns:
        A still-image file name, or None.
    """
    for name in catalog_media_names(metadata):
        if Path(name).suffix.lower() in _IMAGE_SUFFIXES:
            return Path(name).name
    images = re.findall(r"!\[.*\]\((.*?\.(?:jpg|jpeg|png))?.*\)", content)
    names = [Path(image).name for image in images if image]
    return names[0] if names else None


def _populate_post_metadata(
    md_glob: Iterator[Path], site_dir: Path, limit: list[Path] | None = None
) -> list[ExistingPost]:
    """Populate the metadata for all posts.

    Args:
        md_glob: The glob of markdown files.
        site_dir: The directory of the site.
        limit: The list of posts to limit to.

    Returns:
        The list of posts.
    """
    posts = []

    for path in md_glob:
        if limit and path not in limit:
            continue
        parsed_post = frontmatter_load(path)
        date = datetime.fromisoformat(parsed_post["date"])
        if not date.tzinfo:
            date = date.replace(tzinfo=timezone.utc)
        image_file_names = _index_image_name(parsed_post.metadata, parsed_post.content)

        # Some older posts have categories, convert to tags
        tags = parsed_post.metadata.get("tags", [])
        categories = parsed_post.metadata.get("categories", [])

        post = ExistingPost(
            author=parsed_post.get("author", ""),
            date=date,
            fs_post_directory=path.parent,
            md_content=parsed_post.content,
            post_id=path.parent.name,
            tags=tags + categories,
            title=parsed_post["title"],
        )
        post.post_url = Path("/") / post.fs_post_full_html_path.relative_to(site_dir)
        if image_file_names:
            post.index_image = image_file_names
            post.thumbnail_parent_url = Path("/") / post.fs_media_dir.relative_to(site_dir)
        posts.append(post)
    # Ensure we are ordered chronologically
    posts.sort(key=lambda x: x.date)

    return posts


def _populate_post_next_previous(posts: list[ExistingPost], site_dir: Path) -> None:
    """Populate the next and previous metadata for all posts.

    Args:
        posts: The list of posts.
        site_dir: The directory of the site.
    """
    for idx, post in enumerate(posts):
        if idx == 0:
            previous_post = posts[-1]
        else:
            previous_post = posts[idx - 1]
        post.previous = previous_post.fs_post_full_html_path.relative_to(site_dir)

        if idx == len(posts) - 1:
            next_post = posts[0]
        else:
            next_post = posts[idx + 1]
        post.next = next_post.fs_post_full_html_path.relative_to(site_dir)


def _prune_post_list(post_id: str, posts: list[ExistingPost]) -> list[ExistingPost]:
    """Prune the list of posts to only include the post and the previous and next posts.

    Args:
        post_id: The id of the post to build.
        posts: The list of posts.

    Returns:
        The list of posts to build.
    """
    found = [idx for idx, post in enumerate(posts) if post.post_id == post_id]
    if not found:
        return []
    post_found = found[0]
    revise = [post_found]
    if post_found == 0:
        revise.append(len(posts) - 1)
    else:
        revise.append(post_found - 1)
    if post_found == len(posts) - 1:
        revise.append(0)
    else:
        revise.append(post_found + 1)

    return [posts[i] for i in revise]


def _render_markdown(content: str) -> str:
    """Render Markdown to HTML.

    Args:
        content: The Markdown content to render.

    Returns:
        The rendered HTML.
    """
    content = cmarkgfm.github_flavored_markdown_to_html(
        content,
        options=cmarkgfmOptions.CMARK_OPT_UNSAFE,
    )
    return content


def find_post(site_dir: Path, post_id: str) -> ExistingPost | None:
    """Find a post by id under the site posts directory.

    Args:
        site_dir: The directory of the site.
        post_id: The id of the post.

    Returns:
        The post, or None if it is missing or outside the posts directory.
    """
    if not post_id:
        return None
    posts_dir = site_dir / "posts"
    posts_root = posts_dir.resolve()
    all_posts = _populate_post_metadata(md_glob=posts_dir.rglob("*.md"), site_dir=site_dir)
    matches = [post for post in all_posts if post.post_id == post_id]
    if not matches:
        return None
    post_dir = matches[0].fs_post_directory.resolve()
    if not post_dir.is_relative_to(posts_root):
        logger.error("Refusing to use path outside posts dir: %s", post_dir)
        return None
    return matches[0]


def load_site_config(site_dir: Path) -> dict[str, object]:
    """Load optional site config.yml.

    Args:
        site_dir: The directory of the site.

    Returns:
        The config mapping, or empty if the file is missing.
    """
    path = site_dir / "config.yml"
    if not path.is_file():
        logger.info("No site config.yml found at %s", path)
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        logger.warning("Ignoring %s because it is not a YAML mapping", path)
        return {}
    logger.info("Loaded site config from %s", path)
    return loaded


def delete_post(site_dir: Path, post_id: str) -> bool:
    """Delete a post directory from the site.

    Args:
        site_dir: The directory of the site.
        post_id: The id of the post to delete.

    Returns:
        True if the post was found and removed.
    """
    existing = find_post(site_dir, post_id)
    if existing is None:
        return False

    posts_root = (site_dir / "posts").resolve()
    post_dir = existing.fs_post_directory.resolve()
    shutil.rmtree(post_dir)
    parent = post_dir.parent
    for _ in range(2):
        if parent == posts_root or not parent.exists() or any(parent.iterdir()):
            break
        parent.rmdir()
        parent = parent.parent
    return True


def update_post(site_dir: Path, request: Request) -> ExistingPost | None:
    """Update a post's markdown and re-append attached media.

    The edit form holds prose only. This writes that prose, then appends
    generated image and video blocks from the media catalog plus new uploads.
    The post directory, post id, date, and existing media files are kept.

    Args:
        site_dir: The directory of the site.
        request: The edit form request.

    Returns:
        The existing post, or None if it was not found.
    """
    existing = find_post(site_dir, request.form.get("post_id", ""))
    if existing is None:
        return None

    md_path = existing.fs_post_directory / "post.md"
    parsed_post = frontmatter_load(md_path)
    existing_media = catalog_media_names(parsed_post.metadata)

    draft = NewPost(
        author=request.form["author"],
        date=existing.date,
        media_file_names=list(existing_media),
        fs_post_directory=existing.fs_post_directory,
        md_content="",
        post_id=existing.post_id,
        tags=_extract_tags(request),
        title=request.form.get("title", existing.title),
    )
    _extract_images(post=draft, request=request)
    prose = strip_media_appendix(
        request.form.get("content", ""),
        draft.media_file_names,
    )
    already_in_prose = media_names_in_content(prose)
    appendix_names = [name for name in draft.media_file_names if name not in already_in_prose]
    appendix = _media_groups(draft, appendix_names)

    template = jinja_env.get_template("post.md.j2")
    draft.md_content = template.render(
        content=prose,
        images=appendix.get("image", []),
        videos=appendix.get("video", []),
        md_header=draft.md_header,
    )
    draft.write_md()
    return existing


def convert_all_html(
    site_dir: Path,
    post_id: str | None = None,
) -> tuple[list[ExistingPost], list[ExistingPost]]:
    """Convert all posts to html.

    Args:
        site_dir: The directory of the site.
        post_id: The name of the post to build.

    Returns:
        The number of posts built.
    """
    posts_dir = site_dir / "posts"
    md_glob = posts_dir.rglob("*.md")
    all_posts = _populate_post_metadata(md_glob=md_glob, site_dir=site_dir)

    _populate_post_next_previous(posts=all_posts, site_dir=site_dir)

    if post_id:
        revise_posts = _prune_post_list(post_id=post_id, posts=all_posts)
    else:
        revise_posts = all_posts

    for post in revise_posts:
        post.write_html()
    return revise_posts, all_posts


def initialize_new_post(request: Request, posts_dir: Path) -> NewPost:
    """Initialize a new post.

    Args:
        request: The request.
        posts_dir: The directory of the posts.

    Returns:
        The new post.
    """
    now = datetime.now().astimezone()
    now_iso = now.isoformat()
    post_id = f"{now_iso}_{_slugify(request.form['title'])}"

    # Make the directory for the post and images
    dir_path = posts_dir / str(now.year) / str(now.month).zfill(2) / post_id

    post = NewPost(
        author=request.form["author"],
        date=now,
        media_file_names=[],
        fs_post_directory=dir_path,
        md_content="",
        post_id=post_id,
        tags=_extract_tags(request),
        title=request.form.get("title", str(now_iso)),
    )

    _extract_images(post=post, request=request)

    template = jinja_env.get_template("post.md.j2")
    mimes = _media_groups(post, post.media_file_names)
    post.md_content = template.render(
        content=request.form["content"],
        images=mimes.get("image", []),
        videos=mimes.get("video", []),
        md_header=post.md_header,
    )

    return post


def write_index(posts: list[ExistingPost], site_dir: Path) -> None:
    """Write the index file.

    Args:
        posts: The posts.
        site_dir: The directory of the site.
    """
    path = site_dir / "index.html"
    template = jinja_env.get_template("index.html.j2")
    rendered = template.render(posts=posts, title="everything")

    path.write_text(rendered, encoding="utf-8")


def write_tag_indices(posts: list[ExistingPost], site_dir: Path) -> None:
    """Write the tag files.

    Args:
        posts: The posts.
        site_dir: The directory of the site.
    """
    tag_dir = site_dir / "tags"
    # Start with fresh tag indices
    shutil.rmtree(tag_dir, ignore_errors=True)

    all_tags: dict[str, list[ExistingPost]] = {}
    for post in posts:
        for tag in post.tags:
            if tag not in all_tags:
                all_tags[tag] = []
            all_tags[tag].append(post)

    for tag, matching_posts in all_tags.items():
        tag_index_path = Path(tag_dir)
        tag_index_path.mkdir(parents=True, exist_ok=True)
        path = tag_index_path / f"{_slugify(tag)}.html"
        template = jinja_env.get_template("index.html.j2")
        rendered = template.render(posts=matching_posts, title=tag, title_icon="tag")
        path.write_text(rendered, encoding="utf-8")


def write_author_indices(posts: list[ExistingPost], site_dir: Path) -> None:
    """Write the author files.

    Args:
        posts: The posts.
        site_dir: The directory of the site.
    """
    author_dir = site_dir / "authors"
    # Start with fresh author indices
    shutil.rmtree(author_dir, ignore_errors=True)

    all_authors: dict[str, list[ExistingPost]] = {}
    for post in posts:
        author = post.author
        if author not in all_authors:
            all_authors[author] = []
        all_authors[author].append(post)

    for author, matching_posts in all_authors.items():
        author_index_path = Path(author_dir)
        author_index_path.mkdir(parents=True, exist_ok=True)
        path = author_index_path / f"{_slugify(author)}.html"
        template = jinja_env.get_template("index.html.j2")
        rendered = template.render(posts=matching_posts, title=author, title_icon="person")
        path.write_text(rendered, encoding="utf-8")


def build_thumbnails(posts: list[ExistingPost]) -> None:
    """Build thumbnails for the post.

    Args:
        posts: The post to build thumbnails for.

    Raises:
        ValueError: If the thumbnail URL is not set.
    """
    count = 0
    for post in posts:
        image_dir = post.fs_media_dir
        index_image = post.index_image
        if not index_image:
            continue
        image_path = image_dir / index_image
        thumbnail_name = f"thumb_{index_image}"
        if post.thumbnail_parent_url is None:
            raise ValueError("Thumbnail URL not set")
        post.thumbnail_url = post.thumbnail_parent_url / thumbnail_name
        if not (image_dir / thumbnail_name).exists():
            image = Image.open(image_path)
            transposed = ImageOps.exif_transpose(image)
            if transposed is not None:
                image = transposed
            image.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
            save_image = image
            if thumbnail_name.lower().endswith((".jpg", ".jpeg")) and image.mode not in (
                "RGB",
                "L",
            ):
                save_image = image.convert("RGB")
            save_image.save(image_dir / thumbnail_name)
            count += 1
    logger.debug("Built %s thumbnails", count)


def render_search_results(search_str: str, site_dir: Path) -> list[ExistingPost]:
    """Render the search results.

    Args:
        search_str: The search string.
        site_dir: The directory of the site.

    Returns:
        The rendered search results.
    """
    res = subprocess.run(
        f"grep -r -i -l --include='*.md' '{search_str}' {site_dir}",
        shell=True,
        capture_output=True,
        check=False,
    )
    limit = [Path(line) for line in res.stdout.decode("utf-8").splitlines()]
    if not limit:
        return []
    posts_dir = site_dir / "posts"
    md_glob = posts_dir.rglob("*.md")
    posts = _populate_post_metadata(md_glob=md_glob, site_dir=site_dir, limit=limit)
    build_thumbnails(posts)
    return posts
