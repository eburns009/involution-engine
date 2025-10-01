"""
Tests for Redis cache implementation.

Tests Redis cache layer, hybrid caching strategy,
and cache key normalization functionality.
"""

import pytest
import time
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.caching_redis import RedisCache, HybridCache
from app.caching import InprocCache


class TestInprocCache:
    """Tests for in-process L1 cache."""

    def test_basic_operations(self):
        """Test basic cache set/get operations."""
        cache = InprocCache(size=100, ttl=60)

        # Test set and get
        cache.set("key1", {"data": "value1"})
        result = cache.get("key1")
        assert result == {"data": "value1"}

        # Test miss
        result = cache.get("nonexistent")
        assert result is None

    def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = InprocCache(size=100, ttl=1)

        # Set value with short TTL
        cache.set("key1", {"data": "value1"})
        assert cache.get("key1") == {"data": "value1"}

        # Sleep and verify expiration
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_max_size_limit(self):
        """Test LRU eviction at max size."""
        cache = InprocCache(size=2, ttl=60)

        # Fill cache to capacity
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})

        # Should have both
        assert cache.get("key1") == {"data": "value1"}
        assert cache.get("key2") == {"data": "value2"}

        # Add third item, should evict oldest
        cache.set("key3", {"data": "value3"})

        # key1 should be evicted
        assert cache.get("key1") is None
        assert cache.get("key2") == {"data": "value2"}
        assert cache.get("key3") == {"data": "value3"}

    def test_clear_operation(self):
        """Test cache clear operation."""
        cache = InprocCache(size=100, ttl=60)

        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})

        assert cache.get("key1") == {"data": "value1"}

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_stats(self):
        """Test cache statistics."""
        cache = InprocCache(size=100, ttl=60)

        # Initial stats
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0

        # Hit and miss
        cache.set("key1", {"data": "value1"})
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
class TestRedisCache:
    """Tests for Redis cache layer."""

    def test_redis_unavailable_graceful_degradation(self):
        """Test graceful degradation when Redis is unavailable."""
        # Test with bad Redis URL
        cache = RedisCache("redis://localhost:99999", ttl_seconds=60)

        # Should not raise exception
        result = cache.get("key1")
        assert result is None

        # Set should not raise exception
        cache.set("key1", {"data": "value1"})

        # Health check should report unhealthy
        health = cache.health_check()
        assert health["healthy"] is False

    @patch('redis.Redis.from_url')
    def test_redis_connection_success(self, mock_redis):
        """Test successful Redis connection."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        cache = RedisCache("redis://localhost:6379/0", ttl_seconds=60)

        # Should be connected
        health = cache.health_check()
        assert health["healthy"] is True

        mock_client.ping.assert_called()

    @patch('redis.Redis.from_url')
    def test_redis_operations(self, mock_redis):
        """Test Redis cache operations."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        cache = RedisCache("redis://localhost:6379/0", ttl_seconds=60)

        # Test set operation
        test_data = {"data": "value1"}
        cache.set("key1", test_data)

        mock_client.setex.assert_called_once()
        args = mock_client.setex.call_args
        assert args[0][0] == "key1"
        assert args[0][1] == 60  # TTL

        # Test get operation
        mock_client.get.return_value = b'{"data": "value1"}'
        result = cache.get("key1")

        assert result == test_data
        mock_client.get.assert_called_with("key1")

    @patch('redis.Redis.from_url')
    def test_redis_serialization_error(self, mock_redis):
        """Test handling of serialization errors."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        cache = RedisCache("redis://localhost:6379/0", ttl_seconds=60)

        # Test invalid JSON in Redis
        mock_client.get.return_value = b"invalid json"
        result = cache.get("key1")

        assert result is None  # Should handle gracefully

    @patch('redis.Redis.from_url')
    def test_redis_stats(self, mock_redis):
        """Test Redis cache statistics."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        cache = RedisCache("redis://localhost:6379/0", ttl_seconds=60)

        # Mock some operations
        cache.get("key1")  # Miss
        mock_client.get.return_value = b'{"data": "value1"}'
        cache.get("key1")  # Hit

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["connected"] is True


