"""
Star position computation and coordinate transformations.

Handles coordinate system conversions between equatorial and ecliptic
systems, with optional proper motion correction.
"""

import math
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Constants
J2000_JD = 2451545.0  # Julian Date of J2000.0 epoch
DAYS_PER_YEAR = 365.25
ARCSEC_PER_DEGREE = 3600.0
MAS_PER_ARCSEC = 1000.0


def to_ecliptic_of_date(ra_hours: float, dec_deg: float, obliquity_deg: float) -> Dict[str, float]:
    """
    Convert equatorial coordinates to ecliptic coordinates.

    Args:
        ra_hours: Right Ascension in hours
        dec_deg: Declination in degrees
        obliquity_deg: Obliquity of the ecliptic in degrees

    Returns:
        Dictionary with ecliptic longitude and latitude in degrees
    """
    # Convert to radians
    ra_rad = math.radians(ra_hours * 15.0)  # Convert hours to degrees, then to radians
    dec_rad = math.radians(dec_deg)
    eps_rad = math.radians(obliquity_deg)

    # Spherical coordinate transformation
    # From J. Meeus, "Astronomical Algorithms", Ch. 13
    x = math.cos(dec_rad) * math.cos(ra_rad)
    y = math.cos(dec_rad) * math.sin(ra_rad)
    z = math.sin(dec_rad)

    # Rotate around X-axis by obliquity
    x_ecl = x
    y_ecl = y * math.cos(eps_rad) + z * math.sin(eps_rad)
    z_ecl = -y * math.sin(eps_rad) + z * math.cos(eps_rad)

    # Convert to longitude and latitude
    longitude_rad = math.atan2(y_ecl, x_ecl)
    latitude_rad = math.asin(z_ecl)

    # Convert to degrees and normalize longitude
    longitude_deg = (math.degrees(longitude_rad) + 360.0) % 360.0
    latitude_deg = math.degrees(latitude_rad)

    return {
        "lon_deg": longitude_deg,
        "lat_deg": latitude_deg
    }


def apply_proper_motion(ra_hours: float, dec_deg: float, pm_ra_mas_yr: float,
                       pm_dec_mas_yr: float, years_from_j2000: float) -> Dict[str, float]:
    """
    Apply proper motion correction from J2000.0 to specified epoch.

    Args:
        ra_hours: Right Ascension at J2000.0 in hours
        dec_deg: Declination at J2000.0 in degrees
        pm_ra_mas_yr: Proper motion in RA (mas/year, includes cos(dec) factor)
        pm_dec_mas_yr: Proper motion in Dec (mas/year)
        years_from_j2000: Years elapsed since J2000.0

    Returns:
        Dictionary with corrected RA and Dec
    """
    # Convert proper motions from mas/year to degrees
    pm_ra_deg = (pm_ra_mas_yr / MAS_PER_ARCSEC) / ARCSEC_PER_DEGREE
    pm_dec_deg = (pm_dec_mas_yr / MAS_PER_ARCSEC) / ARCSEC_PER_DEGREE

    # Apply proper motion
    new_ra_deg = (ra_hours * 15.0) + (pm_ra_deg * years_from_j2000)
    new_dec_deg = dec_deg + (pm_dec_deg * years_from_j2000)

    # Normalize RA to [0, 360) degrees
    new_ra_deg = (new_ra_deg + 360.0) % 360.0

    # Clamp declination to [-90, 90] degrees
    new_dec_deg = max(-90.0, min(90.0, new_dec_deg))

    return {
        "ra_hours": new_ra_deg / 15.0,
        "dec_deg": new_dec_deg
    }


def get_obliquity_of_date(jd: float) -> float:
    """
    Calculate obliquity of the ecliptic for given Julian Date.

    Uses the IAU 2000A model for obliquity.

    Args:
        jd: Julian Date

    Returns:
        Obliquity in degrees
    """
    # Time in Julian centuries from J2000.0
    T = (jd - J2000_JD) / 36525.0

    # Mean obliquity in arcseconds (IAU 2000A)
    # From J. Meeus, "Astronomical Algorithms", Ch. 22
    epsilon0 = (
        84381.448 - 46.8150 * T - 0.00059 * T * T + 0.001813 * T * T * T
    )

    # Convert to degrees
    return epsilon0 / ARCSEC_PER_DEGREE


