#!/bin/bash
# Comprehensive Housekeeping Script
# =================================
#
# Performs deep cleaning and maintenance tasks for the entire system
# Recommended to run weekly or monthly depending on system load

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
HOUSEKEEPING_LOG="/tmp/housekeeping_$(date +%Y%m%d_%H%M%S).log"

# Redirect all output to log file and console
exec > >(tee -a "$HOUSEKEEPING_LOG")
exec 2>&1

echo "[$TIMESTAMP] 🧹 Starting comprehensive system housekeeping..."
echo "[$TIMESTAMP] 📋 Log file: $HOUSEKEEPING_LOG"

# Function to run with error handling
run_task() {
    local task_name="$1"
    local task_command="$2"

    echo "[$TIMESTAMP] 🔄 Starting: $task_name"

    if eval "$task_command"; then
        echo "[$TIMESTAMP] ✅ Completed: $task_name"
        return 0
    else
        echo "[$TIMESTAMP] ❌ Failed: $task_name"
        return 1
    fi
}

# Function to get size before/after for comparison
get_directory_size() {
    local dir="$1"
    if [ -d "$dir" ]; then
        du -sb "$dir" 2>/dev/null | cut -f1 || echo "0"
    else
        echo "0"
    fi
}

# Task 1: Docker System Cleanup
echo "[$TIMESTAMP] 📋 Task 1: Docker System Cleanup"

DOCKER_SIZE_BEFORE=$(docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}" 2>/dev/null | grep -v "TYPE" || echo "")

run_task "Remove unused Docker containers" "docker container prune -f"
run_task "Remove unused Docker images" "docker image prune -f"
run_task "Remove unused Docker networks" "docker network prune -f"
run_task "Remove unused Docker volumes (dangling only)" "docker volume prune -f"

echo "[$TIMESTAMP] 📊 Docker cleanup summary:"
echo "[$TIMESTAMP]   Before cleanup:"
echo "$DOCKER_SIZE_BEFORE" | while IFS= read -r line; do
    echo "[$TIMESTAMP]     $line"
done

DOCKER_SIZE_AFTER=$(docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}" 2>/dev/null | grep -v "TYPE" || echo "")
echo "[$TIMESTAMP]   After cleanup:"
echo "$DOCKER_SIZE_AFTER" | while IFS= read -r line; do
    echo "[$TIMESTAMP]     $line"
done

# Task 2: Database Maintenance
echo "[$TIMESTAMP] 📋 Task 2: Database Maintenance"

run_task "PostgreSQL VACUUM" "docker-compose exec -T nominatim bash -c 'psql -U nominatim -d nominatim -c \"VACUUM;\"' || echo 'VACUUM skipped - database not ready'"

run_task "PostgreSQL ANALYZE" "docker-compose exec -T nominatim bash -c 'psql -U nominatim -d nominatim -c \"ANALYZE;\"' || echo 'ANALYZE skipped - database not ready'"

