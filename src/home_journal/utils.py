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
from typing import Generator

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


def _populate_post_metadata(
    md_glob: Generator[Path, None, None], site_dir: Path
) -> list[ExistingPost]:
    """Populate the metadata for all posts.

    Args:
        md_glob: The glob of markdown files.
        site_dir: The directory of the site.

    Returns:
        The list of posts.
    """
    posts = []

    for path in md_glob:
        parsed_post = frontmatter_load(path)
        date = datetime.fromisoformat(parsed_post["date"])
        if not date.tzinfo:
            date = date.replace(tzinfo=timezone.utc)
        image_file_names = parsed_post.metadata.get("image_file_names", [])
        # Some older posts may not have the header information
        if not image_file_names:
            images = re.findall(r"!\[.*\]\((.*?\.(?:jpg|jpeg|png))?.*\)", parsed_post.content)
            image_file_names = [Path(image).name for image in images if image]

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
            post.index_image = image_file_names[0]
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
    now = datetime.now()
    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
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

    mimes: dict[str, list[tuple[Path, str]]] = {}
    for media in post.media_file_names:
        path = post.fs_media_dir / media
        mime = magic.from_file(path, mime=True)
        mime_type, _mime_subtype = mime.split("/")
        if mime_type not in mimes:
            mimes[mime_type] = []
        mimes[mime_type].append(
            (
                post.relative_media_path / media,
                mime,
            )
        )

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
        rendered = template.render(posts=matching_posts, title=tag)
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
        rendered = template.render(posts=matching_posts, title=author)
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
            # Rotate the in memory image correctly
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1000, 1000), Image.ANTIALIAS)
            image.save(image_dir / thumbnail_name)
            count += 1
    logger.debug("Built %s thumbnails", count)
