#!/bin/bash

# Involution Engine - Security Audit Script
# Performs comprehensive security assessment

set -euo pipefail

# Configuration
AUDIT_REPORT_FILE="${AUDIT_REPORT_FILE:-security_audit_$(date +%Y%m%d_%H%M%S).json}"
ENGINE_BASE_URL="${ENGINE_BASE_URL:-http://localhost:8000}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Initialize audit report
init_report() {
    cat > "$AUDIT_REPORT_FILE" <<EOF
{
    "audit_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "engine_url": "$ENGINE_BASE_URL",
    "checks": {},
    "summary": {
        "total_checks": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
}
EOF
}

# Add check result to report
add_check_result() {
    local check_name="$1"
    local status="$2"  # pass, fail, warn
    local message="$3"
    local details="${4:-{}}"

    # Update summary counts
    local total=$(jq '.summary.total_checks + 1' "$AUDIT_REPORT_FILE")
    local field="passed"
    [[ "$status" == "fail" ]] && field="failed"
    [[ "$status" == "warn" ]] && field="warnings"
    local count=$(jq ".summary.$field + 1" "$AUDIT_REPORT_FILE")

    # Add check result
    jq --arg name "$check_name" \
       --arg status "$status" \
       --arg message "$message" \
       --argjson details "$details" \
       --argjson total "$total" \
       --argjson count "$count" \
       ".checks[\$name] = {status: \$status, message: \$message, details: \$details} |
        .summary.total_checks = \$total |
        .summary.$field = \$count" \
       "$AUDIT_REPORT_FILE" > "$AUDIT_REPORT_FILE.tmp" && mv "$AUDIT_REPORT_FILE.tmp" "$AUDIT_REPORT_FILE"

    log "$status: $check_name - $message"
}

# Check HTTPS enforcement
check_https_enforcement() {
    log "Checking HTTPS enforcement..."

    # Test if HTTP redirects to HTTPS (in production)
    if [[ "$ENGINE_BASE_URL" == http* ]]; then
        local http_url="${ENGINE_BASE_URL/https:/http:}"

        if curl -s -I "$http_url/health" 2>/dev/null | grep -q "Location.*https"; then
            add_check_result "https_enforcement" "pass" "HTTP properly redirects to HTTPS"
        else
            if [[ "$ENGINE_BASE_URL" == *localhost* ]] || [[ "$ENGINE_BASE_URL" == *127.0.0.1* ]]; then
                add_check_result "https_enforcement" "warn" "HTTPS not enforced (acceptable for localhost)"
            else
                add_check_result "https_enforcement" "fail" "HTTP does not redirect to HTTPS"
            fi
        fi
    else
        add_check_result "https_enforcement" "pass" "Using HTTPS URL"
    fi
}

# Check security headers
check_security_headers() {
    log "Checking security headers..."

    local headers
    if ! headers=$(curl -s -I "$ENGINE_BASE_URL/health" 2>/dev/null); then
        add_check_result "security_headers" "fail" "Could not fetch headers from health endpoint"
        return
    fi

    local missing_headers=()
    local weak_headers=()

    # Check for required security headers
    if ! echo "$headers" | grep -qi "x-content-type-options.*nosniff"; then
        missing_headers+=("X-Content-Type-Options")
    fi

    if ! echo "$headers" | grep -qi "x-frame-options"; then
        missing_headers+=("X-Frame-Options")
    fi

    if ! echo "$headers" | grep -qi "content-security-policy"; then
        missing_headers+=("Content-Security-Policy")
    fi

    if ! echo "$headers" | grep -qi "referrer-policy"; then
        missing_headers+=("Referrer-Policy")
    fi

    # Check for HSTS (should be present in production HTTPS)
    if [[ "$ENGINE_BASE_URL" == https* ]] && ! echo "$headers" | grep -qi "strict-transport-security"; then
        missing_headers+=("Strict-Transport-Security")
    fi

    # Check for information disclosure
    if echo "$headers" | grep -qi "server:"; then
        weak_headers+=("Server header present (information disclosure)")
    fi

    if echo "$headers" | grep -qi "x-powered-by"; then
        weak_headers+=("X-Powered-By header present (information disclosure)")
    fi

    # Generate report
    local status="pass"
    local message="All security headers properly configured"
    local details="{\"missing_headers\": $(printf '%s\n' "${missing_headers[@]}" | jq -R . | jq -s .), \"weak_headers\": $(printf '%s\n' "${weak_headers[@]}" | jq -R . | jq -s .)}"

    if [[ ${#missing_headers[@]} -gt 0 ]]; then
        status="fail"
        message="Missing critical security headers: ${missing_headers[*]}"
    elif [[ ${#weak_headers[@]} -gt 0 ]]; then
        status="warn"
        message="Information disclosure headers present: ${weak_headers[*]}"
    fi

    add_check_result "security_headers" "$status" "$message" "$details"
}

# Check rate limiting
check_rate_limiting() {
    log "Checking rate limiting..."

    # Make rapid requests to test rate limiting
    local success_count=0
    local rate_limited=false

    for i in {1..20}; do
        local response_code
        response_code=$(curl -s -o /dev/null -w "%{http_code}" "$ENGINE_BASE_URL/health" 2>/dev/null || echo "000")

        if [[ "$response_code" == "200" ]]; then
            ((success_count++))
        elif [[ "$response_code" == "429" ]]; then
            rate_limited=true
            break
        fi
    done

    if [[ "$rate_limited" == true ]]; then
        add_check_result "rate_limiting" "pass" "Rate limiting is active and working"
    elif [[ "$success_count" -eq 20 ]]; then
        add_check_result "rate_limiting" "warn" "No rate limiting detected in 20 rapid requests"
    else
        add_check_result "rate_limiting" "fail" "Inconsistent response to rapid requests"
    fi
}

# Check CORS configuration
check_cors_configuration() {
    log "Checking CORS configuration..."

    # Test CORS with a potentially malicious origin
    local cors_headers
    cors_headers=$(curl -s -H "Origin: https://evil.com" -H "Access-Control-Request-Method: POST" \
                       -X OPTIONS "$ENGINE_BASE_URL/health" 2>/dev/null | head -20)

    if echo "$cors_headers" | grep -qi "access-control-allow-origin.*evil.com"; then
        add_check_result "cors_config" "fail" "CORS allows potentially dangerous origins"
    elif echo "$cors_headers" | grep -qi "access-control-allow-origin.*\*"; then
        add_check_result "cors_config" "fail" "CORS allows all origins (*) - security risk"
    else
        add_check_result "cors_config" "pass" "CORS properly restricts origins"
    fi
}

# Check for sensitive information exposure
check_info_disclosure() {
    log "Checking for information disclosure..."

    local exposed_info=()

    # Check health endpoint for sensitive info
    local health_response
    if health_response=$(curl -s "$ENGINE_BASE_URL/health" 2>/dev/null); then
        # Check for debug information in production
        if echo "$health_response" | jq -e '.service.debug_enabled == true' >/dev/null 2>&1; then
            if [[ "$ENGINE_BASE_URL" != *localhost* ]] && [[ "$ENGINE_BASE_URL" != *127.0.0.1* ]]; then
                exposed_info+=("Debug mode enabled in non-localhost environment")
            fi
        fi

        # Check for detailed error messages
        if echo "$health_response" | grep -qi "error.*exception\|traceback\|stack trace"; then
            exposed_info+=("Detailed error messages in health endpoint")
        fi
    fi

    # Test error responses for information disclosure
    local error_response
    error_response=$(curl -s "$ENGINE_BASE_URL/nonexistent-endpoint" 2>/dev/null || echo "")
    if echo "$error_response" | grep -qi "traceback\|exception.*at.*line\|internal server error.*details"; then
        exposed_info+=("Detailed error messages in 404 responses")
    fi

    if [[ ${#exposed_info[@]} -gt 0 ]]; then
        local details="{\"exposed_info\": $(printf '%s\n' "${exposed_info[@]}" | jq -R . | jq -s .)}"
        add_check_result "info_disclosure" "fail" "Information disclosure detected: ${exposed_info[*]}" "$details"
    else
        add_check_result "info_disclosure" "pass" "No information disclosure detected"
    fi
}

# Check SSL/TLS configuration (if HTTPS)
check_ssl_config() {
    if [[ "$ENGINE_BASE_URL" != https* ]]; then
        add_check_result "ssl_config" "warn" "Not using HTTPS - SSL check skipped"
        return
    fi

    log "Checking SSL/TLS configuration..."

    local hostname
    hostname=$(echo "$ENGINE_BASE_URL" | sed -E 's|https?://([^/]+).*|\1|')

    # Use openssl to check SSL configuration
    local ssl_info
    if ssl_info=$(echo | openssl s_client -connect "$hostname:443" -servername "$hostname" 2>/dev/null); then
        # Check TLS version
        local tls_version
        tls_version=$(echo "$ssl_info" | grep "Protocol" | head -1)

        if echo "$tls_version" | grep -qi "TLSv1\.[2-3]"; then
            add_check_result "ssl_config" "pass" "Using secure TLS version"
        else
            add_check_result "ssl_config" "fail" "Using insecure TLS version: $tls_version"
        fi
    else
        add_check_result "ssl_config" "fail" "Could not establish SSL connection"
    fi
}

# Generate final report
generate_final_report() {
    log "Generating final security audit report..."

    # Calculate security score
    local total=$(jq '.summary.total_checks' "$AUDIT_REPORT_FILE")
    local passed=$(jq '.summary.passed' "$AUDIT_REPORT_FILE")
    local failed=$(jq '.summary.failed' "$AUDIT_REPORT_FILE")
    local warnings=$(jq '.summary.warnings' "$AUDIT_REPORT_FILE")

    local score=0
    if [[ "$total" -gt 0 ]]; then
        score=$(( (passed * 100) / total ))
    fi

    # Add final summary
    jq --argjson score "$score" \
       '.summary.security_score = $score |
        .summary.risk_level = (
          if $score >= 90 then "LOW"
          elif $score >= 70 then "MEDIUM"
          elif $score >= 50 then "HIGH"
          else "CRITICAL"
          end
        )' \
       "$AUDIT_REPORT_FILE" > "$AUDIT_REPORT_FILE.tmp" && mv "$AUDIT_REPORT_FILE.tmp" "$AUDIT_REPORT_FILE"

    echo
    echo "=== SECURITY AUDIT SUMMARY ==="
    echo "Total Checks: $total"
    echo "Passed: $passed"
    echo "Failed: $failed"
    echo "Warnings: $warnings"
    echo "Security Score: $score%"
    echo "Risk Level: $(jq -r '.summary.risk_level' "$AUDIT_REPORT_FILE")"
    echo
    echo "Full report saved to: $AUDIT_REPORT_FILE"
}

main() {
    log "Starting comprehensive security audit..."

    # Initialize report
    init_report

    # Run all security checks
    check_https_enforcement
    check_security_headers
    check_rate_limiting
    check_cors_configuration
    check_info_disclosure
    check_ssl_config

    # Generate final report
    generate_final_report

    log "Security audit completed"
}

# Ensure jq is available
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required for this script but not installed"
    exit 1
fi

# Run main function
main "$@"