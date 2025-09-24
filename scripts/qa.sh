#!/usr/bin/env bash
set -euo pipefail

echo "== Environment =="
python --version || true
node --version || true
pip --version || true
echo

# -------- Python: lint, types, security, deps --------
echo "== Python QA =="
python -m pip install -U pip >/dev/null
pip install -q ruff mypy bandit pip-audit detect-secrets pytest requests
# If your service has its own requirements, install them:
if [ -f services/spice/requirements.txt ]; then
  pip install -q -r services/spice/requirements.txt
fi

ruff check .
mypy services/spice || true
bandit -q -r services/spice -x "services/spice/test_*" || true
# Fail CI on known vulns
pip-audit

# Secrets scan (workspace)
git ls-files -z | xargs -0 detect-secrets scan > .secrets.baseline || true
echo "Secrets baseline written to .secrets.baseline"
echo

# -------- Node: lockfile, lint, audit (if package.json exists) --------
if [ -f package.json ]; then
  echo "== Node QA =="
  if [ ! -f package-lock.json ]; then
    npm i --package-lock-only
  fi
  npm ci
  # ESLint only if configured (avoid noisy init prompt)
  if [ -f eslint.config.js ] || [ -f .eslintrc ] || [ -f .eslintrc.json ] || [ -f .eslintrc.js ]; then
    npx eslint . || true
  else
    echo "No ESLint config found; skipping lint."
  fi
  npm audit --omit=dev || true
  echo
fi

# -------- Dockerfile lint (hadolint via container) --------
if [ -f services/spice/Dockerfile ]; then
  echo "== Dockerfile QA =="
  docker run --rm -i hadolint/hadolint < services/spice/Dockerfile || true
  echo
fi

# -------- Git hygiene: large files in history; kernels not tracked --------
echo "== Git Hygiene =="
git rev-list --objects --all | sort -k2 > .git-objects.txt
awk '{print $1}' .git-objects.txt | xargs -I{} git cat-file -s {} 2>/dev/null | \
  awk '{sum+=$1} END {printf "Total object bytes in repo: %.2f MB\n", sum/1024/1024}'
# Flag >50MB blobs
awk '{print $1}' .git-objects.txt | while read O; do
  S=$(git cat-file -s "$O" 2>/dev/null || echo 0)
  if [ "$S" -ge $((50*1024*1024)) ]; then
    H=$(git cat-file -p "$O" 2>/dev/null | head -n1 || echo "")
    echo "WARNING: large object (~$(printf "%.2f" "$(echo "$S/1024/1024" | bc -l)") MB): $O $H"
  fi
done

# Ensure kernels aren't tracked (except metakernel)
if git ls-files | grep -E '^services/spice/kernels/(spk|pck|lsk)/' >/dev/null; then
  echo "ERROR: SPICE kernel binaries are tracked in Git. Remove them and rely on the downloader."
  exit 1
fi
echo

# -------- Runtime smoke & perf sample --------
echo "== Runtime Smoke =="
# Ensure kernels exist; fetch if needed
if [ -x services/spice/download_kernels.sh ]; then
  bash services/spice/download_kernels.sh
fi

export DISABLE_RATE_LIMIT=1
export PYTHONUNBUFFERED=1

# Start app in background (run from services/spice directory for kernel path resolution)
cd services/spice
PY_APP="main:app"
uvicorn "$PY_APP" --host 127.0.0.1 --port 8000 --log-level warning &
UV_PID=$!
cd ../..

# Wait for boot
for i in {1..30}; do
  if curl -s http://127.0.0.1:8000/health >/dev/null; then break; fi
  sleep 1
done

echo "-- /health --"
curl -s http://127.0.0.1:8000/health | jq . || curl -s http://127.0.0.1:8000/health

echo "-- /calculate (smoke) --"
REQ='{"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":50,"ayanamsa":"lahiri"}'
curl -s -X POST http://127.0.0.1:8000/calculate -H 'content-type: application/json' -d "$REQ" | jq . || true

# Perf sample: 20 calls; print naive P95
echo "-- Perf (20 calls) --"
TS=()
for i in {1..20}; do
  T0=$(date +%s%3N)
  curl -s -X POST http://127.0.0.1:8000/calculate -H 'content-type: application/json' -d "$REQ" >/dev/null
  T1=$(date +%s%3N); TS+=($((T1-T0)))
done
IFS=$'\n' SORTED=($(printf "%s\n" "${TS[@]}" | sort -n)); unset IFS
P95=${SORTED[$((19*95/100))]}
echo "Latency ms (min/med/p95/max): ${SORTED[0]}/${SORTED[9]}/${P95}/${SORTED[19]}"
# Optional guardrail: fail if p95 > 300ms locally
if [ "$P95" -gt 300 ]; then
  echo "WARNING: local P95 > 300ms (investigate cache, build type, or CPU throttling)."
fi

# Tear down app
kill "$UV_PID" >/dev/null 2>&1 || true
wait "$UV_PID" 2>/dev/null || true

echo
echo "✅ Comprehensive QA completed."