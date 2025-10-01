import json
import logging
import math
import os
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from typing import Literal

import numpy as np
import spiceypy as spice
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator
from security import SecurityConfig
from security import SecurityMetrics
from security import get_client_ip
from security import is_suspicious_request
from security import security_metrics
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from time_resolver_v2 import resolve_time as resolve_time_v2

# Time resolver imports

# Contract Constants
ECL_FRAME = "ECLIPDATE"
COORD_SYSTEM = "ecliptic_of_date"
OBLIQUITY_MODEL = "IAU1980-mean"
ABCORR = "LT+S"
METAKERNEL_PATH = os.getenv("METAKERNEL_PATH", "kernels/involution.tm")
KERNEL_SET_TAG = os.getenv("KERNEL_SET_TAG", "2024-Q3")
SERVICE_VERSION = "2.0.0"

# Zodiac support
Zodiac = Literal["tropical", "sidereal"]

# Time Resolver Parity Profiles
class ParityProfile(str, Enum):
    strict_history = "strict_history"
    astro_com = "astro_com"
    clairvision = "clairvision"
    as_entered = "as_entered"

def real_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For header, fallback to socket IP"""
    # First IP in XFF is the client; fall back to socket
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

storage_uri = os.getenv("RATE_LIMIT_STORAGE_URI")  # e.g., "redis://your-redis:6379/0"
limiter = Limiter(key_func=real_ip, storage_uri=storage_uri)

# Configure structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler()]
)
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
            "count": count
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
            "window_minutes": window_minutes
        }

# Global metrics collector
metrics = MetricsCollector()

def log_calculation(target: str, et: float, frame: str, abcorr: str, ayanamsa: str,
                   latency_ms: float, success: bool, error: str | None = None) -> None:
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
        "success": success
    }
    if error:
        log_entry["error"] = error

    logger.info(json.dumps(log_entry))

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    # Resolve metakernel path (supports both relative and absolute paths)
    if os.path.isabs(METAKERNEL_PATH):
        metakernel = METAKERNEL_PATH
    else:
        # Relative to the file so dev + container both work
        base = Path(__file__).resolve().parent
        metakernel = str(base / METAKERNEL_PATH)

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

        # Log TZDB version for time resolution tracking
        try:
            from time_resolver_v2 import get_tzdb_version
            tzdb_version = get_tzdb_version()
            print(f"✓ Time Resolver TZDB: {tzdb_version}")
        except Exception as e:
            print(f"⚠ Could not determine TZDB version: {e}")

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
    lifespan=lifespan
)

app.state.limiter = limiter


def _rl_handler(request, exc):  # correct handler signature
    return JSONResponse(status_code=429, content={"detail":"rate limit exceeded"})
app.add_exception_handler(RateLimitExceeded, _rl_handler)

# In tests, disable rate limiting via env
if os.getenv("DISABLE_RATE_LIMIT", "0") == "1":
    class _NoopLimiter:
        enabled = False
        def limit(self, *a: Any, **k: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def deco(fn: Callable[..., Any]) -> Callable[..., Any]: return fn
            return deco
    limiter = _NoopLimiter()  # type: ignore[assignment]
    app.state.limiter = limiter

# Security Middleware Configuration
# =================================

# 1. Trusted Host Protection
TRUSTED_HOSTS = [h.strip() for h in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,*.yourdomain.com").split(",")]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)

# 2. GZip Compression for Performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Security Headers Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
    """Add comprehensive security headers to all responses"""
    response = await call_next(request)

    # Only add security headers in production or when explicitly enabled
    if os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() == "true":
        # HSTS - Force HTTPS for 1 year
        response.headers["Strict-Transport-Security"] = f"max-age={os.getenv('HSTS_MAX_AGE', '31536000')}; includeSubDomains; preload"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = os.getenv("X_FRAME_OPTIONS", "DENY")

        # XSS Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy
        csp_policy = os.getenv("CSP_POLICY", "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'")
        response.headers["Content-Security-Policy"] = csp_policy

        # Referrer Policy
        response.headers["Referrer-Policy"] = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")

        # Permissions Policy (Feature Policy)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=(), usb=()"

        # Remove server headers that reveal implementation details
        response.headers.pop("Server", None)

    return response

# 4. Security Monitoring and Threat Detection Middleware
@app.middleware("http")
async def security_monitoring_middleware(request: Request, call_next: Callable) -> Response:
    """Monitor requests for security threats and suspicious patterns"""

    # Get client IP considering proxy headers
    client_ip = get_client_ip(dict(request.headers), request.client.host if request.client else None)

    # Check for suspicious request patterns
    suspicious_reason = is_suspicious_request(dict(request.headers), str(request.url.path))
    if suspicious_reason:
        security_metrics.record_suspicious_request(f"{client_ip}: {suspicious_reason}")
        # Log but don't block - allow further analysis
        logging.warning(f"Suspicious request from {client_ip}: {suspicious_reason}")

    # Validate request size
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_len = int(content_length)
            max_size = int(os.getenv("MAX_REQUEST_SIZE", "1048576"))
            if content_len > max_size:
                security_metrics.record_blocked_request(f"Request too large: {content_len} bytes")
                raise HTTPException(status_code=413, detail="Request entity too large")
        except ValueError:
            security_metrics.record_blocked_request("Invalid content-length header")
            raise HTTPException(status_code=400, detail="Invalid content-length header")

    return await call_next(request)

# 5. Request ID and Logging Middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next: Callable) -> Response:
    """Add request ID and comprehensive logging"""
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Log request details (exclude sensitive headers)
    sensitive_headers = {"authorization", "x-api-key", "cookie"}
    safe_headers = {k: v for k, v in request.headers.items() if k.lower() not in sensitive_headers}

    if os.getenv("ENABLE_REQUEST_LOGGING", "true").lower() == "true":
        logging.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "query_params": str(request.query_params),
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
                "headers": safe_headers,
            }
        )

    # Process request and measure timing
    start_time = time.time()
    try:
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log response
        duration_ms = (time.time() - start_time) * 1000
        if os.getenv("ENABLE_REQUEST_LOGGING", "true").lower() == "true":
            logging.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )

        return response

    except Exception as e:
        # Log errors with request context
        duration_ms = (time.time() - start_time) * 1000
        logging.error(
            "Request failed",
            extra={
                "request_id": request_id,
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True
        )
        raise

# 5. Rate Limiting Middleware
if os.getenv("DISABLE_RATE_LIMIT", "0") != "1":
    app.add_middleware(SlowAPIMiddleware)

# 6. CORS Configuration
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]
ALLOWED_METHODS = [m.strip() for m in os.getenv("ALLOWED_METHODS", "GET,POST").split(",")]
ALLOWED_HEADERS = [h.strip() for h in os.getenv("ALLOWED_HEADERS", "content-type,authorization,x-request-id").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
    allow_credentials=os.getenv("ALLOW_CREDENTIALS", "true").lower() == "true",
)

# SPICE State Management:
# - CSPICE is NOT thread-safe, use one process per worker
# - furnsh/kclear ONLY called at startup/shutdown, NEVER mid-request
# - Global SPICE state is immutable during request processing

class ChartRequest(BaseModel):
    birth_time: datetime = Field(
        ...,
        description="ISO 8601 with timezone, e.g. 2024-06-21T18:00:00Z or 2024-06-21T12:00:00-06:00"
    )
    latitude: float = Field(..., ge=-90, le=90, description="Degrees, -90..90")
    longitude: float = Field(..., ge=-180, le=180, description="Degrees, -180..180")
    elevation: float = Field(0.0, ge=-500, le=10000, description="Meters, -500..10000")
    # NEW: which zodiac to report in
    zodiac: Zodiac = "sidereal"
    # Ayanamsa is only used when zodiac == "sidereal"
    ayanamsa: Literal["lahiri", "fagan_bradley"] = "lahiri"
    # Parity profile for auditability (legacy endpoint still supports this)
    parity_profile: ParityProfile = Field(
        ParityProfile.strict_history,
        description="Time resolution mode (informational for legacy endpoint)"
    )

    @field_validator("birth_time")
    @classmethod
    def ensure_timezone_and_utc(cls, v: datetime) -> datetime:
        # Must include tzinfo; normalize to UTC for downstream use
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("birth_time must include a timezone (Z or ±HH:MM)")
        return v.astimezone(UTC)

class ChartRequestWithTimeResolution(BaseModel):
    local_datetime: str = Field(
        ...,
        description="Local datetime in ISO format without timezone, e.g. 1962-07-02T23:33:00"
    )
    latitude: float = Field(..., ge=-90, le=90, description="Degrees, -90..90")
    longitude: float = Field(..., ge=-180, le=180, description="Degrees, -180..180")
    elevation: float = Field(0.0, ge=-500, le=10000, description="Meters, -500..10000")

    # Time resolution settings
    parity_profile: ParityProfile = Field(
        ParityProfile.strict_history,
        description="Time resolution mode for historical accuracy"
    )
    user_provided_zone: str | None = Field(
        None,
        description="User-provided timezone identifier (for as_entered mode)"
    )
    user_provided_offset: int | None = Field(
        None,
        description="User-provided UTC offset in seconds (for as_entered mode)"
    )

    # NEW: which zodiac to report in
    zodiac: Zodiac = "sidereal"
    # Ayanamsa is only used when zodiac == "sidereal"
    ayanamsa: Literal["lahiri", "fagan_bradley"] = "lahiri"

    @field_validator("local_datetime")
    @classmethod
    def validate_local_datetime(cls, v: str) -> str:
        try:
            # Validate it can be parsed as ISO datetime
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("local_datetime must be in ISO 8601 format without timezone, e.g. 1962-07-02T23:33:00")

class PlanetPosition(BaseModel):
    longitude: float
    latitude: float
    distance: float

class ApiMeta(BaseModel):
    service_version: str
    spice_version: str
    kernel_set_tag: str
    ecliptic_frame: str
    zodiac: Zodiac
    ayanamsa_deg: float | None
    observer_frame_used: str
    request_id: str
    timestamp: float

    # Parity profile used for this calculation (for auditability)
    parity_profile: ParityProfile = Field(
        ParityProfile.strict_history,
        description="Time resolution mode used for this chart"
    )

    # Time resolution metadata (when using local_datetime)
    time_resolution: dict[str, Any] | None = Field(
        None,
        description="Time resolution metadata including UTC, zone_id, confidence, etc."
    )
    chart_warnings: list[str] = Field(
        default_factory=list,
        description="Chart-level warnings (e.g., low time resolution confidence)"
    )

class CalculationResponse(BaseModel):
    data: dict[str, PlanetPosition]
    meta: ApiMeta

# Houses models
HouseSystem = Literal["placidus", "whole-sign", "equal"]
McHemisphere = Literal["south", "north", "auto"]

class HousesRequest(BaseModel):
    # Time can be provided in two ways (same as ChartRequest)
    birth_time: datetime | None = Field(
        None,
        description="Legacy: ISO 8601 with timezone (use local_datetime for historical accuracy)"
    )
    local_datetime: str | None = Field(
        None,
        description="Local datetime in ISO format without timezone, e.g. 1962-07-02T23:33:00"
    )

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)  # east +
    elevation: float = Field(0.0, ge=-500, le=10000)

    # Time resolution settings (used with local_datetime)
    parity_profile: ParityProfile | None = Field(
        ParityProfile.strict_history,
        description="Time resolution mode for historical accuracy"
    )
    user_provided_zone: str | None = Field(None, description="User-provided timezone identifier")
    user_provided_offset: int | None = Field(None, description="User-provided UTC offset in seconds")

    zodiac: Zodiac = "sidereal"   # NEW
    ayanamsa: Literal["lahiri","fagan_bradley"] = "lahiri"
    system: HouseSystem = "placidus"
    mc_hemisphere: McHemisphere = "south"

    @field_validator("birth_time")
    @classmethod
    def ensure_timezone_and_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        # Must include tzinfo; normalize to UTC for downstream use
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("birth_time must include a timezone (Z or ±HH:MM)")
        return v.astimezone(UTC)

    @field_validator("local_datetime")
    @classmethod
    def validate_local_datetime(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("local_datetime must be in ISO 8601 format without timezone")

    @model_validator(mode='after')
    def validate_time_inputs(self):
        if self.birth_time is None and self.local_datetime is None:
            raise ValueError("Either birth_time or local_datetime must be provided")
        if self.birth_time is not None and self.local_datetime is not None:
            raise ValueError("Provide either birth_time OR local_datetime, not both")
        return self

class HousesResponse(BaseModel):
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


# Time Resolver Models

class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"

class TimeResolveRequest(BaseModel):
    local_datetime: str = Field(
        ...,
        description="Local datetime (ISO 8601 format without timezone)",
        example="1962-07-02T23:33:00"
    )
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    parity_profile: ParityProfile = Field(
        ParityProfile.strict_history,
        description="Resolution mode"
    )
    user_provided_zone: str | None = Field(
        None,
        description="User-provided timezone identifier (for as_entered mode)"
    )
    user_provided_offset: int | None = Field(
        None,
        description="User-provided UTC offset in seconds (for as_entered mode)"
    )

class TimeProvenance(BaseModel):
    tzdb_version: str
    sources: list[str]
    resolution_mode: str
    patches_applied: list[str]

class TimeResolveResponseModel(BaseModel):
    utc: str = Field(..., description="UTC datetime in ISO 8601 format")
    zone_id: str = Field(..., description="IANA timezone identifier")
    offset_seconds: int = Field(..., description="UTC offset in seconds")
    dst_active: bool = Field(..., description="Whether daylight saving time was active")
    confidence: ConfidenceLevel = Field(..., description="Confidence level in the resolution")
    reason: str = Field(..., description="Human-readable explanation of resolution method")
    notes: list[str] = Field(default_factory=list, description="Additional notes")
    provenance: TimeProvenance = Field(..., description="Data provenance information")
    warnings: list[str] = Field(default_factory=list, description="Warnings about potential issues")


@app.post("/calculate", response_model=CalculationResponse)
@limiter.limit("10/minute")
async def calculate_planetary_positions(request: Request, chart: ChartRequest) -> CalculationResponse:
    """Calculate topocentric sidereal positions using spkcpo (Legacy endpoint)

    IMPORTANT: This function only READS from SPICE state.
    No furnsh/kclear calls are made during request processing.
    """
    start_time = time.time()
    et = None
    frame = ECL_FRAME
    abcorr = ABCORR

    try:
        # Legacy mode: use provided birth_time
        et = spice.str2et(chart.birth_time.isoformat().replace("+00:00", "Z"))

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

        # Calculate ayanamsa once if needed
        ayanamsa_deg = calculate_ayanamsa(chart.ayanamsa, et) if chart.zodiac == "sidereal" else None

        # Track observer frame (will be same for all bodies at this epoch)
        observer_frame_used = None

        for name, body_id in bodies.items():
            body_start_time = time.time()

            # Get topocentric position using corrected SPICE call
            pos_topo_j2000, obs_frame = topocentric_vec_j2000(
                body_id, et, chart.latitude, chart.longitude, chart.elevation
            )

            # Capture observer frame from first calculation
            if observer_frame_used is None:
                observer_frame_used = obs_frame

            # Convert to ecliptic of date using SPICE frames
            ecl_pos = convert_to_ecliptic_of_date_spice(pos_topo_j2000, et)

            # Apply zodiac-specific longitude reporting
            tropical_lon = ecl_pos["longitude"]
            if chart.zodiac == "sidereal":
                out_lon = (tropical_lon - ayanamsa_deg) % 360
            else:
                out_lon = tropical_lon

            results[name] = PlanetPosition(
                longitude=round(out_lon, 6),
                latitude=round(ecl_pos["latitude"], 6),
                distance=round(ecl_pos["distance"], 8)
            )

            # Log individual body calculation
            body_latency_ms = (time.time() - body_start_time) * 1000
            log_calculation(body_id, et, frame, abcorr, chart.ayanamsa, body_latency_ms, True)

        # Log overall request
        total_latency_ms = (time.time() - start_time) * 1000
        log_calculation("ALL_BODIES", et or 0, frame, abcorr, chart.ayanamsa if chart.zodiac == "sidereal" else "tropical", total_latency_ms, True)

        # Create meta information
        meta = ApiMeta(
            service_version=SERVICE_VERSION,
            spice_version=spice.tkvrsn('TOOLKIT'),
            kernel_set_tag=KERNEL_SET_TAG,
            ecliptic_frame=ECL_FRAME,
            zodiac=chart.zodiac,
            ayanamsa_deg=round(ayanamsa_deg, 6) if ayanamsa_deg is not None else None,
            observer_frame_used=observer_frame_used or "UNKNOWN",
            request_id=str(uuid.uuid4()),
            timestamp=time.time(),
            parity_profile=chart.parity_profile,  # Echo chosen profile for auditability
            time_resolution=None,  # No time resolution in legacy mode
            chart_warnings=[]      # No warnings in legacy mode
        )

        return CalculationResponse(data=results, meta=meta)

    except Exception as e:
        # Log error with timing info
        error_latency_ms = (time.time() - start_time) * 1000
        log_calculation("ERROR", et or 0, frame, abcorr, chart.ayanamsa if chart.zodiac == "sidereal" else "tropical", error_latency_ms, False, str(e))

        msg = str(e)
        # Map SPICE time parse errors to 422 if anything slips through
        if "SPICE(BADTIMESTRING)" in msg or "SPICE(INVALIDTIME)" in msg or "SPICE(UNPARSEDTIME)" in msg:
            raise HTTPException(status_code=422, detail="Invalid birth_time format; use ISO 8601 with timezone (e.g. 2024-06-21T18:00:00Z)")

        print(f"Calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


@app.post("/calculate-with-time-resolution", response_model=CalculationResponse)
@limiter.limit("10/minute")
async def calculate_planetary_positions_with_time_resolution(request: Request, chart: ChartRequestWithTimeResolution) -> CalculationResponse:
    """Calculate topocentric positions with historical time resolution

    IMPORTANT: This function only READS from SPICE state.
    No furnsh/kclear calls are made during request processing.
    Uses time resolver for historically accurate timezone conversion.
    """
    start_time = time.time()
    et = None
    frame = ECL_FRAME
    abcorr = ABCORR
    time_resolution_result = None
    chart_warnings = []

    try:
        # Use time resolver for historical accuracy
        time_payload = {
            "local_datetime": chart.local_datetime,
            "latitude": chart.latitude,
            "longitude": chart.longitude,
            "parity_profile": chart.parity_profile.value,
            "user_provided_zone": chart.user_provided_zone,
            "user_provided_offset": chart.user_provided_offset
        }

        time_resolution_result = resolve_time_v2(time_payload)

        # Check for low confidence or corrections and add warnings
        confidence_map = {"high": 0.95, "medium": 0.85, "low": 0.7, "unknown": 0.5}
        confidence_val = confidence_map.get(time_resolution_result["confidence"], 0.5)

        if confidence_val < 0.9:
            chart_warnings.append(f"Time resolution confidence is {time_resolution_result['confidence']} ({confidence_val:.0%})")

        if time_resolution_result.get("warnings"):
            chart_warnings.extend([f"Time: {w}" for w in time_resolution_result["warnings"]])

        if time_resolution_result["provenance"]["patches_applied"]:
            chart_warnings.append(f"Historical timezone corrections applied: {', '.join(time_resolution_result['provenance']['patches_applied'])}")

        # Use resolved UTC time
        utc_time_str = time_resolution_result["utc"]
        et = spice.str2et(utc_time_str)

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

        # Calculate ayanamsa once if needed
        ayanamsa_deg = calculate_ayanamsa(chart.ayanamsa, et) if chart.zodiac == "sidereal" else None

        # Track observer frame (will be same for all bodies at this epoch)
        observer_frame_used = None

        for name, body_id in bodies.items():
            body_start_time = time.time()

            # Get topocentric position using corrected SPICE call
            pos_topo_j2000, obs_frame = topocentric_vec_j2000(
                body_id, et, chart.latitude, chart.longitude, chart.elevation
            )

            # Capture observer frame from first calculation
            if observer_frame_used is None:
                observer_frame_used = obs_frame

            # Convert to ecliptic of date using SPICE frames
            ecl_pos = convert_to_ecliptic_of_date_spice(pos_topo_j2000, et)

            # Apply zodiac-specific longitude reporting
            tropical_lon = ecl_pos["longitude"]
            if chart.zodiac == "sidereal":
                out_lon = (tropical_lon - ayanamsa_deg) % 360
            else:
                out_lon = tropical_lon

            results[name] = PlanetPosition(
                longitude=round(out_lon, 6),
                latitude=round(ecl_pos["latitude"], 6),
                distance=round(ecl_pos["distance"], 8)
            )

            # Log individual body calculation
            body_latency_ms = (time.time() - body_start_time) * 1000
            log_calculation(body_id, et, frame, abcorr, chart.ayanamsa, body_latency_ms, True)

        # Log overall request
        total_latency_ms = (time.time() - start_time) * 1000
        log_calculation("ALL_BODIES", et or 0, frame, abcorr, chart.ayanamsa if chart.zodiac == "sidereal" else "tropical", total_latency_ms, True)

        # Create meta information with time resolution data
        meta = ApiMeta(
            service_version=SERVICE_VERSION,
            spice_version=spice.tkvrsn('TOOLKIT'),
            kernel_set_tag=KERNEL_SET_TAG,
            ecliptic_frame=ECL_FRAME,
            zodiac=chart.zodiac,
            ayanamsa_deg=round(ayanamsa_deg, 6) if ayanamsa_deg is not None else None,
            observer_frame_used=observer_frame_used or "UNKNOWN",
            request_id=str(uuid.uuid4()),
            timestamp=time.time(),
            parity_profile=chart.parity_profile,  # Echo chosen profile for auditability
            time_resolution=time_resolution_result,
            chart_warnings=chart_warnings
        )

        return CalculationResponse(data=results, meta=meta)

    except Exception as e:
        # Log error with timing info
        error_latency_ms = (time.time() - start_time) * 1000
        log_calculation("ERROR", et or 0, frame, abcorr, chart.ayanamsa if chart.zodiac == "sidereal" else "tropical", error_latency_ms, False, str(e))

        msg = str(e)
        # Map SPICE time parse errors to 422 if anything slips through
        if "SPICE(BADTIMESTRING)" in msg or "SPICE(INVALIDTIME)" in msg or "SPICE(UNPARSEDTIME)" in msg:
            raise HTTPException(status_code=422, detail="Invalid local_datetime format; use ISO 8601 without timezone (e.g. 1962-07-02T23:33:00)")

        print(f"Calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")

def _observer_pos_in_iau_earth(lat_deg: float, lon_deg: float, elev_m: float) -> np.ndarray:
    """Observer position in the IAU_EARTH body-fixed frame (km)."""
    # WGS-84-like spheroid; keep consistent with your house math
    re = 6378.137  # km
    f  = 1.0/298.257223563
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    alt = elev_m / 1000.0
    # Geodetic → rectangular in body-fixed
    x, y, z = spice.georec(lon, lat, alt, re, f)
    return np.array([x, y, z])

def select_observer_frame(et: float) -> str:
    """
    Use high-precision Earth orientation (ITRF93) when available,
    otherwise fall back to IAU_EARTH for very old/future dates.
    """
    try:
        spice.pxform("ITRF93", "J2000", et)
        return "ITRF93"
    except Exception:
        return "IAU_EARTH"

def topocentric_vec_j2000(target: str, et: float, lat_deg: float, lon_deg: float, elev_m: float) -> tuple[Any, str]:
    """Calculate topocentric position using spkcpo for proper LT+S corrections

    Returns:
        tuple: (position_vector, observer_frame_used)
    """
    # Choose observer frame dynamically based on EOP coverage
    obs_frame = select_observer_frame(et)

    if obs_frame == "ITRF93":
        # Earth figure from SPICE for ITRF93
        _, radii = spice.bodvrd("EARTH", "RADII", 3)
        re, rp = radii[0], radii[2]
        f = (re - rp) / re

        lon = np.radians(lon_deg)
        lat = np.radians(lat_deg)
        alt_km = elev_m / 1000.0

        # Observer position in ITRF93
        obs_pos = spice.georec(lon, lat, alt_km, re, f)
    else:
        # Fallback for historical dates (e.g., 1962): use IAU_EARTH body-fixed frame
        obs_pos = _observer_pos_in_iau_earth(lat_deg, lon_deg, elev_m)

    # Use spkcpo with the chosen frame
    state, _ = spice.spkcpo(
        target, et,
        "J2000", "OBSERVER", "LT+S",
        obs_pos, "EARTH", obs_frame
    )
    pos_j2000 = state[:3]

    return pos_j2000, obs_frame

def apply_precession_iau2006(pos_j2000: np.ndarray, T: float) -> np.ndarray:
    """Apply IAU 2006/2000A precession from J2000.0 to date (T centuries since J2000)"""
    # IAU 2006 precession angles (arcseconds, converted to radians)
    zeta_A  = np.radians((2306.2181*T + 0.30188*T**2 + 0.017998*T**3) / 3600.0)
    z_A     = np.radians((2306.2181*T + 1.09468*T**2 + 0.018203*T**3) / 3600.0)
    theta_A = np.radians((2004.3109*T - 0.42665*T**2 - 0.041833*T**3) / 3600.0)

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

        rotation_matrix = np.array([
            [1.0, 0.0, 0.0],
            [0.0, cos_obliq, sin_obliq],
            [0.0, -sin_obliq, cos_obliq]
        ])

        # Transform to ecliptic of date
        v_ecl_date = rotation_matrix @ v_eq_date

        # Convert to spherical coordinates
        lon_rad = np.arctan2(v_ecl_date[1], v_ecl_date[0])
        lat_rad = np.arcsin(v_ecl_date[2])

        return {
            "longitude": (np.degrees(lon_rad) + 360.0) % 360.0,
            "latitude": np.degrees(lat_rad),
            "distance": r_km / 149597870.7
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


# Houses calculation helpers
def _wrap(deg: float) -> float:
    x = deg % 360.0
    return x + 360.0 if x < 0 else x

def _atan2d(y: float, x: float) -> float:
    return _wrap(math.degrees(math.atan2(y, x)))

def _obliquity_deg(jd_tt_like: float) -> float:
    # Extract obliquity calculation from existing convert_to_ecliptic_of_date_spice function
    T = (jd_tt_like - 2451545.0) / 36525.0
    # IAU 1980 mean obliquity of the ecliptic formula
    obliq_deg = 23.43929111 - (46.8150 * T + 0.00059 * T**2 - 0.001813 * T**3) / 3600.0
    return obliq_deg

def _jd_from_iso_utc(iso_z: str) -> float:
    # fast, no external deps
    dt = datetime.fromisoformat(iso_z.replace("Z", "+00:00"))
    return dt.timestamp() / 86400.0 + 2440587.5  # Unix epoch to JD (UTC)

def _gmst_deg(jd_ut: float) -> float:
    # IAU 2006-ish simplified; fine for house geometry
    T = (jd_ut - 2451545.0) / 36525.0
    gmst = 280.46061837 + 360.98564736629 * (jd_ut - 2451545.0) + 0.000387933*T*T - (T*T*T)/38710000.0
    return _wrap(gmst)

def _asc_mc_tropical_and_sidereal(iso_z: str, lat_deg: float, lon_deg: float, ay_name: str, mc_hemisphere: McHemisphere = "south") -> dict[str, float]:
    jd = _jd_from_iso_utc(iso_z)
    eps = math.radians(_obliquity_deg(jd))
    ay = calculate_ayanamsa(ay_name, spice.str2et(iso_z))  # reuse your helper to stay identical to service
    gmst = _gmst_deg(jd)
    lst = math.radians(_wrap(gmst + lon_deg))
    phi = math.radians(lat_deg)

    # Local triad in equatorial frame
    z_hat = (math.cos(phi)*math.cos(lst), math.cos(phi)*math.sin(lst), math.sin(phi))
    e_hat = (-math.sin(lst), math.cos(lst), 0.0)
    n_hat = (-math.sin(phi)*math.cos(lst), -math.sin(phi)*math.sin(lst), math.cos(phi))
    s_hat = (-n_hat[0], -n_hat[1], -n_hat[2])

    # Ecliptic plane normal in equatorial coords
    n_ecl = (0.0, -math.sin(eps), math.cos(eps))

    def cross(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    def dot(a,b):   return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
    def norm(a):    return math.sqrt(dot(a,a))
    def unit(a):
        s = norm(a)
        return (a[0]/s,a[1]/s,a[2]/s)
    def rotx(v, ang):
        c,s = math.cos(ang), math.sin(ang)
        x,y,z = v
        return (x, c*y - s*z, s*y + c*z)

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
        pick_south = (lat_deg >= 0.0)
        ref = s_hat if pick_south else n_hat
        if dot(ref, d_mc) < 0:
            d_mc = (-d_mc[0], -d_mc[1], -d_mc[2])

    # Equatorial → Ecliptic-of-date (rotate by -ε about X)
    de_asc = rotx(d_asc, -eps)
    de_mc  = rotx(d_mc,  -eps)

    asc_trop = _atan2d(de_asc[1], de_asc[0])
    mc_trop  = _atan2d(de_mc[1],  de_mc[0])

    asc_sid = _wrap(asc_trop - ay)
    mc_sid  = _wrap(mc_trop  - ay)
    return {
        "asc_tropical": asc_trop, "mc_tropical": mc_trop,
        "asc": asc_sid, "mc": mc_sid,
        "ay": ay, "eps_deg": math.degrees(eps), "lst_deg": math.degrees(lst)
    }

def _placidus_cusps(iso_z: str, lat_deg: float, lon_deg: float, ay_name: str, zodiac: Zodiac, mc_hemisphere: McHemisphere = "south") -> list[float]:
    """
    Placidus: divide diurnal semi-arc around MC to get 11/12,
              divide nocturnal semi-arc using RAMC-30/60 (+180°) to get 2/3.
    Then enforce oppositions: 5=11+180, 6=12+180, 8=2+180, 9=3+180.
    """
    jd = _jd_from_iso_utc(iso_z)
    eps = math.radians(_obliquity_deg(jd))
    ay  = calculate_ayanamsa(ay_name, spice.str2et(iso_z))
    gmst = _gmst_deg(jd)
    RAMC = math.radians(_wrap(gmst + lon_deg))  # RA of MC
    phi  = math.radians(lat_deg)
    cphi = math.cos(phi)
    if abs(cphi) < 1e-2:
        raise HTTPException(status_code=422, detail="Placidus undefined near poles (|latitude| too high)")

    def ra_from_hour(h: float) -> float:
        # α = atan2( sin h, cos h * cos φ )  (correct quadrant)
        return math.atan2(math.sin(h), math.cos(h) * cphi)

    def ecl_lambda_from_ra(alpha: float) -> float:
        # β=0 inversion: λ = atan2( sin α / cos ε, cos α )
        return _atan2d(math.sin(alpha)/math.cos(eps), math.cos(alpha))

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
    asc_mc = _asc_mc_tropical_and_sidereal(iso_z, lat_deg, lon_deg, ay_name, mc_hemisphere)
    l01_t = asc_mc["asc_tropical"]

    # Opposites (tropical)
    l04_t = _wrap(l10_t + 180.0)
    l07_t = _wrap(l01_t + 180.0)

    # All tropical cusps first
    trop_cusps = [l01_t, l02_t, l03_t, l04_t, 0, 0, l07_t, 0, 0, l10_t, l11_t, l12_t]

    # Enforce strict Placidus oppositions (tropical)
    trop_cusps[4] = _wrap(trop_cusps[10] + 180.0)  # l05 = l11 + 180
    trop_cusps[5] = _wrap(trop_cusps[11] + 180.0)  # l06 = l12 + 180
    trop_cusps[7] = _wrap(trop_cusps[1] + 180.0)   # l08 = l02 + 180
    trop_cusps[8] = _wrap(trop_cusps[2] + 180.0)   # l09 = l03 + 180

    # Apply zodiac conversion
    return _finalize_cusps(trop_cusps, ay, zodiac)

def _whole_sign_cusps(asc_tropical: float, ay: float, zodiac: Zodiac) -> list[float]:
    """Whole Sign houses: 30° boundaries starting from Asc sign"""
    if zodiac == "sidereal":
        asc_final = _wrap(asc_tropical - ay)
    else:
        asc_final = asc_tropical
    base = math.floor(asc_final/30.0)*30.0
    return [_wrap(base + 30.0*i) for i in range(12)]

def _equal_cusps(asc_tropical: float, ay: float, zodiac: Zodiac) -> list[float]:
    """Equal houses: 30° intervals starting from Asc"""
    if zodiac == "sidereal":
        asc_final = _wrap(asc_tropical - ay)
    else:
        asc_final = asc_tropical
    return [_wrap(asc_final + 30.0*i) for i in range(12)]

def _finalize_cusps(trop_list: list[float], ay: float, zodiac: Zodiac) -> list[float]:
    """Finalize cusps based on zodiac - subtract ayanamsa for sidereal, keep tropical as-is"""
    if zodiac == "sidereal":
        return [_wrap(x - ay) for x in trop_list]
    else:
        return [_wrap(x) for x in trop_list]


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Comprehensive health check with operational status"""
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "uptime_seconds": time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0,
        "checks": {}
    }

    # SPICE system check
    try:
        et = spice.str2et("2024-01-01T00:00:00")
        spice.pxform("ITRF93", "J2000", et)
        _, radii = spice.bodvrd("EARTH", "RADII", 3)

        health_data["checks"]["spice"] = {
            "status": "healthy",
            "kernels_loaded": int(spice.ktotal('ALL')),
            "spice_version": spice.tkvrsn('TOOLKIT'),
            "earth_radii_km": [round(r, 3) for r in radii]
        }
    except Exception as e:
        health_data["checks"]["spice"] = {
            "status": "error",
            "error": str(e)
        }
        health_data["status"] = "degraded"

    # Time resolver check
    try:
        from time_resolver_v2 import get_tzdb_version
        tzdb_version = get_tzdb_version()
        health_data["checks"]["time_resolver"] = {
            "status": "healthy",
            "tzdb_version": tzdb_version
        }
    except Exception as e:
        health_data["checks"]["time_resolver"] = {
            "status": "error",
            "error": str(e)
        }
        health_data["status"] = "degraded"

    # Performance metrics
    try:
        latency_stats = metrics.get_latency_percentiles()
        error_stats = metrics.get_error_rate()

        health_data["checks"]["performance"] = {
            "status": "healthy" if error_stats["error_rate"] < 0.05 else "warning",
            "latency_p50_ms": latency_stats["p50"],
            "latency_p95_ms": latency_stats["p95"],
            "error_rate": error_stats["error_rate"],
            "total_requests": latency_stats["count"]
        }
    except Exception as e:
        health_data["checks"]["performance"] = {
            "status": "error",
            "error": str(e)
        }

    # System resources (basic check)
    try:
        import os

        import psutil

        # Memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        health_data["checks"]["system"] = {
            "status": "healthy",
            "memory_usage_mb": round(memory_info.rss / 1024 / 1024, 2),
            "cpu_percent": process.cpu_percent(),
            "open_files": len(process.open_files())
        }
    except ImportError:
        # psutil not available - basic fallback
        health_data["checks"]["system"] = {
            "status": "info",
            "message": "System monitoring unavailable (psutil not installed)"
        }
    except Exception as e:
        health_data["checks"]["system"] = {
            "status": "error",
            "error": str(e)
        }

    # Security metrics
    try:
        sec_metrics = security_metrics.get_metrics()
        health_data["checks"]["security"] = {
            "status": "healthy" if sec_metrics["blocked_requests"] < 100 else "warning",
            "blocked_requests": sec_metrics["blocked_requests"],
            "rate_limited_requests": sec_metrics["rate_limited_requests"],
            "suspicious_requests": sec_metrics["suspicious_requests"],
            "security_headers_enabled": os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() == "true",
            "trusted_hosts_configured": len([h.strip() for h in os.getenv("TRUSTED_HOSTS", "").split(",")]) if os.getenv("TRUSTED_HOSTS") else 0
        }
    except Exception as e:
        health_data["checks"]["security"] = {
            "status": "error",
            "error": str(e)
        }

    # Service configuration
    health_data["service"] = {
        "version": SERVICE_VERSION,
        "environment": os.getenv("ENV", "unknown"),
        "debug_enabled": os.getenv("DEBUG", "0") == "1",
        "rate_limiting_enabled": os.getenv("DISABLE_RATE_LIMIT", "0") == "0",
        "cors_origins": len(os.getenv("ALLOWED_ORIGINS", "").split(",")) if os.getenv("ALLOWED_ORIGINS") else 0,
        "security_hardening_enabled": True
    }

    # Overall status determination
    check_statuses = [check.get("status", "unknown") for check in health_data["checks"].values()]
    if "error" in check_statuses:
        health_data["status"] = "unhealthy"
    elif "warning" in check_statuses or "degraded" in check_statuses:
        health_data["status"] = "degraded"

    return health_data

