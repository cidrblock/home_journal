"""Guards what a page is allowed to pull down before it is useful."""

from datetime import datetime
from types import SimpleNamespace

from home_journal.utils import jinja_env


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
