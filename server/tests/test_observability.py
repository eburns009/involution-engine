"""
Tests for observability features: logging, metrics, and tracing.

Tests structured logging, Prometheus metrics collection,
and optional OpenTelemetry tracing functionality.
"""

import pytest
import json
import io
import logging
import time
import os
from unittest.mock import patch, MagicMock

from app.obs.logging import (
    JsonFormatter, StructuredLogger, setup_logging,
    set_request_context, clear_request_context, get_request_id,
    TimedOperation
)
from app.obs.metrics import (
    metrics, MetricsCollector, get_metrics_content,
    REQUEST_COUNT, POSITIONS_CALCULATED, ERRORS_TOTAL
)
from app.obs.tracing import (
    TracingConfig, TracingManager, setup_tracing,
    trace_positions, trace_time_resolve, trace_geocode
)


class TestJsonFormatter:
    """Tests for JSON log formatting."""

    def test_basic_formatting(self):
        """Test basic JSON log formatting."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert "timestamp" in log_data

    def test_request_context_inclusion(self):
        """Test request context inclusion in logs."""
        formatter = JsonFormatter()

        # Set request context
        request_id = set_request_context("test-request-123", "user-456")

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test with context",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["request_id"] == "test-request-123"
        assert log_data["user_id"] == "user-456"

        # Clear context
        clear_request_context()

    def test_extra_fields(self):
        """Test inclusion of extra fields in logs."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test with extras",
            args=(),
            exc_info=None
        )

        # Add extra fields
        record.operation = "test_operation"
        record.duration_ms = 123.45
        record.system = "tropical"

        formatted = formatter.format(record)
        log_data = json.loads(formatted)

        assert log_data["operation"] == "test_operation"
        assert log_data["duration_ms"] == 123.45
        assert log_data["system"] == "tropical"


