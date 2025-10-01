#!/usr/bin/env bash
# CI Smoke Test: Verify SPICE kernel loading and frame transforms
set -euo pipefail

echo "==> Testing SPICE kernel loading and transforms..."

# Test kernel transform functionality
python - <<'PY'
import spiceypy as s

try:
    # Load kernels
    s.furnsh("services/spice/kernels/involution.tm")
    print("✓ Kernels loaded successfully")

    # Test critical frame transformation (ITRF93 -> J2000)
    et = s.str2et("2000-01-01T00:00:00")
    matrix = s.pxform("ITRF93", "J2000", et)
    print("✓ ITRF93 -> J2000 transformation successful")

    # Test basic planetary ephemeris
    pos, _ = s.spkpos("SUN", et, "J2000", "LT+S", "EARTH")
    print("✓ Solar position calculation successful")

    # Test standard ecliptic frame transformation
    matrix2 = s.pxform("J2000", "ECLIPJ2000", et)
    print("✓ J2000 -> ECLIPJ2000 transformation successful")

    # Test kernel coverage
    count = s.ktotal("ALL")
    print(f"✓ {count} kernels loaded")

    # Cleanup
    s.kclear()
    print("✓ Kernels cleared successfully")
    print("OK")

except Exception as e:
    print(f"✗ SPICE Error: {e}")
    exit(1)
PY

echo "✓ SPICE kernel transform smoke test passed"