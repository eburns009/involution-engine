#!/bin/bash
# Quick start script for Nominatim stack
# Usage: ./quick_start.sh [region]

set -e

REGION=${1:-monaco}

echo "🚀 Nominatim Stack Quick Start"
echo "==============================="
echo ""

echo "📦 Step 1: Download OSM data for $REGION..."
./scripts/download_data.sh "$REGION"
echo ""

echo "🐳 Step 2: Starting Docker containers..."
docker-compose up -d
echo ""

echo "⏳ Step 3: Waiting for import to complete..."
echo "   This may take a while depending on the region size:"
echo "   - Monaco: ~5 minutes"
echo "   - New York: ~30 minutes"
echo "   - California: ~2 hours"
echo "   - Germany: ~4 hours"
echo "   - US: ~12+ hours"
echo ""

echo "   Monitoring import progress..."
echo "   (Press Ctrl+C to stop monitoring, containers will continue)"
echo ""

# Monitor until ready
while true; do
    if curl -f -s http://localhost:8080/status.php >/dev/null 2>&1; then
        echo "✅ Import complete! API is ready."
        break
    else
        echo "   ⏳ Still importing... ($(date '+%H:%M:%S'))"
        sleep 30
    fi
done

echo ""
echo "🧪 Step 4: Running health check..."
./scripts/health_check.sh
echo ""

echo "🎉 Nominatim is ready!"
echo ""
echo "📍 Try these API calls:"
echo "   # Search for a place"
echo "   curl 'http://localhost:8080/search?q=London&format=json&limit=1'"
echo ""
echo "   # Reverse geocoding"
echo "   curl 'http://localhost:8080/reverse?lat=51.5074&lon=-0.1278&format=json'"
echo ""
echo "🔗 Integration with Time Resolver:"
echo "   ./scripts/integration_test.sh"
echo ""
echo "📖 Full documentation: README.md"