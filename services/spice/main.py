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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
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
    """Calculate topocentric position using simple approach"""
    # Get geocentric position
    pos_geo, _ = spice.spkpos(target, et, "J2000", "LT+S", "399")

    # Get observer position in J2000
    _, radii = spice.bodvrd("EARTH", "RADII", 3)
    re, rp = radii[0], radii[2]
    f = (re - rp) / re

    lon = np.radians(lon_deg)
    lat = np.radians(lat_deg)
    alt_km = elev_m / 1000.0

    # Observer position in ITRF93
    obs_itrf = spice.georec(lon, lat, alt_km, re, f)

    # Transform to J2000
    transform_matrix = spice.pxform("ITRF93", "J2000", et)
    obs_j2000 = spice.mxv(transform_matrix, obs_itrf)

    # Topocentric = geocentric - observer
    return pos_geo - obs_j2000

def convert_to_ecliptic_of_date(pos_j2000: np.ndarray, et: float) -> Dict[str, float]:
    """Convert to ecliptic coordinates using SPICE frames"""
    # Transform J2000 → ecliptic J2000 (fixed ecliptic plane)
    rot = spice.pxform("J2000", "ECLIPJ2000", et)
    ecl_vector = spice.mxv(rot, pos_j2000)

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
        spice.pxform("J2000", "ECLIPJ2000", et)

        return {
            "status": "ok",
            "kernels": int(spice.ktotal('ALL')),
            "spice_version": spice.tkvrsn('TOOLKIT')
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)