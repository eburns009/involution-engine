"""
House system calculations for astrological charts.

This module handles ASC/MC calculation and house cusp generation for
multiple house systems (Placidus, Whole Sign, Equal).
"""

import math
from datetime import datetime
from typing import Literal

import spiceypy as spice
from fastapi import HTTPException

# Type aliases
Zodiac = Literal["tropical", "sidereal"]
HouseSystem = Literal["placidus", "whole-sign", "equal"]
McHemisphere = Literal["south", "north", "auto"]


def _wrap360(x: float) -> float:
    """Wrap angle to [0, 360)"""
    v = x % 360.0
    return v if v >= 0 else v + 360.0


def _atan2d(y: float, x: float) -> float:
    """Arctangent in degrees with quadrant awareness"""
    return _wrap360(math.degrees(math.atan2(y, x)))


def _obliquity_deg(jd_tt_like: float) -> float:
    """
    Calculate mean obliquity of the ecliptic using IAU 1980 formula.

    Args:
        jd_tt_like: Julian Date in TT-like scale

    Returns:
        Obliquity in degrees
    """
    T = (jd_tt_like - 2451545.0) / 36525.0
    # IAU 1980 mean obliquity of the ecliptic formula
    obliq_deg = 23.43929111 - (46.8150 * T + 0.00059 * T**2 - 0.001813 * T**3) / 3600.0
    return obliq_deg


def _jd_from_iso_utc(iso_z: str) -> float:
    """
    Convert ISO UTC string to Julian Date.

    Args:
        iso_z: ISO format UTC datetime string (with Z or +00:00)

    Returns:
        Julian Date (UTC-based)
    """
    dt = datetime.fromisoformat(iso_z.replace("Z", "+00:00"))
    return dt.timestamp() / 86400.0 + 2440587.5  # Unix epoch to JD (UTC)


def _gmst_deg(jd_ut: float) -> float:
    """
    Calculate Greenwich Mean Sidereal Time in degrees.

    Uses IAU 2006-ish simplified formula.

    Args:
        jd_ut: Julian Date in UT scale

    Returns:
        GMST in degrees
    """
    T = (jd_ut - 2451545.0) / 36525.0
    gmst = (
        280.46061837
        + 360.98564736629 * (jd_ut - 2451545.0)
        + 0.000387933 * T * T
        - (T * T * T) / 38710000.0
    )
    return _wrap360(gmst)


