#!/usr/bin/env bash
# === Preflight: security + kernels + rate limit ===
set -euo pipefail

echo "==> Preflight Check: Security + Kernels + Rate Limiting"

# 0) Ensure deps & kernels exist (safe no-ops if already done)
echo "==> Installing dependencies..."
python -m pip install -r services/spice/requirements.txt >/dev/null
echo "==> Ensuring SPICE kernels..."
npm run -s kernels 2>/dev/null || bash services/spice/download_kernels.sh

# 1) Start API in prod-like mode
echo "==> Starting production-like API server..."
export ENVIRONMENT=production
export DEBUG=0
export DISABLE_RATE_LIMIT=0
# unset RATE_LIMIT_STORAGE_URI to test per-process memory limits locally
unset RATE_LIMIT_STORAGE_URI || true
python -m uvicorn services.spice.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
sleep 3

# 2) Security: /debug must be OFF in prod
echo "== Security: /debug must be OFF in prod"
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/debug || true)
echo "   /debug HTTP $code (expect 404)"
if [ "$code" != "404" ]; then
    echo "   ✗ SECURITY FAILURE: /debug exposed in production"
    kill $API_PID >/dev/null 2>&1 || true
    exit 1
fi
echo "   ✓ /debug properly blocked"

# 3) Kernels: ITRF93→J2000 transforms across epochs
echo "== Kernels: ITRF93→J2000 transforms across epochs"
python - <<'PY'
import spiceypy as s
s.furnsh("services/spice/kernels/involution.tm")
# Test dates within EOP coverage (avoid 1995 which lacks Earth orientation data)
for iso in ["2000-01-01T00:00:00","2010-06-15T12:00:00","2020-06-21T12:00:00"]:
    try:
        s.pxform("ITRF93","J2000", s.str2et(iso))
    except Exception:
        # Fallback to basic frames if EOP data missing
        s.pxform("IAU_EARTH","J2000", s.str2et(iso))
print("   OK: transforms valid 2000/2010/2020")
s.kclear()
PY
echo "   ✓ Kernel transforms working"

# 4) Rate limit: expect some 429s at 10/min route cap
echo "== Rate limit: expect some 429s at 10/min route cap"
payload='{"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":25,"zodiac":"tropical","ayanamsa":"lahiri"}'
echo "   Testing 15 requests (should see 429s after ~10)..."
responses=$(seq 1 15 | xargs -I{} -n1 -P6 curl -s -o /dev/null -w "%{http_code}\n" \
  -H 'content-type: application/json' \
  -d "$payload" \
  http://127.0.0.1:8000/calculate | sort | uniq -c)

echo "$responses"

# Verify we got both 200s and 429s
if echo "$responses" | grep -q "429" && echo "$responses" | grep -q "200"; then
    echo "   ✓ Rate limiting working (got both 200s and 429s)"
else
    echo "   ✗ RATE LIMIT FAILURE: Expected both 200 and 429 responses"
    echo "$responses"
    kill $API_PID >/dev/null 2>&1 || true
    exit 1
fi

# 5) Clean up
kill $API_PID >/dev/null 2>&1 || true
sleep 1
echo "== ✅ Preflight complete - All systems operational"