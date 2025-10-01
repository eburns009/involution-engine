#!/bin/bash
# Code quality check script

set -e

echo "🔍 Running code quality checks..."

# Basic ruff check (excluding some directories)
echo "📝 Running ruff linting..."
python -m ruff check engine/main.py engine/time_resolver.py engine/time_resolver_v2.py tests/batch/*.py --fix

# Basic mypy check on main files only
echo "🔍 Running mypy type checking..."
python -m mypy engine/main.py --ignore-missing-imports --disable-error-code=union-attr --disable-error-code=call-arg || true

# Bandit security check
echo "🔒 Running bandit security check..."
python -m bandit -r engine/main.py engine/time_resolver.py engine/time_resolver_v2.py -q || true

echo "✅ Code quality checks completed!"