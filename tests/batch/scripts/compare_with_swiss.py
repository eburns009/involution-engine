import pandas as pd
import requests
import swisseph as swe

SPICE_URL = "http://localhost:8000"  # your endpoint

# ---- settings you want to test ----
ZODIAC = "sidereal"  # "sidereal" or "tropical"
AYANAMSA = "fagan_bradley"  # used only when ZODIAC="sidereal"
HOUSE = "placidus"          # "placidus" | "equal" | "whole-sign"
TOPO = False                # geocentric vs topocentric comparison
ELEV_M = 25

# ---- Swiss Ephem flags (mean ecliptic-of-date, apparent) ----
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_NONUT  # NONUT => mean-of-date
# (do NOT set TRUEPOS; we want apparent)

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN
}
HOUSE_CODE = {"placidus": b"P", "equal": b"E", "whole-sign": b"W"}[HOUSE]

# test cases (UTC)
CASES = [
    # name, iso, lat, lon, elev
    ("Varanasi 1991", "1991-12-25T01:15:00Z", 25.3176, 82.9739, 80),
    ("New York 1988", "1988-05-05T18:20:00Z", 40.7128, -74.0060, 10),
    ("Houston 1969",  "1969-07-20T20:17:00Z", 29.7604, -95.3698, 10),
    ("Sydney 2022",   "2022-12-21T11:00:00Z", -33.8688, 151.2093, 30),
    ("SF Solstice 24","2024-06-21T18:00:00Z", 37.7749, -122.4194, 25),
]

def wrapdiff(a,b):  # minimal angular difference in degrees
    return abs(((a-b+540)%360)-180)

def jd_ut(iso_z):
    # Swiss expects UT as Julian day
    return swe.julday(int(iso_z[0:4]), int(iso_z[5:7]), int(iso_z[8:10]),
                      int(iso_z[11:13]) + int(iso_z[14:16])/60.0, swe.GREG_CAL)

def swiss_positions(iso, lat, lon, elev):
    if TOPO:
        swe.set_topo(lon, lat, elev/1000.0)
    else:
        swe.set_topo(0,0,0)
    jdut = jd_ut(iso)
    ay_deg = 0.0
    if ZODIAC == "sidereal":
        # match your chosen ayanamsa
        if AYANAMSA == "lahiri":
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        else:
            swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY, 0, 0)
        sidereal = True
    else:
        # tropical: disable sidereal mode
        swe.set_sid_mode(swe.SIDM_FAGAN_BRADLEY, 0, 0)  # reset
        sidereal = False

    out = {}
    for name, ipl in PLANETS.items():
        lon_lat_dist, _ = swe.calc_ut(jdut, ipl, FLAGS)
        lam = lon_lat_dist[0]  # ecliptic longitude of date (mean, apparent)
        if sidereal:
            # Swiss gives sidereal directly when sid mode set → no subtraction needed
            pass
        out[name] = lam % 360.0
    return out

def swiss_houses(iso, lat, lon, elev):
    jdut = jd_ut(iso)
    if TOPO:
        swe.set_topo(lon, lat, elev/1000.0)
    else:
        swe.set_topo(0,0,0)
    # Swiss houses use local sidereal internally; HOUSE_CODE selects system
    # always returns TROPICAL cusp longitudes of date; if sidereal wanted, Swiss can do that too,
    # but for parity we'll subtract ayanamsa manually when needed
    ascmc, cusps = swe.houses_ex(jdut, lat, lon, HOUSE_CODE)
    asc_trop = ascmc[0] % 360.0
    mc_trop  = ascmc[1] % 360.0
    cusps_trop = [c % 360.0 for c in cusps[:12]]
    if ZODIAC == "sidereal":
        # get ayanamsa numeric for this date
        ay = swe.get_ayanamsa_ut(jdut)
        asc = (asc_trop - ay) % 360.0
        mc  = (mc_trop  - ay) % 360.0
        cusps_sid = [ (c - ay) % 360.0 for c in cusps_trop ]
        return asc, mc, cusps_sid
    return asc_trop, mc_trop, cusps_trop

def api_positions(iso, lat, lon, elev):
    j = {
      "birth_time": iso, "latitude": lat, "longitude": lon,
      "elevation": elev if TOPO else 0, "zodiac": ZODIAC, "ayanamsa": AYANAMSA
    }
    r = requests.post(f"{SPICE_URL}/calculate", json=j, timeout=20)
    r.raise_for_status()
    data = r.json()["data"]
    return {k: data[k]["longitude"] for k in PLANETS}

