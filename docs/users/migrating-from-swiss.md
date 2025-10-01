# Migrating from Swiss Ephemeris

This guide helps you migrate from Swiss Ephemeris to the Involution Engine, mapping concepts and providing equivalent API calls.

## Overview

The Involution Engine is designed to be familiar to Swiss Ephemeris users while providing a modern REST API interface. Most Swiss Ephemeris functions have direct equivalents in our API.

## Key Differences

| Aspect | Swiss Ephemeris | Involution Engine |
|--------|-----------------|-------------------|
| Interface | C library / command line | REST API (JSON) |
| Time Input | Julian Date numbers | ISO datetime strings |
| Coordinates | Function parameters | JSON request body |
| Error Handling | Return codes | HTTP status + structured errors |
| Precision | ~0.001" (sub-arcsecond) | 1-30" (production optimized) |
| Ephemeris Files | Manual management | Automatic DE440/DE441 switching |

## Ayanāṃśa Mapping

### Swiss Ephemeris Ayanāṃśa IDs → Involution Engine

| Swiss ID | Swiss Name | Involution ID | Involution Name |
|----------|------------|---------------|-----------------|
| `SE_SIDM_LAHIRI` (1) | Lahiri | `lahiri` | Lahiri (Chitrapaksha) |
| `SE_SIDM_FAGAN_BRADLEY` (0) | Fagan/Bradley | `fagan_bradley_dynamic` | Fagan-Bradley (Dynamic) |
| `SE_SIDM_KRISHNAMURTI` (5) | Krishnamurti | `krishnamurti` | Krishnamurti |
| `SE_SIDM_RAMAN` (3) | B.V. Raman | `raman` | B.V. Raman |
| `SE_SIDM_YUKTESHWAR` (7) | Yukteshwar | `yukteshwar` | Yukteshwar |
| - | - | `fagan_bradley_fixed` | Fagan-Bradley (Fixed at 24.22°) |

### Example Migration

**Swiss Ephemeris (C)**:
```c
swe_set_sid_mode(SE_SIDM_LAHIRI, 0, 0);
swe_calc(jd, SE_SUN, flags, xx, serr);
```

**Involution Engine (REST)**:
```bash
curl -X POST /v1/positions -d '{
  "when": {"utc": "2023-12-25T15:30:00Z"},
  "system": "sidereal",
  "ayanamsha": {"id": "lahiri"},
  "bodies": ["Sun"]
}'
```

## Planet/Body Mapping

### Swiss Ephemeris Constants → Involution Engine Names

| Swiss Constant | Swiss Name | Involution Name |
|----------------|------------|-----------------|
| `SE_SUN` (0) | Sun | `"Sun"` |
| `SE_MOON` (1) | Moon | `"Moon"` |
| `SE_MERCURY` (2) | Mercury | `"Mercury"` |
| `SE_VENUS` (3) | Venus | `"Venus"` |
| `SE_MARS` (4) | Mars | `"Mars"` |
| `SE_JUPITER` (5) | Jupiter | `"Jupiter"` |
| `SE_SATURN` (6) | Saturn | `"Saturn"` |
| `SE_URANUS` (7) | Uranus | `"Uranus"` |
| `SE_NEPTUNE` (8) | Neptune | `"Neptune"` |
| `SE_PLUTO` (9) | Pluto | `"Pluto"` |
| `SE_TRUE_NODE` (11) | True Node | `"TrueNode"` |
| `SE_MEAN_NODE` (10) | Mean Node | `"MeanNode"` |

## Common Migration Examples

### 1. Basic Planetary Positions

**Swiss Ephemeris**:
```c
double jd = 2460310.5;  // Dec 25, 2023, 12:00 UTC
double xx[6];
char serr[AS_MAXCH];

swe_calc(jd, SE_SUN, SEFLG_SWIEPH, xx, serr);
printf("Sun longitude: %.6f\n", xx[0]);
```

**Involution Engine**:
```bash
curl -X POST /v1/positions -d '{
  "when": {"utc": "2023-12-25T12:00:00Z"},
  "system": "tropical",
  "bodies": ["Sun"]
}'
```

Response:
```json
{
  "bodies": [
    {"name": "Sun", "lon_deg": 274.123456, "lat_deg": 0.000123}
  ]
}
```

### 2. Sidereal Calculations

**Swiss Ephemeris**:
```c
swe_set_sid_mode(SE_SIDM_LAHIRI, 0, 0);
swe_calc(jd, SE_SUN, SEFLG_SIDEREAL | SEFLG_SWIEPH, xx, serr);
```

