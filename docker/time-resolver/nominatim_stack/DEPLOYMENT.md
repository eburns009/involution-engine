# Production Deployment Guide
# Address-to-Timezone Resolution System
## Version 1.0 - Production Ready

---

## 🎯 System Overview

This system provides comprehensive address-to-timezone resolution with historical accuracy, supporting:

- **Address Geocoding**: Convert addresses to precise coordinates
- **Historical Timezone Resolution**: Accurate timezone calculations for any date/time
- **Integrated Pipeline**: Complete address → coordinates → timezone workflow
- **Production Monitoring**: Comprehensive health checks and performance metrics
- **Automated Maintenance**: Self-healing with backup and recovery

---

## 🏗️ Architecture Components

### Core Services
- **Time Resolver** (Port 8082): Historical timezone calculation engine
- **Geocoding Gateway** (Port 8086): Address-to-coordinates conversion
- **Integrated Service** (Port 8087): Complete pipeline orchestration
- **Monitoring Dashboard** (Port 8088): Real-time system monitoring
- **NGINX Caching Proxy** (Port 8090): High-performance caching layer for Nominatim

### Supporting Infrastructure
- **Nominatim** (Port 8080): OpenStreetMap geocoding service
- **PostgreSQL**: Geospatial database with historical data
- **Docker Compose**: Container orchestration
- **Cron Jobs**: Automated maintenance and monitoring

---

## 🚀 Quick Start Deployment

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- 50GB disk space minimum
- Linux/Unix operating system

### 1. Clone and Setup
```bash
git clone <repository>
cd docker/time-resolver/nominatim_stack

# Review configuration
cp .env.example .env
# Edit .env with your settings
```

### 2. Launch Services
```bash
# Start core infrastructure
docker-compose up -d nominatim

# Wait for Nominatim to initialize (5-10 minutes)
docker-compose logs -f nominatim

# Start NGINX caching proxy (optional but recommended)
docker-compose -f docker-compose.yml -f docker-compose.nginx.yml up -d nginx

# Start application services
python test_geocoding_api.py &          # Port 8086
python integrated_service.py &         # Port 8087

# Start Time Resolver
cd ../time_resolver
RESOLVER_PATCH_FILE=config/patches_us_pre1967.json python -m time_resolver.api &  # Port 8082
```

### 3. Verify Deployment
```bash
# Run comprehensive validation
./scripts/release_gate.sh

# Run integration tests
./scripts/phase4_integration_test.sh

# Test complete pipeline
curl 'http://localhost:8087/resolve?address=Monaco&local_datetime=2023-07-01T12:00:00'
```

---

## 📊 Production Configuration

### Environment Variables
```bash
# Core services
NOMINATIM_BASE_URL=http://localhost:8080
GEOCODING_SERVICE_URL=http://localhost:8086
TIME_RESOLVER_URL=http://localhost:8082
INTEGRATED_SERVICE_URL=http://localhost:8087

# Database settings
POSTGRES_USER=nominatim
POSTGRES_DB=nominatim
POSTGRES_PASSWORD=<secure_password>

# Resource limits
THREADS=4
WORKERS=2
DISABLE_RATE_LIMIT=0
```

### Docker Compose Production Overrides
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  nominatim:
    restart: always
    environment:
      - NOMINATIM_EXTRA_PARAMS=--enable-debug-statements=false
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  postgres:
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
    driver: local
```

---

## 🔧 Production Hardening

### Security Configuration
```bash
# Set secure passwords
export POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Restrict network access
iptables -A INPUT -p tcp --dport 8080:8088 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080:8088 -j DROP

# Enable SSL/TLS (recommended)
# Configure reverse proxy (nginx/traefik) with certificates
```

### Performance Tuning
```bash
# PostgreSQL optimization
echo "shared_buffers = 256MB" >> postgresql.conf
echo "effective_cache_size = 1GB" >> postgresql.conf
echo "work_mem = 64MB" >> postgresql.conf

# Docker resource limits
docker-compose config --services | xargs -I {} docker update --cpus="2" --memory="4g" {}
```

### Backup Configuration
```bash
# Set up automated backups
crontab -e
# Add: 0 4 * * 0 /path/to/scripts/backup_restore.sh backup full

