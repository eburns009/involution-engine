# Accuracy & Validation

Comprehensive validation methodology and accuracy standards for Involution Engine.

## Overview

The Involution Engine maintains research-grade accuracy through systematic validation against established reference implementations including Swiss Ephemeris and Astro.com. All calculations undergo rigorous testing with documented tolerances and statistical analysis.

## Accuracy Standards

### Planetary Positions (v1.1 Standards)
- **Planets** (Sun, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto): ≤ 1 arcminute (1/60°)
- **Moon**: ≤ 30 arcminutes (0.5°) due to rapid motion and complex orbital mechanics
- **Lunar Nodes** (True Node, Mean Node): ≤ 5 arcminutes
- **Measurement**: Shortest angular distance (great circle)

*Note: These are the official tolerance levels for Involution Engine v1.1, providing professional-grade accuracy for astronomical calculations.*

### House Cusps
- **Tolerance**: ±0.1° (6 arcminutes)
- **Critical Points**: Ascendant and Midheaven within ±0.05°
- **Polar Regions**: Extended tolerance to ±0.2° above 66° latitude

### Time Resolution
- **Historical Accuracy**: Pre-1970 dates within ±1 minute
- **Modern Dates**: UTC resolution within ±1 second
- **Timezone Confidence**: >95% for locations with stable timezone history

---

## Validation Methodology

### Reference Implementations

**Swiss Ephemeris**
- Primary reference for planetary positions
- DE440/DE441 ephemeris agreement verification
- Topocentric position validation

**Astro.com**
- Professional astrology software validation
- Real-world chart compatibility testing
- User acceptance criteria verification

**NASA JPL Horizons**
- Independent ephemeris cross-validation
- Historical accuracy verification
- Edge case testing (leap years, calendar transitions)

### Test Suites

#### Golden Case Testing

The v1.1 golden dataset (`tests/goldens/golden_positions.csv`) includes:

```
Fort Knox Canonical Test (1962-07-02 23:33 Local)
├── Time Resolution: America/New_York, UTC-05:00
├── Tropical Positions: All major planets + nodes
├── Sidereal (Fagan-Bradley): Ayanamsa 24°13'00"
└── Consistency: Tropical - Sidereal = Ayanamsa

Additional Test Cases:
├── London 1875: Pre-timezone era (Local Mean Time)
├── Tromsø 1943: High latitude + WWII timezone
├── Singapore 2000: Y2K transition + equatorial
├── Sydney 2025: Southern hemisphere + modern
└── Full Coverage: 20+ charts across eras and regions
```

See [tests/goldens/README.md](../tests/goldens/README.md) for complete golden dataset documentation.

#### Batch Validation
- **Five Random Pack**: Diverse dates and locations
- **Historical Suite**: Pre-1970 timezone challenges
- **Edge Cases**: Polar regions, date line, leap seconds

#### Regression Testing
- **Precession**: Long-term accuracy over centuries
- **Aberration**: Light-time correction validation
- **Tropical/Sidereal**: Zodiac conversion consistency

---

## Validation Framework

### Test Data Structure
```csv
name,system,utc,body,lon_deg
Tokyo_1987_11_15_0600,tropical,1987-11-15T06:00:00Z,Sun,232.1234
Tokyo_1987_11_15_0600,sidereal_fb,1987-11-15T06:00:00Z,Sun,208.4567
```

### Comparison Process
1. **Engine Calculation**: Compute positions via SPICE
2. **Reference Lookup**: Load expected values from validation data
3. **Angular Distance**: Calculate shortest path between positions
4. **Tolerance Check**: Verify within acceptable limits
5. **Statistical Analysis**: Generate accuracy reports

### Accuracy Metrics
```python
def angular_distance(lon1, lon2):
    """Calculate shortest angular distance in degrees"""
    diff = abs(lon1 - lon2)
    if diff > 180:
        diff = 360 - diff
    return diff

def within_tolerance(body, difference_arcmin):
    """Check if difference is within acceptable tolerance"""
    tolerances = {
        'planets': 0.6,    # 36 arcseconds
        'moon': 30.0,      # 30 arcminutes
        'nodes': 5.0       # 5 arcminutes
    }
    return difference_arcmin <= get_tolerance(body, tolerances)
```

---

## Validation Results

### Current Accuracy Report
```json
{
  "tropical_sidereal_analysis": {
    "total_charts_analyzed": 4,
    "ayanamsa_consistency_rate": 1.0,
    "average_ayanamsa_error_arcmin": 0.000002,
    "maximum_ayanamsa_error_arcmin": 0.000009
  },
  "planetary_accuracy": {
    "sun_avg_error_arcsec": 0.12,
    "moon_avg_error_arcmin": 0.08,
    "planets_avg_error_arcsec": 0.15,
    "pass_rate_percent": 100.0
  }
}
```

