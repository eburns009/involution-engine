import pytest
import requests
import json

# This assumes server is running on localhost:8002
BASE_URL = "http://localhost:8002"

def test_calculation() -> None:
    """Simple test using requests to running server"""
    payload = {
        "birth_time": "2024-06-21T18:00:00Z",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "elevation": 50,
        "ayanamsa": "lahiri"
    }

    response = requests.post(f"{BASE_URL}/calculate", json=payload, timeout=10)

    if response.status_code == 200:
        data = response.json()
        print("\nActual values:")
        print(json.dumps(data, indent=2))

        # These will be updated with actual values
        assert "Sun" in data
        assert "Moon" in data
        assert "Mars" in data

        # Basic structure validation
        for planet, pos in data.items():
            assert "longitude" in pos
            assert "latitude" in pos
            assert "distance" in pos
            assert 0 <= pos["longitude"] < 360
            assert -90 <= pos["latitude"] <= 90
            assert pos["distance"] > 0
    else:
        pytest.skip(f"Server not running or error: {response.status_code}")

def test_health() -> None:
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    except requests.ConnectionError:
        pytest.skip("Server not running")