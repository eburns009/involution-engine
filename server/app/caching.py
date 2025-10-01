import time
import json
import hashlib
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Union
from functools import lru_cache


def normalize_request(obj: Any) -> str:
    """
    Create stable JSON representation for hashing.

    Args:
        obj: Object to normalize (typically a dict or list)

    Returns:
        Stable JSON string with sorted keys
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def etag_for(obj: Any) -> str:
    """
    Generate ETag hash for object.

    Args:
        obj: Object to generate ETag for

    Returns:
        16-character hex ETag
    """
    return hashlib.sha256(normalize_request(obj).encode()).hexdigest()[:16]


class InprocCache:
    """
    Thread-safe in-process LRU cache with TTL support.

    This cache stores response data in memory with automatic expiration
    and LRU eviction when the cache reaches its size limit.
    """

    def __init__(self, size: int, ttl: int):
        """
        Initialize cache.

        Args:
            size: Maximum number of entries
            ttl: Time-to-live in seconds
        """
        self.size = size
        self.ttl = ttl
        self.data: OrderedDict[str, tuple] = OrderedDict()  # key -> (expires, value)
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self.data.get(key)
            if entry is None:
                self._misses += 1
                return None

            expires, value = entry
            now = time.time()

            if expires < now:
                # Expired entry
                self.data.pop(key, None)
                self._misses += 1
                return None

            # Move to end (mark as recently used)
            self.data.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to store
        """
        with self._lock:
            expires = time.time() + self.ttl
            self.data[key] = (expires, value)

            # Move to end (mark as recently used)
            self.data.move_to_end(key)

            # Evict oldest entries if over size limit
            while len(self.data) > self.size:
                oldest_key = next(iter(self.data))
                self.data.pop(oldest_key)
                self._evictions += 1

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was present, False otherwise
        """
        with self._lock:
            return self.data.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self.data.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            now = time.time()
            expired_keys = []

            for key, (expires, _) in self.data.items():
                if expires < now:
                    expired_keys.append(key)

            for key in expired_keys:
                self.data.pop(key, None)

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / max(1, total_requests)) * 100

            return {
                "size": len(self.data),
                "max_size": self.size,
                "ttl_seconds": self.ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": hit_rate,
                "evictions": self._evictions,
                "total_requests": total_requests
            }

    def get_keys(self) -> list:
        """Get list of all cache keys."""
        with self._lock:
            return list(self.data.keys())


class CacheKey:
    """
    Helper class for generating consistent cache keys.
    """

    @staticmethod
    def for_positions(
        utc: str,
        system: str,
        ayanamsha: Optional[Dict[str, Any]],
        frame: str,
        epoch: str,
        bodies: list
    ) -> str:
        """
        Generate cache key for position calculation.

        Args:
            utc: UTC time string
            system: Zodiac system
            ayanamsha: Ayanāṃśa configuration
            frame: Reference frame
            epoch: Reference epoch
            bodies: List of celestial bodies

        Returns:
            Cache key string
        """
        key_data = {
            "type": "positions",
            "utc": utc,
            "system": system,
            "ayanamsha": ayanamsha,
            "frame": frame,
            "epoch": epoch,
            "bodies": sorted(bodies)  # Sort for consistency
        }
        return normalize_request(key_data)

    @staticmethod
    def for_time_resolution(
        local_datetime: str,
        place: Dict[str, Any],
        parity_profile: str
    ) -> str:
        """
        Generate cache key for time resolution.

        Args:
            local_datetime: Local datetime string
            place: Place information
            parity_profile: Parity profile

        Returns:
            Cache key string
        """
        key_data = {
            "type": "time_resolution",
            "local_datetime": local_datetime,
            "place": place,
            "parity_profile": parity_profile
        }
        return normalize_request(key_data)

    @staticmethod
    def for_geocoding(query: str, limit: int) -> str:
        """
        Generate cache key for geocoding search.

        Args:
            query: Search query
            limit: Result limit

        Returns:
            Cache key string
        """
        key_data = {
            "type": "geocoding",
            "query": query.strip().lower(),  # Normalize query
            "limit": limit
        }
        return normalize_request(key_data)


class CacheManager:
    """
    Manager for multiple cache instances.
    """

    def __init__(self):
        self._caches: Dict[str, InprocCache] = {}
        self._lock = threading.RLock()

    def create_cache(self, name: str, size: int, ttl: int) -> InprocCache:
        """
        Create a named cache instance.

        Args:
            name: Cache name
            size: Maximum size
            ttl: Time-to-live in seconds

        Returns:
            Cache instance
        """
        with self._lock:
            if name in self._caches:
                raise ValueError(f"Cache '{name}' already exists")

            cache = InprocCache(size, ttl)
            self._caches[name] = cache
            return cache

    def get_cache(self, name: str) -> Optional[InprocCache]:
        """
        Get cache by name.

        Args:
            name: Cache name

        Returns:
            Cache instance or None if not found
        """
        with self._lock:
            return self._caches.get(name)

    def delete_cache(self, name: str) -> bool:
        """
        Delete cache by name.

        Args:
            name: Cache name to delete

        Returns:
            True if cache was deleted, False if not found
        """
        with self._lock:
            if name in self._caches:
                self._caches[name].clear()
                del self._caches[name]
                return True
            return False

    def clear_all(self) -> None:
        """Clear all caches."""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()

    def cleanup_all_expired(self) -> Dict[str, int]:
        """
        Cleanup expired entries from all caches.

        Returns:
            Dict mapping cache names to number of expired entries removed
        """
        with self._lock:
            results = {}
            for name, cache in self._caches.items():
                results[name] = cache.cleanup_expired()
            return results

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all caches.

        Returns:
            Dict mapping cache names to their statistics
        """
        with self._lock:
            return {name: cache.get_stats() for name, cache in self._caches.items()}

    def get_cache_names(self) -> list:
        """Get list of all cache names."""
        with self._lock:
            return list(self._caches.keys())


