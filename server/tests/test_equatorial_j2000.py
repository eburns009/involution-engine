"""
Tests for equatorial/J2000 coordinate output.

Tests the enhanced coordinate system support including
equatorial coordinates (RA/Dec) in J2000 epoch.
"""

import pytest
import httpx
import os

BASE_URL = os.getenv("ENGINE_BASE", "http://localhost:8080")


class TestEquatorialJ2000:
    """Tests for equatorial coordinate system with J2000 epoch."""

    @pytest.mark.asyncio
    async def test_equatorial_j2000_request(self):
        """Test requesting equatorial coordinates with J2000 epoch."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun", "Moon"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "bodies" in data
        assert len(data["bodies"]) == 2

        # Check that RA/Dec are included
        for body in data["bodies"]:
            assert "ra_hours" in body
            assert "dec_deg" in body
            # Ecliptic coordinates should also be present for compatibility
            assert "lon_deg" in body
            assert "lat_deg" in body

    @pytest.mark.asyncio
    async def test_ra_dec_value_ranges(self):
        """Test that RA/Dec values are in valid ranges."""
        payload = {
            "when": {"utc": "2023-01-01T12:00:00Z"},
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        for body in data["bodies"]:
            ra_hours = body["ra_hours"]
            dec_deg = body["dec_deg"]

            # RA should be 0-24 hours
            assert 0.0 <= ra_hours < 24.0

            # Dec should be -90 to +90 degrees
            assert -90.0 <= dec_deg <= 90.0

    @pytest.mark.asyncio
    async def test_equatorial_vs_ecliptic_coordinates(self):
        """Test that equatorial and ecliptic coordinates are different."""
        payload = {
            "when": {"utc": "2023-06-21T12:00:00Z"},  # Summer solstice
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        sun = data["bodies"][0]
        assert sun["name"] == "Sun"

        # Coordinates should be different (except at special points)
        ra_hours = sun["ra_hours"]
        dec_deg = sun["dec_deg"]
        lon_deg = sun["lon_deg"]
        lat_deg = sun["lat_deg"]

        # RA in degrees would be ra_hours * 15
        ra_deg = ra_hours * 15

        # They should generally be different values
        # (unless we're at a special coordinate system intersection)
        assert ra_deg != lon_deg or dec_deg != lat_deg

    @pytest.mark.asyncio
    async def test_ecliptic_of_date_still_works(self):
        """Test that default ecliptic of date still works."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "frame": {"type": "ecliptic_of_date"},
            "epoch": "of_date",
            "bodies": ["Sun", "Moon"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Should have ecliptic coordinates
        for body in data["bodies"]:
            assert "lon_deg" in body
            assert "lat_deg" in body
            # Should NOT have RA/Dec for ecliptic frame
            assert body.get("ra_hours") is None
            assert body.get("dec_deg") is None

    @pytest.mark.asyncio
    async def test_invalid_frame_epoch_combination(self):
        """Test error for invalid frame/epoch combinations."""
        # Equatorial frame with of_date epoch (not supported in Phase 2)
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "of_date",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INPUT.INVALID"
        assert "Equatorial frame requires J2000 epoch" in error_data["detail"]

    @pytest.mark.asyncio
    async def test_ecliptic_with_j2000_epoch_error(self):
        """Test error for ecliptic frame with J2000 epoch."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "frame": {"type": "ecliptic_of_date"},
            "epoch": "J2000",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INPUT.INVALID"
        assert "Ecliptic of date frame requires of_date epoch" in error_data["detail"]

    @pytest.mark.asyncio
    async def test_sidereal_equatorial_j2000(self):
        """Test sidereal system with equatorial/J2000."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "sidereal",
            "ayanamsha": {"id": "lahiri"},
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        sun = data["bodies"][0]
        assert "ra_hours" in sun
        assert "dec_deg" in sun
        assert "lon_deg" in sun  # Sidereal longitude
        assert "lat_deg" in sun

        # Should have ayanāṃśa information
        assert "ayanamsha" in data["provenance"]
        assert data["provenance"]["ayanamsha"]["id"] == "lahiri"

    @pytest.mark.asyncio
    async def test_coordinate_precision(self):
        """Test coordinate precision and reasonable values."""
        payload = {
            "when": {"utc": "2000-01-01T12:00:00Z"},  # J2000 epoch
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        sun = data["bodies"][0]
        ra_hours = sun["ra_hours"]
        dec_deg = sun["dec_deg"]

        # At J2000.0, Sun should be near winter solstice
        # RA around 18-19 hours, Dec around -23 degrees
        assert 17.0 < ra_hours < 20.0
        assert -25.0 < dec_deg < -20.0

    @pytest.mark.asyncio
    async def test_all_bodies_equatorial(self):
        """Test all supported bodies with equatorial coordinates."""
        payload = {
            "when": {"utc": "2023-01-01T00:00:00Z"},
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": [
                "Sun", "Moon", "Mercury", "Venus", "Mars",
                "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=15)

        assert response.status_code == 200
        data = response.json()

        assert len(data["bodies"]) == 10

        for body in data["bodies"]:
            # All bodies should have both coordinate systems
            assert "ra_hours" in body
            assert "dec_deg" in body
            assert "lon_deg" in body
            assert "lat_deg" in body

            # Validate ranges
            assert 0.0 <= body["ra_hours"] < 24.0
            assert -90.0 <= body["dec_deg"] <= 90.0
            assert 0.0 <= body["lon_deg"] < 360.0
            assert -90.0 <= body["lat_deg"] <= 90.0

    @pytest.mark.asyncio
    async def test_provenance_frame_epoch_info(self):
        """Test that provenance includes frame and epoch information."""
        payload = {
            "when": {"utc": "2023-01-01T12:00:00Z"},
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200
        data = response.json()

        provenance = data["provenance"]
        assert provenance["reference_frame"] == "equatorial"
        assert provenance["epoch"] == "J2000"

    @pytest.mark.asyncio
    async def test_caching_with_frame_epoch(self):
        """Test that caching works correctly with frame/epoch variations."""
        base_payload = {
            "when": {"utc": "2023-01-01T12:00:00Z"},
            "system": "tropical",
            "bodies": ["Sun"]
        }

        # First request - ecliptic/of_date
        payload1 = {**base_payload, "frame": {"type": "ecliptic_of_date"}, "epoch": "of_date"}

        async with httpx.AsyncClient() as client:
            response1 = await client.post(f"{BASE_URL}/v1/positions", json=payload1, timeout=10)

        assert response1.status_code == 200
        etag1 = response1.headers.get("etag")

        # Second request - equatorial/J2000
        payload2 = {**base_payload, "frame": {"type": "equatorial"}, "epoch": "J2000"}

        async with httpx.AsyncClient() as client:
            response2 = await client.post(f"{BASE_URL}/v1/positions", json=payload2, timeout=10)

        assert response2.status_code == 200
        etag2 = response2.headers.get("etag")

        # Should have different ETags (different cache keys)
        assert etag1 != etag2

        # Different coordinate values
        data1 = response1.json()
        data2 = response2.json()

        sun1 = data1["bodies"][0]
        sun2 = data2["bodies"][0]

        # First has only ecliptic
        assert "ra_hours" not in sun1 or sun1["ra_hours"] is None
        assert "lon_deg" in sun1

        # Second has both
        assert "ra_hours" in sun2
        assert "lon_deg" in sun2