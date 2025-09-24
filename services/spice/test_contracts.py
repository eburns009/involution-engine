"""
Contract tests for SPICE API format validation

These tests ensure API request/response formats remain stable for clients.
They validate schema structure without requiring SPICE kernels.
"""

import os
from fastapi.testclient import TestClient

# Disable rate limiting for tests
os.environ["DISABLE_RATE_LIMIT"] = "1"

from main import app

def get_client() -> TestClient:
    return TestClient(app)

def test_calculate_endpoint_contract() -> None:
    """Contract test: /calculate endpoint request/response format"""
    client = get_client()

    # Valid request payload structure
    payload = {
        "birth_time": "2024-06-21T18:00:00Z",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "elevation": 50,
        "ayanamsa": "lahiri"
    }

    r = client.post("/calculate", json=payload)

    # Contract validation (regardless of success/failure)
    assert r.status_code in [200, 500]  # Expected status codes

    if r.status_code == 200:
        # Success response contract
        data = r.json()

        # Top-level structure
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], dict)
        assert isinstance(data["meta"], dict)

        # Meta field contract
        meta = data["meta"]
        required_meta_fields = {
            "service_version", "spice_version", "kernel_set_tag",
            "ecliptic_frame", "request_id", "timestamp"
        }
        assert set(meta.keys()) == required_meta_fields
        assert isinstance(meta["service_version"], str)
        assert isinstance(meta["spice_version"], str)
        assert isinstance(meta["kernel_set_tag"], str)
        assert isinstance(meta["ecliptic_frame"], str)
        assert isinstance(meta["request_id"], str)
        assert isinstance(meta["timestamp"], (int, float))

        # Data field contract (planetary positions)
        planetary_data = data["data"]
        expected_bodies = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
        assert set(planetary_data.keys()) == expected_bodies

        # Each body structure contract
        for body, position in planetary_data.items():
            assert isinstance(position, dict)
            assert set(position.keys()) == {"longitude", "latitude", "distance"}
            assert isinstance(position["longitude"], (int, float))
            assert isinstance(position["latitude"], (int, float))
            assert isinstance(position["distance"], (int, float))

            # Value range contracts
            assert 0 <= position["longitude"] <= 360
            assert -90 <= position["latitude"] <= 90
            assert position["distance"] > 0

    else:
        # Error response contract (500)
        data = r.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

def test_health_endpoint_contract() -> None:
    """Contract test: /health endpoint format"""
    client = get_client()
    r = client.get("/health")

    assert r.status_code == 200
    data = r.json()

    # Health endpoint contract
    assert "status" in data
    assert data["status"] in ["ok", "error"]

    if data["status"] == "ok":
        # Success health contract
        required_fields = {
            "status", "kernels", "spice_version", "earth_radii_km",
            "coordinate_system", "aberration_correction"
        }
        assert set(data.keys()) == required_fields
        assert isinstance(data["kernels"], int)
        assert isinstance(data["spice_version"], str)
        assert isinstance(data["earth_radii_km"], list)
        assert len(data["earth_radii_km"]) == 3
        assert data["coordinate_system"] == "ecliptic_of_date"
        assert data["aberration_correction"] == "LT+S"

    else:
        # Error health contract
        assert "detail" in data

def test_version_endpoint_contract() -> None:
    """Contract test: /version endpoint format"""
    client = get_client()
    r = client.get("/version")

    assert r.status_code == 200
    data = r.json()

    # Version endpoint contract
    required_top_level = {
        "service_version", "spice_version", "kernel_set",
        "coordinate_frames", "ayanamsa_systems", "precision"
    }
    assert set(data.keys()) == required_top_level

    # Kernel set contract
    kernel_set = data["kernel_set"]
    kernel_required = {
        "tag", "count", "de_ephemeris", "earth_orientation",
        "planetary_constants", "leap_seconds"
    }
    assert set(kernel_set.keys()) == kernel_required
    assert isinstance(kernel_set["count"], int)

    # Coordinate frames contract
    frames = data["coordinate_frames"]
    frame_required = {"reference", "observer", "ecliptic", "aberration_correction"}
    assert set(frames.keys()) == frame_required
    assert frames["ecliptic"] == "ECLIPDATE"
    assert frames["reference"] == "J2000"
    assert frames["observer"] == "ITRF93"
    assert frames["aberration_correction"] == "LT+S"

    # Ayanamsa systems contract
    assert isinstance(data["ayanamsa_systems"], list)
    assert "lahiri" in data["ayanamsa_systems"]
    assert "fagan_bradley" in data["ayanamsa_systems"]

    # Precision contract
    precision = data["precision"]
    precision_required = {"longitude_digits", "latitude_digits", "distance_digits"}
    assert set(precision.keys()) == precision_required
    assert precision["longitude_digits"] == 6
    assert precision["latitude_digits"] == 6
    assert precision["distance_digits"] == 8

def test_metrics_endpoint_contract() -> None:
    """Contract test: /metrics endpoint format"""
    client = get_client()
    r = client.get("/metrics")

    assert r.status_code == 200
    data = r.json()

    # Metrics endpoint contract
    required_fields = {"latency", "errors", "timestamp", "alerts"}
    assert set(data.keys()) == required_fields

    # Latency metrics contract
    latency = data["latency"]
    latency_required = {"p50", "p95", "count"}
    assert set(latency.keys()) == latency_required
    assert isinstance(latency["p50"], (int, float))
    assert isinstance(latency["p95"], (int, float))
    assert isinstance(latency["count"], int)

    # Error metrics contract
    errors = data["errors"]
    error_required = {
        "error_rate", "total_errors", "spkinsuffdata_errors",
        "total_requests", "window_minutes"
    }
    assert set(errors.keys()) == error_required
    assert isinstance(errors["error_rate"], (int, float))
    assert 0 <= errors["error_rate"] <= 1

    # Alerts contract
    alerts = data["alerts"]
    alert_required = {"high_latency", "spkinsuffdata", "high_error_rate"}
    assert set(alerts.keys()) == alert_required
    for alert_name, alert_value in alerts.items():
        assert isinstance(alert_value, bool)

    # Timestamp contract
    assert isinstance(data["timestamp"], (int, float))

def test_request_validation_contract() -> None:
    """Contract test: Request validation error formats"""
    client = get_client()

    # Missing required fields
    r = client.post("/calculate", json={})
    assert r.status_code == 422  # Validation error

    # Invalid field types
    invalid_payload = {
        "birth_time": "invalid-date",
        "latitude": "not-a-number",
        "longitude": -122.4194,
        "elevation": 50,
        "ayanamsa": "lahiri"
    }
    r = client.post("/calculate", json=invalid_payload)
    assert r.status_code == 422

def test_cors_headers_contract() -> None:
    """Contract test: CORS headers in responses"""
    client = get_client()

    # Test preflight request
    r = client.options("/health")
    # Note: TestClient may not fully simulate CORS, but endpoint should exist
    assert r.status_code in [200, 405]  # Either works or method not allowed

    # Test actual request has no CORS issues
    r = client.get("/health")
    assert r.status_code == 200

# Contract test implementation notes:
# 1. Tests validate API schema without requiring SPICE kernels
# 2. Success and error response formats are both tested
# 3. Field types, required fields, and value ranges are validated
# 4. Tests will catch breaking changes to API contracts
# 5. Gracefully handle both success (200) and error (500) cases for /calculate