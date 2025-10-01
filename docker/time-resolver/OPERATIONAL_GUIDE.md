# Time Resolver Operational Guide

## TZDB Bundling & Update Strategy

### Current Setup

The Time Resolver uses **bundled tzdata** via Python's `tzdata` package for maximum reproducibility and control:

```dockerfile
# From requirements.txt
tzdata==2025.1
```

**Benefits of bundled tzdata:**
- ✅ **Reproducible builds**: Same IANA version across all environments
- ✅ **No system dependencies**: Works regardless of host OS tzdata version
- ✅ **Version control**: Explicit tzdata version in requirements.txt
- ✅ **Fast deployments**: No need to sync system packages

### Update Schedule

**Monthly updates** or when IANA releases critical patches:

1. **Monitor IANA releases**: https://www.iana.org/time-zones
2. **Update requirements.txt**: Bump tzdata version
3. **Test historical accuracy**: Run audit suite
4. **Deploy with health checks**: Verify `/healthz` reports new version

### Update Process

```bash
# 1. Check current version
curl http://localhost:8080/healthz | jq '.tzdb_version'

# 2. Update requirements.txt
echo "tzdata==2025.2" >> requirements.txt

# 3. Rebuild and test
make build
make test

# 4. Run comprehensive audit
make audit

# 5. Deploy with health verification
make run &
sleep 5
curl http://localhost:8080/healthz | jq '.'
```

### Backzone Support

For **historical accuracy before 1970**, enable backzone data:

#### Current Implementation
- **Python tzdata**: Includes backzone by default ✅
- **Patch files**: Custom historical corrections for US pre-1967

#### Manual Backzone (if using system tzdb)
```bash
# On systems using system tzdb, ensure backzone is enabled
# Ubuntu/Debian:
sudo apt-get install tzdata-dev

# Verify backzone data
python -c "
from zoneinfo import ZoneInfo
# Test pre-1970 timezone
ny = ZoneInfo('America/New_York')
print('Backzone available:', ny is not None)
"
```

### Cache Strategy

**LRU Cache** for coordinate→timezone lookups:

```python
@lru_cache(maxsize=1024)
def latlon_to_zone_cached(lat_rounded: float, lon_rounded: float) -> str:
    # Round to ~111m precision for cache efficiency
    # Most timezone boundaries are much larger than this
```

**Monitor cache performance:**
```bash
curl http://localhost:8080/healthz | jq '.cache_stats'
```

**Expected performance:**
- Cold start: 0% hit rate
- Warm service: 70-90% hit rate (with coordinate rounding)
- Cache size: 1024 entries (~64KB memory)

### Provenance Logging

**Every chart request** generates structured logs for audit trails:

```bash
# Chart request
CHART_REQUEST request_id=123 local_datetime=1943-06-15T14:30:00
lat=37.890000 lon=-85.960000 parity_profile=strict_history
tzdb_version=tzdata-2025.1 patch_version=patches-e868200c

# Chart completion
CHART_COMPLETED request_id=123 utc=1943-06-15T17:30:00Z
zone_id=America/New_York offset_seconds=-10800 dst_active=True
confidence=high patches_applied=['fort_knox_1943'] warnings=0
```

**Log analysis patterns:**
```bash
# Find all Fort Knox corrections
grep "fort_knox_1943" app.log

# Monitor confidence levels
grep "confidence=low" app.log

# Track patch effectiveness
grep "patches_applied=\[\]" app.log | wc -l
```

### Health Monitoring

**Three-tier health checks:**

1. **Basic**: `/health` - Minimal response for load balancers
2. **Detailed**: `/healthz` - Full operational status
3. **Performance**: Cache stats, version info, patch status

```bash
# Load balancer health check
curl -f http://localhost:8080/health

# Operations monitoring
curl http://localhost:8080/healthz | jq '{
  status: .status,
  tzdb_version: .tzdb_version,
  patch_version: .patch_version,
  cache_hit_rate: .cache_stats.hit_rate,
  patches_loaded: .patches_loaded
}'
```

### Deployment Strategy

**Blue-green deployment** with version verification:

```bash
# 1. Deploy new version
docker run -d -p 8081:8080 time-resolver:v2

# 2. Health check with version verification
curl http://localhost:8081/healthz | jq '.tzdb_version'

# 3. Audit against known test cases
python audit_runner.py --base-url http://localhost:8081

# 4. Switch traffic (nginx/load balancer)
# 5. Monitor logs for 24h
# 6. Decommission old version
```

### Performance Considerations

**Container sizing:**
- Memory: 256MB baseline + 64KB per 1k cache entries
- CPU: Minimal (timezone lookups are I/O bound)
- Storage: 50MB image + 1MB patch files

**Scaling:**
- Stateless service: Horizontal scaling friendly
- Cache: Per-container (acceptable for coordinate lookups)
- Patches: Immutable after container start

### Troubleshooting

**Common issues:**

1. **Missing patches**: Check `RESOLVER_PATCH_FILE` environment variable
2. **Cache cold starts**: Monitor `cache_stats.hit_rate` in `/healthz`
3. **Version drift**: Verify `/healthz` reports expected `tzdb_version`
4. **Log volume**: Consider structured logging with retention policies

**Debug commands:**
```bash
# Verify tzdata version
python -c "import tzdata; print(tzdata.__version__)"

# Check patch file integrity
python -c "
import json, hashlib
with open('config/patches_us_pre1967.json', 'rb') as f:
    print('MD5:', hashlib.md5(f.read()).hexdigest()[:8])
"

# Test specific coordinates
curl -X POST http://localhost:8080/v1/time/resolve \
  -H "Content-Type: application/json" \
  -d '{"local_datetime": "1943-06-15T14:30:00", "place": {"lat": 37.89, "lon": -85.96}, "parity_profile": "strict_history"}'
```

### Security Considerations

- **Non-root container**: Service runs as `timeresolver` user
- **Minimal attack surface**: Only timezone data and computation
- **No secrets**: All configuration via environment variables
- **Read-only patches**: Historical data is immutable

This operational guide ensures reliable, auditable, and maintainable timezone resolution with clear upgrade paths and monitoring strategies.