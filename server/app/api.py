# server/app/api.py
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from typing import List
import asyncio
import logging
import time

from .schemas import (
    PositionsRequest, PositionsResponse, TimeResolveRequest, TimeResolveResponse,
    GeocodeResponse, GeocodeResult, ErrorOut
)
from .errors import bad_request, handle_ayanamsha_error, ErrorHandler
from .caching import InprocCache, CacheKey, cached_positions_response, get_cached_response_with_etag
from .ephemeris.ayanamsha import resolve_ayanamsha, validate_ayanamsha_for_system
from .time_resolver.client import resolve_time
from .geocode.client import geocode_search
from .config import AppConfig
from .obs.logging import StructuredLogger, TimedOperation, set_request_context
from .obs.metrics import metrics
from .obs.tracing import trace_positions, trace_time_resolve, trace_geocode, add_trace_attribute

# Structured logger for business operations
business_logger = StructuredLogger(__name__)
logger = logging.getLogger(__name__)

router = APIRouter()

# Global variables - will be injected in main.py
CACHE: InprocCache = None
POOL = None
CONFIG: AppConfig = None


@router.post(
    "/v1/positions",
    response_model=PositionsResponse,
    responses={
        400: {"model": ErrorOut},
        429: {"model": ErrorOut},
        500: {"model": ErrorOut}
    }
)
async def positions(req: PositionsRequest, request: Request):
    """
    Compute planetary positions for specified bodies and time.
    """
    # Set request context
    request_id = set_request_context()
    start_time = time.perf_counter()
    cache_hit = False
    ephemeris_used = "unknown"

    try:
        # Validate ayanāṃśa for system
        ayanamsha_id = req.ayanamsha.id if req.ayanamsha else None
        validate_ayanamsha_for_system(req.system, ayanamsha_id)

        # Derive UTC time
        if req.when.utc:
            utc = req.when.utc
        else:
            # Validate place information for local time
            if not req.when.place or (
                not req.when.place.name and
                (req.when.place.lat is None or req.when.place.lon is None)
            ):
                bad_request(
                    "INPUT.INVALID",
                    "Place required when using local time",
                    "Provide place.name or place.lat/lon for local datetime conversion.",
                    "Include complete place information or use UTC time directly."
                )

            # Resolve local time to UTC
            place_data = req.when.place.dict(exclude_none=True)
            utc = await resolve_time(
                local_datetime=req.when.local_datetime,
                place=place_data,
                config=CONFIG.time,
                parity_profile=req.parity_profile
            )

        # Resolve ayanāṃśa configuration
        ayanamsha_config = None
        if req.system == "sidereal":
            ayanamsha_config = resolve_ayanamsha(ayanamsha_id)

        # Extract frame and epoch
        frame_type = req.frame.type if req.frame else "ecliptic_of_date"
        epoch = req.epoch or "of_date"

        # Generate cache key and check cache
        cache_key = CacheKey.for_positions(
            utc=utc,
            system=req.system,
            ayanamsha=ayanamsha_config,
            frame=frame_type,
            epoch=epoch,
            bodies=req.bodies
        )

        cached_response = get_cached_response_with_etag(CACHE, cache_key)
        if cached_response:
            cache_hit = True
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Record metrics and logs for cache hit
            metrics.record_position_calculation(
                system=req.system,
                ephemeris="cached",
                body_count=len(req.bodies),
                duration_seconds=duration_ms / 1000,
                cache_hit=True
            )

            business_logger.positions_calculated(
                system=req.system,
                bodies=req.bodies,
                duration_ms=duration_ms,
                ephemeris="cached",
                ayanamsha=ayanamsha_id,
                cache_hit=True
            )

            logger.debug(f"Cache hit for positions request")
            return JSONResponse(
                cached_response,
                headers={
                    "ETag": cached_response.get("etag", ""),
                    "Cache-Control": "public, max-age=300",
                    "X-Request-ID": request_id
                }
            )

        # Compute via worker pool
        try:
            calculation_args = {
                "utc": utc,
                "system": req.system,
                "ayanamsha": ayanamsha_config,
                "frame": frame_type,
                "epoch": epoch,
                "bodies": req.bodies
            }

            logger.debug(f"Submitting calculation for {len(req.bodies)} bodies at {utc}")

            # Time the calculation with optional tracing
            calc_start = time.perf_counter()
            with trace_positions(req.system, req.bodies, "DE440", ayanamsha_id):
                add_trace_attribute("involution.utc", utc)
                add_trace_attribute("involution.frame", frame_type)
                add_trace_attribute("involution.epoch", epoch)

                calculation_result = POOL.calculate_sync(calculation_args, timeout=20.0)

            calc_duration = time.perf_counter() - calc_start
            ephemeris_used = calculation_result.get("ephemeris_used", "DE440")

            # Update trace with actual ephemeris
            add_trace_attribute("involution.ephemeris_actual", ephemeris_used)

            # Record worker pool metrics
            metrics.record_worker_task("completed", calc_duration)

        except Exception as e:
            logger.error(f"Calculation failed: {e}")
            ErrorHandler.handle_computation_error(e, "positions calculation")

        # Build response
        response_data = {
            "utc": utc,
            "provenance": {
                "tzdb_version": CONFIG.time.tzdb_version,
                "patch_version": "patches-e868200c",  # TODO: wire actual version
                "parity_profile": req.parity_profile or CONFIG.time.parity_profile_default,
                "kernels_bundle": CONFIG.kernels.bundle,
                "reference_frame": frame_type,
                "epoch": epoch,
                "ephemeris": calculation_result.get("ephemeris_used", "DE440")
            },
            "bodies": calculation_result["bodies"]
        }

        # Add ayanāṃśa info for sidereal calculations
        if req.system == "sidereal" and ayanamsha_config:
            response_data["provenance"]["ayanamsha"] = {
                "id": ayanamsha_config.get("id"),
                "value_deg": calculation_result.get("ayanamsha_value")
            }

        # Cache the response with ETag
        cached_response = cached_positions_response(response_data, CACHE, cache_key)

        # Record successful operation metrics and logs
        duration_ms = (time.perf_counter() - start_time) * 1000

        metrics.record_position_calculation(
            system=req.system,
            ephemeris=ephemeris_used,
            body_count=len(req.bodies),
            duration_seconds=duration_ms / 1000,
            cache_hit=False
        )

        business_logger.positions_calculated(
            system=req.system,
            bodies=req.bodies,
            duration_ms=duration_ms,
            ephemeris=ephemeris_used,
            ayanamsha=ayanamsha_id,
            cache_hit=False
        )

        return JSONResponse(
            cached_response,
            headers={
                "ETag": cached_response["etag"],
                "Cache-Control": "public, max-age=300",
                "X-Request-ID": request_id
            }
        )

    except Exception as e:
        # Record error metrics and logs
        duration_ms = (time.perf_counter() - start_time) * 1000

        if hasattr(e, 'status_code'):  # Already a properly formatted HTTPException
            # Extract error code from HTTPException detail if available
            error_code = getattr(e, 'detail', {}).get('code', 'UNKNOWN') if isinstance(getattr(e, 'detail', None), dict) else 'UNKNOWN'

            metrics.record_error(error_code)
            business_logger.positions_error(
                error_code=error_code,
                error_title=str(e.detail) if hasattr(e, 'detail') else str(e),
                system=req.system,
                bodies=req.bodies,
                duration_ms=duration_ms
            )
            raise e
        else:
            metrics.record_error("INTERNAL.UNEXPECTED")
            business_logger.positions_error(
                error_code="INTERNAL.UNEXPECTED",
                error_title="Unexpected error in positions endpoint",
                system=req.system,
                bodies=req.bodies,
                duration_ms=duration_ms,
                spice_error=str(e)
            )
            logger.error(f"Unexpected error in positions endpoint: {e}")
            ErrorHandler.handle_input_error(e)


