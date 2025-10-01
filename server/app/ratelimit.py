"""
Redis-based distributed rate limiting for the Involution Engine.

Provides token bucket rate limiting shared across multiple service instances
using Redis as the coordination backend.
"""

import time
import math
import logging
from typing import Tuple, Optional, Dict, Any
from fastapi import Request
from starlette.responses import JSONResponse

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from .errors import bad_request

logger = logging.getLogger(__name__)


def parse_limit(limit_str: str) -> Tuple[int, int]:
    """
    Parse limit string into tokens and period.

    Args:
        limit_str: Limit string like "200/minute" or "1000/hour"

    Returns:
        Tuple of (tokens, period_seconds)

    Raises:
        ValueError: If limit string is invalid
    """
    try:
        tokens_str, unit = limit_str.split("/", 1)
        tokens = int(tokens_str)

        unit = unit.lower().strip()
        if unit in ["second", "sec", "s"]:
            period = 1
        elif unit in ["minute", "min", "m"]:
            period = 60
        elif unit in ["hour", "hr", "h"]:
            period = 3600
        elif unit in ["day", "d"]:
            period = 86400
        else:
            raise ValueError(f"Unknown time unit: {unit}")

        if tokens <= 0:
            raise ValueError("Token count must be positive")

        return tokens, period

    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid limit format '{limit_str}': {e}")


class RedisRateLimiter:
    """
    Redis-based token bucket rate limiter.

    Implements distributed rate limiting using Redis atomic operations
    to ensure consistent behavior across multiple service instances.
    """

    def __init__(self, redis_url: str, limit: str, key_prefix: str = "rl"):
        """
        Initialize Redis rate limiter.

        Args:
            redis_url: Redis connection URL
            limit: Rate limit string (e.g., "200/minute")
            key_prefix: Prefix for Redis keys
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.tokens, self.period = parse_limit(limit)
        self._redis = None
        self._connected = False
        self._stats = {
            "requests": 0,
            "allowed": 0,
            "denied": 0,
            "errors": 0
        }

        self._connect()

    def _connect(self) -> None:
        """Establish Redis connection."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available for rate limiting - install with: pip install redis")
            return

        try:
            self._redis = redis.Redis.from_url(self.redis_url, decode_responses=False)
            # Test connection
            self._redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis rate limiter: {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis rate limiter: {e}")
            self._connected = False

    def allow(self, key: str) -> Tuple[bool, int, Dict[str, Any]]:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Unique identifier for rate limiting (e.g., IP address)

        Returns:
            Tuple of (allowed, remaining_tokens, rate_limit_info)
        """
        self._stats["requests"] += 1

        if not self._connected or not self._redis:
            # Fail open - allow request if Redis is unavailable
            logger.warning("Redis unavailable, allowing request (fail-open)")
            self._stats["errors"] += 1
            return True, self.tokens, self._get_rate_limit_info(self.tokens)

        try:
            # Use Redis time-window approach with sliding window
            now = int(time.time())
            window_start = now - (now % self.period)
            bucket_key = f"{self.key_prefix}:{key}:{window_start}"

            # Use Redis pipeline for atomic operations
            pipe = self._redis.pipeline()
            pipe.incr(bucket_key)
            pipe.expire(bucket_key, self.period + 1)  # Cleanup old keys
            results = pipe.execute()

            current_count = results[0]
            remaining = max(self.tokens - current_count, 0)
            allowed = current_count <= self.tokens

            if allowed:
                self._stats["allowed"] += 1
            else:
                self._stats["denied"] += 1

            rate_limit_info = self._get_rate_limit_info(remaining, window_start + self.period)

            return allowed, remaining, rate_limit_info

        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            self._stats["errors"] += 1
            # Fail open - allow request if Redis operation fails
            return True, self.tokens, self._get_rate_limit_info(self.tokens)

    def _get_rate_limit_info(self, remaining: int, reset_time: Optional[int] = None) -> Dict[str, Any]:
        """Get rate limit information for headers."""
        info = {
            "limit": self.tokens,
            "remaining": remaining,
            "period": self.period
        }

        if reset_time:
            info["reset_time"] = reset_time

        return info

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        success_rate = self._stats["allowed"] / max(self._stats["requests"], 1)

        return {
            "connected": self._connected,
            "redis_url": self.redis_url,
            "limit": f"{self.tokens}/{self.period}s",
            "requests": self._stats["requests"],
            "allowed": self._stats["allowed"],
            "denied": self._stats["denied"],
            "errors": self._stats["errors"],
            "success_rate": success_rate
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on rate limiter."""
        if not self._connected or not self._redis:
            return {
                "healthy": False,
                "error": "Not connected to Redis"
            }

        try:
            start_time = time.perf_counter()
            self._redis.ping()
            latency_ms = (time.perf_counter() - start_time) * 1000

            return {
                "healthy": True,
                "latency_ms": round(latency_ms, 2)
            }

        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }


