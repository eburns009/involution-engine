#!/bin/bash
# Comprehensive health check for Nominatim stack
# Usage: ./scripts/health_check.sh

set -e

NOMINATIM_URL="http://localhost:8080"
TIMEOUT=10

echo "🏥 Nominatim Stack Health Check"
echo "================================="

# 1. Check if containers are running
echo "1. Container Status:"
if docker-compose ps | grep -q "Up"; then
    echo "   ✅ Containers are running"
    docker-compose ps --format "table {{.Name}}\t{{.State}}\t{{.Ports}}"
else
    echo "   ❌ Containers not running"
    echo "   Run: docker-compose up -d"
    exit 1
fi

echo ""

# 2. Check Nominatim API health
echo "2. API Health:"
if curl -f -s --connect-timeout $TIMEOUT "$NOMINATIM_URL/status.php" >/dev/null; then
    echo "   ✅ API is responding"

    # Get detailed status
    STATUS=$(curl -s "$NOMINATIM_URL/status.php")
    echo "   📊 Status: $STATUS"
else
    echo "   ❌ API not responding"
    echo "   Check: docker-compose logs nominatim"
    exit 1
fi

echo ""

# 3. Test basic functionality
echo "3. Functionality Test:"
SEARCH_RESULT=$(curl -s "$NOMINATIM_URL/search?q=London&format=json&limit=1" || echo "[]")
if echo "$SEARCH_RESULT" | jq -e '.[0].place_id' >/dev/null 2>&1; then
    PLACE_ID=$(echo "$SEARCH_RESULT" | jq -r '.[0].place_id')
    LAT=$(echo "$SEARCH_RESULT" | jq -r '.[0].lat')
    LON=$(echo "$SEARCH_RESULT" | jq -r '.[0].lon')
    echo "   ✅ Search working (found place_id: $PLACE_ID)"

    # Test reverse geocoding
    REVERSE_RESULT=$(curl -s "$NOMINATIM_URL/reverse?lat=$LAT&lon=$LON&format=json" || echo "{}")
    if echo "$REVERSE_RESULT" | jq -e '.place_id' >/dev/null 2>&1; then
        echo "   ✅ Reverse geocoding working"
    else
        echo "   ⚠️  Reverse geocoding not working"
    fi
else
    echo "   ❌ Search not working (database may still be importing)"
    echo "   Check: docker-compose logs nominatim"
fi

echo ""

# 4. Check database size and replication status
echo "4. Database Status:"
DB_SIZE=$(docker-compose exec -T nominatim psql -d nominatim -t -c "SELECT pg_size_pretty(pg_database_size('nominatim'));" 2>/dev/null | xargs || echo "unknown")
echo "   📁 Database size: $DB_SIZE"

REPL_STATUS=$(docker-compose exec -T nominatim /app/nominatim replication --check 2>/dev/null || echo "Replication not configured")
echo "   🔄 Replication: $REPL_STATUS"

echo ""

# 5. Check recent logs for errors
echo "5. Recent Logs (last 10 lines):"
echo "   Nominatim:"
docker-compose logs --tail=5 nominatim | sed 's/^/     /'
echo "   Updater:"
docker-compose logs --tail=5 nominatim-updater | sed 's/^/     /'

echo ""

# 6. Performance metrics
echo "6. Performance Metrics:"
CONNECTIONS=$(docker-compose exec -T nominatim psql -d nominatim -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null | xargs || echo "unknown")
echo "   🔗 Active connections: $CONNECTIONS"

# Test search performance
echo "   ⏱️  Testing search performance..."
START_TIME=$(date +%s%N)
curl -s "$NOMINATIM_URL/search?q=Paris&format=json&limit=1" >/dev/null
END_TIME=$(date +%s%N)
DURATION_MS=$(( (END_TIME - START_TIME) / 1000000 ))
echo "   🚀 Search response time: ${DURATION_MS}ms"

echo ""
echo "✅ Health check complete!"

# Summary
if [ "$DURATION_MS" -lt 1000 ]; then
    PERF="🚀 Excellent"
elif [ "$DURATION_MS" -lt 3000 ]; then
    PERF="✅ Good"
else
    PERF="⚠️  Slow"
fi

echo ""
echo "📊 Summary:"
echo "   API Status: ✅ Online"
echo "   Database: $DB_SIZE"
echo "   Performance: $PERF (${DURATION_MS}ms)"
echo "   Replication: $REPL_STATUS"