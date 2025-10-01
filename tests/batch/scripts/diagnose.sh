#!/usr/bin/env bash
set -euo pipefail

OUTDIR="diagnostics"; mkdir -p "$OUTDIR"

echo "# Involution Engine – Full Diagnosis" > "$OUTDIR/report.md"
echo -e "\n## Repo" >> "$OUTDIR/report.md"
echo -n "branch: " >> "$OUTDIR/report.md"; git rev-parse --abbrev-ref HEAD >> "$OUTDIR/report.md"
echo -n "commit: " >> "$OUTDIR/report.md"; git rev-parse --short HEAD >> "$OUTDIR/report.md"

# 1) Inventory key files
echo -e "\n## File inventory" >> "$OUTDIR/report.md"
ls -lah services/spice | sed 's/^/    /' >> "$OUTDIR/report.md" || true
echo -e "\n### metakernel (involution.tm)" >> "$OUTDIR/report.md"
awk '{print "    " $0}' services/spice/kernels/involution.tm >> "$OUTDIR/report.md" || echo "    (missing)" >> "$OUTDIR/report.md"

# 2) Frame & API scan
echo -e "\n## Frame & API scan" >> "$OUTDIR/report.md"
echo '```' >> "$OUTDIR/report.md"
grep -nE 'ECLIPDATE|ECLIPJ2000|pxform\("J2000"|spkcpo\(|spkpos\(' -n services/spice/main.py || true >> "$OUTDIR/report.md"
echo '```' >> "$OUTDIR/report.md"

# 3) Kernel hygiene
echo -e "\n## Kernel hygiene" >> "$OUTDIR/report.md"
echo 'Tracked kernel binaries:' >> "$OUTDIR/report.md"
git ls-files | grep -E '^services/spice/kernels/(spk|pck|lsk)/' | sed 's/^/    /' >> "$OUTDIR/report.md" || echo "    (none tracked)" >> "$OUTDIR/report.md"

# 4) Environment & deps
echo -e "\n## Python env" >> "$OUTDIR/report.md"
python -V | sed 's/^/    /' >> "$OUTDIR/report.md" || true
pip -V | sed 's/^/    /' >> "$OUTDIR/report.md" || true

# 5) Quick QA (non-fatal on minor tools)
echo -e "\n## QA summary" >> "$OUTDIR/report.md"
python -m pip install -U pip >/dev/null 2>&1 || true
pip install -q ruff mypy bandit pip-audit pytest requests >/dev/null 2>&1 || true
[ -f services/spice/requirements.txt ] && pip install -q -r services/spice/requirements.txt >/dev/null 2>&1 || true

echo -n "ruff: " >> "$OUTDIR/report.md"; ruff check . >/dev/null && echo "ok" >> "$OUTDIR/report.md" || echo "issues" >> "$OUTDIR/report.md"
echo -n "mypy: " >> "$OUTDIR/report.md"; mypy services/spice >/dev/null && echo "ok" >> "$OUTDIR/report.md" || echo "issues" >> "$OUTDIR/report.md"
echo -n "bandit: " >> "$OUTDIR/report.md"; bandit -q -r services/spice -x "services/spice/test_*" && echo "ok" >> "$OUTDIR/report.md" || echo "issues" >> "$OUTDIR/report.md"
echo -n "pip-audit: " >> "$OUTDIR/report.md"; (pip-audit >/dev/null && echo "ok" || echo "vulns") >> "$OUTDIR/report.md"

# 6) Runtime smoke (headless)
echo -e "\n## Runtime smoke" >> "$OUTDIR/report.md"
if [ -x services/spice/download_kernels.sh ]; then
  bash services/spice/download_kernels.sh || true
fi

export DISABLE_RATE_LIMIT=1
python - <<'PY' > "$OUTDIR/runtime.json" 2> "$OUTDIR/runtime.err" || true
import json, os, time
import requests
from threading import Thread
from uvicorn import Config, Server
from services.spice.main import app

def run():
    config = Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = Server(config)
    server.run()

t = Thread(target=run, daemon=True); t.start()
# wait for boot
import socket, time
for _ in range(60):
    try:
        s=socket.create_connection(("127.0.0.1",8000),0.25); s.close(); break
    except: time.sleep(0.25)

base="http://127.0.0.1:8000"
r1 = requests.get(base+"/health", timeout=10); h = r1.json()
payload = {"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":50,"ayanamsa":"lahiri"}
r2 = requests.post(base+"/calculate", json=payload, timeout=20); c = r2.json()

print(json.dumps({"health":h,"calculate":c}, indent=2))
PY

echo '```json' >> "$OUTDIR/report.md"
sed 's/^/    /' "$OUTDIR/runtime.json" >> "$OUTDIR/report.md" || echo "    (runtime failed)" >> "$OUTDIR/report.md"
echo '```' >> "$OUTDIR/report.md"

# 7) Coverage probe (ET windows for key bodies)
echo -e "\n## SPK coverage (key bodies)" >> "$OUTDIR/report.md"
python - <<'PY' > "$OUTDIR/coverage.txt" 2>/dev/null || true
import spiceypy as spice
from pathlib import Path
mk = 'services/spice/kernels/involution.tm'
try:
    spice.kclear(); spice.furnsh(mk)
    bodies = [10,399,301,1,2,3,4,5,6]
    for i in range(spice.ktotal('SPK')):
        fn, *_ = spice.kdata(i,'SPK')
        ids = sorted(list(spice.spkobj(fn)))
        print(f"[SPK] {fn} -> {ids[:12]}{' ...' if len(ids)>12 else ''}")
    for b in bodies:
        found=False
        for i in range(spice.ktotal('SPK')):
            fn, *_ = spice.kdata(i,'SPK')
            try:
                win = spice.spkcov(fn, b)
                if win.card() > 0:
                    found=True
                    from math import floor
                    b0,e0 = spice.wnfetd(win,0)
                    print(f"body {b}: {spice.et2utc(b0,'ISOC',3)} -> {spice.et2utc(e0,'ISOC',3)} via {fn}")
                    break
            except Exception:
                pass
        if not found: print(f"body {b}: (no coverage)")
finally:
    spice.kclear()
PY
sed 's/^/    /' "$OUTDIR/coverage.txt" >> "$OUTDIR/report.md" || echo "    (coverage probe failed)" >> "$OUTDIR/report.md"

echo -e "\n## Conclusions (auto)" >> "$OUTDIR/report.md"
grep -q '"coordinate_system": "ecliptic_of_date"' "$OUTDIR/runtime.json" && echo "- Frame OK: ecliptic_of_date reported" >> "$OUTDIR/report.md" || echo "- Frame MISMATCH: not reporting ecliptic_of_date" >> "$OUTDIR/report.md"
grep -q '"frame": "ECLIPDATE"' "$OUTDIR/runtime.json" && echo "- Meta frame OK: ECLIPDATE" >> "$OUTDIR/report.md" || echo "- Meta frame MISMATCH" >> "$OUTDIR/report.md"
grep -q 'spkcpo' services/spice/main.py && echo "- Topocentric via spkcpo: YES" >> "$OUTDIR/report.md" || echo "- Topocentric via spkcpo: NO (check)" >> "$OUTDIR/report.md"

echo "Done. See $OUTDIR/report.md"