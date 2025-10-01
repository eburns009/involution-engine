# Security Hardening Guide

This document provides comprehensive security guidelines for deploying and operating the Involution Engine in production environments.

## 🔒 Pre-Deployment Security Checklist

### Environment Configuration

- [ ] **Change all default passwords** in `.env` file
- [ ] **Configure proper CORS origins** - never use `*` in production
- [ ] **Set strong Redis password** and enable auth
- [ ] **Configure database with strong credentials** and SSL
- [ ] **Set up proper trusted hosts** configuration
- [ ] **Enable security headers** (`ENABLE_SECURITY_HEADERS=true`)
- [ ] **Configure rate limiting** with Redis backend
- [ ] **Set resource limits** (memory, CPU, disk)
- [ ] **Enable request logging** for audit trails

### TLS/SSL Configuration

- [ ] **Deploy with HTTPS only** - no HTTP in production
- [ ] **Configure HSTS** with appropriate max-age
- [ ] **Use strong cipher suites** and disable weak protocols
- [ ] **Enable OCSP stapling** for certificate validation
- [ ] **Set up certificate auto-renewal** (Let's Encrypt/cert-manager)

### Network Security

- [ ] **Configure firewall rules** to restrict access
- [ ] **Use private networks** for service-to-service communication
- [ ] **Enable DDoS protection** at load balancer level
- [ ] **Set up intrusion detection** monitoring
- [ ] **Configure reverse proxy** (nginx) with security headers

## 🛡️ Operational Security Features

### Security Middleware Stack

The engine includes comprehensive security middleware:

1. **Trusted Host Protection** - Validates incoming host headers
2. **Security Headers** - Adds comprehensive security headers
3. **Request Monitoring** - Tracks suspicious patterns
4. **Rate Limiting** - Prevents abuse and DoS attacks
5. **CORS Protection** - Restricts cross-origin requests
6. **Request Size Validation** - Prevents oversized requests

### Security Monitoring

Real-time security monitoring includes:

- **Blocked request tracking** - Count and log blocked requests
- **Suspicious pattern detection** - Identify potential attacks
- **Rate limit violations** - Track rate limiting events
- **Invalid host attempts** - Monitor host header attacks
- **Performance impact** - Monitor security overhead

### Health Endpoint Security

The `/health` endpoint includes security metrics:

```json
{
  "checks": {
    "security": {
      "status": "healthy",
      "blocked_requests": 5,
      "rate_limited_requests": 12,
      "suspicious_requests": 2,
      "security_headers_enabled": true,
      "trusted_hosts_configured": 3
    }
  }
}
```

## 🔧 Security Configuration

### Environment Variables

Critical security environment variables:

```bash
# Security Headers
ENABLE_SECURITY_HEADERS=true
HSTS_MAX_AGE=31536000
CSP_POLICY="default-src 'self'; connect-src 'self'"
X_FRAME_OPTIONS=DENY
REFERRER_POLICY=strict-origin-when-cross-origin

# CORS Configuration
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
ALLOWED_METHODS=GET,POST
ALLOWED_HEADERS=content-type,authorization,x-request-id
ALLOW_CREDENTIALS=true

# Host Protection
TRUSTED_HOSTS=yourdomain.com,app.yourdomain.com,api.yourdomain.com

# Rate Limiting
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_CALCULATE=60/minute
RATE_LIMIT_TIMESOLVE=30/minute
RATE_LIMIT_STORAGE_URI=redis://redis:6379/0

# Request Limits
MAX_REQUEST_SIZE=1048576
REQUEST_TIMEOUT=30
MAX_CONCURRENT_REQUESTS=100

# Logging
ENABLE_REQUEST_LOGGING=true
LOG_SENSITIVE_DATA=false
```

### Docker Security

Production Docker configuration includes:

- **Non-root user** execution
- **Read-only root filesystem** where possible
- **Resource limits** (CPU, memory)
- **Security scanning** of base images
- **Minimal attack surface** with multi-stage builds

## 🚨 Security Monitoring Tools

### Security Monitor Script

Run continuous security monitoring:

```bash
# Monitor security metrics every 5 minutes
./scripts/security_monitor.sh

# With custom thresholds
ALERT_THRESHOLD_BLOCKED=25 \
ALERT_THRESHOLD_SUSPICIOUS=10 \
./scripts/security_monitor.sh
```

### Security Audit Script

Perform comprehensive security assessment:

```bash
# Full security audit
./scripts/security_audit.sh

# Audit with custom engine URL
ENGINE_BASE_URL=https://your-api.com ./scripts/security_audit.sh
```

The audit checks:
- HTTPS enforcement and redirects
- Security header presence and configuration
- Rate limiting effectiveness
- CORS configuration security
- Information disclosure vulnerabilities
- SSL/TLS configuration strength

## 📊 Security Metrics

### Key Performance Indicators

Monitor these security KPIs:

- **Security Score** - Overall security assessment (aim for >90%)
- **Blocked Request Rate** - Should be <1% of total requests
- **False Positive Rate** - Legitimate requests blocked (<0.1%)
- **Response Time Impact** - Security overhead (<10ms)
- **Alert Response Time** - Time to respond to security events

### Alerting Thresholds

Set up alerts for:

- **High blocked request rate** (>50 requests/hour)
- **Suspicious pattern detection** (>25 events/hour)
- **Rate limit violations** (>100 events/hour)
- **SSL certificate expiry** (<30 days)
- **Security check failures** (any critical check)

## 🔍 Incident Response

### Security Event Response

When security events are detected:

1. **Immediate Assessment** - Determine threat severity
2. **Containment** - Block malicious IPs if needed
3. **Investigation** - Analyze logs and request patterns
4. **Mitigation** - Apply appropriate countermeasures
5. **Documentation** - Record incident details
6. **Review** - Update security measures based on learnings

### Log Analysis

Security-relevant log events include:

```json
{
  "level": "WARNING",
  "message": "Suspicious request detected",
  "request_id": "uuid",
  "client_ip": "1.2.3.4",
  "reason": "Suspicious user-agent: sqlmap",
  "path": "/api/calculate"
}
```

## 🔄 Security Maintenance

### Regular Security Tasks

- **Weekly**: Review security metrics and alerts
- **Monthly**: Run comprehensive security audit
- **Quarterly**: Update dependencies and security patches
- **Annually**: Conduct penetration testing

### Dependency Security

- Use `pip-audit` to scan Python dependencies
- Monitor CVE databases for security advisories
- Keep base Docker images updated
- Use minimal base images (Alpine, distroless)

### Backup Security

- **Encrypt backups** at rest and in transit
- **Secure backup storage** with access controls
- **Test backup restoration** procedures
- **Monitor backup integrity** and completeness

## 📚 Security Resources

### Documentation

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Docker Security](https://docs.docker.com/engine/security/)
- [Kubernetes Security](https://kubernetes.io/docs/concepts/security/)

### Security Tools

- **Static Analysis**: `bandit`, `safety`, `semgrep`
- **Dependency Scanning**: `pip-audit`, `trivy`
- **Container Scanning**: `clair`, `aqua`, `twistlock`
- **Runtime Security**: `falco`, `sysdig`

## ⚠️ Security Disclaimers

- This guide provides baseline security measures
- Additional security controls may be required for your environment
- Regular security assessments by qualified professionals are recommended
- Security is an ongoing process, not a one-time configuration
- Always test security measures in non-production environments first