# CI/CD Documentation

Comprehensive continuous integration and deployment pipeline for Involution Engine.

## Workflow Overview

### 🚀 Quick Check (`quick-check.yml`)
**Triggers:** Every PR and push to main/develop
**Duration:** ~5 minutes
**Purpose:** Fast feedback loop for development

**Checks:**
- Code formatting (Black)
- Linting (Ruff)
- Type checking (MyPy)
- Security scan (Bandit)
- Repository structure validation
- Import path validation

**Gates:**
- ✅ All format and lint issues resolved
- ✅ No debugging artifacts in production code
- ✅ Required documentation files present
- ✅ No obvious security issues

### 🔬 Comprehensive CI (`comprehensive-ci.yml`)
**Triggers:** PR and push to main
**Duration:** ~15-20 minutes
**Purpose:** Full validation before merge/deployment

**Jobs:**
1. **Code Quality & Security**
   - Black formatting validation
   - Ruff linting with GitHub annotations
   - MyPy type checking
   - Bandit security analysis
   - Dependency vulnerability scanning

2. **Unit Tests**
   - Full test suite execution
   - Code coverage reporting
   - Test result artifacts

3. **Accuracy & Performance Testing**
   - Five Random Pack validation
   - Accuracy gate: 100% pass rate required
   - Performance gate: P95 < 500ms
   - Real engine service testing

4. **Integration Tests**
   - API contract validation
   - Endpoint testing
   - Time resolution testing
   - Houses calculation testing

5. **Deployment Readiness** (main branch only)
   - Production configuration validation
   - Docker build verification
   - Gunicorn configuration testing

### 🌙 Nightly Comprehensive (`nightly-comprehensive.yml`)
**Triggers:** Daily at 2 AM UTC + manual
**Duration:** ~45-60 minutes
**Purpose:** Extended validation and regression detection

**Features:**
- Extended accuracy testing across all example packs
- Stress testing with 250+ chart calculations
- Historical date range validation (1700-2050)
- Edge case testing (polar regions, date line)
- Performance analysis under load
- Kernel integrity verification
- Automated issue creation on failure

## Quality Gates

### Accuracy Standards
```yaml
Required Pass Rate: 100%
Tolerance Standards:
  - Planets: ±1.0 arcminute
  - Moon: ±30.0 arcminutes (rapid motion)
  - Nodes: ±5.0 arcminutes
```

### Performance Budgets
```yaml
Standard Testing:
  - P95 Latency: <500ms per chart
  - P50 Latency: <200ms per chart

Stress Testing:
  - P95 Latency: <1000ms per chart
  - Throughput: >2 charts/second
```

### Security Requirements
```yaml
Code Security:
  - No hardcoded secrets
  - Bandit security scan: PASS
  - Dependency vulnerabilities: LOW/NONE

Operational Security:
  - Debug endpoints disabled in production
  - Rate limiting enabled
  - CORS properly configured
```

## Artifacts and Reports

### Generated Artifacts
- **Accuracy Reports**: CSV and JSON format accuracy comparisons
- **Performance Reports**: Detailed timing and throughput metrics
- **Security Reports**: Bandit and dependency scan results
- **Coverage Reports**: HTML and XML code coverage
- **Kernel Integrity**: SPICE kernel validation reports

### Artifact Retention
- **Pull Request artifacts**: 7 days
- **Main branch artifacts**: 30 days
- **Nightly test artifacts**: 30 days
- **Security reports**: 90 days

## Environment Configuration

### Required Environment Variables
```bash
# CI Environment
DISABLE_RATE_LIMIT=1          # Disable rate limiting for tests
PYTHONDONTWRITEBYTECODE=1     # Prevent .pyc files
ENGINE_BASE=http://127.0.0.1:8000  # Engine service URL

# Optional
DEBUG=0                       # Disable debug endpoints
ENV=test                      # Test environment flag
```

### Required Dependencies
```bash
# Core dependencies
pip install -r engine/requirements.txt

# Testing dependencies
pip install pytest pytest-cov pytest-asyncio

# Quality tools
pip install ruff black mypy bandit safety

# System tools
apt-get install bc jq curl    # For numerical comparisons and JSON processing
```

## Failure Handling

### Automatic Actions
- **Nightly failure**: Automatic issue creation with failure details
- **Security alerts**: Artifact upload for investigation
- **Performance regression**: Warning annotations in PR

### Manual Investigation Steps
1. **Accuracy Failures**:
   ```bash
   # Download accuracy artifacts
   # Review accuracy_report.csv for specific failures
   # Check reference data validity
   # Validate SPICE kernel integrity
   ```

2. **Performance Failures**:
   ```bash
   # Download performance artifacts
   # Analyze metrics_summary.json
   # Check system resource usage
   # Validate test environment consistency
   ```

3. **Security Failures**:
   ```bash
   # Review bandit-report.json
   # Check pip-audit-report.json
   # Validate dependency versions
   # Scan for hardcoded secrets
   ```

## Local Development

### Run Quality Checks Locally
```bash
# Quick checks (matches quick-check workflow)
black --check engine/ tests/
ruff check engine/ tests/
mypy engine/main.py --ignore-missing-imports

# Full local testing
./scripts/quality_check.sh
pytest tests/
```

### Local Accuracy Testing
```bash
# Start engine locally
cd engine && uvicorn main:app --reload --port 8000 &

# Run accuracy tests
python tests/batch/batch_compute_positions.py \
  --input examples/five_random/charts_input.csv \
  --output local_test_positions.csv

python tests/batch/accuracy_compare.py \
  --engine local_test_positions.csv \
  --reference examples/five_random/reference_filled.csv \
  --out_csv local_accuracy_report.csv \
  --out_json local_accuracy_summary.json
```

## Integration with External Services

### GitHub Integration
- **Status checks**: Required for PR merging
- **Annotations**: Inline code quality feedback
- **Issue creation**: Automated failure reporting
- **Artifact links**: Direct download from PR checks

### Future Integrations
- **Slack notifications**: Build status updates
- **Dashboard monitoring**: Real-time CI metrics
- **Performance trending**: Historical performance tracking
- **Security scanning**: Enhanced SAST/DAST integration

## Customization

### Adding New Test Packs
1. Create new example pack in `examples/`
2. Add to nightly workflow test matrix
3. Define specific accuracy tolerances if needed
4. Update artifact collection paths

### Adjusting Performance Budgets
1. Update budget thresholds in workflow files
2. Modify comparison logic in performance gates
3. Update documentation to reflect new standards

### Custom Quality Rules
1. Update `pyproject.toml` tool configurations
2. Modify workflow quality check steps
3. Add new validation scripts to `scripts/`

## Monitoring and Metrics

### Key Metrics Tracked
- **Test execution time**: Workflow duration trends
- **Accuracy pass rates**: Historical accuracy tracking
- **Performance metrics**: P50/P95 latency trends
- **Security issues**: Vulnerability tracking over time

### Alerting Criteria
- **Accuracy regression**: <100% pass rate
- **Performance regression**: >20% increase in P95 latency
- **Security regression**: New HIGH/CRITICAL vulnerabilities
- **Infrastructure failure**: 3+ consecutive workflow failures

The CI/CD pipeline ensures Involution Engine maintains research-grade accuracy and performance standards through comprehensive automated testing and quality gates.