"""Helper utilities."""
import re
import shutil
import unicodedata

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Generator

import cmarkgfm
import jinja2
import yaml

from cmarkgfm.cmark import Options as cmarkgfmOptions
from flask.wrappers import Request
from frontmatter import load as frontmatter_load
from PIL import Image
from PIL import ImageOps


jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
)


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

    # The next post url
    next: Path | None = None
    # The previous post url
    previous: Path | None = None

    @property
    def fs_image_dir(self) -> Path:
        """Get the full path to the image directory."""
        return self.fs_post_directory / "images"

    @property
    def fs_post_full_html_path(self) -> Path:
        """Get the full path to the post html file."""
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

    def write_html(self) -> None:
        """Write the post to an HTML file.

        Args:
            post: The post.
        """
        template = jinja_env.get_template("post.html.j2")
        html_content = _render_markdown(self.md_content)
        rendered = template.render(post=self, content=html_content)
        self.fs_post_full_html_path.write_text(rendered, encoding="utf-8")


@dataclass(kw_only=True)
class NewPost(BasePost):
    """Metadata for a post."""

    # The filename for each of the images
    image_file_names: list[str]

    @property
    def fs_post_full_md_path(self) -> Path:
        """Get the full path to the post md file."""
        return self.fs_post_directory / "post.md"

    @property
    def md_header(self) -> str:
        """Convert the post metadata to a dictionary.

        This is needed during templating of the markdown and html files.

        Returns:
            The post metadata as a dictionary.
        """
        include = {
            "date": str(self.date),
            "image_file_names": self.image_file_names,
            "post_id": self.post_id,
            "tags": self.tags,
            "title": self.title,
        }
        return yaml.dump(include, default_flow_style=False)  # type: ignore[no-any-return]

    @property
    def relative_image_path(self) -> Path:
        """Get the relative path to the image directory."""
        return self.fs_image_dir.relative_to(self.fs_post_directory)

    @property
    def relative_image_paths(self) -> list[Path]:
        """Get the relative paths to the images.

        Returns:
            The relative paths to the images.
        """
        return [self.relative_image_path / image for image in self.image_file_names]

    def write_md(self) -> None:
        """Write the post to a markdown file.

        Args:
            post: The post.
            dir_path: The directory to write the post to.
        """
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
    selected_tags = [key.split("-", 1)[1] for key in request.form.keys() if key.startswith("tag-")]
    form_tags = request.form.get("tags", "")
    tag_list = [tag.strip() for tag in form_tags.split(",")] + selected_tags
    if not tag_list:
        tag_list = ["random"]
    tag_list = [tag.lower() for tag in tag_list if tag]
    return tag_list


def _extract_images(post: NewPost, request: Request) -> None:
    """Extract images from flask request.

    Args:
        request: The Markdown content to extract images from.

    Returns:
        The image relative paths.
    """
    if not post.fs_image_dir:
        raise ValueError("fs_image_dir is not set")
    post.fs_image_dir.mkdir(exist_ok=True, parents=True)

    images = request.files.getlist("images")
    for image in images:
        if image:
            if isinstance(image.filename, str):
                image_path = Path(image.filename)
                image_filename = _slugify(image_path.stem) + image_path.suffix.lower()
                image_path = post.fs_image_dir / image_filename
                image.save(image_path)
                post.image_file_names.append(image_filename)


def _populate_post_metadata(
    md_glob: Generator[Path, None, None], site_dir: Path
) -> list[ExistingPost]:
    """Populate the metadata for all posts.

    Args:
        md_glob: The glob of markdown files.
        site_dir: The directory of the site.
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
            post.thumbnail_parent_url = Path("/") / post.fs_image_dir.relative_to(site_dir)
        posts.append(post)
    # Ensure we are ordered cronologically
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
        post_name: The name of the post to build.
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
    """
    now = datetime.now()
    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    post_id = f"{now_iso}_{_slugify(request.form['title'])}"

    # Make the directory for the post and images
    dir_path = posts_dir / str(now.year) / str(now.month).zfill(2) / post_id

    post = NewPost(
        date=now,
        image_file_names=[],
        fs_post_directory=dir_path,
        md_content="",
        post_id=post_id,
        tags=_extract_tags(request),
        title=request.form.get("title", str(now_iso)),
    )

    _extract_images(post=post, request=request)

    template = jinja_env.get_template("post.md.j2")
    post.md_content = template.render(
        content=request.form["content"],
        images=post.relative_image_paths,
        md_header=post.md_header,
    )

    return post


def write_index(posts: list[ExistingPost], site_dir: Path) -> None:
    """Write the index file.

    Args:
        posts: The posts.
    """
    path = site_dir / "index.html"
    template = jinja_env.get_template("index.html.j2")
    rendered = template.render(posts=posts, title="everything")

    path.write_text(rendered, encoding="utf-8")


def write_tag_indicies(posts: list[ExistingPost], site_dir: Path) -> None:
    """Write the tag files.

    Args:
        posts: The posts.
    """
    tag_dir = site_dir / "tags"
    # Start with fresh tag indicies
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


def build_thumbnails(posts: list[ExistingPost]) -> None:
    """Build thumbnails for the post.

    Args:
        post: The post to build thumbnails for.
    """
    for post in posts:
        image_dir = post.fs_image_dir
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
