
def wrapdiff(a, b):
    """Calculate the minimum angular difference between two angles in degrees"""
    return abs(((a - b + 540) % 360) - 180)

def test_positions_tropical_equals_sidereal_plus_ayanamsa(client):
    """Test that tropical positions equal sidereal positions plus ayanamsa"""
    payload_base = {
        "birth_time":"2000-01-01T12:00:00Z",  # J2000 epoch, clean test
        "latitude": 0.0, "longitude": 0.0, "elevation": 0,
    }
    # Get tropical
    r_t = client.post("/calculate", json={**payload_base, "zodiac":"tropical", "ayanamsa":"fagan_bradley"}, timeout=20)
    assert r_t.status_code == 200, r_t.text
    j_t = r_t.json()

    # Get sidereal (same timestamp) using same ayanamsa
    r_s = client.post("/calculate", json={**payload_base, "zodiac":"sidereal", "ayanamsa":"fagan_bradley"}, timeout=20)
    assert r_s.status_code == 200, r_s.text
    j_s = r_s.json()

    # Read ayanamsa value from service meta
    ay = j_s["meta"].get("ayanamsa_deg", None)
    assert ay is not None, "Sidereal response should include ayanamsa_deg in meta"

    # Tropical response should not have ayanamsa_deg
    assert j_t["meta"].get("ayanamsa_deg") is None, "Tropical response should not include ayanamsa_deg"

    # Check zodiac values in meta
    assert j_t["meta"]["zodiac"] == "tropical"
    assert j_s["meta"]["zodiac"] == "sidereal"

    bodies = ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"]
    for b in bodies:
        lt = j_t["data"][b]["longitude"]
        ls = j_s["data"][b]["longitude"]

        # Tropical longitude minus ayanamsa should equal sidereal longitude
        expected_sidereal = (lt - ay) % 360.0
        d = wrapdiff(expected_sidereal, ls)
        assert d < 0.01, f"{b} tropical - ayanamsa != sidereal (tropical={lt:.6f}, sidereal={ls:.6f}, ayanamsa={ay:.6f}, diff={d:.4f}°)"

def test_houses_tropical_equals_sidereal_plus_ayanamsa(client):
    """Test that tropical house cusps equal sidereal cusps plus ayanamsa"""
    base = {
        "birth_time":"2024-06-21T18:00:00Z",
        "latitude": 37.7749, "longitude": -122.4194, "elevation": 25,
        "system":"placidus", "mc_hemisphere":"south"
    }
    rt = client.post("/houses", json={**base, "zodiac":"tropical", "ayanamsa":"lahiri"}, timeout=20)
    rs = client.post("/houses", json={**base, "zodiac":"sidereal",  "ayanamsa":"lahiri"}, timeout=20)
    assert rt.status_code == 200 and rs.status_code == 200, f"Tropical: {rt.text}, Sidereal: {rs.text}"
    jt, js = rt.json(), rs.json()

    # Get ayanamsa from sidereal response
    aydeg = js.get("ayanamsa_deg")
    assert aydeg is not None, "Sidereal houses response should include ayanamsa_deg"

    # Tropical response should not have ayanamsa_deg
    assert jt.get("ayanamsa_deg") is None, "Tropical houses response should not include ayanamsa_deg"

    # Check zodiac values
    assert jt["zodiac"] == "tropical"
    assert js["zodiac"] == "sidereal"

    # Asc/MC consistency
    expected_sidereal_asc = (jt["asc"] - aydeg) % 360.0
    expected_sidereal_mc = (jt["mc"] - aydeg) % 360.0

    assert wrapdiff(expected_sidereal_asc, js["asc"]) < 0.02, f"ASC: tropical-ay={expected_sidereal_asc:.6f} != sidereal={js['asc']:.6f}"
    assert wrapdiff(expected_sidereal_mc, js["mc"]) < 0.02, f"MC: tropical-ay={expected_sidereal_mc:.6f} != sidereal={js['mc']:.6f}"

    # All cusps consistency
    for i, (ct, cs) in enumerate(zip(jt["cusps"], js["cusps"])):
        expected_sidereal_cusp = (ct - aydeg) % 360.0
        diff = wrapdiff(expected_sidereal_cusp, cs)
        assert diff < 0.02, f"Cusp {i+1}: tropical-ay={expected_sidereal_cusp:.6f} != sidereal={cs:.6f}, diff={diff:.4f}°"

