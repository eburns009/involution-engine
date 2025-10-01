# Involution Engine Observability

This directory contains observability configuration and examples for monitoring the Involution Engine v1.1.

## Overview

The Involution Engine includes comprehensive observability features:

- **Structured JSON Logging** - Business operation logging with request correlation
- **Prometheus Metrics** - Performance and business metrics for monitoring
- **OpenTelemetry Tracing** - Optional distributed tracing support
- **Enhanced Health Checks** - Rich health endpoint with business statistics

## Quick Start

### 1. Enable Structured Logging

Structured logging is enabled by default. Logs are output in JSON format:

```json
{
  "timestamp": "2023-12-01T12:00:00.000Z",
  "level": "INFO",
  "logger": "app.api",
  "message": "Positions calculated successfully",
  "request_id": "abc123",
  "operation": "positions_calculated",
  "system": "tropical",
  "bodies": ["Sun", "Moon"],
  "duration_ms": 45.2,
  "ephemeris": "DE440",
  "cache_hit": false
}
```

### 2. Prometheus Metrics

Access metrics at: `http://localhost:8080/metrics`

Key metrics include:
- `involution_requests_total` - HTTP request count by endpoint/status
- `involution_request_duration_seconds` - Request latency distribution
- `involution_positions_calculated_total` - Position calculations by system/ephemeris
- `involution_positions_duration_seconds` - Calculation performance
- `involution_cache_hit_rate` - Cache performance
- `involution_errors_total` - Error rates by category

### 3. Health Check with Business Stats

Enhanced health endpoint: `http://localhost:8080/healthz`

Returns comprehensive status including:
- SPICE kernel status and verification
- Worker pool health and statistics
- Cache performance metrics
- Business operation summary
- System configuration

### 4. Optional OpenTelemetry Tracing

Enable tracing with environment variables:

```bash
export OTEL_ENABLED=true
export OTEL_SERVICE_NAME=involution-engine
export OTEL_JAEGER_ENDPOINT=http://localhost:14268/api/traces
```

Requires OpenTelemetry packages:
```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-exporter-jaeger
```

## Grafana Dashboard

Import the included Grafana dashboard for comprehensive monitoring:

1. Copy `grafana-dashboard.json` to your Grafana instance
2. Configure Prometheus data source
3. Import the dashboard

The dashboard includes:
- Request rate and latency percentiles
- Position calculation performance by system
- Cache hit rates and efficiency
- Error rates by category
- Worker pool utilization
- System health overview

## Monitoring Setup

### Docker Compose Example

```yaml
version: '3.8'
services:
  involution-engine:
    build: ./server
    ports:
      - "8080:8080"
    environment:
      - OTEL_ENABLED=true
      - OTEL_JAEGER_ENDPOINT=http://jaeger:14268/api/traces

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
      - "14268:14268"

volumes:
  grafana-storage:
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'involution-engine'
    static_configs:
      - targets: ['involution-engine:8080']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

## Log Aggregation

For production deployments, consider log aggregation with:

### ELK Stack
- **Elasticsearch** - Log storage and search
- **Logstash** - Log processing and transformation
- **Kibana** - Log visualization and analysis

### Fluentd/Fluent Bit
- Lightweight log forwarding
- Support for multiple output destinations
- Built-in JSON parsing

Example Fluentd configuration:
```
<source>
  @type forward
  port 24224
</source>

<filter involution.**>
  @type parser
  key_name log
  <parse>
    @type json
  </parse>
</filter>

<match involution.**>
  @type elasticsearch
  host elasticsearch
  port 9200
  index_name involution-logs
</match>
```

## Business Metrics

The system provides business-specific metrics for astronomical operations:

### Position Calculations
- **Calculation Rate** - Positions calculated per second by system (tropical/sidereal)
- **Performance** - P50/P95/P99 latency for calculations
- **Ephemeris Usage** - Distribution between DE440/DE441 usage
- **Body Distribution** - Most frequently calculated celestial bodies
- **Cache Efficiency** - Cache hit rates for position requests

### Time Resolution
- **Resolution Rate** - Local time to UTC conversions per second
- **Performance** - Time resolution latency
- **TZDB Coverage** - Geographic distribution of time resolution requests

### Geocoding
- **Search Rate** - Geocoding searches per second
- **Result Quality** - Distribution of result counts per search
- **Performance** - Geocoding search latency

### Error Patterns
- **Error Categories** - Breakdown by error type (RANGE, INPUT, SYSTEM, etc.)
- **Error Rates** - Error frequency over time
- **Recovery Patterns** - Error resolution and retry behavior

## Alerting

Recommended alerts for production:

### Critical Alerts
- Application down (no metrics for 2+ minutes)
- High error rate (>5% for 5+ minutes)
- Cache hit rate below 70%
- Worker pool queue depth >10

### Warning Alerts
- P95 latency >200ms for 10+ minutes
- Kernel verification failures
- SPICE worker process failures
- Low cache efficiency (<50% hit rate)

### Prometheus Alerting Rules

```yaml
groups:
- name: involution-engine
  rules:
  - alert: HighErrorRate
    expr: rate(involution_errors_total[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors/second"

  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(involution_request_duration_seconds_bucket[5m])) > 0.2
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High request latency"
      description: "95th percentile latency is {{ $value }}s"

  - alert: LowCacheHitRate
    expr: involution_cache_hit_rate < 0.7
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Low cache hit rate"
      description: "Cache hit rate is {{ $value }}"
```

## Configuration

Observability features can be configured via environment variables:

```bash
# Structured Logging
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
JSON_LOGGING=true           # Enable JSON formatting

# OpenTelemetry Tracing
OTEL_ENABLED=false          # Enable/disable tracing
OTEL_SERVICE_NAME=involution-engine
OTEL_JAEGER_ENDPOINT=http://localhost:14268/api/traces
OTEL_SAMPLE_RATE=1.0        # Sampling rate (0.0-1.0)

# Metrics
METRICS_ENABLED=true        # Enable/disable Prometheus metrics
```

## Production Considerations

### Performance Impact
- **Structured Logging** - Minimal overhead (~1-2ms per request)
- **Prometheus Metrics** - Low overhead (~0.5ms per request)
- **OpenTelemetry Tracing** - Moderate overhead (~5-10ms per request when enabled)

### Data Retention
- **Metrics** - Recommend 30-90 days retention
- **Logs** - Recommend 7-30 days retention
- **Traces** - Recommend 1-7 days retention

### Security
- Ensure metrics endpoints are not publicly accessible
- Use authentication for Grafana and monitoring tools
- Consider log sanitization for sensitive data
- Implement proper RBAC for monitoring access

### Scalability
- Use horizontal scaling for log aggregation
- Implement metrics federation for multiple instances
- Consider sampling for high-volume tracing
- Use efficient time-series databases for metrics storage