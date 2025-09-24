# Production Deployment Guide

## 🚀 Production Command

**Use multi-process gunicorn (CSPICE isn't thread-safe):**

```bash
gunicorn services.spice.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 2 --bind 0.0.0.0:8000 --timeout 30
```

## 🔧 Environment Variables

**Required in production:**

```bash
ALLOWED_ORIGINS=https://your-ui.example
DISABLE_RATE_LIMIT=           # (unset/empty in prod)
```

**Optional:**

```bash
ENV=prod                      # Default: dev
```

## 🏗️ Container Deployment

**Dockerfile example:**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN bash services/spice/download_kernels.sh

EXPOSE 8000
CMD ["gunicorn", "services.spice.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", "--bind", "0.0.0.0:8000", "--timeout", "30"]
```

## 🔍 Health Checks

**Uptime monitoring:**

```bash
curl -s https://your-spice.example/health | jq .
```

**Expected response:**

```json
{
  "status": "ok",
  "kernels": 5,
  "spice_version": "CSPICE_N0067",
  "coordinate_system": "ecliptic_of_date"
}
```

## 🧪 Post-Deploy Smoke Test

```bash
# Health check
curl -s https://your-spice.example/health | jq .

# Calculation test
curl -s -X POST https://your-spice.example/calculate \
  -H 'content-type: application/json' \
  -d '{
    "birth_time": "2024-06-21T18:00:00Z",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "elevation": 50,
    "ayanamsa": "lahiri"
  }' | jq .
```

## 🛡️ Security Checklist

- [ ] `ALLOWED_ORIGINS` set to specific domains (never `*`)
- [ ] `DISABLE_RATE_LIMIT` unset in production
- [ ] HTTPS enabled with valid certificate
- [ ] Container runs as non-root user
- [ ] Firewall allows only necessary ports

## 📊 Monitoring

**Nightly smoke tests** run automatically via GitHub Actions.

**Set repository variable:**
- Go to repo Settings → Secrets and variables → Actions → Variables
- Add `SPICE_URL` = `https://your-spice.example`

## 🔄 Rollback Plan

**Quick rollback to v0.1.0:**

```bash
git checkout main
git reset --hard v0.1.0
# Deploy using your normal process
```

**Prefer revert PR for production rollbacks when possible.**

## 🎯 UI Integration

**Point Next.js to production:**

```bash
NEXT_PUBLIC_SPICE_URL=https://your-spice.example
```

**Test with 3 sanity cases:**
1. J2000 epoch: `2000-01-01T12:00:00Z`
2. Recent date: `2024-06-21T18:00:00Z`
3. Near-coverage edge: `2640-01-01T00:00:00Z`