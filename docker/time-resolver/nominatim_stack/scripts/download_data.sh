#!/bin/bash
# Download OSM data for different regions
# Usage: ./scripts/download_data.sh [region]

set -e

REGION=${1:-monaco}
DATA_DIR="./data"

mkdir -p "$DATA_DIR"

case "$REGION" in
    "monaco")
        echo "📦 Downloading Monaco (smallest, good for testing)..."
        URL="https://download.geofabrik.de/europe/monaco-latest.osm.pbf"
        UPDATES="https://download.geofabrik.de/europe/monaco-updates"
        ;;
    "us"|"usa")
        echo "📦 Downloading United States (large, ~10GB)..."
        URL="https://download.geofabrik.de/north-america/us-latest.osm.pbf"
        UPDATES="https://download.geofabrik.de/north-america/us-updates"
        ;;
    "germany"|"de")
        echo "📦 Downloading Germany (medium, ~3GB)..."
        URL="https://download.geofabrik.de/europe/germany-latest.osm.pbf"
        UPDATES="https://download.geofabrik.de/europe/germany-updates"
        ;;
    "california"|"ca")
        echo "📦 Downloading California (medium, ~1GB)..."
        URL="https://download.geofabrik.de/north-america/us/california-latest.osm.pbf"
        UPDATES="https://download.geofabrik.de/north-america/us-updates"
        ;;
    "new-york"|"ny")
        echo "📦 Downloading New York (small, ~200MB)..."
        URL="https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf"
        UPDATES="https://download.geofabrik.de/north-america/us-updates"
        ;;
    "kentucky"|"ky")
        echo "📦 Downloading Kentucky (small, ~100MB - includes Fort Knox)..."
        URL="https://download.geofabrik.de/north-america/us/kentucky-latest.osm.pbf"
        UPDATES="https://download.geofabrik.de/north-america/us-updates"
        ;;
    *)
        echo "❌ Unknown region: $REGION"
        echo "Available regions: monaco, us, germany, california, new-york, kentucky"
        echo "Usage: $0 [region]"
        exit 1
        ;;
esac

echo "⬇️  Downloading from: $URL"
wget -c "$URL" -O "$DATA_DIR/data.osm.pbf"

echo "⚙️  Updating .env with replication URL..."
sed -i "s|REPLICATION_URL=.*|REPLICATION_URL=$UPDATES|" .env

echo "✅ Download complete!"
echo "📁 File: $DATA_DIR/data.osm.pbf"
echo "🔄 Updates: $UPDATES"
echo ""
echo "Next steps:"
echo "  docker-compose up -d"
echo "  docker-compose logs -f nominatim"