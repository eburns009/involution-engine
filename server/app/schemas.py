# server/app/schemas.py
from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field, root_validator

BodyName = Literal[
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "TrueNode", "MeanNode"
]
FrameType = Literal["ecliptic_of_date", "equatorial"]
EpochType = Literal["of_date", "J2000"]
SystemType = Literal["tropical", "sidereal"]
ParityProfile = Literal["strict_history", "best_effort", "modern_only"]


class Place(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)


class When(BaseModel):
    utc: Optional[str] = None
    local_datetime: Optional[str] = None
    place: Optional[Place] = None

    @root_validator
    def validate_when_fields(cls, values):
        utc = values.get("utc")
        local_datetime = values.get("local_datetime")
        place = values.get("place")

        has_utc = bool(utc)
        has_local = bool(local_datetime) and place is not None

        if (has_utc and has_local) or (not has_utc and not has_local):
            raise ValueError('Provide either "utc" OR ("local_datetime" + "place")')

        return values


class Ayanamsha(BaseModel):
    id: str  # e.g., "FAGAN_BRADLEY_DYNAMIC"


class Frame(BaseModel):
    type: FrameType = "ecliptic_of_date"


class PositionsRequest(BaseModel):
    when: When
    system: SystemType
    ayanamsha: Optional[Ayanamsha] = None
    frame: Optional[Frame] = None
    epoch: Optional[EpochType] = "of_date"
    bodies: List[BodyName] = Field(..., min_items=1)
    parity_profile: Optional[ParityProfile] = None


class TimeResolveRequest(BaseModel):
    local_datetime: str
    place: Place
    parity_profile: Optional[ParityProfile] = "strict_history"


class BodyOut(BaseModel):
    name: BodyName
    lon_deg: float
    lat_deg: Optional[float] = None
    ra_hours: Optional[float] = None
    dec_deg: Optional[float] = None


class AyanamshaOut(BaseModel):
    id: str
    value_deg: Optional[float] = None


class ProvenanceOut(BaseModel):
    tzdb_version: str
    patch_version: str
    parity_profile: Optional[str] = None
    ayanamsha: Optional[AyanamshaOut] = None
    kernels_bundle: str
    reference_frame: str
    epoch: str
    ephemeris: str  # "DE440" or "DE441"


class PositionsResponse(BaseModel):
    utc: str
    provenance: ProvenanceOut
    bodies: List[BodyOut]
    etag: Optional[str] = None


class TimeResolveResponse(BaseModel):
    utc: str
    provenance: dict


class GeocodeResult(BaseModel):
    name: str
    lat: float
    lon: float
    country: Optional[str] = None
    admin1: Optional[str] = None


class GeocodeResponse(BaseModel):
    results: List[GeocodeResult]


class HealthzResponse(BaseModel):
    status: str = "healthy"
    timestamp: Optional[str] = None
    version: Optional[str] = None
    kernels: dict
    cache: dict
    pool: dict
    ephemeris: dict
    time: dict


class ErrorOut(BaseModel):
    code: str
    title: str
    detail: Optional[str] = None
    tip: Optional[str] = None