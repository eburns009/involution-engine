# Render Deployment Guide

## Quick Deploy (One-Click Blueprint)

1. **Connect GitHub to Render**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Blueprint"
   - Select this repository
   - Render will auto-detect `render.yaml` and create both services

2. **After API deploys (spice-api)**
   - Copy the API URL from Render dashboard (e.g., `https://spice-api-xyz.onrender.com`)
   - Update these locations with the actual URL:
     - `render.yaml` line 23: `ALLOWED_ORIGINS` value
     - `render.yaml` line 33: `NEXT_PUBLIC_ENGINE_BASE` value
     - `.env.production`: `NEXT_PUBLIC_ENGINE_BASE`
   - Commit changes to trigger redeploy

3. **Verify Deployment**
   ```bash
   # Check API health
   curl https://spice-api-xyz.onrender.com/health

   # Expected response: {"status":"healthy", "data": {...}}
   ```

4. **Open UI**
   - Visit `https://research-ui-xyz.onrender.com/research`
   - Try Fort Knox preset (1962-07-02 23:33:00)
   - DevTools → Network should show API calls to `spice-api-xyz.onrender.com`

---

## Manual Deploy (Alternative)

If you prefer manual setup instead of Blueprint:

### 1. Deploy API First

**Render Dashboard → New Web Service**
- **Name**: `spice-api`
- **Environment**: Docker
- **Dockerfile Path**: `./services/spice/Dockerfile`
- **Docker Context**: `.` (repo root)
- **Health Check Path**: `/health`
- **Plan**: Starter ($7/mo)

**Environment Variables**:
```
ENGINE_KERNEL_BUNDLE=de440-modern
LOG_LEVEL=INFO
WORKERS=2
ALLOWED_ORIGINS=https://research-ui.onrender.com,http://localhost:3000
DISABLE_RATE_LIMIT=0
```

**Build Settings**:
- Auto-deploy: Yes
- Branch: `main`

---

### 2. Deploy UI Second

**Render Dashboard → New Web Service**
- **Name**: `research-ui`
- **Environment**: Node
- **Build Command**: `npm ci && npm run build`
- **Start Command**: `npm run start`
- **Plan**: Starter ($7/mo)

**Environment Variables** (update URL after API is live):
```
NEXT_PUBLIC_ENGINE_BASE=https://spice-api-xyz.onrender.com
NODE_ENV=production
```

---

## Troubleshooting

### API fails at startup
**Symptom**: `/health` returns 500 or service crashes
**Fix**: Check logs for "Metakernel not found" → kernels didn't copy into image
```bash
# Test Docker build locally first
cd /workspaces/involution-engine
docker build -f services/spice/Dockerfile -t spice-test .
docker run -p 8000:8000 spice-test
curl http://localhost:8000/health
```

### CORS errors in browser console
**Symptom**: `Access-Control-Allow-Origin` errors
**Fix**: Verify `ALLOWED_ORIGINS` env var in API includes UI URL
```bash
# In Render dashboard → spice-api → Environment
ALLOWED_ORIGINS=https://research-ui-xyz.onrender.com,http://localhost:3000
```

### UI can't connect to API
**Symptom**: Network tab shows 404s or requests to wrong host
**Fix**: Check `NEXT_PUBLIC_ENGINE_BASE` is set correctly
```bash
# In Render dashboard → research-ui → Environment
NEXT_PUBLIC_ENGINE_BASE=https://spice-api-xyz.onrender.com

# Rebuild UI after changing env vars (they're baked at build time)
```

### Cold starts (15-30s delay)
**Expected**: Free/Starter plans spin down after 15min inactivity
**Fix**: Upgrade to Standard plan ($25/mo) for always-on instances

### Kernel coverage errors (historical dates)
**Symptom**: 400 errors for dates before 1650 or after 2650
**Fix**: Check `ENGINE_KERNEL_BUNDLE` is set to `de440-modern` (not `de440-full`)
- `de440-modern`: 1550-2650 (faster, smaller)
- `de440-full`: 1650-2650 (research-grade)

---

## Cost Estimate

- **API**: Starter ($7/mo) or Standard ($25/mo for always-on)
- **UI**: Starter ($7/mo)
- **Total**: $14-32/mo

Free tier: 750 hours/mo (good for testing, not production)

---

## Post-Deploy Checklist

- [ ] API `/health` returns 200 with kernel info
- [ ] UI loads at `/research`
- [ ] Fort Knox preset calculates successfully
- [ ] No CORS errors in browser console
- [ ] Network tab shows requests to correct API domain
- [ ] Tropical/Sidereal toggle works
- [ ] Custom date/location inputs work

---

## Next Steps

1. **Add Redis** (optional, Phase 2):
   - Render → New Redis instance
   - Add `REDIS_URL` env var to API
   - Enables distributed caching + rate limiting

2. **Set up monitoring**:
   - `/metrics` endpoint → Prometheus/Grafana
   - Render health checks → auto-restart on failure

3. **Custom domain** (optional):
   - research.yourdomain.com → research-ui
   - api.yourdomain.com → spice-api