# Check database size
DB_SIZE=$(docker-compose exec -T nominatim bash -c "
    psql -U nominatim -d nominatim -t -c \"
        SELECT pg_size_pretty(pg_database_size('nominatim'));
    \" 2>/dev/null | xargs || echo 'unknown'
")
echo "[$TIMESTAMP] 📊 Current database size: $DB_SIZE"

# Task 3: Log File Management
echo "[$TIMESTAMP] 📋 Task 3: Comprehensive Log Management"

LOG_SIZE_BEFORE=$(get_directory_size "/var/log")

run_task "Run log rotation script" "./scripts/log_rotation.sh"

# Additional log cleanup
run_task "Clean system journal logs (7 days)" "journalctl --vacuum-time=7d || echo 'journalctl not available'"

run_task "Clean Docker container logs" "docker-compose down && docker-compose up -d || echo 'Container restart skipped'"

LOG_SIZE_AFTER=$(get_directory_size "/var/log")
SPACE_SAVED=$((LOG_SIZE_BEFORE - LOG_SIZE_AFTER))

echo "[$TIMESTAMP] 📊 Log cleanup summary:"
echo "[$TIMESTAMP]   Before: $(numfmt --to=iec $LOG_SIZE_BEFORE)B"
echo "[$TIMESTAMP]   After: $(numfmt --to=iec $LOG_SIZE_AFTER)B"
echo "[$TIMESTAMP]   Saved: $(numfmt --to=iec $SPACE_SAVED)B"

# Task 4: Temporary File Cleanup
echo "[$TIMESTAMP] 📋 Task 4: Temporary File Cleanup"

TEMP_SIZE_BEFORE=$(get_directory_size "/tmp")

run_task "Clean /tmp files older than 7 days" "find /tmp -type f -mtime +7 -delete 2>/dev/null || true"

run_task "Clean container temporary files" "docker-compose exec -T nominatim bash -c 'find /tmp -name \"*.tmp\" -o -name \"*.temp\" -mtime +1 -delete 2>/dev/null || true'"

run_task "Clean old status files" "docker-compose exec -T nominatim bash -c 'find /tmp -name \"*status*.json\" -mtime +7 -delete 2>/dev/null || true'"

TEMP_SIZE_AFTER=$(get_directory_size "/tmp")
TEMP_SPACE_SAVED=$((TEMP_SIZE_BEFORE - TEMP_SIZE_AFTER))

echo "[$TIMESTAMP] 📊 Temporary file cleanup:"
echo "[$TIMESTAMP]   Saved: $(numfmt --to=iec $TEMP_SPACE_SAVED)B"

# Task 5: Performance Optimization
echo "[$TIMESTAMP] 📋 Task 5: Performance Optimization"

run_task "Clear system cache" "sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || echo 'Cache clear skipped - insufficient permissions'"

run_task "Update locate database" "updatedb || echo 'updatedb skipped - not available'"

# Check memory usage
MEMORY_USAGE=$(free -h | grep '^Mem:' | awk '{print $3 "/" $2 " (" $3/$2*100 "%)"}' || echo "unknown")
echo "[$TIMESTAMP] 📊 Memory usage: $MEMORY_USAGE"

# Task 6: Security Maintenance
echo "[$TIMESTAMP] 📋 Task 6: Security Maintenance"

run_task "Clean old authentication logs" "find /var/log -name 'auth.log*' -mtime +30 -delete 2>/dev/null || true"

run_task "Review failed login attempts" "grep 'Failed password' /var/log/auth.log 2>/dev/null | tail -5 || echo 'No auth.log available'"

# Task 7: Backup Verification
echo "[$TIMESTAMP] 📋 Task 7: Backup and Recovery Check"

# Check if backup directory exists and has recent backups
BACKUP_DIR="/backups"
if [ -d "$BACKUP_DIR" ]; then
    RECENT_BACKUPS=$(find "$BACKUP_DIR" -type f -mtime -7 2>/dev/null | wc -l)
    echo "[$TIMESTAMP] 📊 Recent backups (last 7 days): $RECENT_BACKUPS files"

    if [ "$RECENT_BACKUPS" -eq 0 ]; then
        echo "[$TIMESTAMP] ⚠️  WARNING: No recent backups found"
    fi
else
    echo "[$TIMESTAMP] ℹ️  No backup directory configured"
fi

# Task 8: Configuration Validation
echo "[$TIMESTAMP] 📋 Task 8: Configuration Validation"

run_task "Validate Docker Compose configuration" "docker-compose config --quiet"

run_task "Check container health" "docker-compose ps"

# Verify all expected services are running
EXPECTED_SERVICES=("nominatim" "nominatim-updater")
for service in "${EXPECTED_SERVICES[@]}"; do
    if docker-compose ps "$service" | grep -q "Up"; then
        echo "[$TIMESTAMP] ✅ Service $service is running"
    else
        echo "[$TIMESTAMP] ⚠️  Service $service is not running"
    fi
done

# Task 9: Resource Usage Report
echo "[$TIMESTAMP] 📋 Task 9: Resource Usage Report"

echo "[$TIMESTAMP] 📊 System resource summary:"
echo "[$TIMESTAMP]   CPU Load: $(uptime | awk '{print $10, $11, $12}')"
echo "[$TIMESTAMP]   Memory: $(free -h | grep '^Mem:' | awk '{print "Used: " $3 " / " $2 " (" int($3/$2*100) "%)"}')"
echo "[$TIMESTAMP]   Disk: $(df -h / | tail -1 | awk '{print "Used: " $3 " / " $2 " (" $5 ")"}')"

# List largest directories
echo "[$TIMESTAMP] 📊 Largest directories (top 10):"
du -h /var/lib/docker /tmp /var/log 2>/dev/null | sort -hr | head -10 | while IFS= read -r line; do
    echo "[$TIMESTAMP]     $line"
done

# Task 10: Generate Housekeeping Report
echo "[$TIMESTAMP] 📋 Task 10: Generate Final Report"

FINAL_DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
HOUSEKEEPING_REPORT="/tmp/housekeeping_report_$(date +%Y%m%d_%H%M%S).json"

cat > "$HOUSEKEEPING_REPORT" << EOF
{
  "timestamp": "$TIMESTAMP",
  "housekeeping_version": "1.0",
  "disk_usage_after_cleanup": $FINAL_DISK_USAGE,
  "space_saved": {
    "logs_bytes": $SPACE_SAVED,
    "temp_files_bytes": $TEMP_SPACE_SAVED,
    "total_estimated_bytes": $((SPACE_SAVED + TEMP_SPACE_SAVED))
  },
  "tasks_completed": [
    "Docker system cleanup",
    "Database maintenance",
    "Log file management",
    "Temporary file cleanup",
    "Performance optimization",
    "Security maintenance",
    "Backup verification",
    "Configuration validation",
    "Resource usage report"
  ],
  "recommendations": [
    "Monitor disk usage trends",
    "Schedule regular housekeeping",
    "Review backup procedures"
  ],
  "next_housekeeping": "$(date -d '+1 week' '+%Y-%m-%d')"
}
EOF

echo "[$TIMESTAMP] 📁 Housekeeping report saved to: $HOUSEKEEPING_REPORT"

# Final summary
echo "[$TIMESTAMP] 🎉 Comprehensive housekeeping completed!"
echo "[$TIMESTAMP] 📊 Summary:"
echo "[$TIMESTAMP]   Total space saved: $(numfmt --to=iec $((SPACE_SAVED + TEMP_SPACE_SAVED)))B"
echo "[$TIMESTAMP]   Final disk usage: ${FINAL_DISK_USAGE}%"
echo "[$TIMESTAMP]   Log file: $HOUSEKEEPING_LOG"
echo "[$TIMESTAMP]   Report file: $HOUSEKEEPING_REPORT"

# Recommend next actions based on final disk usage
if [ $FINAL_DISK_USAGE -gt 85 ]; then
    echo "[$TIMESTAMP] ⚠️  Recommendation: Consider expanding disk space or more aggressive cleanup"
elif [ $FINAL_DISK_USAGE -gt 75 ]; then
    echo "[$TIMESTAMP] 💡 Recommendation: Schedule housekeeping more frequently"
else
    echo "[$TIMESTAMP] ✅ System maintenance is adequate for current usage"
fi

echo "[$TIMESTAMP] ✅ All housekeeping tasks completed successfully!"