def _asc_mc_tropical_and_sidereal(
    iso_z: str,
    lat_deg: float,
    lon_deg: float,
    ay_name: str,
    calculate_ayanamsa_func,
    mc_hemisphere: McHemisphere = "south",
) -> dict[str, float]:
    """
    Calculate Ascendant and Midheaven in both tropical and sidereal zodiacs.

    Uses geometric intersection of local horizon/meridian with ecliptic plane.

    Args:
        iso_z: ISO UTC datetime string
        lat_deg: Geographic latitude in degrees
        lon_deg: Geographic longitude in degrees
        ay_name: Ayanamsa name ("lahiri" or "fagan_bradley")
        calculate_ayanamsa_func: Function to calculate ayanamsa value
        mc_hemisphere: Which hemisphere to prefer for MC ("south", "north", "auto")

    Returns:
        Dictionary with asc_tropical, mc_tropical, asc (sidereal), mc (sidereal), ay, eps_deg, lst_deg
    """
    jd = _jd_from_iso_utc(iso_z)
    eps = math.radians(_obliquity_deg(jd))
    ay = calculate_ayanamsa_func(ay_name, spice.str2et(iso_z))
    gmst = _gmst_deg(jd)
    lst = math.radians(_wrap360(gmst + lon_deg))
    phi = math.radians(lat_deg)

    # Local triad in equatorial frame
    z_hat = (math.cos(phi) * math.cos(lst), math.cos(phi) * math.sin(lst), math.sin(phi))
    e_hat = (-math.sin(lst), math.cos(lst), 0.0)
    n_hat = (-math.sin(phi) * math.cos(lst), -math.sin(phi) * math.sin(lst), math.cos(phi))
    s_hat = (-n_hat[0], -n_hat[1], -n_hat[2])

    # Ecliptic plane normal in equatorial coords
    n_ecl = (0.0, -math.sin(eps), math.cos(eps))

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def norm(a):
        return math.sqrt(dot(a, a))

    def unit(a):
        s = norm(a)
        return (a[0] / s, a[1] / s, a[2] / s)

    def rotx(v, ang):
        c, s = math.cos(ang), math.sin(ang)
        x, y, z = v
        return (x, c * y - s * z, s * y + c * z)

    # Asc: intersection of horizon (normal z_hat) & ecliptic (normal n_ecl) → choose eastern
    d_asc = unit(cross(n_ecl, z_hat))
    if dot(e_hat, d_asc) < 0:
        d_asc = (-d_asc[0], -d_asc[1], -d_asc[2])

    # MC: intersection of meridian (normal e_hat) & ecliptic → choose by hemisphere
    d_mc = unit(cross(n_ecl, e_hat))
    if mc_hemisphere == "south":
        if dot(s_hat, d_mc) < 0:
            d_mc = (-d_mc[0], -d_mc[1], -d_mc[2])
    elif mc_hemisphere == "north":
        if dot(n_hat, d_mc) < 0:
            d_mc = (-d_mc[0], -d_mc[1], -d_mc[2])
    else:  # auto
        # typical: south for φ≥0, north for φ<0
        pick_south = lat_deg >= 0.0
        ref = s_hat if pick_south else n_hat
        if dot(ref, d_mc) < 0:
            d_mc = (-d_mc[0], -d_mc[1], -d_mc[2])

    # Equatorial → Ecliptic-of-date (rotate by -ε about X)
    de_asc = rotx(d_asc, -eps)
    de_mc = rotx(d_mc, -eps)

    asc_trop = _atan2d(de_asc[1], de_asc[0])
    mc_trop = _atan2d(de_mc[1], de_mc[0])

    asc_sid = _wrap360(asc_trop - ay)
    mc_sid = _wrap360(mc_trop - ay)
    return {
        "asc_tropical": asc_trop,
        "mc_tropical": mc_trop,
        "asc": asc_sid,
        "mc": mc_sid,
        "ay": ay,
        "eps_deg": math.degrees(eps),
        "lst_deg": math.degrees(lst),
    }


