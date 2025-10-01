# Batch Testing Harness

Comprehensive testing framework for validating planetary position calculations against reference implementations.

## Overview

The batch testing harness provides tools for:
- Computing planetary positions in bulk
- Comparing results against reference data
- Generating accuracy reports and metrics
- Validating against Swiss Ephemeris and Astro.com

## Directory Structure

```
tests/batch/
├── README.md                    # This file
├── templates/                   # Template files for new test cases
│   ├── charts_input_skeleton.csv    # Input template with documentation
│   └── reference_skeleton.csv       # Reference data template
├── reference_data/              # Reference position data
│   ├── reference.csv                # Main reference dataset
│   └── reference_prefilled_with_utc.csv  # UTC-filled reference data
├── results/                     # Test execution results
│   ├── out/                         # Standard batch results
│   ├── out_metrics/                 # Performance metrics
│   └── out_small/                   # Small test results
├── scripts/                     # Legacy scripts (to be organized)
├── accuracy_compare.py          # Main comparison tool
├── batch_compute_positions.py   # Bulk position calculator
├── batch_compute_positions_metrics.py  # Performance benchmarking
└── populate_reference_utc.py    # UTC timestamp population tool
```

## Core Tools

### 1. Batch Position Calculator

Calculate planetary positions for multiple charts:

```bash
python tests/batch/batch_compute_positions.py \
  --input tests/batch/templates/charts_input_skeleton.csv \
  --output tests/batch/results/positions.csv \
  --engine_base http://localhost:8000
```

**Input Format** (`charts_input.csv`):
```csv
name,local_datetime,place_name,lat,lon,systems,ayanamsha_id,ayanamsha_value
fort_knox,1962-07-02T23:33:00,Fort Knox KY,37.840347,-85.949127,"tropical,sidereal_fb",FAGAN_BRADLEY_FIXED,24:13:00
```

**Output Format** (`positions.csv`):
```csv
name,system,utc,body,lon_deg,lat_deg,distance_au
fort_knox,tropical,1962-07-03T04:33:00Z,Sun,100.779070,-0.0001,1.0160
```

### 2. Accuracy Comparison

Compare engine results against reference data:

```bash
python tests/batch/accuracy_compare.py \
  --engine results/engine_positions.csv \
  --reference reference_data/reference.csv \
  --out_csv results/accuracy_report.csv \
  --out_json results/accuracy_summary.json \
  --tol_planets_arcmin 1.0 \
  --tol_moon_arcmin 30.0 \
  --tol_nodes_arcmin 5.0
```

**Accuracy Report** (`accuracy_report.csv`):
```csv
name,system,body,engine_lon,reference_lon,difference_arcmin,tolerance_arcmin,pass
fort_knox,tropical,Sun,100.779070,100.779000,0.252,36.0,PASS
```

**Summary Statistics** (`accuracy_summary.json`):
```json
{
  "total_comparisons": 70,
  "total_pass": 70,
  "pass_rate_percent": 100.0,
  "worst_case_arcmin": 0.5,
  "average_error_arcmin": 0.1
}
```

### 3. Performance Metrics

Benchmark calculation performance:

```bash
python tests/batch/batch_compute_positions_metrics.py \
  --input tests/batch/templates/charts_input_skeleton.csv \
  --output tests/batch/results/metrics.json \
  --engine_base http://localhost:8000
```

## Tolerance Standards

### Planetary Positions
- **Major Planets**: ±1.0 arcminute (±0.017°)
- **Moon**: ±30.0 arcminutes (±0.5°) due to rapid motion
- **Lunar Nodes**: ±5.0 arcminutes (±0.083°)

### Angular Distance Calculation
Uses shortest path along great circle:
```python
def angular_distance(lon1, lon2):
    diff = abs(lon1 - lon2)
    if diff > 180:
        diff = 360 - diff
    return diff * 60  # Convert to arcminutes
```

## Quality Gates

### CI/CD Integration
```bash
# Run accuracy validation in CI
python tests/batch/accuracy_compare.py \
  --engine $ENGINE_RESULTS \
  --reference tests/batch/reference_data/reference.csv \
  --out_json accuracy_results.json

# Fail build if accuracy below 100%
PASS_RATE=$(jq -r '.pass_rate_percent' accuracy_results.json)
if [ "${PASS_RATE}" != "100.0" ]; then
  echo "FAIL: Accuracy test failed with ${PASS_RATE}% pass rate"
  exit 1
fi
```

### Performance Thresholds
- **Response Time**: <500ms per chart (p95)
- **Accuracy**: 100% pass rate required
- **Reliability**: No SPICE calculation failures

## Test Data Management

### Creating New Test Cases

1. **Add to Input Template**:
```csv
new_test,2025-01-15T12:00:00,New York NY,40.7128,-74.0060,"tropical,sidereal_lahiri",LAHIRI,24:05:30
```

2. **Generate Reference Data**:
- Use Swiss Ephemeris, Astro.com, or other trusted source
- Add to `reference_data/reference.csv`
- Ensure UTC timestamps match exactly

3. **Validate**:
```bash
python tests/batch/batch_compute_positions.py --input new_test.csv --output engine_results.csv
python tests/batch/accuracy_compare.py --engine engine_results.csv --reference reference.csv --out_json results.json
```

The batch testing harness ensures Involution Engine maintains research-grade accuracy through systematic validation and continuous monitoring.