# High-Leverage Test Plan for Involution Engine v1.0.0

This document outlines the comprehensive test strategy for hardening correctness, performance, and operational resilience.

---

## Test Categories

### 1. Numerical Correctness & Ephemeris Edge Cases ✅

**File**: `tests/test_ephemeris_edge_cases.py`

**Coverage**:
- DE440 ⇄ DE441 handoff boundaries (±1, ±7, ±30 days)
- Continuity validation (Δlon < 0.1' planets, < 10' Moon)
- Kernel integrity checks (checksums, corruption handling)
- Extreme date ranges (1400 CE - 3000 CE)
- Moon high-precision at perigee/apogee
- Ecliptic latitude bounds validation

**Run**: `pytest tests/test_ephemeris_edge_cases.py -v`

---

### 2. Ayanāṃśa Invariants & Property-Based Testing ✅

**File**: `tests/test_ayanamsa_properties.py`

**Coverage**:
- Property: Sidereal = Tropical - Ayanāṃśa (within 1')
- Property: Ayanāṃśa increases over time (precession)
- Property: Fagan-Bradley Fixed is constant
- Property: Longitude periodicity sanity checks
- Property: Longitude wraparound normalization

**Uses**: Hypothesis for generative testing (50+ examples per property)

**Run**: `pytest tests/test_ayanamsa_properties.py -v`

---

### 3. Ayanāṃśa Accuracy Validation ✅

**File**: `tests/test_ayanamsa_accuracy.py`

**Coverage**:
- Reference value validation (18 test cases vs Swiss Ephemeris)
- Tolerances: Lahiri/Fagan-Bradley ≤0.1', others ≤0.5'
- Time progression tests
- Registry completeness
- Invalid system error handling

**Run**: `pytest tests/test_ayanamsa_accuracy.py -v`

---

### 4. Performance Benchmarks ✅

**File**: `tests/test_performance_benchmarks.py`

**Performance Budgets** (p95):
- /v1/positions (Sun+Moon): ≤150ms
- /v1/positions (all 10 bodies): ≤250ms
- Cache hit: ≤50ms
- /healthz: ≤20ms

**Coverage**:
- Minimal bodies benchmark
- All bodies benchmark
- Cache hit performance
- Concurrent load (10 threads)
- Sidereal calculation overhead

**Run**: `pytest tests/test_performance_benchmarks.py --benchmark-only`

**CI Integration**:
```bash
pytest --benchmark-autosave --benchmark-json=output.json
# Fail CI if p95 regresses by >20% vs baseline
```

---

### 5. Monitoring & Observability ✅

**File**: `tests/test_monitoring_observability.py`

**Required Metrics**:
- `http_requests_total{method, endpoint, status}`
- `http_request_duration_seconds` (histogram)
- `involution_positions_calculated_total`
- `involution_cache_operations_total`
- `involution_cache_hit_rate` (gauge, [0.0-1.0])
- `involution_worker_pool_size`
- `involution_worker_pool_queue_size`

**Healthz Validation**:
- Kernel status (de440/de441 with checksums)
- Cache backend status
- Worker pool queue depth
- System metadata (version, uptime, timestamp)

**Run**: `pytest tests/test_monitoring_observability.py -v`

---

## Test Execution Guide

### Local Development

```bash
# Install test dependencies
pip install -r tests/requirements-test.txt

# Run all tests
pytest tests/ -v

# Run specific test category
pytest tests/test_ephemeris_edge_cases.py -v

# Run with coverage
pytest tests/ --cov=server --cov-report=html

# Run benchmarks
pytest tests/test_performance_benchmarks.py --benchmark-only

# Run property-based tests with more examples
pytest tests/test_ayanamsa_properties.py -v --hypothesis-profile=ci
```

### CI/CD Integration

```yaml
# .github/workflows/comprehensive-ci.yml

jobs:
  test-accuracy:
    runs-on: ubuntu-latest
    steps:
      - name: Run numerical correctness tests
        run: pytest tests/test_ephemeris_edge_cases.py -v

      - name: Run ayanamsa validation
        run: pytest tests/test_ayanamsa_accuracy.py -v

      - name: Run property-based tests
        run: pytest tests/test_ayanamsa_properties.py -v

  test-performance:
    runs-on: ubuntu-latest
    steps:
      - name: Benchmark performance
        run: |
          pytest tests/test_performance_benchmarks.py \
            --benchmark-only \
            --benchmark-autosave \
            --benchmark-json=bench_output.json

      - name: Check performance budgets
        run: |
          python scripts/check_performance_budgets.py bench_output.json

  test-observability:
    runs-on: ubuntu-latest
    steps:
      - name: Validate metrics
        run: pytest tests/test_monitoring_observability.py -v
```

---

## Additional Test Categories (Future)

### API Contract Testing (with schemathesis)

```python
import schemathesis

schema = schemathesis.from_uri("http://localhost:8080/openapi.json")

@schema.parametrize()
def test_api_contract(case):
    case.call_and_validate()
```

**Run**: `schemathesis run http://localhost:8080/openapi.json`

---

### Time & Timezone Robustness

**Golden cases**:
- US "War Time" (NYC 1942-45)
- Dublin wartime BST
- Newfoundland UTC-03:30 pre-confederation
- Asia/Calcutta pre-1945
- Australia Lord Howe (30-minute DST)
- DST boundary times (fold hours)

**File**: `tests/test_time_resolver_edge_cases.py` (TODO)

---

### Concurrency & Chaos Testing

**Tests**:
- 100-500 concurrent requests (no deadlocks)
- Kill SPICE worker mid-load (pool shrinks gracefully)
- Redis outage (fallback to in-process cache)
- Corrupted kernel file (graceful error)

**File**: `tests/test_chaos_resilience.py` (TODO)

---

### Fixed Stars (Feature-Flagged)

**Tests**:
- Catalog integrity (mag cutoff, required columns)
- Ecliptic conversion sanity (Spica, Regulus, Aldebaran, Antares)
- Performance: <100ms for mag ≤2.5 catalog

**File**: `tests/test_fixed_stars.py` (TODO)

---

### Examples-as-Tests

**Validate all examples in `examples/http/`**:

```python
import subprocess
import json

def test_example_fort_knox_request():
    result = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'http://localhost:8080/v1/positions',
        '-H', 'Content-Type: application/json',
        '-d', '@examples/http/fort-knox-request.json'
    ], capture_output=True, text=True)

    data = json.loads(result.stdout)
    assert "bodies" in data
    assert "Sun" in data["bodies"]
```

**File**: `tests/test_examples_executable.py` (TODO)

---

## Performance Thresholds (CI Gates)

| Metric | Budget (p95) | Critical Threshold |
|--------|--------------|-------------------|
| /v1/positions (Sun+Moon) | ≤150ms | >200ms (fail) |
| /v1/positions (10 bodies) | ≤250ms | >350ms (fail) |
| Cache hit | ≤50ms | >100ms (fail) |
| /healthz | ≤20ms | >50ms (fail) |
| Concurrent load (10 threads) | <1% error rate | >5% (fail) |

---

## Accuracy Thresholds (CI Gates)

| Body Type | Longitude Tolerance | Critical Threshold |
|-----------|---------------------|-------------------|
| Planets | ≤1' (60") | >2' (fail) |
| Moon | ≤30' (1800") | >60' (fail) |
| Nodes | ≤5' (300") | >10' (fail) |
| Drift (p95 across grid) | ≤0.8' | >1.5' (fail) |

---

## Test Tooling

### Installed

- ✅ **pytest** - Core testing framework
- ✅ **hypothesis** - Property-based testing
- ✅ **pytest-benchmark** - Performance benchmarking
- ✅ **requests** - HTTP client for API tests

### Recommended (Install as Needed)

- **schemathesis** - OpenAPI contract fuzzing
- **locust** or **k6** - Load testing
- **pytest-xdist** - Parallel test execution
- **pytest-timeout** - Timeout protection
- **pytest-html** - HTML test reports

---

## Running Complete Test Suite

```bash
# Full suite with coverage and benchmarks
pytest tests/ \
  --cov=server \
  --cov-report=html \
  --cov-report=term \
  --benchmark-skip \
  -v \
  --tb=short

# Benchmarks separately
pytest tests/test_performance_benchmarks.py --benchmark-only

# Property-based with extended examples
pytest tests/test_ayanamsa_properties.py --hypothesis-seed=random -v

# Parallel execution (faster)
pytest tests/ -n auto --dist loadfile
```

---

## Test Metrics & Goals

**Current Coverage**:
- ✅ Numerical correctness (ephemeris handoff, kernel integrity)
- ✅ Ayanāṃśa accuracy (reference values + properties)
- ✅ Performance benchmarks (with budgets)
- ✅ Monitoring/observability (metrics + healthz)

**Target v1.0.0**:
- Code coverage: >80%
- Golden test pass rate: 100%
- Performance budget compliance: 100%
- Property-based tests: >500 examples passing

**Future Enhancements**:
- API contract fuzzing (schemathesis)
- Time resolver edge cases
- Chaos/resilience testing
- Load testing (k6/locust)
- Examples-as-tests automation

---

## Contact

For questions about testing strategy or adding new test categories, see:
- Test strategy: This document
- CI/CD workflows: `.github/workflows/comprehensive-ci.yml`
- Audit report: Issue #8
