#!/bin/bash
# Nominatim Health Check Script
# =============================
#
# Performs comprehensive health checks and status monitoring

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
HEALTH_STATUS_FILE="/tmp/nominatim-health-status.json"
NOMINATIM_CMD="/usr/local/bin/nominatim"

echo "[$TIMESTAMP] 🔍 Starting Nominatim health check..."

# Initialize health status
START_TIME=$(date +%s)

# Function to update health status
update_health_status() {
    local overall_status="$1"
    local details="$2"
    local end_time=$(date '+%Y-%m-%d %H:%M:%S UTC')
    local end_timestamp=$(date +%s)

    cat > "$HEALTH_STATUS_FILE" << EOF
{
  "timestamp": "$end_time",
  "check_timestamp": $end_timestamp,
  "overall_status": "$overall_status",
  "checks": $details,
  "healthy": $([ "$overall_status" = "healthy" ] && echo "true" || echo "false")
}
EOF
}

# Array to store check results
declare -a checks=()

# Check 1: Database connectivity
echo "[$TIMESTAMP] 🔍 Checking database connectivity..."
DB_CHECK=$(timeout 10 $NOMINATIM_CMD admin --check-database 2>&1 || echo "DB_ERROR")
if echo "$DB_CHECK" | grep -q "DB_ERROR"; then
    checks+=('{"name": "database_connectivity", "status": "failed", "message": "Database connection failed", "details": "'$(echo "$DB_CHECK" | tr '"' "'" | head -1)'"}')
    echo "[$TIMESTAMP] ❌ Database connectivity: FAILED"
else
    checks+=('{"name": "database_connectivity", "status": "passed", "message": "Database connection successful", "details": "Connected and responsive"}')
    echo "[$TIMESTAMP] ✅ Database connectivity: OK"
fi

# Check 2: API endpoint responsiveness
echo "[$TIMESTAMP] 🔍 Checking API endpoint..."
API_CHECK=$(timeout 10 curl -s "http://localhost:8080/status.php" 2>/dev/null || echo "API_ERROR")
if [ "$API_CHECK" = "API_ERROR" ] || [ -z "$API_CHECK" ]; then
    checks+=('{"name": "api_endpoint", "status": "failed", "message": "API endpoint not responding", "details": "HTTP request failed or timed out"}')
    echo "[$TIMESTAMP] ❌ API endpoint: FAILED"
else
    checks+=('{"name": "api_endpoint", "status": "passed", "message": "API endpoint responsive", "details": "HTTP 200 OK received"}')
    echo "[$TIMESTAMP] ✅ API endpoint: OK"
fi

# Check 3: Replication status
echo "[$TIMESTAMP] 🔍 Checking replication status..."
REPL_CHECK=$($NOMINATIM_CMD replication --check-for-updates 2>&1 || echo "REPL_ERROR")
if echo "$REPL_CHECK" | grep -q "REPL_ERROR"; then
    checks+=('{"name": "replication_status", "status": "failed", "message": "Replication check failed", "details": "'$(echo "$REPL_CHECK" | tr '"' "'" | head -1)'"}')
    echo "[$TIMESTAMP] ❌ Replication status: FAILED"
else
    checks+=('{"name": "replication_status", "status": "passed", "message": "Replication system operational", "details": "'$(echo "$REPL_CHECK" | tr '"' "'" | head -1)'"}')
    echo "[$TIMESTAMP] ✅ Replication status: OK"
fi

# Check 4: Disk space
echo "[$TIMESTAMP] 🔍 Checking disk space..."
DISK_USAGE=$(df /var/lib/postgresql/14/main 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo "100")
if [ "$DISK_USAGE" -gt 90 ]; then
    checks+=('{"name": "disk_space", "status": "failed", "message": "Disk space critically low", "details": "Usage: '${DISK_USAGE}'% - above 90% threshold"}')
    echo "[$TIMESTAMP] ❌ Disk space: CRITICAL (${DISK_USAGE}%)"
elif [ "$DISK_USAGE" -gt 80 ]; then
    checks+=('{"name": "disk_space", "status": "warning", "message": "Disk space high", "details": "Usage: '${DISK_USAGE}'% - above 80% threshold"}')
    echo "[$TIMESTAMP] ⚠️  Disk space: WARNING (${DISK_USAGE}%)"
