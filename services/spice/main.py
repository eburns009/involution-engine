from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import spiceypy as spice
import numpy as np
import os
from typing import Dict, Any, Callable
from pathlib import Path

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Involution SPICE Service",
    version="1.0.0",
    description="Research-grade planetary position calculations"
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
            def deco(fn: Callable[..., Any]) -> Callable[..., Any]: return fn
            return deco
    limiter = _NoopLimiter()  # type: ignore[assignment]
    app.state.limiter = limiter

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization"],
    allow_credentials=True,
)

class ChartRequest(BaseModel):
    birth_time: str
    latitude: float
    longitude: float
    elevation: float = 0.0
    ayanamsa: str = "lahiri"

class PlanetPosition(BaseModel):
    longitude: float
    latitude: float
    distance: float

@app.on_event("startup")
async def initialize_spice() -> None:
    """Load SPICE kernels with proper validation

    CRITICAL: This is the ONLY place where furnsh() is called.
    SPICE state must remain immutable during request processing.
    """
    # Resolve relative to the file so dev + container both work
    base = Path(__file__).resolve().parent
    metakernel = str(base / "kernels" / "involution.tm")

    if not os.path.exists(metakernel):
        print("WARNING: Metakernel not found. Download kernels first.")
        return

    try:
        spice.furnsh(metakernel)

        # Verify required frames are available
        et = spice.str2et("2024-01-01T00:00:00")
        spice.pxform("ITRF93", "J2000", et)
        spice.pxform("J2000", "ECLIPJ2000", et)

        print(f"✓ SPICE initialized - Toolkit: {spice.tkvrsn('TOOLKIT')}")
        print(f"✓ Kernels loaded: {spice.ktotal('ALL')}")

        # Log kernel coverage windows for supply chain verification
        log_kernel_coverage()

    except Exception as e:
        print(f"✗ SPICE initialization failed: {e}")
        raise

@limiter.limit("10/minute")
@app.post("/calculate", response_model=Dict[str, PlanetPosition])
async def calculate_planetary_positions(request: Request, chart: ChartRequest) -> Dict[str, PlanetPosition]:
    """Calculate topocentric sidereal positions using spkcpo

    IMPORTANT: This function only READS from SPICE state.
    No furnsh/kclear calls are made during request processing.
    """
    try:
        et = spice.str2et(chart.birth_time)

        bodies = {
            "Sun": "SUN",                    # 10
            "Moon": "MOON",                  # 301
            "Mercury": "MERCURY BARYCENTER", # 1
            "Venus": "VENUS BARYCENTER",     # 2
            "Mars": "MARS BARYCENTER",       # 4
            "Jupiter": "JUPITER BARYCENTER", # 5
            "Saturn": "SATURN BARYCENTER",   # 6
        }

        results = {}

        for name, body_id in bodies.items():
            # Get topocentric position using corrected SPICE call
            pos_topo_j2000 = topocentric_vec_j2000(
                body_id, et, chart.latitude, chart.longitude, chart.elevation
            )

            # Convert to ecliptic of date using SPICE frames
            ecl_pos = convert_to_ecliptic_of_date_spice(pos_topo_j2000, et)

            # Apply ayanamsa correction
            ayanamsa_deg = calculate_ayanamsa(chart.ayanamsa, et)
            sidereal_lon = (ecl_pos["longitude"] - ayanamsa_deg) % 360

            results[name] = PlanetPosition(
                longitude=round(sidereal_lon, 6),
                latitude=round(ecl_pos["latitude"], 6),
                distance=round(ecl_pos["distance"], 8)
            )

        return results

    except Exception as e:
        print(f"Calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")

def topocentric_vec_j2000(target: str, et: float, lat_deg: float, lon_deg: float, elev_m: float) -> Any:
    """Calculate topocentric position using spkcpo for proper LT+S corrections"""
    # Earth figure from SPICE
    _, radii = spice.bodvrd("EARTH", "RADII", 3)
    re, rp = radii[0], radii[2]
    f = (re - rp) / re

    lon = np.radians(lon_deg)
    lat = np.radians(lat_deg)
    alt_km = elev_m / 1000.0

    # Observer position in ITRF93
    obs_itrf = spice.georec(lon, lat, alt_km, re, f)

    # Use spkcpo for proper topocentric calculation with LT+S
    state, _ = spice.spkcpo(
        target, et,
        "J2000", "OBSERVER", "LT+S",
        obs_itrf, "EARTH", "ITRF93"
    )
    pos_j2000 = state[:3]

    return pos_j2000

def convert_to_ecliptic_of_date_spice(pos_j2000: np.ndarray, et: float) -> Dict[str, float]:
    """Convert to ecliptic coordinates of date using SPICE frames"""
    try:
        # Use SPICE frame transformation: J2000 → ECLIPDATE
        rotation_matrix = spice.pxform("J2000", "ECLIPDATE", et)

        # Transform position vector
        ecl_vector = np.dot(rotation_matrix, pos_j2000)

        # Convert to spherical coordinates
        lon_rad = np.arctan2(ecl_vector[1], ecl_vector[0])
        lat_rad = np.arcsin(ecl_vector[2] / np.linalg.norm(ecl_vector))
        distance_km = np.linalg.norm(ecl_vector)

        return {
            "longitude": (np.degrees(lon_rad) + 360.0) % 360.0,
            "latitude": np.degrees(lat_rad),
            "distance": distance_km / 149597870.7
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
            "Saturn": "SATURN BARYCENTER"
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

@app.on_event("shutdown")
async def cleanup_spice() -> None:
    """Clean up SPICE kernels on shutdown

    CRITICAL: This is the ONLY place where kclear() is called.
    No SPICE state modification during request processing.
    """
    try:
        spice.kclear()
        print("✓ SPICE kernels cleared")
    except Exception:
        pass  # nosec B110 - Safe to ignore cleanup failures

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check with frame validation"""
    try:
        et = spice.str2et("2024-01-01T00:00:00")

        # Test required frame transforms (same as /calculate endpoint)
        spice.pxform("ITRF93", "J2000", et)
        spice.pxform("J2000", "ECLIPDATE", et)  # Validate ecliptic-of-date frame

        # Get Earth radii for debugging
        _, radii = spice.bodvrd("EARTH", "RADII", 3)

        return {
            "status": "ok",
            "kernels": int(spice.ktotal('ALL')),
            "spice_version": spice.tkvrsn('TOOLKIT'),
            "earth_radii_km": [round(r, 3) for r in radii],
            "coordinate_system": "ecliptic_of_date",
            "aberration_correction": "LT+S"
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/debug")
async def debug_info() -> Dict[str, Any]:
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
            "spice_version": spice.tkvrsn('TOOLKIT'),
            "kernels_loaded": int(spice.ktotal('ALL')),
            "target_bodies": bodies,
            "aberration_correction": "LT+S",
            "reference_frame": "J2000",
            "observer_frame": "ITRF93",
            "coordinate_system": "ecliptic_of_date",
            "obliquity_formula": "IAU_1980",
            "topocentric_method": "spkcpo",
            "earth_figure": "SPICE_bodvrd_georec"
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import os
    import uvicorn
    if os.getenv("ENV", "dev") == "dev":
        uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104