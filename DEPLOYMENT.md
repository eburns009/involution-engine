# Involution Engine - Production Deployment Guide

Complete guide for deploying the Involution Engine to production environments with enterprise-grade reliability, security, and monitoring.

## Requirements

### CSPICE Thread-Safety
**CRITICAL**: CSPICE is NOT thread-safe. Use process-based workers only.

### Rate Limiting Dependencies
**Redis Required**: Rate limiting uses shared Redis storage for consistency across multiple workers.
- Without Redis: Each worker maintains separate rate limits (10 req/min per worker)
- With Redis: Rate limits shared across all workers (10 req/min total)
- Set `RATE_LIMIT_STORAGE_URI=redis://your-redis:6379/0`

**Proxy Support**: Rate limiting uses real client IP from `X-Forwarded-For` header.
- **Important**: Only deploy behind trusted reverse proxies (nginx, CloudFlare, etc.)
- **Security**: Untrusted proxies could spoof IPs to bypass rate limits
- Direct connections fall back to socket IP address

## Production Deployment

### 1. Quick Start
```bash
# Set your domain
export ALLOWED_ORIGINS=https://your-domain.com

# Start production server (automated)
./scripts/start_prod.sh
```

### 2. Manual Deployment
```bash
# Set production environment
export ENVIRONMENT=production
export DEBUG=0
export DISABLE_RATE_LIMIT=0
export ALLOWED_ORIGINS=https://your-domain.com
export RATE_LIMIT_STORAGE_URI=redis://your-redis:6379/0

# Optional: Select ephemeris version
export KERNEL_SET_TAG=DE440              # Standard (1550-2650 CE, 114MB)
# export KERNEL_SET_TAG=DE441            # Historical (13201 BCE - 17191 CE, 310MB)
# export METAKERNEL_PATH=kernels/involution_de441.tm

# Ensure kernels are available
cd services/spice && ./download_kernels.sh && cd ../..

# Start with optimal worker count (2 per vCPU)
gunicorn services.spice.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers $((\$(nproc) * 2)) \
  --bind 0.0.0.0:8000 \
  --timeout 30 \
  --preload=false \
  --max-requests 1000
```

### 3. Using Configuration File
```bash
gunicorn services.spice.main:app -c gunicorn.conf.py
```

### 4. Dual Ephemeris Deployment
For research applications requiring both modern and historical coverage:

```bash
# Automated dual deployment
./scripts/start_dual_ephemeris.sh
```

This creates two services:
- **Modern (DE440)** on port 8000: 1550-2650 CE coverage (114MB)
- **Historical (DE441)** on port 8001: 13201 BCE - 17191 CE coverage (310MB)

```bash
# Test both services
./scripts/test_dual_ephemeris.sh

# Smoke test ephemeris coverage and observer frame behavior
./scripts/smoke_test_ephemeris.sh

# Quick verification (matches manual curl commands)
./scripts/quick_smoke.sh

# Stop both services
./scripts/stop_dual_ephemeris.sh
```

### 5. Smart Gateway (Optional)
For UI applications, deploy an intelligent routing gateway:

```bash
# Start backend services
./scripts/start_dual_ephemeris.sh

# Start gateway
cd gateway && npm install && npm start
```

**Gateway Benefits:**
- **Auto-routing**: Modern dates → DE440 (fast), historical → DE441 (comprehensive)
- **User prompts**: "Enable Historical Pack" for out-of-range dates
- **Manual overrides**: `?kernel=de441` or `x-historical-enabled: true` header
- **Resource optimization**: Only uses heavy DE441 service when needed

**API Examples:**
```bash
# Modern date → Auto-routes to DE440
POST http://localhost:3000/calculate
{"birth_time":"2024-06-21T18:00:00Z",...}

# Historical date → Prompts for Historical Pack
POST http://localhost:3000/calculate
{"birth_time":"1066-10-14T12:00:00Z",...}
# Returns: {"error":"Historical ephemeris required",...}

# Force historical ephemeris
POST http://localhost:3000/calculate?kernel=de441
{"birth_time":"1066-10-14T12:00:00Z",...}
```

