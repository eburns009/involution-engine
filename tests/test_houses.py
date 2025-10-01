"""
Houses endpoint tests for Placidus, Whole Sign, and Equal house systems
"""

def test_placidus_contract(client):
    """Test Placidus house system contract and invariants"""
    r = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":37.7749,"longitude":-122.4194,"elevation":50,
        "ayanamsa":"lahiri","system":"placidus"
    }, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()

    # Contract validation
    assert j["frame"] == "ECLIPDATE"
    assert j["coordinate_system"] == "ecliptic_of_date"
    assert j["ecliptic_model"] == "IAU1980-mean"
    assert j["system"] == "placidus"
    assert j["ayanamsa"] == "lahiri"
    assert len(j["cusps"]) == 12

    # Asc/MC values
    assert isinstance(j["asc"], (int, float))
    assert isinstance(j["mc"], (int, float))
    assert 0 <= j["asc"] < 360
    assert 0 <= j["mc"] < 360

    # All cusps in range
    for i, cusp in enumerate(j["cusps"]):
        assert isinstance(cusp, (int, float)), f"Cusp {i+1} not numeric"
        assert 0 <= cusp < 360, f"Cusp {i+1} out of range: {cusp}"

    # Opposites hold (houses 1&7, 10&4)
    def angular_distance(a, b):
        diff = abs(a - b)
        return min(diff, 360 - diff)

    # Check if two angles are exactly opposite (180° apart)
    def are_opposite(a, b):
        diff = abs(a - b) % 360
        return min(diff, 360 - diff) == 180.0

    assert are_opposite(j["asc"], j["cusps"][6]), f"Asc ({j['asc']}) and 7th cusp ({j['cusps'][6]}) not opposite"   # 1 & 7 opposite
    assert are_opposite(j["mc"], j["cusps"][3]), f"MC ({j['mc']}) and 4th cusp ({j['cusps'][3]}) not opposite"     # 10 & 4 opposite

def test_placidus_polar_guard(client):
    """Test that Placidus rejects polar latitudes"""
    r = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":80.0,"longitude":0,"elevation":0,
        "ayanamsa":"lahiri","system":"placidus"
    }, timeout=20)
    assert r.status_code == 422
    assert "polar" in r.text.lower() or "undefined" in r.text.lower()

def test_whole_sign_contract(client):
    """Test Whole Sign house system contract"""
    r = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":37.7749,"longitude":-122.4194,"elevation":50,
        "ayanamsa":"lahiri","system":"whole-sign"
    }, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()

    # Contract validation
    assert j["system"] == "whole-sign"
    assert j["frame"] == "ECLIPDATE"
    assert len(j["cusps"]) == 12

    # Whole Sign invariant: cusps are 30° apart
    cusps = j["cusps"]
    for i in range(12):
        next_cusp = cusps[(i + 1) % 12]
        diff = (next_cusp - cusps[i]) % 360
        assert abs(diff - 30.0) < 1e-6, f"Cusps {i+1}-{((i+1)%12)+1} not 30° apart: {diff}"

def test_equal_contract(client):
    """Test Equal house system contract"""
    r = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":37.7749,"longitude":-122.4194,"elevation":50,
        "ayanamsa":"lahiri","system":"equal"
    }, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()

    # Contract validation
    assert j["system"] == "equal"
    assert j["frame"] == "ECLIPDATE"
    assert len(j["cusps"]) == 12

    # Equal houses invariant: cusps are 30° apart starting from Asc
    cusps = j["cusps"]
    asc = j["asc"]

    # First cusp should equal Ascendant
    assert abs(cusps[0] - asc) < 1e-6, "First cusp should equal Ascendant"

    # All cusps should be 30° apart
    for i in range(12):
        expected = (asc + 30.0 * i) % 360
        assert abs(cusps[i] - expected) < 1e-6, f"Cusp {i+1} not at expected position"

def test_ayanamsa_systems(client):
    """Test different ayanamsa systems produce different results"""

    # Lahiri
    r1 = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":37.7749,"longitude":-122.4194,"elevation":50,
        "ayanamsa":"lahiri","system":"equal"
    }, timeout=20)
    assert r1.status_code == 200

    # Fagan-Bradley
    r2 = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":37.7749,"longitude":-122.4194,"elevation":50,
        "ayanamsa":"fagan_bradley","system":"equal"
    }, timeout=20)
    assert r2.status_code == 200

    j1, j2 = r1.json(), r2.json()

    # Different ayanamsas should produce different results
    assert abs(j1["asc"] - j2["asc"]) > 0.1, "Different ayanamsas should produce different Asc"
    assert abs(j1["mc"] - j2["mc"]) > 0.1, "Different ayanamsas should produce different MC"

def test_houses_validation(client):
    """Test request validation for houses endpoint"""

    # Missing required fields
    r = client.post("/houses", json={})
    assert r.status_code == 422

    # Invalid latitude
    r = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":95,"longitude":0,"elevation":0,
        "ayanamsa":"lahiri","system":"placidus"
    })
    assert r.status_code == 422

    # Invalid house system
    r = client.post("/houses", json={
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude":37.7749,"longitude":-122.4194,"elevation":50,
        "ayanamsa":"lahiri","system":"invalid-system"
    })
    assert r.status_code == 422