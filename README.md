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

## 🔒 API Contract (UI-ready)

### Base
- **Base URL (dev):** `http://localhost:8000`
- **Content-Type:** `application/json`
- **Time scale:** Input timestamps **UTC ISO-8601** (`YYYY-MM-DDTHH:mm:ssZ`)
- **Frames & model:** `ecliptic_of_date` (IAU-1980 mean), **topocentric**, aberration **LT+S**
- **Units:** angles in **degrees**; distances in **AU**; elevation in **meters**

---

### Endpoints

#### `GET /health` → 200
Minimal readiness & coordinate system.
```json
{
  "status": "ok",
  "kernels": 5,
  "spice_version": "CSPICE_N0067",
  "coordinate_system": "ecliptic_of_date"
}
```

#### `GET /info` → 200
Runtime metadata (stable keys below; order not guaranteed).
```json
{
  "spice_version": "CSPICE_N0067",
  "frame": "ECLIPDATE",
  "ecliptic_model": "IAU1980-mean",
  "abcorr": "LT+S",
  "kernels": [
    "services/spice/kernels/lsk/naif0012.tls",
    "services/spice/kernels/pck/pck00011.tpc",
    "services/spice/kernels/pck/earth_latest_high_prec.bpc",
    "services/spice/kernels/spk/planets/de440.bsp"
  ],
  "ts": "2025-09-23T21:45:00Z"
}
```

#### `POST /calculate` → 200
Compute topocentric sidereal ecliptic positions.

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
  "data": {
    "Sun":     { "longitude": 66.3075,  "latitude": -0.0040, "distance": 1.0160 },
    "Moon":    { "longitude": 242.2140, "latitude": -5.0400, "distance": 0.0026 },
    "Mercury": { "longitude": 74.8124,  "latitude": 1.7296,  "distance": 1.2932 },
    "Venus":   { "longitude": 70.9775,  "latitude": 0.6025,  "distance": 1.7270 },
    "Mars":    { "longitude": 14.7190,  "latitude": -1.0332, "distance": 1.7770 },
    "Jupiter": { "longitude": 41.6442,  "latitude": -0.7007, "distance": 5.9302 },
    "Saturn":  { "longitude": 324.8395, "latitude": -1.9440, "distance": 9.4347 }
  },
  "meta": {
    "ecliptic_frame": "ECLIPDATE",
    "service_version": "1.0.0",
    "spice_version": "CSPICE_N0067",
    "kernel_set_tag": "2024-Q3"
  }
}
```

**Error (example, out of coverage)** → 500
```json
{
  "detail": "SPICE calculation failed: SPICE(SPKINSUFFDATA) -- Insufficient ephemeris data has been loaded to compute the state of target body 4 (MARS BARYCENTER) relative to observer body 399 (EARTH) at the ephemeris epoch 1470-01-01T00:00:00.000."
}
```

### Contract guarantees

- **Rate limiting:** Responses may include standard `X-RateLimit-*` headers in production
- **CORS:** Allowed origins configured via `ALLOWED_ORIGINS` env (comma-separated); wildcard never used in prod
- **Angle semantics:** Longitude `[0, 360)` degrees, wrap-safe; Latitude `[-90, 90]` degrees
- **Distance:** Astronomical Units (AU)
- **Targets:** Sun/Moon (centers), planets via barycenters matching DE440
- **Sidereal:** Ayanāṁśa applied only to longitude after ecliptic-of-date rotation

### TypeScript types (drop-in)
```typescript
export type Ayanamsa = 'lahiri' | 'fagan_bradley';

export interface CalculateRequest {
  birth_time: string;       // ISO UTC, e.g. "2024-06-21T18:00:00Z"
  latitude: number;         // -90..90
  longitude: number;        // -180..180
  elevation: number;        // meters
  ayanamsa: Ayanamsa;
}

export interface BodyPosition {
  longitude: number;        // degrees, [0,360)
  latitude: number;         // degrees, [-90,90]
  distance: number;         // AU
}

export interface CalculateResponse {
  data: Record<'Sun'|'Moon'|'Mercury'|'Venus'|'Mars'|'Jupiter'|'Saturn', BodyPosition>;
  meta: {
    ecliptic_frame: 'ECLIPDATE';
    service_version: string;
    spice_version: string;
    kernel_set_tag: string;
  };
}
```

### Curl examples
```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/info | jq .
curl -s -X POST http://localhost:8000/calculate \
  -H 'content-type: application/json' \
  -d '{"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":50,"ayanamsa":"lahiri"}' | jq .
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

**Shutdown**: `spice.kclear()` in FastAPI lifespan pattern

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

## 🚀 Production Deployment

For production, use process workers since CSPICE isn't thread-safe:

```bash
# Docker CMD, Procfile, or deploy script:
gunicorn services.spice.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000 --timeout 30
```

## 🗺️ Roadmap

- `/info` endpoint with kernel list & coverage windows
- Small-body support via Horizons-generated SPKs
- Next.js UI (form, results, caching)

## 🙏 Acknowledgments

- NASA NAIF SPICE Toolkit and JPL ephemerides
- SpiceyPy maintainers and contributors
