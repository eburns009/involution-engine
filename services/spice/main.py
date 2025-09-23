from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import spiceypy as spice
import numpy as np
import os
from typing import Dict
from pathlib import Path

app = FastAPI(
    title="Involution SPICE Service",
    version="1.0.0",
    description="Research-grade planetary position calculations"
)

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
async def initialize_spice():
    """Load SPICE kernels with proper validation"""
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

    except Exception as e:
        print(f"✗ SPICE initialization failed: {e}")
        raise

@app.post("/calculate", response_model=Dict[str, PlanetPosition])
async def calculate_planetary_positions(request: ChartRequest):
    """Calculate topocentric sidereal positions using spkcpo"""
    try:
        et = spice.str2et(request.birth_time)

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
                body_id, et, request.latitude, request.longitude, request.elevation
            )

            # Convert to ecliptic of date using SPICE frames
            ecl_pos = convert_to_ecliptic_of_date(pos_topo_j2000, et)

            # Apply ayanamsa correction
            ayanamsa_deg = calculate_ayanamsa(request.ayanamsa, et)
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

def topocentric_vec_j2000(target: str, et: float, lat_deg: float, lon_deg: float, elev_m: float):
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

def convert_to_ecliptic_of_date(pos_j2000: np.ndarray, et: float) -> Dict[str, float]:
    """Convert to ecliptic coordinates of date using manual transformation"""
    # Calculate mean obliquity of ecliptic for the date
    # Use IAU 1980 formula for mean obliquity
    jd_tt = spice.j2000() + et / spice.spd()
    T = (jd_tt - 2451545.0) / 36525.0

    # Mean obliquity in arcseconds, then convert to radians
    epsilon_arcsec = 23.0 * 3600 + 26.0 * 60 + 21.448 - 46.8150 * T - 0.00059 * T * T + 0.001813 * T * T * T
    epsilon_rad = np.radians(epsilon_arcsec / 3600.0)

    # Transform J2000 → mean ecliptic of date manually
    # This is a rotation about the x-axis by the obliquity angle
    cos_eps = np.cos(epsilon_rad)
    sin_eps = np.sin(epsilon_rad)

    rot_matrix = np.array([
        [1.0, 0.0, 0.0],
        [0.0, cos_eps, sin_eps],
        [0.0, -sin_eps, cos_eps]
    ])

    ecl_vector = np.dot(rot_matrix, pos_j2000)

    # Convert to spherical coordinates
    lon_rad = np.arctan2(ecl_vector[1], ecl_vector[0])
    lat_rad = np.arcsin(ecl_vector[2] / np.linalg.norm(ecl_vector))
    distance_km = np.linalg.norm(ecl_vector)

    return {
        "longitude": (np.degrees(lon_rad) + 360.0) % 360.0,
        "latitude": np.degrees(lat_rad),
        "distance": distance_km / 149597870.7
    }

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

@app.get("/health")
async def health_check():
    """Health check with frame validation"""
    try:
        et = spice.str2et("2024-01-01T00:00:00")

        # Test required frame transforms
        spice.pxform("ITRF93", "J2000", et)
        # Note: Using manual ecliptic-of-date calculation, no frame validation needed

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
async def debug_info():
    """Debug endpoint with detailed configuration info"""
    try:
        et = spice.str2et("2024-01-01T00:00:00")

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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)