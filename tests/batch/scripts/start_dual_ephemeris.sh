#!/usr/bin/env bash
# Start dual ephemeris services - Modern (DE440) + Historical (DE441)
set -euo pipefail

echo "==> Starting Dual Ephemeris Services"

# Ensure both kernels are downloaded
echo "==> Downloading DE440 kernels..."
KERNEL_SET_TAG=DE440 bash services/spice/download_kernels.sh

echo "==> Downloading DE441 kernels..."
KERNEL_SET_TAG=DE441 bash services/spice/download_kernels.sh

# Clean up any existing processes
pkill -f "uvicorn.*spice" || true
sleep 2

echo "==> Starting Modern ephemeris (DE440) on :8000"
METAKERNEL_PATH=services/spice/kernels/involution_de440.tm \
KERNEL_SET_TAG=DE440 \
ENVIRONMENT=production DEBUG=0 DISABLE_RATE_LIMIT=0 \
python -m uvicorn services.spice.main:app --host 127.0.0.1 --port 8000 &
DE440_PID=$!

echo "==> Starting Historical ephemeris (DE441) on :8001"
METAKERNEL_PATH=services/spice/kernels/involution_de441.tm \
KERNEL_SET_TAG=DE441 \
ENVIRONMENT=production DEBUG=0 DISABLE_RATE_LIMIT=0 \
python -m uvicorn services.spice.main:app --host 127.0.0.1 --port 8001 &
DE441_PID=$!

# Wait for services to start
sleep 5

echo "==> Testing services..."

# Test DE440 service
echo "Testing DE440 (port 8000)..."
if curl -fsS http://127.0.0.1:8000/health > /dev/null; then
    echo "✓ DE440 service healthy"
else
    echo "✗ DE440 service failed"
    kill $DE440_PID $DE441_PID 2>/dev/null || true
    exit 1
fi

# Test DE441 service
echo "Testing DE441 (port 8001)..."
if curl -fsS http://127.0.0.1:8001/health > /dev/null; then
    echo "✓ DE441 service healthy"
else
    echo "✗ DE441 service failed"
    kill $DE440_PID $DE441_PID 2>/dev/null || true
    exit 1
fi

# Show service info
echo ""
echo "🚀 Dual Ephemeris Services Running:"
echo "   Modern (DE440):     http://127.0.0.1:8000"
echo "   Historical (DE441): http://127.0.0.1:8001"
echo ""
echo "📊 Coverage:"
echo "   DE440: 1550-2650 CE (standard)"
echo "   DE441: 13201 BCE - 17191 CE (extended)"
echo ""
echo "💾 Disk Usage:"
echo "   DE440: ~114MB planetary ephemeris"
echo "   DE441: ~310MB planetary ephemeris"
echo ""
echo "🔄 To stop: pkill -f 'uvicorn.*spice'"
echo ""

# Save PIDs for cleanup
echo "$DE440_PID $DE441_PID" > /tmp/dual_ephemeris_pids

echo "✅ Dual ephemeris deployment complete"