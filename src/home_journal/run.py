"""Form to post."""
import argparse
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
from .utils import initialize_new_post
from .utils import write_author_indices
from .utils import write_index
from .utils import write_tag_indices


app = Flask(__name__, static_url_path="", template_folder=str(Path(__file__).parent / "templates"))
logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from werkzeug.wrappers import Response as BaseResponse


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
    return Response(render_template("new.html.j2", tags=app.config["tags"]))


@app.route("/all")
def endpoint_convert_all() -> str:
    """Serve the index.html file from the static folder.

    Returns:
        The count of posts converted.
    """
    logger.debug("Converting all posts")
    revised, all_posts = convert_all_html(app.config["site_dir"])
    build_thumbnails(all_posts)
    write_index(all_posts, site_dir=app.config["site_dir"])
    write_author_indices(all_posts, site_dir=app.config["site_dir"])
    write_tag_indices(all_posts, site_dir=app.config["site_dir"])
    return f"Built {len(revised)} of {len(all_posts)} posts."


@app.route("/", methods=["POST"])
def endpoint_post() -> "BaseResponse":
    """Create a new post from the form data and redirect to it.

    Returns:
        A redirect to the new post.
    """
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
    app.config["site_dir"] = pathlib.Path(args.site_directory)
    app.config["tags"] = args.tags
    app.static_folder = args.site_directory
    logger.info("Starting server")
    if args.init:
        logger.info("Initializing site")
        res = endpoint_convert_all()
        logger.info(res)

    serve(app, host="0.0.0.0", port=args.port, threads=8)
