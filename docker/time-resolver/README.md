# Time Resolver Service

A standalone Python microservice for historical timezone resolution with IANA tzdb and custom patches for pre-1967 US timezone accuracy.

## Features

- **Historical Accuracy**: IANA timezone database with custom patches for US pre-1967 Standard Time Act era
- **Multiple Parity Profiles**: Compatible with Astrodienst, Clairvision, and other astrological software
- **Slim Container**: Reproducible Docker image with bundled tzdata 2025.1
- **OpenAPI Documentation**: Complete API specification and interactive docs
- **Health Monitoring**: Built-in health checks and monitoring endpoints
- **Latest Dependencies**: FastAPI 0.115.0, Pydantic 2.9.2, TimezoneFinder 6.5.5

## Quick Start

### Using Docker Compose

```bash
# Start the service
docker-compose -f docker/time-resolver.docker-compose.yml up -d

# Check health
curl http://localhost:8080/health

# Test resolution
curl -X POST http://localhost:8080/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "local_datetime": "1962-07-02T23:33:00",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "parity_profile": "strict_history"
  }'
```

### Building from Source

```bash
# Build the image
docker build -f docker/time-resolver.Dockerfile -t time-resolver .

# Run the container
docker run -p 8080:8080 time-resolver
```

## API Documentation

The service provides interactive API documentation at:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- OpenAPI spec: `http://localhost:8080/openapi.json`

## Parity Profiles

| Profile | Description | Use Case |
|---------|-------------|----------|
| `strict_history` | IANA tzdb + historical patches | Maximum accuracy for serious work |
| `astro_com` | Standard IANA rules only | Astrodienst compatibility |
| `clairvision` | Future compatibility mode | Clairvision software compatibility |
| `as_entered` | Trust user input | Manual timezone override with warnings |

## Endpoints

### `POST /resolve`

Resolve historical timezone for local datetime.

**Request:**
```json
{
  "local_datetime": "1943-06-15T14:30:00",
  "latitude": 37.8917,
  "longitude": -85.9623,
  "parity_profile": "strict_history"
}
```

**Response:**
```json
{
  "utc": "1943-06-15T18:30:00Z",
  "zone_id": "America/New_York",
  "offset_seconds": -14400,
  "dst_active": true,
  "confidence": "high",
  "reason": "Fort Knox used Eastern War Time during WWII",
  "notes": ["Applied patch: fort_knox_1943"],
  "warnings": [],
  "provenance": {
    "tzdb_version": "tzdata-2024.2",
    "sources": ["coordinate_lookup", "IANA_tzdb", "historical_patches"],
    "resolution_mode": "strict_history",
    "patches_applied": ["fort_knox_1943"]
  }
}
```

### `GET /health`

Service health check with version information.

## Historical Patches

The service includes 10 historical patches for US timezone accuracy:

1. **Fort Knox 1943**: Eastern War Time during WWII
2. **Louisville Central Time**: Used Central Time until 1961
3. **Michigan Upper Peninsula**: Central Time usage
4. **Arizona War Time**: War Time 1942-1944
5. **Hawaii Standard Time**: HST (-10:30) before 1947
6. **Chicago War Time**: Year-round Central War Time
7. **Detroit Fast Time**: Local mean solar time 1905-1915
8. **Philadelphia War Time**: Eastern War Time
9. **Texas Central Border**: El Paso area Mountain Time
10. **NYC War Time 1943**: Year-round Eastern War Time

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `RESOLVER_PATCH_FILE` | `/app/config/patches_us_pre1967.json` | Path to patches file |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |
| `TZ` | `UTC` | Container timezone |

### Custom Patches

To use custom patches, mount a JSON file and set `RESOLVER_PATCH_FILE`:

```bash
docker run -p 8080:8080 \
  -v /path/to/patches.json:/app/config/custom_patches.json \
  -e RESOLVER_PATCH_FILE=/app/config/custom_patches.json \
  time-resolver
```

## Production Deployment

For production, use the nginx proxy configuration:

```bash
# Start with nginx proxy
docker-compose -f docker/time-resolver.docker-compose.yml --profile production up -d
```

This provides:
- Rate limiting (10 requests/second)
- CORS handling
- Health check endpoint
- Reverse proxy with load balancing

## Development

### Local Development

```bash
cd docker/time-resolver

# Install dependencies
pip install -r requirements.txt

# Run the service
python -m time_resolver.api
```

### Testing

```bash
# Test with different parity profiles
curl -X POST http://localhost:8080/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "local_datetime": "1943-06-15T14:30:00",
    "latitude": 37.8917,
    "longitude": -85.9623,
    "parity_profile": "astro_com"
  }'
```

## Integration

### Python Client

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

response = client.post("/resolve", json={
    "local_datetime": "1962-07-02T23:33:00",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "parity_profile": "strict_history"
})

result = response.json()
print(f"UTC: {result['utc']}")
print(f"Zone: {result['zone_id']}")
print(f"Confidence: {result['confidence']}")
```

### JavaScript Client

```javascript
const response = await fetch('http://localhost:8080/resolve', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    local_datetime: '1962-07-02T23:33:00',
    latitude: 40.7128,
    longitude: -74.0060,
    parity_profile: 'strict_history'
  })
});

const result = await response.json();
console.log(`UTC: ${result.utc}`);
console.log(`Zone: ${result.zone_id}`);
```

## License

MIT License - see LICENSE file for details.