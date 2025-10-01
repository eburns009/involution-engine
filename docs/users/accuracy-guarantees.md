# Accuracy Guarantees

**Involution Engine v1.1** provides research-grade astrological calculations with defined accuracy tolerances and continuous validation against Swiss Ephemeris reference data.

---

## 📐 Tolerance Specifications

### Planetary Positions

| Body Type | Tolerance (Longitude) | Tolerance (Latitude) | Notes |
|-----------|----------------------|---------------------|--------|
| **Planets** (Sun, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto) | **≤1 arcminute (60")** | ≤1 arcminute | Tropical & sidereal |
| **Moon** | **≤30 arcminutes (0.5°)** | ≤30 arcminutes | Higher tolerance due to rapid motion |
| **Lunar Nodes** (True Node, Mean Node) | **≤5 arcminutes (300")** | N/A | Node positions only |

### Houses & Angles

| Component | Tolerance | System |
|-----------|-----------|--------|
| **House Cusps** | ≤3 arcminutes | Placidus, Koch, Equal |
| **Ascendant** | ≤1 arcminute | All systems |
| **Midheaven** | ≤1 arcminute | All systems |

### Coordinate Systems

| Output | Tolerance | Reference Frame |
|--------|-----------|-----------------|
| **Ecliptic Longitude** | ≤1' (planets), ≤30' (Moon) | Ecliptic of Date (IAU 1980 mean) |
| **Ecliptic Latitude** | ≤1' | Ecliptic of Date |
| **Right Ascension** | ≤1 arcsecond | Equatorial J2000 |
| **Declination** | ≤1 arcsecond | Equatorial J2000 |

---

## 🎯 Validation Methodology

### 1. Golden Test Dataset

**Reference Data**: 20+ historical charts spanning 1875-2025 with known positions from:
- Swiss Ephemeris (official reference)
- Astro.com calculated charts
- Published ephemeris tables

**Test Cases**:
- **Fort Knox 1962** (canonical): July 3, 1962, 04:33 UTC at Fort Knox, KY
  - Tropical positions validated to ≤0.5 arcminutes
  - Sidereal (Fagan-Bradley) positions validated
  - House cusps (Placidus) validated to ≤3 arcminutes

- **Historical Eras**:
  - 1875-1900: Uranus/Neptune discovery era
  - 1930-1950: Pluto discovery validation
  - 2000-2025: Modern high-precision era

**Location**: `tests/goldens/golden_positions.csv` with full provenance tracking

### 2. Drift Detection System

**Automated Monitoring**: Weekly GitHub Actions workflow compares Involution Engine against Swiss Ephemeris reference.

**Drift Detection Script**: `ops/drift/drift_check.py`

**Alert Thresholds**:
- **Warning**: >5% of test charts exceed tolerance → Notification
- **Critical**: >10% of test charts exceed tolerance → Deployment freeze

**Test Suite**: 100+ calculations across date range, geographic locations, and zodiac systems.

**Workflow**: `.github/workflows/drift.yml` (runs every Monday 00:00 UTC + manual trigger)

### 3. Continuous Integration Testing

**Quality Gates** (all must pass):
1. Unit tests (pytest)
2. Golden test validation
3. API contract tests (OpenAPI schema)
4. Integration tests (end-to-end)
5. Performance benchmarks (latency <200ms p95)
6. Drift detection (accuracy within tolerance)

---

## 🔬 Ephemeris Data Sources

### Primary Ephemeris: DE440 (1550-2650 CE)

**Source**: NASA JPL Development Ephemeris 440
**Coverage**: January 1, 1550 CE to December 31, 2650 CE
**Accuracy**: Sub-arcsecond for planetary positions
**Version**: DE440 (released 2021)

**Kernel Files**:
- `de440.bsp` - Planetary ephemeris
- `de440_tech-440.bsp` - Moon ephemeris (high precision)

### Extended Ephemeris: DE441 (13000 BCE - 17000 CE)

**Source**: NASA JPL Development Ephemeris 441
**Coverage**: Extended historical/future range
**Accuracy**: Slightly reduced for extreme dates
**Usage**: Automatic handoff for dates outside DE440 range

**Handoff Policy**:
```
Date < 1550 CE    → DE441
1550 CE - 2650 CE → DE440 (preferred)
Date > 2650 CE    → DE441
```

### Auxiliary Data

| Data Type | Source | Version | Purpose |
|-----------|--------|---------|---------|
| **Leap Seconds** | NAIF LSK | naif0012.tls | Time scale conversions (UTC ↔ TDB) |
| **Planetary Constants** | IAU PCK | pck00011.tpc | Physical parameters, pole orientations |
| **Earth Orientation** | JPL Earth PCK | earth_latest_high_prec.bpc | Topocentric corrections |
| **Timezone Database** | IANA TZDB | 2024.2 | Historical timezone resolution |

---

## 📊 Known Limitations

### 1. Date Range Constraints

**DE440 Optimal Range**: 1550-2650 CE
- Outside this range: Automatic DE441 fallback (slightly reduced accuracy)
- Dates before 1500 BCE: Limited validation data available
- Far-future dates (>3000 CE): Secular perturbations increase uncertainty

### 2. Topocentric Precision

**Geographic Precision**: Limited by Earth orientation model
- Modern era (1900+): Excellent topocentric accuracy
- Historical era (<1900): Earth rotation parameters less certain
- Impact: ±1-2 arcseconds for house cusps in 1800s

### 3. Ayanāṃśa Systems

**Tropical/Sidereal Offset**: Accuracy depends on ayanāṃśa formula

| System | Validation Status | Tolerance |
|--------|------------------|-----------|
| **Lahiri** | ✅ Official Indian Government formula | ≤0.1' |
| **Fagan-Bradley (Dynamic)** | ✅ Time-dependent calculation | ≤0.1' |
| **Fagan-Bradley (Fixed)** | ✅ Fixed 24.22° at 1950-01-01 | Exact |
| **Krishnamurti** | ⚠️ KP system reference | ≤0.5' |
| **B.V. Raman** | ⚠️ Classical tradition | ≤0.5' |
| **Yukteshwar** | ⚠️ Yogic astronomy | ≤0.5' |

**Note**: All ayanāṃśa systems are validated against published reference values. Sidereal longitude = Tropical longitude - Ayanāṃśa offset.

### 4. House Systems

**Topocentric House Systems**: Not all systems equally validated
- **Placidus**: Fully validated (reference: Swiss Ephemeris)
- **Koch**: Validated (reference: Swiss Ephemeris)
- **Equal**: Trivial (Ascendant + 30° increments)
- **Whole Sign**: Trivial (sign boundaries)
- **Other systems**: Use with caution, limited validation

---

## 🛡️ Accuracy Assurance Process

### Pre-Release Validation

**Before every release**:
1. ✅ All golden tests pass (20+ reference charts)
2. ✅ Drift detection shows <1% divergence from Swiss Ephemeris
3. ✅ Performance tests confirm latency <200ms p95
4. ✅ Integration tests validate end-to-end workflow
5. ✅ Manual spot-check of Fort Knox 1962 canonical case

### Continuous Monitoring

**Post-deployment**:
- Weekly drift detection runs automatically
- Alert on sustained drift (>5% charts out of tolerance for 3+ consecutive weeks)
- Kernel checksum verification on service startup
- Health check reports ephemeris version and coverage

### Version Tracking

**Provenance Logging**: Every calculation includes:
```json
{
  "metadata": {
    "ephemeris": "de440",
    "ephemeris_version": "2021-release",
    "kernel_checksums": {
      "de440.bsp": "sha256:abc123...",
      "naif0012.tls": "sha256:def456..."
    },
    "service_version": "1.1.0",
    "calculation_timestamp": "2025-10-01T21:30:00Z"
  }
}
```

---

## 🔍 Reproducing Calculations

### Kernel Checksums (v1.1.0)

To reproduce calculations exactly, use kernels with these SHA256 checksums:

```
de440.bsp                      : [To be generated on release]
de440_tech-440.bsp            : [To be generated on release]
de441.bsp                     : [To be generated on release]
naif0012.tls                  : [To be generated on release]
pck00011.tpc                  : [To be generated on release]
earth_latest_high_prec.bpc    : [To be generated on release]
```

**Download Script**: `server/scripts/download_kernels.sh` fetches verified kernels from NASA NAIF.

### Calculation Parameters

**To reproduce any historical calculation**:
1. Use exact kernel versions (checksums above)
2. Apply same topocentric correction (geodetic coordinates → ITRF93)
3. Use same aberration correction (`LT+S` - light time + stellar aberration)
4. Apply same ayanāṃśa formula (see registry: `server/app/ephemeris/ayanamsas.yaml`)
5. Verify TZDB version for historical timezone resolution (2024.2)

---

## 📞 Reporting Accuracy Issues

If you discover a calculation that exceeds the stated tolerances:

1. **Verify Reference**: Confirm Swiss Ephemeris or published ephemeris value
2. **Document Case**: Date/time (UTC), location (lat/lon/elev), zodiac system, ayanāṃśa
3. **Report Issue**: [GitHub Issues](https://github.com/eburns009/involution-engine/issues)
   - Label: `accuracy`, `drift-detected`
   - Include: Input parameters, expected vs. actual values, tolerance exceeded

**Expected Response Time**:
- Critical accuracy issues (>1° deviation): 24-48 hours
- Minor drift (within 2x tolerance): Next release cycle
- Enhancement requests: Roadmap consideration

---

## 🎯 Accuracy Roadmap

### v1.1 (Current)
- ✅ DE440/DE441 ephemeris with automatic handoff
- ✅ Weekly drift detection vs. Swiss Ephemeris
- ✅ 20+ golden test cases with provenance
- ✅ 6 ayanāṃśa systems validated

### v1.2 (Planned)
- 🔄 Expand golden dataset to 100+ reference charts
- 🔄 Add fixed stars (Yale Bright Star Catalog, mag ≤2.5)
- 🔄 Precession corrections for fixed stars
- 🔄 Additional house systems (Campanus, Regiomontanus)

### v2.0 (Future)
- 🔮 Asteroid ephemeris (Ceres, Pallas, Juno, Vesta)
- 🔮 Chiron and centaur objects
- 🔮 Hypothetical points (Lilith, Part of Fortune)
- 🔮 Lunar apogee/perigee tracking

---

## 📚 References

- [NASA NAIF SPICE Toolkit](https://naif.jpl.nasa.gov/naif/)
- [JPL Solar System Dynamics](https://ssd.jpl.nasa.gov/)
- [Swiss Ephemeris Official Documentation](https://www.astro.com/swisseph/)
- [IAU SOFA Standards](http://www.iausofa.org/)
- [IERS Earth Orientation Parameters](https://www.iers.org/IERS/EN/Home/home_node.html)

---

**Last Updated**: 2025-10-01
**Applies to**: Involution Engine v1.1.0+