def ip_key(request: Request) -> str:
    """
    Extract IP address for rate limiting key.

    Args:
        request: FastAPI request object

    Returns:
        IP address string
    """
    # Check for forwarded IP headers (proxy/load balancer)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP if there are multiple
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"


def user_key(request: Request) -> str:
    """
    Extract user identifier for rate limiting key.

    Args:
        request: FastAPI request object

    Returns:
        User identifier string
    """
    # Extract from authorization header, API key, etc.
    auth_header = request.headers.get("authorization")
    if auth_header:
        # Simple extraction - in production, decode JWT or API key
        return f"user:{auth_header[:20]}"

    # Fallback to IP-based limiting
    return f"ip:{ip_key(request)}"


def create_rate_limit_response(
    rate_limit_info: Dict[str, Any],
    retry_after_seconds: int = 60
) -> JSONResponse:
    """
    Create rate limit exceeded response.

    Args:
        rate_limit_info: Rate limit information
        retry_after_seconds: Seconds to wait before retrying

    Returns:
        JSONResponse with 429 status
    """
    headers = {
        "Retry-After": str(retry_after_seconds),
        "X-RateLimit-Limit": str(rate_limit_info["limit"]),
        "X-RateLimit-Remaining": str(rate_limit_info["remaining"]),
        "X-RateLimit-Reset": str(rate_limit_info.get("reset_time", int(time.time()) + retry_after_seconds))
    }

    return JSONResponse(
        status_code=429,
        content={
            "code": "RATE.LIMITED",
            "title": "Too many requests",
            "detail": "Per-IP rate limit exceeded.",
            "tip": f"Retry after {retry_after_seconds} seconds. "
                   f"Limit: {rate_limit_info['limit']} requests per {rate_limit_info['period']} seconds."
        },
        headers=headers
    )


class RateLimitMiddleware:
    """
    Middleware for automatic rate limiting.

    Applies rate limiting to all requests using configurable key extraction
    and limit rules.
    """

    def __init__(self, rate_limiter: RedisRateLimiter, key_extractor=ip_key):
        """
        Initialize rate limit middleware.

        Args:
            rate_limiter: Redis rate limiter instance
            key_extractor: Function to extract rate limiting key from request
        """
        self.rate_limiter = rate_limiter
        self.key_extractor = key_extractor

    async def __call__(self, request: Request, call_next):
        """Apply rate limiting to request."""
        # Extract rate limiting key
        key = self.key_extractor(request)

        # Check rate limit
        allowed, remaining, rate_limit_info = self.rate_limiter.allow(key)

        if not allowed:
            # Return rate limit exceeded response
            return create_rate_limit_response(rate_limit_info)

        # Add rate limit headers to successful responses
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        if "reset_time" in rate_limit_info:
            response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset_time"])

        return response


def setup_rate_limiting(app, config) -> Optional[RedisRateLimiter]:
    """
    Setup rate limiting for FastAPI application.

    Args:
        app: FastAPI application
        config: Rate limiting configuration

    Returns:
        Rate limiter instance if enabled, None otherwise
    """
    if not config.enabled:
        logger.info("Rate limiting disabled")
        return None

    try:
        # Use first rule for now (could be extended to multiple rules)
        rule = config.rules[0] if config.rules else None
        if not rule:
            logger.warning("No rate limit rules configured")
            return None

        rate_limiter = RedisRateLimiter(config.redis_url, rule.limit)

        # Add middleware
        middleware = RateLimitMiddleware(rate_limiter)
        app.middleware("http")(middleware)

        logger.info(f"Rate limiting enabled: {rule.limit} per {rule.key}")
        return rate_limiter

    except Exception as e:
        logger.error(f"Failed to setup rate limiting: {e}")
        return None