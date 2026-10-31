"""Guards the first-paint path.

The page used to start at ``visibility: hidden`` and only become visible from a
DOMContentLoaded handler, which meant nothing was painted until every stylesheet and
script had downloaded and executed. On a slow link that is seconds of blank screen.
"""

from pathlib import Path

import home_journal


PACKAGE = Path(home_journal.__file__).parent
PAGES = sorted((PACKAGE / "templates").glob("*.html.j2")) + [
    PACKAGE / "site" / "index.html"
]


def test_stylesheet_does_not_hide_the_page() -> None:
    css = (PACKAGE / "site" / "css" / "site.css").read_text()

    assert "visibility: hidden" not in css


def test_pages_pick_the_theme_inline_before_the_first_paint() -> None:
    for page in PAGES:
        html = page.read_text()

        assert "document.body.className" in html, page.name


def test_stylesheet_and_script_urls_are_versioned_for_cache_busting() -> None:
    for page in PAGES:
        html = page.read_text()

        assert "/css/site.css?v=" in html, page.name
        assert "/js/site.js?v=" in html, page.name
