# Involution Engine

[![Quick Check](https://github.com/involution-engine/involution-engine/actions/workflows/quick-check.yml/badge.svg)](https://github.com/involution-engine/involution-engine/actions/workflows/quick-check.yml)
[![Comprehensive CI](https://github.com/involution-engine/involution-engine/actions/workflows/comprehensive-ci.yml/badge.svg)](https://github.com/involution-engine/involution-engine/actions/workflows/comprehensive-ci.yml)
[![Nightly Tests](https://github.com/involution-engine/involution-engine/actions/workflows/nightly-comprehensive.yml/badge.svg)](https://github.com/involution-engine/involution-engine/actions/workflows/nightly-comprehensive.yml)

Research-grade, self-contained astrological calculation engine with topocentric positions, time resolution, and tropical/sidereal zodiac support. Powered by NASA NAIF SPICE (via SpiceyPy) with comprehensive validation and testing.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Involution Engine                         │
├─────────────────────────────────────────────────────────────┤
│  /engine          │ Core calculation services (SPICE+FastAPI)│
│  /time_resolver   │ Timezone + parity logic                  │
│  /geocode_proxy   │ Nominatim/nginx proxy (planned)          │
│  /batch_positions │ Testing harness + validation scripts     │
│  /examples        │ Reference charts + accuracy test packs   │
│  /tests           │ Unit tests + golden case validation      │
└─────────────────────────────────────────────────────────────┘
```

**Data Flow:**
Client → Engine (FastAPI) → SPICE Toolkit → Time Resolver → Validated Positions

## Quickstart

### Docker Compose (Recommended)

```bash
docker compose up -d
```

Services will be available at:
- Engine: `http://localhost:8000`
- Time Resolver: `http://localhost:5000`
- Health checks: `/health` on each service

### Local Development

```bash
# 1. Install Python dependencies
pip install -r engine/requirements.txt

# 2. Download SPICE kernels
./engine/download_kernels.sh

# 3. Start the engine
cd engine && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 4. Test the engine
curl -s http://localhost:8000/health
```

## Example Chart Query (Fort Knox Test)

```bash
curl -s -X POST http://localhost:8000/calculate \
  -H 'content-type: application/json' \
  -d '{
    "birth_time": "1962-07-03T04:33:00Z",
    "latitude": 37.840347,
    "longitude": -85.949127,
    "elevation": 0.0,
    "zodiac": "tropical",
    "ayanamsa": "lahiri"
  }' | jq .
```

## Key Features

- **Topocentric Positions**: Observer-based calculations via `spkcpo` with `LT+S` corrections
- **Tropical & Sidereal**: Both zodiac systems with multiple ayanamsa options
- **Time Resolution**: Handles complex timezone scenarios with parity profiles
- **Houses**: Multiple house systems (Placidus, Koch, Equal, etc.)
- **Validation**: Comprehensive testing against Swiss Ephemeris and Astro.com
- **Security**: CORS controls, rate limiting, input validation

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Service health and metadata |
| `/v1/positions` | POST | Planetary positions |
| `/v1/time/resolve` | POST | Time zone resolution |
| `/v1/geocode/search` | GET | Location search |

See [docs/openapi/v1.1.yaml](docs/openapi/v1.1.yaml) for complete API documentation.

### API v1.1 Documentation

- **[OpenAPI Specification](docs/openapi/v1.1.yaml)** - Complete API contract with examples
- **[Error Taxonomy](docs/error-taxonomy.md)** - Standardized error codes and resolution guidance
- **[Example Requests](examples/http/)** - Sample HTTP requests and responses

## Accuracy & Validation

The engine is validated against:
- Swiss Ephemeris reference positions
- Astro.com calculated charts
- Historical accuracy test suites

Tolerance: ±0.01° for planetary positions, ±0.1° for house cusps.

See [docs/accuracy.md](docs/accuracy.md) for validation methodology.

## Development

```bash
# Run all tests
pytest tests/

# Code quality checks
ruff check engine/
mypy engine/
bandit -r engine/

# Performance benchmarks
python tests/batch/accuracy_compare.py
```

## Documentation

- **[Golden Test Data](tests/goldens/README.md)** - Reference dataset with full provenance
- **[Accuracy Methodology](docs/accuracy.md)** - Validation tolerances and procedures
- **[Roadmap](docs/roadmap.md)** - Features and versioning strategy
- **[Error Taxonomy](docs/error-taxonomy.md)** - Standardized error handling

## Example Test Packs

- `examples/five_random/` - Random date validation pack
- `examples/fagan_multi_date_suite/` - Fagan-Bradley test cases

## License

Research and educational use. See LICENSE for details.

## Acknowledgments

- NASA NAIF SPICE Toolkit and JPL ephemerides
- SpiceyPy maintainers and contributors