### 6. Container Deployment
```dockerfile
FROM python:3.12-slim

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn

# Copy application
COPY . /app
WORKDIR /app

# Download kernels
RUN cd services/spice && ./download_kernels.sh

# Set production environment
ENV ENVIRONMENT=production
ENV DEBUG=0
ENV DISABLE_RATE_LIMIT=0
ENV WORKERS=4

EXPOSE 8000
CMD ["./scripts/start_prod.sh"]
```

## Security Checklist

- ✅ **DEBUG=0**: /debug endpoint blocked in production
- ✅ **DISABLE_RATE_LIMIT=0**: Rate limiting enforced (20/min per IP)
- ✅ **ENVIRONMENT=production**: Production mode enabled
- ✅ **ALLOWED_ORIGINS**: Set to your actual frontend domain
- ✅ **Process isolation**: Each worker has independent SPICE state

## Performance Guidelines

### Worker Scaling
- **CPU-bound workload**: 2 workers per vCPU (recommended start)
- **Memory usage**: ~110MB per worker (SPICE kernels loaded)
- **Maximum workers**: Cap at 8 for memory management

### Monitoring
- **Health check**: `GET /health`
- **Metrics**: `GET /metrics` (latency, error rates)
- **Performance target**: <10ms p95 latency

### Load Testing
```bash
# Test concurrent requests
python -c "
import requests, concurrent.futures, time
url = 'http://localhost:8000/calculate'
payload = {
    'birth_time': '2024-06-21T18:00:00Z',
    'latitude': 37.7749, 'longitude': -122.4194,
    'elevation': 25, 'zodiac': 'tropical', 'ayanamsa': 'lahiri'
}

def test_req(_):
    start = time.perf_counter()
    r = requests.post(url, json=payload, timeout=10)
    return r.status_code, (time.perf_counter() - start) * 1000

with concurrent.futures.ThreadPoolExecutor(20) as e:
    results = list(e.map(test_req, range(100)))

success = sum(1 for code, _ in results if code == 200)
avg_ms = sum(ms for _, ms in results) / len(results)
print(f'Success: {success}/100, Avg: {avg_ms:.1f}ms')
"
```

## Troubleshooting

### SPICE Kernel Issues
```bash
# Re-download kernels if corrupted
cd services/spice
rm -rf kernels/
./download_kernels.sh
```

### Worker Memory Issues
```bash
# Reduce worker count if memory constrained
export WORKERS=2
./scripts/start_prod.sh
```

### Rate Limiting Too Aggressive
```bash
# Temporarily disable for debugging (NOT for production)
export DISABLE_RATE_LIMIT=1
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | - | Set to `production` |
| `DEBUG` | 0 | Set to `0` to disable /debug |
| `DISABLE_RATE_LIMIT` | 0 | Set to `0` to enforce limits |
| `ALLOWED_ORIGINS` | - | Comma-separated frontend domains |
| `WORKERS` | cpu_count*2 | Number of worker processes |
| `PORT` | 8000 | Server port |
| `LOG_LEVEL` | info | Logging level |

---

## 🏗️ Enterprise Production Deployment

### Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Load Balancer │    │     Nginx        │    │  Engine Cluster │
│   (Cloudflare)  │───▶│   (SSL Term)     │───▶│   (2 instances) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              │                         ▼
                              │                 ┌─────────────────┐
                              │                 │     Redis       │
                              │                 │   (Cache/RL)    │
                              │                 └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Time Resolver │    │   PostgreSQL    │
                       │    Service      │    │   (Optional)    │
                       └─────────────────┘    └─────────────────┘
```

## 🐳 Docker Production Deployment

### Quick Start with Docker Compose

```bash
# 1. Clone repository
git clone https://github.com/yourusername/involution-engine.git
cd involution-engine

# 2. Configure environment
cp .env.example .env
# Edit .env with your production settings

# 3. Deploy full production stack
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify deployment
curl -f https://yourdomain.com/health
```

### Production Environment Configuration

