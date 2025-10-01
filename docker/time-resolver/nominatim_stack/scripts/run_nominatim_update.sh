#!/bin/bash
# Enhanced Nominatim Update Script
# ================================
#
# Performs nightly replication updates with comprehensive logging,
# error handling, and status reporting

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
UPDATE_STATUS_FILE="/tmp/nominatim-last-update.json"
NOMINATIM_CMD="/usr/local/bin/nominatim"

echo "[$TIMESTAMP] 🔄 Starting Nominatim replication update..."

# Capture start time
START_TIME=$(date +%s)

# Initialize status
cat > "$UPDATE_STATUS_FILE" << EOF
{
  "status": "running",
  "start_time": "$TIMESTAMP",
  "start_timestamp": $START_TIME,
  "end_time": null,
  "end_timestamp": null,
  "duration_seconds": null,
  "success": false,
  "error": null,
  "updates_applied": null,
  "data_size_before": null,
  "data_size_after": null
}
EOF

# Function to update status file
update_status() {
    local status="$1"
    local error="$2"
    local end_time=$(date '+%Y-%m-%d %H:%M:%S UTC')
    local end_timestamp=$(date +%s)
    local duration=$((end_timestamp - START_TIME))

    cat > "$UPDATE_STATUS_FILE" << EOF
{
  "status": "$status",
  "start_time": "$TIMESTAMP",
  "start_timestamp": $START_TIME,
  "end_time": "$end_time",
  "end_timestamp": $end_timestamp,
  "duration_seconds": $duration,
  "success": $([ "$status" = "completed" ] && echo "true" || echo "false"),
  "error": $([ -n "$error" ] && echo "\"$error\"" || echo "null"),
  "updates_applied": $([ "$status" = "completed" ] && echo "\"$UPDATES_APPLIED\"" || echo "null"),
  "data_size_before": $([ -n "$DATA_SIZE_BEFORE" ] && echo "$DATA_SIZE_BEFORE" || echo "null"),
  "data_size_after": $([ -n "$DATA_SIZE_AFTER" ] && echo "$DATA_SIZE_AFTER" || echo "null")
}
EOF
}

# Trap errors
trap 'update_status "failed" "Update process failed unexpectedly"' ERR

# Check database size before update
echo "[$TIMESTAMP] 📊 Checking database size before update..."
if command -v du >/dev/null 2>&1; then
    DATA_SIZE_BEFORE=$(du -sb /var/lib/postgresql/14/main 2>/dev/null | cut -f1 || echo "0")
    echo "[$TIMESTAMP] 📊 Database size before: $DATA_SIZE_BEFORE bytes"
fi

# Check replication status
echo "[$TIMESTAMP] 🔍 Checking replication status..."
REPLICATION_STATUS=$($NOMINATIM_CMD replication --check-for-updates 2>&1 || echo "ERROR")

if echo "$REPLICATION_STATUS" | grep -q "ERROR"; then
    echo "[$TIMESTAMP] ❌ Replication check failed: $REPLICATION_STATUS"
    update_status "failed" "Replication check failed: $REPLICATION_STATUS"
    exit 1
fi

echo "[$TIMESTAMP] ✅ Replication status: $REPLICATION_STATUS"

# Perform the update
echo "[$TIMESTAMP] 🔄 Running replication update..."
UPDATE_OUTPUT=$($NOMINATIM_CMD replication --update 2>&1)
UPDATE_EXIT_CODE=$?

if [ $UPDATE_EXIT_CODE -ne 0 ]; then
    echo "[$TIMESTAMP] ❌ Update failed with exit code $UPDATE_EXIT_CODE"
    echo "[$TIMESTAMP] ❌ Output: $UPDATE_OUTPUT"
    update_status "failed" "Update command failed: $UPDATE_OUTPUT"
    exit 1
fi

echo "[$TIMESTAMP] ✅ Update completed successfully"
echo "[$TIMESTAMP] 📝 Output: $UPDATE_OUTPUT"

# Parse update results
UPDATES_APPLIED=$(echo "$UPDATE_OUTPUT" | grep -o "imported [0-9]* diffs" | grep -o "[0-9]*" || echo "0")
if [ -z "$UPDATES_APPLIED" ]; then
    UPDATES_APPLIED="0"
fi

# Check database size after update
if command -v du >/dev/null 2>&1; then
    DATA_SIZE_AFTER=$(du -sb /var/lib/postgresql/14/main 2>/dev/null | cut -f1 || echo "0")
    echo "[$TIMESTAMP] 📊 Database size after: $DATA_SIZE_AFTER bytes"

    if [ "$DATA_SIZE_BEFORE" != "0" ] && [ "$DATA_SIZE_AFTER" != "0" ]; then
        SIZE_CHANGE=$((DATA_SIZE_AFTER - DATA_SIZE_BEFORE))
        echo "[$TIMESTAMP] 📊 Size change: $SIZE_CHANGE bytes"
    fi
fi

# Update final status
update_status "completed" ""

echo "[$TIMESTAMP] 🎉 Nominatim replication update completed successfully!"
echo "[$TIMESTAMP] 📊 Updates applied: $UPDATES_APPLIED"
echo "[$TIMESTAMP] 📁 Status saved to: $UPDATE_STATUS_FILE"

# Trigger a brief database health check
echo "[$TIMESTAMP] 🔍 Running post-update health check..."
HEALTH_CHECK=$($NOMINATIM_CMD admin --check-database 2>&1 || echo "HEALTH_ERROR")

if echo "$HEALTH_CHECK" | grep -q "HEALTH_ERROR"; then
    echo "[$TIMESTAMP] ⚠️  Post-update health check warning: $HEALTH_CHECK"
else
    echo "[$TIMESTAMP] ✅ Post-update health check passed"
fi

echo "[$TIMESTAMP] ✅ Update process complete!"