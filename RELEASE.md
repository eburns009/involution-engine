# Release Process

## Standard Release Flow

After feature branch is squash-merged to main:

```bash
# Switch to main and get latest changes
git checkout main && git pull

# Create annotated tag for the release
git tag -a v0.1.0 -m "Involution SPICE service v0.1.0"

# Push tag to trigger release
git push origin v0.1.0
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- `v0.1.0` - Initial release
- `v0.1.1` - Patch fixes
- `v0.2.0` - Minor features/improvements
- `v1.0.0` - Major release/breaking changes

## Release Checklist

Before creating a release tag:

- [ ] All CI checks pass on main branch
- [ ] Security audit clean (ruff, mypy, bandit, pip-audit)
- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if exists)

## Docker Release

Tags automatically trigger container builds:

```bash
# Build and tag container
docker build -t involution-spice:v0.1.0 services/spice/
docker tag involution-spice:v0.1.0 involution-spice:latest

# Push to registry (if configured)
docker push involution-spice:v0.1.0
docker push involution-spice:latest
```

## Hotfix Process

For critical fixes to production:

```bash
# Create hotfix branch from main
git checkout main
git checkout -b hotfix/critical-fix

# Make minimal fix, test, commit
git commit -m "fix: critical security patch"

# Merge directly to main (fast-track)
git checkout main
git merge hotfix/critical-fix

# Tag patch release
git tag -a v0.1.1 -m "Hotfix v0.1.1: Critical security patch"
git push origin v0.1.1

# Clean up
git branch -d hotfix/critical-fix
```