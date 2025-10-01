# HTTP API Examples

This directory contains example HTTP requests and responses for the Involution Engine API v1.1.

## Fort Knox Test Case

The "Fort Knox" test case is our canonical reference for validation and documentation.

**Location**: Fort Knox, Kentucky, USA
**Coordinates**: 37.840347°N, 85.949127°W
**Date/Time**: July 3, 1962, 04:33:00 UTC
**Zodiac**: Tropical
**Ayanāṃśa**: Lahiri (for sidereal calculations)

### Making a Request

```bash
curl -s -X POST http://localhost:8000/v1/positions \
  -H 'Content-Type: application/json' \
  -d @fort-knox-request.json | jq .
```

### Files

- `fort-knox-request.json` - Example request payload
- `fort-knox-response.json` - Example response (illustrative values)

### Other Endpoints

#### Time Resolution

```bash
curl -s -X POST http://localhost:8000/v1/time/resolve \
  -H 'Content-Type: application/json' \
  -d '{
    "local_datetime": "1962-07-02T23:33:00",
    "place": {
      "lat": 37.840347,
      "lon": -85.949127
    },
    "parity_profile": "strict_history"
  }' | jq .
```

#### Geocoding

```bash
curl -s "http://localhost:8000/v1/geocode/search?q=Fort+Knox,+KY" | jq .
```

#### Health Check

```bash
curl -s http://localhost:8000/healthz | jq .
```

## API Documentation

For complete API documentation, see:
- [OpenAPI v1.1 Specification](../../docs/openapi/v1.1.yaml)
- [Error Taxonomy](../../docs/error-taxonomy.md)
