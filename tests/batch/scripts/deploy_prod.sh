#!/usr/bin/env bash
set -euo pipefail

echo "==> Production Deployment Script"
echo "==> Loading production environment..."

# Load production environment
export ENVIRONMENT=production
export DEBUG=0
export DISABLE_RATE_LIMIT=0
export ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-"https://your-ui.example.com"}
export RATE_LIMIT_STORAGE_URI=${RATE_LIMIT_STORAGE_URI:-"redis://your-redis:6379/0"}

echo "    ENVIRONMENT: $ENVIRONMENT"
echo "    DEBUG: $DEBUG"
echo "    DISABLE_RATE_LIMIT: $DISABLE_RATE_LIMIT"
echo "    ALLOWED_ORIGINS: $ALLOWED_ORIGINS"
echo "    RATE_LIMIT_STORAGE_URI: $RATE_LIMIT_STORAGE_URI"

echo "==> Downloading SPICE kernels..."
cd services/spice
./download_kernels.sh

echo "==> Running production validation..."
cd ../..

# Start server in background for testing (single worker for validation)
gunicorn services.spice.main:app -k uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:8000 --timeout 30 --daemon --pid /tmp/spice_test.pid
API_PID=$(cat /tmp/spice_test.pid)
sleep 5

# Test critical endpoints
echo "==> Testing /health endpoint..."
curl -fsS http://localhost:8000/health > /dev/null

echo "==> Testing /debug is blocked..."
if curl -s http://localhost:8000/debug | grep -q '"detail":"Not Found"'; then
    echo "    ✓ /debug properly blocked in production"
else
    echo "    ✗ /debug not properly blocked!"
    kill $API_PID
    exit 1
fi

echo "==> Testing calculation endpoint..."
curl -fsS -X POST http://localhost:8000/calculate \
  -H 'content-type: application/json' \
  -d '{"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":25,"zodiac":"tropical","ayanamsa":"lahiri"}' > /dev/null

# Clean up test server
kill $API_PID 2>/dev/null || true
rm -f /tmp/spice_test.pid

echo "==> ✅ Production validation complete!"
echo "==> Ready for deployment with:"
echo ""
echo "# Single-machine deployment (2 workers per vCPU):"
echo "gunicorn services.spice.main:app -k uvicorn.workers.UvicornWorker --workers \$((\$(nproc) * 2)) --bind 0.0.0.0:8000 --timeout 30"
echo ""
echo "# Or use configuration file:"
echo "gunicorn services.spice.main:app -c gunicorn.conf.py"
echo ""
echo "# For container deployments, set WORKERS environment variable:"
echo "export WORKERS=4  # Override auto-detection"
echo "gunicorn services.spice.main:app -c gunicorn.conf.py"