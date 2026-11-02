"""The icon font ships as a ~3 KB subset, so using a new icon needs a rebuild."""

import re

from pathlib import Path

import home_journal

PACKAGE = Path(home_journal.__file__).parent
REPO = Path(__file__).resolve().parent.parent
ICON_NAMES = REPO / "tools" / "icon_names.txt"
FONT = PACKAGE / "site" / "css" / "material-symbols-outlined.woff2"


def _declared() -> set[str]:
    return {
        line.strip()
        for line in ICON_NAMES.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _used() -> set[str]:
    pages = list((PACKAGE / "templates").glob("*.j2")) + [PACKAGE / "site" / "index.html"]
    used = set()
    for page in pages:
        used.update(re.findall(r"<i[^>]*>([a-z_]+)</i>", page.read_text(encoding="utf-8")))
    # Tag, author and search pages get their heading icon from python, not a template.
    for module in ("run.py", "utils.py"):
        source = (PACKAGE / module).read_text(encoding="utf-8")
        used.update(re.findall(r'title_icon="([a-z_]+)"', source))
    return used


def test_every_used_icon_is_declared_for_the_subset() -> None:
    assert _used() <= _declared()


def test_the_shipped_font_is_a_subset() -> None:
    assert FONT.stat().st_size < 20_000
