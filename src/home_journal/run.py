"""Form to post."""
import argparse
import hmac
import logging
import pathlib

from pathlib import Path
from typing import TYPE_CHECKING

from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask.wrappers import Response
from waitress import serve

from .utils import build_thumbnails
from .utils import convert_all_html
from .utils import delete_post
from .utils import initialize_new_post
from .utils import load_site_config
from .utils import render_search_results
from .utils import write_author_indices
from .utils import write_index
from .utils import write_tag_indices


app = Flask(__name__, static_url_path="", template_folder=str(Path(__file__).parent / "templates"))
logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from werkzeug.wrappers import Response as BaseResponse


@app.route("/config.yml")
@app.route("/config.yaml")
def endpoint_hide_config() -> Response:
    """Do not serve the site config file.

    Returns:
        A 404 response.
    """
    return Response(status=404)


@app.route("/")
def endpoint_root() -> Response:
    """Serve the index.html file from the static folder.

    Returns:
        The index.html file.
    """
    return app.send_static_file("index.html")


@app.route("/new.html")
def endpoint_new() -> Response:
    """Serve the index.html file from the static folder.

    Returns:
        The new.html file with the tags.
    """
    return Response(
        render_template(
            "new.html.j2",
            tags=app.config["tags"],
            authors=app.config["authors"],
        )
    )


@app.route("/search", methods=["POST"])
def endpoint_search() -> Response:
    """Search all the posts.

    Returns:
        An index page with the search results.
    """
    search = request.form["search"]
    result = render_search_results(search, app.config["site_dir"])
    return Response(
        render_template("index.html.j2", posts=result, title=search, title_icon="search")
    )


@app.route("/all")
def endpoint_convert_all() -> str:
    """Serve the index.html file from the static folder.

    Returns:
        The count of posts converted.
    """
    logger.debug("Converting all posts")
    revised, all_posts = _rebuild_site()
    return f"Built {len(revised)} of {len(all_posts)} posts."


def _rebuild_site() -> tuple[list, list]:
    """Rebuild HTML, thumbnails, and indices for the whole site.

    Returns:
        The revised posts and the full post list.
    """
    site_dir = app.config["site_dir"]
    revised, all_posts = convert_all_html(site_dir)
    build_thumbnails(all_posts)
    write_index(all_posts, site_dir=site_dir)
    write_author_indices(all_posts, site_dir=site_dir)
    write_tag_indices(all_posts, site_dir=site_dir)
    return revised, all_posts


def _passcode_matches(provided: str) -> bool:
    """Return True if the provided passcode matches the configured one.

    Args:
        provided: The passcode from the request.

    Returns:
        True if the passcode is configured and matches.
    """
    expected = app.config.get("delete_passcode")
    if not expected:
        return False
    provided_text = str(provided)
    expected_text = str(expected)
    if len(provided_text) != len(expected_text):
        return False
    return hmac.compare_digest(provided_text, expected_text)


@app.route("/delete", methods=["POST"])
def endpoint_delete() -> "BaseResponse | Response":
    """Delete a post after the passcode is confirmed.

    Returns:
        A redirect to the index, or an error response.
    """
    if not _passcode_matches(request.form.get("passcode", "")):
        logger.warning("Rejected post delete with invalid passcode")
        return Response("Invalid passcode", status=403)

    post_id = request.form.get("post_id", "")
    if not post_id or not delete_post(app.config["site_dir"], post_id):
        logger.warning("Post not found for delete: %s", post_id)
        return Response("Post not found", status=404)

    logger.info("Deleted post %s", post_id)
    _rebuild_site()
    return redirect("/")


@app.route("/", methods=["POST"])
def endpoint_post() -> "BaseResponse | Response":
    """Create a new post from the form data and redirect to it.

    Returns:
        A redirect to the new post.
    """
    allowed_authors = app.config.get("authors") or []
    author = request.form.get("author", "")
    if allowed_authors and author not in allowed_authors:
        logger.warning("Rejected post with invalid author: %s", author)
        return Response("Invalid author", status=400)

    site_dir = app.config["site_dir"]
    posts_dir = app.config["site_dir"] / "posts"
    post = initialize_new_post(request=request, posts_dir=posts_dir)
    post.write_md()

    _revise_posts, all_posts = convert_all_html(
        site_dir=site_dir,
        post_id=post.post_id,
    )
    build_thumbnails(all_posts)
    write_index(all_posts, site_dir=site_dir)
    write_author_indices(all_posts, site_dir=site_dir)
    write_tag_indices(all_posts, site_dir=site_dir)
    return redirect(post.fs_post_full_html_path.relative_to(site_dir).as_posix())


def run_server(args: argparse.Namespace) -> None:
    """Run the app.

    Args:
        args: The parsed command line arguments.
    """
    site_dir = pathlib.Path(args.site_directory)
    config = load_site_config(site_dir)
    raw_tags = args.tags if args.tags else config.get("tags")
    raw_authors = config.get("authors")
    app.config["site_dir"] = site_dir
    app.config["tags"] = raw_tags if isinstance(raw_tags, list) else []
    app.config["authors"] = raw_authors if isinstance(raw_authors, list) else []
    app.config["delete_passcode"] = config.get("delete_passcode")
    app.static_folder = args.site_directory
    logger.info("Starting server")
    if args.init:
        logger.info("Initializing site")
        res = endpoint_convert_all()
        logger.info(res)

    serve(app, host="0.0.0.0", port=args.port, threads=8)
