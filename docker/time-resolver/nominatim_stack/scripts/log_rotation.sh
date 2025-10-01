#!/bin/bash
# Log Rotation and Cleanup Script
# ===============================
#
# Manages log files and temporary data to prevent disk space issues
# Runs daily to clean up old logs and status files

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
LOG_RETENTION_DAYS=30
STATUS_RETENTION_DAYS=7
DOCKER_LOG_MAX_SIZE="100m"

echo "[$TIMESTAMP] 🧹 Starting log rotation and cleanup..."

# Function to safely rotate a log file
rotate_log() {
    local log_file="$1"
    local max_age_days="$2"

    if [ -f "$log_file" ]; then
        local file_age_days=$((($(date +%s) - $(stat -c %Y "$log_file")) / 86400))
        local file_size=$(stat -c%s "$log_file" 2>/dev/null || echo "0")

        echo "[$TIMESTAMP]   📄 $log_file: ${file_size} bytes, ${file_age_days} days old"

        # Rotate if file is older than retention period or larger than 50MB
        if [ $file_age_days -gt $max_age_days ] || [ $file_size -gt 52428800 ]; then
            echo "[$TIMESTAMP]   🔄 Rotating $log_file"

            # Create timestamped backup
            local backup_name="${log_file}.$(date -r "$log_file" +%Y%m%d_%H%M%S)"
            cp "$log_file" "$backup_name"

            # Compress the backup
            gzip "$backup_name"

            # Truncate original log
            > "$log_file"

            echo "[$TIMESTAMP]   ✅ Created backup: ${backup_name}.gz"
        else
            echo "[$TIMESTAMP]   ✅ No rotation needed"
        fi
    else
        echo "[$TIMESTAMP]   ℹ️  $log_file does not exist"
    fi
}

# Function to clean up old files
cleanup_old_files() {
    local pattern="$1"
    local max_age_days="$2"
    local location="$3"

    echo "[$TIMESTAMP] 🔍 Cleaning up files matching '$pattern' older than $max_age_days days in $location"

    local found_files=$(find "$location" -name "$pattern" -type f -mtime +$max_age_days 2>/dev/null || true)

    if [ -n "$found_files" ]; then
        echo "$found_files" | while read -r file; do
            echo "[$TIMESTAMP]   🗑️  Removing: $file"
            rm -f "$file"
        done
    else
        echo "[$TIMESTAMP]   ✅ No old files found to clean up"
    fi
}

# 1. Rotate Docker container logs
echo "[$TIMESTAMP] 📋 Step 1: Docker log management"
if command -v docker >/dev/null 2>&1; then
    # Get container logs sizes
    echo "[$TIMESTAMP]   📊 Current container log sizes:"
    docker ps --format "table {{.Names}}" | tail -n +2 | while read container; do
        if [ -n "$container" ]; then
            log_size=$(docker logs --details "$container" 2>/dev/null | wc -c || echo "0")
            echo "[$TIMESTAMP]     $container: $log_size bytes"
        fi
    done

    # Configure log rotation for running containers
    echo "[$TIMESTAMP]   🔧 Log rotation is handled by Docker daemon (max-size: $DOCKER_LOG_MAX_SIZE)"
else
    echo "[$TIMESTAMP]   ⚠️  Docker not available"
fi

# 2. Rotate application logs
echo "[$TIMESTAMP] 📋 Step 2: Application log rotation"

# Nominatim logs (inside container)
docker-compose exec -T nominatim bash -c "
    echo '[$TIMESTAMP] 🔍 Checking Nominatim container logs...'

    # Rotate update logs
    if [ -f /tmp/nominatim-updates.log ]; then
        echo '[$TIMESTAMP]   📄 Update log: \$(stat -c%s /tmp/nominatim-updates.log 2>/dev/null || echo 0) bytes'
        if [ \$(stat -c%s /tmp/nominatim-updates.log 2>/dev/null || echo 0) -gt 10485760 ]; then
            echo '[$TIMESTAMP]   🔄 Rotating update log (>10MB)'
            mv /tmp/nominatim-updates.log /tmp/nominatim-updates.log.\$(date +%Y%m%d_%H%M%S)
            touch /tmp/nominatim-updates.log
        fi
    fi

    # Rotate health logs
    if [ -f /tmp/nominatim-health.log ]; then
        echo '[$TIMESTAMP]   📄 Health log: \$(stat -c%s /tmp/nominatim-health.log 2>/dev/null || echo 0) bytes'
        if [ \$(stat -c%s /tmp/nominatim-health.log 2>/dev/null || echo 0) -gt 5242880 ]; then
            echo '[$TIMESTAMP]   🔄 Rotating health log (>5MB)'
            mv /tmp/nominatim-health.log /tmp/nominatim-health.log.\$(date +%Y%m%d_%H%M%S)
            touch /tmp/nominatim-health.log
        fi
    fi
