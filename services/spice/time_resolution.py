"""
Time resolution and timezone utilities.

This module handles conversion of local datetimes to UTC with historical
timezone accuracy, including DST handling and regional timezone complexity.
"""

import math
from datetime import datetime
from pathlib import Path

import pytz
from fastapi import HTTPException
from scipy.spatial import KDTree
from timezonefinder import TimezoneFinder

# Global timezone finder (initialize once)
tf = TimezoneFinder()

# GeoNames cities database for historical timezone lookups
geonames_cities_coords: list[tuple[float, float]] = []
geonames_cities_timezones: list[str] = []
geonames_kdtree: KDTree | None = None

# Load GeoNames database on module import
try:
    cities_file = Path(__file__).parent / "cities15000.txt"
    with open(cities_file, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) > 17:
                try:
                    lat = float(parts[4])
                    lon = float(parts[5])
                    tz = parts[17]
                    if tz:  # Only add if timezone is present
                        geonames_cities_coords.append((lat, lon))
                        geonames_cities_timezones.append(tz)
                except (ValueError, IndexError):
                    continue

    # Build KDTree for O(log n) nearest neighbor search
    if geonames_cities_coords:
        geonames_kdtree = KDTree(geonames_cities_coords)
        print(f"✓ Loaded {len(geonames_cities_coords)} GeoNames cities with KDTree index")
    else:
        print("⚠ No valid cities found in GeoNames database")
except FileNotFoundError:
    print("⚠ GeoNames cities15000.txt not found - will use fallback timezone detection")
except Exception as e:
    print(f"⚠ Error loading GeoNames database: {e}")
    geonames_kdtree = None


# Regional timezone overrides for areas with complex historical timezone boundaries
# Format: (lat_min, lat_max, lon_min, lon_max, lon_divisions)
# lon_divisions: list of (lon_threshold, timezone_name)
REGIONAL_TIMEZONES = [
    {
        "name": "Kentucky",
        "bounds": (36.5, 39.5, -89.5, -81.5),
        "divisions": [
            (-85.0, "America/Kentucky/Louisville"),
            (float("inf"), "America/Kentucky/Monticello"),
        ],
    },
    {
        "name": "Indiana",
        "bounds": (37.5, 42.0, -88.0, -84.5),
        "divisions": [
            (-86.0, "America/Indiana/Knox"),
            (-85.0, "America/Indiana/Indianapolis"),
            (float("inf"), "America/Indiana/Vevay"),
        ],
    },
    {
        "name": "Michigan",
        "bounds": (45.0, 48.5, -90.5, -83.5),
        "divisions": [(-87.0, "America/Menominee"), (float("inf"), "America/Detroit")],
    },
    {
        "name": "North Dakota",
        "bounds": (45.5, 49.5, -104.5, -96.5),
        "divisions": [
            (-101.0, "America/North_Dakota/New_Salem"),
            (float("inf"), "America/Chicago"),
        ],
    },
]


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance in km between two points using Haversine formula.

    Args:
        lat1, lon1: First point coordinates in degrees
        lat2, lon2: Second point coordinates in degrees

    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth radius in km (mean radius)

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def find_nearest_city_timezone(lat: float, lon: float, max_distance_km: float = 100) -> str | None:
    """
    Find timezone of nearest city from GeoNames database using KDTree spatial index.

    Uses KDTree for O(log n) nearest neighbor search (vs O(n) linear scan).
    Distance is calculated using Haversine formula for accuracy on a sphere.

    Args:
        lat: Latitude in degrees (-90 to 90)
        lon: Longitude in degrees (-180 to 180)
        max_distance_km: Maximum distance in km to search (default 100km)

    Returns:
        IANA timezone name if city found within max_distance_km, else None
    """
    if geonames_kdtree is None or not geonames_cities_timezones:
        return None

    # Query KDTree for nearest city (euclidean distance as approximation)
    distance, index = geonames_kdtree.query([lat, lon])

    # Verify distance using proper Haversine formula (great-circle distance)
    city_lat, city_lon = geonames_cities_coords[index]
    actual_distance_km = _haversine_distance(lat, lon, city_lat, city_lon)

    # Only return if within max distance
    if actual_distance_km <= max_distance_km:
        return geonames_cities_timezones[index]
    return None


