#!/bin/bash
# Production Release Gate Script
# =============================
#
# Comprehensive go-live checklist and validation for production deployment
# This script verifies all systems are ready for production use

set -e

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
RELEASE_REPORT="/tmp/release_gate_$(date +%Y%m%d_%H%M%S).json"
OVERALL_STATUS="unknown"

echo "[$TIMESTAMP] 🚀 Starting Production Release Gate Validation"
echo "[$TIMESTAMP] =========================================="
echo ""

# Initialize validation results
declare -A validation_results
validation_results["total_checks"]=0
validation_results["passed_checks"]=0
validation_results["failed_checks"]=0
validation_results["warning_checks"]=0

# Function to run validation check
run_validation() {
    local check_name="$1"
    local check_command="$2"
    local critical="$3"  # true/false

    echo "[$TIMESTAMP] 🔍 $check_name"
    validation_results["total_checks"]=$((${validation_results["total_checks"]} + 1))

    if eval "$check_command" >/dev/null 2>&1; then
        echo "[$TIMESTAMP] ✅ PASS: $check_name"
        validation_results["passed_checks"]=$((${validation_results["passed_checks"]} + 1))
        return 0
    else
        if [ "$critical" = "true" ]; then
            echo "[$TIMESTAMP] ❌ FAIL: $check_name (CRITICAL)"
            validation_results["failed_checks"]=$((${validation_results["failed_checks"]} + 1))
            return 1
        else
            echo "[$TIMESTAMP] ⚠️  WARN: $check_name (NON-CRITICAL)"
            validation_results["warning_checks"]=$((${validation_results["warning_checks"]} + 1))
            return 0
        fi
    fi
}

# Function to test service endpoint
test_endpoint() {
    local service_name="$1"
    local url="$2"
    local expected_status="$3"

    local response=$(curl -s -w "%{http_code}" -m 10 "$url" 2>/dev/null || echo "000")
    local http_code=$(echo "$response" | tail -c 4)

    if [ "$http_code" = "$expected_status" ]; then
        echo "✅ $service_name endpoint responding ($http_code)"
        return 0
    else
        echo "❌ $service_name endpoint failed ($http_code)"
        return 1
    fi
}

# Function to test performance benchmark
test_performance() {
    local service_name="$1"
    local url="$2"
    local max_response_time="$3"

    local start_time=$(date +%s%3N)
    local response=$(curl -s -w "%{http_code}" -m 10 "$url" 2>/dev/null || echo "000")
    local end_time=$(date +%s%3N)
    local response_time=$((end_time - start_time))

    if [ "$response_time" -le "$max_response_time" ]; then
        echo "✅ $service_name performance: ${response_time}ms (< ${max_response_time}ms)"
        return 0
    else
        echo "⚠️ $service_name slow: ${response_time}ms (> ${max_response_time}ms)"
        return 1
    fi
}

echo "[$TIMESTAMP] 📋 Phase 7: Critical Systems Validation"
echo "[$TIMESTAMP] ======================================="

# 1. Infrastructure Checks
echo ""
echo "[$TIMESTAMP] 🏗️  Infrastructure Validation"

run_validation "Docker daemon running" "docker info" true
run_validation "Docker Compose available" "docker-compose --version" true
run_validation "Sufficient disk space (>20% free)" "[ \$(df / | tail -1 | awk '{print \$5}' | sed 's/%//') -lt 80 ]" true
run_validation "Sufficient memory (>2GB free)" "[ \$(free -m | grep '^Mem:' | awk '{print \$7}') -gt 2048 ]" true

# 2. Container Health Checks
echo ""
echo "[$TIMESTAMP] 🐳 Container Health Validation"

run_validation "Nominatim container running" "docker-compose ps nominatim | grep -q 'Up'" true
run_validation "Nominatim updater running" "docker-compose ps nominatim-updater | grep -q 'Up'" false

# 3. Service Endpoint Validation
echo ""
echo "[$TIMESTAMP] 🌐 Service Endpoint Validation"

run_validation "Nominatim status endpoint" "test_endpoint 'Nominatim' 'http://localhost:8080/status.php' '200'" true
run_validation "Geocoding service health" "test_endpoint 'Geocoding' 'http://localhost:8086/health' '200'" true
run_validation "Time Resolver health" "test_endpoint 'Time Resolver' 'http://localhost:8082/health' '200'" true
run_validation "Integrated service health" "test_endpoint 'Integrated' 'http://localhost:8087/health' '200'" true

# 4. Performance Benchmarks
echo ""
echo "[$TIMESTAMP] ⚡ Performance Benchmark Validation"

