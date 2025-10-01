# Release Process

This document outlines the complete release process for the Involution Engine, including quality gates, validation procedures, and deployment workflows.

## Overview

The Involution Engine follows a rigorous release process designed to ensure:
- **Quality**: All releases meet accuracy and performance standards
- **Security**: No vulnerabilities or secrets in production code
- **Reliability**: Comprehensive testing before production deployment
- **Traceability**: Full audit trail of changes and validations

## Release Types

### Patch Releases (v1.0.X)
- **Purpose**: Bug fixes, minor accuracy improvements, security patches
- **Frequency**: As needed, typically weekly
- **Process**: Standard quality gates → staging → production
- **Approval**: Automated deployment after gates pass

### Minor Releases (v1.X.0)
- **Purpose**: New features, API enhancements, ayanāṃśa additions
- **Frequency**: Monthly or quarterly
- **Process**: Full validation → canary deployment → staged rollout
- **Approval**: Manual approval required for production

### Major Releases (vX.0.0)
- **Purpose**: Breaking changes, major architectural updates
- **Frequency**: Yearly or as needed
- **Process**: Extended validation → beta testing → gradual rollout
- **Approval**: Multiple stakeholder approval required

## Quality Gates

All releases must pass six quality gates before deployment:

### Gate 1: Code Quality
- **Black code formatting**: Ensures consistent Python style
- **isort import sorting**: Maintains clean import organization
- **flake8 linting**: Catches common Python issues
- **mypy type checking**: Validates type annotations

**Failure Action**: Automatic PR block, requires fixes before merge

### Gate 2: Unit Tests
- **Coverage requirement**: ≥80% code coverage
- **Test execution**: All unit tests must pass
- **Performance**: Test suite completes in <15 minutes

**Failure Action**: Blocks merge, requires test fixes or additions

### Gate 3: Integration Tests
- **Service interaction**: Tests engine + time resolver + Redis
- **End-to-end workflows**: Complete API request cycles
- **Service health**: All components respond correctly

**Failure Action**: Requires integration debugging before merge

### Gate 4: Accuracy Validation
- **Golden dataset**: Tests against known reference values
- **Performance benchmarks**: Response time <200ms for complex calculations
- **Tolerance checking**: Planetary positions within guaranteed accuracy

**Failure Action**: Critical blocker, requires accuracy investigation

### Gate 5: Security Checks
- **Dependency scanning**: No known vulnerabilities in libraries
- **Static analysis**: Bandit security linting passes
- **Secrets detection**: No hardcoded credentials or keys

**Failure Action**: Security review required before proceeding

### Gate 6: API Contract Validation
- **Endpoint availability**: All documented endpoints respond
- **Response structure**: JSON schemas match documentation
- **Error handling**: Proper error codes and messages

**Failure Action**: API compatibility review required

## Release Workflow

### Automated Triggers

#### Git Tag Push
```bash
git tag v1.2.3
git push origin v1.2.3
```

#### Manual Trigger
```bash
# Via GitHub Actions UI
# Select: workflow_dispatch
# Parameters:
#   - tag_name: v1.2.3
#   - deploy_environment: production
```

### Release Pipeline Stages

#### 1. Validation (15 minutes)
- Execute all six quality gates
- Extract version from tag/input
- Generate deployment decision

**Success Criteria**: All gates pass
**Failure Action**: Halt pipeline, notify team

#### 2. Build (10 minutes)
- Create Docker image with version tag
- Upload artifacts for deployment
- Verify build integrity

**Success Criteria**: Image builds successfully
**Failure Action**: Investigation required

#### 3. Staging Deployment (10 minutes)
- Deploy to staging environment
- Verify deployment health
- Run staging-specific tests

**Success Criteria**: Staging responds correctly
**Failure Action**: Rollback staging, investigate

#### 4. Staging Validation (10 minutes)
- End-to-end testing in staging environment
- Performance validation
- Cross-service integration checks

**Success Criteria**: All staging tests pass
**Failure Action**: Block production deployment

#### 5. Production Deployment (15 minutes)
- **Manual Approval Required**: Human verification step
- Deploy to production environment
- Canary deployment for minor/major releases
- Health check validation

**Success Criteria**: Production health checks pass
**Failure Action**: Automatic rollback triggered

#### 6. Production Validation (10 minutes)
- Live production testing
- Response time verification
- Accuracy spot checks

**Success Criteria**: Production operates within parameters
**Failure Action**: Emergency rollback procedures

#### 7. GitHub Release Creation (5 minutes)
- Generate release notes from commits
- Create tagged GitHub release
- Notify stakeholders

**Success Criteria**: Release documented and published

## Canary Deployment Process

For minor and major releases, we use canary deployments to minimize risk:

### Phase 1: 10% Traffic (24 hours)
```nginx
upstream involution_engine {
    server engine-stable:8080 weight=90;
    server engine-canary:8080 weight=10;
}
```

**Monitoring**:
- Error rate increase <0.1%
- Response time increase <10%
- Accuracy within tolerances

