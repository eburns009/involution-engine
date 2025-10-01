#!/usr/bin/env bash
# Comprehensive smoke test for dual ephemeris and observer frame behavior
set -euo pipefail

echo "🧪 Ephemeris & Observer Frame Smoke Test"
echo "========================================"

# Test function to make calculation requests
test_calculation() {
    local port=$1
    local date=$2
    local description=$3
    local expected_frame=$4

    echo ""
    echo "📅 Testing: $description ($date)"
    echo "   Port: $port"

    # Test service info
    local kernel_tag=$(curl -s http://127.0.0.1:$port/info | jq -r '.meta.kernel_set_tag')
    echo "   Kernel: $kernel_tag"

    # Make calculation request
    local payload="{\"birth_time\":\"$date\",\"latitude\":37.7749,\"longitude\":-122.4194,\"elevation\":25,\"zodiac\":\"tropical\",\"ayanamsa\":\"lahiri\"}"

    local response=$(curl -s -X POST http://127.0.0.1:$port/calculate \
        -H 'content-type: application/json' \
        -d "$payload")

    if echo "$response" | jq -e '.meta' > /dev/null 2>&1; then
        local actual_kernel=$(echo "$response" | jq -r '.meta.kernel_set_tag')
        local actual_frame=$(echo "$response" | jq -r '.meta.observer_frame_used')

        echo "   Result: $actual_kernel / $actual_frame"

        if [[ "$actual_frame" == "$expected_frame" ]]; then
            echo "   ✅ Observer frame as expected"
        else
            echo "   ⚠️  Expected $expected_frame, got $actual_frame"
        fi
    else
        echo "   ❌ Calculation failed:"
        echo "$response" | jq -r '.detail // "Unknown error"' | sed 's/^/      /'
    fi
}

# Verify both services are running
echo "🔍 Checking services..."
for port in 8000 8001; do
    if curl -s http://127.0.0.1:$port/health > /dev/null; then
        local kernel=$(curl -s http://127.0.0.1:$port/info | jq -r '.meta.kernel_set_tag')
        echo "   ✅ Port $port: $kernel"
    else
        echo "   ❌ Port $port: Not responding"
        echo ""
        echo "💡 Start services with: ./scripts/start_dual_ephemeris.sh"
        exit 1
    fi
done

# Test scenarios
echo ""
echo "🧪 Test Scenarios:"

# Modern date - both services should work with ITRF93
test_calculation 8000 "2024-06-21T18:00:00Z" "Modern date on DE440" "ITRF93"
test_calculation 8001 "2024-06-21T18:00:00Z" "Modern date on DE441" "ITRF93"

# Far future - should use IAU_EARTH (no EOP data for year 3000)
test_calculation 8000 "3000-06-01T00:00:00Z" "Far future on DE440" "IAU_EARTH"
test_calculation 8001 "3000-06-01T00:00:00Z" "Far future on DE441" "IAU_EARTH"

# Edge of DE440 coverage - DE441 should handle, DE440 might fail
test_calculation 8001 "2700-01-01T00:00:00Z" "Near DE440 limit on DE441" "IAU_EARTH"

echo ""
echo "🔬 Coverage Summary:"
echo "   DE440: 1550-2650 CE (standard astrology range)"
echo "   DE441: 13201 BCE - 17191 CE (extended historical range)"
echo ""
echo "🔭 Observer Frame Logic:"
echo "   ITRF93: High precision Earth orientation (modern dates)"
echo "   IAU_EARTH: Fallback for dates without EOP data"
echo ""
echo "✅ Smoke test complete"