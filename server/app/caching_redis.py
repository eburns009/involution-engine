"""
Redis-based caching for the Involution Engine.

Provides distributed caching capabilities using Redis for multi-instance
deployments, with fallback to in-process caching.
"""

import json
import time
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis-based cache with JSON serialization.

    Provides distributed caching for position calculations and other
    expensive operations across multiple service instances.
    """

    def __init__(self, url: str, ttl: int, key_prefix: str = "involution"):
        """
        Initialize Redis cache.

        Args:
            url: Redis connection URL
            ttl: Default time-to-live in seconds
            key_prefix: Prefix for all cache keys
        """
        self.url = url
        self.ttl = ttl
        self.key_prefix = key_prefix
        self._redis = None
        self._connected = False
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0,
            "last_error": None
        }

        self._connect()

    def _connect(self) -> None:
        """Establish Redis connection."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available - install with: pip install redis")
            return

        try:
            self._redis = redis.Redis.from_url(self.url, decode_responses=True)
            # Test connection
            self._redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis cache: {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis cache: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            self._connected = False

    def _make_key(self, key: str) -> str:
        """Create full cache key with prefix."""
        return f"{self.key_prefix}:{key}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self._connected or not self._redis:
            self._stats["misses"] += 1
            return None

        try:
            full_key = self._make_key(key)
            data = self._redis.get(full_key)

            if data is None:
                self._stats["misses"] += 1
                return None

            value = json.loads(data)
            self._stats["hits"] += 1
            return value

        except Exception as e:
            logger.error(f"Redis cache get error: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            self._stats["misses"] += 1
            return None

    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self._redis:
            return False

        try:
            full_key = self._make_key(key)
            data = json.dumps(value, separators=(",", ":"))
            cache_ttl = ttl or self.ttl

            result = self._redis.setex(full_key, cache_ttl, data)
            if result:
                self._stats["sets"] += 1
            return bool(result)

        except Exception as e:
            logger.error(f"Redis cache set error: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return False

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self._redis:
            return False

        try:
            full_key = self._make_key(key)
            result = self._redis.delete(full_key)
            return bool(result)

        except Exception as e:
            logger.error(f"Redis cache delete error: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return False

    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern.

        Args:
            pattern: Pattern to match (supports * wildcards)

        Returns:
            Number of keys deleted
        """
        if not self._connected or not self._redis:
            return 0

        try:
            full_pattern = self._make_key(pattern)
            keys = self._redis.keys(full_pattern)
            if keys:
                return self._redis.delete(*keys)
            return 0

        except Exception as e:
            logger.error(f"Redis cache clear pattern error: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            "type": "redis",
            "connected": self._connected,
            "url": self.url,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "errors": self._stats["errors"],
            "hit_rate": hit_rate,
            "last_error": self._stats["last_error"]
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis connection.

        Returns:
            Dict with health status
        """
        if not self._connected or not self._redis:
            return {
                "healthy": False,
                "error": "Not connected to Redis"
            }

        try:
            # Test basic operations
            start_time = time.perf_counter()
            self._redis.ping()
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Test set/get operations
            test_key = self._make_key("health_check")
            test_value = {"timestamp": datetime.now(timezone.utc).isoformat()}

            self._redis.setex(test_key, 10, json.dumps(test_value))
            retrieved = self._redis.get(test_key)
            self._redis.delete(test_key)

            if retrieved:
                return {
                    "healthy": True,
                    "latency_ms": round(latency_ms, 2),
                    "operations": "ok"
                }
            else:
                return {
                    "healthy": False,
                    "error": "Set/get test failed"
                }

        except Exception as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return {
                "healthy": False,
                "error": str(e)
            }


class HybridCache:
    """
    Hybrid cache that combines Redis (L2) with in-process LRU (L1).

    Provides fast local access with distributed sharing across instances.
    """

    def __init__(self,
                 inproc_cache: 'InprocCache',
                 redis_cache: Optional[RedisCache] = None):
        """
        Initialize hybrid cache.

        Args:
            inproc_cache: In-process LRU cache (L1)
            redis_cache: Redis distributed cache (L2)
        """
        self.inproc = inproc_cache
        self.redis = redis_cache
        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "sets": 0
        }

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value from hybrid cache (L1 then L2).

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        # Try L1 cache first
        value = self.inproc.get(key)
        if value is not None:
            self._stats["l1_hits"] += 1
            return value

        # Try L2 cache (Redis)
        if self.redis:
            value = self.redis.get(key)
            if value is not None:
                # Populate L1 cache for future requests
                self.inproc.set(key, value)
                self._stats["l2_hits"] += 1
                return value

        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Set value in hybrid cache (both L1 and L2).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        # Set in L1 cache
        self.inproc.set(key, value)

        # Set in L2 cache if available
        if self.redis:
            self.redis.set(key, value, ttl)

        self._stats["sets"] += 1

    def delete(self, key: str) -> None:
        """
        Delete value from hybrid cache (both L1 and L2).

        Args:
            key: Cache key
        """
        self.inproc.delete(key)
        if self.redis:
            self.redis.delete(key)

    def clear(self) -> None:
        """Clear both L1 and L2 caches."""
        self.inproc.clear()
        if self.redis:
            self.redis.clear_pattern("*")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get hybrid cache statistics.

        Returns:
            Dict with cache statistics
        """
        total_requests = self._stats["l1_hits"] + self._stats["l2_hits"] + self._stats["misses"]
        l1_hit_rate = self._stats["l1_hits"] / total_requests if total_requests > 0 else 0.0
        l2_hit_rate = self._stats["l2_hits"] / total_requests if total_requests > 0 else 0.0
        total_hit_rate = (self._stats["l1_hits"] + self._stats["l2_hits"]) / total_requests if total_requests > 0 else 0.0

        stats = {
            "type": "hybrid",
            "l1_hits": self._stats["l1_hits"],
            "l2_hits": self._stats["l2_hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "l1_hit_rate": l1_hit_rate,
            "l2_hit_rate": l2_hit_rate,
            "total_hit_rate": total_hit_rate,
            "inproc": self.inproc.get_stats()
        }

        if self.redis:
            stats["redis"] = self.redis.get_stats()

        return stats

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on hybrid cache.

        Returns:
            Dict with health status
        """
        health = {
            "inproc": {"healthy": True}  # In-process cache is always healthy
        }

        if self.redis:
            health["redis"] = self.redis.health_check()

        return health