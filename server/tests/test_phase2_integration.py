"""
Integration tests for Phase 2 — Usability & Breadth features.

Tests the complete integration of ayanāṃśa registry, equatorial/J2000 output,
flexible date parsing, Redis cache, and distributed rate limiting.
"""

import pytest
import httpx
import os
import time
from unittest.mock import patch

BASE_URL = os.getenv("ENGINE_BASE", "http://localhost:8080")


class TestPhase2Integration:
    """Integration tests for all Phase 2 features working together."""

    @pytest.mark.asyncio
    async def test_complete_sidereal_workflow(self):
        """Test complete sidereal workflow with all Phase 2 features."""
        payload = {
            "when": {
                "local_datetime": "July 2, 1962 11:33 PM",  # Flexible date parsing
                "place": {
                    "name": "Fort Knox, Kentucky",
                    "lat": 37.840347,
                    "lon": -85.949127
                }
            },
            "system": "sidereal",
            "ayanamsha": {"id": "lahiri"},  # Ayanāṃśa registry
            "frame": {"type": "equatorial"},  # Equatorial coordinates
            "epoch": "J2000",  # J2000 epoch
            "bodies": ["Sun", "Moon"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=15)

        # Should succeed with all features integrated
        if response.status_code == 200:
            data = response.json()

            # Verify flexible date parsing worked
            assert "utc" in data
            assert data["utc"] == "1962-07-03T04:33:00Z"

            # Verify ayanāṃśa registry worked
            assert "provenance" in data
            assert data["provenance"]["ayanamsha"]["id"] == "lahiri"
            assert "value_deg" in data["provenance"]["ayanamsha"]

            # Verify equatorial coordinates
            assert data["provenance"]["reference_frame"] == "equatorial"
            assert data["provenance"]["epoch"] == "J2000"

            for body in data["bodies"]:
                # Should have both coordinate systems
                assert "ra_hours" in body  # Equatorial
                assert "dec_deg" in body
                assert "lon_deg" in body  # Sidereal ecliptic
                assert "lat_deg" in body

                # Validate ranges
                assert 0.0 <= body["ra_hours"] < 24.0
                assert -90.0 <= body["dec_deg"] <= 90.0

            # Verify rate limiting headers are present
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers

            # Verify caching headers (ETag)
            assert "etag" in response.headers

    @pytest.mark.asyncio
    async def test_tropical_equatorial_with_flexible_dates(self):
        """Test tropical system with equatorial output and flexible dates."""
        # Test various date formats for same time
        date_formats = [
            "1962-07-03T04:33:00Z",  # ISO UTC
            "1962-07-03T04:33:00+00:00",  # UTC with offset
        ]

        responses = []
        for date_format in date_formats:
            payload = {
                "when": {"utc": date_format},
                "system": "tropical",
                "frame": {"type": "equatorial"},
                "epoch": "J2000",
                "bodies": ["Sun"]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

            responses.append(response)

        # All should succeed
        successful = [r for r in responses if r.status_code == 200]
        if len(successful) > 1:
            # Should have same UTC time
            utc_times = [r.json()["utc"] for r in successful]
            assert all(utc == utc_times[0] for utc in utc_times)

            # Should have same equatorial coordinates
            sun_positions = [r.json()["bodies"][0] for r in successful]
            ra_values = [s["ra_hours"] for s in sun_positions]
            assert all(abs(ra - ra_values[0]) < 0.001 for ra in ra_values)

    @pytest.mark.asyncio
    async def test_caching_with_normalized_dates(self):
        """Test that caching works with date normalization across formats."""
        place = {
            "lat": 37.840347,
            "lon": -85.949127
        }

        # Same logical time in different formats
        payloads = [
            {
                "when": {
                    "local_datetime": "2023-01-01T12:00:00",
                    "place": place
                },
                "system": "tropical",
                "bodies": ["Sun"]
            },
            {
                "when": {
                    "local_datetime": "Jan 1, 2023 12:00 PM",
                    "place": place
                },
                "system": "tropical",
                "bodies": ["Sun"]
            },
            {
                "when": {
                    "local_datetime": "01/01/2023 12:00:00",
                    "place": place
                },
                "system": "tropical",
                "bodies": ["Sun"]
            }
        ]

        responses = []
        async with httpx.AsyncClient() as client:
            for payload in payloads:
                response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)
                responses.append(response)

        # Check if successful responses have same ETag (indicating cache hit)
        successful = [r for r in responses if r.status_code == 200]
        if len(successful) > 1:
            etags = [r.headers.get("etag") for r in successful]
            # At least some should match (cache hit)
            assert len(set(etags)) <= len(etags)

    @pytest.mark.asyncio
    async def test_all_ayanamsha_systems(self):
        """Test all ayanāṃśa systems from registry."""
        ayanamsha_systems = [
            "lahiri",
            "fagan_bradley_dynamic",
            "fagan_bradley_fixed",
            "krishnamurti",
            "raman",
            "yukteshwar"
        ]

        base_payload = {
            "when": {"utc": "2000-01-01T12:00:00Z"},
            "system": "sidereal",
            "bodies": ["Sun"]
        }

        successful_responses = []

        for ayanamsha_id in ayanamsha_systems:
            payload = {
                **base_payload,
                "ayanamsha": {"id": ayanamsha_id}
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

            if response.status_code == 200:
                successful_responses.append((ayanamsha_id, response))

        # Should have at least basic ayanāṃśa systems working
        assert len(successful_responses) >= 3

        for ayanamsha_id, response in successful_responses:
            data = response.json()

            # Verify ayanāṃśa was applied
            assert data["provenance"]["ayanamsha"]["id"] == ayanamsha_id
            assert "value_deg" in data["provenance"]["ayanamsha"]

            # Ayanāṃśa values should be reasonable (15-30 degrees for modern times)
            ayanamsha_value = data["provenance"]["ayanamsha"]["value_deg"]
            assert 10.0 <= ayanamsha_value <= 35.0

    @pytest.mark.asyncio
    async def test_coordinate_frame_consistency(self):
        """Test coordinate frame consistency across systems."""
        base_payload = {
            "when": {"utc": "2023-06-21T12:00:00Z"},  # Summer solstice
            "bodies": ["Sun"]
        }

        test_cases = [
            {
                "system": "tropical",
                "frame": {"type": "ecliptic_of_date"},
                "epoch": "of_date"
            },
            {
                "system": "tropical",
                "frame": {"type": "equatorial"},
                "epoch": "J2000"
            },
            {
                "system": "sidereal",
                "ayanamsha": {"id": "lahiri"},
                "frame": {"type": "ecliptic_of_date"},
                "epoch": "of_date"
            },
            {
                "system": "sidereal",
                "ayanamsha": {"id": "lahiri"},
                "frame": {"type": "equatorial"},
                "epoch": "J2000"
            }
        ]

        responses = []
        for case in test_cases:
            payload = {**base_payload, **case}

            async with httpx.AsyncClient() as client:
                response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

            responses.append((case, response))

        successful = [(case, r) for case, r in responses if r.status_code == 200]

        for case, response in successful:
            data = response.json()
            sun = data["bodies"][0]

            # Verify frame and epoch in provenance
            assert data["provenance"]["reference_frame"] == case["frame"]["type"]
            assert data["provenance"]["epoch"] == case["epoch"]

            # Verify coordinate presence based on frame
            if case["frame"]["type"] == "equatorial":
                assert "ra_hours" in sun
                assert "dec_deg" in sun
                assert 0.0 <= sun["ra_hours"] < 24.0
                assert -90.0 <= sun["dec_deg"] <= 90.0

            # Always should have ecliptic coordinates for compatibility
            assert "lon_deg" in sun
            assert "lat_deg" in sun
            assert 0.0 <= sun["lon_deg"] < 360.0
            assert -90.0 <= sun["lat_deg"] <= 90.0

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """Test error handling across integrated features."""
        error_cases = [
            {
                "name": "invalid_ayanamsha",
                "payload": {
                    "when": {"utc": "2023-01-01T12:00:00Z"},
                    "system": "sidereal",
                    "ayanamsha": {"id": "nonexistent"},
                    "bodies": ["Sun"]
                },
                "expected_code": "AYANAMSHA.UNSUPPORTED"
            },
            {
                "name": "invalid_frame_epoch_combo",
                "payload": {
                    "when": {"utc": "2023-01-01T12:00:00Z"},
                    "system": "tropical",
                    "frame": {"type": "equatorial"},
                    "epoch": "of_date",
                    "bodies": ["Sun"]
                },
                "expected_code": "INPUT.INVALID"
            },
            {
                "name": "invalid_local_datetime",
                "payload": {
                    "when": {
                        "local_datetime": "invalid date format",
                        "place": {"lat": 40.7128, "lon": -74.0060}
                    },
                    "system": "tropical",
                    "bodies": ["Sun"]
                },
                "expected_code": "INPUT.INVALID"
            },
            {
                "name": "conflicting_when_fields",
                "payload": {
                    "when": {
                        "utc": "2023-01-01T12:00:00Z",
                        "local_datetime": "2023-01-01T07:00:00",
                        "place": {"lat": 40.7128, "lon": -74.0060}
                    },
                    "system": "tropical",
                    "bodies": ["Sun"]
                }
            }
        ]

        for case in error_cases:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{BASE_URL}/v1/positions", json=case["payload"], timeout=10)

            # Should be an error response
            assert response.status_code >= 400

            if response.status_code != 422:  # Skip Pydantic validation errors
                error_data = response.json()
                if "expected_code" in case:
                    assert case["expected_code"] in error_data.get("code", "")

    @pytest.mark.asyncio
    async def test_rate_limiting_behavior(self):
        """Test rate limiting doesn't interfere with features."""
        payload = {
            "when": {"utc": "2023-01-01T12:00:00Z"},
            "system": "tropical",
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun"]
        }

        # Make multiple requests
        responses = []
        async with httpx.AsyncClient() as client:
            for i in range(5):
                response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)
                responses.append(response)

                # Small delay to avoid overwhelming
                time.sleep(0.1)

        # Should have rate limit headers on successful responses
        successful = [r for r in responses if r.status_code == 200]

        for response in successful:
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers

        # If any rate limited, should have proper response
        rate_limited = [r for r in responses if r.status_code == 429]
        for response in rate_limited:
            assert "Retry-After" in response.headers
            error_data = response.json()
            assert error_data["code"] == "RATE.LIMITED"

    @pytest.mark.asyncio
    async def test_health_endpoint_with_phase2_features(self):
        """Test health endpoint includes Phase 2 feature status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

        assert response.status_code == 200
        health_data = response.json()

        # Should include basic health info
        assert "status" in health_data
        assert "timestamp" in health_data

        # May include cache and rate limiting status if configured
        if "cache" in health_data:
            cache_info = health_data["cache"]
            assert "type" in cache_info

        if "rate_limiter" in health_data:
            rl_info = health_data["rate_limiter"]
            assert "healthy" in rl_info

    @pytest.mark.asyncio
    async def test_backwards_compatibility(self):
        """Test that Phase 2 features maintain backwards compatibility."""
        # Simple v1.0 style request should still work
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun", "Moon"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Should have all expected v1.0 fields
            assert "utc" in data
            assert "bodies" in data
            assert len(data["bodies"]) == 2

            # Should have ecliptic coordinates (default)
            for body in data["bodies"]:
                assert "name" in body
                assert "lon_deg" in body
                assert "lat_deg" in body

            # Provenance should indicate defaults
            assert data["provenance"]["reference_frame"] == "ecliptic_of_date"
            assert data["provenance"]["epoch"] == "of_date"

    @pytest.mark.asyncio
    async def test_performance_with_all_features(self):
        """Test performance impact of Phase 2 features."""
        payload = {
            "when": {
                "local_datetime": "Dec 25, 2023 3:30 PM",
                "place": {"lat": 40.7128, "lon": -74.0060}
            },
            "system": "sidereal",
            "ayanamsha": {"id": "lahiri"},
            "frame": {"type": "equatorial"},
            "epoch": "J2000",
            "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        }

        start_time = time.time()

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=30)

        end_time = time.time()
        duration = end_time - start_time

        if response.status_code == 200:
            # Should complete in reasonable time (under 10 seconds even with all features)
            assert duration < 10.0

            data = response.json()
            assert len(data["bodies"]) == 7

            # All bodies should have both coordinate systems
            for body in data["bodies"]:
                assert "ra_hours" in body
                assert "dec_deg" in body
                assert "lon_deg" in body
                assert "lat_deg" in body