# Configure backup retention
export BACKUP_RETENTION_DAYS=30
export MAX_BACKUPS=10
```

---

## 📈 Monitoring & Alerting

### Health Monitoring Endpoints
- **System Status**: `http://localhost:8088/status`
- **Service Health**:
  - Time Resolver: `http://localhost:8082/health`
  - Geocoding: `http://localhost:8086/health`
  - Integrated: `http://localhost:8087/health`

### Key Metrics to Monitor
```bash
# Response times (target: <2s)
curl -w "@curl-format.txt" http://localhost:8087/health

# Error rates (target: <1%)
grep "ERROR" /var/log/application.log | wc -l

# Resource usage (target: <80%)
./scripts/performance_metrics.sh
```

### Automated Monitoring Schedule
```cron
# /etc/cron.d/system-monitoring
0 * * * *     root    /scripts/performance_metrics.sh
0 */4 * * *   root    /scripts/disk_monitor.sh
0 */6 * * *   root    /scripts/check_nominatim_health.sh
0 2 * * *     root    /scripts/log_rotation.sh
0 1 * * 0     root    /scripts/housekeeping.sh
0 4 * * 0     root    /scripts/backup_restore.sh backup full
```

---

## 🚨 Operational Procedures

### Daily Operations Checklist
- [ ] Check system health dashboard
- [ ] Review error logs for anomalies
- [ ] Verify backup completion status
- [ ] Monitor disk space usage
- [ ] Validate service response times

### Weekly Maintenance
- [ ] Run comprehensive housekeeping
- [ ] Verify backup integrity
- [ ] Review performance trends
- [ ] Update security patches
- [ ] Check database optimization needs

### Emergency Procedures

#### Service Restart
```bash
# Restart individual service
docker-compose restart nominatim

# Restart all services
docker-compose down && docker-compose up -d

# Check service logs
docker-compose logs --tail=100 <service_name>
```

#### Database Recovery
```bash
# Restore from backup
./scripts/backup_restore.sh restore /backups/backup_YYYYMMDD_HHMMSS

# Manual database repair
docker-compose exec nominatim psql -U nominatim -c "REINDEX DATABASE nominatim;"
```

#### Performance Issues
```bash
# Check system resources
./scripts/performance_metrics.sh

# Clear caches
./scripts/housekeeping.sh

# Restart services if needed
docker-compose restart
```

---

## 📋 Testing & Validation

### Pre-Production Tests
```bash
# Infrastructure validation
./scripts/release_gate.sh

# Integration testing
./scripts/phase4_integration_test.sh

# Performance benchmarking
./scripts/performance_metrics.sh

# Security scanning
./scripts/security_audit.sh  # If available
```

### Production Smoke Tests
```bash
# Test critical workflows
curl 'http://localhost:8087/resolve?address=Fort%20Knox&local_datetime=1943-06-15T14:30:00'

# Verify historical accuracy
curl 'http://localhost:8087/resolve?address=Monaco&local_datetime=2023-07-01T12:00:00'

# Check error handling
curl 'http://localhost:8087/resolve?address=InvalidPlace&local_datetime=2023-01-01T12:00:00'
```

### Performance Benchmarks
- **Address Resolution**: <2 seconds (95th percentile)
- **Historical Accuracy**: ±0 minutes for post-1970 dates
- **Service Availability**: 99.9% uptime target
- **Resource Usage**: <80% CPU/Memory during peak load

---

## 🔧 Troubleshooting Guide

### Common Issues

#### "Service Unavailable" Errors
```bash
# Check service status
docker-compose ps

# Check logs
docker-compose logs <service_name>

# Restart if needed
docker-compose restart <service_name>
```

#### Database Connection Issues
```bash
# Check PostgreSQL status
docker-compose exec nominatim pg_isready

# Verify credentials
docker-compose exec nominatim psql -U nominatim -l

# Check disk space
df -h
```

