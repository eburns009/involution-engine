#!/bin/bash
# Disk Space Monitoring and Alert Script
# ======================================
#
# Monitors disk usage and sends alerts when thresholds are exceeded
# Can be configured to run periodically for proactive monitoring

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
ALERT_FILE="/tmp/disk_alerts.json"
WARNING_THRESHOLD=80
CRITICAL_THRESHOLD=90

echo "[$TIMESTAMP] 💿 Starting disk space monitoring..."

# Function to check disk usage for a mount point
check_disk_usage() {
    local mount_point="$1"
    local usage_info=$(df "$mount_point" | tail -1)
    local usage_percent=$(echo "$usage_info" | awk '{print $5}' | sed 's/%//')
    local available=$(echo "$usage_info" | awk '{print $4}')
    local available_human=$(echo "$usage_info" | awk '{print $4}' | numfmt --to=iec-i --suffix=B --from-unit=1024)
    local total=$(echo "$usage_info" | awk '{print $2}')
    local total_human=$(echo "$usage_info" | awk '{print $2}' | numfmt --to=iec-i --suffix=B --from-unit=1024)

    echo "[$TIMESTAMP] 📊 $mount_point: ${usage_percent}% used (${available_human} of ${total_human} available)"

    # Determine alert level
    local alert_level="ok"
    local message=""

    if [ $usage_percent -ge $CRITICAL_THRESHOLD ]; then
        alert_level="critical"
        message="CRITICAL: Disk usage ${usage_percent}% >= ${CRITICAL_THRESHOLD}% threshold"
        echo "[$TIMESTAMP] 🚨 $message"
    elif [ $usage_percent -ge $WARNING_THRESHOLD ]; then
        alert_level="warning"
        message="WARNING: Disk usage ${usage_percent}% >= ${WARNING_THRESHOLD}% threshold"
        echo "[$TIMESTAMP] ⚠️  $message"
    else
        message="Disk usage within normal limits"
        echo "[$TIMESTAMP] ✅ $message"
    fi

    # Return structured data
    cat << EOF
{
  "mount_point": "$mount_point",
  "usage_percent": $usage_percent,
  "available_bytes": $available,
  "available_human": "$available_human",
  "total_bytes": $total,
  "total_human": "$total_human",
  "alert_level": "$alert_level",
  "message": "$message",
  "timestamp": "$TIMESTAMP"
}
EOF
}

# Function to check Docker volumes disk usage
check_docker_volumes() {
    echo "[$TIMESTAMP] 🐳 Checking Docker volume usage..."

    if command -v docker >/dev/null 2>&1; then
        # Check Docker system disk usage
        local docker_info=$(docker system df 2>/dev/null || echo "Error getting Docker disk usage")

        if [[ "$docker_info" != "Error"* ]]; then
            echo "[$TIMESTAMP] 📋 Docker system disk usage:"
            echo "$docker_info" | while IFS= read -r line; do
                echo "[$TIMESTAMP]   $line"
            done

            # Get specific volume sizes
            echo "[$TIMESTAMP] 📦 Docker volume details:"
            docker volume ls --format "table {{.Driver}}\t{{.Name}}" | tail -n +2 | while read -r driver volume_name; do
                if [ -n "$volume_name" ]; then
                    # Try to get volume size (may not work on all systems)
                    local volume_path=$(docker volume inspect "$volume_name" --format '{{.Mountpoint}}' 2>/dev/null || echo "unknown")
                    if [ "$volume_path" != "unknown" ] && [ -d "$volume_path" ]; then
                        local volume_size=$(du -sh "$volume_path" 2>/dev/null | cut -f1 || echo "unknown")
                        echo "[$TIMESTAMP]     $volume_name: $volume_size"
                    else
                        echo "[$TIMESTAMP]     $volume_name: (size unknown)"
                    fi
                fi
            done
        else
            echo "[$TIMESTAMP] ⚠️  Could not get Docker disk usage information"
        fi
    else
        echo "[$TIMESTAMP] ⚠️  Docker not available"
    fi
}

