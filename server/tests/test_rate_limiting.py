"""
Tests for Redis-based distributed rate limiting.

Tests token bucket rate limiting, Redis coordination,
and rate limit middleware functionality.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request
from fastapi.testclient import TestClient

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.ratelimit import (
    parse_limit, RedisRateLimiter, ip_key, user_key,
    create_rate_limit_response, RateLimitMiddleware
)


class TestParseLimit:
    """Tests for rate limit string parsing."""

    def test_parse_valid_limits(self):
        """Test parsing valid limit strings."""
        # Basic formats
        tokens, period = parse_limit("100/minute")
        assert tokens == 100
        assert period == 60

        tokens, period = parse_limit("500/hour")
        assert tokens == 500
        assert period == 3600

        tokens, period = parse_limit("10/second")
        assert tokens == 10
        assert period == 1

        tokens, period = parse_limit("1000/day")
        assert tokens == 1000
        assert period == 86400

    def test_parse_unit_variations(self):
        """Test parsing with different unit variations."""
        # Short forms
        tokens, period = parse_limit("50/min")
        assert tokens == 50
        assert period == 60

        tokens, period = parse_limit("10/sec")
        assert tokens == 10
        assert period == 1

        tokens, period = parse_limit("200/hr")
        assert tokens == 200
        assert period == 3600

        tokens, period = parse_limit("100/d")
        assert tokens == 100
        assert period == 86400

        # Single letters
        tokens, period = parse_limit("30/m")
        assert tokens == 30
        assert period == 60

        tokens, period = parse_limit("5/s")
        assert tokens == 5
        assert period == 1

        tokens, period = parse_limit("60/h")
        assert tokens == 60
        assert period == 3600

    def test_parse_case_insensitive(self):
        """Test case-insensitive parsing."""
        tokens, period = parse_limit("100/MINUTE")
        assert tokens == 100
        assert period == 60

        tokens, period = parse_limit("50/Hour")
        assert tokens == 50
        assert period == 3600

    def test_parse_with_whitespace(self):
        """Test parsing with extra whitespace."""
        tokens, period = parse_limit("100 / minute ")
        assert tokens == 100
        assert period == 60

        tokens, period = parse_limit(" 50/hour ")
        assert tokens == 50
        assert period == 3600

    def test_parse_invalid_formats(self):
        """Test error handling for invalid formats."""
        with pytest.raises(ValueError, match="Invalid limit format"):
            parse_limit("invalid")

        with pytest.raises(ValueError, match="Invalid limit format"):
            parse_limit("100")

        with pytest.raises(ValueError, match="Invalid limit format"):
            parse_limit("/minute")

        with pytest.raises(ValueError, match="Unknown time unit"):
            parse_limit("100/unknown")

    def test_parse_invalid_tokens(self):
        """Test error handling for invalid token counts."""
        with pytest.raises(ValueError, match="Token count must be positive"):
            parse_limit("0/minute")

        with pytest.raises(ValueError, match="Token count must be positive"):
            parse_limit("-10/minute")

        with pytest.raises(ValueError, match="Invalid limit format"):
            parse_limit("abc/minute")


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
class TestRedisRateLimiter:
    """Tests for Redis-based rate limiter."""

    def test_redis_unavailable_fail_open(self):
        """Test fail-open behavior when Redis is unavailable."""
        # Use bad Redis URL
        limiter = RedisRateLimiter("redis://localhost:99999", "10/minute")

        # Should allow request (fail open)
        allowed, remaining, info = limiter.allow("test_key")
        assert allowed is True
        assert remaining == 10
        assert info["limit"] == 10

        # Stats should show errors
        stats = limiter.get_stats()
        assert stats["connected"] is False
        assert stats["errors"] > 0

    @patch('redis.Redis.from_url')
    def test_redis_connection_success(self, mock_redis):
        """Test successful Redis connection."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        limiter = RedisRateLimiter("redis://localhost:6379/0", "10/minute")

        # Should be connected
        stats = limiter.get_stats()
        assert stats["connected"] is True

        mock_client.ping.assert_called()

    @patch('redis.Redis.from_url')
    def test_rate_limiting_logic(self, mock_redis):
        """Test core rate limiting logic."""
        mock_client = Mock()
        mock_client.ping.return_value = True

        # Mock pipeline operations
        mock_pipe = Mock()
        mock_pipe.execute.return_value = [1, True]  # First request
        mock_client.pipeline.return_value = mock_pipe

        mock_redis.return_value = mock_client

        limiter = RedisRateLimiter("redis://localhost:6379/0", "10/minute")

        # First request should be allowed
        allowed, remaining, info = limiter.allow("test_key")
        assert allowed is True
        assert remaining == 9  # 10 - 1
        assert info["limit"] == 10

        # Verify Redis operations
        mock_client.pipeline.assert_called()
        mock_pipe.incr.assert_called()
        mock_pipe.expire.assert_called()

    @patch('redis.Redis.from_url')
    def test_rate_limit_exceeded(self, mock_redis):
        """Test behavior when rate limit is exceeded."""
        mock_client = Mock()
        mock_client.ping.return_value = True

        # Mock pipeline operations - exceed limit
        mock_pipe = Mock()
        mock_pipe.execute.return_value = [11, True]  # Exceeds 10/minute
        mock_client.pipeline.return_value = mock_pipe

        mock_redis.return_value = mock_client

        limiter = RedisRateLimiter("redis://localhost:6379/0", "10/minute")

        # Request should be denied
        allowed, remaining, info = limiter.allow("test_key")
        assert allowed is False
        assert remaining == 0
        assert info["limit"] == 10

        # Check stats
        stats = limiter.get_stats()
        assert stats["denied"] == 1

    @patch('redis.Redis.from_url')
    def test_sliding_window_key_generation(self, mock_redis):
        """Test sliding window key generation."""
        mock_client = Mock()
        mock_client.ping.return_value = True

        mock_pipe = Mock()
        mock_pipe.execute.return_value = [1, True]
        mock_client.pipeline.return_value = mock_pipe

        mock_redis.return_value = mock_client

        limiter = RedisRateLimiter("redis://localhost:6379/0", "10/minute")

        # Mock time to specific value
        with patch('time.time', return_value=1609459200):  # 2021-01-01 00:00:00
            limiter.allow("test_key")

            # Check that key includes time window
            expected_window_start = 1609459200 - (1609459200 % 60)  # Minute boundary
            expected_key = f"rl:test_key:{expected_window_start}"

            mock_pipe.incr.assert_called_with(expected_key)
            mock_pipe.expire.assert_called_with(expected_key, 61)  # period + 1

    @patch('redis.Redis.from_url')
    def test_redis_error_fail_open(self, mock_redis):
        """Test fail-open behavior on Redis errors."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.pipeline.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        limiter = RedisRateLimiter("redis://localhost:6379/0", "10/minute")

        # Should allow request despite Redis error
        allowed, remaining, info = limiter.allow("test_key")
        assert allowed is True
        assert remaining == 10

        # Stats should show error
        stats = limiter.get_stats()
        assert stats["errors"] == 1

    def test_health_check_no_redis(self):
        """Test health check when Redis is unavailable."""
        limiter = RedisRateLimiter("redis://localhost:99999", "10/minute")

        health = limiter.health_check()
        assert health["healthy"] is False
        assert "error" in health

    @patch('redis.Redis.from_url')
    def test_health_check_with_redis(self, mock_redis):
        """Test health check with working Redis."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        limiter = RedisRateLimiter("redis://localhost:6379/0", "10/minute")

        # Mock timing for latency test
        with patch('time.perf_counter', side_effect=[0.0, 0.001]):  # 1ms latency
            health = limiter.health_check()

        assert health["healthy"] is True
        assert health["latency_ms"] == 1.0

    @patch('redis.Redis.from_url')
    def test_statistics_tracking(self, mock_redis):
        """Test statistics tracking."""
        mock_client = Mock()
        mock_client.ping.return_value = True

        # Mock multiple requests
        mock_pipe = Mock()
        mock_client.pipeline.return_value = mock_pipe

        mock_redis.return_value = mock_client

        limiter = RedisRateLimiter("redis://localhost:6379/0", "5/minute")

        # Simulate requests
        mock_pipe.execute.return_value = [1, True]  # Allowed
        limiter.allow("key1")

        mock_pipe.execute.return_value = [3, True]  # Allowed
        limiter.allow("key1")

        mock_pipe.execute.return_value = [6, True]  # Denied (exceeds 5)
        limiter.allow("key1")

        stats = limiter.get_stats()
        assert stats["requests"] == 3
        assert stats["allowed"] == 2
        assert stats["denied"] == 1
        assert stats["success_rate"] == 2.0 / 3.0


