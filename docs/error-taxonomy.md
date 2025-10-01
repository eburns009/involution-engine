# Error Taxonomy

This document defines the standardized error codes used by the Involution Engine API v1.1. Each error follows the pattern `CATEGORY.SPECIFIC_ERROR` and includes actionable guidance for resolution.

## Error Code Table

| Code | HTTP | Title | Detail (example) | Tip |
|------|------|-------|------------------|-----|
| `RANGE.EPHEMERIS_OUTSIDE` | 400 | Date outside ephemeris range | Supported range 1550–2650 (DE440). | Use a supported date or change kernels. |
| `TIME.RESOLUTION_FAILED` | 400 | Timezone couldn't be resolved | Historical rules unavailable for place/date. | Provide lat/lon or adjust parity profile. |
| `AYANAMSHA.UNSUPPORTED` | 400 | Unknown ayanāṃśa id | The ayanāṃśa registry does not include "foo_bar". | Use one of: LAHIRI, FAGAN_BRADLEY_DYNAMIC, RAMAN, KRISHNAMURTI. |
| `INPUT.INVALID` | 400 | Invalid input | "when" must include either "utc" or ("local_datetime" + "place"). | See OpenAPI schema for examples. |
| `INPUT.MISSING_REQUIRED` | 400 | Required field missing | Field "bodies" is required for position calculations. | Include all required fields per OpenAPI specification. |
| `INPUT.INVALID_FORMAT` | 400 | Invalid field format | "lat" must be a number between -90 and 90. | Check field types and ranges in API documentation. |
| `BODIES.UNSUPPORTED` | 400 | Unsupported celestial body | Body "Chiron" is not supported in current ephemeris. | Use supported bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, TrueNode, MeanNode. |
| `SYSTEM.INCOMPATIBLE` | 400 | Incompatible system configuration | Ayanāṃśa specified for tropical system. | Remove ayanāṃśa for tropical calculations or use sidereal system. |
| `GEOCODE.NOT_FOUND` | 400 | Location not found | No results found for search query. | Try a more specific or different location name. |
| `GEOCODE.AMBIGUOUS` | 400 | Location ambiguous | Multiple locations found; be more specific. | Include country, state, or other disambiguating information. |
| `RATE.LIMITED` | 429 | Too many requests | Per-IP rate limit exceeded. | Retry after header-specified time. |
| `RATE.QUOTA_EXCEEDED` | 429 | Daily quota exceeded | API usage quota exceeded for today. | Upgrade plan or retry tomorrow. |
| `KERNELS.NOT_AVAILABLE` | 500 | Ephemeris kernels not available | Kernels bundle not loaded or checksum mismatch. | Service warming; retry shortly. |
| `KERNELS.CORRUPTION` | 500 | Kernel data corruption detected | Integrity check failed for ephemeris data. | Report to support; service will attempt auto-recovery. |
| `COMPUTE.EPHEMERIS_ERROR` | 500 | Ephemeris computation failed | SPICE library returned error during calculation. | Retry request; report if persistent. |
| `COMPUTE.CONVERGENCE_FAILED` | 500 | Numerical convergence failed | Iterative calculation did not converge within limits. | Try nearby date/time or report if persistent. |
| `SERVICE.UNAVAILABLE` | 503 | Service temporarily unavailable | Service is starting up or under maintenance. | Retry after a few moments. |
| `SERVICE.OVERLOADED` | 503 | Service overloaded | Too many concurrent requests. | Retry with exponential backoff. |

## Error Categories

### INPUT
Client-side input validation errors. These indicate malformed requests, missing required fields, or invalid parameter values.

### RANGE
Errors related to data ranges and boundaries, particularly for dates outside supported ephemeris ranges.

### TIME
Time resolution and timezone-related errors, including historical timezone data availability.

### AYANAMSHA
Ayanāṃśa-related errors for sidereal calculations.

### BODIES
Celestial body specification errors.

### SYSTEM
System configuration and compatibility errors.

### GEOCODE
Geographic location search and resolution errors.

### RATE
Rate limiting and quota management errors.

### KERNELS
SPICE kernel loading and availability errors.

### COMPUTE
Computational errors during ephemeris calculations.

### SERVICE
Service-level availability and capacity errors.

## CSPICE Error Mapping

The following table maps common CSPICE (NASA's SPICE library) errors to our standardized taxonomy:

| CSPICE Error Pattern | Mapped Code | Notes |
|---------------------|-------------|-------|
| `SPICE(SPKINSUFFDATA)` | `RANGE.EPHEMERIS_OUTSIDE` | Date outside loaded ephemeris range |
| `SPICE(KERNELNOTFOUND)` | `KERNELS.NOT_AVAILABLE` | Required kernel file not found |
| `SPICE(BADTIMESTRING)` | `INPUT.INVALID_FORMAT` | Invalid time format passed to SPICE |
| `SPICE(NOLEAPSECONDS)` | `KERNELS.NOT_AVAILABLE` | Leap seconds kernel not loaded |
| `SPICE(NOSUCHFILE)` | `KERNELS.NOT_AVAILABLE` | Kernel file missing or inaccessible |
| `SPICE(INVALIDTARGET)` | `BODIES.UNSUPPORTED` | Invalid or unsupported body ID |
| `SPICE(NOTSUPPORTED)` | `COMPUTE.EPHEMERIS_ERROR` | Unsupported operation in SPICE |
| `SPICE(DIVIDEBYZERO)` | `COMPUTE.CONVERGENCE_FAILED` | Numerical instability in calculation |

## Error Response Format

All errors follow this JSON structure:

```json
{
  "code": "CATEGORY.SPECIFIC_ERROR",
  "title": "Human-readable title",
  "detail": "Specific details about this instance",
  "tip": "Actionable guidance for resolution"
}
```

## Adding New Error Codes

When adding new error codes:

1. Follow the `CATEGORY.SPECIFIC_ERROR` pattern
2. Use existing categories when possible
3. Provide clear, actionable tips
4. Include mapping for any underlying library errors
5. Update this documentation
6. Add examples to the OpenAPI specification

## HTTP Status Code Guidelines

- **400 Bad Request**: Client errors (INPUT, RANGE, TIME, AYANAMSHA, BODIES, SYSTEM, GEOCODE categories)
- **429 Too Many Requests**: Rate limiting (RATE category)
- **500 Internal Server Error**: Server-side computation errors (COMPUTE, KERNELS categories)
- **503 Service Unavailable**: Service capacity/availability issues (SERVICE category)