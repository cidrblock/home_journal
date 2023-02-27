"""Form to post."""
import argparse
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
from .utils import write_index
from .utils import write_tag_indicies


if TYPE_CHECKING:
    from werkzeug.wrappers import Response as BaseResponse


app = Flask(__name__, static_url_path="", template_folder=Path(__file__).parent / "templates")


@app.route("/")
def endpoint_root() -> Response:
    """Serve the index.html file from the static folder."""
    return app.send_static_file("index.html")


@app.route("/new.html")
def endpoint_new() -> Response:
    """Serve the index.html file from the static folder."""
    return Response(render_template("new.html.j2", tags=app.config["tags"]))


@app.route("/all")
def endpoint_convert_all() -> str:
    """Serve the index.html file from the static folder."""
    revised, all_posts = convert_all_html(app.config["site_dir"])
    build_thumbnails(all_posts)
    write_index(all_posts, site_dir=app.config["site_dir"])
    write_tag_indicies(all_posts, site_dir=app.config["site_dir"])
    return f"Built {len(revised)} of {len(all_posts)} posts."


@app.route("/", methods=["POST"])
def endpoint_post() -> "BaseResponse":
    """Create a new post from the form data and redirect to it."""
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
    write_tag_indicies(all_posts, site_dir=site_dir)

    return redirect(post.fs_post_full_html_path.relative_to(site_dir).as_posix())


def list_tags(values):
    """Split a comma separated list of tags.

    Args:
        values: A comma separated list of tags.
    Returns:
        A list of tags.
    """
    return values.split(",")


def main() -> None:
    """Run the app."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-sd",
        "--site_directory",
        type=str,
        help="Path to the site directory",
        required=True,
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="Port to run the server on",
        default=8000,
    )
    parser.add_argument("-t", "--tags", help="A list of tags for new posts", type=list_tags)

    args = parser.parse_args()
    app.config["site_dir"] = pathlib.Path(args.site_directory)
    app.config["tags"] = args.tags
    app.static_folder = args.site_directory

    serve(app, host="0.0.0.0", port=args.port, threads=8)


if __name__ == "__main__":
    main()