else
    checks+=('{"name": "disk_space", "status": "passed", "message": "Disk space OK", "details": "Usage: '${DISK_USAGE}'% - within normal limits"}')
    echo "[$TIMESTAMP] ✅ Disk space: OK (${DISK_USAGE}%)"
fi

# Check 5: Last update status
echo "[$TIMESTAMP] 🔍 Checking last update status..."
UPDATE_STATUS_FILE="/tmp/nominatim-last-update.json"
if [ -f "$UPDATE_STATUS_FILE" ]; then
    LAST_UPDATE_SUCCESS=$(cat "$UPDATE_STATUS_FILE" | grep '"success"' | grep -o 'true\|false' || echo "unknown")
    LAST_UPDATE_TIME=$(cat "$UPDATE_STATUS_FILE" | grep '"end_time"' | cut -d'"' -f4 || echo "unknown")

    if [ "$LAST_UPDATE_SUCCESS" = "true" ]; then
        checks+=('{"name": "last_update", "status": "passed", "message": "Last update successful", "details": "Completed: '${LAST_UPDATE_TIME}'"}')
        echo "[$TIMESTAMP] ✅ Last update: SUCCESS ($LAST_UPDATE_TIME)"
    else
        checks+=('{"name": "last_update", "status": "failed", "message": "Last update failed", "details": "Failed: '${LAST_UPDATE_TIME}'"}')
        echo "[$TIMESTAMP] ❌ Last update: FAILED ($LAST_UPDATE_TIME)"
    fi
else
    checks+=('{"name": "last_update", "status": "unknown", "message": "No update status available", "details": "Update status file not found"}')
    echo "[$TIMESTAMP] ⚠️  Last update: UNKNOWN (no status file)"
fi

# Check 6: Basic geocoding test
echo "[$TIMESTAMP] 🔍 Testing basic geocoding functionality..."
GEOCODE_TEST=$(timeout 10 curl -s "http://localhost:8080/search?q=Monaco&format=json&limit=1" 2>/dev/null || echo "GEOCODE_ERROR")
if [ "$GEOCODE_TEST" = "GEOCODE_ERROR" ] || [ "$GEOCODE_TEST" = "[]" ] || [ -z "$GEOCODE_TEST" ]; then
    checks+=('{"name": "geocoding_functionality", "status": "failed", "message": "Geocoding test failed", "details": "Monaco search returned no results or failed"}')
    echo "[$TIMESTAMP] ❌ Geocoding functionality: FAILED"
else
    checks+=('{"name": "geocoding_functionality", "status": "passed", "message": "Geocoding test successful", "details": "Monaco search returned valid results"}')
    echo "[$TIMESTAMP] ✅ Geocoding functionality: OK"
fi

# Determine overall status
failed_checks=$(printf '%s\n' "${checks[@]}" | grep '"status": "failed"' | wc -l)
warning_checks=$(printf '%s\n' "${checks[@]}" | grep '"status": "warning"' | wc -l)

if [ "$failed_checks" -gt 0 ]; then
    overall_status="unhealthy"
    echo "[$TIMESTAMP] 🚨 Overall status: UNHEALTHY ($failed_checks failures, $warning_checks warnings)"
elif [ "$warning_checks" -gt 0 ]; then
    overall_status="degraded"
    echo "[$TIMESTAMP] ⚠️  Overall status: DEGRADED ($warning_checks warnings)"
else
    overall_status="healthy"
    echo "[$TIMESTAMP] ✅ Overall status: HEALTHY"
fi

# Create JSON array from checks
checks_json="[$(IFS=','; echo "${checks[*]}")]"

# Update health status file
update_health_status "$overall_status" "$checks_json"

echo "[$TIMESTAMP] 📁 Health status saved to: $HEALTH_STATUS_FILE"
echo "[$TIMESTAMP] ✅ Health check complete!"

# Exit with appropriate code
if [ "$overall_status" = "unhealthy" ]; then
    exit 1
elif [ "$overall_status" = "degraded" ]; then
    exit 2
else
    exit 0
fi