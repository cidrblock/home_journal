"""Command line interface for home journal."""

import argparse
import logging
import os
import shutil

from importlib import resources

from .run import endpoint_convert_all
from .run import run_server


logger = logging.getLogger()


def _list_tags(values: str) -> list[str]:
    """Split a comma separated list of tags.

    Args:
        values: A comma separated list of tags.

    Returns:
        A list of tags.
    """
    return values.split(",")


def _parse_args() -> argparse.Namespace:
    """Parse the command line arguments.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--init",
        help="Initialize the site with css, js, and icons",
        action="store_true",
    )
    parser.add_argument(
        "-l",
        "--log_level",
        type=str.lower,
        help="Log level",
        default="INFO",
        choices=["debug", "info", "warning", "error", "critical"],
    )
    parser.add_argument(
        "-f",
        "--log_file",
        type=str,
        help="Log file",
        default=os.getcwd() + "/hj.log",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="Port to run the server on",
        default=8000,
    )
    parser.add_argument(
        "-s",
        "--site_directory",
        type=str,
        help="Path to the site directory",
        required=True,
    )
    parser.add_argument(
        "-t",
        "--tags",
        help="A list of tags for new posts",
        type=_list_tags,
    )

    args = parser.parse_args()

    return args


def _setup_logging(args: argparse.Namespace) -> None:
    """Set up the logging.

    Args:
        args: The parsed command line arguments.
    """
    log_file = args.log_file
    file_handler = logging.FileHandler(log_file, mode="w")
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s '%(name)s.%(funcName)s' %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    level = logging.getLevelName(args.log_level.upper())
    logger.setLevel(level)
    logger.info("Started")


def _init_site(args: argparse.Namespace) -> None:
    """Initialize the site.

    Args:
        args: The parsed command line arguments.
    """
    if args.init:
        logging.info("Initializing site")
        data_dir = [
            entry for entry in resources.files("home_journal").iterdir() if entry.name == "site"
        ][0]
        shutil.copytree(str(data_dir), args.site_directory, dirs_exist_ok=True)
        logging.info("Site initialized")


def main() -> None:
    """Run the app."""
    args = _parse_args()
    _setup_logging(args)
    for arg in vars(args):
        logger.debug("%s: %s", arg, getattr(args, arg))
    _init_site(args)
    run_server(args)


if __name__ == "__main__":
    main()
