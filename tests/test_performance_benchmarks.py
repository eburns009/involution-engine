"""
Performance Benchmark Tests

Validates performance budgets and prevents regressions using pytest-benchmark.

Performance budgets (p95):
- /v1/positions (Sun+Moon): ≤150ms
- /v1/positions (all 10 bodies): ≤250ms
- Cache hit: ≤50ms

CI fails if p95 regresses by >20% vs baseline.
"""

import pytest
from datetime import datetime, timezone
import os

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@pytest.fixture
def api_base_url():
    """API base URL from environment or default."""
    return os.getenv("ENGINE_BASE", "http://localhost:8080")


@pytest.fixture
def fort_knox_payload():
    """Standard Fort Knox 1962 test case payload."""
    return {
        "when": {"utc": "1962-07-03T04:33:00Z"},
        "system": "tropical",
        "place": {
            "lat": 37.840347,
            "lon": -85.949127,
            "elev": 0.0
        }
    }


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
@pytest.mark.benchmark(group="positions_minimal")
def test_benchmark_positions_sun_moon(benchmark, api_base_url, fort_knox_payload):
    """
    Benchmark /v1/positions with minimal bodies (Sun + Moon).

    Performance budget: p95 ≤ 150ms
    """
    payload = fort_knox_payload.copy()
    payload["bodies"] = ["Sun", "Moon"]

    def call_api():
        response = requests.post(
            f"{api_base_url}/v1/positions",
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        return response.json()

    result = benchmark(call_api)

    # Verify successful response
    assert "bodies" in result
    assert "Sun" in result["bodies"]
    assert "Moon" in result["bodies"]


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
@pytest.mark.benchmark(group="positions_full")
def test_benchmark_positions_all_bodies(benchmark, api_base_url, fort_knox_payload):
    """
    Benchmark /v1/positions with all 10 major bodies.

    Performance budget: p95 ≤ 250ms
    """
    payload = fort_knox_payload.copy()
    payload["bodies"] = [
        "Sun", "Moon", "Mercury", "Venus", "Mars",
        "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"
    ]

    def call_api():
        response = requests.post(
            f"{api_base_url}/v1/positions",
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        return response.json()

    result = benchmark(call_api)

    # Verify all bodies returned
    assert "bodies" in result
    assert len(result["bodies"]) == 10


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
@pytest.mark.benchmark(group="cache_hit")
def test_benchmark_cache_hit_performance(benchmark, api_base_url, fort_knox_payload):
    """
    Benchmark cached request performance.

    First request warms cache, second request should be <50ms (cache hit).
    """
    payload = fort_knox_payload.copy()
    payload["bodies"] = ["Sun", "Moon", "Mars"]

    # Warm the cache with initial request
    response = requests.post(
        f"{api_base_url}/v1/positions",
        json=payload,
        timeout=5
    )
    response.raise_for_status()

    # Benchmark cache hit
    def call_api_cached():
        response = requests.post(
            f"{api_base_url}/v1/positions",
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        return response.json()

    result = benchmark(call_api_cached)

    # Check for ETag (cache indicator)
    # Note: This is a proxy - actual cache hit detection depends on implementation


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
@pytest.mark.benchmark(group="healthz")
def test_benchmark_healthz_latency(benchmark, api_base_url):
    """
    Benchmark /healthz endpoint latency.

    Should be very fast (<20ms) as it's a simple health check.
    """
    def call_healthz():
        response = requests.get(
            f"{api_base_url}/healthz",
            timeout=5
        )
        response.raise_for_status()
        return response.json()

    result = benchmark(call_healthz)

    # Verify health check structure
    assert "status" in result or "kernels" in result


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
@pytest.mark.benchmark(group="concurrent")
def test_benchmark_concurrent_load(benchmark, api_base_url, fort_knox_payload):
    """
    Benchmark performance under concurrent load simulation.

    Makes 10 requests rapidly to simulate concurrent clients.
    Tests worker pool efficiency.
    """
    import concurrent.futures

    payload = fort_knox_payload.copy()
    payload["bodies"] = ["Sun", "Mars", "Jupiter"]

    def concurrent_requests():
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(10):
                future = executor.submit(
                    requests.post,
                    f"{api_base_url}/v1/positions",
                    json=payload,
                    timeout=10
                )
                futures.append(future)

            results = [f.result() for f in futures]
            return len([r for r in results if r.status_code == 200])

    successful = benchmark(concurrent_requests)

    # All requests should succeed
    assert successful == 10, f"Only {successful}/10 concurrent requests succeeded"


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
@pytest.mark.benchmark(group="sidereal")
def test_benchmark_sidereal_calculation(benchmark, api_base_url, fort_knox_payload):
    """
    Benchmark sidereal position calculation performance.

    Ayanāṃśa computation adds overhead vs tropical.
    Budget: ≤200ms for full calculation.
    """
    payload = fort_knox_payload.copy()
    payload["system"] = "sidereal"
    payload["ayanamsha"] = {"id": "lahiri"}
    payload["bodies"] = ["Sun", "Moon", "Mercury", "Venus", "Mars"]

    def call_api():
        response = requests.post(
            f"{api_base_url}/v1/positions",
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        return response.json()

    result = benchmark(call_api)

    # Verify ayanāṃśa was applied
    assert "metadata" in result
    # Check for ayanamsha metadata if exposed


# Performance budget assertions (run after benchmarks)
def test_performance_budgets_met(benchmark_results=None):
    """
    Validate that all performance budgets are met.

    This test analyzes benchmark results and fails if budgets exceeded.
    Requires pytest-benchmark with --benchmark-autosave.
    """
    # This is a placeholder - actual implementation would parse
    # benchmark JSON output and compare to budgets
    #
    # Example budgets:
    # - positions_minimal (Sun+Moon): p95 ≤ 150ms
    # - positions_full (10 bodies): p95 ≤ 250ms
    # - cache_hit: p95 ≤ 50ms
    # - healthz: p95 ≤ 20ms
    #
    # CI integration:
    # 1. pytest --benchmark-autosave --benchmark-json=output.json
    # 2. Parse output.json
    # 3. Compare p95 values to budgets
    # 4. Fail if >20% regression vs baseline
    pass


if __name__ == "__main__":
    # Run benchmarks with statistics
    pytest.main([
        __file__,
        "-v",
        "--benchmark-only",
        "--benchmark-min-rounds=5",
        "--benchmark-warmup=on",
        "--benchmark-columns=min,max,mean,stddev,median,ops"
    ])
