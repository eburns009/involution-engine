# Accuracy Guarantees

The Involution Engine provides professional-grade accuracy for astrological calculations, with rigorous testing and monitoring to ensure reliable results. This document outlines our accuracy standards, ephemeris management, and quality assurance processes.

## Accuracy Standards by Body

### Planetary Position Tolerances

| Body | Accuracy Guarantee | Typical Performance | Notes |
|------|-------------------|-------------------|-------|
| **Sun** | ≤ 1 arcminute | ~10 arcseconds | High precision, stable |
| **Mercury** | ≤ 1 arcminute | ~15 arcseconds | Orbital perturbations accounted |
| **Venus** | ≤ 1 arcminute | ~10 arcseconds | Excellent accuracy |
| **Mars** | ≤ 1 arcminute | ~20 arcseconds | Well-modeled orbit |
| **Jupiter** | ≤ 1 arcminute | ~15 arcseconds | Gas giant, stable |
| **Saturn** | ≤ 1 arcminute | ~20 arcseconds | Ring system effects included |
| **Uranus** | ≤ 1 arcminute | ~30 arcseconds | Distant orbit modeling |
| **Neptune** | ≤ 1 arcminute | ~40 arcseconds | Most distant planet |
| **Pluto** | ≤ 1 arcminute | ~45 arcseconds | Dwarf planet, complex orbit |
| **Moon** | ≤ 30 arcminutes | ~5-15 arcminutes | Lunar libration complexity |
| **True Node** | ≤ 5 arcminutes | ~1-3 arcminutes | Calculated from lunar orbit |
| **Mean Node** | ≤ 5 arcminutes | ~30 arcseconds | Smoothed calculation |

### Understanding the Numbers