@app.get("/version")
async def get_version() -> dict[str, Any]:
    """API version and kernel information endpoint"""
    try:
        return {
            "service_version": "1.0.0",
            "spice_version": spice.tkvrsn('TOOLKIT'),
            "kernel_set": {
                "tag": "2024-Q3",
                "count": int(spice.ktotal('ALL')),
                "de_ephemeris": "DE440",
                "earth_orientation": "earth_latest_high_prec",
                "planetary_constants": "pck00011",
                "leap_seconds": "naif0012"
            },
            "coordinate_frames": {
                "reference": "J2000",
                "observer": "ITRF93",
                "ecliptic": "ECLIPDATE",
                "aberration_correction": "LT+S"
            },
            "ayanamsa_systems": ["lahiri", "fagan_bradley"],
            "precision": {
                "longitude_digits": 6,
                "latitude_digits": 6,
                "distance_digits": 8
            }
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
                "spkinsuffdata": error_stats["spkinsuffdata_errors"] > 0,  # Alert on any SPICE data errors
                "high_error_rate": error_stats["error_rate"] > 0.1  # Alert if error rate > 10%
            }
        }
    except Exception as e:
        return {"error": str(e), "timestamp": time.time()}

# Only register /debug when DEBUG=1 (safest)
if os.getenv("DEBUG", "0") == "1":
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
            "data": {
                "kernels": kernels,
                "kernel_count": len(kernels)
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
                "timestamp": time.time()
            }
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
                "timestamp": time.time()
            },
            "error": str(e)
        }

