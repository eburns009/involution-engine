#!/usr/bin/env bash
set -euo pipefail

echo "🧪🧭 Running full test suite..."

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
bash "$ROOT/scripts/run_backend_tests.sh"
bash "$ROOT/scripts/run_ui_tests.sh"

echo "🎉 All tests passed!"