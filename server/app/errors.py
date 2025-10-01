from fastapi import HTTPException
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def bad_request(code: str, title: str, detail: str = "", tip: str = ""):
    """
    Raise a 400 Bad Request exception with structured error response.

    Args:
        code: Error code following CATEGORY.SPECIFIC_ERROR pattern
        title: Human-readable error title
        detail: Specific details about this error instance
        tip: Actionable guidance for resolving the error
    """
    error_response = {
        "code": code,
        "title": title,
        "detail": detail,
        "tip": tip
    }
    logger.warning(f"Bad request: {code} - {title} - {detail}")
    raise HTTPException(status_code=400, detail=error_response)


def too_many_requests(code: str = "RATE.LIMITED", title: str = "Too many requests",
                     detail: str = "Per-IP rate limit exceeded.",
                     tip: str = "Retry after header-specified time."):
    """
    Raise a 429 Too Many Requests exception.

    Args:
        code: Error code
        title: Error title
        detail: Error details
        tip: Resolution tip
    """
    error_response = {
        "code": code,
        "title": title,
        "detail": detail,
        "tip": tip
    }
    logger.warning(f"Rate limit exceeded: {detail}")
    raise HTTPException(status_code=429, detail=error_response)


def server_error(code: str = "SERVER.ERROR", title: str = "Server error",
                detail: str = "", tip: str = ""):
    """
    Raise a 500 Internal Server Error exception.

    Args:
        code: Error code
        title: Error title
        detail: Error details
        tip: Resolution tip
    """
    error_response = {
        "code": code,
        "title": title,
        "detail": detail,
        "tip": tip
    }
    logger.error(f"Server error: {code} - {title} - {detail}")
    raise HTTPException(status_code=500, detail=error_response)


def service_unavailable(code: str = "SERVICE.UNAVAILABLE",
                       title: str = "Service temporarily unavailable",
                       detail: str = "Service is starting up or under maintenance.",
                       tip: str = "Retry after a few moments."):
    """
    Raise a 503 Service Unavailable exception.

    Args:
        code: Error code
        title: Error title
        detail: Error details
        tip: Resolution tip
    """
    error_response = {
        "code": code,
        "title": title,
        "detail": detail,
        "tip": tip
    }
    logger.warning(f"Service unavailable: {detail}")
    raise HTTPException(status_code=503, detail=error_response)


def map_spice_error(err: Exception, context: str = ""):
    """
    Map SPICE/computation errors to friendly error codes.

    Args:
        err: The original exception
        context: Additional context about where the error occurred
    """
    error_msg = str(err).upper()

    # Log the original error for debugging
    logger.error(f"SPICE error in {context}: {err}")

    if "SPKINSUFFDATA" in error_msg or "INSUFFICIENT DATA" in error_msg:
        bad_request(
            "RANGE.EPHEMERIS_OUTSIDE",
            "Date outside ephemeris range",
            "Supported range 1550–2650 (DE440).",
            "Use a supported date or change kernels."
        )

    elif "KERNELNOTFOUND" in error_msg or "NOSUCHFILE" in error_msg:
        server_error(
            "KERNELS.NOT_AVAILABLE",
            "Ephemeris kernels not available",
            "Kernels bundle not loaded or checksum mismatch.",
            "Service warming; retry shortly."
        )

    elif "NOLEAPSECONDS" in error_msg:
        server_error(
            "KERNELS.NOT_AVAILABLE",
            "Leap seconds kernel not available",
            "Required leap seconds kernel (LSK) not loaded.",
            "Check kernel bundle configuration."
        )

    elif "INVALIDTARGET" in error_msg:
        bad_request(
            "BODIES.UNSUPPORTED",
            "Invalid or unsupported body",
            f"The specified celestial body is not supported.",
            "Use supported bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, TrueNode, MeanNode."
        )

    elif "BADTIMESTRING" in error_msg or "TIME" in error_msg:
        bad_request(
            "INPUT.INVALID_FORMAT",
            "Invalid time format",
            "The provided time string could not be parsed.",
            "Use ISO format like '1962-07-03T04:33:00Z' or '1962-07-02T23:33:00'."
        )

    elif "DIVIDEBYZERO" in error_msg or "CONVERGENCE" in error_msg:
        server_error(
            "COMPUTE.CONVERGENCE_FAILED",
            "Numerical convergence failed",
            "Iterative calculation did not converge within limits.",
            "Try nearby date/time or report if persistent."
        )

    elif "NOTSUPPORTED" in error_msg:
        server_error(
            "COMPUTE.EPHEMERIS_ERROR",
            "Unsupported operation",
            "The requested calculation is not supported by current ephemeris.",
            "Check calculation parameters or use different ephemeris range."
        )

    else:
        # Generic computation error
        server_error(
            "COMPUTE.EPHEMERIS_ERROR",
            "Ephemeris computation failed",
            f"SPICE library returned error: {str(err)[:100]}",
            "Retry request; report if persistent."
        )


