# Involution Engine — SPICE Ephemeris Service

Research-grade, self-contained ephemeris engine for sidereal astrology.
Powered by NASA NAIF SPICE (via SpiceyPy) with topocentric, light-time and aberration corrections.

---

## ✨ Highlights

- **Topocentric** positions via `spkcpo` (observer-based) with **`LT+S`** corrections
- **Ecliptic-of-date** longitudes (engine transform; validated against SPICE); metadata reports `ECLIPDATE`
- **Planetary barycenters** with **DE440** for robust coverage (1550–2650 CE)
- Minimal, deterministic kernel set (LSK, PCK, Earth BPC, DE440)
- Security hardening: CORS allow-list, optional rate limiting, clean shutdown (`kclear`)
- QA gates: Ruff, MyPy, Bandit, pip-audit, pytest (golden + continuity tests)

---

## 🧱 Architecture (current)

```
Client → API Gateway (Node) → SPICE Service (FastAPI / Python)
└→ Kernels downloaded at build/run (no large files in Git)
```

---

## 🚀 Quick Start (local)

```bash
# 1) Python deps
pip install -r services/spice/requirements.txt

# 2) Kernels (DE440, PCK, LSK, Earth BPC)
npm run kernels    # or: bash services/spice/download_kernels.sh

# 3) Run service
uvicorn services.spice.main:app --reload --host 0.0.0.0 --port 8000

# 4) Health
curl -s http://localhost:8000/health
```

### Env

```bash
ALLOWED_ORIGINS=http://localhost:3000            # comma-separated list
ENV=dev                                          # 'prod' in production
DISABLE_RATE_LIMIT=1                             # tests/CI only
```

Kernels are not committed to Git; they're downloaded at build/run.

## 🔌 API

### GET /health
```json
{
  "status": "ok",
  "kernels": 5,
  "spice_version": "CSPICE_N0067",
  "coordinate_system": "ecliptic_of_date"
}
```

### POST /calculate

**Request**
```json
{
  "birth_time": "2024-06-21T18:00:00Z",
  "latitude": 37.7749,
  "longitude": -122.4194,
  "elevation": 50,
  "ayanamsa": "lahiri"
}
```

**Response**
```json
{
  "positions": {
    "Sun":    {"longitude": 66.3075, "latitude": -0.0040, "distance": 1.0160},
    "Moon":   {"longitude": 242.2140, "latitude": -5.0400, "distance": 0.0026},
    "Mars":   {"longitude": 14.7190, "latitude": -1.0400, "distance": 1.7800},
    "Jupiter":{"longitude": 41.6400, "latitude": -0.7000, "distance": 5.9300},
    "Saturn": {"longitude": 324.8400,"latitude": -1.9400,"distance": 9.4300}
  },
  "meta": {
    "frame": "ECLIPDATE",
    "abcorr": "LT+S",
    "ayanamsa": "lahiri",
    "topocentric": true,
    "elapsed_ms": 123
  }
}
```

**Errors**
```json
{
  "error": {
    "code": "SPKINSUFFDATA",
    "message": "No coverage for target",
    "details": {"target":"MARS BARYCENTER","epoch":"1470-01-01T00:00:00Z"}
  }
}
```

## 📐 Astronomical Method

**Observer**: geodetic lat/lon/elev → ITRF93 vector (SPICE Earth figure)

**Topocentric**: `spkcpo(target, et, "J2000", "LT+S", obs_itrf, "EARTH", "ITRF93")`

**Ecliptic**: ecliptic-of-date longitudes (engine transform validated vs SPICE)

**Sidereal**: apply chosen ayanāṁśa to longitude (e.g., Lahiri, Fagan-Bradley)

**Targets**: Sun (10), Moon (301), planetary barycenters (1–9) for robust DE440 coverage

**Kernels**: `naif0012.tls`, `pck00011.tpc`, `earth_latest_high_prec.bpc`, `de440.bsp`

For planet centers (e.g., Mars 499), add the relevant satellite SPK (e.g., mar097.bsp).

## 🛡️ Security & Ops

**CORS**: allow-list via `ALLOWED_ORIGINS` (no wildcard in prod)

**Rate limiting**: SlowAPI; bypass in tests via `DISABLE_RATE_LIMIT=1`

**Shutdown**: `spice.kclear()` in `@app.on_event("shutdown")`

**Containers**: kernels excluded by `.dockerignore`; prefer non-root user

## ✅ Quality Gates
```bash
ruff check .
mypy services/spice
bandit -q -r services/spice -x "services/spice/test_*"
pip-audit
pytest -q
```

## 🧰 Troubleshooting

**SPKINSUFFDATA**: date outside DE440 coverage, or center requested w/o satellite SPK → use barycenters.

**Git ">100 MB"**: you tried to commit kernels → revert; `.gitignore`/`.dockerignore` handle this.

**Frame mismatches**: `/health.coordinate_system` must match calculation path.

## 🗺️ Roadmap

- `/info` endpoint with kernel list & coverage windows
- Option to swap to SPICE `pxform("J2000","ECLIPDATE")` for ecliptic rotation everywhere
- Small-body support via Horizons-generated SPKs
- Next.js UI (form, results, caching)

## 🙏 Acknowledgments

- NASA NAIF SPICE Toolkit and JPL ephemerides
- SpiceyPy maintainers and contributors