@router.post(
    "/v1/time/resolve",
    response_model=TimeResolveResponse,
    responses={
        400: {"model": ErrorOut},
        429: {"model": ErrorOut},
        500: {"model": ErrorOut}
    }
)
async def time_resolve(req: TimeResolveRequest, request: Request):
    """
    Resolve local datetime to UTC using timezone rules.
    """
    # Set request context
    request_id = set_request_context()
    start_time = time.perf_counter()

    try:
        # Validate place information
        if not req.place.name and (req.place.lat is None or req.place.lon is None):
            bad_request(
                "INPUT.MISSING_REQUIRED",
                "Place information required",
                "Provide either place.name or place.lat/lon for timezone resolution.",
                "Include complete place information for accurate timezone resolution."
            )

        # Check cache first
        cache_key = CacheKey.for_time_resolution(
            local_datetime=req.local_datetime,
            place=req.place.dict(exclude_none=True),
            parity_profile=req.parity_profile
        )

        cached_response = CACHE.get(cache_key)
        if cached_response:
            duration_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_time_resolution(True, duration_ms / 1000)

            logger.debug("Cache hit for time resolution request")

            # Add request ID to cached response
            response = JSONResponse(
                cached_response,
                headers={"X-Request-ID": request_id}
            )
            return response

        # Resolve time with optional tracing
        place_data = req.place.dict(exclude_none=True)
        place_name = req.place.name or f"{req.place.lat},{req.place.lon}"

        with trace_time_resolve(req.local_datetime, place_name, CONFIG.time.tzdb_version):
            add_trace_attribute("involution.parity_profile", req.parity_profile or "default")
            utc = await resolve_time(
                local_datetime=req.local_datetime,
                place=place_data,
                config=CONFIG.time,
                parity_profile=req.parity_profile
            )
            add_trace_attribute("involution.utc_result", utc)

        response_data = {
            "utc": utc,
            "provenance": {
                "tzdb_version": CONFIG.time.tzdb_version,
                "patch_version": "patches-e868200c",
                "parity_profile": req.parity_profile
            }
        }

        # Cache the response
        CACHE.set(cache_key, response_data)

        # Record successful operation metrics and logs
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_time_resolution(True, duration_ms / 1000)

        business_logger.time_resolved(
            local_datetime=req.local_datetime,
            place_name=req.place.name or f"{req.place.lat},{req.place.lon}",
            utc_result=utc,
            duration_ms=duration_ms,
            tzdb_version=CONFIG.time.tzdb_version
        )

        return JSONResponse(
            response_data,
            headers={"X-Request-ID": request_id}
        )

    except Exception as e:
        # Record error metrics
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_time_resolution(False, duration_ms / 1000)

        if hasattr(e, 'status_code'):  # Already a properly formatted HTTPException
            error_code = getattr(e, 'detail', {}).get('code', 'UNKNOWN') if isinstance(getattr(e, 'detail', None), dict) else 'UNKNOWN'
            metrics.record_error(error_code)
            raise e
        else:
            metrics.record_error("INTERNAL.UNEXPECTED")
            logger.error(f"Unexpected error in time resolve endpoint: {e}")
            ErrorHandler.handle_input_error(e)