class TestHybridCache:
    """Tests for hybrid caching strategy."""

    def test_hybrid_l1_hit(self):
        """Test L1 cache hit in hybrid cache."""
        inproc = InprocCache(size=100, ttl=60)
        redis_cache = None  # No Redis

        hybrid = HybridCache(inproc, redis_cache)

        # Set in L1
        inproc.set("key1", {"data": "value1"})

        # Should hit L1
        result = hybrid.get("key1")
        assert result == {"data": "value1"}

    @patch('app.caching_redis.RedisCache')
    def test_hybrid_l2_hit(self, mock_redis_class):
        """Test L2 cache hit with L1 population."""
        inproc = InprocCache(size=100, ttl=60)

        # Mock Redis cache
        mock_redis = Mock()
        mock_redis.get.return_value = {"data": "value1"}
        mock_redis_class.return_value = mock_redis

        hybrid = HybridCache(inproc, mock_redis)

        # Should hit L2 and populate L1
        result = hybrid.get("key1")
        assert result == {"data": "value1"}

        # Verify L1 was populated
        assert inproc.get("key1") == {"data": "value1"}

    @patch('app.caching_redis.RedisCache')
    def test_hybrid_set_both_layers(self, mock_redis_class):
        """Test setting value in both cache layers."""
        inproc = InprocCache(size=100, ttl=60)

        # Mock Redis cache
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis

        hybrid = HybridCache(inproc, mock_redis)

        # Set value
        test_data = {"data": "value1"}
        hybrid.set("key1", test_data)

        # Should be in L1
        assert inproc.get("key1") == test_data

        # Should call L2 set
        mock_redis.set.assert_called_once_with("key1", test_data)

    def test_hybrid_no_redis(self):
        """Test hybrid cache with no Redis backend."""
        inproc = InprocCache(size=100, ttl=60)
        hybrid = HybridCache(inproc, None)

        # Should work with L1 only
        hybrid.set("key1", {"data": "value1"})
        result = hybrid.get("key1")
        assert result == {"data": "value1"}

    @patch('app.caching_redis.RedisCache')
    def test_hybrid_clear_both_layers(self, mock_redis_class):
        """Test clearing both cache layers."""
        inproc = InprocCache(size=100, ttl=60)

        # Mock Redis cache
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis

        hybrid = HybridCache(inproc, mock_redis)

        # Set values
        hybrid.set("key1", {"data": "value1"})

        # Clear
        hybrid.clear()

        # L1 should be empty
        assert inproc.get("key1") is None

        # L2 clear should be called
        mock_redis.clear.assert_called_once()

    @patch('app.caching_redis.RedisCache')
    def test_hybrid_stats_combination(self, mock_redis_class):
        """Test combined statistics from both layers."""
        inproc = InprocCache(size=100, ttl=60)

        # Mock Redis cache with stats
        mock_redis = Mock()
        mock_redis.get_stats.return_value = {
            "hits": 5,
            "misses": 3,
            "connected": True
        }
        mock_redis_class.return_value = mock_redis

        hybrid = HybridCache(inproc, mock_redis)

        # Generate some L1 stats
        hybrid.set("key1", {"data": "value1"})
        hybrid.get("key1")  # L1 hit
        hybrid.get("key2")  # L1 miss

        stats = hybrid.get_stats()

        # Should combine stats
        assert "l1" in stats
        assert "l2" in stats
        assert stats["l1"]["hits"] == 1
        assert stats["l1"]["misses"] == 1
        assert stats["l2"]["hits"] == 5
        assert stats["l2"]["misses"] == 3

    @patch('app.caching_redis.RedisCache')
    def test_hybrid_health_check(self, mock_redis_class):
        """Test hybrid cache health check."""
        inproc = InprocCache(size=100, ttl=60)

        # Mock Redis cache with health check
        mock_redis = Mock()
        mock_redis.health_check.return_value = {
            "healthy": True,
            "latency_ms": 1.5
        }
        mock_redis_class.return_value = mock_redis

        hybrid = HybridCache(inproc, mock_redis)

        health = hybrid.health_check()

        assert health["l1"]["healthy"] is True
        assert health["l2"]["healthy"] is True
        assert health["l2"]["latency_ms"] == 1.5