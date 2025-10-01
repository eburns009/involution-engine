"""
Structured JSON logging for the Involution Engine.

Provides consistent, structured logging with request correlation,
performance metrics, and business context for observability.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Dict, Any, Optional
from datetime import datetime, timezone


# Context variables for request correlation
request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_context: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs in a consistent JSON format with:
    - Standard fields: timestamp, level, logger, message
    - Request correlation: request_id, user_id
    - Performance: duration_ms (for timed operations)
    - Business context: system, bodies, ayanamsha, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base log structure
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request correlation if available
        request_id = request_id_context.get()
        if request_id:
            log_entry["request_id"] = request_id

        user_id = user_id_context.get()
        if user_id:
            log_entry["user_id"] = user_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the log record
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info'
            } and not key.startswith('_'):
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))


class StructuredLogger:
    """
    Structured logger with business context support.

    Provides methods for logging common business operations with
    consistent structure and correlation.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def positions_calculated(
        self,
        system: str,
        bodies: list,
        duration_ms: float,
        ephemeris: str,
        ayanamsha: Optional[str] = None,
        cache_hit: bool = False
    ):
        """Log successful position calculation."""
        self.logger.info(
            "Positions calculated successfully",
            extra={
                "operation": "positions_calculated",
                "system": system,
                "bodies": bodies,
                "body_count": len(bodies),
                "duration_ms": round(duration_ms, 2),
                "ephemeris": ephemeris,
                "ayanamsha": ayanamsha,
                "cache_hit": cache_hit,
                "performance_category": self._categorize_performance(duration_ms)
            }
        )

    def positions_error(
        self,
        error_code: str,
        error_title: str,
        system: str,
        bodies: list,
        duration_ms: float,
        spice_error: Optional[str] = None
    ):
        """Log position calculation error."""
        self.logger.error(
            f"Position calculation failed: {error_title}",
            extra={
                "operation": "positions_error",
                "error_code": error_code,
                "error_title": error_title,
                "system": system,
                "bodies": bodies,
                "body_count": len(bodies),
                "duration_ms": round(duration_ms, 2),
                "spice_error": spice_error
            }
        )

    def time_resolved(
        self,
        local_datetime: str,
        place_name: str,
        utc_result: str,
        duration_ms: float,
        tzdb_version: str
    ):
        """Log successful time resolution."""
        self.logger.info(
            "Local time resolved to UTC",
            extra={
                "operation": "time_resolved",
                "local_datetime": local_datetime,
                "place_name": place_name,
                "utc_result": utc_result,
                "duration_ms": round(duration_ms, 2),
                "tzdb_version": tzdb_version
            }
        )

    def geocode_searched(
        self,
        query: str,
        result_count: int,
        duration_ms: float,
        service: str = "nominatim"
    ):
        """Log geocoding search."""
        self.logger.info(
            "Geocoding search completed",
            extra={
                "operation": "geocode_searched",
                "query": query,
                "result_count": result_count,
                "duration_ms": round(duration_ms, 2),
                "service": service
            }
        )

    def cache_operation(
        self,
        operation: str,  # "hit", "miss", "set", "evict"
        key_hash: str,
        cache_size: int,
        hit_rate: Optional[float] = None
    ):
        """Log cache operations."""
        self.logger.debug(
            f"Cache {operation}",
            extra={
                "operation": f"cache_{operation}",
                "key_hash": key_hash,
                "cache_size": cache_size,
                "hit_rate": hit_rate
            }
        )

    def worker_pool_operation(
        self,
        operation: str,  # "task_submitted", "task_completed", "worker_created", "worker_error"
        pool_size: int,
        queue_size: int,
        duration_ms: Optional[float] = None
    ):
        """Log worker pool operations."""
        level = logging.WARNING if operation.endswith("_error") else logging.DEBUG
        self.logger.log(
            level,
            f"Worker pool {operation}",
            extra={
                "operation": f"worker_pool_{operation}",
                "pool_size": pool_size,
                "queue_size": queue_size,
                "duration_ms": round(duration_ms, 2) if duration_ms else None
            }
        )

    def kernel_operation(
        self,
        operation: str,  # "loaded", "verified", "error"
        kernel_path: str,
        bundle: str,
        checksum_valid: Optional[bool] = None,
        duration_ms: Optional[float] = None
    ):
        """Log SPICE kernel operations."""
        level = logging.ERROR if operation == "error" else logging.INFO
        self.logger.log(
            level,
            f"SPICE kernel {operation}",
            extra={
                "operation": f"kernel_{operation}",
                "kernel_path": kernel_path,
                "bundle": bundle,
                "checksum_valid": checksum_valid,
                "duration_ms": round(duration_ms, 2) if duration_ms else None
            }
        )

    def startup_event(
        self,
        component: str,
        status: str,  # "starting", "ready", "error"
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log application startup events."""
        level = logging.ERROR if status == "error" else logging.INFO
        self.logger.log(
            level,
            f"Startup: {component} {status}",
            extra={
                "operation": "startup",
                "component": component,
                "status": status,
                "duration_ms": round(duration_ms, 2) if duration_ms else None,
                **(details or {})
            }
        )

    @staticmethod
    def _categorize_performance(duration_ms: float) -> str:
        """Categorize performance for easy filtering."""
        if duration_ms < 50:
            return "fast"
        elif duration_ms < 200:
            return "normal"
        elif duration_ms < 1000:
            return "slow"
        else:
            return "very_slow"


def setup_logging(level: str = "INFO", enable_json: bool = True) -> None:
    """
    Setup structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        enable_json: Whether to use JSON formatting
    """
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=[],  # Clear default handlers
        force=True
    )

    # Create console handler
    console_handler = logging.StreamHandler()

    if enable_json:
        console_handler.setFormatter(JsonFormatter())
    else:
        # Simple formatter for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def set_request_context(request_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """
    Set request context for correlation.

    Args:
        request_id: Optional request ID (generated if not provided)
        user_id: Optional user ID

    Returns:
        The request ID (generated or provided)
    """
    if request_id is None:
        request_id = str(uuid.uuid4())

    request_id_context.set(request_id)
    if user_id:
        user_id_context.set(user_id)

    return request_id


def clear_request_context():
    """Clear request context."""
    request_id_context.set(None)
    user_id_context.set(None)


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_context.get()


class TimedOperation:
    """Context manager for timing operations with automatic logging."""

    def __init__(self, logger: StructuredLogger, operation_name: str, **context):
        self.logger = logger
        self.operation_name = operation_name
        self.context = context
        self.start_time = None
        self.duration_ms = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000

        if exc_type is None:
            # Success
            self.logger.logger.info(
                f"Operation completed: {self.operation_name}",
                extra={
                    "operation": self.operation_name,
                    "duration_ms": round(self.duration_ms, 2),
                    "performance_category": StructuredLogger._categorize_performance(self.duration_ms),
                    **self.context
                }
            )
        else:
            # Error
            self.logger.logger.error(
                f"Operation failed: {self.operation_name}",
                extra={
                    "operation": self.operation_name,
                    "duration_ms": round(self.duration_ms, 2),
                    "error_type": exc_type.__name__ if exc_type else None,
                    "error_message": str(exc_val) if exc_val else None,
                    **self.context
                }
            )