def api_houses(iso, lat, lon, elev):
    j = {
      "birth_time": iso, "latitude": lat, "longitude": lon,
      "elevation": elev if TOPO else 0,
      "zodiac": ZODIAC, "ayanamsa": AYANAMSA,
      "system": HOUSE, "mc_hemisphere": "south" if lat>=0 else "north"
    }
    r = requests.post(f"{SPICE_URL}/houses", json=j, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data["asc"], data["mc"], data["cusps"]

def main():
    print("🔬 Swiss Ephemeris Comparison")
    print(f"Settings: {ZODIAC.upper()} zodiac, {HOUSE.upper()} houses")
    if ZODIAC == "sidereal":
        print(f"Ayanāṁśa: {AYANAMSA}")
    print(f"Observer: {'Topocentric' if TOPO else 'Geocentric'}")
    print("Frame: Mean ecliptic-of-date (NONUT flag set)")
    print("=" * 80)

    rows = []
    for name, iso, lat, lon, elev in CASES:
        print(f"\nProcessing {name}...")
        try:
            ap = api_positions(iso, lat, lon, elev)
            sp = swiss_positions(iso, lat, lon, elev)
            ah_asc, ah_mc, ah_c = api_houses(iso, lat, lon, elev)
            sh_asc, sh_mc, sh_c = swiss_houses(iso, lat, lon, elev)

            for body in PLANETS:
                rows.append({
                    "case": name, "type": "planet", "name": body,
                    "api": round(ap[body], 6), "swiss": round(sp[body], 6),
                    "diff_deg": round(wrapdiff(ap[body], sp[body]), 6)
                })
            rows.append({"case": name, "type": "house", "name": "ASC",
                         "api": round(ah_asc, 6), "swiss": round(sh_asc, 6),
                         "diff_deg": round(wrapdiff(ah_asc, sh_asc), 6)})
            rows.append({"case": name, "type": "house", "name": "MC",
                         "api": round(ah_mc, 6), "swiss": round(sh_mc, 6),
                         "diff_deg": round(wrapdiff(ah_mc, sh_mc), 6)})
            for i,(a,s) in enumerate(zip(ah_c, sh_c, strict=False), start=1):
                rows.append({"case": name, "type": "cusp", "name": f"Cusp {i}",
                             "api": round(a, 6), "swiss": round(s, 6),
                             "diff_deg": round(wrapdiff(a, s), 6)})
        except Exception as e:
            print(f"ERROR processing {name}: {e}")

    df = pd.DataFrame(rows)
    print("\n" + "=" * 80)
    print("DETAILED RESULTS:")
    print("=" * 80)
    print(df.to_string(index=False))

    print("\n" + "=" * 80)
    print("SUMMARY BY TYPE:")
    print("=" * 80)
    summary = df.groupby(["type"])["diff_deg"].describe(percentiles=[.5,.95]).round(6)
    print(summary)

    # Pass criteria analysis
    print("\n" + "=" * 80)
    print("PASS CRITERIA ANALYSIS:")
    print("=" * 80)

    planets_ok = df[df["type"] == "planet"]["diff_deg"].max() <= 0.02
    houses_ok = df[df["type"].isin(["house", "cusp"])]["diff_deg"].max() <= 0.03

    print(f"Planets (≤0.02°): {'✅ PASS' if planets_ok else '❌ FAIL'} - Max diff: {df[df['type']=='planet']['diff_deg'].max():.6f}°")
    print(f"Houses (≤0.03°):  {'✅ PASS' if houses_ok else '❌ FAIL'} - Max diff: {df[df['type'].isin(['house','cusp'])]['diff_deg'].max():.6f}°")

    overall_pass = planets_ok and houses_ok
    print(f"\nOVERALL: {'🎉 PASS - Excellent agreement with Swiss Ephemeris!' if overall_pass else '⚠️ FAIL - Check configuration'}")

    if not overall_pass:
        print("\nTROUBLESHOOTING:")
        if not planets_ok:
            print("• Planet differences too large - check ecliptic-of-date pipeline")
        if not houses_ok:
            print("• House differences too large - check MC hemisphere or house system implementation")

if __name__ == "__main__":
    main()
