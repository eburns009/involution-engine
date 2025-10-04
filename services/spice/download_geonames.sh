#!/bin/bash
# Download GeoNames cities database for timezone resolution
# This script is called during deployment to keep the database up-to-date

set -e

GEONAMES_URL="https://download.geonames.org/export/dump/cities15000.zip"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_FILE="$SCRIPT_DIR/cities15000.txt"

echo "📍 Downloading GeoNames cities database..."

# Check if file already exists
if [ -f "$TARGET_FILE" ]; then
    echo "✓ cities15000.txt already exists ($(wc -l < "$TARGET_FILE") cities)"
    echo "  To force re-download, delete the file first"
    exit 0
fi

# Download and extract
echo "  Downloading from $GEONAMES_URL..."
curl -sL "$GEONAMES_URL" -o /tmp/cities15000.zip

echo "  Extracting..."
unzip -q -o /tmp/cities15000.zip -d "$SCRIPT_DIR"

# Verify
if [ -f "$TARGET_FILE" ]; then
    CITY_COUNT=$(wc -l < "$TARGET_FILE")
    echo "✓ Successfully downloaded $CITY_COUNT cities"
else
    echo "✗ Download failed - cities15000.txt not found"
    exit 1
fi

# Cleanup
rm -f /tmp/cities15000.zip
echo "✓ GeoNames database ready"
