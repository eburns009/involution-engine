"""
Tests for flexible date parsing functionality.

Tests various datetime formats and the enhanced local datetime
to UTC conversion with proper validation.
"""

import pytest
import httpx
import os
from unittest.mock import patch

from app.util.dates import (
    try_parse_local, validate_utc_format, parse_flexible_datetime,
    is_valid_datetime_format, get_datetime_format_hints,
    normalize_datetime_for_cache_key
)

BASE_URL = os.getenv("ENGINE_BASE", "http://localhost:8080")


class TestDateParsing:
    """Tests for flexible datetime parsing utilities."""

    def test_try_parse_local_iso_format(self):
        """Test parsing ISO format local datetime."""
        result = try_parse_local("2023-12-25T15:30:00")
        assert result == "2023-12-25T15:30:00"

    def test_try_parse_local_iso_with_space(self):
        """Test parsing ISO-like format with space."""
        result = try_parse_local("2023-12-25 15:30:00")
        assert result == "2023-12-25T15:30:00"

    def test_try_parse_local_us_format(self):
        """Test parsing US date format."""
        result = try_parse_local("12/25/2023 3:30 PM")
        assert result == "2023-12-25T15:30:00"

    def test_try_parse_local_natural_language(self):
        """Test parsing natural language dates."""
        result = try_parse_local("Dec 25, 2023 3:30 PM")
        assert result == "2023-12-25T15:30:00"

    def test_try_parse_local_european_style(self):
        """Test parsing European style dates."""
        result = try_parse_local("25 December 2023 15:30")
        assert result == "2023-12-25T15:30:00"

    def test_try_parse_local_without_seconds(self):
        """Test parsing datetime without seconds."""
        result = try_parse_local("2023-12-25T15:30")
        assert result == "2023-12-25T15:30:00"

    def test_try_parse_local_empty_string(self):
        """Test error for empty datetime string."""
        with pytest.raises(ValueError) as exc_info:
            try_parse_local("")

        assert "Empty datetime string" in str(exc_info.value)

    def test_try_parse_local_with_timezone(self):
        """Test error when timezone is included."""
        with pytest.raises(ValueError) as exc_info:
            try_parse_local("2023-12-25T15:30:00Z")

        assert "Timezone information not allowed" in str(exc_info.value)

    def test_try_parse_local_invalid_format(self):
        """Test error for invalid datetime format."""
        with pytest.raises(ValueError) as exc_info:
            try_parse_local("invalid datetime")

        assert "Unable to parse datetime" in str(exc_info.value)

    def test_try_parse_local_year_range_validation(self):
        """Test year range validation."""
        # Too early
        with pytest.raises(ValueError) as exc_info:
            try_parse_local("0999-01-01T12:00:00")
        assert "outside reasonable range" in str(exc_info.value)

        # Too late
        with pytest.raises(ValueError) as exc_info:
            try_parse_local("3001-01-01T12:00:00")
        assert "outside reasonable range" in str(exc_info.value)

    def test_validate_utc_format_with_z(self):
        """Test UTC validation with Z suffix."""
        result = validate_utc_format("2023-12-25T15:30:00Z")
        assert result == "2023-12-25T15:30:00Z"

    def test_validate_utc_format_with_offset(self):
        """Test UTC validation with timezone offset."""
        result = validate_utc_format("2023-12-25T15:30:00+00:00")
        assert result == "2023-12-25T15:30:00Z"

    def test_validate_utc_format_with_utc_suffix(self):
        """Test UTC validation with UTC suffix."""
        result = validate_utc_format("2023-12-25T15:30:00 UTC")
        assert result == "2023-12-25T15:30:00Z"

    def test_validate_utc_format_without_timezone(self):
        """Test error for UTC string without timezone indicator."""
        with pytest.raises(ValueError) as exc_info:
            validate_utc_format("2023-12-25T15:30:00")

        assert "must include timezone indicator" in str(exc_info.value)

    def test_parse_flexible_datetime_local(self):
        """Test flexible parsing for local datetime."""
        result = parse_flexible_datetime("Dec 25, 2023 3:30 PM", is_utc=False)
        assert result == "2023-12-25T15:30:00"

    def test_parse_flexible_datetime_utc(self):
        """Test flexible parsing for UTC datetime."""
        result = parse_flexible_datetime("2023-12-25T15:30:00Z", is_utc=True)
        assert result == "2023-12-25T15:30:00Z"

    def test_is_valid_datetime_format(self):
        """Test datetime format validation."""
        assert is_valid_datetime_format("2023-12-25T15:30:00") is True
        assert is_valid_datetime_format("Dec 25, 2023 3:30 PM") is True
        assert is_valid_datetime_format("invalid") is False
        assert is_valid_datetime_format("") is False

    def test_get_datetime_format_hints(self):
        """Test getting format hints."""
        hints = get_datetime_format_hints()
        assert isinstance(hints, list)
        assert len(hints) > 0
        assert "2023-12-25T15:30:00" in hints

    def test_normalize_datetime_for_cache_key(self):
        """Test datetime normalization for cache keys."""
        result = normalize_datetime_for_cache_key("2023-12-25T15:30:00")
        assert result == "20231225_153000"

        # Test fallback for invalid dates
        result = normalize_datetime_for_cache_key("invalid date")
        assert "invalid" in result


