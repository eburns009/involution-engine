# 🚀 Involution Engine — Release Checklist

This checklist ensures reproducible, observable, and reversible releases by tying together Phase 1–3 implementations. Use this for every production release to maintain quality and reliability.

## 1. Pre-Release Verification

### ✅ Code Review
- [ ] All commits merged into `main` (squash/fixup done)
- [ ] No `TODO` or commented debug code remains
- [ ] All Phase 3 quality gates passed in CI/CD
- [ ] Security scan results reviewed and approved

### ✅ Dependencies
- [ ] `server/requirements.txt` frozen and pinned
- [ ] Security scan run (`pip-audit` or `safety check`)
- [ ] Phase 3 dependencies validated:
  - [ ] `pandas==2.2.2` (drift analysis)
  - [ ] `numpy==1.26.4` (statistical calculations)

### ✅ Documentation
- [ ] `CHANGELOG.md` updated with version/date
- [ ] Migration notes written if API schema changed
- [ ] User docs updated:
  - [ ] `docs/users/quickstart-astrologers.md`
  - [ ] `docs/users/accuracy-guarantees.md`
  - [ ] `docs/users/migrating-from-swiss.md`
- [ ] Phase 3 feature documentation current

### ✅ Golden Tests
- [ ] Run `five_random` pack vs Swiss Ephemeris
- [ ] Verify drift tolerance compliance:
  - [ ] Planets: ±1 arcminute
  - [ ] Moon: ±30 arcminutes
  - [ ] Nodes: ±5 arcminutes
- [ ] Fort Knox 1962 golden test passes
- [ ] Tropical/sidereal consistency verified

### ✅ Observability
- [ ] `/healthz` endpoint checked:
  - [ ] Kernels loaded status
  - [ ] Cache statistics
  - [ ] Service dependencies
- [ ] `/metrics` Prometheus scrape validated
- [ ] Structured logs visible in dev/staging
- [ ] Drift detection monitoring functional

## 2. Build & Package

### ✅ Docker Images
Build and validate all engine variants:
- [ ] `involution-engine:de440-full`
- [ ] `involution-engine:de440-1900`
- [ ] `involution-engine:de440-modern`
- [ ] SHA256 digests recorded in release notes
- [ ] Images pushed to container registry
- [ ] Vulnerability scan passed for all images

### ✅ Kernel Verification
- [ ] Bundle checksums validated against NASA sources
- [ ] DE440/DE441 handoff boundaries tested
- [ ] Health report archived with build artifacts
- [ ] Ephemeris coverage verified (1550-2650 CE + extensions)

## 3. Canary Rollout

### ✅ Initial Deployment
- [ ] Deploy with Nginx weighted routing (90/10)
- [ ] Verify `docker-compose.canary.yml` configuration
- [ ] Confirm both stable and canary services healthy
- [ ] Direct access ports (8081/8082) functional for debugging

### ✅ Monitoring Phase 1 (24 hours at 90/10)
- [ ] p95 latency < 200ms
- [ ] 5xx error rate < 0.1%
- [ ] Cache hit rate > 70%
- [ ] No accuracy degradation detected
- [ ] User feedback collected

### ✅ Progressive Rollout
- [ ] Gradually increase to 50/50 → 100/0
- [ ] Stable version retired after validation
- [ ] Rollback procedure tested by reloading Nginx weights
- [ ] Load balancer configuration documented

## 4. Drift Detection

### ✅ Manual Validation
- [ ] Run `ops/drift/drift_check.py` manually against Swiss Ephemeris
- [ ] Verify drift report artifact (`drift_report_*.csv`)
- [ ] Review statistical summary and tolerance compliance
- [ ] No significant drift detected (within warning thresholds)

### ✅ Automated Monitoring
- [ ] Weekly GitHub Actions job (`.github/workflows/drift.yml`) enabled and passing
- [ ] Historical trend analysis functional
- [ ] Alert thresholds configured:
  - [ ] Planets: Warning at 0.75', Alert at 1.0'
  - [ ] Moon: Warning at 25.0', Alert at 30.0'
  - [ ] Nodes: Warning at 4.0', Alert at 5.0'
- [ ] GitHub issue creation on drift tested

## 5. Feature Flags

### ✅ Fixed Stars Configuration
- [ ] Confirm `features.fixed_stars.enabled: false` in `config.yaml` (default)
- [ ] If testing enabled:
  - [ ] Verify `/v1/stars/positions` returns mag ≤ 2.5 stars
  - [ ] Yale BSC5 catalog loading functional
  - [ ] Coordinate transformations accurate
  - [ ] Feature flag toggle working correctly
- [ ] Feature flag state documented in `CHANGELOG.md`

### ✅ Future Feature Readiness
- [ ] Feature flag system tested and validated
- [ ] Environment variable overrides functional
- [ ] Configuration reloading without restart verified

## 6. CI/CD Gates

### ✅ GitHub Actions Validation
All workflows must be green before tagging release:

**Quality Gates** (`.github/workflows/quality-gates.yml`):
- [ ] Code Quality: Black, isort, flake8, mypy ✅
- [ ] Unit Tests: >80% coverage ✅
- [ ] Integration Tests: End-to-end validation ✅
- [ ] Accuracy Validation: Golden dataset ✅
- [ ] Security Checks: Dependencies + code scan ✅
- [ ] API Contract: Endpoint validation ✅

**Specialized Workflows**:
- [ ] Drift Detection: Weekly monitoring ✅
- [ ] Performance Benchmarks: <100ms response ✅
- [ ] Canary Configuration: Nginx conf lint ✅
- [ ] Release Pipeline: Staging validation ✅

### ✅ Manual Gate Approvals
- [ ] Engineering lead approval
- [ ] Security review (if applicable)
- [ ] Operations team notified

## 7. Tag & Publish

### ✅ Version Management
- [ ] Git tag created: `vX.Y.Z` (semantic versioning)
- [ ] Tag follows format: `v1.2.3` (major.minor.patch)
- [ ] Pre-release tags use: `v1.2.3-rc.1`, `v1.2.3-beta.1`

### ✅ Artifact Publishing
- [ ] Docker images pushed with tag and digest
- [ ] Release notes published with:
  - [ ] Feature summary
  - [ ] Bug fixes
  - [ ] Breaking changes (if any)
  - [ ] Migration instructions
  - [ ] Accuracy validation results
  - [ ] SHA256 digests
- [ ] GitHub release created with artifacts

### ✅ Communication
- [ ] Announcement posted internally (dev + ops)
- [ ] User documentation updated and published
- [ ] API documentation refreshed
- [ ] Status page updated (if applicable)

## 8. Post-Release Monitoring

### ✅ 24-Hour Observation Window
Monitor critical metrics:
- [ ] **Performance**:
  - [ ] p95 latency trends
  - [ ] Response time distribution
  - [ ] Throughput metrics
- [ ] **Reliability**:
  - [ ] Error rates by endpoint
  - [ ] Service health status
  - [ ] Cache performance
- [ ] **Accuracy**:
  - [ ] Drift job status
  - [ ] Golden test results
  - [ ] User-reported discrepancies

### ✅ User Experience
- [ ] Collect user feedback:
  - [ ] Accuracy comparisons
  - [ ] API ergonomics
  - [ ] Performance perception
  - [ ] Documentation clarity
- [ ] Monitor support channels for issues
- [ ] Track migration success (Swiss Ephemeris users)

### ✅ Operational Health
- [ ] **Infrastructure**:
  - [ ] Container resource usage
  - [ ] Database performance
  - [ ] Network latency
- [ ] **Dependencies**:
  - [ ] Time resolver service health
  - [ ] Redis cache performance
  - [ ] External service availability

### ✅ Post-Release Actions
- [ ] Performance baseline updated
- [ ] Monitoring thresholds adjusted (if needed)
- [ ] Runbook updates based on deployment experience
- [ ] Open Phase 4 backlog ticket(s) if issues observed
- [ ] Retrospective scheduled (for major releases)

## 🚨 Rollback Procedures

### Emergency Rollback Triggers
- [ ] Error rate spike >5%
- [ ] Response time degradation >200%
- [ ] Accuracy drift beyond alert thresholds
- [ ] Critical security vulnerability discovered

### Rollback Execution
1. **Immediate Response** (<5 minutes):
   ```bash
   # Revert load balancer to previous version
   kubectl set image deployment/engine engine=involution-engine:v1.2.2
   # or for Docker Compose
   docker-compose -f docker-compose.canary.yml down
   docker-compose up -d
   ```

2. **Validation** (<15 minutes):
   ```bash
   # Verify health endpoints
   curl -f http://api.involution-engine.com/healthz
   # Check accuracy with golden test
   python tests/golden/quick_validation.py
   ```

3. **Communication**:
   - [ ] Incident response team notified
   - [ ] Status page updated
   - [ ] Users informed of temporary service interruption

## 📋 Release Artifacts Checklist

Save these artifacts for each release:
- [ ] **Code**: Git tag with SHA
- [ ] **Images**: Docker image digests
- [ ] **Config**: Production configuration snapshots
- [ ] **Tests**: Golden test results and drift reports
- [ ] **Docs**: Release notes and migration guides
- [ ] **Monitoring**: Performance baselines and thresholds

## 🎯 Success Criteria

A successful release achieves:
- [ ] **Zero downtime** during deployment
- [ ] **No accuracy regression** (within tolerances)
- [ ] **Performance maintained** (sub-100ms p95)
- [ ] **Security standards** met (zero critical vulnerabilities)
- [ ] **User satisfaction** maintained (feedback collection)
- [ ] **Operational stability** (24h monitoring clean)

---

**Use this checklist for every release to ensure consistency, quality, and reliability of the Involution Engine.**

*Last updated: Phase 3 completion*