# Function to check specific database disk usage
check_database_usage() {
    echo "[$TIMESTAMP] 🗄️  Checking database disk usage..."

    # Check PostgreSQL data directory size
    local pg_data_size=$(docker-compose exec -T nominatim bash -c "
        if [ -d /var/lib/postgresql/14/main ]; then
            du -sh /var/lib/postgresql/14/main 2>/dev/null | cut -f1
        else
            echo 'unknown'
        fi
    " 2>/dev/null || echo "unknown")

    echo "[$TIMESTAMP]   PostgreSQL data: $pg_data_size"

    # Check nominatim-specific data
    local nominatim_data_size=$(docker-compose exec -T nominatim bash -c "
        if [ -d /nominatim/data ]; then
            du -sh /nominatim/data 2>/dev/null | cut -f1
        else
            echo 'unknown'
        fi
    " 2>/dev/null || echo "unknown")

    echo "[$TIMESTAMP]   Nominatim data: $nominatim_data_size"

    # Check temporary files
    local temp_size=$(docker-compose exec -T nominatim bash -c "
        du -sh /tmp 2>/dev/null | cut -f1
    " 2>/dev/null || echo "unknown")

    echo "[$TIMESTAMP]   Temporary files: $temp_size"
}

# Function to generate comprehensive alert report
generate_alert_report() {
    local root_disk_data="$1"

    cat << EOF > "$ALERT_FILE"
{
  "timestamp": "$TIMESTAMP",
  "monitoring_version": "1.0",
  "disk_checks": {
    "root_filesystem": $root_disk_data
  },
  "thresholds": {
    "warning_percent": $WARNING_THRESHOLD,
    "critical_percent": $CRITICAL_THRESHOLD
  },
  "recommendations": []
}
EOF

    # Add recommendations based on usage
    local usage_percent=$(echo "$root_disk_data" | grep -o '"usage_percent": [0-9]*' | cut -d' ' -f2)

    if [ "$usage_percent" -ge $CRITICAL_THRESHOLD ]; then
        # Add critical recommendations
        local temp_recommendations='["Run log cleanup immediately", "Consider expanding disk space", "Remove unnecessary Docker images", "Check for large temporary files"]'
        sed -i "s/\"recommendations\": \[\]/\"recommendations\": $temp_recommendations/" "$ALERT_FILE"
    elif [ "$usage_percent" -ge $WARNING_THRESHOLD ]; then
        # Add warning recommendations
        local temp_recommendations='["Schedule log cleanup", "Monitor disk usage trends", "Review Docker image cleanup"]'
        sed -i "s/\"recommendations\": \[\]/\"recommendations\": $temp_recommendations/" "$ALERT_FILE"
    fi

    echo "[$TIMESTAMP] 📁 Alert report saved to: $ALERT_FILE"
}

# Function to suggest cleanup actions
suggest_cleanup_actions() {
    local usage_percent="$1"

    echo "[$TIMESTAMP] 💡 Disk usage recommendations:"

    if [ $usage_percent -ge $CRITICAL_THRESHOLD ]; then
        echo "[$TIMESTAMP]   🚨 IMMEDIATE ACTIONS REQUIRED:"
        echo "[$TIMESTAMP]     1. Run log cleanup: ./scripts/log_rotation.sh"
        echo "[$TIMESTAMP]     2. Clean Docker: docker system prune -f"
        echo "[$TIMESTAMP]     3. Remove old images: docker image prune -f"
        echo "[$TIMESTAMP]     4. Check large files: find / -size +100M -type f 2>/dev/null | head -10"
    elif [ $usage_percent -ge $WARNING_THRESHOLD ]; then
        echo "[$TIMESTAMP]   ⚠️  RECOMMENDED ACTIONS:"
        echo "[$TIMESTAMP]     1. Schedule log cleanup for tonight"
        echo "[$TIMESTAMP]     2. Review Docker image usage: docker images"
        echo "[$TIMESTAMP]     3. Monitor growth trends"
    else
        echo "[$TIMESTAMP]   ✅ No immediate action required"
        echo "[$TIMESTAMP]     • Continue regular monitoring"
        echo "[$TIMESTAMP]     • Scheduled cleanup will maintain space"
    fi
}

# Main monitoring workflow
echo "[$TIMESTAMP] 🔍 Starting comprehensive disk monitoring..."

# 1. Check main filesystem
echo "[$TIMESTAMP] 📋 Step 1: Main filesystem check"
ROOT_DISK_DATA=$(check_disk_usage "/")

# 2. Check Docker usage
echo "[$TIMESTAMP] 📋 Step 2: Docker system check"
check_docker_volumes

# 3. Check database-specific usage
echo "[$TIMESTAMP] 📋 Step 3: Database storage check"
check_database_usage

# 4. Generate alert report
echo "[$TIMESTAMP] 📋 Step 4: Generate monitoring report"
generate_alert_report "$ROOT_DISK_DATA"

# 5. Extract usage for recommendations
CURRENT_USAGE=$(echo "$ROOT_DISK_DATA" | grep -o '"usage_percent": [0-9]*' | cut -d' ' -f2)

# 6. Provide recommendations
echo "[$TIMESTAMP] 📋 Step 5: Usage recommendations"
suggest_cleanup_actions "$CURRENT_USAGE"

# 7. Exit with appropriate code for monitoring systems
echo "[$TIMESTAMP] 📋 Step 6: Set monitoring exit code"

if [ $CURRENT_USAGE -ge $CRITICAL_THRESHOLD ]; then
    echo "[$TIMESTAMP] ❌ Disk monitoring result: CRITICAL (exit code 2)"
    exit 2
elif [ $CURRENT_USAGE -ge $WARNING_THRESHOLD ]; then
    echo "[$TIMESTAMP] ⚠️  Disk monitoring result: WARNING (exit code 1)"
    exit 1
else
    echo "[$TIMESTAMP] ✅ Disk monitoring result: OK (exit code 0)"
    exit 0
fi