def _in_bounds(lat: float, lon: float, bounds: tuple[float, float, float, float]) -> bool:
    """Check if coordinates fall within geographic bounds."""
    lat_min, lat_max, lon_min, lon_max = bounds
    return lat_min < lat < lat_max and lon_min < lon < lon_max


def _find_timezone_by_longitude(lon: float, divisions: list[tuple[float, str]]) -> str:
    """Find timezone based on longitude divisions."""
    for threshold, tz in divisions:
        if lon < threshold:
            return tz
    return divisions[-1][1]  # Should never reach here, but return last as safety


def get_historical_timezone(lat: float, lon: float) -> str | None:
    """
    Get timezone with historical accuracy using regional IANA timezones.

    Uses a three-tier resolution strategy:
    1. Regional overrides for known complex timezone areas (US states with historical boundary changes)
    2. GeoNames nearest city lookup via KDTree spatial index (worldwide coverage, O(log n))
    3. Fallback to timezonefinder (modern boundaries only)

    Args:
        lat: Latitude in degrees (-90 to 90)
        lon: Longitude in degrees (-180 to 180)

    Returns:
        IANA timezone name (e.g., "America/Chicago") or None if no timezone found
    """
    # Check regional overrides (US states with complex timezone history)
    for region in REGIONAL_TIMEZONES:
        if _in_bounds(lat, lon, region["bounds"]):
            return _find_timezone_by_longitude(lon, region["divisions"])

    # Try GeoNames nearest city lookup for worldwide coverage
    geonames_tz = find_nearest_city_timezone(lat, lon, max_distance_km=100)
    if geonames_tz:
        return geonames_tz

    # Final fallback: timezonefinder (modern boundaries only)
    return tf.timezone_at(lat=lat, lng=lon)


def parse_local_datetime(datetime_str: str) -> datetime:
    """
    Parse local datetime string (without timezone) in ISO format.

    Accepts: YYYY-MM-DDTHH:MM or YYYY-MM-DDTHH:MM:SS

    Args:
        datetime_str: ISO format datetime string without timezone

    Returns:
        Naive datetime object (no timezone info)

    Raises:
        HTTPException 422: Invalid datetime format or timezone info included
    """
    try:
        if len(datetime_str) == 16:  # YYYY-MM-DDTHH:MM
            return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M")
        elif len(datetime_str) == 19:  # YYYY-MM-DDTHH:MM:SS
            return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
        else:
            # Try fromisoformat for flexibility (e.g., with milliseconds)
            local_dt_str = datetime_str.replace("Z", "").replace("+00:00", "")
            if "+" in local_dt_str or local_dt_str.count("-") > 2:
                raise ValueError("Datetime should not include timezone info")
            return datetime.fromisoformat(local_dt_str)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid datetime format. Expected ISO format without timezone (YYYY-MM-DDTHH:MM:SS), got: {datetime_str}",
        )


def localize_datetime_with_dst_handling(
    local_dt: datetime, tz: pytz.BaseTzInfo
) -> tuple[datetime, bool]:
    """
    Localize naive datetime to timezone with DST edge case handling.

    Handles:
    - Ambiguous times (DST fall-back): Uses standard time
    - Non-existent times (DST spring-forward): Uses DST time

    Args:
        local_dt: Naive datetime object (no timezone)
        tz: pytz timezone object

    Returns:
        Tuple of (localized_datetime, is_dst)
    """
    try:
        # Use is_dst=None to raise exception on ambiguous times
        localized_dt = tz.localize(local_dt, is_dst=None)
        return localized_dt, bool(localized_dt.dst())
    except pytz.exceptions.AmbiguousTimeError:
        # Time occurred twice (DST "fall back") - use standard time
        localized_dt = tz.localize(local_dt, is_dst=False)
        return localized_dt, False
    except pytz.exceptions.NonExistentTimeError:
        # Time didn't exist (DST "spring forward") - use the next valid time
        localized_dt = tz.localize(local_dt, is_dst=True)
        return localized_dt, True
