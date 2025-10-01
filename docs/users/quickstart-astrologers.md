# Quick Start Guide for Astrologers

Welcome to the Involution Engine! This guide will help you quickly start using our astrological calculation engine to compute planetary positions with high precision.

## What This Engine Does

The Involution Engine is a professional-grade astrological calculation service that computes planetary positions using NASA's DE440/DE441 ephemeris data. It provides:

- **Planetary Positions**: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto
- **Lunar Nodes**: True Node and Mean Node calculations
- **Multiple Coordinate Systems**: Tropical and Sidereal with various ayanāṃśa options
- **Flexible Time Input**: Local time with automatic timezone resolution
- **High Precision**: Accuracy within 1 arcminute for most planets, 30 arcminutes for Moon
- **Professional Features**: Equatorial coordinates (RA/Dec), fixed stars (when enabled)

## Basic Usage

### 1. Simple Tropical Chart

Get planetary positions for a specific time in the tropical system:

```bash
curl -X POST https://your-engine.com/v1/positions \
  -H "Content-Type: application/json" \
  -d '{
    "when": {
      "utc": "2023-12-25T15:30:00Z"
    },
    "system": "tropical",
    "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
  }'
```

### 2. Using Local Date and Time

Calculate positions using local date/time with automatic timezone resolution:

```bash
curl -X POST https://your-engine.com/v1/positions \
  -H "Content-Type: application/json" \
  -d '{
    "when": {
      "local_datetime": "December 25, 2023 3:30 PM",
      "place": {
        "name": "New York, NY",
        "lat": 40.7128,
        "lon": -74.0060
      }
    },
    "system": "tropical",
    "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
  }'
```

### 3. Sidereal Calculations

Use sidereal system with Lahiri ayanāṃśa:

```bash
curl -X POST https://your-engine.com/v1/positions \
  -H "Content-Type: application/json" \
  -d '{
    "when": {
      "utc": "2023-12-25T15:30:00Z"
    },
    "system": "sidereal",
    "ayanamsha": {
      "id": "lahiri"
    },
    "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
  }'
```

## Supported Ayanāṃśas

| ID | Name | Type | Description |
|----|------|------|-------------|
| `lahiri` | Lahiri (Chitrapaksha) | Formula | Most widely used, official in India |
| `fagan_bradley_dynamic` | Fagan-Bradley (Dynamic) | Formula | Time-dependent calculation |
| `fagan_bradley_fixed` | Fagan-Bradley (Fixed) | Fixed | Fixed at 24.22° (Jan 1, 1950) |
| `krishnamurti` | Krishnamurti | Formula | KP system ayanāṃśa |
| `raman` | B.V. Raman | Formula | Popular in South Indian astrology |
| `yukteshwar` | Yukteshwar | Formula | Based on Sri Yukteshwar's calculations |

### Example with Different Ayanāṃśas

```bash
# Krishnamurti system
curl -X POST https://your-engine.com/v1/positions \
  -d '{
    "when": {"utc": "2023-12-25T15:30:00Z"},
    "system": "sidereal",
    "ayanamsha": {"id": "krishnamurti"},
    "bodies": ["Sun", "Moon"]
  }'
```

## Date and Time Formats

The engine accepts multiple date/time formats for convenience:

### UTC Formats
```json
{"utc": "2023-12-25T15:30:00Z"}
{"utc": "2023-12-25T15:30:00+00:00"}
{"utc": "2023-12-25T15:30:00 UTC"}
```

### Local DateTime Formats
```json
// ISO format
{"local_datetime": "2023-12-25T15:30:00"}

// US format
{"local_datetime": "12/25/2023 3:30 PM"}

// European format
{"local_datetime": "25 December 2023 15:30"}

// Natural language
{"local_datetime": "December 25, 2023 3:30 PM"}
{"local_datetime": "Dec 25, 2023 at 3:30 PM"}
```

### Place Information

When using local datetime, provide place coordinates:

```json
{
  "place": {
    "name": "Optional descriptive name",
    "lat": 40.7128,    // Latitude in decimal degrees
    "lon": -74.0060    // Longitude in decimal degrees
  }
}
```

## Understanding the Response

### Basic Response Structure

```json
{
  "utc": "2023-12-25T15:30:00Z",
  "bodies": [
    {
      "name": "Sun",
      "lon_deg": 274.123456,  // Ecliptic longitude in degrees
      "lat_deg": 0.000123     // Ecliptic latitude in degrees
    }
  ],
  "provenance": {
    "system": "tropical",
    "reference_frame": "ecliptic_of_date",
    "epoch": "of_date",
    "ephemeris": "de440",
    "ayanamsha": null
  }
}
```

### Coordinate Systems

The engine can provide positions in different coordinate systems:

1. **Ecliptic Coordinates** (default):
   - `lon_deg`: Longitude along the ecliptic (0-360°)
   - `lat_deg`: Latitude from the ecliptic (-90° to +90°)

2. **Equatorial Coordinates** (when requested):
   - `ra_hours`: Right Ascension in hours (0-24h)
   - `dec_deg`: Declination in degrees (-90° to +90°)

To request equatorial coordinates:

```json
{
  "when": {"utc": "2023-12-25T15:30:00Z"},
  "system": "tropical",
  "frame": {"type": "equatorial"},
  "epoch": "J2000",
  "bodies": ["Sun", "Moon"]
}
```

## Precision and Accuracy

### Accuracy Guarantees

| Body | Accuracy |
|------|----------|
| Sun, Mercury, Venus, Mars | ≤ 1 arcminute |
| Jupiter, Saturn, Uranus, Neptune, Pluto | ≤ 1 arcminute |
| Moon | ≤ 30 arcminutes |
| True Node, Mean Node | ≤ 5 arcminutes |

### Ephemeris Coverage

- **DE440**: 1550-2650 CE (high precision)
- **DE441**: Outside DE440 range (extended coverage)
- **Automatic switching**: Engine automatically selects appropriate ephemeris

### Time Accuracy

- Resolution: 1 second
- Timezone handling: Automatic using latest IANA timezone database
- Historical dates: Supported back to 1550 CE

## Common Use Cases

### 1. Birth Chart Calculation

```bash
curl -X POST https://your-engine.com/v1/positions \
  -H "Content-Type: application/json" \
  -d '{
    "when": {
      "local_datetime": "July 2, 1962 11:33 PM",
      "place": {
        "name": "Fort Knox, Kentucky",
        "lat": 37.840347,
        "lon": -85.949127
      }
    },
    "system": "tropical",
    "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "TrueNode"]
  }'
```

### 2. Current Planetary Positions

```bash
# Get current positions (use actual current time)
curl -X POST https://your-engine.com/v1/positions \
  -d '{
    "when": {"utc": "2024-01-15T12:00:00Z"},
    "system": "tropical",
    "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
  }'
```

### 3. Comparing Tropical vs Sidereal

```bash
# Tropical
curl -X POST https://your-engine.com/v1/positions \
  -d '{"when": {"utc": "2024-01-01T00:00:00Z"}, "system": "tropical", "bodies": ["Sun"]}'

# Sidereal (Lahiri)
curl -X POST https://your-engine.com/v1/positions \
  -d '{"when": {"utc": "2024-01-01T00:00:00Z"}, "system": "sidereal", "ayanamsha": {"id": "lahiri"}, "bodies": ["Sun"]}'
```

## Error Handling

The engine provides helpful error messages:

### Common Errors

1. **Invalid Date Format**:
   ```json
   {
     "code": "INPUT.INVALID",
     "title": "Invalid local datetime format",
     "detail": "Unable to parse datetime: 'invalid date'",
     "tip": "Use formats like '2023-12-25T15:30:00' or 'Dec 25, 2023 3:30 PM'"
   }
   ```

2. **Missing Ayanāṃśa for Sidereal**:
   ```json
   {
     "code": "AYANAMSHA.REQUIRED",
     "title": "Ayanāṃśa required for sidereal system",
     "detail": "Sidereal calculations require an ayanāṃśa specification",
     "tip": "Add 'ayanamsha': {'id': 'lahiri'} to your request"
   }
   ```

3. **Unsupported Ayanāṃśa**:
   ```json
   {
     "code": "AYANAMSHA.UNSUPPORTED",
     "title": "Unsupported ayanāṃśa",
     "detail": "Ayanāṃśa 'unknown' is not supported",
     "tip": "Use: lahiri, fagan_bradley_dynamic, fagan_bradley_fixed, krishnamurti, raman, yukteshwar"
   }
   ```

## Rate Limits

- **Default**: 200 requests per minute per IP address
- **Headers**: Check `X-RateLimit-Limit` and `X-RateLimit-Remaining` response headers
- **429 Error**: If rate limit exceeded, wait time specified in `Retry-After` header

## Next Steps

1. **Migration Guide**: If migrating from Swiss Ephemeris, see [Migrating from Swiss Ephemeris](migrating-from-swiss.md)
2. **Accuracy Details**: Learn more in [Accuracy Guarantees](accuracy-guarantees.md)
3. **Advanced Features**: Explore equatorial coordinates and fixed stars capabilities
4. **Integration**: Consider caching responses for repeated calculations

## Support

For technical questions or issues:
- Check the error message and tip for immediate guidance
- Review the accuracy guarantees for precision expectations
- Verify your date/time formats match the examples above

The Involution Engine is designed to provide reliable, accurate planetary positions for professional astrological work. Start with the basic examples above and gradually explore advanced features as needed.