@router.get(
    "/v1/geocode/search",
    response_model=GeocodeResponse,
    responses={
        400: {"model": ErrorOut},
        429: {"model": ErrorOut},
        500: {"model": ErrorOut}
    }
)
async def geocode(
    request: Request,
    q: str = Query(..., description="Search query for location"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of results")
):
    """
    Search for geographic locations.
    """
    # Set request context
    request_id = set_request_context()
    start_time = time.perf_counter()

    try:
        # Check cache first
        cache_key = CacheKey.for_geocoding(query=q, limit=limit)
        cached_response = CACHE.get(cache_key)
        if cached_response:
            duration_ms = (time.perf_counter() - start_time) * 1000
            result_count = len(cached_response.get("results", []))

            metrics.record_geocode_search(
                "success" if result_count > 0 else "no_results",
                duration_ms / 1000
            )

            logger.debug("Cache hit for geocoding request")
            return JSONResponse(
                cached_response,
                headers={"X-Request-ID": request_id}
            )

        # Perform geocoding search with optional tracing
        with trace_geocode(q, 0):  # Will update result count after search
            results = await geocode_search(
                query=q,
                limit=limit,
                config=CONFIG.geocoding
            )
            add_trace_attribute("involution.result_count_actual", len(results))

        response_data = {"results": results}

        # Cache the response
        CACHE.set(cache_key, response_data)

        # Record successful operation metrics and logs
        duration_ms = (time.perf_counter() - start_time) * 1000
        result_count = len(results)

        metrics.record_geocode_search(
            "success" if result_count > 0 else "no_results",
            duration_ms / 1000
        )

        business_logger.geocode_searched(
            query=q,
            result_count=result_count,
            duration_ms=duration_ms
        )

        return JSONResponse(
            response_data,
            headers={"X-Request-ID": request_id}
        )

    except Exception as e:
        # Record error metrics
        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_geocode_search("failed", duration_ms / 1000)

        if hasattr(e, 'status_code'):  # Already a properly formatted HTTPException
            error_code = getattr(e, 'detail', {}).get('code', 'UNKNOWN') if isinstance(getattr(e, 'detail', None), dict) else 'UNKNOWN'
            metrics.record_error(error_code)
            raise e
        else:
            metrics.record_error("INTERNAL.UNEXPECTED")
            logger.error(f"Unexpected error in geocoding endpoint: {e}")
            ErrorHandler.handle_service_error(e, "geocoding")