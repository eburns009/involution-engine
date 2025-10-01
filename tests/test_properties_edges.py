import pytest

def test_topocentric_diff_moon_is_significant(client):
    base = {"birth_time":"2024-01-01T12:00:00Z", "elevation":0, "ayanamsa":"lahiri"}
    r1 = client.post("/calculate", json={**base, "latitude":0, "longitude":0}, timeout=20).json()
    r2 = client.post("/calculate", json={**base, "latitude":60,"longitude":0}, timeout=20).json()
    d = abs((r1["data"]["Moon"]["longitude"] - r2["data"]["Moon"]["longitude"] + 540)%360 - 180)
    assert d > 0.3, f"Topocentric Moon difference too small: {d:.4f}°"

@pytest.mark.parametrize("lat,lon", [
    (0, 179.9999), (0, -179.9999), (89.9, 0), (-89.9, 0)
])
def test_extreme_coords_ok(client, lat, lon):
    r = client.post("/calculate", json={
        "birth_time":"2024-06-21T18:00:00Z", "latitude":lat, "longitude":lon,
        "elevation":0, "ayanamsa":"lahiri"
    }, timeout=20)
    assert r.status_code == 200, f"Failed for lat={lat}, lon={lon}: {r.text}"

def test_out_of_coverage_clean_error(client):
    r = client.post("/calculate", json={
        "birth_time":"2700-01-01T00:00:00Z", "latitude":0, "longitude":0,
        "elevation":0, "ayanamsa":"lahiri"
    }, timeout=20)
    j = r.json()
    assert r.status_code in (400,422,500)
    assert "error" in j or "detail" in j  # clean JSON error

def test_perf_20_calls_under_budget(client):
    import time
    payload = {"birth_time":"2024-06-21T18:00:00Z","latitude":0,"longitude":0,"elevation":0,"ayanamsa":"lahiri"}
    t0=time.time()
    for _ in range(20):
        assert client.post("/calculate", json=payload, timeout=20).status_code == 200
    p95_budget = 0.3  # seconds
    elapsed_per_call = (time.time()-t0)/20
    assert elapsed_per_call < p95_budget, f"Performance too slow: {elapsed_per_call:.3f}s per call"

def test_ayanamsa_systems_differ(client):
    base = {"birth_time":"2024-06-21T18:00:00Z", "latitude":0, "longitude":0, "elevation":0}
    lahiri = client.post("/calculate", json={**base, "ayanamsa":"lahiri"}, timeout=20).json()
    fagan = client.post("/calculate", json={**base, "ayanamsa":"fagan_bradley"}, timeout=20).json()

    sun_diff = abs(lahiri["data"]["Sun"]["longitude"] - fagan["data"]["Sun"]["longitude"])
    assert 0.1 < sun_diff < 2.0, f"Ayanamsa difference unexpected: {sun_diff:.4f}°"