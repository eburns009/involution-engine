# Involution Engine v1.1 - Single FastAPI Service

This directory contains the implementation of the Involution Engine with Phase 2 — Usability & Breadth features, including expanded ayanāṃśa registry, equatorial/J2000 coordinate output, flexible date parsing, Redis cache layer, and distributed rate limiting.

## Architecture Overview

```
/server
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + health endpoint
│   ├── api.py               # API endpoints implementation
│   ├── config.py            # Typed configuration with Pydantic
│   ├── schemas.py           # Pydantic models for API
│   ├── caching.py           # LRU cache + ETag support
│   ├── caching_redis.py     # Redis distributed cache layer
│   ├── ratelimit.py         # Redis-based rate limiting
│   ├── errors.py            # Friendly error mapping
│   ├── util/
│   │   └── dates.py         # Flexible date parsing utilities
│   ├── ephemeris/
│   │   ├── __init__.py
│   │   ├── kernels.py       # Kernel verification system
│   │   ├── compute.py       # SPICE calculations with equatorial support
│   │   ├── pool.py          # Bounded worker processes
│   │   ├── ayanamsha.py     # Enhanced ayanāṃśa registry
│   │   └── ayanamsas.yaml   # YAML ayanāṃśa configuration
│   ├── time_resolver/
│   │   └── client.py        # HTTP client to time resolver
│   └── geocode/
│       └── client.py        # HTTP client to Nominatim
├── tests/
│   ├── test_positions_e2e.py
│   ├── test_healthz.py
│   ├── test_error_mapper.py
│   ├── test_ayanamsha_registry.py
│   ├── test_equatorial_j2000.py
│   ├── test_flexible_dates.py
│   ├── test_redis_cache.py
│   ├── test_rate_limiting.py
│   └── test_phase2_integration.py
├── config.yaml             # Example configuration
├── requirements.txt         # Python dependencies
├── Dockerfile.de440-full   # Kernel bundle containers
├── Dockerfile.de440-1900
└── Dockerfile.de440-modern
```

## Phase 2 — Usability & Breadth Features

### ✅ Core Foundation (Phase 1)

1. **Configuration System** (`config.py`)
   - Typed Pydantic models for all settings
   - Environment variable overrides
   - Redis cache and rate limiting configuration

2. **Enhanced Ayanāṃśa Registry** (`ephemeris/ayanamsha.py` + `ayanamsas.yaml`)
   - YAML-based configuration with 6 supported systems
   - Support for fixed and formula types (lahiri, fagan_bradley_dynamic/fixed, krishnamurti, raman, yukteshwar)
   - Case-insensitive resolution and validation

3. **Equatorial/J2000 Coordinate Support** (`ephemeris/compute.py`)
   - RA/Dec output in addition to ecliptic coordinates
   - Frame/epoch validation (ecliptic_of_date + of_date, equatorial + J2000)
   - Coordinate system transformations

4. **Flexible Date Parsing** (`util/dates.py`)
   - Support for multiple datetime formats using python-dateutil
   - ISO, US, European, and natural language date formats
   - Timezone-aware parsing with safety validation

5. **Redis Cache Layer** (`caching_redis.py`)
   - Distributed Redis caching for multi-instance deployments
   - Hybrid L1 (in-process) + L2 (Redis) caching strategy
   - Health checks and statistics

6. **Distributed Rate Limiting** (`ratelimit.py`)
   - Redis-based token bucket rate limiting
   - IP and user-based limiting with configurable rules
   - Fail-open behavior for Redis unavailability

7. **Comprehensive Testing** (`tests/`)
   - Unit tests for all Phase 2 features
   - Integration tests for feature interactions
   - Mock support for Redis when unavailable

### ✅ Production-Ready Features

- **SPICE Compute Engine** with DE440/DE441 automatic handoff
- **Worker Pool** with bounded process management
- **Kernel Management** with SHA256 verification
- **Error Mapping** with structured error responses
- **Client Modules** for time resolver and geocoding
- **Health Monitoring** with comprehensive diagnostics

## Quick Start

```bash
# Install dependencies
cd server
pip install -r requirements.txt

# Optional: Set up Redis for caching and rate limiting
# docker run -d --name redis -p 6379:6379 redis:alpine

# Run the service
uvicorn app.main:app --host 0.0.0.0 --port 8080

# Health check
curl http://localhost:8080/healthz
```

## Configuration

The service uses `config.yaml` for configuration:

```yaml
api:
  cors_origins: ["http://localhost:3000"]
  workers: 4

kernels:
  bundle: "de440-1900"
  path: "/opt/kernels"

cache:
  inproc_lru_size: 4096
  inproc_ttl_seconds: 3600

# Phase 2 Features
redis_cache:
  enabled: true
  url: "redis://localhost:6379/0"
  ttl_seconds: 3600

rate_limiting:
  enabled: true
  redis_url: "redis://localhost:6379/1"
  rules:
    - key: "ip"
      limit: "200/minute"

time:
  base_url: "http://localhost:9000"
  tzdb_version: "2025.1"

ephemeris:
  policy: "auto"  # DE440/DE441 handoff
  ayanamsa_registry_file: "app/ephemeris/ayanamsas.yaml"
```