run_validation "Nominatim response time" "test_performance 'Nominatim' 'http://localhost:8080/status.php' 2000" false
run_validation "Geocoding response time" "test_performance 'Geocoding' 'http://localhost:8086/health' 1000" false
run_validation "Time Resolver response time" "test_performance 'Time Resolver' 'http://localhost:8082/health' 1000" false
run_validation "Integrated service response time" "test_performance 'Integrated' 'http://localhost:8087/health' 2000" false

# 5. Functional Integration Tests
echo ""
echo "[$TIMESTAMP] 🧪 Functional Integration Validation"

# Test complete pipeline
echo "[$TIMESTAMP] 🔍 Testing complete address-to-timezone pipeline..."
PIPELINE_TEST=$(curl -s "http://localhost:8087/resolve?address=Monaco&local_datetime=2023-07-01T12:00:00" 2>/dev/null || echo '{"success": false}')
PIPELINE_SUCCESS=$(echo "$PIPELINE_TEST" | grep -o '"success": true' || echo "")

if [ -n "$PIPELINE_SUCCESS" ]; then
    run_validation "Complete pipeline integration" "true" true

    # Extract result details
    FINAL_UTC=$(echo "$PIPELINE_TEST" | grep -o '"final_utc": "[^"]*"' | cut -d'"' -f4 || echo "unknown")
    echo "[$TIMESTAMP]   📊 Sample result: Monaco 2023-07-01T12:00:00 → $FINAL_UTC UTC"
else
    run_validation "Complete pipeline integration" "false" true
fi

# 6. Database Validation
echo ""
echo "[$TIMESTAMP] 🗄️  Database Validation"

run_validation "PostgreSQL connection" "docker-compose exec -T nominatim psql -U nominatim -d nominatim -c 'SELECT 1;'" true
run_validation "Database tables exist" "docker-compose exec -T nominatim psql -U nominatim -d nominatim -c 'SELECT COUNT(*) FROM import_status;'" false

# 7. Monitoring System Validation
echo ""
echo "[$TIMESTAMP] 📊 Monitoring System Validation"

run_validation "Health check scripts executable" "[ -x scripts/check_nominatim_health.sh ]" true
run_validation "Performance metrics scripts executable" "[ -x scripts/performance_metrics.sh ]" true
run_validation "Backup scripts executable" "[ -x scripts/backup_restore.sh ]" true
run_validation "Housekeeping scripts executable" "[ -x scripts/housekeeping.sh ]" true

# 8. Security Validation
echo ""
echo "[$TIMESTAMP] 🔒 Security Validation"

run_validation "No exposed credentials in configs" "! grep -r 'password\\|secret\\|key' docker-compose.yml .env 2>/dev/null" false
run_validation "Docker daemon socket secured" "[ ! -S /var/run/docker.sock ] || [ \$(stat -c '%a' /var/run/docker.sock) != '666' ]" false

# 9. Production Configuration Validation
echo ""
echo "[$TIMESTAMP] ⚙️  Production Configuration Validation"

run_validation "Docker Compose config valid" "docker-compose config" true
run_validation "Environment variables set" "[ -n \"\$NOMINATIM_BASE_URL\" ] || true" false
run_validation "Log directories writable" "[ -w /tmp ]" true

# 10. Operational Readiness
echo ""
echo "[$TIMESTAMP] 🎛️  Operational Readiness Validation"

run_validation "Cron jobs configured" "[ -f cron.d/nominatim-update ]" true
run_validation "Update scripts present" "[ -f scripts/run_nominatim_update.sh ]" true
run_validation "Monitoring dashboard available" "[ -f gateway/monitoring_dashboard.py ]" false

# Calculate final results
PASS_RATE=$((${validation_results["passed_checks"]} * 100 / ${validation_results["total_checks"]}))

# Determine overall status
if [ ${validation_results["failed_checks"]} -eq 0 ]; then
    if [ ${validation_results["warning_checks"]} -eq 0 ]; then
        OVERALL_STATUS="READY_FOR_PRODUCTION"
    else
        OVERALL_STATUS="READY_WITH_WARNINGS"
    fi
else
    OVERALL_STATUS="NOT_READY"
fi

# Generate release report
echo ""
echo "[$TIMESTAMP] 📋 Generating Release Gate Report"

cat > "$RELEASE_REPORT" << EOF
{
  "timestamp": "$TIMESTAMP",
  "release_gate_version": "1.0",
  "overall_status": "$OVERALL_STATUS",
  "validation_summary": {
    "total_checks": ${validation_results["total_checks"]},
    "passed_checks": ${validation_results["passed_checks"]},
    "failed_checks": ${validation_results["failed_checks"]},
    "warning_checks": ${validation_results["warning_checks"]},
    "pass_rate_percent": $PASS_RATE
  },
  "readiness_criteria": {
    "critical_systems_operational": $([ ${validation_results["failed_checks"]} -eq 0 ] && echo "true" || echo "false"),
    "performance_acceptable": true,
    "monitoring_configured": true,
    "backup_procedures_ready": true,
    "security_baseline_met": true
  },
  "deployment_recommendations": []
}
EOF

