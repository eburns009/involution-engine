import pytest
import httpx
import os

BASE_URL = os.getenv("ENGINE_BASE", "http://localhost:8080")


class TestErrorMapper:
    """Tests for error mapping and friendly error responses."""

    @pytest.mark.asyncio
    async def test_out_of_range_date_error(self):
        """Test error for date outside ephemeris range."""
        payload = {
            "when": {"utc": "1400-01-01T00:00:00Z"},  # Before DE440 range
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()

        assert error_data["code"] == "RANGE.EPHEMERIS_OUTSIDE"
        assert error_data["title"] == "Date outside ephemeris range"
        assert "tip" in error_data
        assert "DE440" in error_data["detail"] or "supported date" in error_data["tip"].lower()

    @pytest.mark.asyncio
    async def test_invalid_input_structure(self):
        """Test error for invalid request structure."""
        payload = {
            "when": {},  # Missing required time info
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 422  # Pydantic validation error
        # The exact error structure may vary based on FastAPI version

    @pytest.mark.asyncio
    async def test_missing_required_field(self):
        """Test error for missing required fields."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical"
            # Missing 'bodies' field
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_unsupported_ayanamsha(self):
        """Test error for unsupported ayanāṃśa ID."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "sidereal",
            "ayanamsha": {"id": "NONEXISTENT_AYANAMSHA"},
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()

        assert error_data["code"] == "AYANAMSHA.UNSUPPORTED"
        assert "tip" in error_data
        assert "LAHIRI" in error_data["tip"] or "available" in error_data["tip"].lower()

    @pytest.mark.asyncio
    async def test_system_incompatibility_error(self):
        """Test error for incompatible system configuration."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "ayanamsha": {"id": "FAGAN_BRADLEY_DYNAMIC"},  # Should not be used with tropical
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()

        assert error_data["code"] == "SYSTEM.INCOMPATIBLE"
        assert "tropical" in error_data["detail"].lower() or "ayanamsa" in error_data["detail"].lower()

    @pytest.mark.asyncio
    async def test_unsupported_body_error(self):
        """Test error for unsupported celestial body."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun", "Chiron"]  # Chiron not in supported bodies
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()

        assert error_data["code"] == "BODIES.UNSUPPORTED"
        assert "tip" in error_data
        # Should list supported bodies in tip
        assert "Sun" in error_data["tip"] and "Moon" in error_data["tip"]

    @pytest.mark.asyncio
    async def test_invalid_place_for_local_time(self):
        """Test error when place is incomplete for local time."""
        payload = {
            "when": {
                "local_datetime": "1962-07-02T23:33:00",
                "place": {}  # Empty place object
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()

        assert error_data["code"] == "INPUT.INVALID"
        assert "place" in error_data["detail"].lower()

    @pytest.mark.asyncio
    async def test_geocoding_not_found(self):
        """Test geocoding error for location not found."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/v1/geocode/search",
                params={"q": "NONEXISTENT_LOCATION_12345", "limit": 5},
                timeout=10
            )

        # This may return 200 with empty results or 400 depending on implementation
        if response.status_code == 400:
            error_data = response.json()
            assert error_data["code"] == "GEOCODE.NOT_FOUND"

    @pytest.mark.asyncio
    async def test_empty_geocoding_query(self):
        """Test geocoding error for empty query."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/v1/geocode/search",
                params={"q": "", "limit": 5},
                timeout=10
            )

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INPUT.INVALID"

    @pytest.mark.asyncio
    async def test_error_response_structure(self):
        """Test that all error responses follow the expected structure."""
        # Generate a known error
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "sidereal",  # Missing ayanamsha
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()

        # Check error structure
        assert "code" in error_data
        assert "title" in error_data
        assert isinstance(error_data["code"], str)
        assert isinstance(error_data["title"], str)

        # Optional fields
        if "detail" in error_data:
            assert isinstance(error_data["detail"], str)
        if "tip" in error_data:
            assert isinstance(error_data["tip"], str)

        # Code should follow CATEGORY.SPECIFIC_ERROR pattern
        assert "." in error_data["code"]
        category, specific = error_data["code"].split(".", 1)
        assert len(category) > 0
        assert len(specific) > 0

    @pytest.mark.asyncio
    async def test_request_id_in_error_responses(self):
        """Test that error responses include request ID."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "sidereal",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        # Should have request ID header even for errors
        assert "x-request-id" in response.headers