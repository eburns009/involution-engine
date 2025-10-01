import pytest

# Frozen goldens (sidereal, ecliptic-of-date) — from verified calculations
# tolerances are in degrees
GOLDENS = [
    {
      "when": "2000-01-01T12:00:00Z", "lat": 0, "lon": 0, "elev": 0, "ayanamsa": "lahiri",
      "expect": {"Sun": {"lon": 256.5214, "lat": -0.0007},
                 "Moon": {"lon": 198.7587, "lat": 4.8539}}
    },
    {
      "when": "2024-06-21T18:00:00Z", "lat": 37.7749, "lon": -122.4194, "elev": 50, "ayanamsa": "lahiri",
      "expect": {"Sun": {"lon": 66.3075, "lat": -0.0009},
                 "Moon": {"lon": 242.2143, "lat": -5.0464}}
    },
]

@pytest.mark.parametrize("row", GOLDENS)
def test_goldens(client, row):
    r = client.post("/calculate", json={
        "birth_time": row["when"], "latitude": row["lat"], "longitude": row["lon"],
        "elevation": row["elev"], "ayanamsa": row["ayanamsa"]
    }, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    for body, exp in row["expect"].items():
        got = data[body]
        # handle wrap for longitude
        dlon = abs((got["longitude"] - exp["lon"] + 540) % 360 - 180)
        assert dlon < 0.02, f"{body} lon off {dlon:.4f}° (got {got['longitude']:.4f}, expected {exp['lon']:.4f})"
        assert abs(got["latitude"] - exp["lat"]) < 0.02, f"{body} lat off (got {got['latitude']:.4f}, expected {exp['lat']:.4f})"
