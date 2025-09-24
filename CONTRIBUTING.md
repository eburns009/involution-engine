# Contributing

## Dev setup
- Python 3.12, Node LTS recommended.
- Install kernels with `npm run kernels` (or `bash services/spice/download_kernels.sh`).

## Commit hygiene
- No large binaries (kernels) in Git. Metakernel only.
- Keep PRs focused; include a brief rationale.

## Quality gates (required)
```bash
ruff check .
mypy services/spice
bandit -q -r services/spice -x "services/spice/test_*"
pip-audit
pytest -q
```

## Tests
- Golden tests must include Sun/Moon + one barycenter at ≥2 epochs.
- Use `DISABLE_RATE_LIMIT=1` in tests.

## Security
- CORS allow-list via `ALLOWED_ORIGINS`.
- No secrets in code or history; use env vars only.