@app.post("/houses", response_model=HousesResponse)
async def houses(req: HousesRequest):
    """Calculate house cusps using Placidus, Whole Sign, or Equal house systems"""
    # normalize to UTC
    if req.birth_time.tzinfo is None or req.birth_time.tzinfo.utcoffset(req.birth_time) is None:
        raise HTTPException(status_code=422, detail="birth_time must include timezone")
    iso_z = req.birth_time.astimezone(UTC).isoformat().replace("+00:00","Z")

    # Get tropical and sidereal ASC/MC
    asc_mc = _asc_mc_tropical_and_sidereal(iso_z, req.latitude, req.longitude, req.ayanamsa, req.mc_hemisphere)
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
            raise HTTPException(status_code=422, detail="Placidus undefined above polar circles (|lat| > ~66.5°)")
        cusps = _placidus_cusps(iso_z, req.latitude, req.longitude, req.ayanamsa, req.zodiac, req.mc_hemisphere)

    return HousesResponse(
        system=req.system,
        frame=ECL_FRAME,
        coordinate_system=COORD_SYSTEM,
        ecliptic_model=OBLIQUITY_MODEL,
        zodiac=req.zodiac,
        ayanamsa=req.ayanamsa if req.zodiac == "sidereal" else None,
        ayanamsa_deg=round(ayanamsa_deg, 6) if ayanamsa_deg is not None else None,
        asc=round(asc, 6), mc=round(mc, 6), cusps=[round(c, 6) for c in cusps]
    )