def parse_utc_to_jd(utc_str: str) -> float:
    """
    Parse UTC datetime string to Julian Date.

    Args:
        utc_str: UTC datetime string (ISO format)

    Returns:
        Julian Date

    Raises:
        ValueError: If datetime format is invalid
    """
    try:
        # Remove 'Z' suffix if present
        if utc_str.endswith('Z'):
            utc_str = utc_str[:-1]

        # Parse datetime
        dt = datetime.fromisoformat(utc_str)

        # Convert to Julian Date
        # Algorithm from Jean Meeus, "Astronomical Algorithms"
        year = dt.year
        month = dt.month
        day = dt.day + dt.hour / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0

        if month <= 2:
            year -= 1
            month += 12

        # Gregorian calendar correction
        A = int(year / 100)
        B = 2 - A + int(A / 4)

        jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5

        return jd

    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid UTC datetime format '{utc_str}': {e}")


def compute_star_positions(stars: List[Dict], utc: str, frame: str = "ecliptic_of_date",
                         epoch: str = "of_date", apply_pm: bool = False) -> List[Dict]:
    """
    Compute star positions for specified date and coordinate frame.

    Args:
        stars: List of star dictionaries from catalog
        utc: UTC datetime string
        frame: Coordinate frame ("ecliptic_of_date" or "equatorial")
        epoch: Coordinate epoch ("of_date" or "J2000")
        apply_pm: Whether to apply proper motion correction

    Returns:
        List of star positions with requested coordinates

    Raises:
        ValueError: If frame/epoch combination is invalid
    """
    # Validate frame/epoch combination
    if frame == "equatorial" and epoch != "J2000":
        raise ValueError("Equatorial frame requires J2000 epoch in current implementation")
    if frame == "ecliptic_of_date" and epoch == "J2000":
        raise ValueError("Ecliptic of date frame requires of_date epoch")

    # Parse UTC to Julian Date
    jd = parse_utc_to_jd(utc)
    years_from_j2000 = (jd - J2000_JD) / DAYS_PER_YEAR

    # Get obliquity if needed for ecliptic coordinates
    if frame == "ecliptic_of_date":
        obliquity = get_obliquity_of_date(jd)
    else:
        obliquity = None

    results = []

    for star in stars:
        try:
            # Start with J2000.0 coordinates
            ra_hours = star["ra_hours"]
            dec_deg = star["dec_deg"]

            # Apply proper motion if requested and available
            if apply_pm and abs(years_from_j2000) > 0.001:  # Only if significant time difference
                pm_ra = star.get("pm_ra_mas_yr", 0.0)
                pm_dec = star.get("pm_dec_mas_yr", 0.0)

                if abs(pm_ra) > 0.1 or abs(pm_dec) > 0.1:  # Only if proper motion is significant
                    corrected = apply_proper_motion(ra_hours, dec_deg, pm_ra, pm_dec, years_from_j2000)
                    ra_hours = corrected["ra_hours"]
                    dec_deg = corrected["dec_deg"]

            # Build base result
            result = {
                "id": star["id"],
                "name": star["name"],
                "vmag": star["vmag"]
            }

            # Add coordinates based on requested frame
            if frame == "equatorial":
                # Return equatorial coordinates (J2000)
                result.update({
                    "ra_hours": ra_hours,
                    "dec_deg": dec_deg
                })
            else:
                # Convert to ecliptic coordinates
                ecliptic = to_ecliptic_of_date(ra_hours, dec_deg, obliquity)
                result.update({
                    "lon_deg": ecliptic["lon_deg"],
                    "lat_deg": ecliptic["lat_deg"]
                })

            # Add proper motion info if applied
            if apply_pm:
                result["proper_motion_applied"] = {
                    "years_from_j2000": round(years_from_j2000, 3),
                    "pm_ra_mas_yr": star.get("pm_ra_mas_yr", 0.0),
                    "pm_dec_mas_yr": star.get("pm_dec_mas_yr", 0.0)
                }

            results.append(result)

        except Exception as e:
            logger.warning(f"Failed to compute position for star {star.get('id', 'unknown')}: {e}")
            continue

    logger.debug(f"Computed positions for {len(results)}/{len(stars)} stars")
    return results