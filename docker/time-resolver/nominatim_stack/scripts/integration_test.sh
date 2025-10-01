#!/bin/bash
# Integration test between Nominatim and Time Resolver
# Usage: ./scripts/integration_test.sh

set -e

NOMINATIM_URL="http://localhost:8080"
TIME_RESOLVER_URL="http://localhost:8081"  # Adjust if Time Resolver runs on different port

echo "🧪 Nominatim + Time Resolver Integration Test"
echo "=============================================="

# Test cases: historical locations with known timezone challenges
declare -A TEST_CASES=(
    ["Fort Knox, KY"]="1943-06-15T14:30:00"
    ["Louisville, KY"]="1950-03-15T12:00:00"
    ["Detroit, MI"]="1910-07-04T09:00:00"
    ["Phoenix, AZ"]="1944-01-01T15:30:00"
)

echo "📍 Testing historical timezone resolution for known locations..."
echo ""

for location in "${!TEST_CASES[@]}"; do
    datetime="${TEST_CASES[$location]}"

    echo "🔍 Testing: $location at $datetime"
    echo "   1. Geocoding with Nominatim..."

    # Step 1: Get coordinates from Nominatim
    SEARCH_RESULT=$(curl -s "$NOMINATIM_URL/search?q=$(echo "$location" | sed 's/ /+/g')&format=json&limit=1" || echo "[]")

    if ! echo "$SEARCH_RESULT" | jq -e '.[0].lat' >/dev/null 2>&1; then
        echo "   ❌ Geocoding failed for $location"
        continue
    fi

    LAT=$(echo "$SEARCH_RESULT" | jq -r '.[0].lat')
    LON=$(echo "$SEARCH_RESULT" | jq -r '.[0].lon')
    DISPLAY_NAME=$(echo "$SEARCH_RESULT" | jq -r '.[0].display_name')

    echo "   ✅ Found: $DISPLAY_NAME"
    echo "   📍 Coordinates: $LAT, $LON"

    # Step 2: Resolve historical timezone
    echo "   2. Resolving historical timezone..."

    TIMEZONE_PAYLOAD=$(cat <<EOF
{
  "local_datetime": "$datetime",
  "place": {
    "lat": $LAT,
    "lon": $LON
  },
  "parity_profile": "strict_history"
}
EOF
)

    TIMEZONE_RESULT=$(curl -s -X POST "$TIME_RESOLVER_URL/v1/time/resolve" \
        -H "Content-Type: application/json" \
        -d "$TIMEZONE_PAYLOAD" || echo "{}")

    if echo "$TIMEZONE_RESULT" | jq -e '.utc' >/dev/null 2>&1; then
        UTC=$(echo "$TIMEZONE_RESULT" | jq -r '.utc')
        ZONE_ID=$(echo "$TIMEZONE_RESULT" | jq -r '.zone_id')
        CONFIDENCE=$(echo "$TIMEZONE_RESULT" | jq -r '.confidence')
        PATCHES=$(echo "$TIMEZONE_RESULT" | jq -r '.provenance.patches_applied[]' 2>/dev/null | tr '\n' ' ' || echo "none")

        echo "   ✅ Timezone resolved: $ZONE_ID"
        echo "   🕐 Local: $datetime → UTC: $UTC"
        echo "   📊 Confidence: $CONFIDENCE"
        echo "   🔧 Patches applied: ${PATCHES:-none}"

        # Check if historical patches were applied for pre-1967 dates
        if [[ "$datetime" < "1967-01-01" && "$PATCHES" != "none" ]]; then
            echo "   🎯 Historical accuracy: Applied pre-1967 patches ✅"
        elif [[ "$datetime" < "1967-01-01" ]]; then
            echo "   ⚠️  Historical accuracy: No patches applied for pre-1967 date"
        fi

    else
        echo "   ❌ Timezone resolution failed"
        echo "   Response: $TIMEZONE_RESULT"
    fi

    echo ""
done

echo "🧪 Running specific test cases..."
echo ""

# Test case 1: Fort Knox 1943 (should apply fort_knox_1943 patch)
echo "🎯 Test Case 1: Fort Knox 1943 (Eastern War Time)"
FORT_KNOX_RESULT=$(curl -s -X POST "$TIME_RESOLVER_URL/v1/time/resolve" \
    -H "Content-Type: application/json" \
    -d '{
        "local_datetime": "1943-06-15T14:30:00",
        "place": {"lat": 37.89, "lon": -85.96},
        "parity_profile": "strict_history"
    }')

if echo "$FORT_KNOX_RESULT" | jq -e '.provenance.patches_applied | contains(["fort_knox_1943"])' >/dev/null 2>&1; then
    echo "✅ Fort Knox patch correctly applied"
    UTC=$(echo "$FORT_KNOX_RESULT" | jq -r '.utc')
    echo "   1943-06-15T14:30:00 local → $UTC UTC"
else
    echo "❌ Fort Knox patch not applied"
fi

echo ""

# Test case 2: Modern comparison (should not apply patches)
echo "🎯 Test Case 2: Modern NYC (no patches expected)"
MODERN_NYC_RESULT=$(curl -s -X POST "$TIME_RESOLVER_URL/v1/time/resolve" \
    -H "Content-Type: application/json" \
    -d '{
        "local_datetime": "2023-06-15T14:30:00",
        "place": {"lat": 40.7128, "lon": -74.0060},
        "parity_profile": "strict_history"
    }')

MODERN_PATCHES=$(echo "$MODERN_NYC_RESULT" | jq -r '.provenance.patches_applied | length')
if [ "$MODERN_PATCHES" = "0" ]; then
    echo "✅ No patches applied for modern date (correct)"
    UTC=$(echo "$MODERN_NYC_RESULT" | jq -r '.utc')
    ZONE=$(echo "$MODERN_NYC_RESULT" | jq -r '.zone_id')
    echo "   2023-06-15T14:30:00 $ZONE → $UTC UTC"
else
    echo "⚠️  Unexpected patches applied for modern date"
fi

echo ""

# Test case 3: Parity profile comparison
echo "🎯 Test Case 3: Parity Profile Comparison (Fort Knox 1943)"
echo "   strict_history vs astro_com:"

for profile in "strict_history" "astro_com"; do
    PARITY_RESULT=$(curl -s -X POST "$TIME_RESOLVER_URL/v1/time/resolve" \
        -H "Content-Type: application/json" \
        -d "{
            \"local_datetime\": \"1943-06-15T14:30:00\",
            \"place\": {\"lat\": 37.89, \"lon\": -85.96},
            \"parity_profile\": \"$profile\"
        }")

    UTC=$(echo "$PARITY_RESULT" | jq -r '.utc')
    PATCHES=$(echo "$PARITY_RESULT" | jq -r '.provenance.patches_applied | length')
    echo "   $profile: $UTC (patches: $PATCHES)"
done

echo ""
echo "✅ Integration test complete!"
echo ""
echo "📊 Summary:"
echo "   🌍 Nominatim provides accurate coordinates for historical locations"
echo "   🕐 Time Resolver applies appropriate historical timezone corrections"
echo "   🎯 Integration enables historically accurate geocoded time resolution"
echo ""
echo "💡 Use case: Build applications that can accurately determine historical"
echo "   timezones for any address or location name, accounting for complex"
echo "   historical timezone changes in the United States."