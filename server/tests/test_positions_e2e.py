import pytest
import httpx
import os
import asyncio

BASE_URL = os.getenv("ENGINE_BASE", "http://localhost:8080")


class TestPositionsE2E:
    """End-to-end tests for the positions endpoint."""

    @pytest.mark.asyncio
    async def test_positions_fort_knox_1962_tropical(self):
        """Test Fort Knox 1962 tropical calculation (baseline test)."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "utc" in data
        assert "provenance" in data
        assert "bodies" in data
        assert "etag" in data

        # Check provenance
        provenance = data["provenance"]
        assert provenance["ephemeris"] in ("DE440", "DE441")
        assert provenance["kernels_bundle"] in ("de440-1900", "de440-full", "de440-modern")
        assert provenance["reference_frame"] == "ecliptic_of_date"
        assert provenance["epoch"] == "of_date"

        # Check bodies
        bodies = data["bodies"]
        assert len(bodies) == 7
        body_names = [b["name"] for b in bodies]
        assert "Sun" in body_names
        assert "Moon" in body_names

        # Validate Sun position (should be around 100° in tropical for Fort Knox 1962)
        sun_body = next(b for b in bodies if b["name"] == "Sun")
        assert 95 <= sun_body["lon_deg"] <= 105  # Approximate range

        # Check ETag header
        assert "etag" in response.headers

    @pytest.mark.asyncio
    async def test_positions_sidereal_requires_ayanamsha(self):
        """Test that sidereal system requires ayanāṃśa."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "sidereal",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "AYANAMSHA.REQUIRED"

    @pytest.mark.asyncio
    async def test_positions_sidereal_with_ayanamsha(self):
        """Test sidereal calculation with Fagan-Bradley ayanāṃśa."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "sidereal",
            "ayanamsha": {"id": "FAGAN_BRADLEY_DYNAMIC"},
            "bodies": ["Sun", "Moon"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Check ayanāṃśa info in provenance
        assert data["provenance"]["ayanamsha"] is not None
        assert data["provenance"]["ayanamsha"]["id"] == "FAGAN_BRADLEY_DYNAMIC"
        assert "value_deg" in data["provenance"]["ayanamsha"]

        # Sidereal positions should be ~24° less than tropical for this era
        sun_body = next(b for b in data["bodies"] if b["name"] == "Sun")
        assert 70 <= sun_body["lon_deg"] <= 80  # Approximate sidereal range

    @pytest.mark.asyncio
    async def test_positions_local_time_conversion(self):
        """Test local time to UTC conversion."""
        payload = {
            "when": {
                "local_datetime": "1962-07-02T23:33:00",
                "place": {
                    "name": "Fort Knox, Kentucky",
                    "lat": 37.840347,
                    "lon": -85.949127
                }
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Should convert to UTC (CST = UTC-6, so 23:33 + 6 = 04:33 next day)
        assert data["utc"] == "1962-07-03T04:33:00Z"

    @pytest.mark.asyncio
    async def test_positions_selectable_bodies(self):
        """Test that only requested bodies are returned."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun", "Mercury"]  # Only 2 bodies
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Should return exactly 2 bodies
        assert len(data["bodies"]) == 2
        body_names = [b["name"] for b in data["bodies"]]
        assert "Sun" in body_names
        assert "Mercury" in body_names
        assert "Moon" not in body_names

    @pytest.mark.asyncio
    async def test_positions_cache_etag_consistency(self):
        """Test that identical requests return identical ETags (cache working)."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun", "Moon"]
        }

        async with httpx.AsyncClient() as client:
            # First request
            response1 = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)
            assert response1.status_code == 200
            etag1 = response1.headers.get("etag")

            # Second identical request
            response2 = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)
            assert response2.status_code == 200
            etag2 = response2.headers.get("etag")

            # ETags should be identical
            assert etag1 == etag2
            assert etag1 is not None

    @pytest.mark.asyncio
    async def test_positions_invalid_body(self):
        """Test error handling for unsupported celestial body."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun", "Chiron"]  # Chiron not supported
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "BODIES.UNSUPPORTED"

    @pytest.mark.asyncio
    async def test_positions_tropical_with_ayanamsha_error(self):
        """Test error when ayanāṃśa is specified for tropical system."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "ayanamsha": {"id": "FAGAN_BRADLEY_DYNAMIC"},  # Invalid for tropical
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "SYSTEM.INCOMPATIBLE"

    @pytest.mark.asyncio
    async def test_positions_equatorial_frame(self):
        """Test equatorial coordinate frame calculation."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Should include RA/Dec for equatorial frame
        sun_body = next(b for b in data["bodies"] if b["name"] == "Sun")
        assert "ra_hours" in sun_body
        assert "dec_deg" in sun_body
        assert data["provenance"]["reference_frame"] == "equatorial"

    @pytest.mark.asyncio
    async def test_positions_performance(self):
        """Test that response time is under 200ms for typical calculation."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "TrueNode"]
        }

        import time
        start_time = time.perf_counter()

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        duration_ms = (time.perf_counter() - start_time) * 1000

        assert response.status_code == 200
        # Performance target: p95 < 200ms (allowing some tolerance for test env)
        assert duration_ms < 500  # Generous for test environment