#### Slow Response Times
```bash
# Check system load
./scripts/performance_metrics.sh

# Clear caches
./scripts/housekeeping.sh

# Check for blocking queries
docker-compose exec nominatim psql -U nominatim -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
```

#### High Disk Usage
```bash
# Run cleanup
./scripts/log_rotation.sh
./scripts/housekeeping.sh

# Check largest directories
du -sh /* | sort -hr | head -10

# Clean Docker resources
docker system prune -f
```

---

## 🎯 Production Deployment Checklist

### Pre-Deployment
- [ ] Server provisioning complete
- [ ] Security hardening applied
- [ ] SSL certificates configured
- [ ] Backup procedures tested
- [ ] Monitoring systems configured
- [ ] Documentation reviewed

### Deployment
- [ ] Release gate validation passed
- [ ] Services deployed in order
- [ ] Health checks passing
- [ ] Integration tests successful
- [ ] Performance benchmarks met
- [ ] Monitoring alerts active

### Post-Deployment
- [ ] Smoke tests completed
- [ ] User acceptance testing
- [ ] Documentation updated
- [ ] Team training completed
- [ ] Incident response procedures reviewed

---

## 📞 Support & Maintenance

### System Administration
- **Logs Location**: `/var/log/` and container logs via `docker-compose logs`
- **Configuration**: `docker-compose.yml`, `.env`, `scripts/` directory
- **Monitoring**: Access web dashboard at `http://localhost:8088`
- **Backups**: Automated to `/backups/` with 30-day retention

### Performance Optimization
- **Database Tuning**: Regular VACUUM/ANALYZE via housekeeping
- **Cache Management**: Automatic cleanup and optimization
- **Resource Scaling**: Horizontal scaling via Docker Compose replicas
- **Load Balancing**: Configure reverse proxy for high availability

### Support Contacts
- **System Administrator**: [Contact Information]
- **Database Administrator**: [Contact Information]
- **Application Support**: [Contact Information]
- **Emergency Escalation**: [Contact Information]

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-09-27 | Initial production release |
| | | Complete address-to-timezone pipeline |
| | | Comprehensive monitoring and automation |
| | | Production-ready deployment procedures |

---

## ⚡ NGINX Caching Proxy

### Overview
The integrated NGINX caching proxy provides high-performance caching for Nominatim geocoding requests with intelligent cache policies and rate limiting.

### Features
- **Smart Caching**: Different cache TTLs for different endpoint types
  - Search queries: 24 hours
  - Reverse geocoding: 12 hours
  - Details: 7 days
  - Status checks: No caching
- **Rate Limiting**: Protects against abuse with configurable limits
- **Compression**: Automatic gzip compression for better performance
- **Security Headers**: Standard security headers automatically added
- **Monitoring**: Built-in status endpoint for monitoring

### Usage
```bash
# Start with caching proxy
docker-compose -f docker-compose.yml -f docker-compose.nginx.yml up -d

# Access Nominatim through cache (recommended)
curl "http://localhost:8090/search?q=Monaco"

# Access Nominatim directly (bypass cache)
curl "http://localhost:8080/search?q=Monaco"

# Monitor cache performance
curl "http://localhost:8090/nginx_status"
```

### Cache Management
```bash
# View cache statistics
docker exec nominatim-nginx ls -la /var/cache/nginx/nominatim/

# Clear cache (restart container)
docker-compose restart nginx

# Bypass cache for debugging
curl "http://localhost:8090/search?q=Monaco&nocache=1"
```

### Performance Benefits
- **Response Time**: Up to 10x faster for cached requests
- **Reduced Load**: Significant reduction in database queries
- **Bandwidth**: Automatic compression reduces bandwidth usage
- **Availability**: Serves cached content even during brief service interruptions

---

## 📚 Additional Resources

- **API Documentation**: Available at service `/docs` endpoints
- **Monitoring Dashboard**: `http://localhost:8088`
- **Integration Examples**: See `scripts/phase4_integration_test.sh`
- **Performance Metrics**: Generated by `scripts/performance_metrics.sh`

**🚀 System Status: PRODUCTION READY**

*This deployment guide ensures reliable, scalable, and maintainable operation of the address-to-timezone resolution system in production environments.*