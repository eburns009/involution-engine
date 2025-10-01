"""
Flexible date parsing utilities for the Involution Engine.

Provides robust parsing of various datetime formats using dateutil,
with validation and normalization for astronomical calculations.
"""

from dateutil import parser
from datetime import datetime, timezone
import re
from typing import Optional


def try_parse_local(dt_str: str) -> str:
    """
    Parse a flexible local datetime string and return normalized ISO format.

    Accepts a wide range of ISO-ish formats without timezone information.
    The Time Resolver will handle timezone conversion based on place.

    Args:
        dt_str: Local datetime string in various formats

    Returns:
        Normalized ISO 8601 string (without timezone)

    Raises:
        ValueError: If the datetime string cannot be parsed

    Examples:
        >>> try_parse_local("2023-12-25T15:30:00")
        "2023-12-25T15:30:00"

        >>> try_parse_local("Dec 25, 2023 3:30 PM")
        "2023-12-25T15:30:00"

        >>> try_parse_local("2023/12/25 15:30")
        "2023-12-25T15:30:00"
    """
    if not dt_str or not dt_str.strip():
        raise ValueError("Empty datetime string")

    dt_str = dt_str.strip()

    try:
        # Use dateutil parser for flexible parsing
        # Do not allow timezone information to be parsed
        # We want only local datetime without timezone
        dt = parser.parse(dt_str, default=datetime(1900, 1, 1))

        # Check if the parsed datetime has timezone info
        if dt.tzinfo is not None:
            raise ValueError("Timezone information not allowed in local datetime. Use 'utc' field for UTC times.")

        # Validate reasonable date range for astronomical calculations
        if dt.year < 1000 or dt.year > 3000:
            raise ValueError(f"Year {dt.year} outside reasonable range (1000-3000)")

        # Return normalized ISO format without timezone
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    except parser.ParserError as e:
        raise ValueError(f"Unable to parse datetime '{dt_str}': {e}")
    except ValueError:
        # Re-raise our custom validation errors
        raise
    except Exception as e:
        raise ValueError(f"Unexpected error parsing datetime '{dt_str}': {e}")


def validate_utc_format(utc_str: str) -> str:
    """
    Validate and normalize UTC datetime string.

    Args:
        utc_str: UTC datetime string

    Returns:
        Normalized UTC datetime string

    Raises:
        ValueError: If the UTC string is invalid
    """
    if not utc_str or not utc_str.strip():
        raise ValueError("Empty UTC datetime string")

    utc_str = utc_str.strip()

    # Check for common UTC indicators
    has_utc_indicator = (
        utc_str.endswith('Z') or
        utc_str.endswith('+00:00') or
        utc_str.endswith('-00:00') or
        utc_str.endswith('UTC') or
        '+00:00' in utc_str
    )

    try:
        # Parse the datetime
        if utc_str.endswith('Z'):
            # ISO format with Z suffix
            dt = datetime.fromisoformat(utc_str[:-1])
        elif 'UTC' in utc_str:
            # Remove UTC suffix and parse
            dt_str = utc_str.replace('UTC', '').strip()
            dt = parser.parse(dt_str)
        else:
            # Try ISO format first, then dateutil
            try:
                dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
            except ValueError:
                dt = parser.parse(utc_str)

        # Ensure we have timezone info or can assume UTC
        if dt.tzinfo is None and not has_utc_indicator:
            raise ValueError("UTC datetime must include timezone indicator (Z, +00:00, or UTC)")

        # Convert to UTC if needed
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

        # Validate reasonable date range
        if dt.year < 1000 or dt.year > 3000:
            raise ValueError(f"Year {dt.year} outside reasonable range (1000-3000)")

        # Return normalized ISO format with Z suffix
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        raise ValueError(f"Unable to parse UTC datetime '{utc_str}': {e}")


def parse_flexible_datetime(dt_str: str, is_utc: bool = False) -> str:
    """
    Parse a datetime string with flexible format support.

    Args:
        dt_str: Datetime string to parse
        is_utc: Whether this should be treated as UTC

    Returns:
        Normalized datetime string

    Raises:
        ValueError: If parsing fails
    """
    if is_utc:
        return validate_utc_format(dt_str)
    else:
        return try_parse_local(dt_str)


def is_valid_datetime_format(dt_str: str) -> bool:
    """
    Check if a datetime string can be parsed.

    Args:
        dt_str: Datetime string to validate

    Returns:
        True if the string can be parsed, False otherwise
    """
    try:
        try_parse_local(dt_str)
        return True
    except ValueError:
        return False


def get_datetime_format_hints() -> list[str]:
    """
    Get a list of supported datetime format examples.

    Returns:
        List of example datetime format strings
    """
    return [
        "2023-12-25T15:30:00",  # ISO 8601
        "2023-12-25 15:30:00",  # ISO-like with space
        "2023/12/25 15:30",     # US format with time
        "Dec 25, 2023 3:30 PM", # Natural language
        "25 December 2023 15:30", # European style
        "2023-12-25T15:30",     # ISO without seconds
        "12/25/2023 3:30:00 PM", # US format with AM/PM
    ]


def normalize_datetime_for_cache_key(dt_str: str) -> str:
    """
    Normalize datetime string for use in cache keys.

    Args:
        dt_str: Datetime string to normalize

    Returns:
        Normalized string suitable for cache keys
    """
    try:
        # Parse and normalize to consistent format
        parsed = try_parse_local(dt_str)
        return parsed.replace(':', '').replace('-', '').replace('T', '_')
    except ValueError:
        # Fallback to simple normalization
        return dt_str.replace(':', '').replace('-', '').replace(' ', '_').replace('T', '_')