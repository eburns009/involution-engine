#!/usr/bin/env bash
set -euo pipefail

echo "🧭 Running UI tests..."

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# Unit & component tests
echo "🔬 Running Vitest unit tests..."
npx vitest run --no-coverage

echo "✅ UI tests completed successfully!"