class CacheDecorator:
    """
    Decorator for caching function results.
    """

    def __init__(self, cache: InprocCache, key_func: Optional[callable] = None):
        """
        Initialize cache decorator.

        Args:
            cache: Cache instance to use
            key_func: Function to generate cache key from arguments
        """
        self.cache = cache
        self.key_func = key_func or self._default_key_func

    def __call__(self, func):
        """Decorator wrapper."""
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self.key_func(*args, **kwargs)

            # Try to get from cache
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Not in cache, call function
            result = func(*args, **kwargs)

            # Store in cache
            self.cache.set(cache_key, result)

            return result

        wrapper.cache = self.cache
        wrapper.cache_key_func = self.key_func
        return wrapper

    def _default_key_func(self, *args, **kwargs) -> str:
        """Default key generation function."""
        key_data = {
            "args": args,
            "kwargs": kwargs
        }
        return normalize_request(key_data)


# Global cache manager instance
cache_manager = CacheManager()


# Utility functions for common caching patterns
def cached_positions_response(
    response_data: Dict[str, Any],
    cache: InprocCache,
    cache_key: str
) -> Dict[str, Any]:
    """
    Prepare and cache a positions response with ETag.

    Args:
        response_data: Response data to cache
        cache: Cache instance
        cache_key: Cache key

    Returns:
        Response data with ETag added
    """
    # Add ETag to response
    response_data["etag"] = etag_for(response_data)

    # Cache the response
    cache.set(cache_key, response_data)

    return response_data


def get_cached_response_with_etag(
    cache: InprocCache,
    cache_key: str
) -> Optional[Dict[str, Any]]:
    """
    Get cached response that includes ETag.

    Args:
        cache: Cache instance
        cache_key: Cache key

    Returns:
        Cached response with ETag or None if not found
    """
    cached = cache.get(cache_key)
    if cached and "etag" in cached:
        return cached
    return None