#!/usr/bin/env bash
# Quick smoke test matching the provided examples
set -euo pipefail

echo "🧪 Quick Ephemeris Smoke Test"
echo "============================="

echo ""
echo "DE440 service info:"
curl -s http://127.0.0.1:8000/info | jq '.meta.kernel_set_tag'

echo ""
echo "DE440 modern calculation (2024):"
curl -s -X POST http://127.0.0.1:8000/calculate \
 -H 'content-type: application/json' \
 -d '{"birth_time":"2024-06-21T18:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":25,"zodiac":"tropical","ayanamsa":"lahiri"}' \
 | jq '.meta.kernel_set_tag,.meta.observer_frame_used'

echo ""
echo "DE441 service info:"
curl -s http://127.0.0.1:8001/info | jq '.meta.kernel_set_tag'

echo ""
echo "DE441 far future calculation (3000) - expect IAU_EARTH fallback:"
curl -s -X POST http://127.0.0.1:8001/calculate \
 -H 'content-type: application/json' \
 -d '{"birth_time":"3000-06-01T00:00:00Z","latitude":37.7749,"longitude":-122.4194,"elevation":25,"zodiac":"tropical","ayanamsa":"lahiri"}' \
 | jq '.meta.kernel_set_tag,.meta.observer_frame_used'

echo ""
echo "✅ Expected results:"
echo "   DE440/2024: kernel_set_tag='DE440', observer_frame='ITRF93'"
echo "   DE441/3000: kernel_set_tag='DE441', observer_frame='IAU_EARTH'"