"""
Prometheus metrics collection for the Involution Engine.

Provides business metrics for monitoring calculation performance,
cache efficiency, error rates, and system health.
"""

from prometheus_client import (
    Counter, Histogram, Gauge, Info, CollectorRegistry,
    generate_latest, CONTENT_TYPE_LATEST
)
from typing import Dict, Any, Optional, List
import time
from contextvars import ContextVar


# Global metrics registry
REGISTRY = CollectorRegistry()

# Request metrics
REQUEST_COUNT = Counter(
    'involution_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code'],
    registry=REGISTRY
)

REQUEST_DURATION = Histogram(
    'involution_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
    registry=REGISTRY
)

# Position calculation metrics
POSITIONS_CALCULATED = Counter(
    'involution_positions_calculated_total',
    'Total number of position calculations',
    ['system', 'ephemeris', 'cache_hit'],
    registry=REGISTRY
)

POSITIONS_DURATION = Histogram(
    'involution_positions_duration_seconds',
    'Position calculation duration in seconds',
    ['system', 'ephemeris'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
    registry=REGISTRY
)

POSITIONS_BODY_COUNT = Histogram(
    'involution_positions_body_count',
    'Number of bodies calculated per request',
    buckets=[1, 2, 3, 5, 7, 10, 12],
    registry=REGISTRY
)

# Error metrics
ERRORS_TOTAL = Counter(
    'involution_errors_total',
    'Total number of errors by category',
    ['error_code', 'error_category'],
    registry=REGISTRY
)

# Cache metrics
CACHE_OPERATIONS = Counter(
    'involution_cache_operations_total',
    'Total cache operations',
    ['operation'],  # hit, miss, set, evict
    registry=REGISTRY
)

CACHE_SIZE = Gauge(
    'involution_cache_size_entries',
    'Current number of entries in cache',
    registry=REGISTRY
)

CACHE_HIT_RATE = Gauge(
    'involution_cache_hit_rate',
    'Cache hit rate (0.0 to 1.0)',
    registry=REGISTRY
)

# Worker pool metrics
WORKER_POOL_SIZE = Gauge(
    'involution_worker_pool_size',
    'Number of worker processes',
    registry=REGISTRY
)

WORKER_POOL_QUEUE_SIZE = Gauge(
    'involution_worker_pool_queue_size',
    'Number of tasks in worker queue',
    registry=REGISTRY
)

WORKER_POOL_TASKS = Counter(
    'involution_worker_pool_tasks_total',
    'Total worker pool tasks',
    ['status'],  # submitted, completed, failed
    registry=REGISTRY
)

WORKER_POOL_TASK_DURATION = Histogram(
    'involution_worker_pool_task_duration_seconds',
    'Worker pool task duration',
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
    registry=REGISTRY
)

# SPICE kernel metrics
KERNEL_LOADS = Counter(
    'involution_kernel_loads_total',
    'Total kernel load operations',
    ['bundle', 'status'],  # success, failed
    registry=REGISTRY
)

KERNEL_VERIFICATION = Counter(
    'involution_kernel_verifications_total',
    'Total kernel verifications',
    ['bundle', 'valid'],  # true, false
    registry=REGISTRY
)

# Time resolution metrics
TIME_RESOLUTIONS = Counter(
    'involution_time_resolutions_total',
    'Total time resolution requests',
    ['status'],  # success, failed
    registry=REGISTRY
)

TIME_RESOLUTION_DURATION = Histogram(
    'involution_time_resolution_duration_seconds',
    'Time resolution duration',
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0],
    registry=REGISTRY
)

# Geocoding metrics
GEOCODE_SEARCHES = Counter(
    'involution_geocode_searches_total',
    'Total geocoding searches',
    ['status'],  # success, failed, no_results
    registry=REGISTRY
)

GEOCODE_DURATION = Histogram(
    'involution_geocode_duration_seconds',
    'Geocoding search duration',
    buckets=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
    registry=REGISTRY
)

# System info
SYSTEM_INFO = Info(
    'involution_system_info',
    'System information',
    registry=REGISTRY
)

# Application uptime
APP_START_TIME = Gauge(
    'involution_app_start_time_seconds',
    'Unix timestamp when the application started',
    registry=REGISTRY
)


