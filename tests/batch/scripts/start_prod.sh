#!/usr/bin/env bash
set -euo pipefail

echo "==> Starting SPICE service in production mode"

# Load production environment
export ENVIRONMENT=production
export DEBUG=0
export DISABLE_RATE_LIMIT=0
export ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-"https://your-ui.example.com"}

# Ensure kernels are downloaded
echo "==> Checking SPICE kernels..."
if [ ! -f "services/spice/kernels/spk/planets/de440.bsp" ]; then
    echo "Downloading kernels..."
    cd services/spice
    ./download_kernels.sh
    cd ../..
else
    echo "Kernels already present"
fi

# Determine optimal worker count
WORKERS=${WORKERS:-$(($(nproc) * 2))}
echo "==> Starting with $WORKERS workers (2 per vCPU for CSPICE thread-safety)"

# Start production server
echo "==> Starting Gunicorn with Uvicorn workers..."
exec gunicorn services.spice.main:app \
    -k uvicorn.workers.UvicornWorker \
    --workers $WORKERS \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --preload=false \
    --max-requests 1000 \
    --max-requests-jitter 100