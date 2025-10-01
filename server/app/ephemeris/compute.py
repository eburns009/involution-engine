"""
SPICE-based ephemeris calculations for planetary positions.

This module handles the core astronomical calculations using NASA's SPICE toolkit.
It supports both tropical and sidereal zodiac systems with configurable ayanāṃśa.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dateutil.parser import parse as parse_datetime

# SPICE toolkit imports - in production, install with: pip install spiceypy
try:
    import spiceypy as spice
    SPICE_AVAILABLE = True
except ImportError:
    SPICE_AVAILABLE = False
    logging.warning("SpiceyPy not available - using mock calculations")

from .ayanamsha import get_ayanamsha_value, apply_ayanamsha
from .kernels import get_kernel_type

logger = logging.getLogger(__name__)

# Global state for kernel loading
KERNELS_LOADED = False
LOADED_KERNELS = []
CURRENT_BUNDLE = None


# SPICE body name mappings
SPICE_BODY_CODES = {
    "Sun": 10,
    "Moon": 301,
    "Mercury": 199,
    "Venus": 299,
    "Mars": 499,
    "Jupiter": 599,
    "Saturn": 699,
    "Uranus": 799,
    "Neptune": 899,
    "Pluto": 999,
    # Lunar nodes are computed differently
    "TrueNode": "MOON_TRUE_NODE",
    "MeanNode": "MOON_MEAN_NODE"
}

# Supported celestial bodies
SUPPORTED_BODIES = list(SPICE_BODY_CODES.keys())


def compute_positions_init(kernels_dir: str, bundle: str) -> None:
    """
    Initialize SPICE kernels in worker process.

    This function is called once per worker process to load the necessary
    SPICE kernels for ephemeris calculations.

    Args:
        kernels_dir: Directory containing SPICE kernels
        bundle: Kernel bundle name
    """
    global KERNELS_LOADED, LOADED_KERNELS, CURRENT_BUNDLE

    if KERNELS_LOADED and CURRENT_BUNDLE == bundle:
        logger.debug(f"Kernels already loaded for bundle {bundle}")
        return

    try:
        # Clear any previously loaded kernels
        if KERNELS_LOADED:
            _clear_kernels()

        bundle_path = os.path.join(kernels_dir, bundle)
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"Kernel bundle directory not found: {bundle_path}")

        # Load kernels from bundle
        kernel_files = _find_kernel_files(bundle_path)
        if not kernel_files:
            raise ValueError(f"No kernel files found in bundle: {bundle_path}")

        if SPICE_AVAILABLE:
            _load_spice_kernels(kernel_files)
        else:
            logger.warning("SPICE not available - using mock kernel loading")

        KERNELS_LOADED = True
        CURRENT_BUNDLE = bundle
        LOADED_KERNELS = kernel_files
        logger.info(f"Loaded {len(kernel_files)} kernel files for bundle {bundle}")

    except Exception as e:
        logger.error(f"Failed to initialize kernels for bundle {bundle}: {e}")
        KERNELS_LOADED = False
        raise


def _find_kernel_files(bundle_dir: str) -> List[str]:
    """Find all kernel files in bundle directory."""
    kernel_files = []
    for root, dirs, files in os.walk(bundle_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if get_kernel_type(file) != "unknown":
                kernel_files.append(file_path)
    return sorted(kernel_files)


def _load_spice_kernels(kernel_files: List[str]) -> None:
    """Load SPICE kernel files."""
    for kernel_file in kernel_files:
        try:
            spice.furnsh(kernel_file)
            logger.debug(f"Loaded SPICE kernel: {kernel_file}")
        except Exception as e:
            logger.error(f"Failed to load kernel {kernel_file}: {e}")
            raise


def _clear_kernels() -> None:
    """Clear all loaded SPICE kernels."""
    global KERNELS_LOADED, LOADED_KERNELS
    if SPICE_AVAILABLE:
        try:
            spice.kclear()
            logger.debug("Cleared all SPICE kernels")
        except Exception as e:
            logger.warning(f"Error clearing SPICE kernels: {e}")
    KERNELS_LOADED = False
    LOADED_KERNELS = []


def compute_positions(
    utc: str,
    system: str,
    ayanamsha: Dict[str, Any],
    frame: str,
    epoch: str,
    bodies: List[str]
) -> Dict[str, Any]:
    """
    Compute planetary positions for specified bodies and time.

    Args:
        utc: UTC time in ISO format
        system: Zodiac system ('tropical' or 'sidereal')
        ayanamsha: Ayanāṃśa configuration dict
        frame: Reference frame ('ecliptic_of_date' or 'equatorial')
        epoch: Reference epoch ('of_date' or 'J2000')
        bodies: List of celestial body names

    Returns:
        Dict with calculated positions

    Raises:
        ValueError: For invalid inputs or unsupported configurations
        RuntimeError: For SPICE calculation errors
    """
    if not KERNELS_LOADED:
        raise RuntimeError("KERNELS.NOT_AVAILABLE: Kernels not loaded in worker process")

    # Validate inputs
    _validate_computation_inputs(utc, system, frame, epoch, bodies)

    # Validate frame/epoch combination (Phase 2 limitation)
    if frame == "equatorial" and epoch != "J2000":
        raise ValueError("INPUT.INVALID: Equatorial frame requires J2000 epoch in Phase 2")
    if frame == "ecliptic_of_date" and epoch != "of_date":
        raise ValueError("INPUT.INVALID: Ecliptic of date frame requires of_date epoch")

    try:
        # Parse UTC time and convert to Julian Date
        dt = parse_datetime(utc)
        jd = _datetime_to_jd(dt)
        et = _jd_to_et(jd)

        # Determine which ephemeris to use (DE440/DE441)
        ephemeris_used = _determine_ephemeris(dt)

        results = []
        ayanamsha_value = None

        # Calculate ayanāṃśa value if needed
        if system == "sidereal":
            ayanamsha_value = get_ayanamsha_value(ayanamsha, jd)

        # Calculate positions for each requested body
        for body in bodies:
            if body not in SUPPORTED_BODIES:
                raise ValueError(f"BODIES.UNSUPPORTED: Body '{body}' not supported")

            try:
                position = _calculate_body_position(body, et, frame, epoch)

                # Apply ayanāṃśa for sidereal system
                if system == "sidereal" and ayanamsha_value is not None:
                    if "lon_deg" in position:
                        position["lon_deg"] = apply_ayanamsha(position["lon_deg"], ayanamsha_value)

                results.append(position)

            except Exception as e:
                logger.error(f"Failed to calculate position for {body}: {e}")
                # Map SPICE errors to friendly error codes
                _handle_spice_error(e, body, utc)

        return {
            "bodies": results,
            "ephemeris_used": ephemeris_used,
            "ayanamsha_value": ayanamsha_value,
            "julian_date": jd,
            "ephemeris_time": et
        }

    except Exception as e:
        logger.error(f"Computation failed for {utc}: {e}")
        raise


def _validate_computation_inputs(
    utc: str,
    system: str,
    frame: str,
    epoch: str,
    bodies: List[str]
) -> None:
    """Validate computation inputs."""
    if system not in ["tropical", "sidereal"]:
        raise ValueError(f"INPUT.INVALID: Invalid system '{system}'. Must be 'tropical' or 'sidereal'")

    if frame not in ["ecliptic_of_date", "equatorial"]:
        raise ValueError(f"INPUT.INVALID: Invalid frame '{frame}'. Must be 'ecliptic_of_date' or 'equatorial'")

    if epoch not in ["of_date", "J2000"]:
        raise ValueError(f"INPUT.INVALID: Invalid epoch '{epoch}'. Must be 'of_date' or 'J2000'")

    if not bodies:
        raise ValueError("INPUT.MISSING_REQUIRED: At least one body must be specified")

    for body in bodies:
        if body not in SUPPORTED_BODIES:
            raise ValueError(f"BODIES.UNSUPPORTED: Body '{body}' not supported. "
                           f"Supported: {', '.join(SUPPORTED_BODIES)}")


def _datetime_to_jd(dt: datetime) -> float:
    """Convert datetime to Julian Date."""
    # Standard algorithm for Julian Date calculation
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3

    jdn = dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045

    # Add fractional day
    fraction = (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
    return jdn + fraction


def _jd_to_et(jd: float) -> float:
    """Convert Julian Date to SPICE Ephemeris Time."""
    if SPICE_AVAILABLE:
        try:
            # Convert JD to ET using SPICE
            return spice.unitim(jd, "JDTDB", "ET")
        except Exception as e:
            logger.warning(f"SPICE time conversion failed, using approximation: {e}")

    # Approximation: ET ≈ (JD - 2451545.0) * 86400.0
    return (jd - 2451545.0) * 86400.0


def _determine_ephemeris(dt: datetime) -> str:
    """Determine which ephemeris to use based on date."""
    # DE440 optimal range: 1550-2650
    if 1550 <= dt.year <= 2650:
        return "DE440"
    else:
        return "DE441"


def _calculate_body_position(
    body: str,
    et: float,
    frame: str,
    epoch: str
) -> Dict[str, Any]:
    """Calculate position for a single celestial body."""

    if body in ["TrueNode", "MeanNode"]:
        return _calculate_lunar_node(body, et, frame)

    spice_code = SPICE_BODY_CODES[body]

    if SPICE_AVAILABLE:
        return _calculate_spice_position(body, spice_code, et, frame, epoch)
    else:
        return _calculate_mock_position(body, et)


def _calculate_spice_position(
    body: str,
    spice_code: int,
    et: float,
    frame: str,
    epoch: str
) -> Dict[str, Any]:
    """Calculate position using SPICE."""
    try:
        # Observer is Earth center (geocentric)
        observer = 399  # Earth

        # Determine SPICE reference frame based on requested frame/epoch
        if frame == "ecliptic_of_date" and epoch == "of_date":
            spice_frame = "ECLIPDATE"  # Ecliptic and equinox of date
        elif frame == "equatorial" and epoch == "J2000":
            spice_frame = "J2000"  # Equatorial J2000
        else:
            # Fallback to ECLIPJ2000 for other combinations
            spice_frame = "ECLIPJ2000"

        # Calculate position and velocity
        state, light_time = spice.spkezr(str(spice_code), et, spice_frame, "LT+S", str(observer))

        # Extract position (first 3 elements are position, last 3 are velocity)
        position = state[:3]

        result = {"name": body}

        if frame == "ecliptic_of_date":
            # Convert to ecliptic longitude/latitude
            lon_deg, lat_deg, radius = _cartesian_to_spherical(position)
            result.update({
                "lon_deg": lon_deg,
                "lat_deg": lat_deg
            })

        elif frame == "equatorial" and epoch == "J2000":
            # Position is already in J2000 equatorial coordinates
            ra_hours, dec_deg = _cartesian_to_equatorial(position)
            result.update({
                "ra_hours": ra_hours,
                "dec_deg": dec_deg
            })
            # Also include ecliptic coordinates for compatibility
            lon_deg, lat_deg, radius = _cartesian_to_spherical_ecliptic(position)
            result.update({
                "lon_deg": lon_deg,
                "lat_deg": lat_deg
            })

        return result

    except Exception as e:
        logger.error(f"SPICE calculation failed for {body}: {e}")
        raise RuntimeError(f"COMPUTE.EPHEMERIS_ERROR: {str(e)}")


def _calculate_mock_position(body: str, et: float) -> Dict[str, Any]:
    """Calculate mock position when SPICE is not available."""
    # Mock positions for testing - in production, this would not be used
    import math

    # Simple mock based on body and time
    body_offsets = {
        "Sun": 0,
        "Moon": 90,
        "Mercury": 30,
        "Venus": 60,
        "Mars": 120,
        "Jupiter": 150,
        "Saturn": 180,
        "Uranus": 210,
        "Neptune": 240,
        "Pluto": 270,
        "TrueNode": 180,
        "MeanNode": 180
    }

    # Mock calculation with time-based variation
    base_lon = body_offsets.get(body, 0)
    time_variation = (et / 86400.0) * 0.1  # Small daily motion
    lon_deg = (base_lon + time_variation) % 360

    result = {
        "name": body,
        "lon_deg": lon_deg,
        "lat_deg": 0.0  # Mock latitude
    }

    # Add mock RA/Dec for equatorial requests
    ra_hours = (lon_deg / 15.0) % 24  # Convert longitude to hours
    dec_deg = 0.0  # Mock declination
    result.update({
        "ra_hours": ra_hours,
        "dec_deg": dec_deg
    })

    return result


def _calculate_lunar_node(body: str, et: float, frame: str) -> Dict[str, Any]:
    """Calculate lunar node position."""
    if SPICE_AVAILABLE:
        try:
            # Lunar nodes require special calculation
            # This is a simplified implementation
            # In production, use proper lunar theory

            # Mock calculation for now
            node_lon = 180.0  # Placeholder

            return {
                "name": body,
                "lon_deg": node_lon,
                "lat_deg": 0.0
            }

        except Exception as e:
            logger.error(f"Lunar node calculation failed: {e}")
            raise
    else:
        return _calculate_mock_position(body, et)


def _cartesian_to_spherical(position: List[float]) -> Tuple[float, float, float]:
    """Convert Cartesian coordinates to spherical (longitude, latitude, radius)."""
    import math

    x, y, z = position
    radius = math.sqrt(x*x + y*y + z*z)

    # Longitude (0-360 degrees)
    lon_rad = math.atan2(y, x)
    lon_deg = math.degrees(lon_rad)
    if lon_deg < 0:
        lon_deg += 360

    # Latitude (-90 to +90 degrees)
    lat_rad = math.asin(z / radius) if radius > 0 else 0
    lat_deg = math.degrees(lat_rad)

    return lon_deg, lat_deg, radius


def _cartesian_to_equatorial(position: List[float]) -> Tuple[float, float]:
    """Convert Cartesian coordinates to equatorial (RA, Dec)."""
    import math

    x, y, z = position
    radius = math.sqrt(x*x + y*y + z*z)

    # Right Ascension (0-24 hours)
    ra_rad = math.atan2(y, x)
    ra_hours = math.degrees(ra_rad) / 15.0  # Convert to hours
    if ra_hours < 0:
        ra_hours += 24

    # Declination (-90 to +90 degrees)
    dec_rad = math.asin(z / radius) if radius > 0 else 0
    dec_deg = math.degrees(dec_rad)

    return ra_hours, dec_deg


def _cartesian_to_spherical_ecliptic(position: List[float]) -> Tuple[float, float, float]:
    """Convert Cartesian coordinates to ecliptic spherical coordinates."""
    import math

    x, y, z = position
    radius = math.sqrt(x*x + y*y + z*z)

    # Ecliptic longitude (0-360 degrees)
    lon_rad = math.atan2(y, x)
    lon_deg = math.degrees(lon_rad)
    if lon_deg < 0:
        lon_deg += 360

    # Ecliptic latitude (-90 to +90 degrees)
    lat_rad = math.asin(z / radius) if radius > 0 else 0
    lat_deg = math.degrees(lat_rad)

    return lon_deg, lat_deg, radius


def _ecliptic_to_equatorial(lon_deg: float, lat_deg: float, et: float) -> Tuple[float, float]:
    """Convert ecliptic coordinates to equatorial."""
    import math

    # Simplified conversion using mean obliquity
    # In production, use SPICE's coordinate transformation
    obliquity = 23.43929  # Mean obliquity (simplified)
    obliquity_rad = math.radians(obliquity)

    lon_rad = math.radians(lon_deg)
    lat_rad = math.radians(lat_deg)

    # Convert to equatorial coordinates
    ra_rad = math.atan2(
        math.sin(lon_rad) * math.cos(obliquity_rad) - math.tan(lat_rad) * math.sin(obliquity_rad),
        math.cos(lon_rad)
    )

    dec_rad = math.asin(
        math.sin(lat_rad) * math.cos(obliquity_rad) +
        math.cos(lat_rad) * math.sin(obliquity_rad) * math.sin(lon_rad)
    )

    # Convert to hours and degrees
    ra_hours = math.degrees(ra_rad) / 15.0  # Convert to hours
    if ra_hours < 0:
        ra_hours += 24

    dec_deg = math.degrees(dec_rad)

    return ra_hours, dec_deg


def _handle_spice_error(error: Exception, body: str, utc: str) -> None:
    """Map SPICE errors to friendly error codes."""
    error_msg = str(error).upper()

    if "SPKINSUFFDATA" in error_msg or "INSUFFICIENT DATA" in error_msg:
        raise ValueError(f"RANGE.EPHEMERIS_OUTSIDE: Date {utc} outside ephemeris range for {body}. "
                        "Supported range 1550–2650 (DE440).")

    elif "KERNELNOTFOUND" in error_msg or "NOSUCHFILE" in error_msg:
        raise RuntimeError("KERNELS.NOT_AVAILABLE: Required ephemeris kernels not found.")

    elif "INVALIDTARGET" in error_msg:
        raise ValueError(f"BODIES.UNSUPPORTED: Invalid or unsupported body: {body}")

    elif "DIVIDEBYZERO" in error_msg or "CONVERGENCE" in error_msg:
        raise RuntimeError(f"COMPUTE.CONVERGENCE_FAILED: Numerical calculation failed for {body} at {utc}")

    else:
        # Generic computation error
        raise RuntimeError(f"COMPUTE.EPHEMERIS_ERROR: Calculation failed for {body}: {error}")


def get_kernel_status() -> Dict[str, Any]:
    """Get status of loaded kernels."""
    return {
        "loaded": KERNELS_LOADED,
        "bundle": CURRENT_BUNDLE,
        "kernel_count": len(LOADED_KERNELS),
        "spice_available": SPICE_AVAILABLE
    }