**Involution Engine**:
```bash
curl -X POST /v1/positions -d '{
  "when": {"utc": "2023-12-25T12:00:00Z"},
  "system": "sidereal",
  "ayanamsha": {"id": "lahiri"},
  "bodies": ["Sun"]
}'
```

### 3. Multiple Bodies

**Swiss Ephemeris**:
```c
int planets[] = {SE_SUN, SE_MOON, SE_MERCURY, SE_VENUS, SE_MARS};
for (int i = 0; i < 5; i++) {
    swe_calc(jd, planets[i], SEFLG_SWIEPH, xx, serr);
    printf("%s: %.6f\n", planet_names[i], xx[0]);
}
```

**Involution Engine**:
```bash
curl -X POST /v1/positions -d '{
  "when": {"utc": "2023-12-25T12:00:00Z"},
  "system": "tropical",
  "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars"]
}'
```

### 4. True Node Calculation

**Swiss Ephemeris**:
```c
swe_calc(jd, SE_TRUE_NODE, SEFLG_SWIEPH, xx, serr);
```

**Involution Engine**:
```bash
curl -X POST /v1/positions -d '{
  "when": {"utc": "2023-12-25T12:00:00Z"},
  "system": "tropical",
  "bodies": ["TrueNode"]
}'
```

## Time Conversion

### Julian Date → ISO DateTime

Swiss Ephemeris uses Julian Dates, while Involution Engine uses ISO datetime strings.

**Swiss Ephemeris**:
```c
double jd = 2460310.5;  // Dec 25, 2023, 12:00 UTC
```

**Involution Engine**:
```json
{"utc": "2023-12-25T12:00:00Z"}
```

### Common Julian Date Conversions

| Julian Date | ISO DateTime | Description |
|-------------|--------------|-------------|
| 2451545.0 | 2000-01-01T12:00:00Z | J2000.0 epoch |
| 2460310.5 | 2023-12-25T12:00:00Z | Christmas 2023 |
| 2465443.5 | 2038-01-19T12:00:00Z | Unix epoch limit |

### Using a Conversion Function

If you have Julian Dates from Swiss Ephemeris:

```python
from datetime import datetime, timezone

def jd_to_iso(jd):
    """Convert Julian Date to ISO datetime string."""
    # Julian Date of Unix epoch (1970-01-01 00:00:00 UTC)
    unix_epoch_jd = 2440587.5

    # Convert to Unix timestamp
    unix_timestamp = (jd - unix_epoch_jd) * 86400

    # Create datetime object
    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)

    return dt.isoformat().replace('+00:00', 'Z')

# Example usage
jd = 2460310.5
iso_time = jd_to_iso(jd)  # "2023-12-25T12:00:00Z"
```

## Coordinate Systems and Flags

### Swiss Ephemeris Flags → Involution Engine

| Swiss Flag | Description | Involution Equivalent |
|------------|-------------|----------------------|
| `SEFLG_SWIEPH` | Use Swiss Ephemeris | Default (uses DE440/DE441) |
| `SEFLG_SIDEREAL` | Sidereal coordinates | `"system": "sidereal"` |
| `SEFLG_EQUATORIAL` | Equatorial coordinates | `"frame": {"type": "equatorial"}` |
| `SEFLG_J2000` | J2000.0 coordinates | `"epoch": "J2000"` |
| `SEFLG_TRUEPOS` | True positions | Default behavior |
| `SEFLG_NONUT` | No nutation | Not configurable |

### Coordinate Frame Examples

**Swiss Ephemeris - Equatorial J2000**:
```c
swe_calc(jd, SE_SUN, SEFLG_SWIEPH | SEFLG_EQUATORIAL | SEFLG_J2000, xx, serr);
```

**Involution Engine - Equatorial J2000**:
```bash
curl -X POST /v1/positions -d '{
  "when": {"utc": "2023-12-25T12:00:00Z"},
  "system": "tropical",
  "frame": {"type": "equatorial"},
  "epoch": "J2000",
  "bodies": ["Sun"]
}'
```

## Error Handling Comparison

### Swiss Ephemeris Error Codes

**Swiss Ephemeris**:
```c
int ret = swe_calc(jd, SE_SUN, flags, xx, serr);
if (ret < 0) {
    printf("Error: %s\n", serr);
}
```

