"""Offline nearest-city lookup using bundled GeoNames data."""
import gzip
import math

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


DATA_PATH = Path(__file__).parent / "data" / "cities1000.tsv.gz"


@dataclass(frozen=True)
class City:
    """A populated place from the bundled GeoNames extract."""

    name: str
    admin1: str
    country: str
    lat: float
    lon: float


@dataclass(frozen=True)
class _CityPoint:
    """A city with its coordinates pre-converted to radians."""

    lat: float
    lon: float
    city: City


@lru_cache(maxsize=1)
def _load_cities() -> tuple[_CityPoint, ...]:
    """Load and cache the bundled city list.

    Returns:
        The cities, with radians pre-computed for nearest-neighbour lookup.
    """
    cities = []
    with gzip.open(DATA_PATH, "rt", encoding="utf-8") as handle:
        next(handle, None)
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 5:
                continue
            name, admin1, country, lat_text, lon_text = parts
            try:
                lat = float(lat_text)
                lon = float(lon_text)
            except ValueError:
                continue
            cities.append(
                _CityPoint(
                    lat=math.radians(lat),
                    lon=math.radians(lon),
                    city=City(name=name, admin1=admin1, country=country, lat=lat, lon=lon),
                )
            )
    return tuple(cities)


def nearest_city(lat: float, lon: float) -> City | None:
    """Return the closest bundled city to a coordinate.

    Uses a squared equirectangular distance, which is accurate enough for
    picking a place name and avoids trigonometry per candidate.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Returns:
        The nearest city, or None if the data is unavailable.
    """
    lat_radians = math.radians(lat)
    lon_radians = math.radians(lon)
    cos_lat = math.cos(lat_radians)
    best_distance = None
    best_city = None
    for point in _load_cities():
        delta_lat = point.lat - lat_radians
        delta_lon = point.lon - lon_radians
        if delta_lon > math.pi:
            delta_lon -= 2 * math.pi
        elif delta_lon < -math.pi:
            delta_lon += 2 * math.pi
        distance = delta_lat * delta_lat + (delta_lon * cos_lat) ** 2
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_city = point.city
    return best_city


def city_label(city: City) -> str:
    """Format a city as a display name.

    Args:
        city: The city to format.

    Returns:
        "Name, Region" when a region is known, otherwise "Name, Country".
    """
    if city.admin1:
        return f"{city.name}, {city.admin1}"
    if city.country:
        return f"{city.name}, {city.country}"
    return city.name
