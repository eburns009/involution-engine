def test_health(client):
    r = client.get("/health", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "healthy"
    assert j["meta"]["coordinate_system"] == "ecliptic_of_date"
    assert j["data"]["kernels_loaded"] >= 4

def test_info(client):
    r = client.get("/info", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["meta"]["ecliptic_frame"] == "ECLIPDATE"
    assert j["meta"]["obliquity_model"] == "IAU1980-mean"
    assert isinstance(j["meta"]["spice_version"], str)

def test_calculate_shape(client):
    payload = {
        "birth_time": "2024-06-21T18:00:00Z",
        "latitude": 37.7749, "longitude": -122.4194, "elevation": 50,
        "ayanamsa": "lahiri",
    }
    r = client.post("/calculate", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["meta"]["ecliptic_frame"] == "ECLIPDATE"
    assert j["meta"]["service_version"] == "2.0.0"
    for name in ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"]:
        p = j["data"][name]
        assert 0 <= (p["longitude"] % 360) < 360
        assert -90 <= p["latitude"] <= 90
        assert p["distance"] > 0