**Rollback Triggers**:
- Error rate >1%
- Response time >300ms
- Any accuracy degradation

### Phase 2: 50% Traffic (24 hours)
```nginx
upstream involution_engine {
    server engine-stable:8080 weight=50;
    server engine-canary:8080 weight=50;
}
```

**Monitoring**:
- Sustained performance
- User feedback analysis
- Extended accuracy validation

### Phase 3: 100% Traffic
```nginx
upstream involution_engine {
    server engine-canary:8080 weight=100;
}
```

**Completion**: Old version removed after 72 hours

## Rollback Procedures

### Automatic Rollback Triggers
- Health check failures for >5 minutes
- Error rate spike >5%
- Response time degradation >200%
- Critical accuracy deviation detected

### Manual Rollback Process

#### Emergency Rollback (< 5 minutes)
```bash
# Revert load balancer to previous version
kubectl set image deployment/engine engine=involution-engine:v1.2.2

# Scale down canary deployment
kubectl scale deployment/engine-canary --replicas=0
```

#### Staged Rollback (< 15 minutes)
```bash
# Gradual traffic reduction
# 100% → 50% → 10% → 0%
# Monitor at each stage
```

### Post-Rollback Actions
1. **Incident Response**: Document rollback reason
2. **Root Cause Analysis**: Identify failure source
3. **Fix Development**: Address underlying issues
4. **Re-release Planning**: Schedule corrected version

## Monitoring and Alerting

### Release Health Metrics
- **Deployment Success Rate**: Target >98%
- **Rollback Frequency**: Target <2% of releases
- **Quality Gate Pass Rate**: Target >95%
- **Time to Production**: Target <2 hours for patches

### Alerting Channels
- **Slack**: Real-time deployment notifications
- **Email**: Release completion summaries
- **PagerDuty**: Critical failure alerts
- **GitHub**: PR comments and issue creation

### Key Performance Indicators

#### Reliability Metrics
- **MTTR (Mean Time to Recovery)**: <30 minutes
- **MTBF (Mean Time Between Failures)**: >30 days
- **Deployment Frequency**: Daily for patches, weekly for features

#### Quality Metrics
- **Accuracy Compliance**: 100% within tolerances
- **Security Scan Pass Rate**: 100%
- **Test Coverage**: >80%

## Version Management

### Semantic Versioning (SemVer)
- **MAJOR.MINOR.PATCH** (e.g., v1.2.3)
- **MAJOR**: Breaking changes, architectural shifts
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, security patches

### Pre-release Versions
- **Alpha**: `v1.2.3-alpha.1` - Early development
- **Beta**: `v1.2.3-beta.1` - Feature complete, testing
- **RC**: `v1.2.3-rc.1` - Release candidate

### Branch Strategy
- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/***: Individual feature development
- **hotfix/***: Emergency production fixes

## Release Schedule

### Regular Release Cadence
- **Patch Releases**: Weekly (Tuesdays)
- **Minor Releases**: Monthly (First Tuesday)
- **Major Releases**: Quarterly or annually

### Emergency Releases
- **Security Patches**: Within 24 hours of discovery
- **Critical Bugs**: Within 48 hours of confirmation
- **Accuracy Issues**: Within 4 hours of detection

## Documentation Requirements

### Pre-Release Documentation
- [ ] API changes documented
- [ ] Migration guides updated
- [ ] Accuracy tolerance changes noted
- [ ] Deployment procedure verified

### Post-Release Documentation
- [ ] Release notes published
- [ ] User guides updated
- [ ] Internal runbooks refreshed
- [ ] Monitoring dashboards configured

## Compliance and Audit

### Release Audit Trail
- **Git Tags**: Immutable version history
- **GitHub Releases**: Public change documentation
- **CI/CD Logs**: Complete pipeline execution records
- **Deployment Manifests**: Infrastructure as code

### Compliance Checks
- **Quality Gates**: All six gates must pass
- **Security Scans**: No critical vulnerabilities
- **Manual Approvals**: Human verification for production
- **Rollback Capability**: Verified before deployment

## Troubleshooting

### Common Release Issues

#### Quality Gate Failures
**Symptom**: Pipeline blocked at validation stage
**Resolution**:
1. Review specific gate failure details
2. Fix code/test issues locally
3. Re-run pipeline with updated code

#### Deployment Timeouts
**Symptom**: Services fail to start within timeout
**Resolution**:
1. Check resource constraints
2. Verify health check endpoints
3. Increase timeout if necessary

#### Canary Deployment Issues
**Symptom**: Increased error rates during canary
**Resolution**:
1. Halt traffic increase immediately
2. Analyze error patterns and logs
3. Rollback if issues persist >30 minutes

### Emergency Contacts
- **On-Call Engineer**: Primary deployment support
- **Release Manager**: Overall process oversight
- **Security Team**: For security-related issues
- **Infrastructure Team**: For deployment environment issues

This release process ensures that every deployment of the Involution Engine maintains the highest standards of quality, security, and reliability while providing rapid recovery capabilities when issues arise.