Environment overrides:
- `KERNEL_BUNDLE` - Override kernel bundle
- `WORKERS` - Number of worker processes
- `TIME_RESOLVER_URL` - Time resolver service URL
- `REDIS_URL` - Redis connection URL for cache and rate limiting
- `DISABLE_RATE_LIMIT` - Disable rate limiting for development

## API Endpoints

- `POST /v1/positions` - Planetary positions
- `POST /v1/time/resolve` - Time zone resolution
- `GET /v1/geocode/search` - Location search
- `GET /healthz` - Service health check

## Key Features

### Core Engine
- **Single Service**: No gateway or microservice complexity
- **Preloaded Kernels**: Workers preload SPICE kernels for performance
- **Auto Ephemeris**: DE440/DE441 handoff based on date range
- **Typed Config**: Full Pydantic validation
- **Health Monitoring**: Rich `/healthz` endpoint

### Phase 2 - Usability & Breadth
- **Expanded Ayanāṃśa Registry**: YAML-based with 6 supported systems
- **Equatorial Coordinates**: RA/Dec output with J2000 epoch support
- **Flexible Date Parsing**: Multiple datetime formats using dateutil
- **Distributed Caching**: Redis L2 cache with hybrid L1/L2 strategy
- **Rate Limiting**: Redis-based token bucket with fail-open behavior
- **Error Mapping**: Enhanced SPICE errors → friendly API error codes

## Testing Strategy

1. **Unit Tests**: Individual component testing
2. **Golden Tests**: Validate against Fort Knox 1962 baseline
3. **E2E Tests**: Full API request/response cycles
4. **Performance**: p95 < 200ms for typical calculations

## Performance Targets

- Response time: <100ms p95 for planetary calculations
- Memory usage: <50MB per worker process
- Kernel load time: <500ms for complete initialization
- Accuracy: ≤1' planets, ≤30' Moon, ≤5' nodes

## Production Deployment

The service is designed for containerized deployment:

```dockerfile
FROM python:3.11-slim
COPY kernels/ /opt/kernels/
COPY app/ /app/
COPY config.yaml /app/
WORKDIR /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Phase 2 Acceptance Criteria

### ✅ Core Foundation
- [x] Configuration system with typed validation
- [x] Kernel verification and management
- [x] Worker pool with preloaded kernels
- [x] SPICE computation engine
- [x] Comprehensive error mapping
- [x] HTTP clients for external services
- [x] Pydantic schemas matching OpenAPI v1.1
- [x] FastAPI endpoints implementation
- [x] Main app with middleware

### ✅ Phase 2 - Usability & Breadth
- [x] **Ayanāṃśa Registry**: YAML-based with 6 systems (lahiri, fagan_bradley_dynamic/fixed, krishnamurti, raman, yukteshwar)
- [x] **Equatorial/J2000 Output**: RA/Dec coordinates with proper frame/epoch validation
- [x] **Flexible Date Parsing**: Multiple formats (ISO, US, European, natural language) using dateutil
- [x] **Redis Cache Layer**: Distributed L2 cache with hybrid L1/L2 strategy and health monitoring
- [x] **Distributed Rate Limiting**: Redis-based token bucket with IP/user keys and fail-open behavior
- [x] **Comprehensive Testing**: Unit tests, integration tests, and Phase 2 feature validation

### ✅ Production Ready
- [x] Enhanced configuration with Redis support
- [x] Health monitoring with cache and rate limiter status
- [x] Backwards compatibility maintained
- [x] Performance validation (cache hit rates, rate limiting efficiency)
- [x] Error taxonomy with actionable guidance

## Usage Examples

### Equatorial Coordinates with Sidereal System
```bash
curl -X POST http://localhost:8080/v1/positions \
  -H "Content-Type: application/json" \
  -d '{
    "when": {"utc": "2023-01-01T12:00:00Z"},
    "system": "sidereal",
    "ayanamsha": {"id": "lahiri"},
    "frame": {"type": "equatorial"},
    "epoch": "J2000",
    "bodies": ["Sun", "Moon"]
  }'
```

### Flexible Date Formats
```bash
# Natural language
curl -X POST http://localhost:8080/v1/positions \
  -d '{"when": {"local_datetime": "Dec 25, 2023 3:30 PM", "place": {"lat": 40.7128, "lon": -74.0060}}, "system": "tropical", "bodies": ["Sun"]}'

# US format
curl -X POST http://localhost:8080/v1/positions \
  -d '{"when": {"local_datetime": "12/25/2023 15:30:00", "place": {"lat": 40.7128, "lon": -74.0060}}, "system": "tropical", "bodies": ["Sun"]}'
```

This implementation provides a robust, production-ready single-service architecture for the Involution Engine v1.1 with Phase 2 — Usability & Breadth features.