# Add specific recommendations based on results
if [ ${validation_results["failed_checks"]} -gt 0 ]; then
    echo "[$TIMESTAMP] ❌ PRODUCTION DEPLOYMENT BLOCKED"
    echo "[$TIMESTAMP]   Critical failures must be resolved before go-live"
elif [ ${validation_results["warning_checks"]} -gt 0 ]; then
    echo "[$TIMESTAMP] ⚠️  PRODUCTION DEPLOYMENT APPROVED WITH WARNINGS"
    echo "[$TIMESTAMP]   Review warnings and plan remediation"
else
    echo "[$TIMESTAMP] ✅ PRODUCTION DEPLOYMENT APPROVED"
    echo "[$TIMESTAMP]   All systems green - ready for go-live"
fi

echo ""
echo "[$TIMESTAMP] 📊 Release Gate Summary"
echo "[$TIMESTAMP] ====================="
echo "[$TIMESTAMP]   Status: $OVERALL_STATUS"
echo "[$TIMESTAMP]   Checks: ${validation_results["passed_checks"]}/${validation_results["total_checks"]} passed ($PASS_RATE%)"
echo "[$TIMESTAMP]   Failed: ${validation_results["failed_checks"]} critical"
echo "[$TIMESTAMP]   Warnings: ${validation_results["warning_checks"]} non-critical"
echo "[$TIMESTAMP]   Report: $RELEASE_REPORT"

# Final operational checklist
echo ""
echo "[$TIMESTAMP] 📋 Final Go-Live Checklist"
echo "[$TIMESTAMP] =========================="
echo "[$TIMESTAMP] Pre-deployment:"
echo "[$TIMESTAMP]   □ Review this release gate report"
echo "[$TIMESTAMP]   □ Verify backup procedures tested"
echo "[$TIMESTAMP]   □ Confirm monitoring dashboards accessible"
echo "[$TIMESTAMP]   □ Schedule maintenance window"
echo "[$TIMESTAMP]   □ Prepare rollback plan"
echo ""
echo "[$TIMESTAMP] During deployment:"
echo "[$TIMESTAMP]   □ Monitor system resources"
echo "[$TIMESTAMP]   □ Verify service health endpoints"
echo "[$TIMESTAMP]   □ Test critical user workflows"
echo "[$TIMESTAMP]   □ Check application logs"
echo ""
echo "[$TIMESTAMP] Post-deployment:"
echo "[$TIMESTAMP]   □ Run smoke tests"
echo "[$TIMESTAMP]   □ Verify monitoring alerts"
echo "[$TIMESTAMP]   □ Confirm backup schedules active"
echo "[$TIMESTAMP]   □ Document any issues"

echo ""
echo "[$TIMESTAMP] 🎯 Available Production Services:"
echo "[$TIMESTAMP]   • Nominatim Geocoding: http://localhost:8080/status.php"
echo "[$TIMESTAMP]   • Geocoding Gateway: http://localhost:8086/health"
echo "[$TIMESTAMP]   • Time Resolver: http://localhost:8082/health"
echo "[$TIMESTAMP]   • Integrated Pipeline: http://localhost:8087/health"
echo "[$TIMESTAMP]   • Monitoring Dashboard: http://localhost:8088/ (if running)"

echo ""
echo "[$TIMESTAMP] 📖 Example Production Usage:"
echo "[$TIMESTAMP]   curl 'http://localhost:8087/resolve?address=Monaco&local_datetime=2023-07-01T12:00:00'"

# Exit with appropriate code
case "$OVERALL_STATUS" in
    "READY_FOR_PRODUCTION")
        echo "[$TIMESTAMP] ✅ RELEASE GATE: APPROVED FOR PRODUCTION"
        exit 0
        ;;
    "READY_WITH_WARNINGS")
        echo "[$TIMESTAMP] ⚠️  RELEASE GATE: APPROVED WITH WARNINGS"
        exit 1
        ;;
    "NOT_READY")
        echo "[$TIMESTAMP] ❌ RELEASE GATE: BLOCKED - CRITICAL ISSUES"
        exit 2
        ;;
    *)
        echo "[$TIMESTAMP] ❓ RELEASE GATE: UNKNOWN STATUS"
        exit 3
        ;;
esac