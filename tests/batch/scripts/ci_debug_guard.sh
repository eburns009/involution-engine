#!/usr/bin/env bash
# CI Guard: Ensure /debug endpoint is blocked in production
set -euo pipefail

echo "==> Testing /debug endpoint is blocked in production..."

# Start production server
ENVIRONMENT=production python -m uvicorn services.spice.main:app --host 127.0.0.1 --port 8000 &
PID=$!
sleep 3

# Test /debug endpoint
echo "==> Checking /debug endpoint..."
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/debug || true)

# Cleanup
kill $PID 2>/dev/null || true
sleep 1

# Verify /debug is blocked (404)
if [ "$code" = "404" ]; then
    echo "✓ /debug properly blocked in production (404)"
    exit 0
else
    echo "✗ ERROR: /debug exposed in production (got $code, expected 404)"
    exit 1
fi