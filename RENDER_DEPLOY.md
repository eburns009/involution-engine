# Render.com Deployment Guide

## Option A: Docker Deploy (Recommended)

**1. Create `render.yaml` (already included):**

```yaml
services:
  - type: web
    name: involution-spice
    env: docker
    plan: starter
    autoDeploy: true
    healthCheckPath: /health
    envVars:
      - key: ALLOWED_ORIGINS
        value: https://your-ui.example
```

**2. Deploy steps:**

1. Connect GitHub repo to Render
2. Service will auto-deploy from `main` branch
3. Dockerfile already configured with gunicorn multi-process
4. Kernels download automatically during build

## Option B: Native Python Deploy

**1. Alternative `render.yaml` for native:**

```yaml
services:
  - type: web
    name: involution-spice
    env: python
    plan: starter
    autoDeploy: true
    region: oregon
    rootDir: services/spice
    buildCommand: |
      pip install -r requirements.txt
      bash download_kernels.sh
    startCommand: >
      gunicorn main:app
      -k uvicorn.workers.UvicornWorker
      --workers 2 --bind 0.0.0.0:$PORT --timeout 30
    healthCheckPath: /health
    envVars:
      - key: ALLOWED_ORIGINS
        value: https://your-ui.example
```

## Post-Deploy Verification

**Replace with your actual Render hostname:**

```bash
BASE="https://involution-spice.onrender.com"

# Health check
curl -s "$BASE/health" | jq .

# Full calculation test
curl -s -X POST "$BASE/calculate" \
  -H 'content-type: application/json' \
  -d '{
    "birth_time": "2024-06-21T18:00:00Z",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "elevation": 50,
    "ayanamsa": "lahiri"
  }' | jq .
```

## Expected Responses

**Health check:**
```json
{
  "status": "ok",
  "kernels": 5,
  "spice_version": "CSPICE_N0067",
  "coordinate_system": "ecliptic_of_date"
}
```

**Calculation response should include:**
- `data.Sun.longitude` around 66°
- `meta.ecliptic_frame` = "ECLIPDATE"
- `meta.service_version` = "1.0.0"

## Environment Configuration

**Set in Render dashboard:**
- `ALLOWED_ORIGINS` = your UI domain (no wildcards in prod)
- Leave `DISABLE_RATE_LIMIT` unset (enables rate limiting)

## Monitoring Setup

1. **GitHub repository variables:**
   - Settings → Secrets and variables → Actions → Variables
   - Add `SPICE_URL` = `https://your-service.onrender.com`

2. **Nightly smoke tests** will run automatically via GitHub Actions