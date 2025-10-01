# 📖 Involution Engine — Changelog

All notable changes to this project will be documented here.
Format inspired by [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Phase 3 implementation components in development
- Enhanced CI/CD pipeline with quality gates

### Changed
- Documentation structure reorganization

### Fixed
- Minor accuracy improvements in development

---

## [v1.1.0] - 2025-01-15

### 🔭 Ephemeris & Kernels
- **Ephemeris bundle**: DE440 / DE441 handoff enabled ✅
- **Kernel variants built**:
  - `de440-full` (1550–2650 CE)
  - `de440-1900` (1900–2100 CE)
  - `de440-modern` (1950–2050 CE)
- **Kernel SHA256 checksums** recorded in `/docs/releases/kernels/v1.1.0.sha256`
- **Automatic handoff** validated: DE440 for 1550-2650 CE, DE441 for extended ranges

### 🌍 Time & Location
- **TZDB version**: `tzdata-2024.2`
- **Time Resolver patches**: Enhanced local datetime parsing with natural language support
- **Geocoding backend**: Nominatim (self-hosted v4.4)
- **Timezone coverage**: Full IANA database with historical transitions

### 🛰️ API
- **New endpoints**:
  - `/v1/stars/positions` (feature-flagged, disabled by default)
  - Enhanced `/healthz` with kernel status and cache metrics
- **Updated endpoints**:
  - `/v1/positions`: Added support for flexible `bodies` array selector
  - `/v1/time/resolve`: Improved natural language datetime parsing
- **Error taxonomy expanded**:
  - `INPUT.INVALID` for malformed requests
  - `EPHEMERIS.DATE_RANGE` for dates outside kernel coverage
  - `AYANAMSHA.REQUIRED` for sidereal calculations
  - `FEATURE.DISABLED` for feature-flagged endpoints

### ✨ Features
- **Fixed Stars**:
  - **Status**: Disabled by default (`features.fixed_stars.enabled: false`)
  - **Catalog**: Yale Bright Star Catalog (BSC5), magnitude ≤ 2.5
  - **Coordinate systems**: Equatorial ↔ Ecliptic transformations
  - **Proper motion**: Basic correction capability implemented
- **Ayanāṃśa registry**:
  - Lahiri (Chitrapaksha) - official Indian government formula
  - Fagan-Bradley Dynamic (time-dependent calculation)
  - Fagan-Bradley Fixed (24.22° at Jan 1, 1950)
  - Krishnamurti, B.V. Raman, Yukteshwar
- **Health & metrics**: `/healthz`, `/metrics` endpoints with comprehensive status reporting

### ⚡ Performance
- **Caching**: In-process LRU with ETag support and Redis backend
- **Response times**: p95 latency <100ms for standard calculations
- **Canary rollout**: Successfully deployed with p95 latency <200ms, error rate <0.1%
- **Throughput**: Sustained 1000+ req/min with <1% error rate

### 🛡️ Security & Ops
- **Container security**: Non-root Docker images with minimal base layers
- **Audit logging**: Full provenance tracking (UTC resolution, ayanāṃśa selection, kernel versions)
- **CI/CD gates**: 6-gate quality pipeline with accuracy tests, drift detection, performance benchmarks
- **Drift detection**: Weekly automated monitoring against Swiss Ephemeris reference
- **Dependency scanning**: Zero critical vulnerabilities in production dependencies

### 📚 Documentation
- **User guides**:
  - `docs/users/quickstart-astrologers.md` - Comprehensive API introduction for astrologers
  - `docs/users/migrating-from-swiss.md` - Swiss Ephemeris to Involution Engine migration
  - `docs/users/accuracy-guarantees.md` - Detailed accuracy specifications and monitoring
- **Operations**:
  - `RELEASE_CHECKLIST.md` - Production release procedures
  - `docs/deploy/canary.md` - Canary deployment guide
  - `docs/deploy/release-process.md` - Complete release workflow documentation

### 🔄 Infrastructure
- **Canary deployments**: Nginx weighted upstream with 90/10 → 50/50 → 100/0 progression
- **Service orchestration**: Docker Compose with health checks and dependency management
- **Monitoring**: Prometheus metrics, structured logging, automated alerting

---

## [v1.0.0] - 2024-12-01

### 🔭 Ephemeris & Kernels
- **Initial release** with DE440 ephemeris support
- **Kernel variants**:
  - `de440-full` for maximum date range coverage
  - `de440-1900` optimized for modern historical calculations
- **Accuracy guarantees**: ≤1' for planets, ≤30' for Moon, ≤5' for nodes

### 🌍 Time & Location
- **TZDB version**: `tzdata-2024.1`
- **Time Resolver**: Local datetime to UTC conversion service
- **Coordinate validation**: Lat/lon boundary checking and normalization

### 🛰️ API
- **Core endpoints**:
  - `/v1/positions` - Planetary position calculations
  - `/v1/time/resolve` - Local datetime to UTC conversion
  - `/healthz` - Service health monitoring
- **Coordinate systems**: Tropical and Sidereal with configurable ayanāṃśa
- **Bodies supported**: Sun, Moon, planets, True/Mean lunar nodes

### ✨ Features
- **Tropical zodiac**: High-precision planetary positions
- **Sidereal systems**: Multiple ayanāṃśa implementations
- **Flexible time input**: UTC, local datetime with timezone resolution
- **JSON API**: RESTful interface with structured error responses

### ⚡ Performance
- **Sub-second response times** for standard calculations
- **Efficient caching** for repeated queries
- **Scalable architecture** with microservice design

### 🛡️ Security & Ops
- **Production hardening**: Security headers, rate limiting
- **Health monitoring**: Comprehensive status reporting
- **Error handling**: Structured error codes with helpful messages

### 📚 Documentation
- **API documentation**: Complete endpoint specifications
- **Accuracy specifications**: Detailed tolerance documentation
- **Deployment guides**: Docker and production setup instructions

---

## Example Entry Format

```markdown
## [vX.Y.Z] - YYYY-MM-DD

### 🔭 Ephemeris & Kernels
- Built `de440-1900` slim bundle (~50MB) for default deployments
- Automatic DE440→DE441 handoff validated in golden tests

### 🌍 Time & Location
- Updated tzdb to `tzdata-2025.1`
- Added historical patch for Newfoundland 1940 timezone transition

### 🛰️ API
- `/v1/positions` now supports `bodies=["Sun","Moon"]` subset queries
- Enhanced error responses with actionable tips

### ✨ Features
- **Fixed Stars**: Endpoint scaffolded (feature flag: disabled)
- **Ayanāṃśa**: Added Raman and Yukteshwar implementations

### ⚡ Performance
- Cache hit rate observed at 72% in staging environment
- Canary rollout to production completed successfully

### 🛡️ Security & Ops
- Updated base images to address CVE-2024-XXXX
- Enhanced audit logging with request provenance

### 📚 Documentation
- Added "Quick Start for Astrologers" comprehensive guide
- Updated Swiss Ephemeris migration examples
```

---

**Versioning**: This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking API changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, security patches

**Release Artifacts**: Each release includes Docker images, kernel checksums, and validation reports in the [GitHub Releases](https://github.com/your-org/involution-engine/releases) section.