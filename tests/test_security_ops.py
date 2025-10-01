
def test_cors_headers(client):
    r = client.options(
        "/calculate",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200, f"CORS preflight failed: {r.status_code}"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

def test_invalid_json_returns_422(client):
    r = client.post("/calculate",
                   content="invalid json",
                   headers={"Content-Type": "application/json"},
                   timeout=10)
    assert r.status_code == 422, f"Expected 422 for invalid JSON, got {r.status_code}"

def test_missing_fields_returns_422(client):
    r = client.post("/calculate", json={"birth_time": "2024-01-01T00:00:00Z"}, timeout=10)
    assert r.status_code == 422, f"Expected 422 for missing fields, got {r.status_code}"
    assert "latitude" in r.text.lower() or "longitude" in r.text.lower()

def test_invalid_birth_time_format(client):
    r = client.post("/calculate", json={
        "birth_time": "invalid-date",
        "latitude": 0, "longitude": 0, "elevation": 0, "ayanamsa": "lahiri"
    }, timeout=10)
    assert r.status_code == 422, f"Expected 422 for invalid date, got {r.status_code}"

def test_extreme_latitude_rejected(client):
    r = client.post("/calculate", json={
        "birth_time": "2024-01-01T00:00:00Z",
        "latitude": 95, "longitude": 0, "elevation": 0, "ayanamsa": "lahiri"
    }, timeout=10)
    assert r.status_code == 422, f"Expected 422 for lat=95°, got {r.status_code}"