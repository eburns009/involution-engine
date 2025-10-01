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
if [ -f services/spice/requirements.txt ]; then
  pip install -q -r services/spice/requirements.txt
fi

ruff check .
mypy services/spice
bandit -q -r services/spice -x "services/spice/test_*"
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

# -------- Git hygiene: large files; ensure kernels not tracked --------
echo "== Git Hygiene =="
git rev-list --objects --all | sort -k2 > .git-objects.txt
awk '{print $1}' .git-objects.txt | while read O; do
  S=$(git cat-file -s "$O" 2>/dev/null || echo 0)
  if [ "$S" -ge $((50*1024*1024)) ]; then
    echo "WARNING: large object detected (~$(awk "BEGIN{printf \"%.2f\", $S/1024/1024}") MB) -> $O"
  fi
done

if git ls-files | grep -E '^services/spice/kernels/(spk|pck|lsk)/' >/dev/null; then
  echo "ERROR: SPICE kernel binaries are tracked in Git. Remove them and rely on the downloader."
  exit 1
fi
echo

# -------- Runtime smoke & perf sample (skippable) --------
if [ "${QA_SKIP_RUNTIME:-0}" = "1" ]; then
  echo "== Runtime Smoke == (skipped on PRs)"
  echo "✅ Comprehensive QA completed (runtime skipped)."
  exit 0
fi

echo "== Runtime Smoke =="
if [ -x services/spice/download_kernels.sh ]; then
  bash services/spice/download_kernels.sh
fi

export DISABLE_RATE_LIMIT=1
export PYTHONUNBUFFERED=1

PY_APP="services.spice.main:app"
uvicorn "$PY_APP" --host 127.0.0.1 --port 8000 --log-level warning &
UV_PID=$!

# Wait for boot (max 30s)
for i in {1..30}; do
  if curl -s http://127.0.0.1:8000/health >/dev/null; then break; fi
  sleep 1
done

echo "-- /health --"
if command -v jq >/dev/null 2>&1; then
  curl -s http://127.0.0.1:8000/health | jq .
else
  curl -s http://127.0.0.1:8000/health
fi

echo "-- /calculate (smoke) --"
REQ='{"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":50,"ayanamsa":"lahiri"}'
curl -s -X POST http://127.0.0.1:8000/calculate -H 'content-type: application/json' -d "$REQ" >/dev/null || {
  echo "ERROR: /calculate failed"; kill "$UV_PID" 2>/dev/null || true; exit 1;
}

# Perf sample: 20 calls; naive P95
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
if [ "$P95" -gt 300 ]; then
  echo "WARNING: local P95 > 300ms (investigate cache, CPU throttling, or build type)."
fi

kill "$UV_PID" >/dev/null 2>&1 || true
wait "$UV_PID" 2>/dev/null || true
echo
echo "✅ Comprehensive QA completed."
