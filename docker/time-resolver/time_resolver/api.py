"""
Time Resolver API - Minimal FastAPI shim for historical timezone resolution
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from .core import resolve_time, get_tzdb_version, get_system_health

app = FastAPI(title="Time Resolver")

class Place(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    lon: float = Field(..., ge=-180, le=180, description="Longitude in degrees")

class ResolveReq(BaseModel):
    local_datetime: str = Field(
        ...,
        description="Local datetime (ISO 8601 format without timezone)",
        example="1962-07-02T23:33:00"
    )
    place: Place
    tz_label_user: Optional[str] = Field(
        None,
        description="User-provided timezone identifier"
    )
    assume_dst: Optional[bool] = Field(
        None,
        description="Assume DST is active (for as_entered mode)"
    )
    parity_profile: Literal["strict_history","astro_com","clairvision","as_entered"] = Field(
        "strict_history",
        description="Time resolution mode"
    )
    calendar: Literal["civil","julian"] = Field(
        "civil",
        description="Calendar system (currently only civil supported)"
    )

@app.post("/v1/time/resolve")
def post_resolve(req: ResolveReq):
    """
    Resolve historical timezone for local datetime

    Minimal API that adapts requests to the core resolver format.
    """
    try:
        # Convert minimal request to core resolver format
        payload = {
            "local_datetime": req.local_datetime,
            "latitude": req.place.lat,
            "longitude": req.place.lon,
            "parity_profile": req.parity_profile,
            "user_provided_zone": req.tz_label_user,
            "user_provided_offset": None  # Could be derived from assume_dst if needed
        }

        # Handle calendar system
        if req.calendar == "julian":
            raise HTTPException(status_code=400, detail="Julian calendar not yet supported")

        # Call core resolver and return result directly
        return resolve_time(payload)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Minimal health check
@app.get("/health")
def health():
    """Simple health check"""
    return {
        "status": "healthy",
        "tzdb_version": get_tzdb_version()
    }

# Comprehensive health check with operational details
@app.get("/healthz")
def healthz():
    """Comprehensive health check with tzdb and patch versions"""
    return get_system_health()