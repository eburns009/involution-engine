import csv
import io
import json
import logging
import os
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path
from typing import Any

import numpy as np
import pytz
import spiceypy as spice
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from houses import (
    _asc_mc_tropical_and_sidereal,
    _equal_cusps,
    _placidus_cusps,
    _whole_sign_cusps,
    _wrap360,
)

# Import from new modules
from models import (
    AVAILABLE_BODIES,
    ApiMeta,
    CalculationResponse,
    ChartRequest,
    HousesRequest,
    HousesResponse,
    PlanetPosition,
    TimeResolveRequest,
    TimeResolveResponse,
    Zodiac,
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from time_resolution import (
    get_historical_timezone,
)
from time_resolution import (
    localize_datetime_with_dst_handling as _localize_datetime_with_dst_handling,
)
from time_resolution import (
    parse_local_datetime as _parse_local_datetime,
)

# Contract Constants
ECL_FRAME = "ECLIPDATE"
COORD_SYSTEM = "ecliptic_of_date"
OBLIQUITY_MODEL = "IAU1980-mean"
ABCORR = "LT+S"
KERNEL_SET_TAG = "2024-Q3"
SERVICE_VERSION = "2.0.0"

# Zodiac signs for UI enrichment
SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

limiter = Limiter(key_func=get_remote_address)

# Configure structured JSON logging
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)


