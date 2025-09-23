from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import spiceypy as spice
import numpy as np
import os
from typing import Dict
from datetime import datetime

app = FastAPI(
    title="Involution SPICE Service",
    version="1.0.0",
    description="Research-grade planetary position calculations"
)

class ChartRequest(BaseModel):
    birth_time: str  # ISO 8601 UTC
    latitude: float
    longitude: float
    elevation: float = 0.0
    ayanamsa: str = "lahiri"

class PlanetPosition(BaseModel):
    longitude: float  # Sidereal ecliptic longitude
    latitude: float   # Ecliptic latitude
    distance: float   # Distance in AU

@app.on_event("startup")
async def initialize_spice():
    """Load SPICE kernels"""
    metakernel = "/app/kernels/involution.tm"

    # For development, use local kernels directory
    if not os.path.exists(metakernel):
        metakernel = "../../kernels/involution.tm"

    if not os.path.exists(metakernel):
        print("WARNING: Metakernel not found. SPICE calculations will fail.")
        print("Run the kernel download script first: ./tools/download_kernels.sh")
        return

    try:
        spice.furnsh(metakernel)

        # Verify SPICE is operational
        et = spice.str2et("2024-01-01T12:00:00")
        state, _ = spice.spkezr("10", et, "J2000", "LT+S", "399")

        print(f"✓ SPICE initialized - Toolkit: {spice.tkvrsn('TOOLKIT')}")
        print(f"✓ Kernels loaded: {spice.ktotal('ALL')}")

    except Exception as e:
        print(f"✗ SPICE initialization failed: {e}")
        raise

@app.post("/calculate", response_model=Dict[str, PlanetPosition])
async def calculate_planetary_positions(request: ChartRequest):
    """Calculate topocentric sidereal positions"""
    try:
        et = spice.str2et(request.birth_time)

        # Planet center NAIF IDs (corrected from expert review)
        bodies = {
            "Sun": "10", "Moon": "301", "Mercury": "199", "Venus": "299",
            "Mars": "499", "Jupiter": "599", "Saturn": "699"
        }

        results = {}

        for name, body_id in bodies.items():
            # Get apparent geocentric position
            pos_geo, _ = spice.spkpos(body_id, et, "J2000", "LT+S", "399")

            # Calculate topocentric correction using SPICE Earth constants
            obs_j2000 = calculate_observer_vector(et, request.latitude, request.longitude, request.elevation)
            pos_topo = pos_geo - obs_j2000

            # Convert to ecliptic of date using SPICE frames (no custom math)
            ecl_pos = convert_to_ecliptic_of_date(pos_topo, et)

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

def calculate_observer_vector(et: float, lat_deg: float, lon_deg: float, elev_m: float) -> np.ndarray:
    """Calculate observer position using SPICE Earth constants"""
    # Get Earth radii from loaded kernels
    _, radii = spice.bodvrd("EARTH", "RADII", 3)
    re, rp = radii[0], radii[2]
    f = (re - rp) / re

    # Convert to radians and km
    lon_rad = np.radians(lon_deg)
    lat_rad = np.radians(lat_deg)
    alt_km = elev_m / 1000.0

    # Observer position in ITRF93 using SPICE
    r_itrf = spice.georec(lon_rad, lat_rad, alt_km, re, f)

    # Transform ITRF93 → J2000
    transform_matrix = spice.pxform("ITRF93", "J2000", et)
    obs_j2000 = spice.mxv(transform_matrix, r_itrf)

    return obs_j2000

def convert_to_ecliptic_of_date(pos_j2000: np.ndarray, et: float) -> Dict[str, float]:
    """Convert to ecliptic coordinates using SPICE frames"""
    # Use SPICE built-in frame transformation (expert recommendation)
    rotation_matrix = spice.pxform("J2000", "ECLIPDATE", et)
    ecl_vector_km = spice.mxv(rotation_matrix, pos_j2000)

    # Convert to spherical coordinates
    longitude_rad = np.arctan2(ecl_vector_km[1], ecl_vector_km[0])
    latitude_rad = np.arcsin(ecl_vector_km[2] / np.linalg.norm(ecl_vector_km))
    distance_km = np.linalg.norm(ecl_vector_km)

    return {
        "longitude": (np.degrees(longitude_rad) + 360) % 360,
        "latitude": np.degrees(latitude_rad),
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
    """Health check with SPICE verification"""
    try:
        et = spice.str2et("2024-01-01T12:00:00")
        state, _ = spice.spkezr("10", et, "J2000", "LT+S", "399")

        return {
            "status": "healthy",
            "spice_version": spice.tkvrsn('TOOLKIT'),
            "kernels_loaded": spice.ktotal('ALL'),
            "test_calculation": "passed"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"SPICE error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)