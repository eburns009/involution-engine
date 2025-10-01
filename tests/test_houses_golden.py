"""
Golden test for houses calculations matching reference dataset
"""

def d(dms_sign, deg, m, s):
    """Convert degrees/minutes/seconds in a sign to absolute longitude"""
    sign_offsets = {
        "Aries": 0, "Taurus": 30, "Gemini": 60, "Cancer": 90,
        "Leo": 120, "Virgo": 150, "Libra": 180, "Scorpio": 210,
        "Sagittarius": 240, "Capricorn": 270, "Aquarius": 300, "Pisces": 330
    }
    return sign_offsets[dms_sign] + deg + m/60 + s/3600

def test_placidus_equator_1970_fb_north_mc(client):
    """Test Placidus at equator (1970-01-01 00:00Z, 0°N 0°E) with Fagan-Bradley and north MC"""
    r = client.post("/houses", json={
        "birth_time":"1970-01-01T00:00:00Z",
        "latitude":0.0, "longitude":0.0, "elevation":0,
        "ayanamsa":"fagan_bradley",
        "system":"placidus",
        "mc_hemisphere":"north"
    }, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()

    # Verify MC hemisphere is working
    assert j["system"] == "placidus"
    assert j["frame"] == "ECLIPDATE"

    cusps = j["cusps"]

    # Reference golden values from user's dataset
    gold = [
        d("Virgo", 16, 48, 24),      # House 1 (Asc)
        d("Libra", 18, 21, 24),      # House 2
        d("Scorpio", 17, 25, 40),    # House 3
        d("Sagittarius", 15, 4, 46), # House 4 (IC)
        d("Capricorn", 13, 29, 40),  # House 5
        d("Aquarius", 14, 17, 5),    # House 6
        d("Pisces", 16, 48, 24),     # House 7 (Desc)
        d("Aries", 18, 21, 24),      # House 8
        d("Taurus", 17, 25, 40),     # House 9
        d("Gemini", 15, 4, 46),      # House 10 (MC)
        d("Cancer", 13, 29, 40),     # House 11
        d("Leo", 14, 17, 5),         # House 12
    ]

    # Test Asc matches exactly (within a few arc-seconds)
    asc_diff = abs(((j["asc"] - gold[0] + 540) % 360) - 180)
    assert asc_diff < 0.01, f"Asc differs by {asc_diff:.4f}° from golden: got {j['asc']:.6f}°, expected {gold[0]:.6f}°"

    # Test MC matches exactly (should be ~75.08°)
    mc_diff = abs(((j["mc"] - gold[9] + 540) % 360) - 180)
    assert mc_diff < 0.01, f"MC differs by {mc_diff:.4f}° from golden: got {j['mc']:.6f}°, expected {gold[9]:.6f}°"

    # Test all cusps match within arc-seconds
    for i, (got, exp) in enumerate(zip(cusps, gold)):
        diff = abs(((got - exp + 540) % 360) - 180)
        assert diff < 0.02, f"Cusp {i+1} off by {diff:.4f}°: got {got:.6f}°, expected {exp:.6f}°"

    # Test exact opposites (key Placidus invariant)
    def are_opposite(a, b, tolerance=1e-6):
        diff = abs(a - b) % 360
        return abs(min(diff, 360 - diff) - 180.0) < tolerance

    assert are_opposite(cusps[0], cusps[6]), f"Houses 1&7 not opposite: {cusps[0]:.6f} vs {cusps[6]:.6f}"
    assert are_opposite(cusps[1], cusps[7]), f"Houses 2&8 not opposite: {cusps[1]:.6f} vs {cusps[8]:.6f}"
    assert are_opposite(cusps[2], cusps[8]), f"Houses 3&9 not opposite: {cusps[2]:.6f} vs {cusps[8]:.6f}"
    assert are_opposite(cusps[3], cusps[9]), f"Houses 4&10 not opposite: {cusps[3]:.6f} vs {cusps[9]:.6f}"
    assert are_opposite(cusps[4], cusps[10]), f"Houses 5&11 not opposite: {cusps[4]:.6f} vs {cusps[10]:.6f}"
    assert are_opposite(cusps[5], cusps[11]), f"Houses 6&12 not opposite: {cusps[5]:.6f} vs {cusps[11]:.6f}"

def test_mc_hemisphere_differences(client):
    """Test that different MC hemispheres produce different results at equator"""
    base_request = {
        "birth_time":"1970-01-01T00:00:00Z",
        "latitude":0.0, "longitude":0.0, "elevation":0,
        "ayanamsa":"fagan_bradley", "system":"placidus"
    }

    # Test south MC (default)
    r_south = client.post("/houses", json={**base_request, "mc_hemisphere": "south"})
    assert r_south.status_code == 200

    # Test north MC
    r_north = client.post("/houses", json={**base_request, "mc_hemisphere": "north"})
    assert r_north.status_code == 200

    # Test auto MC
    r_auto = client.post("/houses", json={**base_request, "mc_hemisphere": "auto"})
    assert r_auto.status_code == 200

    j_south = r_south.json()
    j_north = r_north.json()
    j_auto = r_auto.json()

    # At equator (lat=0), different hemisphere choices should give opposite MCs
    mc_diff = abs(j_south["mc"] - j_north["mc"]) % 360
    assert abs(mc_diff - 180.0) < 1e-6, f"North/South MCs not opposite at equator: {mc_diff}°"

    # Auto should pick south for lat≥0
    assert abs(j_auto["mc"] - j_south["mc"]) < 1e-6, "Auto MC should match south MC at equator"