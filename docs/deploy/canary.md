# Canary Deployment Guide

This guide explains how to perform safe canary deployments of the Involution Engine using weighted traffic distribution.

## Overview

The canary deployment system uses Nginx to distribute traffic between stable and canary versions:
- **90/10 split**: Initial canary testing with 10% traffic
- **50/50 split**: Expanded testing if metrics look good
- **100/0 split**: Full rollout or complete rollback

## Prerequisites

- Docker and Docker Compose installed
- SPICE kernels volume available (`kernels` external volume)
- Monitoring setup for observing metrics

## Deployment Process

### 1. Prepare Canary Image

Build the new version with a canary tag:

```bash
# Build canary version
docker build -f server/Dockerfile.de440-1900 -t involution-engine:de440-1900-canary .

# Verify image
docker images | grep canary
```

### 2. Start Canary Deployment

Deploy with 90/10 traffic split:

```bash
# Start canary deployment
docker-compose -f docker-compose.canary.yml up -d

# Verify all services are healthy
docker-compose -f docker-compose.canary.yml ps
docker-compose -f docker-compose.canary.yml logs --tail=50
```

### 3. Monitor Initial Canary (90/10)

Monitor for **2-4 hours** and check:

#### Health Endpoints
```bash
# Main load balancer health
curl http://localhost:8080/healthz

# Direct stable access
curl http://localhost:8081/healthz

# Direct canary access
curl http://localhost:8082/healthz
```

#### Metrics Comparison
```bash
# Overall metrics through load balancer
curl http://localhost:8080/metrics

# Stable version metrics
curl http://localhost:8081/metrics

# Canary version metrics
curl http://localhost:8082/metrics
```

#### Key Metrics to Watch
- **P95 Latency**: Should remain < 200ms
- **5xx Error Rate**: Should be < 0.1%
- **Cache Hit Rate**: Should match stable version
- **Health Check Status**: All services green
- **Memory Usage**: Within expected bounds

#### Log Analysis
```bash
# Check for errors in canary
docker logs engine-canary | grep ERROR

# Compare error patterns
docker logs engine-stable | grep ERROR | wc -l
docker logs engine-canary | grep ERROR | wc -l
```

### 4. Expand to 50/50 (If Green)

If metrics look good after 2-4 hours, increase canary traffic:

```bash
# Edit ops/nginx/canary.conf
# Change weights to: weight=50 for both stable and canary

# Update the upstream block:
upstream involution_engine {
    server engine-stable:8080 weight=50;   # vX (current)
    server engine-canary:8080 weight=50;   # vX+1 (new)
    keepalive 64;
}

# Reload Nginx configuration (zero downtime)
docker exec nginx-canary nginx -s reload
```

Monitor for another **2-4 hours** with equal traffic distribution.

### 5. Complete Rollout (100%)

If 50/50 testing is successful, complete the rollout:

```bash
# Update weights to 0/100 (canary becomes primary)
# Edit ops/nginx/canary.conf:
upstream involution_engine {
    server engine-stable:8080 weight=0;    # vX (old)
    server engine-canary:8080 weight=100;  # vX+1 (new)
    keepalive 64;
}

# Reload configuration
docker exec nginx-canary nginx -s reload

# Monitor for 1 hour, then stop old stable version
docker stop engine-stable

# Update tags for next deployment
docker tag involution-engine:de440-1900-canary involution-engine:de440-1900
```

## Rollback Procedures

### Immediate Rollback (Any Stage)

If issues are detected, perform immediate rollback:

```bash
# Emergency rollback: Route all traffic to stable
# Edit ops/nginx/canary.conf:
upstream involution_engine {
    server engine-stable:8080 weight=100;  # vX (stable)
    server engine-canary:8080 weight=0;    # vX+1 (problematic)
    keepalive 64;
}

# Reload Nginx (takes effect immediately)
docker exec nginx-canary nginx -s reload

# Verify rollback
curl http://localhost:8080/healthz
```

### Complete Rollback

Remove canary version entirely:

```bash
# Stop canary container
docker stop engine-canary

# Remove from upstream (optional)
# Edit ops/nginx/canary.conf to only include stable server

# Reload configuration
docker exec nginx-canary nginx -s reload
```

## Traffic Distribution Verification

### Test Traffic Distribution

Verify traffic is being distributed correctly:

```bash
# Make multiple requests and check X-Request-Id distribution
for i in {1..100}; do
  curl -s -I http://localhost:8080/healthz | grep X-Request-Id
done | sort | uniq -c

# Check access logs
docker logs nginx-canary | tail -100
```

### A/B Testing Endpoints

Use direct access endpoints for validation:

```bash
# Test specific version behavior
curl http://localhost:8080/stable/v1/positions -X POST -d '{...}'
curl http://localhost:8080/canary/v1/positions -X POST -d '{...}'
```

## Monitoring and Alerting

### Key Monitoring Points

1. **Response Time Distribution**
   - P50, P95, P99 latencies
   - Compare stable vs canary directly

2. **Error Rates**
   - HTTP 5xx responses
   - Application error logs
   - Health check failures

3. **Resource Usage**
   - Memory consumption
   - CPU utilization
   - Redis cache performance

4. **Business Metrics**
   - Cache hit rates
   - Request volume distribution
   - Response accuracy (drift detection)

### Automated Monitoring

Set up alerts for:
- P95 latency > 300ms
- Error rate > 0.5%
- Health check failures
- Memory usage > 80%

## Troubleshooting

### Common Issues

1. **Canary Won't Start**
   ```bash
   # Check container logs
   docker logs engine-canary

   # Verify image
   docker inspect involution-engine:de440-1900-canary

   # Check resource availability
   docker stats
   ```

2. **Traffic Not Distributing**
   ```bash
   # Verify Nginx config syntax
   docker exec nginx-canary nginx -t

   # Check upstream status
   docker exec nginx-canary cat /etc/nginx/conf.d/default.conf

   # Restart Nginx if needed
   docker restart nginx-canary
   ```

3. **Performance Degradation**
   ```bash
   # Compare resource usage
   docker stats engine-stable engine-canary

   # Check Redis connection
   docker exec redis-canary redis-cli ping

   # Analyze slow queries
   docker logs engine-canary | grep "slow"
   ```

### Emergency Procedures

1. **Total System Failure**
   ```bash
   # Immediate rollback to stable only
   docker stop engine-canary nginx-canary
   docker run -d -p 8080:8080 --name emergency-stable involution-engine:de440-1900
   ```

2. **Database/Redis Issues**
   ```bash
   # Check Redis health
   docker exec redis-canary redis-cli info replication

   # Restart Redis if needed
   docker restart redis-canary
   ```

## Best Practices

1. **Always test in staging first** with the same canary setup
2. **Monitor continuously** during canary periods
3. **Have rollback plan ready** before starting deployment
4. **Document any issues** encountered for future deployments
5. **Communicate deployment status** to team
6. **Schedule deployments** during low-traffic periods when possible

## Automation

For production environments, consider automating the canary process:
- Automated metrics collection and comparison
- Auto-rollback on threshold breaches
- Slack/email notifications on deployment events
- Integration with CI/CD pipeline

This manual process provides the foundation for future automation while ensuring safe, observable deployments.