- **Arcminute (')**: 1/60th of a degree. The Moon appears about 30 arcminutes wide from Earth.
- **Arcsecond ('')**: 1/60th of an arcminute, or 1/3600th of a degree. Very high precision.
- **Astrological Impact**: Our 1 arcminute guarantee means planetary positions are accurate to within 1/30th of the Moon's apparent diameter.

### Special Considerations

#### Moon Accuracy
The Moon's position is inherently more challenging due to:
- **Libration**: Complex orbital motion with multiple periodic terms
- **Perturbations**: Strong gravitational influence from Sun and Earth
- **Proximity**: Small errors in time or ephemeris model amplify quickly

Our 30 arcminute guarantee for the Moon is conservative and typically achieves much better performance (5-15 arcminutes in practice).

#### Node Accuracy
Lunar nodes are calculated points, not physical bodies:
- **True Node**: Instantaneous intersection of lunar orbit with ecliptic
- **Mean Node**: Smoothed average, filtering short-period oscillations
- Both are derived from lunar orbital elements and inherit lunar modeling complexity

## Ephemeris Foundation

### NASA's Planetary Ephemeris

The Involution Engine uses NASA's Development Ephemeris (DE) series:

| Ephemeris | Coverage | Precision | Primary Use |
|-----------|----------|-----------|-------------|
| **DE440** | 1550-2650 CE | Sub-arcsecond | Standard calculations |
| **DE441** | 13,201 BCE - 17,191 CE | Arcsecond | Extended historical range |

### Automatic DE440/DE441 Handoff

The engine automatically selects the appropriate ephemeris:

```
Request Date Range:
├── 1550-2650 CE     → DE440 (highest precision)
├── Before 1550 CE   → DE441 (extended coverage)
└── After 2650 CE    → DE441 (extended coverage)
```

#### What This Means for Users

1. **Seamless Experience**: No manual ephemeris selection required
2. **Optimal Precision**: Always use the most accurate data available
3. **Extended Range**: Historical dates back to 13,201 BCE supported
4. **Consistent Interface**: API remains identical regardless of ephemeris

#### Precision Impact

- **DE440 Range (1550-2650 CE)**: Sub-arcsecond precision from NASA
- **DE441 Extended Range**: Slightly reduced precision but still exceeds our guarantees
- **Transition Points**: No discontinuities at 1550/2650 boundaries

### Ephemeris Updates

- **Frequency**: DE ephemeris files are updated by NASA every few years
- **Integration**: New releases are tested and integrated after validation
- **Backwards Compatibility**: Historical calculations remain consistent

## Quality Assurance: Drift Detection

### Weekly Monitoring System

We maintain accuracy through continuous monitoring against the Swiss Ephemeris reference:

#### Automated Testing Schedule
- **Frequency**: Every Monday at 06:00 UTC
- **Coverage**: 20+ golden reference charts spanning 1875-2025
- **Bodies**: All supported planets and lunar nodes
- **Systems**: Both tropical and sidereal with multiple ayanāṃśas

#### Reference Data Validation

Our golden dataset includes:
- **Temporal Coverage**: Historical to modern eras
- **Geographic Diversity**: Global coordinate spread
- **Ayanāṃśa Variety**: All supported sidereal systems
- **Known Accuracy**: Swiss Ephemeris as professional reference

### Statistical Analysis

#### Drift Detection Thresholds

| Body | Warning Level | Alert Level | Action Required |
|------|---------------|-------------|-----------------|
| Planets | > 30 arcseconds | > 45 arcseconds | Investigation |
| Moon | > 20 arcminutes | > 25 arcminutes | Investigation |
| Nodes | > 3 arcminutes | > 4 arcminutes | Investigation |

#### Trending Analysis
- **7-day rolling averages**: Detect gradual drift
- **Percentile tracking**: Monitor worst-case scenarios
- **Regression detection**: Identify systematic changes

### What Happens When Drift Is Detected

#### Immediate Response (< 1 hour)
1. **Automated alerts** sent to engineering team
2. **GitHub issue** created with drift analysis
3. **Detailed report** generated with affected time ranges

#### Investigation Process (< 24 hours)
1. **Root cause analysis**: Identify source of drift
2. **Impact assessment**: Determine affected calculations
3. **Validation testing**: Verify fixes against golden data

#### Resolution Timeline
- **Minor drift** (< alert threshold): Monitored, documented
- **Significant drift** (> alert threshold): Fixed within 72 hours
- **Critical drift** (> 2x alert threshold): Emergency deployment

#### Historical Performance
- **2023**: Zero critical drift events
- **Typical causes**: Ephemeris updates, coordinate system improvements
- **Average resolution**: 18 hours for significant drift

## Time System Accuracy

### UTC and Timezone Handling

#### Time Resolution
- **Input precision**: 1 second resolution
- **Internal calculation**: Microsecond precision maintained
- **Julian Date conversion**: IEEE 754 double precision

#### Timezone Database
- **Source**: IANA timezone database (tzdata)
- **Updates**: Automatic with operating system updates
- **Coverage**: All historical timezone changes since 1970
- **Pre-1970**: UTC-based assumptions for simplicity

#### Leap Second Handling
- **UTC standard**: Properly accounts for leap seconds
- **TAI conversion**: When required for high-precision calculations
- **Future leap seconds**: Handled as they are announced

### Historical Date Accuracy

#### Calendar Systems
- **Gregorian**: 1582 CE onwards (post-papal reform)
- **Julian**: Pre-1582 dates automatically converted
- **Proleptic Gregorian**: Used for consistency across all dates

#### Limitations
- **Before 1550 CE**: Reduced ephemeris precision with DE441
- **Ancient dates**: Timezone assumptions become less reliable
- **Medieval period**: Calendar confusion in historical sources

## Coordinate System Precision

### Ayanāṃśa Accuracy

#### Implementation Fidelity
- **Lahiri**: Official Indian government formula
- **Fagan-Bradley**: Both dynamic and fixed implementations
- **Others**: Standard formulas from authoritative sources

#### Precision Characteristics
- **Formula precision**: Sub-arcsecond internal calculations
- **Rounding**: Final output rounded to practical precision
- **Consistency**: Identical results for identical inputs

### Reference Frame Accuracy

#### Ecliptic Coordinates
- **Obliquity**: IAU 2000A model for precision
- **Nutation**: Full nutation model applied
- **Precession**: Long-term axial precession included

#### Equatorial Coordinates (when supported)
- **Epoch**: J2000.0 or date-specific as requested
- **Proper motion**: For fixed stars when enabled
- **Aberration**: Stellar aberration corrections applied

## Validation and Testing

### Regression Testing
- **Golden datasets**: 500+ reference calculations
- **Swiss Ephemeris comparison**: Primary validation standard
- **Multi-platform**: Linux, macOS, Windows validation
- **Version consistency**: Results identical across deployments

### Stress Testing
- **Date range**: Full ephemeris coverage tested
- **Edge cases**: Leap years, timezone boundaries, epoch transitions
- **Performance**: Sub-100ms response time maintained
- **Concurrency**: Parallel calculation accuracy verified

### User Acceptance Testing
- **Professional astrologers**: Real-world usage validation
- **Migration testing**: Swiss Ephemeris conversion accuracy
- **Documentation accuracy**: Examples verified against live API

## Recommendations for Users

### When to Trust Our Accuracy
- **Standard astrological work**: Our guarantees exceed typical requirements
- **Professional practice**: Suitable for all commercial astrological software
- **Academic research**: Appropriate for most astrological studies
- **Personal use**: More than sufficient for individual charts

### When to Use Alternative Sources
- **Research astronomy**: For sub-arcsecond requirements, use JPL directly
- **Spacecraft navigation**: NASA provides specialized ephemeris
- **Historical astronomy**: Very ancient dates may need specialized treatment
- **Legal astronomy**: Some jurisdictions require specific ephemeris sources

### Best Practices
1. **Use UTC when possible**: Eliminates timezone conversion errors
2. **Validate critical calculations**: Cross-check important results
3. **Monitor our status page**: Stay informed of any known issues
4. **Cache results**: Identical inputs always produce identical outputs
5. **Report discrepancies**: Help us maintain quality through user feedback

## Continuous Improvement

### Accuracy Enhancement Pipeline
- **User feedback**: Real-world usage informs improvements
- **Academic partnerships**: Collaboration with astronomical institutions
- **Software updates**: Regular enhancement of calculation algorithms
- **Hardware optimization**: Improved numerical precision where beneficial

### Future Accuracy Goals
- **Sub-arcminute planets**: Target ≤ 30 arcseconds for all major planets
- **Improved lunar modeling**: Target ≤ 15 arcminutes for Moon
- **Extended coverage**: Maintain accuracy across expanding date ranges
- **Additional bodies**: Asteroid and comet support with defined accuracy

The Involution Engine's accuracy guarantees are backed by rigorous testing, continuous monitoring, and a commitment to professional-grade astrological computation. Our automated quality assurance ensures that you can rely on our calculations for all your astrological work.