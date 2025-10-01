# Post-Deploy Smoke Tests

Quick validation commands for production deployment.

## Environment Setup

```bash
# Set your production SPICE service URL
export SPICE_URL="https://api.yourdomain.com/spice"
# or for local testing:
# export SPICE_URL="http://localhost:8000"
```

## Health Check

```bash
# Basic health validation
curl -s $SPICE_URL/health

# Expected response:
# {
#   "status": "ok",
#   "kernels": 4,
#   "spice_version": "N0067",
#   "earth_radii_km": [6378.137, 6378.137, 6356.752],
#   "coordinate_system": "ecliptic_of_date",
#   "aberration_correction": "LT+S"
# }
```

## Core Calculation Test

```bash
# Test planetary position calculation
curl -s -X POST $SPICE_URL/calculate \
  -H 'content-type: application/json' \
  -d '{
    "birth_time":"2024-06-21T18:00:00Z",
    "latitude":37.7749,
    "longitude":-122.4194,
    "elevation":50,
    "ayanamsa":"lahiri"
  }'

# Expected response format:
# {
#   "Sun": {
#     "longitude": 86.xxxx,
#     "latitude": 0.xxxx,
#     "distance": 1.xxxxxxxx
#   },
#   "Moon": {
#     "longitude": xxx.xxxx,
#     "latitude": x.xxxx,
#     "distance": 0.xxxxxxxx
#   },
#   ... (Mercury, Venus, Mars, Jupiter, Saturn)
# }
```

## Advanced Validation

```bash
# Test different ayanamsa
curl -s -X POST $SPICE_URL/calculate \
  -H 'content-type: application/json' \
  -d '{
    "birth_time":"2024-06-21T18:00:00Z",
    "latitude":37.7749,
    "longitude":-122.4194,
    "elevation":50,
    "ayanamsa":"fagan_bradley"
  }'

# Test error handling (invalid ayanamsa)
curl -s -X POST $SPICE_URL/calculate \
  -H 'content-type: application/json' \
  -d '{
    "birth_time":"2024-06-21T18:00:00Z",
    "latitude":37.7749,
    "longitude":-122.4194,
    "elevation":50,
    "ayanamsa":"invalid"
  }'

# Expected: HTTP 500 with error detail
```

## Performance Test

```bash
# Basic performance check (should complete in <2s)
time curl -s -X POST $SPICE_URL/calculate \
  -H 'content-type: application/json' \
  -d '{
    "birth_time":"2024-06-21T18:00:00Z",
    "latitude":37.7749,
    "longitude":-122.4194,
    "elevation":50,
    "ayanamsa":"lahiri"
  }' > /dev/null
```

## Security Validation

```bash
# CORS check (should reject from unauthorized origins)
curl -s -H "Origin: https://malicious.com" $SPICE_URL/health

# Rate limiting check (after multiple rapid requests)
for i in {1..15}; do
  curl -s $SPICE_URL/health > /dev/null
  echo "Request $i"
done
# Should eventually return 429 Too Many Requests
```

## Debug Information

```bash
# Get detailed service info
curl -s $SPICE_URL/debug

# Check service logs (if accessible)
# docker logs <container-name>
# kubectl logs deployment/spice-service
```

## Success Criteria

✅ **Health check returns status: "ok"**
✅ **Calculation completes in <2 seconds**
✅ **Returns 7 planetary positions (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn)**
✅ **Longitude values are 0-360 degrees**
✅ **Latitude values are ±90 degrees**
✅ **Distance values are positive**
✅ **Error handling works for invalid inputs**
✅ **CORS properly configured**
✅ **Rate limiting active (if enabled)**