"""Guards what a page is allowed to pull down before it is useful."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from home_journal.utils import _render_markdown
from home_journal.utils import _thumbnail_name
from home_journal.utils import jinja_env
from PIL import Image


def _post(**kwargs: object) -> SimpleNamespace:
    fields = {
        "title": "A post",
        "date": datetime(2026, 1, 1),
        "author": "Brad",
        "author_index": "brad.html",
        "location": None,
        "tags": [],
        "post_id": "2026-01-01T00:00:00_a-post",
        "previous": "previous",
        "next": "next",
        "thumbnail_url": "/posts/thumb.jpg",
        "post_url": "/posts/a-post/index.html",
    }
    fields.update(kwargs)
    return SimpleNamespace(**fields)


def test_index_thumbnails_are_lazy() -> None:
    html = jinja_env.get_template("index.html.j2").render(
        posts=[_post()], title="everything", title_icon=None
    )

    assert 'loading="lazy"' in html
    assert 'decoding="async"' in html


def test_pannellum_is_only_loaded_for_panoramas() -> None:
    template = jinja_env.get_template("post.html.j2")

    plain = template.render(
        post=_post(),
        content='<p class="progressive-image"><img src="media/a.jpg" /></p>',
    )

    assert "pannellum.js" not in plain
    assert "pannellum.css" not in plain

    panorama = template.render(
        post=_post(),
        content='<p class="progressive-image pannellum-panorama"><img src="media/a.jpg" /></p>',
    )

    assert "/js/pannellum.js" in panorama
    assert "/css/pannellum.css" in panorama


def test_thumbnails_keep_their_size_but_ship_as_webp() -> None:
    assert _thumbnail_name("PXL_20261031_012553112.jpg") == "thumb_PXL_20261031_012553112.webp"


def test_videos_are_left_to_load_on_tap(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    Image.new("RGB", (640, 360)).save(media / "preview_clip.jpg")
    html = _render_markdown(
        '<div class="video"><video controls autoplay muted loop>'
        '<source src="media/clip.mp4" type="video/mp4" /></video></div>',
        media_dir=media,
    )

    assert "autoplay" not in html
    assert "loop" not in html
    assert "muted" not in html
    assert 'preload="none"' in html
    assert 'data-poster="media/preview_clip.jpg"' in html
    assert "playsinline" in html


def test_video_without_a_still_still_fetches_nothing(tmp_path: Path) -> None:
    html = _render_markdown(
        '<div class="video"><video controls>'
        '<source src="media/clip.mp4" type="video/mp4" /></video></div>',
        media_dir=tmp_path,
    )

    assert 'preload="none"' in html
    assert "data-poster=" not in html


def test_previews_reserve_their_box(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    Image.new("RGB", (640, 480)).save(media / "preview_a.jpg")

    html = _render_markdown("![](media/a.jpg)", media_dir=media)

    assert 'width="640" height="480"' in html


def test_posts_ship_previews_and_defer_the_original(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    Image.new("RGB", (640, 480)).save(media / "preview_a.jpg")

    html = _render_markdown("![](media/a.jpg)", media_dir=media)

    assert '<img src="media/preview_a.jpg"' in html
    assert 'data-full-src="media/a.jpg"' in html
    assert '<img src="media/a.jpg"' not in html
    assert 'loading="lazy"' in html
    assert "data-src=" not in html


def test_linked_images_show_the_preview_too(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    Image.new("RGB", (320, 240)).save(media / "preview_b.jpg")

    html = _render_markdown("[![](media/b.jpg)](media/b.jpg)", media_dir=media)

    assert '<a href="media/b.jpg">' in html
    assert '<img src="media/preview_b.jpg"' in html
    assert 'data-full-src="media/b.jpg"' in html
    assert '<img src="media/b.jpg"' not in html


def test_post_script_does_not_fetch_originals_while_scrolling() -> None:
    script = (
        Path(__file__).parent.parent / "src" / "home_journal" / "site" / "js" / "post.js"
    ).read_text()

    assert "pointerdown" not in script
    assert "loadProgressiveImages" not in script
    assert "preloadFullImage" in script
