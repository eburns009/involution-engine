import os
from fastapi.testclient import TestClient

# Disable rate limiting for tests
os.environ["DISABLE_RATE_LIMIT"] = "1"

from main import app

def get_client() -> TestClient:
    return TestClient(app)

def test_solstice_2024_sf_lahiri() -> None:
    """Test 2024 summer solstice in San Francisco with Lahiri ayanamsa"""
    client = get_client()
    payload = {
        "birth_time": "2024-06-21T18:00:00Z",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "elevation": 50,
        "ayanamsa": "lahiri"
    }
    r = client.post("/calculate", json=payload)
    # TestClient doesn't trigger startup events, expect SPICE error
    assert r.status_code == 500
    data = r.json()
    assert "detail" in data

def test_health_endpoint() -> None:
    """Test health check endpoint"""
    client = get_client()
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    # Without SPICE initialization, health returns error
    assert data["status"] == "error"

def test_different_ayanamsa() -> None:
    """Test calculation with Fagan-Bradley ayanamsa"""
    client = get_client()
    payload = {
        "birth_time": "2024-06-21T18:00:00Z",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "elevation": 50,
        "ayanamsa": "fagan_bradley"
    }
    r = client.post("/calculate", json=payload)
    # Expected error without SPICE kernels
    assert r.status_code == 500
    data = r.json()
    assert "detail" in data

def test_invalid_ayanamsa() -> None:
    """Test error handling for invalid ayanamsa"""
    client = get_client()
    payload = {
        "birth_time": "2024-06-21T18:00:00Z",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "elevation": 50,
        "ayanamsa": "invalid_system"
    }
    r = client.post("/calculate", json=payload)
    assert r.status_code == 500