class TestKeyExtraction:
    """Tests for rate limiting key extraction."""

    def test_ip_key_direct_client(self):
        """Test IP extraction from direct client."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        key = ip_key(request)
        assert key == "192.168.1.100"

    def test_ip_key_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For header."""
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "203.0.113.195, 192.168.1.100"}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        key = ip_key(request)
        assert key == "203.0.113.195"  # First IP in chain

    def test_ip_key_real_ip(self):
        """Test IP extraction from X-Real-IP header."""
        request = Mock(spec=Request)
        request.headers = {"x-real-ip": "203.0.113.195"}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        key = ip_key(request)
        assert key == "203.0.113.195"

    def test_ip_key_forwarded_for_priority(self):
        """Test X-Forwarded-For takes priority over X-Real-IP."""
        request = Mock(spec=Request)
        request.headers = {
            "x-forwarded-for": "203.0.113.195",
            "x-real-ip": "198.51.100.5"
        }

        key = ip_key(request)
        assert key == "203.0.113.195"

    def test_ip_key_no_client(self):
        """Test fallback when no client information."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None

        key = ip_key(request)
        assert key == "unknown"

    def test_user_key_with_auth(self):
        """Test user key extraction with authorization header."""
        request = Mock(spec=Request)
        request.headers = {"authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9"}

        key = user_key(request)
        assert key.startswith("user:")
        assert "Bearer eyJ0eXAiOiJKV" in key

    def test_user_key_fallback_to_ip(self):
        """Test user key fallback to IP-based limiting."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        key = user_key(request)
        assert key == "ip:192.168.1.100"


