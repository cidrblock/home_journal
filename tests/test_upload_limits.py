from home_journal.run import app


MAX_UPLOAD_SIZE = 250 * 1024 * 1024


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