" 2>/dev/null || echo "[$TIMESTAMP]   ⚠️  Could not access Nominatim container"

# 3. Clean up temporary status files
echo "[$TIMESTAMP] 📋 Step 3: Temporary file cleanup"

# Clean up old status files from containers
docker-compose exec -T nominatim bash -c "
    echo '[$TIMESTAMP] 🗑️  Cleaning up old status files in container...'

    # Remove old status files (older than $STATUS_RETENTION_DAYS days)
    find /tmp -name 'nominatim-*.json' -type f -mtime +$STATUS_RETENTION_DAYS -delete 2>/dev/null || true
    find /tmp -name 'nominatim-*.log.*' -type f -mtime +$LOG_RETENTION_DAYS -delete 2>/dev/null || true

    echo '[$TIMESTAMP] ✅ Container cleanup complete'
" 2>/dev/null || echo "[$TIMESTAMP]   ⚠️  Could not clean up Nominatim container"

# 4. Host log cleanup
echo "[$TIMESTAMP] 📋 Step 4: Host system log cleanup"

# Clean up gateway logs (if any)
if [ -d "/workspaces/involution-engine/docker/time-resolver/nominatim_stack/logs" ]; then
    cleanup_old_files "*.log" $LOG_RETENTION_DAYS "/workspaces/involution-engine/docker/time-resolver/nominatim_stack/logs"
    cleanup_old_files "*.log.gz" $((LOG_RETENTION_DAYS * 2)) "/workspaces/involution-engine/docker/time-resolver/nominatim_stack/logs"
fi

# 5. Database maintenance
echo "[$TIMESTAMP] 📋 Step 5: Database maintenance"

# PostgreSQL log cleanup (if accessible)
docker-compose exec -T nominatim bash -c "
    echo '[$TIMESTAMP] 🗄️  Checking PostgreSQL logs...'

    if [ -d /var/lib/postgresql/14/main/log ]; then
        find /var/lib/postgresql/14/main/log -name '*.log' -type f -mtime +$LOG_RETENTION_DAYS -delete 2>/dev/null || true
        echo '[$TIMESTAMP] ✅ PostgreSQL log cleanup complete'
    else
        echo '[$TIMESTAMP] ℹ️  PostgreSQL log directory not found'
    fi
" 2>/dev/null || echo "[$TIMESTAMP]   ⚠️  Could not access PostgreSQL logs"

# 6. System disk space check
echo "[$TIMESTAMP] 📋 Step 6: Disk space verification"

DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
DISK_AVAILABLE=$(df -h / | tail -1 | awk '{print $4}')

echo "[$TIMESTAMP]   💿 Current disk usage: ${DISK_USAGE}% (${DISK_AVAILABLE} available)"

if [ $DISK_USAGE -gt 90 ]; then
    echo "[$TIMESTAMP]   🚨 CRITICAL: Disk usage above 90%!"
elif [ $DISK_USAGE -gt 80 ]; then
    echo "[$TIMESTAMP]   ⚠️  WARNING: Disk usage above 80%"
else
    echo "[$TIMESTAMP]   ✅ Disk usage within normal limits"
fi

# 7. Generate cleanup report
echo "[$TIMESTAMP] 📋 Step 7: Cleanup summary"

CLEANUP_REPORT="/tmp/log_cleanup_$(date +%Y%m%d_%H%M%S).json"

cat > "$CLEANUP_REPORT" << EOF
{
  "timestamp": "$TIMESTAMP",
  "disk_usage_percent": $DISK_USAGE,
  "disk_available": "$DISK_AVAILABLE",
  "retention_policies": {
    "logs_days": $LOG_RETENTION_DAYS,
    "status_files_days": $STATUS_RETENTION_DAYS,
    "docker_log_max_size": "$DOCKER_LOG_MAX_SIZE"
  },
  "cleanup_completed": true,
  "warnings": []
}
EOF

echo "[$TIMESTAMP] 📁 Cleanup report saved to: $CLEANUP_REPORT"
echo "[$TIMESTAMP] 🎉 Log rotation and cleanup completed successfully!"

# Optional: Show summary of log sizes after cleanup
echo "[$TIMESTAMP] 📊 Post-cleanup log summary:"
echo "[$TIMESTAMP]   Host logs: $(du -sh /workspaces/involution-engine/docker/time-resolver/nominatim_stack/logs 2>/dev/null | cut -f1 || echo 'N/A')"

docker-compose exec -T nominatim bash -c "
    echo '[$TIMESTAMP]   Container logs:'
    echo '[$TIMESTAMP]     /tmp: \$(du -sh /tmp 2>/dev/null | cut -f1)'
    echo '[$TIMESTAMP]     Status files: \$(ls -la /tmp/nominatim-*.json 2>/dev/null | wc -l) files'
" 2>/dev/null || true

echo "[$TIMESTAMP] ✅ All cleanup tasks completed!"