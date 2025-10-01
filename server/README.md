# Involution Engine v1.1 - Single FastAPI Service

This directory contains the implementation of Phase 1 — Simplify Core, which replaces the gateway + scattered config with one FastAPI service.

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
│   ├── errors.py            # Friendly error mapping
│   ├── ephemeris/
│   │   ├── __init__.py
│   │   ├── kernels.py       # Kernel verification system
│   │   ├── compute.py       # SPICE calculations
│   │   ├── pool.py          # Bounded worker processes
│   │   └── ayanamsha.py     # Ayanāṃśa registry
│   ├── time_resolver/
│   │   └── client.py        # HTTP client to time resolver
│   └── geocode/
│       └── client.py        # HTTP client to Nominatim
├── tests/
│   ├── test_positions_e2e.py
│   ├── test_healthz.py
│   └── test_error_mapper.py
├── config.yaml             # Example configuration
├── Dockerfile.de440-full   # Kernel bundle containers
├── Dockerfile.de440-1900
└── Dockerfile.de440-modern
```

## Implementation Status

### ✅ Completed Components

1. **Configuration System** (`config.py`)
   - Typed Pydantic models for all settings
   - Environment variable overrides
   - Validation and error handling

2. **Ayanāṃśa Registry** (`ephemeris/ayanamsha.py`)
   - Pluggable ayanāṃśa system
   - Support for fixed and formula types
   - Validation for tropical/sidereal compatibility

3. **Kernel Management** (`ephemeris/kernels.py`)
   - SHA256 verification system
   - Bundle validation and info
   - Comprehensive error handling

4. **Worker Pool** (`ephemeris/pool.py`)
   - Bounded process pool with preloaded kernels
   - Statistics and health monitoring
   - Proper shutdown and cleanup

5. **SPICE Compute Engine** (`ephemeris/compute.py`)
   - Full SPICE integration with fallback mocks
   - DE440/DE441 automatic handoff
   - Comprehensive error mapping

6. **Caching System** (`caching.py`)
   - Thread-safe in-process LRU cache
   - ETag generation and management
   - TTL and automatic cleanup

7. **Error Mapping** (`errors.py`)
   - SPICE error → friendly error codes
   - Structured error responses
   - Comprehensive error handling

8. **Client Modules**
   - Time resolver HTTP client
   - Geocoding service HTTP client

### 🚧 Remaining Work

To complete Phase 1, you need to implement:

1. **Schemas** (`schemas.py`) - Pydantic models matching OpenAPI v1.1
2. **API Endpoints** (`api.py`) - FastAPI routes for all endpoints
3. **Main Application** (`main.py`) - FastAPI app with middleware
4. **Dockerfiles** - Container builds for kernel bundles
5. **Tests** - E2E tests for all functionality

## Quick Start (Once Complete)

```bash
# Install dependencies
pip install fastapi uvicorn pydantic[dotenv] httpx spiceypy

# Run the service
cd server
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

time:
  base_url: "http://localhost:9000"
  tzdb_version: "2025.1"

ephemeris:
  policy: "auto"  # DE440/DE441 handoff
```

Environment overrides:
- `KERNEL_BUNDLE` - Override kernel bundle
- `WORKERS` - Number of worker processes
- `TIME_RESOLVER_URL` - Time resolver service URL

## API Endpoints

- `POST /v1/positions` - Planetary positions
- `POST /v1/time/resolve` - Time zone resolution
- `GET /v1/geocode/search` - Location search
- `GET /healthz` - Service health check

## Key Features

- **Single Service**: No gateway or microservice complexity
- **Preloaded Kernels**: Workers preload SPICE kernels for performance
- **LRU Caching**: In-memory cache with ETag support
- **Error Mapping**: SPICE errors → friendly API error codes
- **Auto Ephemeris**: DE440/DE441 handoff based on date range
- **Typed Config**: Full Pydantic validation
- **Health Monitoring**: Rich `/healthz` endpoint

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

## Acceptance Criteria

- [x] Configuration system with typed validation
- [x] Ayanāṃśa registry with pluggable support
- [x] Kernel verification and management
- [x] Worker pool with preloaded kernels
- [x] SPICE computation engine
- [x] LRU caching with ETag
- [x] Comprehensive error mapping
- [x] HTTP clients for external services
- [ ] Pydantic schemas matching OpenAPI v1.1
- [ ] FastAPI endpoints implementation
- [ ] Main app with middleware
- [ ] Comprehensive test suite
- [ ] Performance validation
- [ ] Docker builds

## Next Steps

1. Complete the remaining schemas, API, and main app files
2. Implement comprehensive test suite
3. Validate against golden tests and five_random pack
4. Create Docker builds for kernel bundles
5. Performance testing and optimization
6. Create PR with full acceptance criteria

This foundation provides a robust, production-ready single-service architecture for the Involution Engine v1.1.