#!/usr/bin/env bash
set -euo pipefail

echo "🧪 Running backend tests..."

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
bash "$ROOT/scripts/ensure_kernels.sh"

cd "$ROOT"

echo "🔬 Running pytest with coverage..."
pytest -q --maxfail=1 --disable-warnings --cov=services/spice --cov-report=term-missing --cov-report=html:services/spice/htmlcov

echo "✅ Backend tests completed successfully!"
echo "📊 Coverage report saved to services/spice/htmlcov/"