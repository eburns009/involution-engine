"""
Monitoring & Observability Tests

Validates that metrics, health checks, and observability infrastructure
meet operational requirements.

Ensures /metrics exports expected counters/histograms and /healthz
reports comprehensive system status.
"""

import pytest
import re

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@pytest.fixture
def api_base_url():
    """API base URL from environment or default."""
    import os
    return os.getenv("ENGINE_BASE", "http://localhost:8080")


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_metrics_endpoint_exists(api_base_url):
    """Verify /metrics endpoint is accessible."""
    response = requests.get(f"{api_base_url}/metrics", timeout=5)

    assert response.status_code == 200, (
        f"/metrics endpoint returned {response.status_code}"
    )

    # Verify Prometheus text format
    assert response.headers.get("Content-Type").startswith("text/plain"), (
        f"Unexpected Content-Type: {response.headers.get('Content-Type')}"
    )


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_metrics_required_counters_exist(api_base_url):
    """
    Validate that required Prometheus metrics are exported.

    Required metrics:
    - http_requests_total{method, endpoint, status}
    - involution_positions_calculated_total
    - involution_cache_operations_total
    - involution_errors_total
    """
    response = requests.get(f"{api_base_url}/metrics", timeout=5)
    metrics_text = response.text

    required_metrics = [
        "http_requests_total",
        "involution_positions_calculated_total",
        "involution_cache_operations_total",
        "involution_errors_total",
    ]

    for metric_name in required_metrics:
        # Look for metric name in output (not just TYPE/HELP)
        metric_pattern = rf"^{re.escape(metric_name)}\{{.*\}}\s+\d+"

        assert re.search(metric_pattern, metrics_text, re.MULTILINE), (
            f"Required metric '{metric_name}' not found or has no data points"
        )


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_metrics_required_histograms_exist(api_base_url):
    """
    Validate that required histogram metrics are exported.

    Required histograms:
    - http_request_duration_seconds (with buckets)
    - involution_positions_duration_seconds
    """
    response = requests.get(f"{api_base_url}/metrics", timeout=5)
    metrics_text = response.text

    required_histograms = [
        "http_request_duration_seconds",
        "involution_positions_duration_seconds",
    ]

    for histogram_name in required_histograms:
        # Histograms should have _bucket, _sum, _count suffixes
        bucket_pattern = rf"{re.escape(histogram_name)}_bucket\{{.*le=\".*\"\}}"
        sum_pattern = rf"{re.escape(histogram_name)}_sum"
        count_pattern = rf"{re.escape(histogram_name)}_count"

        assert re.search(bucket_pattern, metrics_text, re.MULTILINE), (
            f"Histogram '{histogram_name}' missing _bucket metrics"
        )

        assert re.search(sum_pattern, metrics_text, re.MULTILINE), (
            f"Histogram '{histogram_name}' missing _sum"
        )

        assert re.search(count_pattern, metrics_text, re.MULTILINE), (
            f"Histogram '{histogram_name}' missing _count"
        )


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_metrics_required_gauges_exist(api_base_url):
    """
    Validate that required gauge metrics are exported.

    Required gauges:
    - involution_worker_pool_size
    - involution_worker_pool_queue_size
    - involution_cache_size_entries
    - involution_cache_hit_rate
    """
    response = requests.get(f"{api_base_url}/metrics", timeout=5)
    metrics_text = response.text

    required_gauges = [
        "involution_worker_pool_size",
        "involution_worker_pool_queue_size",
        "involution_cache_size_entries",
        "involution_cache_hit_rate",
    ]

    for gauge_name in required_gauges:
        # Gauges should appear with a numeric value
        gauge_pattern = rf"^{re.escape(gauge_name)}\s+\d+"

        # May also have labels
        gauge_with_labels_pattern = rf"^{re.escape(gauge_name)}\{{.*\}}\s+[\d\.]+"

        found = (
            re.search(gauge_pattern, metrics_text, re.MULTILINE) or
            re.search(gauge_with_labels_pattern, metrics_text, re.MULTILINE)
        )

        assert found, f"Required gauge '{gauge_name}' not found in metrics output"


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_healthz_endpoint_exists(api_base_url):
    """Verify /healthz endpoint is accessible and returns healthy status."""
    response = requests.get(f"{api_base_url}/healthz", timeout=5)

    assert response.status_code == 200, (
        f"/healthz endpoint returned {response.status_code}"
    )

    health_data = response.json()

    # Should have status field
    assert "status" in health_data, "Health check missing 'status' field"


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_healthz_reports_kernel_status(api_base_url):
    """
    Validate that /healthz reports kernel status.

    Required fields:
    - kernels.de440 or kernels.de441 (at least one)
    - kernels.*.status or kernels.*.ok
    """
    response = requests.get(f"{api_base_url}/healthz", timeout=5)
    health_data = response.json()

    assert "kernels" in health_data, "Health check missing 'kernels' field"

    kernels = health_data["kernels"]

    # Should report at least one ephemeris kernel
    assert kernels, "No kernel status reported"

    # Check that kernel status includes required fields
    if isinstance(kernels, dict):
        for kernel_name, kernel_info in kernels.items():
            if isinstance(kernel_info, dict):
                # Should have status or ok field
                assert "status" in kernel_info or "ok" in kernel_info, (
                    f"Kernel '{kernel_name}' missing status information"
                )


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_healthz_reports_cache_status(api_base_url):
    """
    Validate that /healthz reports cache status.

    Should include cache backend type and health status.
    """
    response = requests.get(f"{api_base_url}/healthz", timeout=5)
    health_data = response.json()

    # Cache status may be optional depending on configuration
    if "cache" in health_data:
        cache_info = health_data["cache"]

        # Should report backend type
        assert "backend" in cache_info or "type" in cache_info, (
            "Cache status missing backend/type information"
        )


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_healthz_reports_system_metadata(api_base_url):
    """
    Validate that /healthz reports system metadata.

    Should include:
    - version
    - uptime (optional)
    - timestamp
    """
    response = requests.get(f"{api_base_url}/healthz", timeout=5)
    health_data = response.json()

    # Version should be reported
    assert "version" in health_data or "service_version" in health_data, (
        "Health check missing version information"
    )

    # Timestamp should be present
    assert "timestamp" in health_data or "ts" in health_data, (
        "Health check missing timestamp"
    )


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_healthz_reports_worker_pool_status(api_base_url):
    """
    Validate that /healthz reports worker pool status.

    Should include:
    - pool size
    - queue depth
    - active workers
    """
    response = requests.get(f"{api_base_url}/healthz", timeout=5)
    health_data = response.json()

    # Pool status may be nested or at top level
    if "pool" in health_data:
        pool_info = health_data["pool"]

        # Should report queue depth (critical for capacity monitoring)
        assert "queue_depth" in pool_info or "queue_size" in pool_info, (
            "Pool status missing queue depth information"
        )


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_metrics_labels_are_valid(api_base_url):
    """
    Validate that metric labels follow Prometheus conventions.

    Labels should:
    - Use snake_case
    - Not have empty values
    - Be consistent across metrics
    """
    response = requests.get(f"{api_base_url}/metrics", timeout=5)
    metrics_text = response.text

    # Find all label definitions
    label_pattern = r'\{([^}]+)\}'

    for match in re.finditer(label_pattern, metrics_text):
        labels_str = match.group(1)

        # Parse labels
        for label in labels_str.split(','):
            if '=' in label:
                key, value = label.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"')

                # Check label naming convention (snake_case)
                assert re.match(r'^[a-z_][a-z0-9_]*$', key), (
                    f"Label name '{key}' doesn't follow snake_case convention"
                )

                # Check label value is not empty
                assert value, f"Label '{key}' has empty value"


@pytest.mark.skipif(not REQUESTS_AVAILABLE, reason="requests required")
def test_cache_hit_rate_metric_bounded(api_base_url):
    """
    Validate that cache_hit_rate metric is in range [0.0, 1.0].

    Cache hit rate should be a ratio, not a percentage.
    """
    response = requests.get(f"{api_base_url}/metrics", timeout=5)
    metrics_text = response.text

    # Find cache_hit_rate metric
    pattern = r'involution_cache_hit_rate\s+([\d\.]+)'

    match = re.search(pattern, metrics_text)

    if match:
        hit_rate = float(match.group(1))

        assert 0.0 <= hit_rate <= 1.0, (
            f"Cache hit rate {hit_rate} outside valid range [0.0, 1.0]"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