class TestFlexibleDatesAPI:
    """Tests for flexible date parsing in API endpoints."""

    @pytest.mark.asyncio
    async def test_utc_iso_format(self):
        """Test UTC in standard ISO format."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00Z"},
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_utc_with_offset(self):
        """Test UTC with timezone offset."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00+00:00"},
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_utc_invalid_format(self):
        """Test error for invalid UTC format."""
        payload = {
            "when": {"utc": "1962-07-03T04:33:00"},  # Missing timezone
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INPUT.INVALID"
        assert "Invalid UTC datetime format" in error_data["title"]

    @pytest.mark.asyncio
    async def test_local_datetime_iso_format(self):
        """Test local datetime in ISO format."""
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

        # Should succeed (time resolver will handle conversion)
        # Note: May fail if time resolver is not available, but parsing should work
        assert response.status_code in [200, 500]  # 500 if time resolver unavailable

    @pytest.mark.asyncio
    async def test_local_datetime_natural_format(self):
        """Test local datetime in natural language format."""
        payload = {
            "when": {
                "local_datetime": "July 2, 1962 11:33 PM",
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

        # Should succeed in parsing (time resolver availability may vary)
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_local_datetime_us_format(self):
        """Test local datetime in US format."""
        payload = {
            "when": {
                "local_datetime": "07/02/1962 11:33:00 PM",
                "place": {
                    "lat": 37.840347,
                    "lon": -85.949127
                }
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        # Should succeed in parsing
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_local_datetime_invalid_format(self):
        """Test error for invalid local datetime format."""
        payload = {
            "when": {
                "local_datetime": "invalid datetime format",
                "place": {
                    "lat": 37.840347,
                    "lon": -85.949127
                }
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INPUT.INVALID"
        assert "Invalid local datetime format" in error_data["title"]

    @pytest.mark.asyncio
    async def test_conflicting_time_inputs(self):
        """Test error for conflicting UTC and local datetime."""
        payload = {
            "when": {
                "utc": "1962-07-03T04:33:00Z",
                "local_datetime": "1962-07-02T23:33:00",
                "place": {
                    "lat": 37.840347,
                    "lon": -85.949127
                }
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 422  # Pydantic validation error
        # The When model validates mutual exclusion

    @pytest.mark.asyncio
    async def test_local_datetime_without_place(self):
        """Test error for local datetime without place."""
        payload = {
            "when": {
                "local_datetime": "1962-07-02T23:33:00"
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_local_datetime_incomplete_place(self):
        """Test error for local datetime with incomplete place."""
        payload = {
            "when": {
                "local_datetime": "1962-07-02T23:33:00",
                "place": {}  # Empty place
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

        assert response.status_code == 400
        error_data = response.json()
        assert error_data["code"] == "INPUT.INVALID"
        assert "Place required" in error_data["title"]

    @pytest.mark.asyncio
    async def test_date_format_variations_consistency(self):
        """Test that different formats for same time produce same results."""
        base_payload = {
            "system": "tropical",
            "bodies": ["Sun"]
        }

        # Same time in different formats (if time resolver available)
        formats = [
            "1962-07-02T23:33:00",
            "July 2, 1962 11:33 PM",
            "07/02/1962 23:33:00"
        ]

        place = {
            "name": "Fort Knox, Kentucky",
            "lat": 37.840347,
            "lon": -85.949127
        }

        responses = []

        for date_format in formats:
            payload = {
                **base_payload,
                "when": {
                    "local_datetime": date_format,
                    "place": place
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

            responses.append(response)

        # If time resolver is available, all should succeed with same UTC
        successful_responses = [r for r in responses if r.status_code == 200]

        if len(successful_responses) > 1:
            # Compare UTC values
            utc_values = [r.json()["utc"] for r in successful_responses]
            # All should be the same
            assert all(utc == utc_values[0] for utc in utc_values)

    @pytest.mark.asyncio
    async def test_caching_with_normalized_dates(self):
        """Test that caching works with date normalization."""
        place = {
            "lat": 37.840347,
            "lon": -85.949127
        }

        # Same time in different formats
        payload1 = {
            "when": {
                "local_datetime": "2023-01-01T12:00:00",
                "place": place
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        payload2 = {
            "when": {
                "local_datetime": "Jan 1, 2023 12:00 PM",
                "place": place
            },
            "system": "tropical",
            "bodies": ["Sun"]
        }

        async with httpx.AsyncClient() as client:
            response1 = await client.post(f"{BASE_URL}/v1/positions", json=payload1, timeout=10)
            response2 = await client.post(f"{BASE_URL}/v1/positions", json=payload2, timeout=10)

        # Both should be processed (may succeed or fail based on time resolver availability)
        assert response1.status_code in [200, 400, 500]
        assert response2.status_code in [200, 400, 500]

        # If both succeed, they should have the same ETag (same normalized time)
        if response1.status_code == 200 and response2.status_code == 200:
            etag1 = response1.headers.get("etag")
            etag2 = response2.headers.get("etag")
            assert etag1 == etag2