# v0.1.0 — Involution SPICE Service (Topocentric ECLIPDATE, DE440, QA Green)

## Highlights

- **Research-grade astronomy**: Topocentric positions via `spkcpo` with LT+S corrections
- **Sidereal coordinates**: Ecliptic-of-date (IAU-1980 mean) + ayanāṁśa (Lahiri, Fagan-Bradley)
- **Deterministic ephemerides**: DE440 (1550–2650 CE), Sun/Moon centers + planetary barycenters
- **API contract frozen**: Stable JSON schema for `/calculate`, `/health`, `/info`
- **Security & ops**: CORS allow-list, rate limiting, FastAPI lifespan, clean `kclear()` shutdown
- **Quality gates**: ruff, mypy, bandit, pip-audit, pytest, runtime smoke, perf sample; CI on PRs & main

## Endpoints

- **`GET /health`** → `{ status:"ok", coordinate_system:"ecliptic_of_date", ... }`
- **`GET /info`** → toolkit version, kernels, `frame:"ECLIPDATE"`, `ecliptic_model:"IAU1980-mean"`
- **`POST /calculate`** → `positions{Sun…Saturn}` with `meta{ frame:"ECLIPDATE", abcorr:"LT+S", ayanamsa, topocentric:true, elapsed_ms }`

## Breaking/Behavior Notes

- **Longitudes are sidereal** (ecliptic-of-date rotated, then ayanāṁśa applied to longitude only)
- **Planets use barycenters** (DE440 standard). Sun/Moon are centers
- **CSPICE is not thread-safe** → run multi-process in production

## Deploy Quickstart

**Run multi-process:**
```bash
gunicorn services.spice.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 2 --bind 0.0.0.0:8000 --timeout 30
```

**Env:**
```bash
ALLOWED_ORIGINS=https://your-ui.example
# leave DISABLE_RATE_LIMIT unset/empty in prod
```

## Known Limits / Next

- **Coverage**: 1550–2650 CE (DE440). Out-of-range → SPKINSUFFDATA
- **Model**: IAU-1980 mean ecliptic-of-date. If you upgrade to IAU-2006 later, update goldens & announce
- **Future**: asteroids/comets ingestion, historical DE441 option, cache & metrics export

## Verification

- **CI**: QA workflow green on PRs & main (runtime smoke runs on main)
- **Nightly coverage probe** optional; UI page `/ephemeris` integration suggested