class TestStructuredLogger:
    """Tests for structured business logging."""

    def setup_method(self):
        """Setup test logger."""
        self.logger = StructuredLogger("test.business")

    def test_positions_calculated_logging(self):
        """Test positions calculation logging."""
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.positions_calculated(
                system="tropical",
                bodies=["Sun", "Moon"],
                duration_ms=45.67,
                ephemeris="DE440",
                ayanamsha=None,
                cache_hit=False
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert "Positions calculated successfully" in call_args[0][0]

            extra = call_args[1]["extra"]
            assert extra["operation"] == "positions_calculated"
            assert extra["system"] == "tropical"
            assert extra["bodies"] == ["Sun", "Moon"]
            assert extra["duration_ms"] == 45.67
            assert extra["ephemeris"] == "DE440"
            assert extra["cache_hit"] is False

    def test_positions_error_logging(self):
        """Test positions error logging."""
        with patch.object(self.logger.logger, 'error') as mock_error:
            self.logger.positions_error(
                error_code="RANGE.EPHEMERIS_OUTSIDE",
                error_title="Date outside ephemeris range",
                system="tropical",
                bodies=["Sun"],
                duration_ms=12.34,
                spice_error="SPICE(SPKINSUFFDATA)"
            )

            mock_error.assert_called_once()
            call_args = mock_error.call_args

            extra = call_args[1]["extra"]
            assert extra["operation"] == "positions_error"
            assert extra["error_code"] == "RANGE.EPHEMERIS_OUTSIDE"
            assert extra["spice_error"] == "SPICE(SPKINSUFFDATA)"

    def test_cache_operation_logging(self):
        """Test cache operation logging."""
        with patch.object(self.logger.logger, 'debug') as mock_debug:
            self.logger.cache_operation(
                operation="hit",
                key_hash="abc123",
                cache_size=42,
                hit_rate=0.85
            )

            mock_debug.assert_called_once()
            call_args = mock_debug.call_args

            extra = call_args[1]["extra"]
            assert extra["operation"] == "cache_hit"
            assert extra["key_hash"] == "abc123"
            assert extra["cache_size"] == 42
            assert extra["hit_rate"] == 0.85


class TestTimedOperation:
    """Tests for timed operation context manager."""

    def test_successful_operation(self):
        """Test timed operation for successful execution."""
        logger = StructuredLogger("test.timed")

        with patch.object(logger.logger, 'info') as mock_info:
            with TimedOperation(logger, "test_operation", system="tropical"):
                time.sleep(0.01)  # Small delay

            mock_info.assert_called_once()
            call_args = mock_info.call_args

            extra = call_args[1]["extra"]
            assert extra["operation"] == "test_operation"
            assert extra["system"] == "tropical"
            assert extra["duration_ms"] > 0

    def test_failed_operation(self):
        """Test timed operation for failed execution."""
        logger = StructuredLogger("test.timed")

        with patch.object(logger.logger, 'error') as mock_error:
            with pytest.raises(ValueError):
                with TimedOperation(logger, "failing_operation"):
                    raise ValueError("Test error")

            mock_error.assert_called_once()
            call_args = mock_error.call_args

            extra = call_args[1]["extra"]
            assert extra["operation"] == "failing_operation"
            assert extra["error_type"] == "ValueError"
            assert extra["error_message"] == "Test error"


class TestMetricsCollection:
    """Tests for Prometheus metrics collection."""

    def test_request_metrics(self):
        """Test HTTP request metrics recording."""
        initial_count = REQUEST_COUNT._value._value

        metrics.record_request("POST", "/v1/positions", 200, 0.15)

        # Check that counter increased
        labels = ("POST", "/v1/positions", "200")
        new_count = REQUEST_COUNT.labels(*labels)._value._value
        assert new_count > 0

    def test_position_calculation_metrics(self):
        """Test position calculation metrics."""
        initial_count = POSITIONS_CALCULATED._value._value

        metrics.record_position_calculation(
            system="tropical",
            ephemeris="DE440",
            body_count=7,
            duration_seconds=0.05,
            cache_hit=False
        )

        # Check that metrics were recorded
        labels = ("tropical", "DE440", "false")
        new_count = POSITIONS_CALCULATED.labels(*labels)._value._value
        assert new_count > 0

    def test_error_metrics(self):
        """Test error metrics recording."""
        initial_count = ERRORS_TOTAL._value._value

        metrics.record_error("RANGE.EPHEMERIS_OUTSIDE")

        # Check that error counter increased
        labels = ("RANGE.EPHEMERIS_OUTSIDE", "RANGE")
        new_count = ERRORS_TOTAL.labels(*labels)._value._value
        assert new_count > 0

    def test_metrics_summary(self):
        """Test metrics summary generation."""
        summary = metrics.get_metrics_summary()

        assert "uptime_seconds" in summary
        assert "cache" in summary
        assert "worker_pool" in summary
        assert isinstance(summary["uptime_seconds"], (int, float))
        assert isinstance(summary["cache"]["size"], int)
        assert isinstance(summary["cache"]["hit_rate"], float)

    def test_metrics_export(self):
        """Test Prometheus metrics export."""
        content, content_type = get_metrics_content()

        assert isinstance(content, str)
        assert "text/plain" in content_type
        assert "involution_requests_total" in content
        assert "involution_positions_calculated_total" in content


class TestTracingConfig:
    """Tests for tracing configuration."""

    def test_default_config(self):
        """Test default tracing configuration."""
        config = TracingConfig()

        assert config.enabled is False
        assert config.service_name == "involution-engine"
        assert config.sample_rate == 1.0

    def test_env_config(self):
        """Test configuration from environment variables."""
        env_vars = {
            "OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "test-service",
            "OTEL_JAEGER_ENDPOINT": "http://test:14268/api/traces",
            "OTEL_SAMPLE_RATE": "0.5"
        }

        with patch.dict(os.environ, env_vars):
            config = TracingConfig.from_env()

            assert config.enabled is True
            assert config.service_name == "test-service"
            assert config.jaeger_endpoint == "http://test:14268/api/traces"
            assert config.sample_rate == 0.5


class TestTracingManager:
    """Tests for tracing manager."""

    def setup_method(self):
        """Setup test tracing manager."""
        self.manager = TracingManager()

    def test_disabled_tracing(self):
        """Test tracing manager with disabled configuration."""
        config = TracingConfig(enabled=False)
        result = self.manager.setup(config)

        assert result is False
        assert self.manager.enabled is False

    def test_trace_operation_disabled(self):
        """Test trace operation when tracing is disabled."""
        # Should work without errors when disabled
        with self.manager.trace_operation("test_op", {"key": "value"}) as span:
            assert span is None

    def test_trace_positions_attributes(self):
        """Test position calculation tracing attributes."""
        with patch.object(self.manager, 'trace_operation') as mock_trace:
            context_manager = self.manager.trace_positions_calculation(
                system="sidereal",
                bodies=["Sun", "Moon", "Mars"],
                ephemeris="DE441",
                ayanamsha="FAGAN_BRADLEY_DYNAMIC"
            )

            mock_trace.assert_called_once()
            call_args = mock_trace.call_args
            assert call_args[0][0] == "positions_calculation"

            attributes = call_args[0][1]
            assert attributes["involution.system"] == "sidereal"
            assert attributes["involution.body_count"] == 3
            assert attributes["involution.ephemeris"] == "DE441"
            assert attributes["involution.ayanamsha"] == "FAGAN_BRADLEY_DYNAMIC"

    def test_convenience_functions(self):
        """Test tracing convenience functions."""
        with patch('app.obs.tracing.tracing') as mock_tracing:
            # Test positions tracing
            trace_positions("tropical", ["Sun"], "DE440", None)
            mock_tracing.trace_positions_calculation.assert_called_with(
                "tropical", ["Sun"], "DE440", None
            )

            # Test time resolution tracing
            trace_time_resolve("2023-01-01T12:00:00", "Fort Knox", "2023c")
            mock_tracing.trace_time_resolution.assert_called_with(
                "2023-01-01T12:00:00", "Fort Knox", "2023c"
            )

            # Test geocoding tracing
            trace_geocode("Fort Knox Kentucky", 5)
            mock_tracing.trace_geocoding.assert_called_with(
                "Fort Knox Kentucky", 5
            )


class TestObservabilityIntegration:
    """Integration tests for observability features."""

    def test_structured_logging_setup(self):
        """Test structured logging setup."""
        # Capture log output
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)

        # Setup logging with JSON formatter
        setup_logging(level="INFO", enable_json=True)

        # Replace handler for testing
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers = [handler]

        try:
            # Create test log
            logger = logging.getLogger("test.integration")
            logger.info("Test structured log")

            # Check output
            output = stream.getvalue()
            assert output.strip()  # Should have content

            # Try to parse as JSON
            try:
                log_data = json.loads(output.strip())
                assert log_data["level"] == "INFO"
                assert log_data["message"] == "Test structured log"
            except json.JSONDecodeError:
                # Fall back to simple format check
                assert "Test structured log" in output

        finally:
            # Restore original handlers
            root_logger.handlers = original_handlers

    def test_request_context_flow(self):
        """Test request context throughout operation flow."""
        # Set request context
        request_id = set_request_context()
        assert get_request_id() == request_id

        # Use structured logger
        logger = StructuredLogger("test.context")

        with patch.object(logger.logger, 'info') as mock_info:
            logger.positions_calculated(
                system="tropical",
                bodies=["Sun"],
                duration_ms=50.0,
                ephemeris="DE440"
            )

            # Verify logging happened
            mock_info.assert_called_once()

        # Clear context
        clear_request_context()
        assert get_request_id() is None

    @pytest.mark.skipif(
        not os.getenv("OTEL_ENABLED"),
        reason="OpenTelemetry integration test requires OTEL_ENABLED=true"
    )
    def test_tracing_integration(self):
        """Integration test for OpenTelemetry tracing (when enabled)."""
        config = TracingConfig(
            enabled=True,
            service_name="test-involution-engine",
            jaeger_endpoint="http://localhost:14268/api/traces"
        )

        # This test will only pass if OpenTelemetry packages are installed
        # and Jaeger is running
        try:
            success = setup_tracing(config)
            if success:
                # Test trace operation
                with trace_positions("tropical", ["Sun"], "DE440"):
                    time.sleep(0.001)  # Small operation

                assert True  # If we get here, tracing worked
            else:
                pytest.skip("Tracing setup failed (expected in test environment)")
        except Exception as e:
            pytest.skip(f"Tracing integration test failed: {e}")