Create your `.env` file with these critical settings:

```bash
# === REQUIRED PRODUCTION SETTINGS ===
ENV=production
DEBUG=0
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
TRUSTED_HOSTS=yourdomain.com,app.yourdomain.com,api.yourdomain.com

# === SECURITY CONFIGURATION ===
ENABLE_SECURITY_HEADERS=true
HSTS_MAX_AGE=31536000
RATE_LIMIT_STORAGE_URI=redis://redis:6379/0
DB_PASSWORD=your_secure_database_password_here
REDIS_PASSWORD=your_secure_redis_password_here

# === PERFORMANCE SETTINGS ===
WORKERS=4
WORKER_TIMEOUT=30
MAX_REQUEST_SIZE=1048576
ENABLE_POSITION_CACHE=true

# === MONITORING & LOGGING ===
LOG_LEVEL=INFO
LOG_FORMAT=json
METRICS_ENABLED=true
ENABLE_REQUEST_LOGGING=true
```

## 🔒 Security Hardening

### SSL/TLS Configuration

1. **Configure SSL certificates:**
   ```bash
   mkdir -p nginx/ssl
   # Place your SSL certificates
   cp yourdomain.crt nginx/ssl/
   cp yourdomain.key nginx/ssl/
   ```

2. **Nginx SSL configuration:**
   ```nginx
   server {
       listen 443 ssl http2;
       server_name yourdomain.com;

       ssl_certificate /etc/nginx/ssl/yourdomain.crt;
       ssl_certificate_key /etc/nginx/ssl/yourdomain.key;
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM;

       # Security headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload";
       add_header X-Frame-Options DENY;
       add_header X-Content-Type-Options nosniff;
   }
   ```

### Security Monitoring

```bash
# Run security audit
./scripts/security_audit.sh

# Continuous security monitoring
./scripts/security_monitor.sh

# View security metrics
curl https://yourdomain.com/health | jq '.checks.security'
```

## 📊 Monitoring & Observability

### Health Checks

The comprehensive health endpoint at `/health` provides:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "uptime_seconds": 3600,
  "checks": {
    "spice": {"status": "healthy", "kernels_loaded": 15},
    "time_resolver": {"status": "healthy", "tzdb_version": "2023c"},
    "performance": {"status": "healthy", "latency_p95_ms": 245},
    "security": {"status": "healthy", "blocked_requests": 5},
    "system": {"status": "healthy", "memory_usage_mb": 512.3}
  }
}
```

### Grafana Dashboards

Enable monitoring stack:

```bash
docker-compose -f docker-compose.prod.yml --profile monitoring up -d
```

Access dashboards:
- **Grafana**: https://yourdomain.com:3000
- **Prometheus**: Internal metrics collection

### Performance Monitoring

```bash
# Performance metrics script
./scripts/performance_metrics.sh

# Real-time monitoring
watch -n 5 'curl -s https://yourdomain.com/health | jq ".checks.performance"'
```

## 🚀 Scaling & Performance

### Horizontal Scaling

```bash
# Scale engine instances
docker-compose -f docker-compose.prod.yml up -d --scale engine-1=3 --scale engine-2=3

# Verify load distribution
for i in {1..10}; do
  curl -s https://yourdomain.com/health | jq '.service.instance_id'
done
```

### Performance Optimization

1. **Worker tuning:**
   ```bash
   # CPU-intensive: 2 workers per core
   WORKERS=$(($(nproc) * 2))

   # Memory-optimized: Monitor and adjust
   WORKER_MEMORY_LIMIT=2048m
   ```

2. **Cache optimization:**
   ```bash
   # Enable all caching
   ENABLE_POSITION_CACHE=true
   POSITION_CACHE_TTL=3600
   ENABLE_AYANAMSA_CACHE=true
   AYANAMSA_CACHE_TTL=86400
   ```

3. **Database tuning:**
   ```bash
   # Connection pool sizing
   DB_POOL_SIZE=10
   DB_MAX_OVERFLOW=20
   ```

### Load Testing

```bash
# Stress test with artillery
npm install -g artillery
artillery quick --count 100 --num 10 https://yourdomain.com/health