class MetricsCollector:
    """Simple metrics collector for latency and error tracking"""

    def __init__(self, max_samples: int = 1000):
        self.latencies: deque[float] = deque(maxlen=max_samples)
        self.errors: deque[float] = deque(maxlen=max_samples)  # Store timestamps
        self.spkinsuffdata_errors: deque[float] = deque(maxlen=max_samples)

    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement"""
        self.latencies.append(latency_ms)

    def record_error(self, error_msg: str) -> None:
        """Record an error occurrence"""
        current_time = time.time()
        self.errors.append(current_time)

        # Check for SPICE insufficient data errors
        if "SPKINSUFFDATA" in error_msg or "insufficient data" in error_msg.lower():
            self.spkinsuffdata_errors.append(current_time)

    def get_latency_percentiles(self) -> dict[str, float]:
        """Get p50 and p95 latency percentiles"""
        if not self.latencies:
            return {"p50": 0.0, "p95": 0.0, "count": 0}

        sorted_latencies = sorted(self.latencies)
        count = len(sorted_latencies)

        p50_idx = int(count * 0.5)
        p95_idx = int(count * 0.95)

        return {
            "p50": round(sorted_latencies[p50_idx], 2),
            "p95": round(sorted_latencies[p95_idx], 2),
            "count": count,
        }

    def get_error_rate(self, window_minutes: int = 5) -> dict[str, Any]:
        """Get error rate over the last N minutes"""
        current_time = time.time()
        window_start = current_time - (window_minutes * 60)

        recent_errors = [t for t in self.errors if t >= window_start]
        recent_spk_errors = [t for t in self.spkinsuffdata_errors if t >= window_start]

        # Total requests approximated from latency records + error records
        total_requests = len([t for t in self.latencies if t >= window_start]) + len(recent_errors)

        error_rate = len(recent_errors) / total_requests if total_requests > 0 else 0.0

        return {
            "error_rate": round(error_rate, 4),
            "total_errors": len(recent_errors),
            "spkinsuffdata_errors": len(recent_spk_errors),
            "total_requests": total_requests,
            "window_minutes": window_minutes,
        }


# Global metrics collector
metrics = MetricsCollector()


def log_calculation(
    target: str,
    et: float,
    frame: str,
    abcorr: str,
    ayanamsa: str,
    latency_ms: float,
    success: bool,
    error: str | None = None,
) -> None:
    """Log calculation details in structured JSON format and update metrics"""
    # Update metrics
    metrics.record_latency(latency_ms)
    if not success and error:
        metrics.record_error(error)

    log_entry = {
        "timestamp": time.time(),
        "event": "calculation",
        "target": target,
        "et": et,
        "frame": frame,
        "abcorr": abcorr,
        "ayanamsa": ayanamsa,
        "latency_ms": round(latency_ms, 2),
        "success": success,
    }
    if error:
        log_entry["error"] = error

    logger.info(json.dumps(log_entry))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    # Resolve relative to the file so dev + container both work
    base = Path(__file__).resolve().parent
    metakernel = str(base / "kernels" / "involution.tm")

    if not os.path.exists(metakernel):
        print("WARNING: Metakernel not found. Download kernels first.")
        yield
        return

    try:
        spice.furnsh(metakernel)

        # Verify required frames are available
        et = spice.str2et("2024-01-01T00:00:00")
        spice.pxform("ITRF93", "J2000", et)

        print(f"✓ SPICE initialized - Toolkit: {spice.tkvrsn('TOOLKIT')}")
        print(f"✓ Kernels loaded: {spice.ktotal('ALL')}")

        # Log kernel coverage windows for supply chain verification
        log_kernel_coverage()

        yield

    except Exception as e:
        print(f"✗ SPICE initialization failed: {e}")
        raise
    finally:
        # Shutdown cleanup
        try:
            spice.kclear()
            print("✓ SPICE kernels cleared")
        except Exception:
            pass  # nosec B110 - Safe to ignore cleanup failures


app = FastAPI(
    title="Involution SPICE Service",
    version="2.0.0",
    description="Research-grade planetary position calculations",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

# SPICE State Management:
# - CSPICE is NOT thread-safe, use one process per worker
# - furnsh/kclear ONLY called at startup/shutdown, NEVER mid-request
# - Global SPICE state is immutable during request processing

# In tests, disable rate limiting via env
if os.getenv("DISABLE_RATE_LIMIT", "0") == "1":

    class _NoopLimiter:
        enabled = False

        def limit(self, *a: Any, **k: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
                return fn

            return deco

    limiter = _NoopLimiter()  # type: ignore[assignment]
    app.state.limiter = limiter

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,https://research-ui.onrender.com"
    ).split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization"],
    allow_credentials=True,
)


def _calculate_single_body_position(
    body_name: str,
    body_id: str,
    et: float,
    lat: float,
    lon: float,
    elev: float,
    zodiac: Zodiac,
    ayanamsa_deg: float | None,
) -> PlanetPosition:
    """
    Calculate position for a single celestial body.

    Args:
        body_name: Display name of the body (e.g., "Sun")
        body_id: SPICE body identifier (e.g., "SUN")
        et: SPICE ephemeris time
        lat, lon, elev: Observer location
        zodiac: "tropical" or "sidereal"
        ayanamsa_deg: Ayanamsa value in degrees (None for tropical)

    Returns:
        PlanetPosition with all calculated fields
    """
    # Get topocentric position
    pos_topo_j2000 = topocentric_vec_j2000(body_id, et, lat, lon, elev)

    # Convert to ecliptic of date
    ecl_pos = convert_to_ecliptic_of_date_spice(pos_topo_j2000, et)

    # Apply zodiac-specific longitude
    tropical_lon = ecl_pos["longitude"]
    out_lon = (tropical_lon - ayanamsa_deg) % 360 if zodiac == "sidereal" else tropical_lon

    # Calculate speed (degrees/day)
    try:
        speed = estimate_longitude_speed(body_id, et, lat, lon, elev)
    except Exception:
        speed = None  # Continue without speed if calculation fails

    # Generate UI-ready fields
    sign, degree_in_sign = zodiac_from_longitude(out_lon)
    D, M, S = dms_from_degrees(degree_in_sign)

    return PlanetPosition(
        longitude=round(out_lon, 6),
        latitude=round(ecl_pos["latitude"], 6),
        distance=round(ecl_pos["distance"], 8),
        sign=sign,
        degree=round(degree_in_sign, 6),
        degrees=D,
        minutes=M,
        seconds=round(S, 2),
        speed=round(speed, 6) if speed is not None else None,
        is_retrograde=retro_from_speed(speed),
    )


@limiter.limit("10/minute")
@app.post("/calculate", response_model=CalculationResponse)
async def calculate_planetary_positions(
    request: Request, chart: ChartRequest
) -> CalculationResponse:
    """Calculate topocentric sidereal positions using spkcpo

    IMPORTANT: This function only READS from SPICE state.
    No furnsh/kclear calls are made during request processing.
    """
    start_time = time.time()
    et = None
    frame = ECL_FRAME
    abcorr = ABCORR

    try:
        # Convert to SPICE ET from ISO Z (always UTC now)
        et = spice.str2et(chart.birth_time.isoformat().replace("+00:00", "Z"))

        # Calculate ayanamsa once if needed
        ayanamsa_deg = (
            calculate_ayanamsa(chart.ayanamsa, et) if chart.zodiac == "sidereal" else None
        )

        # Calculate positions for all requested bodies
        results = {}
        for name in chart.bodies:
            body_start_time = time.time()
            body_id = AVAILABLE_BODIES[name]

            results[name] = _calculate_single_body_position(
                name,
                body_id,
                et,
                chart.latitude,
                chart.longitude,
                chart.elevation,
                chart.zodiac,
                ayanamsa_deg,
            )

            # Log individual body calculation
            body_latency_ms = (time.time() - body_start_time) * 1000
            log_calculation(body_id, et, frame, abcorr, chart.ayanamsa, body_latency_ms, True)

        # Log overall request
        total_latency_ms = (time.time() - start_time) * 1000
        log_calculation(
            "ALL_BODIES",
            et or 0,
            frame,
            abcorr,
            chart.ayanamsa if chart.zodiac == "sidereal" else "tropical",
            total_latency_ms,
            True,
        )

        # Create meta information
        meta = ApiMeta(
            service_version=SERVICE_VERSION,
            spice_version=spice.tkvrsn("TOOLKIT"),
            kernel_set_tag=KERNEL_SET_TAG,
            ecliptic_frame=ECL_FRAME,
            zodiac=chart.zodiac,
            ayanamsa_deg=round(ayanamsa_deg, 6) if ayanamsa_deg is not None else None,
            request_id=str(uuid.uuid4()),
            timestamp=time.time(),
        )

        return CalculationResponse(data=results, meta=meta)

    except Exception as e:
        # Log error with timing info
        error_latency_ms = (time.time() - start_time) * 1000
        log_calculation(
            "ERROR",
            et or 0,
            frame,
            abcorr,
            chart.ayanamsa if chart.zodiac == "sidereal" else "tropical",
            error_latency_ms,
            False,
            str(e),
        )

        # Map error to user-friendly message
        status_code, detail = map_error(e)
        print(f"Calculation error: {e}")
        raise HTTPException(status_code=status_code, detail=detail)


def _observer_pos_in_iau_earth(lat_deg: float, lon_deg: float, elev_m: float) -> np.ndarray:
    """Observer position in the IAU_EARTH body-fixed frame (km)."""
    # WGS-84-like spheroid; keep consistent with your house math
    re = 6378.137  # km
    f = 1.0 / 298.257223563
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    alt = elev_m / 1000.0
    # Geodetic → rectangular in body-fixed
    x, y, z = spice.georec(lon, lat, alt, re, f)
    return np.array([x, y, z])


def topocentric_vec_j2000(
    target: str, et: float, lat_deg: float, lon_deg: float, elev_m: float
) -> Any:
    """Calculate topocentric position using spkcpo for proper LT+S corrections"""
    # Choose observer frame dynamically based on EOP coverage
    obs_frame = "ITRF93"
    try:
        # Test if ITRF93 transform exists at this epoch (requires EOP data)
        spice.pxform("ITRF93", "J2000", et)

        # Earth figure from SPICE for ITRF93
        _, radii = spice.bodvrd("EARTH", "RADII", 3)
        re, rp = radii[0], radii[2]
        f = (re - rp) / re

        lon = np.radians(lon_deg)
        lat = np.radians(lat_deg)
        alt_km = elev_m / 1000.0

        # Observer position in ITRF93
        obs_pos = spice.georec(lon, lat, alt_km, re, f)

    except Exception:
        # Fallback for historical dates (e.g., 1962): use IAU_EARTH body-fixed frame
        obs_frame = "IAU_EARTH"
        obs_pos = _observer_pos_in_iau_earth(lat_deg, lon_deg, elev_m)

    # Use spkcpo with the chosen frame
    state, _ = spice.spkcpo(target, et, "J2000", "OBSERVER", "LT+S", obs_pos, "EARTH", obs_frame)
    pos_j2000 = state[:3]

    return pos_j2000


def apply_precession_iau2006(pos_j2000: np.ndarray, T: float) -> np.ndarray:
    """Apply IAU 2006/2000A precession from J2000.0 to date (T centuries since J2000)"""
    # IAU 2006 precession angles (arcseconds, converted to radians)
    zeta_A = np.radians((2306.2181 * T + 0.30188 * T**2 + 0.017998 * T**3) / 3600.0)
    z_A = np.radians((2306.2181 * T + 1.09468 * T**2 + 0.018203 * T**3) / 3600.0)
    theta_A = np.radians((2004.3109 * T - 0.42665 * T**2 - 0.041833 * T**3) / 3600.0)

    # Rotation matrices - corrected order and signs
    cos_zeta, sin_zeta = np.cos(-zeta_A), np.sin(-zeta_A)
    cos_z, sin_z = np.cos(-z_A), np.sin(-z_A)
    cos_theta, sin_theta = np.cos(theta_A), np.sin(theta_A)

    # P = R3(-z_A) * R2(theta_A) * R3(-zeta_A) applied to J2000 coordinates
    R1 = np.array([[cos_zeta, sin_zeta, 0], [-sin_zeta, cos_zeta, 0], [0, 0, 1]])  # R3(-zeta_A)
    R2 = np.array([[cos_theta, 0, -sin_theta], [0, 1, 0], [sin_theta, 0, cos_theta]])  # R2(theta_A)
    R3 = np.array([[cos_z, sin_z, 0], [-sin_z, cos_z, 0], [0, 0, 1]])  # R3(-z_A)

    P = R3 @ R2 @ R1
    return P @ pos_j2000


def convert_to_ecliptic_of_date_spice(pos_j2000: np.ndarray, et: float) -> dict[str, float]:
    """
    Convert to ecliptic coordinates of date with proper precession:
    1) J2000 equatorial → mean equatorial of date (precession)
    2) Mean equatorial of date → ecliptic of date (obliquity rotation)
    """
    try:
        # Get Julian date and centuries since J2000.0
        jd_tt = spice.j2000() + et / spice.spd()
        T = (jd_tt - 2451545.0) / 36525.0

        # 1) Normalize & precess J2000 → mean equator of date
        r_km = np.linalg.norm(pos_j2000)
        v = pos_j2000 / r_km
        v_eq_date = apply_precession_iau2006(v, T)

        # 2) IAU 1980 mean obliquity of the ecliptic
        obliq_deg = 23.43929111 - (46.8150 * T + 0.00059 * T**2 - 0.001813 * T**3) / 3600.0
        obliq_rad = np.radians(obliq_deg)

        # Create rotation matrix from equatorial of date to ecliptic of date
        cos_obliq = np.cos(obliq_rad)
        sin_obliq = np.sin(obliq_rad)

        rotation_matrix = np.array(
            [[1.0, 0.0, 0.0], [0.0, cos_obliq, sin_obliq], [0.0, -sin_obliq, cos_obliq]]
        )

        # Transform to ecliptic of date
        v_ecl_date = rotation_matrix @ v_eq_date

        # Convert to spherical coordinates
        lon_rad = np.arctan2(v_ecl_date[1], v_ecl_date[0])
        lat_rad = np.arcsin(v_ecl_date[2])

        return {
            "longitude": (np.degrees(lon_rad) + 360.0) % 360.0,
            "latitude": np.degrees(lat_rad),
            "distance": r_km / 149597870.7,
        }
    except Exception as e:
        raise RuntimeError(f"SPICE frame transformation failed: {e}")


def log_kernel_coverage() -> None:
    """Log kernel coverage windows to verify complete downloads"""
    try:
        bodies = {
            "Sun": "SUN",
            "Moon": "MOON",
            "Mercury": "MERCURY BARYCENTER",
            "Venus": "VENUS BARYCENTER",
            "Mars": "MARS BARYCENTER",
            "Jupiter": "JUPITER BARYCENTER",
            "Saturn": "SATURN BARYCENTER",
        }

        print("=== Kernel Coverage Verification ===")

        for name, body_id in bodies.items():
            try:
                # Get coverage windows for this body
                cell = spice.cell_double(200)  # Create cell for coverage data
                spice.spkcov("kernels/spk/planets/de440.bsp", int(spice.bodn2c(body_id)), cell)

                # Get coverage intervals
                intervals = spice.wnfetd(cell, 0) if spice.wncard(cell) > 0 else (0, 0)

                if intervals[0] != 0:
                    start_utc = spice.et2utc(intervals[0], "ISOC", 0)
                    end_utc = spice.et2utc(intervals[1], "ISOC", 0)
                    print(f"✓ {name}: {start_utc} to {end_utc}")
                else:
                    print(f"⚠ {name}: No coverage found")

            except Exception as e:
                print(f"⚠ {name}: Coverage check failed - {e}")

        print("=====================================\n")

    except Exception as e:
        print(f"⚠ Kernel coverage logging failed: {e}")


def calculate_ayanamsa(system: str, et: float) -> float:
    """Calculate ayanamsa for given system"""
    jd_tt = spice.j2000() + et / spice.spd()
    T = (jd_tt - 2451545.0) / 36525.0

    if system == "lahiri":
        ayanamsa = 23.85144
        ayanamsa += (50.2876 * T * 100) / 3600
        ayanamsa += 0.000464 * T * T
        ayanamsa += -0.0000002 * T * T * T
        return ayanamsa % 360

    elif system == "fagan_bradley":
        T1950 = (jd_tt - 2433282.5) / 36525.0
        ayanamsa = 24.042222 + (50.2564 * T1950 * 100) / 3600
        return ayanamsa % 360

    else:
        raise ValueError(f"Unknown ayanamsa system: {system}")


# Houses calculation helpers
# UI-ready helper functions
def zodiac_from_longitude(lon_deg: float) -> tuple[str, float]:
    """Convert ecliptic longitude to zodiac sign and degree within sign"""
    lon = _wrap360(lon_deg)
    idx = int(lon // 30)
    return SIGNS[idx], lon - 30.0 * idx


def dms_from_degrees(deg: float) -> tuple[int, int, float]:
    """Convert decimal degrees to degrees, minutes, seconds"""
    d = int(deg)
    m_full = abs(deg - d) * 60.0
    m = int(m_full)
    s = (m_full - m) * 60.0
    return d, m, s


def retro_from_speed(speed_deg_per_day: float | None) -> bool | None:
    """Determine if body is retrograde based on longitudinal speed"""
    if speed_deg_per_day is None:
        return None
    return speed_deg_per_day < 0


def estimate_longitude_speed(body_id: str, et: float, lat: float, lon: float, elev: float) -> float:
    """Estimate longitudinal speed in degrees/day using numeric differentiation"""
    # Sample at t-12h and t+12h (1 day window total)
    dt_seconds = 12 * 3600  # 12 hours in seconds
    et0 = et - dt_seconds
    et1 = et + dt_seconds

    # Calculate positions
    pos0 = topocentric_vec_j2000(body_id, et0, lat, lon, elev)
    pos1 = topocentric_vec_j2000(body_id, et1, lat, lon, elev)

    # Convert to ecliptic
    ecl0 = convert_to_ecliptic_of_date_spice(pos0, et0)
    ecl1 = convert_to_ecliptic_of_date_spice(pos1, et1)

    # Calculate shortest angular distance (wrap-aware)
    lon0, lon1 = ecl0["longitude"], ecl1["longitude"]
    d = _wrap360(lon1 - lon0)
    if d > 180.0:
        d -= 360.0

    # degrees per day
    return d / 1.0


# Aspect calculation
ASPECTS = {
    "conjunction": (0, 8),
    "opposition": (180, 8),
    "trine": (120, 6),
    "square": (90, 6),
    "sextile": (60, 4),
}


def angle_gap(a: float, b: float) -> float:
    """Calculate shortest angular distance between two angles"""
    d = abs(_wrap360(a) - _wrap360(b))
    return d if d <= 180 else 360 - d


def calc_aspects(positions: dict[str, PlanetPosition]) -> list[dict[str, Any]]:
    """Calculate aspects between all planet pairs"""
    names = list(positions.keys())
    results = []
    for i, p1 in enumerate(names):
        for p2 in names[i + 1 :]:
            gap = angle_gap(positions[p1].longitude, positions[p2].longitude)
            for aspect_name, (target, orb) in ASPECTS.items():
                if abs(gap - target) <= orb:
                    results.append(
                        {
                            "p1": p1,
                            "p2": p2,
                            "type": aspect_name,
                            "angle_deg": round(gap, 2),
                            "orb_deg": round(abs(gap - target), 2),
                        }
                    )
    return results


# Error mapping
def map_error(e: Exception) -> tuple[int, str]:
    """Map SPICE errors to user-friendly HTTP errors"""
    m = str(e)
    if (
        "SPKINSUFFDATA" in m
        or "outside the bounds" in m
        or "insufficient ephemeris data" in m.lower()
    ):
        return 400, "Date outside supported ephemeris range (1550-2650)"
    if "BADTIMESTRING" in m or "INVALIDTIME" in m or "time format" in m.lower():
        return (
            422,
            "Invalid date/time format. Use ISO 8601 with timezone (e.g., 2024-06-21T18:00:00Z)",
        )
    if "SPICE(SPKINSUFFDATA)" in m:
        return 400, "Ephemeris data insufficient for requested date"
    if "SPICE(NOFRAMECONNECT)" in m:
        return 500, "Frame transformation not available"
    return 500, "Calculation error occurred"


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check with frame validation"""
    try:
        et = spice.str2et("2024-01-01T00:00:00")

        # Test required frame transforms (same as /calculate endpoint)
        spice.pxform("ITRF93", "J2000", et)

        # Get Earth radii for debugging
        _, radii = spice.bodvrd("EARTH", "RADII", 3)

        return {
            "status": "healthy",
            "data": {
                "kernels_loaded": int(spice.ktotal("ALL")),
                "earth_radii_km": [round(r, 3) for r in radii],
            },
            "meta": {
                "service_version": SERVICE_VERSION,
                "spice_version": spice.tkvrsn("TOOLKIT"),
                "kernel_set_tag": KERNEL_SET_TAG,
                "ecliptic_frame": ECL_FRAME,
                "coordinate_system": COORD_SYSTEM,
                "obliquity_model": OBLIQUITY_MODEL,
                "aberration_correction": ABCORR,
                "request_id": str(uuid.uuid4()),
                "timestamp": time.time(),
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "data": {},
            "meta": {
                "service_version": SERVICE_VERSION,
                "spice_version": "unknown",
                "kernel_set_tag": KERNEL_SET_TAG,
                "ecliptic_frame": ECL_FRAME,
                "coordinate_system": COORD_SYSTEM,
                "obliquity_model": OBLIQUITY_MODEL,
                "aberration_correction": ABCORR,
                "request_id": str(uuid.uuid4()),
                "timestamp": time.time(),
            },
            "error": str(e),
        }


@app.get("/version")
async def get_version() -> dict[str, Any]:
    """API version and kernel information endpoint"""
    try:
        return {
            "service_version": "1.0.0",
            "spice_version": spice.tkvrsn("TOOLKIT"),
            "kernel_set": {
                "tag": "2024-Q3",
                "count": int(spice.ktotal("ALL")),
                "de_ephemeris": "DE440",
                "earth_orientation": "earth_latest_high_prec",
                "planetary_constants": "pck00011",
                "leap_seconds": "naif0012",
            },
            "coordinate_frames": {
                "reference": "J2000",
                "observer": "ITRF93",
                "ecliptic": "ECLIPDATE",
                "aberration_correction": "LT+S",
            },
            "ayanamsa_systems": ["lahiri", "fagan_bradley"],
            "precision": {"longitude_digits": 6, "latitude_digits": 6, "distance_digits": 8},
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Observability endpoint with latency and error metrics"""
    try:
        latency_stats = metrics.get_latency_percentiles()
        error_stats = metrics.get_error_rate()

        return {
            "latency": latency_stats,
            "errors": error_stats,
            "timestamp": time.time(),
            "alerts": {
                "high_latency": latency_stats["p95"] > 2000,  # Alert if p95 > 2s
                "spkinsuffdata": error_stats["spkinsuffdata_errors"]
                > 0,  # Alert on any SPICE data errors
                "high_error_rate": error_stats["error_rate"] > 0.1,  # Alert if error rate > 10%
            },
        }
    except Exception as e:
        return {"error": str(e), "timestamp": time.time()}


@app.get("/debug")
async def debug_info() -> dict[str, Any]:
    """Debug endpoint with detailed configuration info"""
    try:
        # Test targets
        bodies = {
            "Sun": "SUN",
            "Moon": "MOON",
            "Mercury": "MERCURY BARYCENTER",
            "Venus": "VENUS BARYCENTER",
            "Mars": "MARS BARYCENTER",
            "Jupiter": "JUPITER BARYCENTER",
            "Saturn": "SATURN BARYCENTER",
        }

        return {
            "spice_version": spice.tkvrsn("TOOLKIT"),
            "kernels_loaded": int(spice.ktotal("ALL")),
            "target_bodies": bodies,
            "aberration_correction": "LT+S",
            "reference_frame": "J2000",
            "observer_frame": "ITRF93",
            "coordinate_system": "ecliptic_of_date",
            "obliquity_formula": "IAU_1980",
            "topocentric_method": "spkcpo",
            "earth_figure": "SPICE_bodvrd_georec",
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/info")
async def info() -> dict[str, Any]:
    """Info endpoint with toolkit version, kernels, and coverage"""
    try:
        kernels = []

        # Get loaded kernel information
        for i in range(spice.ktotal("SPK")):
            fn, *_ = spice.kdata(i, "SPK")
            kernels.append(fn)

        return {
            "status": "ok",
            "data": {"kernels": kernels, "kernel_count": len(kernels)},
            "meta": {
                "service_version": SERVICE_VERSION,
                "spice_version": spice.tkvrsn("TOOLKIT"),
                "kernel_set_tag": KERNEL_SET_TAG,
                "ecliptic_frame": ECL_FRAME,
                "coordinate_system": COORD_SYSTEM,
                "obliquity_model": OBLIQUITY_MODEL,
                "aberration_correction": ABCORR,
                "request_id": str(uuid.uuid4()),
                "timestamp": time.time(),
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "data": {},
            "meta": {
                "service_version": SERVICE_VERSION,
                "spice_version": "unknown",
                "kernel_set_tag": KERNEL_SET_TAG,
                "ecliptic_frame": ECL_FRAME,
                "coordinate_system": COORD_SYSTEM,
                "obliquity_model": OBLIQUITY_MODEL,
                "aberration_correction": ABCORR,
                "request_id": str(uuid.uuid4()),
                "timestamp": time.time(),
            },
            "error": str(e),
        }


@app.post("/houses", response_model=HousesResponse)
async def houses(req: HousesRequest):
    """Calculate house cusps using Placidus, Whole Sign, or Equal house systems"""
    # normalize to UTC
    if req.birth_time.tzinfo is None or req.birth_time.tzinfo.utcoffset(req.birth_time) is None:
        raise HTTPException(status_code=422, detail="birth_time must include timezone")
    iso_z = req.birth_time.astimezone(UTC).isoformat().replace("+00:00", "Z")

    # Get tropical and sidereal ASC/MC
    asc_mc = _asc_mc_tropical_and_sidereal(
        iso_z, req.latitude, req.longitude, req.ayanamsa, calculate_ayanamsa, req.mc_hemisphere
    )
    ayanamsa_deg = asc_mc["ay"] if req.zodiac == "sidereal" else None

    # Choose final ASC/MC based on zodiac
    if req.zodiac == "sidereal":
        asc, mc = asc_mc["asc"], asc_mc["mc"]
    else:
        asc, mc = asc_mc["asc_tropical"], asc_mc["mc_tropical"]

    if req.system == "whole-sign":
        cusps = _whole_sign_cusps(asc_mc["asc_tropical"], asc_mc["ay"], req.zodiac)
    elif req.system == "equal":
        cusps = _equal_cusps(asc_mc["asc_tropical"], asc_mc["ay"], req.zodiac)
    else:
        # placidus
        if abs(req.latitude) > 66.5:
            raise HTTPException(
                status_code=422, detail="Placidus undefined above polar circles (|lat| > ~66.5°)"
            )
        cusps = _placidus_cusps(
            iso_z,
            req.latitude,
            req.longitude,
            req.ayanamsa,
            calculate_ayanamsa,
            req.zodiac,
            req.mc_hemisphere,
        )

    return HousesResponse(
        system=req.system,
        frame=ECL_FRAME,
        coordinate_system=COORD_SYSTEM,
        ecliptic_model=OBLIQUITY_MODEL,
        zodiac=req.zodiac,
        ayanamsa=req.ayanamsa if req.zodiac == "sidereal" else None,
        ayanamsa_deg=round(ayanamsa_deg, 6) if ayanamsa_deg is not None else None,
        asc=round(asc, 6),
        mc=round(mc, 6),
        cusps=[round(c, 6) for c in cusps],
    )


@limiter.limit("10/minute")
@app.post("/v1/chart")
async def chart(request: Request, chart_req: ChartRequest):
    """Combined endpoint: planets + houses + aspects in one response"""
    try:
        # Calculate planets
        planets_response = await calculate_planetary_positions(request, chart_req)

        # Calculate houses
        houses_req = HousesRequest(
            birth_time=chart_req.birth_time,
            latitude=chart_req.latitude,
            longitude=chart_req.longitude,
            elevation=chart_req.elevation,
            zodiac=chart_req.zodiac,
            ayanamsa=chart_req.ayanamsa,
            system="placidus" if abs(chart_req.latitude) <= 66.5 else "whole-sign",
            mc_hemisphere="south",
        )
        houses_response = await houses(houses_req)

        # Calculate aspects
        aspects = calc_aspects(planets_response.data)

        return {
            "planets": planets_response.data,
            "houses": houses_response,
            "aspects": aspects,
            "meta": planets_response.meta,
        }
    except HTTPException:
        raise
    except Exception as e:
        status_code, detail = map_error(e)
        raise HTTPException(status_code=status_code, detail=detail)


@limiter.limit("10/minute")
@app.post("/v1/calculate/csv")
async def calculate_csv(request: Request, chart_req: ChartRequest):
    """Export planetary positions as CSV"""
    try:
        # Calculate planets
        planets_response = await calculate_planetary_positions(request, chart_req)

        # Create CSV
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "Body",
                "Longitude",
                "Latitude",
                "Distance",
                "Sign",
                "Degree",
                "DMS",
                "Speed",
                "Retrograde",
            ]
        )

        for name, pos in planets_response.data.items():
            dms_str = (
                f"{pos.degrees}°{pos.minutes}′{pos.seconds:.2f}″" if pos.degrees is not None else ""
            )
            writer.writerow(
                [
                    name,
                    pos.longitude,
                    pos.latitude,
                    pos.distance,
                    pos.sign or "",
                    pos.degree if pos.degree is not None else "",
                    dms_str,
                    pos.speed if pos.speed is not None else "",
                    pos.is_retrograde if pos.is_retrograde is not None else "",
                ]
            )

        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=chart.csv"},
        )
    except HTTPException:
        raise
    except Exception as e:
        status_code, detail = map_error(e)
        raise HTTPException(status_code=status_code, detail=detail)


# Time Resolution Models and Endpoint
@limiter.limit("60/minute")
@app.post("/v1/time/resolve", response_model=TimeResolveResponse)
async def resolve_time(request: Request, req: TimeResolveRequest) -> TimeResolveResponse:
    """
    Resolve local datetime to UTC using geographical coordinates with historical accuracy.

    This endpoint handles:
    - Historical timezone rules (via IANA/pytz database)
    - Daylight Saving Time (DST) transitions and edge cases
    - Timezone boundary changes over time
    - Ambiguous times (DST fall-back: defaults to standard time)
    - Non-existent times (DST spring-forward: uses next valid time)

    Args:
        request: FastAPI request object (for rate limiting)
        req: TimeResolveRequest with local_datetime, coordinates, and optional timezone_override

    Returns:
        TimeResolveResponse with utc_time, timezone, offset_hours, and is_dst flag

    Raises:
        HTTPException 400: Invalid timezone override or coordinates in ocean
        HTTPException 422: Invalid datetime format

    Rate Limit:
        60 requests per minute per IP address
    """
    try:
        # 1. Find timezone from coordinates (or use override)
        if req.timezone_override:
            # Validate the override timezone
            try:
                pytz.timezone(req.timezone_override)
                tz_name = req.timezone_override
            except pytz.exceptions.UnknownTimeZoneError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid timezone: {req.timezone_override}. Must be a valid IANA timezone name.",
                )
        else:
            # Use regional IANA timezones for accurate historical data
            tz_name = get_historical_timezone(req.latitude, req.longitude)

            if not tz_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not determine timezone for coordinates ({req.latitude}, {req.longitude}). Location may be in ocean or invalid. Consider using timezone_override.",
                )

        # 2. Parse local datetime
        local_dt = _parse_local_datetime(req.local_datetime)

        # 3. Localize to timezone with DST handling
        tz = pytz.timezone(tz_name)
        localized_dt, is_dst = _localize_datetime_with_dst_handling(local_dt, tz)

        # 4. Convert to UTC
        utc_dt = localized_dt.astimezone(pytz.UTC)

        # 5. Calculate offset
        offset_seconds = localized_dt.utcoffset().total_seconds() if localized_dt.utcoffset() else 0
        offset_hours = offset_seconds / 3600

        return TimeResolveResponse(
            utc_time=utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            timezone=tz_name,
            offset_hours=round(offset_hours, 2),
            is_dst=is_dst,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Time resolution failed: {str(e)}")


if __name__ == "__main__":
    import os

    import uvicorn

    if os.getenv("ENV", "dev") == "dev":
        uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
