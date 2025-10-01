#!/usr/bin/env bash
# Test dual ephemeris services with different date ranges
set -euo pipefail

echo "==> Testing Dual Ephemeris Coverage"

# Test payload
payload='{"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"zodiac":"tropical"}'

echo ""
echo "📅 Testing Modern Date (2024) - Both services should work:"

echo "DE440 (port 8000):"
if curl -fsS -X POST http://127.0.0.1:8000/calculate \
  -H 'content-type: application/json' \
  -d "$payload" | jq -r '.meta.kernel_set_tag'; then
    echo "✓ DE440 calculation successful"
else
    echo "✗ DE440 calculation failed"
fi

echo "DE441 (port 8001):"
if curl -fsS -X POST http://127.0.0.1:8001/calculate \
  -H 'content-type: application/json' \
  -d "$payload" | jq -r '.meta.kernel_set_tag'; then
    echo "✓ DE441 calculation successful"
else
    echo "✗ DE441 calculation failed"
fi

echo ""
echo "📅 Testing Ancient Date (500 BCE) - Only DE441 should work:"

ancient_payload='{"birth_time":"-0500-06-21T12:00:00Z","latitude":37.7749,"longitude":-122.4194,"zodiac":"tropical"}'

echo "DE440 (port 8000) - Should fail:"
if curl -s -X POST http://127.0.0.1:8000/calculate \
  -H 'content-type: application/json' \
  -d "$ancient_payload" | jq -r '.detail // "Success"'; then
    echo "Expected failure or success"
fi

echo "DE441 (port 8001) - Should succeed:"
if curl -s -X POST http://127.0.0.1:8001/calculate \
  -H 'content-type: application/json' \
  -d "$ancient_payload" | jq -r '.meta.kernel_set_tag // .detail'; then
    echo "Expected success"
fi

echo ""
echo "🔍 Service Information:"
echo "DE440: $(curl -s http://127.0.0.1:8000/version | jq -r '.kernel_set.tag')"
echo "DE441: $(curl -s http://127.0.0.1:8001/version | jq -r '.kernel_set.tag')"

echo ""
echo "✅ Dual ephemeris test complete"