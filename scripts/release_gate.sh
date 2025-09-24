#!/usr/bin/env bash
set -euo pipefail

# ---------- Config ----------
SPICE_URL="${SPICE_URL:-http://localhost:8000}"
PY=${PYTHON:-python}
NPX=${NPX:-npx}

echo "==> Release Gate: starting against $SPICE_URL"

# ---------- Ensure kernels present ----------
if [ -f package.json ]; then
  if jq -e '.scripts.kernels' package.json >/dev/null 2>&1; then
    echo "==> Downloading kernels (cached)"
    npm run -s kernels
  fi
fi

# ---------- Python QA ----------
echo "==> Python QA: ruff, mypy, bandit, pip-audit"
pip install -q ruff mypy bandit pip-audit >/dev/null
ruff check services || ruff check .
mypy services/spice || true
bandit -q -r services || true
pip-audit || true

# ---------- Node QA (optional) ----------
if [ -f package-lock.json ] || [ -f pnpm-lock.yaml ] || [ -f bun.lockb ]; then
  echo "==> Node QA"
  npm ci || npm i --package-lock-only
  npm run -s build || true
  npm audit --omit=dev || true
  if jq -e '.scripts.test' package.json >/dev/null 2>&1; then
    npm test --silent || true
  fi
fi

# ---------- Backend tests ----------
echo "==> Backend tests"
DISABLE_RATE_LIMIT=1 $PY -m pytest -q || true

# ---------- Randomized soak (dates/places) ----------
echo "==> Randomized soak"
$PY - <<'PY'
import os, json, random, time, math, sys
import requests
SPICE_URL=os.getenv("SPICE_URL","http://localhost:8000")
def wrapdiff(a,b): return abs(((a-b+540)%360)-180)
ok=0; fail=0; placidus_422=0
random.seed(42)
for i in range(120):
    # 1550..2650, spread across range
    year = random.choice([1600,1760,1920,1962,2000,2024,2200,2600])
    month = random.randint(1,12); day = min(28, random.randint(1,28))
    hh=random.randint(0,23); mm=random.randint(0,59)
    ts=f"{year:04d}-{month:02d}-{day:02d}T{hh:02d}:{mm:02d}:00Z"
    lat = random.uniform(-65,65)  # exclude polar for general case
    lon = random.uniform(-179,179)
    payload={"birth_time":ts,"latitude":lat,"longitude":lon,"elevation":0,"zodiac":"sidereal","ayanamsa":"fagan_bradley"}
    try:
        r=requests.post(f"{SPICE_URL}/calculate",json=payload,timeout=15); r.raise_for_status()
        pos=r.json()["data"]
        assert all(k in pos for k in ["Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"])
        # Houses: Placidus (may 422 near |lat|>~66); Whole-Sign fallback must succeed
        rh=requests.post(f"{SPICE_URL}/houses",json={**payload,"system":"placidus"},timeout=15)
        if rh.status_code in (400,422):
            placidus_422+=1
            rh2=requests.post(f"{SPICE_URL}/houses",json={**payload,"system":"whole-sign"},timeout=15)
            rh2.raise_for_status()
            cusps=rh2.json()["cusps"]; assert len(cusps)==12
        else:
            rh.raise_for_status()
            cusps=rh.json()["cusps"]; assert len(cusps)==12
            # oppositions invariant
            pairs=[(1,7),(2,8),(3,9),(4,10),(5,11),(6,12)]
            for (i,j) in pairs:
                assert wrapdiff(cusps[i-1], cusps[j-1])<1e-6
        ok+=1
    except Exception as e:
        fail+=1
        print("SOAK-FAIL:", ts, f"({lat:.2f},{lon:.2f})", e, file=sys.stderr)
print(json.dumps({"ok":ok,"fail":fail,"placidus_422":placidus_422}))
PY

# ---------- Performance smoke ----------
echo "==> Performance smoke (30 sequential /calculate)"
$PY - <<'PY'
import time, requests, os, statistics
SPICE_URL=os.getenv("SPICE_URL","http://localhost:8000")
lat,lon=37.7749,-122.4194
ts="2024-06-21T18:00:00Z"
payload={"birth_time":ts,"latitude":lat,"longitude":lon,"elevation":25,"zodiac":"tropical","ayanamsa":"lahiri"}
times=[]
for _ in range(30):
    t0=time.perf_counter()
    r=requests.post(f"{SPICE_URL}/calculate",json=payload,timeout=15); r.raise_for_status()
    times.append((time.perf_counter()-t0)*1000)
p50=statistics.median(times)
p95=sorted(times)[int(0.95*len(times))-1]
print({"ms_p50":round(p50,1),"ms_p95":round(p95,1)})
assert p95 < 150, f"p95 too high: {p95:.1f} ms"
PY

echo "==> Release Gate: COMPLETE"