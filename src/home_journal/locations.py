"""Post locations: coordinates, named places, and photo GPS."""
import logging
import math

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

import yaml

from .geocode import city_label
from .geocode import nearest_city


if TYPE_CHECKING:
    from flask.wrappers import Request

logger = logging.getLogger(__name__)

DEFAULT_PLACE_RADIUS_KM = 5.0
GPS_IFD = 0x8825


@dataclass(frozen=True)
class PostLocation:
    """A named location attached to a post."""

    name: str
    lat: float | None = None
    lon: float | None = None
    source: str = ""

    @property
    def maps_url(self) -> str:
        """Return a Google Maps link for the post location.

        Returns:
            A maps URL built from coordinates when available, otherwise a
            search for the name.
        """
        if self.lat is not None and self.lon is not None:
            return (
                "https://www.google.com/maps/search/?api=1"
                f"&query={self.lat:.6f},{self.lon:.6f}"
            )
        if self.name:
            return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(self.name)
        return ""

    def as_metadata(self) -> dict[str, object]:
        """Return the frontmatter representation of the location.

        Returns:
            A mapping suitable for YAML serialization.
        """
        data: dict[str, object] = {"name": self.name}
        if self.lat is not None:
            data["lat"] = round(self.lat, 6)
        if self.lon is not None:
            data["lon"] = round(self.lon, 6)
        if self.source:
            data["source"] = self.source
        return data


@dataclass(frozen=True)
class PersonalPlace:
    """A hand-curated place from places.yml."""

    name: str
    lat: float
    lon: float
    radius_km: float = DEFAULT_PLACE_RADIUS_KM


def _valid_coordinates(lat: float, lon: float) -> bool:
    """Return True for a usable coordinate pair.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Returns:
        True when the values are in range and not the 0,0 sentinel.
    """
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return not (abs(lat) < 1e-6 and abs(lon) < 1e-6)


def _to_float(value: object) -> float | None:
    """Convert an EXIF or form value to a float.

    Args:
        value: The value to convert.

    Returns:
        The float, or None when it is missing or not a usable number.
    """
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def load_places(site_dir: Path) -> list[PersonalPlace]:
    """Load the optional places.yml list from the site directory.

    Args:
        site_dir: The site directory.

    Returns:
        The valid personal places. Invalid entries are logged and skipped.
    """
    path = site_dir / "places.yml"
    if not path.is_file():
        return []
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        logger.warning("Could not read %s: %s", path, error)
        return []
    entries = loaded.get("places") if isinstance(loaded, dict) else loaded
    if not isinstance(entries, list):
        logger.warning("Ignoring %s because it is not a list of places", path)
        return []
    places = []
    for entry in entries:
        if not isinstance(entry, dict):
            logger.warning("Skipping non-mapping place entry in %s", path)
            continue
        name = str(entry.get("name") or "").strip()
        lat = _to_float(entry.get("lat"))
        lon = _to_float(entry.get("lon"))
        radius = _to_float(entry.get("radius_km")) or DEFAULT_PLACE_RADIUS_KM
        if not name or lat is None or lon is None or not _valid_coordinates(lat, lon):
            logger.warning("Skipping invalid place entry in %s: %s", path, entry)
            continue
        if radius <= 0:
            radius = DEFAULT_PLACE_RADIUS_KM
        places.append(PersonalPlace(name=name, lat=lat, lon=lon, radius_km=radius))
    return places


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two coordinates in kilometres.

    Args:
        lat1: First latitude.
        lon1: First longitude.
        lat2: Second latitude.
        lon2: Second longitude.

    Returns:
        The distance in kilometres.
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, a)))


def match_place(
    places: list[PersonalPlace], lat: float, lon: float
) -> PersonalPlace | None:
    """Return the nearest personal place whose radius contains the coordinate.

    Args:
        places: The personal places.
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Returns:
        The matching place, or None.
    """
    best_distance = None
    best_place = None
    for place in places:
        distance = _haversine_km(lat, lon, place.lat, place.lon)
        if distance <= place.radius_km and (best_distance is None or distance < best_distance):
            best_distance = distance
            best_place = place
    return best_place


def find_place_by_name(places: list[PersonalPlace], name: str) -> PersonalPlace | None:
    """Return a personal place by case-insensitive exact name.

    Args:
        places: The personal places.
        name: The requested name.

    Returns:
        The matching place, or None.
    """
    wanted = name.strip().casefold()
    if not wanted:
        return None
    for place in places:
        if place.name.casefold() == wanted:
            return place
    return None


def resolve_coordinates(
    site_dir: Path,
    lat: float,
    lon: float,
    places: list[PersonalPlace] | None = None,
    source: str = "coords",
) -> PostLocation | None:
    """Name a coordinate using personal places, then the bundled city list.

    Args:
        site_dir: The site directory, used to load places.yml when needed.
        lat: Latitude in degrees.
        lon: Longitude in degrees.
        places: Optional preloaded personal places.
        source: Where the coordinate came from.

    Returns:
        A named location, or None for invalid coordinates.
    """
    if not _valid_coordinates(lat, lon):
        return None
    place = match_place(places if places is not None else load_places(site_dir), lat, lon)
    if place is not None:
        return PostLocation(name=place.name, lat=lat, lon=lon, source="places")
    city = nearest_city(lat, lon)
    name = city_label(city) if city is not None else f"{lat:.5f}, {lon:.5f}"
    return PostLocation(name=name, lat=lat, lon=lon, source=source)


def location_from_form(
    request: "Request", site_dir: Path, places: list[PersonalPlace] | None = None
) -> PostLocation | None:
    """Build a post location from the new/edit form fields.

    Form fields are location_name, location_lat, location_lon, and
    location_source. A name without coordinates is kept as a name-only
    location. A coordinate without a name is named from places.yml or the
    bundled cities.

    Args:
        request: The Flask request.
        site_dir: The site directory.
        places: Optional preloaded personal places.

    Returns:
        The location, or None when the fields are empty.
    """
    available = places if places is not None else load_places(site_dir)
    name = (request.form.get("location_name") or "").strip()
    lat = _to_float(request.form.get("location_lat"))
    lon = _to_float(request.form.get("location_lon"))
    source = (request.form.get("location_source") or "").strip()
    if lat is not None and lon is not None and not _valid_coordinates(lat, lon):
        lat = None
        lon = None
    if lat is not None and lon is not None:
        place = match_place(available, lat, lon)
        if place is not None and (not name or name.casefold() == place.name.casefold()):
            return PostLocation(name=place.name, lat=lat, lon=lon, source="places")
        if not name:
            return resolve_coordinates(
                site_dir,
                lat,
                lon,
                places=available,
                source=source or "coords",
            )
        return PostLocation(name=name, lat=lat, lon=lon, source=source or "manual")
    if name:
        place = find_place_by_name(available, name)
        if place is not None:
            return PostLocation(name=place.name, lat=place.lat, lon=place.lon, source="places")
        return PostLocation(name=name, source="manual")
    return None


def parse_location(metadata: dict[str, object]) -> PostLocation | None:
    """Read a location mapping from post frontmatter.

    Args:
        metadata: Parsed post frontmatter.

    Returns:
        The location, or None when the post has none.
    """
    raw = metadata.get("location")
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    lat = _to_float(raw.get("lat"))
    lon = _to_float(raw.get("lon"))
    if lat is not None and lon is not None and not _valid_coordinates(lat, lon):
        lat = None
        lon = None
    if not name and lat is None:
        return None
    return PostLocation(name=name, lat=lat, lon=lon, source=str(raw.get("source") or ""))
