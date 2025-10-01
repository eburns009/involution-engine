import pytest
import httpx
import os

BASE_URL = os.getenv("ENGINE_BASE", "http://localhost:8080")


class TestHealthz:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_healthz_basic(self):
        """Test basic health check functionality."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "status" in data
        assert "kernels" in data
        assert "cache" in data
        assert "pool" in data
        assert "ephemeris" in data
        assert "time" in data

        # Status should be healthy or degraded
        assert data["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_healthz_kernels_status(self):
        """Test kernels status in health check."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200
        data = response.json()

        kernels = data["kernels"]
        assert "bundle" in kernels
        assert "ok" in kernels
        assert isinstance(kernels["ok"], bool)

        # Bundle should be one of the supported types
        assert kernels["bundle"] in ["de440-full", "de440-1900", "de440-modern"]

    @pytest.mark.asyncio
    async def test_healthz_cache_status(self):
        """Test cache status in health check."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200
        data = response.json()

        cache = data["cache"]
        assert "size" in cache or "entries" in cache  # Different implementations
        assert "hit_rate_percent" in cache or "hits" in cache

    @pytest.mark.asyncio
    async def test_healthz_pool_status(self):
        """Test worker pool status in health check."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200
        data = response.json()

        pool = data["pool"]
        assert "size" in pool
        assert "queue_depth" in pool
        assert isinstance(pool["size"], int)
        assert isinstance(pool["queue_depth"], int)
        assert pool["size"] > 0  # Should have at least 1 worker

    @pytest.mark.asyncio
    async def test_healthz_ephemeris_policy(self):
        """Test ephemeris policy information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200
        data = response.json()

        ephemeris = data["ephemeris"]
        assert "policy" in ephemeris

        # Policy should be auto, de440, or de441
        assert ephemeris["policy"] in ["auto", "de440", "de441"]

        if ephemeris["policy"] == "auto":
            assert "de440_range" in ephemeris

    @pytest.mark.asyncio
    async def test_healthz_time_info(self):
        """Test time resolver information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200
        data = response.json()

        time_info = data["time"]
        assert "tzdb_version" in time_info
        assert "parity_profile_default" in time_info

        # TZDB version should be a reasonable format
        assert isinstance(time_info["tzdb_version"], str)
        assert len(time_info["tzdb_version"]) > 0

    @pytest.mark.asyncio
    async def test_healthz_headers(self):
        """Test health check response headers."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200

        # Should have request ID header
        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) > 0

        # Should have cache control header
        assert "cache-control" in response.headers

    @pytest.mark.asyncio
    async def test_healthz_response_time(self):
        """Test that health check responds quickly."""
        import time

        start_time = time.perf_counter()

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=5)

        duration_ms = (time.perf_counter() - start_time) * 1000

        assert response.status_code == 200
        # Health check should be very fast
        assert duration_ms < 1000  # Under 1 second

    @pytest.mark.asyncio
    async def test_healthz_service_degraded_conditions(self):
        """Test health check under potentially degraded conditions."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        # Should always respond (even if degraded)
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]

        elif response.status_code == 503:
            data = response.json()
            assert data["status"] in ["unhealthy", "starting"]