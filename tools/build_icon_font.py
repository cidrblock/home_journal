"""Subset the bundled Material Symbols font to the icons the site actually uses.

Usage:
    uv run --with fonttools --with brotli tools/build_icon_font.py FULL_FONT.woff2 \
        src/home_journal/site/css/material-symbols-outlined.woff2

FULL_FONT.woff2 is the unsubsetted "Material Symbols Outlined" from the
material-symbols npm package. Every icon is a ligature, so a plain
``pyftsubset --text="add place ..."`` keeps every icon whose name can be spelled
from the retained letters -- 143 KB of the original 237 KB. Filtering the
ligature table down to tools/icon_names.txt first leaves 14 icons and drops the
file to about 3 KB.

Material Symbols is licensed under the SIL Open Font License 1.1.
"""

import sys
import tempfile

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

NAMES_FILE = Path(__file__).with_name("icon_names.txt")


def _read_names(path: Path) -> list[str]:
    """Read the icon names to keep.

    Args:
        path: Path to a file with one ligature name per line.

    Returns:
        The icon names, with blanks and comments removed.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _part(glyph_name: str) -> str:
    """Turn a ligature component glyph name into its text form.

    Args:
        glyph_name: The glyph name, for example "P" or "underscore".

    Returns:
        The character the glyph contributes to the ligature name.
    """
    return "_" if glyph_name == "underscore" else glyph_name.lower()


def _ligature_name(first: str, ligature: object) -> str:
    """Spell the text ligature name of a GSUB ligature record.

    Args:
        first: The glyph name that keys the ligature set.
        ligature: A fontTools Ligature record.

    Returns:
        The typed text that produces this ligature, for example "arrow_back".
    """
    components = ligature.Component  # type: ignore[attr-defined]
    return _part(first) + "".join(_part(component) for component in components)


def _keep_only(font: TTFont, names: set[str]) -> dict[str, str]:
    """Drop every ligature the site does not use.

    Args:
        font: The font to edit in place.
        names: The ligature names to keep.

    Returns:
        A mapping of ligature name to glyph name for the ligatures kept.
    """
    kept = {}
    lookups = font["GSUB"].table.LookupList.Lookup
    for lookup in lookups:
        for subtable in lookup.SubTable:
            # Type 7 (extension) wraps the real substitution table.
            subtable = getattr(subtable, "ExtSubTable", subtable)
            ligatures = getattr(subtable, "ligatures", None)
            if ligatures is None:
                continue
            for first, records in list(ligatures.items()):
                wanted = [rec for rec in records if _ligature_name(first, rec) in names]
                for record in wanted:
                    kept[_ligature_name(first, record)] = record.LigGlyph
                if wanted:
                    ligatures[first] = wanted
                else:
                    del ligatures[first]
    return kept


def main() -> None:
    """Subset the font given on the command line into the packaged location."""
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} FULL_FONT.woff2 OUTPUT.woff2")

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    names = set(_read_names(NAMES_FILE))

    font = TTFont(str(source))
    kept = _keep_only(font, names)
    missing = sorted(names - set(kept))
    if missing:
        raise SystemExit(f"ligature not found in {source}: {', '.join(missing)}")

    with tempfile.TemporaryDirectory() as tmp:
        filtered = Path(tmp) / "filtered.ttf"
        font.save(str(filtered))
        subset.main(
            [
                str(filtered),
                "--text=" + " ".join(sorted(names)),
                # "*" keeps rclt/rlig, which is what turns "arrow_back" into a glyph.
                "--layout-features=*",
                "--flavor=woff2",
                "--output-file=" + str(output),
            ]
        )
    print(f"{output}: {len(kept)} icons, {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
