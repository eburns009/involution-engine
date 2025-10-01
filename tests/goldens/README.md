# Golden Test Data

This directory contains reference astronomical data used for accuracy validation and regression testing.

## Contents

- `golden_positions.csv` - Primary golden dataset with planetary positions
- `reference_sources.md` - Detailed provenance for all reference values
- `regeneration_guide.md` - Instructions for updating golden data

## Data Format

The golden positions CSV follows this schema:

```csv
name,system,utc,body,lon_deg,source,source_version,ayanamsha_id,tzdb_version,patch_version,notes
```

### Field Descriptions

- **name**: Descriptive name for the test case (typically person/place)
- **system**: Zodiac system (`tropical` or `sidereal_fb` for Fagan-Bradley)
- **utc**: UTC timestamp in ISO format
- **body**: Celestial body name
- **lon_deg**: Longitude in decimal degrees
- **source**: Reference source (e.g., "Astro.com", "Swiss Ephemeris")
- **source_version**: Version/date of source software
- **ayanamsha_id**: Ayanāṃśa used (for sidereal calculations)
- **tzdb_version**: Timezone database version used
- **patch_version**: Internal patch/commit identifier
- **notes**: Additional context or special conditions

## Test Cases Coverage

The golden dataset includes:

### Time Periods
- **Pre-1884**: Before standard timezones (Local Mean Time era)
- **WWII Era**: 1940s with wartime timezone adjustments
- **1960s**: Mid-20th century baseline period
- **2000s**: Modern era with current timezone rules
- **2025**: Contemporary calculations

### Geographic Coverage
- **High Latitude**: Northern locations (>60°N) for extreme timezone cases
- **Equatorial**: Near-equator locations
- **Southern Hemisphere**: Cross-hemisphere validation
- **International Date Line**: Pacific timezone edge cases

### Bodies Coverage
All calculations include:
- **Classical Planets**: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn
- **Modern Planets**: Uranus, Neptune, Pluto
- **Lunar Nodes**: True Node, Mean Node

## Accuracy Tolerances

Acceptable deviations from reference sources:

| Body Type | Tolerance |
|-----------|-----------|
| Planets (except Moon) | ≤ 1 arcminute (1/60 degree) |
| Moon | ≤ 30 arcminutes (0.5 degree) |
| Lunar Nodes | ≤ 5 arcminutes |

## Data Regeneration

To update golden data:

1. Verify reference sources are current
2. Run comparison scripts against multiple ephemeris sources
3. Document any discrepancies exceeding tolerances
4. Update provenance fields with new versions
5. Commit with detailed change description

See `regeneration_guide.md` for detailed procedures.

## Quality Assurance

Before accepting new golden data:

1. Cross-validate against at least 2 independent sources
2. Verify timezone resolution is consistent
3. Check ephemeris range coverage (1550-2650 for DE440)
4. Validate ayanāṃśa calculations for sidereal positions
5. Test edge cases (leap years, DST transitions, etc.)

## Usage in Tests

Golden data is used by:

- **Accuracy Tests**: Validate positions against known-good values
- **Regression Tests**: Ensure changes don't affect historical accuracy
- **Integration Tests**: End-to-end API response validation
- **Performance Benchmarks**: Consistent test cases for timing

## References

See `reference_sources.md` for complete citation and provenance information for all golden values.