def map_validation_error(err: Exception):
    """
    Map Pydantic validation errors to friendly error codes.

    Args:
        err: Validation error from Pydantic
    """
    logger.warning(f"Validation error: {err}")

    error_detail = str(err)

    if "field required" in error_detail.lower():
        bad_request(
            "INPUT.MISSING_REQUIRED",
            "Required field missing",
            "One or more required fields are missing from the request.",
            "Include all required fields per OpenAPI specification."
        )

    elif "invalid" in error_detail.lower() or "not a valid" in error_detail.lower():
        bad_request(
            "INPUT.INVALID_FORMAT",
            "Invalid field format",
            f"Field validation failed: {error_detail[:100]}",
            "Check field types and ranges in API documentation."
        )

    else:
        bad_request(
            "INPUT.INVALID",
            "Invalid input",
            f"Request validation failed: {error_detail[:100]}",
            "See OpenAPI schema for examples."
        )


def map_http_client_error(err: Exception, service: str):
    """
    Map HTTP client errors to friendly error codes.

    Args:
        err: HTTP client exception
        service: Name of the service that failed
    """
    logger.error(f"HTTP client error for {service}: {err}")

    error_msg = str(err).lower()

    if "timeout" in error_msg or "timed out" in error_msg:
        server_error(
            "SERVICE.TIMEOUT",
            f"{service} service timeout",
            f"Request to {service} service timed out.",
            "Retry request; check service status if persistent."
        )

    elif "connection" in error_msg or "unreachable" in error_msg:
        server_error(
            "SERVICE.UNAVAILABLE",
            f"{service} service unavailable",
            f"Could not connect to {service} service.",
            "Check service status and retry."
        )

    elif "404" in error_msg or "not found" in error_msg:
        if service.lower() == "geocode":
            bad_request(
                "GEOCODE.NOT_FOUND",
                "Location not found",
                "No results found for search query.",
                "Try a more specific or different location name."
            )
        else:
            server_error(
                "SERVICE.ERROR",
                f"{service} service error",
                f"{service} service returned 404.",
                "Check service configuration."
            )

    else:
        server_error(
            "SERVICE.ERROR",
            f"{service} service error",
            f"Error communicating with {service}: {str(err)[:100]}",
            "Retry request; check service status if persistent."
        )


def handle_ayanamsha_error(err: Exception):
    """
    Handle ayanāṃśa-related errors.

    Args:
        err: Exception from ayanāṃśa processing
    """
    error_msg = str(err)

    if "AYANAMSHA.UNSUPPORTED" in error_msg:
        # Already formatted correctly, re-raise as bad request
        bad_request(
            "AYANAMSHA.UNSUPPORTED",
            "Unknown ayanāṃśa id",
            error_msg.split(": ", 1)[-1] if ": " in error_msg else error_msg,
            "Use one of: LAHIRI, FAGAN_BRADLEY_DYNAMIC, FAGAN_BRADLEY_FIXED."
        )

    elif "SYSTEM.INCOMPATIBLE" in error_msg:
        bad_request(
            "SYSTEM.INCOMPATIBLE",
            "Incompatible system configuration",
            error_msg.split(": ", 1)[-1] if ": " in error_msg else error_msg,
            "Remove ayanāṃśa for tropical calculations or use sidereal system."
        )

    elif "AYANAMSHA.REQUIRED" in error_msg:
        bad_request(
            "AYANAMSHA.REQUIRED",
            "Ayanāṃśa required for sidereal system",
            "Sidereal calculations require ayanāṃśa specification.",
            "Specify ayanāṃśa id in request or use tropical system."
        )

    else:
        bad_request(
            "INPUT.INVALID",
            "Ayanāṃśa configuration error",
            str(err),
            "Check ayanāṃśa configuration and supported values."
        )


def handle_time_resolution_error(err: Exception):
    """
    Handle time resolution errors.

    Args:
        err: Exception from time resolution service
    """
    error_msg = str(err).lower()

    if "timezone" in error_msg or "tz" in error_msg:
        bad_request(
            "TIME.RESOLUTION_FAILED",
            "Timezone couldn't be resolved",
            "Historical rules unavailable for place/date.",
            "Provide lat/lon or adjust parity profile."
        )

    elif "ambiguous" in error_msg:
        bad_request(
            "TIME.AMBIGUOUS",
            "Ambiguous local time",
            "Local time exists twice due to DST transition.",
            "Use UTC time or specify timezone offset."
        )

    elif "nonexistent" in error_msg:
        bad_request(
            "TIME.NONEXISTENT",
            "Nonexistent local time",
            "Local time skipped due to DST transition.",
            "Use UTC time or adjust local time."
        )

    else:
        map_http_client_error(err, "time resolver")


class ErrorHandler:
    """
    Centralized error handling for the application.
    """

    @staticmethod
    def handle_computation_error(err: Exception, context: str = ""):
        """Handle errors from ephemeris computation."""
        if "RANGE.EPHEMERIS_OUTSIDE" in str(err):
            raise err  # Already properly formatted
        elif "BODIES.UNSUPPORTED" in str(err):
            raise err  # Already properly formatted
        else:
            map_spice_error(err, context)

    @staticmethod
    def handle_service_error(err: Exception, service: str):
        """Handle errors from external services."""
        map_http_client_error(err, service)

    @staticmethod
    def handle_input_error(err: Exception):
        """Handle input validation errors."""
        if hasattr(err, 'errors'):  # Pydantic validation error
            map_validation_error(err)
        else:
            bad_request(
                "INPUT.INVALID",
                "Invalid input",
                str(err),
                "Check request format and required fields."
            )