**Involution Engine**:
```bash
# Error response (HTTP 400)
{
  "code": "INPUT.INVALID",
  "title": "Invalid datetime format",
  "detail": "Unable to parse datetime: 'invalid'",
  "tip": "Use ISO format like '2023-12-25T15:30:00Z'"
}
```

### Common Error Mappings

| Swiss Error | Involution Error Code | Description |
|-------------|----------------------|-------------|
| Date out of range | `EPHEMERIS.DATE_RANGE` | Date outside ephemeris coverage |
| Invalid planet | `INPUT.INVALID` | Unknown body name |
| Ephemeris file error | `EPHEMERIS.UNAVAILABLE` | Ephemeris data not available |

## Performance Considerations

### Swiss Ephemeris
- Fast: Direct memory access to ephemeris files
- Precision: Sub-arcsecond accuracy
- Setup: Manual ephemeris file management

### Involution Engine
- Network: HTTP request overhead (~10-50ms)
- Precision: Production-optimized (1-30 arcminutes)
- Caching: Automatic response caching
- Batching: Multiple bodies in single request

### Optimization Tips

1. **Batch Multiple Bodies**: Request all needed bodies in one call
   ```json
   {"bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]}
   ```

2. **Cache Responses**: Cache results for repeated calculations
   ```bash
   # Use ETag headers for cache validation
   curl -H "If-None-Match: \"abc123\"" /v1/positions
   ```

3. **Use UTC Times**: Avoid local time conversion overhead when possible

## Complete Migration Example

Here's a complete example showing Swiss Ephemeris code and its Involution Engine equivalent:

### Swiss Ephemeris Version

```c
#include "swephexp.h"

int main() {
    double jd = 2460310.5;  // Dec 25, 2023, 12:00 UTC
    double xx[6];
    char serr[AS_MAXCH];
    int planets[] = {SE_SUN, SE_MOON, SE_MARS, SE_JUPITER};

    // Set Lahiri ayanamsa for sidereal
    swe_set_sid_mode(SE_SIDM_LAHIRI, 0, 0);

    for (int i = 0; i < 4; i++) {
        int ret = swe_calc(jd, planets[i], SEFLG_SIDEREAL | SEFLG_SWIEPH, xx, serr);
        if (ret >= 0) {
            printf("Planet %d: Lon=%.6f, Lat=%.6f\n", planets[i], xx[0], xx[1]);
        } else {
            printf("Error: %s\n", serr);
        }
    }

    swe_close();
    return 0;
}
```

### Involution Engine Version

```bash
curl -X POST https://your-engine.com/v1/positions \
  -H "Content-Type: application/json" \
  -d '{
    "when": {
      "utc": "2023-12-25T12:00:00Z"
    },
    "system": "sidereal",
    "ayanamsha": {
      "id": "lahiri"
    },
    "bodies": ["Sun", "Moon", "Mars", "Jupiter"]
  }'
```

Response:
```json
{
  "utc": "2023-12-25T12:00:00Z",
  "bodies": [
    {"name": "Sun", "lon_deg": 250.123456, "lat_deg": 0.000123},
    {"name": "Moon", "lon_deg": 123.456789, "lat_deg": -2.345678},
    {"name": "Mars", "lon_deg": 89.012345, "lat_deg": 1.234567},
    {"name": "Jupiter", "lon_deg": 12.345678, "lat_deg": 0.123456}
  ],
  "provenance": {
    "system": "sidereal",
    "ayanamsha": {
      "id": "lahiri",
      "value_deg": 24.123456
    },
    "ephemeris": "de440"
  }
}
```

## Migration Checklist

- [ ] Map your Swiss Ephemeris ayanāṃśa IDs to Involution Engine names
- [ ] Convert Julian Dates to ISO datetime strings
- [ ] Replace planet constants with string names
- [ ] Update error handling for HTTP responses
- [ ] Consider batching multiple bodies in single requests
- [ ] Implement response caching if doing repeated calculations
- [ ] Test precision requirements against Involution Engine accuracy
- [ ] Update any hardcoded precision assumptions

## Need Help?

If you encounter specific migration challenges:

1. **Precision Issues**: Check our [Accuracy Guarantees](accuracy-guarantees.md) documentation
2. **Missing Features**: Contact support - we may be able to add specific Swiss Ephemeris compatibility
3. **Performance Concerns**: Consider our caching strategies and batch request patterns

The Involution Engine provides the core functionality of Swiss Ephemeris in a modern, scalable API format. Most common astrological calculations translate directly with minimal changes to your application logic.