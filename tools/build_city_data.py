"""Build the bundled city list from GeoNames extracts.

Usage:
    python tools/build_city_data.py cities1000.txt admin1CodesASCII.txt \
        countryInfo.txt src/home_journal/data/cities1000.tsv.gz

Source files are the GeoNames dumps:
    https://download.geonames.org/export/dump/cities1000.zip
    https://download.geonames.org/export/dump/admin1CodesASCII.txt
    https://download.geonames.org/export/dump/countryInfo.txt

GeoNames data is licensed CC BY 4.0. See the NOTICE next to the output.
"""
import csv
import gzip
import sys

from pathlib import Path


def _read_admin1(path: Path) -> dict[str, str]:
    """Map "CC.ADM1" to the administrative division name.

    Args:
        path: Path to admin1CodesASCII.txt.

    Returns:
        A mapping of country and admin1 codes to names.
    """
    names = {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 2:
                continue
            names[row[0]] = row[1]
    return names


def _read_countries(path: Path) -> dict[str, str]:
    """Map ISO country code to country name.

    Args:
        path: Path to countryInfo.txt.

    Returns:
        A mapping of ISO country codes to names.
    """
    names = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#") or not line.strip():
                continue
            row = line.rstrip("\n").split("\t")
            if len(row) > 4:
                names[row[0]] = row[4]
    return names


def build(cities_path: Path, admin1_path: Path, countries_path: Path, output: Path) -> int:
    """Write a compact gzip TSV of name, admin1, country, lat, lon.

    Args:
        cities_path: Path to the GeoNames cities1000.txt dump.
        admin1_path: Path to admin1CodesASCII.txt.
        countries_path: Path to countryInfo.txt.
        output: Path to write the gzip TSV.

    Returns:
        The number of rows written.
    """
    admin1 = _read_admin1(admin1_path)
    countries = _read_countries(countries_path)
    # PPLX is a neighbourhood/section, PPLQ/PPLH/PPLW are abandoned,
    # historical, or destroyed places. Keeping them makes a nearest-city
    # lookup return a subdivision instead of the city people name.
    excluded_features = {"PPLX", "PPLQ", "PPLH", "PPLW"}
    rows = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with cities_path.open(encoding="utf-8") as source, gzip.open(
        output, "wt", encoding="utf-8", compresslevel=9
    ) as destination:
        destination.write("name\tadmin1\tcountry\tlat\tlon\n")
        for row in csv.reader(source, delimiter="\t"):
            if len(row) < 11 or row[7].strip() in excluded_features:
                continue
            name = row[1].strip()
            country_code = row[8].strip()
            admin1_code = row[10].strip()
            lat = row[4].strip()
            lon = row[5].strip()
            if not name or not lat or not lon:
                continue
            state = admin1.get(f"{country_code}.{admin1_code}", "")
            country = countries.get(country_code, country_code)
            destination.write(
                "\t".join([name, state, country, lat, lon]) + "\n"
            )
            rows += 1
    return rows


def main() -> None:
    """Build the data file from command line arguments.

    Raises:
        SystemExit: If the argument count is wrong.
    """
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: build_city_data.py cities1000.txt admin1CodesASCII.txt "
            "countryInfo.txt OUTPUT"
        )
    rows = build(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]),
    )
    print(f"wrote {rows} cities to {sys.argv[4]}")


if __name__ == "__main__":
    main()