def _placidus_cusps(
    iso_z: str,
    lat_deg: float,
    lon_deg: float,
    ay_name: str,
    calculate_ayanamsa_func,
    zodiac: Zodiac,
    mc_hemisphere: McHemisphere = "south",
) -> list[float]:
    """
    Calculate Placidus house cusps.

    Placidus divides diurnal semi-arc around MC to get 11/12,
    and nocturnal semi-arc to get 2/3. Enforces strict oppositions.

    Args:
        iso_z: ISO UTC datetime string
        lat_deg: Geographic latitude in degrees
        lon_deg: Geographic longitude in degrees
        ay_name: Ayanamsa name ("lahiri" or "fagan_bradley")
        calculate_ayanamsa_func: Function to calculate ayanamsa value
        zodiac: "tropical" or "sidereal"
        mc_hemisphere: Which hemisphere to prefer for MC

    Returns:
        List of 12 house cusp longitudes in degrees

    Raises:
        HTTPException: If latitude too close to poles (Placidus undefined)
    """
    jd = _jd_from_iso_utc(iso_z)
    eps = math.radians(_obliquity_deg(jd))
    ay = calculate_ayanamsa_func(ay_name, spice.str2et(iso_z))
    gmst = _gmst_deg(jd)
    RAMC = math.radians(_wrap360(gmst + lon_deg))  # RA of MC
    phi = math.radians(lat_deg)
    cphi = math.cos(phi)
    if abs(cphi) < 1e-2:
        raise HTTPException(
            status_code=422, detail="Placidus undefined near poles (|latitude| too high)"
        )

    def ra_from_hour(h: float) -> float:
        # α = atan2( sin h, cos h * cos φ )  (correct quadrant)
        return math.atan2(math.sin(h), math.cos(h) * cphi)

    def ecl_lambda_from_ra(alpha: float) -> float:
        # β=0 inversion: λ = atan2( sin α / cos ε, cos α )
        return _atan2d(math.sin(alpha) / math.cos(eps), math.cos(alpha))

    # Diurnal around MC → XI, XII
    a11 = ra_from_hour(RAMC + math.radians(+30.0))
    a12 = ra_from_hour(RAMC + math.radians(+60.0))
    l11_t = ecl_lambda_from_ra(a11)
    l12_t = ecl_lambda_from_ra(a12)

    # Nocturnal (around IC): houses 2 (RAIC-60), 3 (RAIC-30)
    RAIC = RAMC + math.pi  # RA of IC
    a02 = ra_from_hour(RAIC + math.radians(-60.0))
    a03 = ra_from_hour(RAIC + math.radians(-30.0))
    l02_t = ecl_lambda_from_ra(a02)
    l03_t = ecl_lambda_from_ra(a03)

    # Tropical MC & Asc for 10/1
    l10_t = ecl_lambda_from_ra(RAMC)
    asc_mc = _asc_mc_tropical_and_sidereal(
        iso_z, lat_deg, lon_deg, ay_name, calculate_ayanamsa_func, mc_hemisphere
    )
    l01_t = asc_mc["asc_tropical"]

    # Opposites (tropical)
    l04_t = _wrap360(l10_t + 180.0)
    l07_t = _wrap360(l01_t + 180.0)

    # All tropical cusps first
    trop_cusps = [l01_t, l02_t, l03_t, l04_t, 0, 0, l07_t, 0, 0, l10_t, l11_t, l12_t]

    # Enforce strict Placidus oppositions (tropical)
    trop_cusps[4] = _wrap360(trop_cusps[10] + 180.0)  # l05 = l11 + 180
    trop_cusps[5] = _wrap360(trop_cusps[11] + 180.0)  # l06 = l12 + 180
    trop_cusps[7] = _wrap360(trop_cusps[1] + 180.0)  # l08 = l02 + 180
    trop_cusps[8] = _wrap360(trop_cusps[2] + 180.0)  # l09 = l03 + 180

    # Apply zodiac conversion
    return _finalize_cusps(trop_cusps, ay, zodiac)


def _whole_sign_cusps(asc_tropical: float, ay: float, zodiac: Zodiac) -> list[float]:
    """
    Calculate Whole Sign house cusps.

    Whole Sign houses use 30° boundaries starting from Asc sign.

    Args:
        asc_tropical: Tropical Ascendant longitude
        ay: Ayanamsa value in degrees
        zodiac: "tropical" or "sidereal"

    Returns:
        List of 12 house cusp longitudes in degrees
    """
    if zodiac == "sidereal":
        asc_final = _wrap360(asc_tropical - ay)
    else:
        asc_final = asc_tropical
    base = math.floor(asc_final / 30.0) * 30.0
    return [_wrap360(base + 30.0 * i) for i in range(12)]


def _equal_cusps(asc_tropical: float, ay: float, zodiac: Zodiac) -> list[float]:
    """
    Calculate Equal house cusps.

    Equal houses use 30° intervals starting from Asc.

    Args:
        asc_tropical: Tropical Ascendant longitude
        ay: Ayanamsa value in degrees
        zodiac: "tropical" or "sidereal"

    Returns:
        List of 12 house cusp longitudes in degrees
    """
    if zodiac == "sidereal":
        asc_final = _wrap360(asc_tropical - ay)
    else:
        asc_final = asc_tropical
    return [_wrap360(asc_final + 30.0 * i) for i in range(12)]


def _finalize_cusps(trop_list: list[float], ay: float, zodiac: Zodiac) -> list[float]:
    """
    Finalize cusps based on zodiac.

    Converts tropical cusps to sidereal if needed.

    Args:
        trop_list: List of tropical cusp longitudes
        ay: Ayanamsa value in degrees
        zodiac: "tropical" or "sidereal"

    Returns:
        List of cusp longitudes in requested zodiac
    """
    if zodiac == "sidereal":
        return [_wrap360(x - ay) for x in trop_list]
    else:
        return [_wrap360(x) for x in trop_list]
