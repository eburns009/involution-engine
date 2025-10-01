#!/bin/bash

# Involution Engine - Security Monitoring Script
# Monitors security metrics and alerts on anomalies

set -euo pipefail

# Configuration
ENGINE_BASE_URL="${ENGINE_BASE_URL:-http://localhost:8000}"
ALERT_THRESHOLD_BLOCKED="${ALERT_THRESHOLD_BLOCKED:-50}"
ALERT_THRESHOLD_SUSPICIOUS="${ALERT_THRESHOLD_SUSPICIOUS:-25}"
LOG_FILE="${LOG_FILE:-/var/log/involution/security_monitor.log}"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

send_alert() {
    local message="$1"
    local severity="${2:-WARNING}"

    log "$severity: $message"

    # Send to Slack if webhook configured
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🔒 Involution Engine Security Alert [$severity]: $message\"}" \
            "$SLACK_WEBHOOK" || log "Failed to send Slack alert"
    fi

    # Send to system log
    logger -t "involution-security" "$severity: $message"
}

check_health_endpoint() {
    local response
    if ! response=$(curl -s -f "$ENGINE_BASE_URL/health" 2>/dev/null); then
        send_alert "Health endpoint unreachable" "CRITICAL"
        return 1
    fi

    echo "$response"
}

analyze_security_metrics() {
    local health_data="$1"

    # Extract security metrics using jq
    if ! command -v jq >/dev/null 2>&1; then
        log "WARNING: jq not available, skipping detailed analysis"
        return 0
    fi

    local blocked_requests
    local suspicious_requests
    local security_status

    blocked_requests=$(echo "$health_data" | jq -r '.checks.security.blocked_requests // 0')
    suspicious_requests=$(echo "$health_data" | jq -r '.checks.security.suspicious_requests // 0')
    security_status=$(echo "$health_data" | jq -r '.checks.security.status // "unknown"')

    log "Security metrics - Blocked: $blocked_requests, Suspicious: $suspicious_requests, Status: $security_status"

    # Check thresholds
    if [[ "$blocked_requests" -gt "$ALERT_THRESHOLD_BLOCKED" ]]; then
        send_alert "High number of blocked requests: $blocked_requests (threshold: $ALERT_THRESHOLD_BLOCKED)" "WARNING"
    fi

    if [[ "$suspicious_requests" -gt "$ALERT_THRESHOLD_SUSPICIOUS" ]]; then
        send_alert "High number of suspicious requests: $suspicious_requests (threshold: $ALERT_THRESHOLD_SUSPICIOUS)" "WARNING"
    fi

    if [[ "$security_status" != "healthy" ]]; then
        send_alert "Security check status is not healthy: $security_status" "WARNING"
    fi
}

check_system_security() {
    # Check for suspicious processes
    if pgrep -f "sqlmap|nikto|nmap|dirb|gobuster" >/dev/null; then
        send_alert "Suspicious security tools detected in process list" "CRITICAL"
    fi

    # Check for unusual network connections
    if netstat -an 2>/dev/null | grep -E ":4444|:31337|:1337" >/dev/null; then
        send_alert "Suspicious network connections detected" "WARNING"
    fi

    # Check log files for security patterns
    if [[ -f "/var/log/involution/app.log" ]]; then
        local recent_errors
        recent_errors=$(tail -n 1000 /var/log/involution/app.log | grep -c "ERROR\|CRITICAL" || echo "0")

        if [[ "$recent_errors" -gt 50 ]]; then
            send_alert "High error rate detected in application logs: $recent_errors errors in last 1000 lines" "WARNING"
        fi
    fi
}

main() {
    log "Starting security monitoring check"

    # Check health endpoint
    local health_data
    if ! health_data=$(check_health_endpoint); then
        exit 1
    fi

    # Analyze security metrics
    analyze_security_metrics "$health_data"

    # Check system-level security
    check_system_security

    log "Security monitoring check completed"
}

# Run main function
main "$@"