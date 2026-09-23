import logging

from pathlib import Path

from home_journal.run import app
from home_journal.utils import build_image_previews
from home_journal.utils import _render_markdown
from PIL import Image


MAX_UPLOAD_SIZE = 250 * 1024 * 1024


def test_pano_images_render_as_pannellum_viewers() -> None:
    rendered = _render_markdown(
        "![](media/PXL_20260920_150334255.PANO.jpg)\n\n![](media/ordinary.jpg)"
    )

    assert '<p class="progressive-image pannellum-panorama"' in rendered
    assert 'src="media/preview_PXL_20260920_150334255.PANO.jpg"' in rendered
    assert 'data-panorama="media/PXL_20260920_150334255.PANO.jpg"' in rendered
    assert 'data-full-src="media/ordinary.jpg"' in rendered
    assert '<p class="progressive-image"><img src="media/preview_ordinary.jpg"' in rendered


def test_image_previews_are_created_once(tmp_path: Path) -> None:
    image_dir = tmp_path / "posts" / "post" / "media"
    image_dir.mkdir(parents=True)
    Image.new("RGB", (1200, 800), "red").save(image_dir / "photo.jpg")

    assert build_image_previews(tmp_path) == 1
    assert build_image_previews(tmp_path) == 0
    with Image.open(image_dir / "preview_photo.jpg") as preview:
        assert preview.size == (640, 427)


def test_new_form_exposes_maximum_upload_size() -> None:
    with app.test_client() as client:
        response = client.get("/new.html")

    assert response.status_code == 200
    assert f'data-max-upload-size="{MAX_UPLOAD_SIZE}"'.encode() in response.data


def test_oversized_post_returns_payload_too_large() -> None:
    previous_limit = app.config["MAX_CONTENT_LENGTH"]
    app.config["MAX_CONTENT_LENGTH"] = 1
    try:
        with app.test_client() as client:
            response = client.post(
                "/",
                data={"title": "too large"},
                content_type="multipart/form-data",
            )
    finally:
        app.config["MAX_CONTENT_LENGTH"] = previous_limit

    assert response.status_code == 413


def test_oversized_post_is_logged(caplog) -> None:
    previous_limit = app.config["MAX_CONTENT_LENGTH"]
    app.config["MAX_CONTENT_LENGTH"] = 1
    try:
        with caplog.at_level(logging.WARNING, logger="home_journal.run"):
            with app.test_client() as client:
                response = client.post(
                    "/",
                    data={"title": "too large"},
                    content_type="multipart/form-data",
                )
    finally:
        app.config["MAX_CONTENT_LENGTH"] = previous_limit

    assert response.status_code == 413
    assert "Rejected oversized request" in caplog.text