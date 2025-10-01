# Nominatim Self-Hosted Stack (with Nightly Updates)

This brings up a self-hosted **Nominatim** instance using Docker, with:
- Import from a provided `.osm.pbf` file
- API on **http://localhost:8080/**
- Nightly **replication updates** (Geofabrik diffs) via a cron sidecar

## 1) Prepare data
Download an OSM extract (choose your region):
- Geofabrik: https://download.geofabrik.de/

Example (US):
```bash
wget https://download.geofabrik.de/north-america/us-latest.osm.pbf -O data/data.osm.pbf
```

Example (Germany):
```bash
wget https://download.geofabrik.de/europe/germany-latest.osm.pbf -O data/data.osm.pbf
```

Example (Monaco - smallest for testing):
```bash
wget https://download.geofabrik.de/europe/monaco-latest.osm.pbf -O data/data.osm.pbf
```

## 2) Configure region
Edit `.env` to match your data source:
```bash
# For US updates
REPLICATION_URL=https://download.geofabrik.de/north-america/us-updates

# For Germany updates
REPLICATION_URL=https://download.geofabrik.de/europe/germany-updates

# For Europe updates (broader)
REPLICATION_URL=https://download.geofabrik.de/europe-updates
```

## 3) Start the stack
```bash
# Start Nominatim + updater
docker-compose up -d

# Monitor logs during initial import (can take hours for large regions)
docker-compose logs -f nominatim

# Check status
curl http://localhost:8080/status.php
```

## 4) Query the API
Once import is complete, you can use the Nominatim API:

```bash
# Search for a place
curl "http://localhost:8080/search?q=New+York&format=json&limit=1"

# Reverse geocoding
curl "http://localhost:8080/reverse?lat=40.7128&lon=-74.0060&format=json"

# Lookup by OSM ID
curl "http://localhost:8080/lookup?osm_ids=R207359&format=json"
```

## 5) Monitor updates
The updater runs nightly at 03:30 UTC via cron. Check logs:
```bash
# View updater logs
docker-compose logs nominatim-updater

# Manual update (immediate)
docker-compose exec nominatim /app/nominatim replication --update

# Check replication status
docker-compose exec nominatim /app/nominatim replication --check
```

## File Structure
```
nominatim_stack/
├── docker-compose.yml    # Main stack definition
├── .env                  # Configuration (region, threads, etc.)
├── cron.d/
│   └── nominatim-update  # Nightly update cron job
├── data/
│   └── data.osm.pbf     # Your OSM extract (place here)
├── pgdata/              # PostgreSQL data (auto-created)
└── scripts/             # Helper scripts (optional)
```

## Performance Tuning

### Hardware Requirements
- **Minimum**: 4GB RAM, 2 CPU cores, 50GB disk
- **Recommended**: 16GB+ RAM, 4+ CPU cores, SSD storage
- **Large regions** (US/Europe): 32GB+ RAM, 8+ CPU cores

### Configuration
Edit `.env` for your hardware:
```bash
# Number of import/query threads
THREADS=8

# Additional Nominatim parameters
NOMINATIM_EXTRA_PARAMS=--osm2pgsql-cache 2000
```

### Database Optimization
For production use, consider:
```bash
# Increase PostgreSQL shared_buffers (inside container)
docker-compose exec nominatim psql -d nominatim -c "ALTER SYSTEM SET shared_buffers = '4GB';"
docker-compose restart nominatim
```

## Troubleshooting

### Import Issues
```bash
# Check import logs
docker-compose logs nominatim

# Restart from scratch (removes all data!)
docker-compose down -v
docker-compose up -d
```

### Update Issues
```bash
# Check update status
docker-compose exec nominatim /app/nominatim replication --check

# Reset replication (if stuck)
docker-compose exec nominatim /app/nominatim replication --init

# Manual update with verbose output
docker-compose exec nominatim /app/nominatim replication --update --verbose
```

### Performance Issues
```bash
# Check database size
docker-compose exec nominatim psql -d nominatim -c "SELECT pg_size_pretty(pg_database_size('nominatim'));"

# Check active connections
docker-compose exec nominatim psql -d nominatim -c "SELECT count(*) FROM pg_stat_activity;"

# Check slow queries
docker-compose exec nominatim psql -d nominatim -c "SELECT query, query_start FROM pg_stat_activity WHERE state = 'active';"
```

## API Documentation
- **Search**: `/search?q=query&format=json`
- **Reverse**: `/reverse?lat=LAT&lon=LON&format=json`
- **Lookup**: `/lookup?osm_ids=ID&format=json`
- **Status**: `/status.php`

Full API documentation: https://nominatim.org/release-docs/latest/api/

## Security Notes
- This setup binds to `localhost:8080` only
- For production, use a reverse proxy (nginx) with SSL
- Consider firewall rules for the PostgreSQL port
- Regular backups recommended for large imports

## Integration Examples

### With Time Resolver
Use Nominatim to get coordinates, then resolve historical timezones:
```bash
# 1. Get coordinates for "Fort Knox, KY"
COORDS=$(curl -s "http://localhost:8080/search?q=Fort+Knox+KY&format=json&limit=1" | jq -r '.[0] | "\(.lat),\(.lon)"')

# 2. Resolve 1943 timezone for those coordinates
curl -X POST http://localhost:8081/v1/time/resolve \
  -H "Content-Type: application/json" \
  -d "{\"local_datetime\": \"1943-06-15T14:30:00\", \"place\": {\"lat\": $(echo $COORDS | cut -d, -f1), \"lon\": $(echo $COORDS | cut -d, -f2)}, \"parity_profile\": \"strict_history\"}"
```

### With Mapping Applications
```javascript
// Use in Leaflet/OpenLayers for address search
fetch('http://localhost:8080/search?q=' + encodeURIComponent(address) + '&format=json')
  .then(r => r.json())
  .then(results => {
    if (results.length > 0) {
      const lat = parseFloat(results[0].lat);
      const lon = parseFloat(results[0].lon);
      map.setView([lat, lon], 15);
    }
  });
```

This stack provides a complete, self-updating geocoding solution for applications requiring offline address resolution and reverse geocoding capabilities.