@app.post("/v1/time/resolve", response_model=TimeResolveResponseModel)
@limiter.limit("10/minute")
async def resolve_time(request: Request, time_request: TimeResolveRequest) -> TimeResolveResponseModel:
    """Resolve historical timezone for local datetime

    Convert local datetime + coordinates to UTC with historical timezone rules.
    Supports multiple parity profiles for compatibility with different astrological software.
    """
    try:
        # Convert Pydantic model to dictionary for V2 resolver
        payload = {
            "local_datetime": time_request.local_datetime,
            "latitude": time_request.latitude,
            "longitude": time_request.longitude,
            "parity_profile": time_request.parity_profile.value,
            "user_provided_zone": time_request.user_provided_zone,
            "user_provided_offset": time_request.user_provided_offset
        }

        # Resolve the time using V2 resolver
        result = resolve_time_v2(payload)

        # Convert back to Pydantic model
        return TimeResolveResponseModel(
            utc=result["utc"],
            zone_id=result["zone_id"],
            offset_seconds=result["offset_seconds"],
            dst_active=result["dst_active"],
            confidence=ConfidenceLevel(result["confidence"]),
            reason=result["reason"],
            notes=result["notes"],
            provenance=TimeProvenance(
                tzdb_version=result["provenance"]["tzdb_version"],
                sources=result["provenance"]["sources"],
                resolution_mode=result["provenance"]["resolution_mode"],
                patches_applied=result["provenance"]["patches_applied"]
            ),
            warnings=result["warnings"]
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Time resolution failed: {str(e)}")


if __name__ == "__main__":
    import os

    import uvicorn
    if os.getenv("ENV", "dev") == "dev":
        uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104

