# API Reference

Complete documentation for all Involution Engine endpoints.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: Set via deployment configuration

## Authentication

No authentication required for current version. Rate limiting applies in production.

## Content Type

All requests and responses use `application/json`.

---

## Endpoints

### GET /health

Service health check and basic metadata.

**Response 200**
```json
{
  "status": "ok",
  "kernels": 5,
  "spice_version": "CSPICE_N0067",
  "coordinate_system": "ecliptic_of_date"
}
```

### GET /version

Service version information.

**Response 200**
```json
{
  "service_version": "2.0.0",
  "spice_version": "CSPICE_N0067"
}
```

### GET /info

Detailed runtime metadata including loaded kernels.

**Response 200**
```json
{
  "spice_version": "CSPICE_N0067",
  "frame": "ECLIPDATE",
  "ecliptic_model": "IAU1980-mean",
  "abcorr": "LT+S",
  "kernels": [
    "engine/kernels/lsk/naif0012.tls",
    "engine/kernels/pck/pck00011.tpc",
    "engine/kernels/pck/earth_latest_high_prec.bpc",
    "engine/kernels/spk/planets/de440.bsp"
  ],
  "ts": "2025-09-27T18:00:00Z"
}
```

### GET /metrics

Performance metrics and statistics.

**Response 200**
```json
{
  "requests_total": 1234,
  "requests_per_second": 15.6,
  "average_response_time_ms": 45.2,
  "kernel_load_time_ms": 120.5
}
```

---

## Calculation Endpoints

### POST /calculate

Calculate planetary positions for a given time and location.

**Request Body**
```json
{
  "birth_time": "1962-07-03T04:33:00Z",
  "latitude": 37.840347,
  "longitude": -85.949127,
  "elevation": 0.0,
  "zodiac": "tropical",
  "ayanamsa": "lahiri",
  "parity_profile": "strict_history"
}
```

**Request Fields**
- `birth_time` (string, required): ISO 8601 datetime with timezone
- `latitude` (number, required): Latitude in degrees (-90 to 90)
- `longitude` (number, required): Longitude in degrees (-180 to 180)
- `elevation` (number, optional): Elevation in meters (-500 to 10000), default: 0.0
- `zodiac` (string, optional): "tropical" or "sidereal", default: "sidereal"
- `ayanamsa` (string, optional): "lahiri" or "fagan_bradley", default: "lahiri"
- `parity_profile` (string, optional): Time resolution mode, default: "strict_history"

**Response 200**
```json
{
  "data": {
    "Sun": {
      "longitude": 66.3075,
      "latitude": -0.0040,
      "distance": 1.0160
    },
    "Moon": {
      "longitude": 242.2140,
      "latitude": -5.0400,
      "distance": 0.0026
    },
    "Mercury": {
      "longitude": 74.8124,
      "latitude": 1.7296,
      "distance": 1.2932
    },
    "Venus": {
      "longitude": 70.9775,
      "latitude": 0.6025,
      "distance": 1.7270
    },
    "Mars": {
      "longitude": 14.7190,
      "latitude": -1.0332,
      "distance": 1.7770
    },
    "Jupiter": {
      "longitude": 41.6442,
      "latitude": -0.7007,
      "distance": 5.9302
    },
    "Saturn": {
      "longitude": 324.8395,
      "latitude": -1.9440,
      "distance": 9.4347
    }
  },
  "meta": {
    "service_version": "2.0.0",
    "spice_version": "CSPICE_N0067",
    "kernel_set_tag": "2024-Q3",
    "ecliptic_frame": "ECLIPDATE",
    "zodiac": "tropical",
    "ayanamsa_deg": null,
    "observer_frame_used": "ITRF93",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": 1727460000.0,
    "parity_profile": "strict_history",
    "time_resolution": null,
    "chart_warnings": []
  }
}
```

### POST /calculate-with-time-resolution

Calculate planetary positions with advanced time resolution for historical dates.

**Request Body**
```json
{
  "local_datetime": "1962-07-02T23:33:00",
  "latitude": 37.840347,
  "longitude": -85.949127,
  "elevation": 0.0,
  "parity_profile": "strict_history",
  "user_provided_zone": null,
  "user_provided_offset": null,
  "zodiac": "tropical",
  "ayanamsa": "lahiri"
}
```

**Request Fields**
- `local_datetime` (string, required): Local datetime without timezone (ISO 8601)
- `latitude` (number, required): Latitude in degrees (-90 to 90)
- `longitude` (number, required): Longitude in degrees (-180 to 180)
- `elevation` (number, optional): Elevation in meters, default: 0.0
- `parity_profile` (string, required): Time resolution mode
- `user_provided_zone` (string, optional): User timezone (for as_entered mode)
- `user_provided_offset` (number, optional): UTC offset in seconds (for as_entered mode)
- `zodiac` (string, optional): "tropical" or "sidereal", default: "sidereal"
- `ayanamsa` (string, optional): "lahiri" or "fagan_bradley", default: "lahiri"

**Response 200**
Same format as `/calculate` but includes additional time resolution metadata in `meta.time_resolution`.

---

## Houses Endpoint

### POST /houses

Calculate house cusps for a given time and location.

**Request Body**
```json
{
  "birth_time": "1962-07-03T04:33:00Z",
  "latitude": 37.840347,
  "longitude": -85.949127,
  "elevation": 0.0,
  "house_system": "placidus",
  "zodiac": "tropical",
  "ayanamsa": "lahiri"
}
```