class TestRateLimitResponse:
    """Tests for rate limit response creation."""

    def test_create_rate_limit_response(self):
        """Test rate limit response creation."""
        rate_limit_info = {
            "limit": 100,
            "remaining": 0,
            "period": 60,
            "reset_time": 1609459260
        }

        response = create_rate_limit_response(rate_limit_info, retry_after_seconds=60)

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert response.headers["X-RateLimit-Reset"] == "1609459260"

        # Check response body
        import json
        body = json.loads(response.body)
        assert body["code"] == "RATE.LIMITED"
        assert body["title"] == "Too many requests"
        assert "60 seconds" in body["tip"]

    def test_create_rate_limit_response_without_reset_time(self):
        """Test rate limit response without explicit reset time."""
        rate_limit_info = {
            "limit": 100,
            "remaining": 0,
            "period": 60
        }

        with patch('time.time', return_value=1609459200):
            response = create_rate_limit_response(rate_limit_info)

        # Should use current time + retry_after
        assert response.headers["X-RateLimit-Reset"] == "1609459260"  # 1609459200 + 60


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    @patch('app.ratelimit.RedisRateLimiter')
    def test_middleware_allow_request(self, mock_limiter_class):
        """Test middleware allowing request."""
        # Mock rate limiter
        mock_limiter = Mock()
        mock_limiter.allow.return_value = (True, 5, {"limit": 10, "remaining": 5})
        mock_limiter_class.return_value = mock_limiter

        middleware = RateLimitMiddleware(mock_limiter)

        # Mock request and response
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {}

        response = Mock()
        response.headers = {}

        async def call_next(req):
            return response

        # Test middleware
        import asyncio
        result = asyncio.run(middleware(request, call_next))

        # Should return original response with headers
        assert result == response
        assert result.headers["X-RateLimit-Limit"] == "10"
        assert result.headers["X-RateLimit-Remaining"] == "5"

        # Verify rate limiter was called
        mock_limiter.allow.assert_called_once_with("192.168.1.100")

    @patch('app.ratelimit.RedisRateLimiter')
    def test_middleware_deny_request(self, mock_limiter_class):
        """Test middleware denying request."""
        # Mock rate limiter returning denial
        mock_limiter = Mock()
        mock_limiter.allow.return_value = (False, 0, {"limit": 10, "remaining": 0, "period": 60})
        mock_limiter_class.return_value = mock_limiter

        middleware = RateLimitMiddleware(mock_limiter)

        # Mock request
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {}

        async def call_next(req):
            return Mock()  # Should not be called

        # Test middleware
        import asyncio
        result = asyncio.run(middleware(request, call_next))

        # Should return 429 response
        assert result.status_code == 429
        assert result.headers["X-RateLimit-Limit"] == "10"
        assert result.headers["X-RateLimit-Remaining"] == "0"

    @patch('app.ratelimit.RedisRateLimiter')
    def test_middleware_custom_key_extractor(self, mock_limiter_class):
        """Test middleware with custom key extractor."""
        mock_limiter = Mock()
        mock_limiter.allow.return_value = (True, 5, {"limit": 10, "remaining": 5})
        mock_limiter_class.return_value = mock_limiter

        # Custom key extractor
        def custom_key(request):
            return "custom_key"

        middleware = RateLimitMiddleware(mock_limiter, key_extractor=custom_key)

        # Mock request
        request = Mock(spec=Request)

        response = Mock()
        response.headers = {}

        async def call_next(req):
            return response

        # Test middleware
        import asyncio
        asyncio.run(middleware(request, call_next))

        # Verify custom key was used
        mock_limiter.allow.assert_called_once_with("custom_key")