class MetricsCollector:
    """
    High-level metrics collector for business operations.

    Provides methods to record metrics for common operations
    with consistent labeling and timing.
    """

    def __init__(self):
        self.start_time = time.time()
        APP_START_TIME.set(self.start_time)

    def record_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_seconds: float
    ):
        """Record HTTP request metrics."""
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()

        REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration_seconds)

    def record_position_calculation(
        self,
        system: str,
        ephemeris: str,
        body_count: int,
        duration_seconds: float,
        cache_hit: bool = False
    ):
        """Record position calculation metrics."""
        POSITIONS_CALCULATED.labels(
            system=system,
            ephemeris=ephemeris,
            cache_hit=str(cache_hit).lower()
        ).inc()

        POSITIONS_DURATION.labels(
            system=system,
            ephemeris=ephemeris
        ).observe(duration_seconds)

        POSITIONS_BODY_COUNT.observe(body_count)

    def record_error(self, error_code: str):
        """Record error metrics."""
        # Extract category from error code (e.g., "RANGE.EPHEMERIS_OUTSIDE" -> "RANGE")
        error_category = error_code.split('.')[0] if '.' in error_code else error_code

        ERRORS_TOTAL.labels(
            error_code=error_code,
            error_category=error_category
        ).inc()

    def record_cache_operation(
        self,
        operation: str,  # hit, miss, set, evict
        cache_size: int,
        hit_rate: Optional[float] = None
    ):
        """Record cache operation metrics."""
        CACHE_OPERATIONS.labels(operation=operation).inc()
        CACHE_SIZE.set(cache_size)

        if hit_rate is not None:
            CACHE_HIT_RATE.set(hit_rate)

    def record_worker_pool_state(
        self,
        pool_size: int,
        queue_size: int
    ):
        """Record worker pool state."""
        WORKER_POOL_SIZE.set(pool_size)
        WORKER_POOL_QUEUE_SIZE.set(queue_size)

    def record_worker_task(
        self,
        status: str,  # submitted, completed, failed
        duration_seconds: Optional[float] = None
    ):
        """Record worker pool task metrics."""
        WORKER_POOL_TASKS.labels(status=status).inc()

        if duration_seconds is not None:
            WORKER_POOL_TASK_DURATION.observe(duration_seconds)

    def record_kernel_operation(
        self,
        bundle: str,
        operation: str,  # load, verify
        success: bool
    ):
        """Record SPICE kernel operation metrics."""
        if operation == "load":
            KERNEL_LOADS.labels(
                bundle=bundle,
                status="success" if success else "failed"
            ).inc()
        elif operation == "verify":
            KERNEL_VERIFICATION.labels(
                bundle=bundle,
                valid=str(success).lower()
            ).inc()

    def record_time_resolution(
        self,
        success: bool,
        duration_seconds: float
    ):
        """Record time resolution metrics."""
        TIME_RESOLUTIONS.labels(
            status="success" if success else "failed"
        ).inc()

        TIME_RESOLUTION_DURATION.observe(duration_seconds)

    def record_geocode_search(
        self,
        status: str,  # success, failed, no_results
        duration_seconds: float
    ):
        """Record geocoding search metrics."""
        GEOCODE_SEARCHES.labels(status=status).inc()
        GEOCODE_DURATION.observe(duration_seconds)

    def set_system_info(
        self,
        version: str,
        kernel_bundle: str,
        python_version: str,
        spice_version: str
    ):
        """Set system information metrics."""
        SYSTEM_INFO.info({
            'version': version,
            'kernel_bundle': kernel_bundle,
            'python_version': python_version,
            'spice_version': spice_version
        })

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of key metrics for health checks."""
        # Calculate uptime
        uptime_seconds = time.time() - self.start_time

        # Get current metric values
        try:
            cache_size = int(CACHE_SIZE._value._value) if hasattr(CACHE_SIZE._value, '_value') else 0
            cache_hit_rate = float(CACHE_HIT_RATE._value._value) if hasattr(CACHE_HIT_RATE._value, '_value') else 0.0
            worker_pool_size = int(WORKER_POOL_SIZE._value._value) if hasattr(WORKER_POOL_SIZE._value, '_value') else 0
            queue_size = int(WORKER_POOL_QUEUE_SIZE._value._value) if hasattr(WORKER_POOL_QUEUE_SIZE._value, '_value') else 0
        except (AttributeError, TypeError):
            # Fallback values if metrics haven't been initialized
            cache_size = 0
            cache_hit_rate = 0.0
            worker_pool_size = 0
            queue_size = 0

        return {
            "uptime_seconds": round(uptime_seconds, 1),
            "cache": {
                "size": cache_size,
                "hit_rate": round(cache_hit_rate, 3)
            },
            "worker_pool": {
                "size": worker_pool_size,
                "queue_size": queue_size
            }
        }


# Global metrics collector instance
metrics = MetricsCollector()


def get_metrics_content() -> tuple[str, str]:
    """
    Get Prometheus metrics content for /metrics endpoint.

    Returns:
        Tuple of (content, content_type)
    """
    content = generate_latest(REGISTRY)
    return content.decode('utf-8'), CONTENT_TYPE_LATEST


class RequestMetricsMiddleware:
    """
    Middleware to automatically record request metrics.

    Records request count, duration, and response status for all requests.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request info
        method = scope["method"]
        path = scope["path"]

        # Normalize endpoint for metrics (remove IDs, etc.)
        endpoint = self._normalize_endpoint(path)

        start_time = time.perf_counter()
        status_code = 500  # Default to error

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time
            metrics.record_request(method, endpoint, status_code, duration)

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics grouping."""
        # Remove query parameters
        if "?" in path:
            path = path.split("?")[0]

        # Normalize known API patterns
        if path.startswith("/v1/"):
            return path  # Keep API versioned paths as-is

        # Group common paths
        if path == "/":
            return "/"
        elif path == "/healthz":
            return "/healthz"
        elif path == "/metrics":
            return "/metrics"
        elif path.startswith("/docs"):
            return "/docs"
        elif path.startswith("/openapi"):
            return "/openapi"
        else:
            return "/other"


def setup_metrics_middleware(app):
    """Setup metrics middleware for the FastAPI app."""
    # Note: In FastAPI, middleware is typically added in main.py
    # This function returns the middleware class for manual setup
    return RequestMetricsMiddleware