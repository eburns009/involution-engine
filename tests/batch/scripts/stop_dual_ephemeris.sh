#!/usr/bin/env bash
# Stop dual ephemeris services
set -euo pipefail

echo "==> Stopping Dual Ephemeris Services"

# Kill all uvicorn spice processes
if pkill -f "uvicorn.*spice"; then
    echo "✓ Services stopped"
else
    echo "ℹ️  No running services found"
fi

# Clean up PID file
rm -f /tmp/dual_ephemeris_pids

# Wait for cleanup
sleep 2

# Verify ports are free
for port in 8000 8001; do
    if lsof -ti:$port > /dev/null 2>&1; then
        echo "⚠️  Port $port still in use"
    else
        echo "✓ Port $port available"
    fi
done

echo "✅ Dual ephemeris services stopped"