# Custom load test
python tests/load_test.py --url https://yourdomain.com --concurrent 50 --requests 1000
```

## 💾 Backup & Recovery

### Automated Backup Configuration

```bash
# Enable backup service
docker-compose -f docker-compose.prod.yml --profile backup up -d

# Configure backup schedule (daily at 2 AM)
BACKUP_SCHEDULE="0 2 * * *"
BACKUP_RETENTION_DAYS=30
```

### Backup Strategy

- **Database backups**: Daily with 30-day retention
- **Configuration**: Version controlled in git
- **SPICE kernels**: Weekly backup with integrity checks
- **Application logs**: 30-day rolling retention

### Disaster Recovery Procedures

1. **RTO (Recovery Time Objective)**: <30 minutes
2. **RPO (Recovery Point Objective)**: <4 hours

```bash
# Emergency recovery
./scripts/emergency_recovery.sh

# Restore from specific backup
./scripts/restore_backup.sh 2024-01-01
```

## 🔧 Operations & Maintenance

### Daily Operations

```bash
# Daily health check
./scripts/daily_health_check.sh

# Check logs for errors
./scripts/log_analysis.sh --errors --last 24h

# Backup verification
./scripts/verify_backups.sh
```

### Regular Maintenance

- **Weekly**: Security audit, dependency updates
- **Monthly**: Performance review, capacity planning
- **Quarterly**: Disaster recovery testing

### Update Procedures

```bash
# 1. Backup current state
./scripts/backup.sh

# 2. Pull latest code
git pull origin main

# 3. Update dependencies
pip install -r requirements.txt

# 4. Rolling update (zero downtime)
./scripts/rolling_update.sh

# 5. Verify deployment
curl -f https://yourdomain.com/health
```

## 🚨 Troubleshooting

### Common Issues & Solutions

**High memory usage:**
```bash
# Check memory stats
docker stats

# Reduce worker count if needed
export WORKERS=2
docker-compose -f docker-compose.prod.yml restart
```

**Slow response times:**
```bash
# Check performance metrics
curl https://yourdomain.com/health | jq '.checks.performance'

# Enable caching
export ENABLE_POSITION_CACHE=true
docker-compose -f docker-compose.prod.yml restart
```

**Security alerts:**
```bash
# Check security status
./scripts/security_monitor.sh

# Block malicious IPs
./scripts/block_ip.sh 192.168.1.100
```

### Emergency Procedures

**Service outage:**
```bash
# Quick restart
docker-compose -f docker-compose.prod.yml restart

# Fallback to maintenance mode
./scripts/maintenance_mode.sh enable
```

**Security incident:**
```bash
# Enable enhanced monitoring
./scripts/security_incident_response.sh

# Review recent access logs
./scripts/security_log_analysis.sh --last 1h
```

## 📞 Support & Contacts

### Monitoring Alerts

Configure alerts for:
- Health check failures (critical)
- High error rates >5% (warning)
- Security events >50/hour (warning)
- Performance degradation P95>1000ms (warning)

### Documentation Links

- **API Documentation**: `/docs` endpoint
- **Security Guide**: `SECURITY.md`
- **CI/CD Guide**: `docs/ci-cd.md`
- **Architecture**: `docs/api.md`

### Emergency Contacts

```bash
# Emergency runbook
./scripts/emergency_runbook.sh

# Escalation procedures
./scripts/escalation_matrix.sh
```

---

## ✅ Deployment Verification Checklist

Your production deployment is ready when:

- [ ] All health checks return "healthy" status
- [ ] Security audit passes with score >90%
- [ ] Performance tests show P95 latency <500ms
- [ ] SSL/TLS configuration verified (A+ rating)
- [ ] Rate limiting and CORS properly configured
- [ ] Monitoring and alerting functional
- [ ] Backup procedures tested and verified
- [ ] Emergency procedures documented and tested

**🎉 Production Ready!** Your Involution Engine deployment is enterprise-grade and ready for production traffic.