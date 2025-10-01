# Involution Ephemeris Gateway

Smart routing gateway for dual SPICE ephemeris services with automatic date-based service selection.

## Features

- **Smart Routing**: Automatically routes requests to optimal ephemeris service based on date
- **Coverage Optimization**: Uses DE440 (fast, 114MB) for modern dates, DE441 (comprehensive, 310MB) for historical
- **User-Friendly Prompts**: Suggests enabling "Historical Pack" for out-of-range dates
- **Override Support**: Manual kernel selection via query parameters
- **Transparent Metadata**: Shows routing decisions in response

## Quick Start

```bash
# Install dependencies
npm install

# Start gateway (assumes backend services running)
npm start

# Or with custom service URLs
DE440_SERVICE=http://spice-de440:8000 DE441_SERVICE=http://spice-de441:8001 npm start
```

## Routing Logic

### Automatic Routing

| Date Range | Target Service | Reason |
|------------|----------------|--------|
| 1550-2650 CE | DE440 (:8000) | Optimal coverage, smaller size |
| Outside range + historical enabled | DE441 (:8001) | Extended coverage |
| Outside range + historical disabled | Error + prompt | User needs to opt-in |

### Manual Overrides

```bash
# Force DE441 (historical)
curl -X POST http://localhost:3000/calculate?kernel=de441 -d '{...}'

# Enable historical auto-routing
curl -X POST http://localhost:3000/calculate \
  -H "x-historical-enabled: true" \
  -d '{"birth_time":"500-01-01T00:00:00Z",...}'
```

## API Examples

### Modern Date (Auto → DE440)
```bash
curl -X POST http://localhost:3000/calculate \
  -H 'Content-Type: application/json' \
  -d '{
    "birth_time": "2024-06-21T18:00:00Z",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "zodiac": "tropical"
  }'

# Response includes routing metadata:
{
  "data": {...},
  "meta": {
    "kernel_set_tag": "DE440",
    "gateway_routing": {
      "selected_kernel": "DE440",
      "reason": "optimal_coverage",
      "year": 2024,
      "service_url": "http://127.0.0.1:8000"
    }
  }
}
```

### Historical Date (Prompt for Pack)
```bash
curl -X POST http://localhost:3000/calculate \
  -d '{"birth_time":"1066-10-14T12:00:00Z",...}'

# Response:
{
  "error": "Historical ephemeris required",
  "details": {
    "requested_year": 1066,
    "available_coverage": {
      "de440": "1550-2650 CE",
      "de441": "13201 BCE - 17191 CE"
    },
    "solutions": [
      "Enable Historical Pack in settings",
      "Add ?kernel=de441 to request",
      "Add header: x-historical-enabled: true"
    ]
  },
  "code": "HISTORICAL_REQUIRED"
}
```

### Manual Override
```bash
curl -X POST http://localhost:3000/calculate?kernel=de441 \
  -d '{"birth_time":"1066-10-14T12:00:00Z",...}'

# Routes to DE441 regardless of user settings
```

## UI Integration

### Frontend Settings
```javascript
// User preference
const historicalPackEnabled = getUserSetting('historicalPack');

// Auto-enable historical routing
const headers = {
  'Content-Type': 'application/json'
};

if (historicalPackEnabled) {
  headers['x-historical-enabled'] = 'true';
}

fetch('/calculate', {
  method: 'POST',
  headers,
  body: JSON.stringify(chartRequest)
});
```

### Error Handling
```javascript
try {
  const response = await fetch('/calculate', {...});
  const result = await response.json();

  if (result.code === 'HISTORICAL_REQUIRED') {
    // Show "Enable Historical Pack" dialog
    showHistoricalPackDialog(result.details);
  }
} catch (error) {
  // Handle network errors
}
```

## Deployment

### Docker Compose
```yaml
services:
  gateway:
    build: ./gateway
    ports:
      - "3000:3000"
    environment:
      - DE440_SERVICE=http://spice-de440:8000
      - DE441_SERVICE=http://spice-de441:8001
    depends_on:
      - spice-de440
      - spice-de441

  spice-de440:
    build: ./services/spice
    environment:
      - KERNEL_SET_TAG=DE440
      - METAKERNEL_PATH=kernels/involution_de440.tm

  spice-de441:
    build: ./services/spice
    environment:
      - KERNEL_SET_TAG=DE441
      - METAKERNEL_PATH=kernels/involution_de441.tm
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: involution-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: involution-gateway
  template:
    spec:
      containers:
      - name: gateway
        image: involution/gateway:latest
        env:
        - name: DE440_SERVICE
          value: "http://spice-de440-service:8000"
        - name: DE441_SERVICE
          value: "http://spice-de441-service:8001"
```

## Monitoring

The gateway provides detailed routing metadata for observability:

```json
{
  "meta": {
    "gateway_routing": {
      "selected_kernel": "DE440",
      "reason": "optimal_coverage",
      "year": 2024,
      "service_url": "http://127.0.0.1:8000"
    }
  }
}
```

Use this data for:
- Usage analytics (DE440 vs DE441 usage)
- Performance monitoring (routing overhead)
- Cost optimization (historical service scaling)

## Benefits

- **Performance**: Routes modern dates to lighter DE440 service
- **User Experience**: Clear prompts for historical dates
- **Resource Efficiency**: Only runs heavy DE441 when needed
- **Flexibility**: Manual overrides for power users
- **Transparency**: Full routing decision visibility