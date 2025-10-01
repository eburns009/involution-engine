#!/bin/bash
# Performance Metrics Collection Script
# =====================================
#
# Collects comprehensive performance metrics for the entire system
# Generates historical data for performance analysis and optimization

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
EPOCH_TIME=$(date +%s)
METRICS_DIR="/tmp/metrics"
METRICS_FILE="$METRICS_DIR/performance_$(date +%Y%m%d_%H%M%S).json"

# Create metrics directory
mkdir -p "$METRICS_DIR"

echo "[$TIMESTAMP] 📊 Starting performance metrics collection..."

# Function to get container metrics
get_container_metrics() {
    local container_name="$1"

    if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
        # Get container stats
        local stats=$(docker stats "$container_name" --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" | tail -1)

        local cpu_percent=$(echo "$stats" | awk '{print $1}' | sed 's/%//')
        local memory_usage=$(echo "$stats" | awk '{print $2}')
        local memory_percent=$(echo "$stats" | awk '{print $3}' | sed 's/%//')
        local network_io=$(echo "$stats" | awk '{print $4}')
        local block_io=$(echo "$stats" | awk '{print $5}')

        # Get container health
        local health_status=$(docker inspect "$container_name" --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")

        cat << EOF
{
  "name": "$container_name",
  "cpu_percent": "${cpu_percent:-0}",
  "memory_usage": "$memory_usage",
  "memory_percent": "${memory_percent:-0}",
  "network_io": "$network_io",
  "block_io": "$block_io",
  "health_status": "$health_status",
  "running": true
}
EOF
    else
        cat << EOF
{
  "name": "$container_name",
  "running": false,
  "error": "Container not found"
}
EOF
    fi
}

# Function to test service response times
test_service_performance() {
    local service_name="$1"
    local url="$2"
    local endpoint="$3"

    echo "[$TIMESTAMP] 🔍 Testing $service_name performance..."

    local start_time=$(date +%s%3N)
    local http_code=""
    local response_time=""
    local error=""

    if response=$(curl -s -w "%{http_code}" -m 10 "$url$endpoint" 2>/dev/null); then
        local end_time=$(date +%s%3N)
        response_time=$((end_time - start_time))
        http_code=$(echo "$response" | tail -c 4)

        if [ "$http_code" -eq 200 ]; then
            echo "[$TIMESTAMP]   ✅ $service_name: ${response_time}ms (HTTP $http_code)"
        else
            echo "[$TIMESTAMP]   ⚠️  $service_name: ${response_time}ms (HTTP $http_code)"
            error="HTTP $http_code"
        fi
    else
        echo "[$TIMESTAMP]   ❌ $service_name: Connection failed"
        error="Connection failed"
        response_time=0
    fi

    cat << EOF
{
  "service": "$service_name",
  "url": "$url$endpoint",
  "response_time_ms": $response_time,
  "http_code": "${http_code:-0}",
  "status": "$([ "$http_code" = "200" ] && echo "healthy" || echo "unhealthy")",
  "error": "${error:-null}"
}
EOF
}

# Function to get database performance metrics
get_database_metrics() {
    echo "[$TIMESTAMP] 🗄️  Collecting database metrics..."

    local db_metrics=""

    # Try to get PostgreSQL stats
    if docker-compose exec -T nominatim psql -U nominatim -d nominatim -c "SELECT 1;" >/dev/null 2>&1; then
        # Get database size
        local db_size=$(docker-compose exec -T nominatim psql -U nominatim -d nominatim -t -c "
            SELECT pg_size_pretty(pg_database_size('nominatim'));
        " 2>/dev/null | xargs || echo "unknown")

        # Get connection count
        local connections=$(docker-compose exec -T nominatim psql -U nominatim -d nominatim -t -c "
            SELECT count(*) FROM pg_stat_activity;
        " 2>/dev/null | xargs || echo "0")

        # Get cache hit ratio
        local cache_hit_ratio=$(docker-compose exec -T nominatim psql -U nominatim -d nominatim -t -c "
            SELECT round(
                100.0 * sum(heap_blks_hit) /
                (sum(heap_blks_hit) + sum(heap_blks_read)), 2
            ) as cache_hit_ratio
            FROM pg_statio_user_tables;
        " 2>/dev/null | xargs || echo "0")

        # Test a simple query performance
        local query_start=$(date +%s%3N)
        docker-compose exec -T nominatim psql -U nominatim -d nominatim -c "SELECT COUNT(*) FROM import_status;" >/dev/null 2>&1 || true
        local query_end=$(date +%s%3N)
        local query_time=$((query_end - query_start))

        db_metrics='{
            "database_available": true,
            "database_size": "'"$db_size"'",
            "active_connections": '"$connections"',
            "cache_hit_ratio_percent": '"${cache_hit_ratio:-0}"',
            "test_query_ms": '"$query_time"'
        }'
    else
        db_metrics='{
            "database_available": false,
            "error": "Database connection failed"
        }'
    fi

    echo "$db_metrics"
}

# Function to get system performance metrics
get_system_metrics() {
    echo "[$TIMESTAMP] 💻 Collecting system metrics..."

    # CPU information
    local cpu_cores=$(nproc)
    local load_1min=$(uptime | awk '{print $(NF-2)}' | sed 's/,//')
    local load_5min=$(uptime | awk '{print $(NF-1)}' | sed 's/,//')
    local load_15min=$(uptime | awk '{print $NF}')

    # Memory information
    local memory_info=$(free -b | grep '^Mem:')
    local memory_total=$(echo "$memory_info" | awk '{print $2}')
    local memory_used=$(echo "$memory_info" | awk '{print $3}')
    local memory_free=$(echo "$memory_info" | awk '{print $4}')
    local memory_percent=$(awk "BEGIN {printf \"%.1f\", $memory_used/$memory_total*100}")

    # Disk information
    local disk_info=$(df / | tail -1)
    local disk_total=$(echo "$disk_info" | awk '{print $2}')
    local disk_used=$(echo "$disk_info" | awk '{print $3}')
    local disk_free=$(echo "$disk_info" | awk '{print $4}')
    local disk_percent=$(echo "$disk_info" | awk '{print $5}' | sed 's/%//')

    # Network information (if available)
    local network_interface=$(ip route | grep default | head -1 | awk '{print $5}' || echo "unknown")
    local network_rx_bytes=0
    local network_tx_bytes=0

    if [ "$network_interface" != "unknown" ] && [ -f "/sys/class/net/$network_interface/statistics/rx_bytes" ]; then
        network_rx_bytes=$(cat "/sys/class/net/$network_interface/statistics/rx_bytes" 2>/dev/null || echo "0")
        network_tx_bytes=$(cat "/sys/class/net/$network_interface/statistics/tx_bytes" 2>/dev/null || echo "0")
    fi

    cat << EOF
{
  "cpu": {
    "cores": $cpu_cores,
    "load_1min": $load_1min,
    "load_5min": $load_5min,
    "load_15min": $load_15min
  },
  "memory": {
    "total_bytes": $memory_total,
    "used_bytes": $memory_used,
    "free_bytes": $memory_free,
    "used_percent": $memory_percent
  },
  "disk": {
    "total_kb": $disk_total,
    "used_kb": $disk_used,
    "free_kb": $disk_free,
    "used_percent": $disk_percent
  },
  "network": {
    "interface": "$network_interface",
    "rx_bytes": $network_rx_bytes,
    "tx_bytes": $network_tx_bytes
  }
}
EOF
}

# Main metrics collection
echo "[$TIMESTAMP] 📋 Collecting comprehensive performance metrics..."

# 1. System metrics
echo "[$TIMESTAMP] Step 1: System performance"
SYSTEM_METRICS=$(get_system_metrics)

# 2. Container metrics
echo "[$TIMESTAMP] Step 2: Container performance"
NOMINATIM_METRICS=$(get_container_metrics "nominatim")
UPDATER_METRICS=$(get_container_metrics "nominatim-updater")

# 3. Service response times
echo "[$TIMESTAMP] Step 3: Service response times"
NOMINATIM_RESPONSE=$(test_service_performance "Nominatim" "http://localhost:8080" "/status.php")
GEOCODING_RESPONSE=$(test_service_performance "Geocoding Gateway" "http://localhost:8086" "/health")
TIME_RESOLVER_RESPONSE=$(test_service_performance "Time Resolver" "http://localhost:8082" "/health")
INTEGRATED_RESPONSE=$(test_service_performance "Integrated Service" "http://localhost:8087" "/health")

# 4. Database metrics
echo "[$TIMESTAMP] Step 4: Database performance"
DATABASE_METRICS=$(get_database_metrics)

# 5. Generate comprehensive metrics report
echo "[$TIMESTAMP] Step 5: Generate metrics report"

cat > "$METRICS_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "epoch_time": $EPOCH_TIME,
  "collection_version": "1.0",
  "system_metrics": $SYSTEM_METRICS,
  "container_metrics": [
    $NOMINATIM_METRICS,
    $UPDATER_METRICS
  ],
  "service_response_times": [
    $NOMINATIM_RESPONSE,
    $GEOCODING_RESPONSE,
    $TIME_RESOLVER_RESPONSE,
    $INTEGRATED_RESPONSE
  ],
  "database_metrics": $DATABASE_METRICS,
  "performance_summary": {
    "overall_health": "$([ "$(echo "$SYSTEM_METRICS" | grep -o '"used_percent": [0-9.]*' | cut -d' ' -f2 | cut -d. -f1)" -lt 85 ] && echo "good" || echo "degraded")",
    "critical_services_responding": $(echo "$NOMINATIM_RESPONSE $GEOCODING_RESPONSE" | grep -o '"status": "healthy"' | wc -l),
    "total_services_tested": 4
  }
}
EOF

echo "[$TIMESTAMP] 📁 Performance metrics saved to: $METRICS_FILE"

# 6. Generate performance trends (if historical data exists)
echo "[$TIMESTAMP] Step 6: Performance trends analysis"

HISTORICAL_FILES=$(find "$METRICS_DIR" -name "performance_*.json" -mtime -7 | wc -l)

if [ "$HISTORICAL_FILES" -gt 1 ]; then
    echo "[$TIMESTAMP] 📈 Analyzing trends from $HISTORICAL_FILES recent metrics files..."

    # Simple trend analysis - check if disk usage is increasing
    CURRENT_DISK=$(echo "$SYSTEM_METRICS" | grep -o '"used_percent": [0-9.]*' | cut -d' ' -f2)

    # Get disk usage from 24 hours ago (if available)
    YESTERDAY_FILE=$(find "$METRICS_DIR" -name "performance_*.json" -mtime -1 | head -1)

    if [ -n "$YESTERDAY_FILE" ]; then
        YESTERDAY_DISK=$(cat "$YESTERDAY_FILE" | grep -o '"used_percent": [0-9.]*' | cut -d' ' -f2 2>/dev/null || echo "$CURRENT_DISK")
        DISK_TREND=$(awk "BEGIN {print $CURRENT_DISK - $YESTERDAY_DISK}")

        echo "[$TIMESTAMP] 📊 Disk usage trend: ${DISK_TREND}% change in 24h"

        if awk "BEGIN {exit !($DISK_TREND > 5)}"; then
            echo "[$TIMESTAMP] ⚠️  WARNING: Rapid disk usage increase detected"
        fi
    fi
else
    echo "[$TIMESTAMP] ℹ️  Insufficient historical data for trend analysis"
fi

# 7. Clean up old metrics files (keep last 30 days)
echo "[$TIMESTAMP] Step 7: Metrics file cleanup"
find "$METRICS_DIR" -name "performance_*.json" -mtime +30 -delete 2>/dev/null || true

REMAINING_FILES=$(find "$METRICS_DIR" -name "performance_*.json" | wc -l)
echo "[$TIMESTAMP] 📁 Metrics files retained: $REMAINING_FILES"

# 8. Performance recommendations
echo "[$TIMESTAMP] Step 8: Performance recommendations"

CURRENT_DISK_USAGE=$(echo "$SYSTEM_METRICS" | grep -o '"used_percent": [0-9.]*' | cut -d' ' -f2 | cut -d. -f1)
CURRENT_MEMORY_USAGE=$(echo "$SYSTEM_METRICS" | grep -o '"used_percent": [0-9.]*' | cut -d' ' -f2 | cut -d. -f1)

echo "[$TIMESTAMP] 💡 Performance recommendations:"

if [ "$CURRENT_DISK_USAGE" -gt 80 ]; then
    echo "[$TIMESTAMP]   📀 Consider disk cleanup or expansion (${CURRENT_DISK_USAGE}% used)"
fi

if [ "$CURRENT_MEMORY_USAGE" -gt 85 ]; then
    echo "[$TIMESTAMP]   💾 Monitor memory usage (${CURRENT_MEMORY_USAGE}% used)"
fi

# Check service response times
SLOW_SERVICES=$(echo "$NOMINATIM_RESPONSE $GEOCODING_RESPONSE $TIME_RESOLVER_RESPONSE $INTEGRATED_RESPONSE" | grep -o '"response_time_ms": [0-9]*' | awk -F: '{if($2 > 2000) print "slow"}' | wc -l)

if [ "$SLOW_SERVICES" -gt 0 ]; then
    echo "[$TIMESTAMP]   🐌 $SLOW_SERVICES service(s) have slow response times (>2s)"
fi

echo "[$TIMESTAMP] ✅ Performance metrics collection completed!"
echo "[$TIMESTAMP] 📊 Summary:"
echo "[$TIMESTAMP]   Disk usage: ${CURRENT_DISK_USAGE}%"
echo "[$TIMESTAMP]   Memory usage: ${CURRENT_MEMORY_USAGE}%"
echo "[$TIMESTAMP]   Services responding: $(echo "$NOMINATIM_RESPONSE $GEOCODING_RESPONSE $TIME_RESOLVER_RESPONSE $INTEGRATED_RESPONSE" | grep -o '"status": "healthy"' | wc -l)/4"
echo "[$TIMESTAMP]   Metrics file: $METRICS_FILE"

# Exit with status based on overall health
if [ "$CURRENT_DISK_USAGE" -gt 90 ] || [ "$CURRENT_MEMORY_USAGE" -gt 90 ]; then
    echo "[$TIMESTAMP] ❌ Performance status: CRITICAL"
    exit 2
elif [ "$CURRENT_DISK_USAGE" -gt 80 ] || [ "$CURRENT_MEMORY_USAGE" -gt 80 ] || [ "$SLOW_SERVICES" -gt 1 ]; then
    echo "[$TIMESTAMP] ⚠️  Performance status: WARNING"
    exit 1
else
    echo "[$TIMESTAMP] ✅ Performance status: GOOD"
    exit 0
fi