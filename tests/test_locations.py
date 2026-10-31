"""Tests for post locations and the bundled city lookup."""
from pathlib import Path

from home_journal.geocode import city_label
from home_journal.geocode import nearest_city
from home_journal.locations import PostLocation
from home_journal.locations import load_places
from home_journal.locations import location_from_form
from home_journal.locations import parse_location
from home_journal.locations import resolve_coordinates
from home_journal.run import app


BEND = (44.0582, -121.3153)


class FakeRequest:
    """Minimal request object for form tests."""

    def __init__(self, form: dict[str, str]) -> None:
        """Store the form data.

        Args:
            form: The form fields.
        """
        self.form = form


def test_nearest_city_names_bend() -> None:
    """The bundled data names Bend, Oregon."""
    city = nearest_city(*BEND)

    assert city is not None
    assert city.name == "Bend"
    assert city.admin1 == "Oregon"
    assert city_label(city) == "Bend, Oregon"


def test_location_maps_url_uses_coordinates_then_name() -> None:
    """Maps URLs use coordinates when present, otherwise the name."""
    located = PostLocation(name="Bend, Oregon", lat=44.05, lon=-121.31)
    named = PostLocation(name="Some Place & More")

    assert located.maps_url == (
        "https://www.google.com/maps/search/?api=1&query=44.050000,-121.310000"
    )
    assert named.maps_url == (
        "https://www.google.com/maps/search/?api=1&query=Some+Place+%26+More"
    )


def test_parse_location_reads_frontmatter_mapping() -> None:
    """Frontmatter locations are parsed and empty names are ignored."""
    location = parse_location(
        {"location": {"name": "Bend, Oregon", "lat": 44.05, "lon": -121.31, "source": "gps"}}
    )

    assert location is not None
    assert location.name == "Bend, Oregon"
    assert location.lat == 44.05
    assert location.lon == -121.31
    assert location.source == "gps"
    assert parse_location({"location": {"name": ""}}) is None


def test_resolve_coordinates_prefers_personal_places(tmp_path: Path) -> None:
    """A personal place overrides the nearest city name.

    Args:
        tmp_path: The temporary site directory.
    """
    (tmp_path / "places.yml").write_text(
        "places:\n"
        "  - name: Home Base\n"
        "    lat: 44.05\n"
        "    lon: -121.31\n"
        "    radius_km: 5\n",
        encoding="utf-8",
    )

    location = resolve_coordinates(tmp_path, 44.051, -121.312)
    city = resolve_coordinates(tmp_path, 45.5231, -122.6765)

    assert location is not None
    assert location.name == "Home Base"
    assert location.source == "places"
    assert city is not None
    assert city.name == "Portland, Oregon"


def test_location_from_form_matches_place_and_accepts_name_only(tmp_path: Path) -> None:
    """Form places resolve coordinates; unknown names stay name-only.

    Args:
        tmp_path: The temporary site directory.
    """
    (tmp_path / "places.yml").write_text(
        "places:\n"
        "  - name: Home Base\n"
        "    lat: 44.05\n"
        "    lon: -121.31\n",
        encoding="utf-8",
    )

    placed = location_from_form(FakeRequest({"location_name": "Home Base"}), tmp_path)
    named = location_from_form(FakeRequest({"location_name": "Somewhere"}), tmp_path)

    assert placed is not None
    assert placed.lat == 44.05
    assert placed.lon == -121.31
    assert named is not None
    assert named.name == "Somewhere"
    assert named.lat is None
    assert named.maps_url.startswith("https://www.google.com/maps/search/?api=1&query=")


def test_load_places_skips_invalid_entries(tmp_path: Path) -> None:
    """Invalid places.yml entries are skipped.

    Args:
        tmp_path: The temporary site directory.
    """
    (tmp_path / "places.yml").write_text(
        "places:\n"
        "  - name: Good\n"
        "    lat: 1\n"
        "    lon: 2\n"
        "  - name: Bad\n"
        "    lat: 200\n"
        "    lon: 2\n",
        encoding="utf-8",
    )

    places = load_places(tmp_path)

    assert [place.name for place in places] == ["Good"]


def test_resolve_location_endpoint_returns_a_name() -> None:
    """The resolve endpoint returns a city name for coordinates."""
    with app.test_client() as client:
        response = client.get("/location/resolve?lat=44.0582&lon=-121.3153")

    assert response.status_code == 200
    assert response.get_json()["name"] == "Bend, Oregon"


def test_places_config_is_not_served() -> None:
    """places.yml is hidden from static serving."""
    with app.test_client() as client:
        assert client.get("/places.yml").status_code == 404
        assert client.get("/places.yaml").status_code == 404


def test_new_post_requires_a_location(tmp_path: Path, monkeypatch) -> None:
    """A new post without a location is rejected.

    Args:
        tmp_path: The temporary site directory.
        monkeypatch: pytest's patching fixture.
    """
    monkeypatch.setitem(app.config, "site_dir", tmp_path)
    monkeypatch.setitem(app.config, "tags", [])
    monkeypatch.setitem(app.config, "authors", [])
    with app.test_client() as client:
        response = client.post(
            "/",
            data={"title": "No location", "author": "Brad", "content": "hello"},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    assert response.get_data(as_text=True) == "Location required"


def test_new_post_with_a_location_is_created(tmp_path: Path, monkeypatch) -> None:
    """A new post with a name-only location is created.

    Args:
        tmp_path: The temporary site directory.
        monkeypatch: pytest's patching fixture.
    """
    monkeypatch.setitem(app.config, "site_dir", tmp_path)
    monkeypatch.setitem(app.config, "tags", [])
    monkeypatch.setitem(app.config, "authors", [])
    with app.test_client() as client:
        response = client.post(
            "/",
            data={
                "title": "With location",
                "author": "Brad",
                "content": "hello",
                "location_name": "Bend, Oregon",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 302
    posts = list((tmp_path / "posts").rglob("post.md"))
    assert len(posts) == 1
