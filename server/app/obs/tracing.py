"""
Optional OpenTelemetry tracing support for the Involution Engine.

Provides distributed tracing when enabled via configuration,
with automatic instrumentation for FastAPI and business operations.
"""

import logging
import os
from typing import Optional, Dict, Any
from contextlib import contextmanager

# Optional OpenTelemetry imports
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    trace = None
    TracerProvider = None


logger = logging.getLogger(__name__)


class TracingConfig:
    """Configuration for OpenTelemetry tracing."""

    def __init__(
        self,
        enabled: bool = False,
        service_name: str = "involution-engine",
        jaeger_endpoint: str = "http://localhost:14268/api/traces",
        sample_rate: float = 1.0,
        export_timeout: int = 30
    ):
        self.enabled = enabled
        self.service_name = service_name
        self.jaeger_endpoint = jaeger_endpoint
        self.sample_rate = sample_rate
        self.export_timeout = export_timeout

    @classmethod
    def from_env(cls) -> 'TracingConfig':
        """Create tracing config from environment variables."""
        return cls(
            enabled=os.getenv("OTEL_ENABLED", "false").lower() == "true",
            service_name=os.getenv("OTEL_SERVICE_NAME", "involution-engine"),
            jaeger_endpoint=os.getenv("OTEL_JAEGER_ENDPOINT", "http://localhost:14268/api/traces"),
            sample_rate=float(os.getenv("OTEL_SAMPLE_RATE", "1.0")),
            export_timeout=int(os.getenv("OTEL_EXPORT_TIMEOUT", "30"))
        )


