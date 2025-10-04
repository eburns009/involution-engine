"""
Pydantic models for API requests and responses.

This module contains all data models used by the Involution SPICE Service API.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Type aliases
Zodiac = Literal["tropical", "sidereal"]
HouseSystem = Literal["placidus", "whole-sign", "equal"]
McHemisphere = Literal["south", "north", "auto"]

# Available celestial bodies for calculation
AVAILABLE_BODIES = {
    "Sun": "SUN",
    "Moon": "MOON",
    "Mercury": "MERCURY BARYCENTER",
    "Venus": "VENUS BARYCENTER",
    "Mars": "MARS BARYCENTER",
    "Jupiter": "JUPITER BARYCENTER",
    "Saturn": "SATURN BARYCENTER",
    # TODO: Add Uranus, Neptune, Pluto, True Node, Mean Node, ASC, MC
}


# ============================================================================
# Planetary Position Models
# ============================================================================


class ChartRequest(BaseModel):
    """Request model for planetary position calculations."""

    birth_time: datetime = Field(
        ...,
        description="ISO 8601 with timezone, e.g. 2024-06-21T18:00:00Z or 2024-06-21T12:00:00-06:00",
    )
    latitude: float = Field(..., ge=-90, le=90, description="Degrees, -90..90")
    longitude: float = Field(..., ge=-180, le=180, description="Degrees, -180..180")
    elevation: float = Field(0.0, ge=-500, le=10000, description="Meters, -500..10000")
    zodiac: Zodiac = "sidereal"
    ayanamsa: Literal["lahiri", "fagan_bradley"] = "lahiri"
    bodies: list[str] = Field(default_factory=lambda: list(AVAILABLE_BODIES.keys()))

    @field_validator("birth_time")
    @classmethod
    def ensure_timezone_and_utc(cls, v: datetime) -> datetime:
        """Ensure birth_time has timezone and convert to UTC."""
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("birth_time must include a timezone (Z or ±HH:MM)")
        return v.astimezone(UTC)

    @field_validator("bodies")
    @classmethod
    def validate_bodies(cls, v: list[str]) -> list[str]:
        """Validate requested celestial bodies."""
        invalid = set(v) - set(AVAILABLE_BODIES.keys())
        if invalid:
            raise ValueError(f"Invalid bodies requested: {sorted(invalid)}")
        if not v:
            raise ValueError("At least one body is required")
        return v


class PlanetPosition(BaseModel):
    """Position data for a single celestial body."""

    longitude: float
    latitude: float
    distance: float
    # UI-ready fields
    sign: str | None = None  # e.g. "Aries", "Taurus"
    degree: float | None = None  # 0-29.999... within sign
    degrees: int | None = None  # DMS degrees component
    minutes: int | None = None  # DMS minutes component
    seconds: float | None = None  # DMS seconds component
    speed: float | None = None  # degrees per day (longitude)
    is_retrograde: bool | None = None  # True if speed < 0


class ApiMeta(BaseModel):
    """Metadata for API responses."""

    service_version: str
    spice_version: str
    kernel_set_tag: str
    ecliptic_frame: str
    zodiac: Zodiac
    ayanamsa_deg: float | None
    request_id: str
    timestamp: float


class CalculationResponse(BaseModel):
    """Response model for planetary position calculations."""

    data: dict[str, PlanetPosition]
    meta: ApiMeta


# ============================================================================
# House System Models
# ============================================================================


class HousesRequest(BaseModel):
    """Request model for house cusp calculations."""

    birth_time: datetime = Field(..., description="ISO 8601 with tz, e.g. 2024-06-21T18:00:00Z")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)  # east +
    elevation: float = Field(0.0, ge=-500, le=10000)
    zodiac: Zodiac = "sidereal"
    ayanamsa: Literal["lahiri", "fagan_bradley"] = "lahiri"
    system: HouseSystem = "placidus"
    mc_hemisphere: McHemisphere = "south"

    @field_validator("birth_time")
    @classmethod
    def ensure_timezone_and_utc(cls, v: datetime) -> datetime:
        """Ensure birth_time has timezone and convert to UTC."""
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("birth_time must include a timezone (Z or ±HH:MM)")
        return v.astimezone(UTC)


class HousesResponse(BaseModel):
    """Response model for house cusp calculations."""

    system: HouseSystem
    frame: str
    coordinate_system: str
    ecliptic_model: str
    zodiac: Zodiac
    ayanamsa: str | None
    ayanamsa_deg: float | None
    asc: float
    mc: float
    cusps: list[float]  # 12 cusp longitudes (deg), 0..360


# ============================================================================
# Time Resolution Models
# ============================================================================


class TimeResolveRequest(BaseModel):
    """Request model for local datetime to UTC conversion."""

    local_datetime: str = Field(
        ..., description="Local datetime in ISO format (YYYY-MM-DDTHH:MM:SS)"
    )
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    timezone_override: str | None = Field(
        None, description="Manual timezone override (IANA timezone name, e.g. 'America/Chicago')"
    )


class TimeResolveResponse(BaseModel):
    """Response model for local datetime to UTC conversion."""

    utc_time: str = Field(..., description="UTC time in ISO Z format")
    timezone: str = Field(..., description="IANA timezone identifier")
    offset_hours: float = Field(..., description="UTC offset in hours at the given datetime")
    is_dst: bool = Field(..., description="Whether daylight saving time was active")