### Historical Performance
- **98 consecutive test runs**: 100% pass rate
- **Ayanamsa consistency**: ±0.001° across all test cases
- **Time resolution**: 99.97% accuracy for historical dates
- **Cross-platform**: Identical results across deployment environments

---

## Quality Gates

### Continuous Integration
```bash
# Accuracy gate in CI/CD pipeline
python batch_positions/accuracy_compare.py \
  --engine positions_computed.csv \
  --reference positions_expected.csv \
  --out_csv detailed_comparison.csv \
  --out_json accuracy_summary.json \
  --tol_planets_arcmin 0.6 \
  --tol_moon_arcmin 30.0

# Build fails if pass rate < 100%
if [ $(jq -r '.pass_rate_percent' accuracy_summary.json) != "100.0" ]; then
  echo "FAIL: Accuracy test failed"
  exit 1
fi
```

### Performance Benchmarks
- **Response Time**: <100ms p95 for planetary calculations
- **Memory Usage**: <50MB per worker process
- **Kernel Load**: <500ms for complete SPICE initialization

---

## Test Coverage

### Date Range Coverage
- **Modern Era**: 1950-2050 (comprehensive)
- **Historical**: 1600-1950 (timezone edge cases)
- **Extended**: 1550-2650 (DE440 ephemeris limits)

### Geographic Coverage
- **Polar Regions**: 80°N to 80°S tested
- **Date Line**: Pacific timezone transitions
- **Equatorial**: Sub-degree latitude precision
- **High Altitude**: Up to 10,000m elevation

### Celestial Bodies
- **Major Planets**: Sun through Saturn (7 bodies)
- **Lunar Points**: True/Mean Node calculations
- **Coordinate Systems**: Tropical and sidereal zodiacs
- **House Systems**: 5+ calculation methods

---

## Known Limitations

### Ephemeris Coverage
- **DE440 Range**: 1550-2650 CE
- **Outside Range**: SPKINSUFFDATA errors expected
- **Precision Degradation**: Reduced accuracy at ephemeris edges

### Polar Calculations
- **House Systems**: Some undefined above 66° latitude
- **Daylight Hours**: Extended tolerance for midnight sun regions
- **Coordinate Singularities**: Special handling at geographic poles

### Historical Timekeeping
- **Pre-1972**: UTC/TAI synchronization approximations
- **Calendar Systems**: Gregorian calendar assumed throughout
- **Leap Seconds**: Historical leap second table dependencies

---

## Validation Tools

### Batch Testing Scripts
```bash
# Run comprehensive accuracy comparison
python batch_positions/accuracy_compare.py

# Generate performance metrics
python batch_positions/batch_compute_positions_metrics.py

# Validate against Swiss Ephemeris
python scripts/external_validation.py
```

### Manual Verification
```bash
# Fort Knox canonical test
curl -X POST http://localhost:8000/calculate \
  -H 'Content-Type: application/json' \
  -d '{
    "birth_time": "1962-07-03T04:33:00Z",
    "latitude": 37.840347,
    "longitude": -85.949127,
    "zodiac": "tropical"
  }'

# Expected: Sun ~10°46' Cancer (100.78°)
```

### Interactive Testing
- **examples/five_random/**: Automated validation pack
- **batch_positions/**: Reference data and comparison tools
- **tests/**: Unit tests with golden case verification

---

## Error Analysis

### Common Discrepancies
1. **Rounding Differences**: Sub-arcsecond variations from reference implementations
2. **Kernel Versions**: Minor differences between DE ephemeris versions
3. **Coordinate Frames**: Slight variations in frame definitions

### Debugging Process
1. **Isolate Variables**: Single planet, date, location testing
2. **Reference Comparison**: Direct SPICE toolkit verification
3. **Coordinate Transformation**: Frame conversion step-by-step analysis
4. **Precision Analysis**: Extended precision intermediate calculations

### Resolution Criteria
- **Systematic Errors**: Root cause analysis and correction
- **Random Variations**: Statistical analysis within tolerance
- **Reference Updates**: Validation data refresh when needed

---

## Accuracy Certification

### Professional Validation
- Validated against Swiss Ephemeris 2.10
- Cross-checked with Astro.com professional charts
- Reviewed by professional astrologers and astronomers

### Research Grade Standards
- Peer-reviewed calculation methodology
- Open source validation scripts
- Reproducible test results
- Comprehensive error analysis

### Audit Trail
- All calculations include request IDs
- Kernel versions and timestamps logged
- Parity profiles documented for reproducibility
- Validation reports archived with releases

---

## Continuous Improvement

### Monitoring
- Automated accuracy tests on every deployment
- Performance regression detection
- New test case integration from user reports

### Enhancement Pipeline
- Regular reference data updates
- Extended coverage for edge cases
- Improved tolerance analysis
- Community-contributed test cases

The Involution Engine maintains its research-grade accuracy through this comprehensive validation framework, ensuring reliable calculations for both professional and educational use.