**Request Fields**
- `birth_time` (string, required): ISO 8601 datetime with timezone
- `latitude` (number, required): Latitude in degrees (-90 to 90)
- `longitude` (number, required): Longitude in degrees (-180 to 180)
- `elevation` (number, optional): Elevation in meters, default: 0.0
- `house_system` (string, required): House system ("placidus", "koch", "equal", etc.)
- `zodiac` (string, optional): "tropical" or "sidereal", default: "tropical"
- `ayanamsa` (string, optional): "lahiri" or "fagan_bradley", default: "lahiri"

**Response 200**
```json
{
  "cusps": [0.0, 45.2, 78.9, 112.3, 145.7, 179.1, 212.5, 245.9, 279.3, 312.7, 346.1, 19.5],
  "houses": {
    "1": 0.0,
    "2": 45.2,
    "3": 78.9,
    "4": 112.3,
    "5": 145.7,
    "6": 179.1,
    "7": 212.5,
    "8": 245.9,
    "9": 279.3,
    "10": 312.7,
    "11": 346.1,
    "12": 19.5
  },
  "angles": {
    "ascendant": 0.0,
    "midheaven": 312.7,
    "descendant": 180.0,
    "imum_coeli": 132.7
  },
  "meta": {
    "house_system": "placidus",
    "zodiac": "tropical",
    "ayanamsa_deg": null,
    "service_version": "2.0.0",
    "request_id": "550e8400-e29b-41d4-a716-446655440001"
  }
}
```

---

## Time Resolution Endpoint

### POST /v1/time/resolve

Resolve local datetime to UTC with timezone and historical accuracy information.

**Request Body**
```json
{
  "local_datetime": "1962-07-02T23:33:00",
  "place": {
    "lat": 37.840347,
    "lon": -85.949127
  },
  "parity_profile": "strict_history"
}
```

**Response 200**
```json
{
  "utc": "1962-07-03T04:33:00Z",
  "zone_id": "America/New_York",
  "offset_seconds": -18000,
  "confidence": 0.95,
  "warnings": [],
  "metadata": {
    "parity_profile": "strict_history",
    "historical_accuracy": true
  }
}
```

---

## Error Responses

### 400 Bad Request
Invalid input parameters.

```json
{
  "detail": "Validation error: latitude must be between -90 and 90"
}
```

### 422 Validation Error
Pydantic validation failed.

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "birth_time"],
      "msg": "Field required"
    }
  ]
}
```

### 500 Internal Server Error
SPICE calculation or internal error.

```json
{
  "detail": "SPICE calculation failed: SPICE(SPKINSUFFDATA) -- Insufficient ephemeris data has been loaded to compute the state of target body 4 (MARS BARYCENTER) relative to observer body 399 (EARTH) at the ephemeris epoch 1470-01-01T00:00:00.000."
}
```

### 429 Too Many Requests
Rate limit exceeded (production only).

```json
{
  "detail": "Rate limit exceeded"
}
```

---

## Rate Limiting

Production deployments include rate limiting:
- Default: 100 requests per minute per IP
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## CORS

Allowed origins configured via `ALLOWED_ORIGINS` environment variable. No wildcard origins in production.

---

## Data Formats

### Coordinates
- **Longitude**: Degrees, [0, 360) wrap-safe format
- **Latitude**: Degrees, [-90, 90]
- **Distance**: Astronomical Units (AU)
- **Elevation**: Meters above sea level

### Time
- **Input**: ISO 8601 with timezone (`2024-06-21T18:00:00Z` or `2024-06-21T12:00:00-06:00`)
- **Internal**: UTC timestamps
- **Precision**: Seconds

### Zodiac Systems
- **Tropical**: Standard Western astrology (vernal equinox = 0° Aries)
- **Sidereal**: Star-based zodiac with ayanamsa correction

### Ayanamsa Options
- **lahiri**: Chitrapaksha ayanamsa (default)
- **fagan_bradley**: Fagan-Bradley ayanamsa

---

## Example Usage

### cURL Examples

```bash
# Health check
curl -s http://localhost:8000/health | jq .

# Basic calculation
curl -s -X POST http://localhost:8000/calculate \
  -H 'Content-Type: application/json' \
  -d '{
    "birth_time": "1962-07-03T04:33:00Z",
    "latitude": 37.840347,
    "longitude": -85.949127,
    "zodiac": "tropical"
  }' | jq .

# Houses calculation
curl -s -X POST http://localhost:8000/houses \
  -H 'Content-Type: application/json' \
  -d '{
    "birth_time": "1962-07-03T04:33:00Z",
    "latitude": 37.840347,
    "longitude": -85.949127,
    "house_system": "placidus",
    "zodiac": "tropical"
  }' | jq .
```

### TypeScript Types

```typescript
export type Zodiac = 'tropical' | 'sidereal';
export type Ayanamsa = 'lahiri' | 'fagan_bradley';
export type HouseSystem = 'placidus' | 'koch' | 'equal' | 'campanus' | 'regiomontanus';

export interface ChartRequest {
  birth_time: string;
  latitude: number;
  longitude: number;
  elevation?: number;
  zodiac?: Zodiac;
  ayanamsa?: Ayanamsa;
  parity_profile?: 'strict_history' | 'astro_com' | 'clairvision' | 'as_entered';
}

export interface PlanetPosition {
  longitude: number;
  latitude: number;
  distance: number;
}

export interface CalculationResponse {
  data: Record<string, PlanetPosition>;
  meta: {
    service_version: string;
    spice_version: string;
    kernel_set_tag: string;
    ecliptic_frame: string;
    zodiac: Zodiac;
    ayanamsa_deg: number | null;
    observer_frame_used: string;
    request_id: string;
    timestamp: number;
    parity_profile: string;
    time_resolution?: any;
    chart_warnings: string[];
  };
}
```