def test_whole_sign_tropical_sidereal_consistency(client):
    """Test whole-sign houses work correctly in both zodiacs"""
    base = {
        "birth_time":"2023-03-21T12:00:00Z",  # Spring equinox
        "latitude": 40.7128, "longitude": -74.0060, "elevation": 10,
        "system":"whole-sign", "mc_hemisphere":"south"
    }
    rt = client.post("/houses", json={**base, "zodiac":"tropical", "ayanamsa":"lahiri"}, timeout=20)
    rs = client.post("/houses", json={**base, "zodiac":"sidereal",  "ayanamsa":"lahiri"}, timeout=20)
    assert rt.status_code == 200 and rs.status_code == 200
    jt, js = rt.json(), rs.json()

    aydeg = js.get("ayanamsa_deg")
    assert aydeg is not None

    # Whole-sign cusps should be exact 30° boundaries
    for i, cusp in enumerate(jt["cusps"]):
        # Allow for small floating point errors but should be very close to 30° boundaries
        remainder = cusp % 30
        assert remainder < 0.1 or remainder > 29.9, f"Tropical whole-sign cusp {i+1} should be on 30° boundary, got {cusp:.6f}"

    for i, cusp in enumerate(js["cusps"]):
        remainder = cusp % 30
        assert remainder < 0.1 or remainder > 29.9, f"Sidereal whole-sign cusp {i+1} should be on 30° boundary, got {cusp:.6f}"

def test_equal_houses_tropical_sidereal_consistency(client):
    """Test equal houses work correctly in both zodiacs"""
    base = {
        "birth_time":"1990-12-25T06:30:00Z",
        "latitude": 51.5074, "longitude": -0.1278, "elevation": 35,  # London
        "system":"equal", "mc_hemisphere":"south"
    }
    rt = client.post("/houses", json={**base, "zodiac":"tropical", "ayanamsa":"fagan_bradley"}, timeout=20)
    rs = client.post("/houses", json={**base, "zodiac":"sidereal",  "ayanamsa":"fagan_bradley"}, timeout=20)
    assert rt.status_code == 200 and rs.status_code == 200
    jt, js = rt.json(), rs.json()

    aydeg = js.get("ayanamsa_deg")
    assert aydeg is not None

    # Equal houses should have exactly 30° spacing from ASC
    for i in range(1, 12):
        expected_trop = (jt["cusps"][0] + i * 30) % 360
        actual_trop = jt["cusps"][i]
        assert wrapdiff(expected_trop, actual_trop) < 0.01, f"Tropical equal house {i+1} spacing incorrect"

        expected_sid = (js["cusps"][0] + i * 30) % 360
        actual_sid = js["cusps"][i]
        assert wrapdiff(expected_sid, actual_sid) < 0.01, f"Sidereal equal house {i+1} spacing incorrect"

def test_different_ayanamsa_systems_consistency(client):
    """Test that different ayanamsa systems maintain tropical-sidereal consistency"""
    payload_base = {
        "birth_time":"2010-07-04T20:00:00Z",
        "latitude": 34.0522, "longitude": -118.2437, "elevation": 100,  # Los Angeles
    }

    for ayanamsa in ["lahiri", "fagan_bradley"]:
        # Get tropical (should be identical regardless of ayanamsa choice)
        r_t = client.post("/calculate", json={**payload_base, "zodiac":"tropical", "ayanamsa":ayanamsa}, timeout=20)
        assert r_t.status_code == 200
        j_t = r_t.json()

        # Get sidereal
        r_s = client.post("/calculate", json={**payload_base, "zodiac":"sidereal", "ayanamsa":ayanamsa}, timeout=20)
        assert r_s.status_code == 200
        j_s = r_s.json()

        ay = j_s["meta"]["ayanamsa_deg"]

        # Test Sun position consistency
        sun_trop = j_t["data"]["Sun"]["longitude"]
        sun_sid = j_s["data"]["Sun"]["longitude"]
        expected_sid = (sun_trop - ay) % 360.0
        diff = wrapdiff(expected_sid, sun_sid)
        assert diff < 0.01, f"Sun position inconsistency with {ayanamsa}: diff={diff:.4f}°"

def test_tropical_same_across_ayanamsa_choices(client):
    """Test that tropical positions are identical regardless of ayanamsa parameter"""
    payload_base = {
        "birth_time":"2015-08-15T14:30:00Z",
        "latitude": 19.4326, "longitude": -99.1332, "elevation": 2240,  # Mexico City
        "zodiac": "tropical"
    }

    # Get tropical with Lahiri
    r_lahiri = client.post("/calculate", json={**payload_base, "ayanamsa":"lahiri"}, timeout=20)
    assert r_lahiri.status_code == 200
    j_lahiri = r_lahiri.json()

    # Get tropical with Fagan-Bradley
    r_fagan = client.post("/calculate", json={**payload_base, "ayanamsa":"fagan_bradley"}, timeout=20)
    assert r_fagan.status_code == 200
    j_fagan = r_fagan.json()

    # Tropical positions should be identical regardless of ayanamsa choice
    bodies = ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"]
    for body in bodies:
        pos_lahiri = j_lahiri["data"][body]["longitude"]
        pos_fagan = j_fagan["data"][body]["longitude"]
        diff = wrapdiff(pos_lahiri, pos_fagan)
        assert diff < 0.000001, f"Tropical {body} position differs between ayanamsa choices: {diff:.8f}°"

    # Both should have no ayanamsa_deg in meta
    assert j_lahiri["meta"]["ayanamsa_deg"] is None
    assert j_fagan["meta"]["ayanamsa_deg"] is None
    assert j_lahiri["meta"]["zodiac"] == "tropical"
    assert j_fagan["meta"]["zodiac"] == "tropical"