class TracingManager:
    """
    Manager for OpenTelemetry tracing setup and operations.

    Handles optional tracing setup and provides business operation
    tracing when enabled.
    """

    def __init__(self):
        self.enabled = False
        self.tracer = None
        self.config = None

    def setup(self, config: TracingConfig) -> bool:
        """
        Setup OpenTelemetry tracing.

        Args:
            config: Tracing configuration

        Returns:
            True if tracing was successfully setup, False otherwise
        """
        self.config = config

        if not config.enabled:
            logger.info("Tracing disabled by configuration")
            return False

        if not TRACING_AVAILABLE:
            logger.warning(
                "OpenTelemetry packages not available. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-instrumentation-fastapi opentelemetry-exporter-jaeger"
            )
            return False

        try:
            # Create resource with service info
            resource = Resource.create({
                "service.name": config.service_name,
                "service.version": "1.1.0"
            })

            # Setup tracer provider
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)

            # Setup Jaeger exporter
            jaeger_exporter = JaegerExporter(
                endpoint=config.jaeger_endpoint,
                timeout=config.export_timeout
            )

            # Add span processor
            span_processor = BatchSpanProcessor(jaeger_exporter)
            tracer_provider.add_span_processor(span_processor)

            # Get tracer
            self.tracer = trace.get_tracer(__name__)
            self.enabled = True

            logger.info(f"OpenTelemetry tracing enabled: {config.service_name} -> {config.jaeger_endpoint}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup OpenTelemetry tracing: {e}")
            return False

    def instrument_fastapi(self, app) -> bool:
        """
        Instrument FastAPI application for automatic tracing.

        Args:
            app: FastAPI application instance

        Returns:
            True if instrumentation succeeded, False otherwise
        """
        if not self.enabled or not TRACING_AVAILABLE:
            return False

        try:
            # Instrument FastAPI
            FastAPIInstrumentor.instrument_app(app)

            # Instrument HTTPX for external calls
            HTTPXClientInstrumentor().instrument()

            logger.info("FastAPI tracing instrumentation enabled")
            return True

        except Exception as e:
            logger.error(f"Failed to instrument FastAPI for tracing: {e}")
            return False

    @contextmanager
    def trace_operation(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracing business operations.

        Args:
            operation_name: Name of the operation being traced
            attributes: Optional attributes to add to the span

        Usage:
            with tracing.trace_operation("positions_calculation", {"system": "tropical"}):
                # perform calculation
                pass
        """
        if not self.enabled or not self.tracer:
            # No-op context manager when tracing is disabled
            yield None
            return

        with self.tracer.start_as_current_span(operation_name) as span:
            # Add attributes if provided
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))

            try:
                yield span
            except Exception as e:
                # Record exception in span
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise

    def trace_positions_calculation(
        self,
        system: str,
        bodies: list,
        ephemeris: str,
        ayanamsha: Optional[str] = None
    ):
        """
        Trace a positions calculation operation.

        Args:
            system: Zodiac system (tropical/sidereal)
            bodies: List of celestial bodies
            ephemeris: Ephemeris used (DE440/DE441)
            ayanamsha: Ayanāṃśa ID for sidereal calculations

        Returns:
            Context manager for the trace span
        """
        attributes = {
            "involution.system": system,
            "involution.body_count": len(bodies),
            "involution.bodies": ",".join(bodies),
            "involution.ephemeris": ephemeris
        }

        if ayanamsha:
            attributes["involution.ayanamsha"] = ayanamsha

        return self.trace_operation("positions_calculation", attributes)

    def trace_time_resolution(
        self,
        local_datetime: str,
        place_name: str,
        tzdb_version: str
    ):
        """
        Trace a time resolution operation.

        Args:
            local_datetime: Local datetime being resolved
            place_name: Place name or coordinates
            tzdb_version: TZDB version used

        Returns:
            Context manager for the trace span
        """
        attributes = {
            "involution.local_datetime": local_datetime,
            "involution.place": place_name,
            "involution.tzdb_version": tzdb_version
        }

        return self.trace_operation("time_resolution", attributes)

    def trace_geocoding(self, query: str, result_count: int):
        """
        Trace a geocoding operation.

        Args:
            query: Search query
            result_count: Number of results found

        Returns:
            Context manager for the trace span
        """
        attributes = {
            "involution.geocode_query": query,
            "involution.result_count": result_count
        }

        return self.trace_operation("geocoding_search", attributes)

    def trace_cache_operation(self, operation: str, cache_size: int, hit_rate: float):
        """
        Trace a cache operation.

        Args:
            operation: Cache operation (hit/miss/set/evict)
            cache_size: Current cache size
            hit_rate: Cache hit rate

        Returns:
            Context manager for the trace span
        """
        attributes = {
            "involution.cache_operation": operation,
            "involution.cache_size": cache_size,
            "involution.cache_hit_rate": hit_rate
        }

        return self.trace_operation("cache_operation", attributes)

    def add_span_attribute(self, key: str, value: Any):
        """
        Add attribute to current span if tracing is enabled.

        Args:
            key: Attribute key
            value: Attribute value
        """
        if not self.enabled or not TRACING_AVAILABLE:
            return

        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute(key, str(value))

    def record_exception(self, exception: Exception):
        """
        Record exception in current span if tracing is enabled.

        Args:
            exception: Exception to record
        """
        if not self.enabled or not TRACING_AVAILABLE:
            return

        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.record_exception(exception)
            current_span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))


# Global tracing manager instance
tracing = TracingManager()


def setup_tracing(config: Optional[TracingConfig] = None) -> bool:
    """
    Setup OpenTelemetry tracing with configuration.

    Args:
        config: Optional tracing configuration (uses env vars if not provided)

    Returns:
        True if tracing was successfully setup, False otherwise
    """
    if config is None:
        config = TracingConfig.from_env()

    return tracing.setup(config)


def instrument_fastapi_tracing(app) -> bool:
    """
    Instrument FastAPI application for automatic tracing.

    Args:
        app: FastAPI application instance

    Returns:
        True if instrumentation succeeded, False otherwise
    """
    return tracing.instrument_fastapi(app)


# Convenience functions for common tracing operations
def trace_positions(system: str, bodies: list, ephemeris: str, ayanamsha: Optional[str] = None):
    """Convenience function for tracing positions calculations."""
    return tracing.trace_positions_calculation(system, bodies, ephemeris, ayanamsha)


def trace_time_resolve(local_datetime: str, place_name: str, tzdb_version: str):
    """Convenience function for tracing time resolution."""
    return tracing.trace_time_resolution(local_datetime, place_name, tzdb_version)


def trace_geocode(query: str, result_count: int):
    """Convenience function for tracing geocoding."""
    return tracing.trace_geocoding(query, result_count)


def add_trace_attribute(key: str, value: Any):
    """Convenience function for adding span attributes."""
    tracing.add_span_attribute(key, value)


def record_trace_exception(exception: Exception):
    """Convenience function for recording exceptions."""
    tracing.record_exception(exception)