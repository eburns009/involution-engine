# Roadmap

Development roadmap and versioning strategy for Involution Engine.

## Current Version: 1.1.0 (Foundation Release)

### Single-Service Architecture ✅

**Unified Engine Service**
- Single FastAPI service handling all astronomical calculations
- Topocentric planetary positions via SPICE toolkit
- Tropical and sidereal zodiac support
- Multiple ayanāṃśa options (Lahiri, Fagan-Bradley Dynamic, Raman, Krishnamurti)
- Time resolution with parity profiles
- Built-in geocoding proxy (thin Nominatim wrapper)
- ECLIPDATE frame with IAU-1980 mean obliquity
- Light-time and aberration corrections (LT+S)

**API v1.1 Endpoints**
- `POST /v1/positions` - Planetary position calculations
- `POST /v1/time/resolve` - Timezone resolution
- `GET /v1/geocode/search` - Location search proxy
- `GET /healthz` - Service health check

**Quality & Validation**
- Golden test dataset with full provenance (`tests/goldens/`)
- Standardized error taxonomy with actionable guidance
- Comprehensive OpenAPI v1.1 specification
- Validation against Swiss Ephemeris and Astro.com
- Professional-grade accuracy tolerances (≤1' planets, ≤30' Moon, ≤5' nodes)

**Production Readiness**
- Docker containerization
- Production-ready gunicorn configuration
- Structured error handling with tips
- Rate limiting and CORS controls

---

## Version 2.1.0 (Q4 2024) 🚧

### Planned Features

**Fixed Stars Support**
- Fixed star positions and calculations
- Popular fixed star catalog integration
- Coordinate precession handling

**Enhanced Time Resolution**
- Expanded timezone database support
- Improved historical accuracy for pre-1970 dates
- DST transition edge case handling

**Performance Optimization**
- Response caching layer
- Kernel loading optimization
- Connection pooling for concurrent requests

**API Enhancements**
- Batch calculation endpoints
- WebSocket support for real-time updates
- Additional house systems

---

## Version 2.2.0 (Q1 2025) 🔮

### Planned Features

**Sky Tonight**
- Current planetary positions
- Real-time transits
- Ephemeris windows

**Small Bodies**
- Asteroid positions (Ceres, Pallas, Juno, Vesta)
- Chiron calculations
- Hypothetical bodies (Lilith)

**Advanced Calculations**
- Arabic Parts/Lots
- Midpoints calculations
- Harmonic charts

**UI/Frontend**
- Next.js reference implementation
- Interactive chart visualization
- Settings and preferences management

---

## Version 3.0.0 (Q2 2025) 🌟

### Major Features

**Time Windows**
- Transit calculations
- Progression and direction support
- Event timing analysis

**Geocoding Service**
- Built-in Nominatim proxy
- Location search and validation
- Timezone automatic detection

**Extended Ephemeris**
- Support for additional DE ephemeris versions
- Historical range extensions
- Custom kernel loading

**Plugin Architecture**
- Custom calculation plugins
- Third-party integrations
- Extensible house systems

---

## Versioning Strategy

### Semantic Versioning
- **Major (X.0.0)**: Breaking API changes, architectural updates
- **Minor (X.Y.0)**: New features, backward-compatible enhancements
- **Patch (X.Y.Z)**: Bug fixes, security updates, documentation

### Parity Profiles
Engine maintains multiple parity profiles for compatibility:

- **strict_history**: Maximum historical accuracy, research-grade
- **astro_com**: Compatibility with Astro.com calculations
- **clairvision**: Compatibility with Clairvision software
- **as_entered**: Use user-provided timezone data as-is

### API Compatibility
- **v1 endpoints**: Maintained for backward compatibility
- **v2 endpoints**: Current feature set
- **v3 endpoints**: Planned for major release

---

## Feature Status

### ✅ Complete
- [x] Topocentric planetary positions
- [x] Tropical/sidereal zodiac support
- [x] Multiple ayanamsa options
- [x] House systems (5+ types)
- [x] Time resolution with historical accuracy
- [x] Production deployment support
- [x] Comprehensive testing harness
- [x] Validation against reference implementations

### 🚧 In Progress
- [ ] Fixed stars integration
- [ ] Performance optimization
- [ ] Batch calculation endpoints
- [ ] WebSocket real-time updates

### 🔮 Planned
- [ ] Sky Tonight real-time features
- [ ] Small body calculations (asteroids, Chiron)
- [ ] Arabic Parts/Lots
- [ ] Transit and progression calculations
- [ ] Built-in geocoding service
- [ ] Next.js UI reference implementation

### 🤔 Under Consideration
- [ ] Machine learning for timezone disambiguation
- [ ] GraphQL API alternative
- [ ] Mobile SDK development
- [ ] Integration with popular astrology software

---

## Technology Roadmap

### Current Stack (v1.1)
- **Backend**: Python 3.11+, FastAPI, SpiceyPy
- **Ephemeris**: JPL DE440 (1550-2650 CE), DE441 (outside range)
- **Kernels**: NASA NAIF SPICE (DE440, PCK, LSK, BPC)
- **Testing**: pytest, golden case validation with provenance
- **Deployment**: Docker, gunicorn, nginx

### DE440/DE441 Handoff Policy
- **Primary Range (1550-2650 CE)**: DE440 ephemeris for optimal accuracy
- **Extended Range**: Automatic DE441 handoff for dates outside DE440 coverage
- **Seamless Transition**: No API changes required for ephemeris switching
- **Performance**: DE440 optimized for historical and near-future calculations

### Planned Additions
- **Caching**: Redis for response caching with ETag support
- **Monitoring**: Prometheus metrics, structured logging
- **Documentation**: Enhanced interactive documentation
- **Testing**: Expanded golden dataset coverage

### Performance Targets (v1.1)
- **Response Time**: <100ms p95 for planetary calculations
- **Accuracy**: ≤1' planets, ≤30' Moon, ≤5' nodes
- **Availability**: 99.9% uptime SLA
- **Throughput**: 1000+ requests/minute per instance

---

## Community & Contributions

### Open Source Plans
- Core engine remains open source
- Community contributions welcome
- Plugin ecosystem development
- Documentation improvements

### Research Collaborations
- Academic partnerships for validation
- Professional astrologer feedback
- Historical accuracy studies
- Cross-platform compatibility testing

---

## Migration Guide

### From v1.x to v2.x
- Update endpoint URLs (`/calculate` remains compatible)
- Add `zodiac` parameter for tropical/sidereal selection
- Update response parsing for new metadata fields
- Test with new parity profiles

### Breaking Changes Policy
- 6-month deprecation notice for major changes
- Backward compatibility maintained for 2 releases
- Clear migration documentation provided
- Community notification via changelog

---

## Support & Maintenance

### Long-term Support (LTS)
- **v2.0.x**: LTS until Q2 2026
- **v3.0.x**: LTS planned from Q2 2025
- Security updates for all supported versions
- Critical bug fixes with expedited releases

### Release Schedule
- **Major releases**: Annual (Q2)
- **Minor releases**: Quarterly
- **Patch releases**: As needed (security, critical bugs)
- **Preview releases**: Monthly development snapshots

---

## Feedback & Requests

Submit feature requests and feedback:
- GitHub Issues for bugs and enhancements
- Discussions for roadmap input
- Community Discord for real-time feedback
- Professional consulting for custom features

The roadmap is subject to change based on community feedback, technical considerations, and resource availability.