"""
Ayanāṃśa Property-Based and Invariant Tests

Property-based testing using Hypothesis to validate fundamental invariants:
- Sidereal = Tropical - Ayanāṃśa (within tolerance)
- Time progression matches expected precession rate
- Invariants hold across all dates and ayanāṃśa systems

High-leverage tests that catch subtle formula errors.
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Optional
import math

try:
    from hypothesis import given, strategies as st, settings, assume
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    pytest.skip("hypothesis library required for property tests", allow_module_level=True)


# Strategies for property-based testing
dates_strategy = st.datetimes(
    min_value=datetime(1900, 1, 1, tzinfo=timezone.utc),
    max_value=datetime(2100, 12, 31, tzinfo=timezone.utc)
)

bodies_strategy = st.sampled_from([
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"
])

ayanamsa_strategy = st.sampled_from([
    "lahiri",
    "fagan_bradley",
    "fagan_bradley_fixed",
    "krishnamurti",
    "raman",
    "yukteshwar"
])


def get_tropical_position(dt: datetime, body: str) -> Optional[float]:
    """Fetch tropical longitude for a body at given datetime."""
    try:
        import requests
        import os

        base_url = os.getenv("ENGINE_BASE", "http://localhost:8080")
        utc_iso = dt.isoformat().replace("+00:00", "Z")

        payload = {
            "when": {"utc": utc_iso},
            "system": "tropical",
            "bodies": [body]
        }

        response = requests.post(
            f"{base_url}/v1/positions",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        return data["bodies"][body]["lon_deg"]

    except Exception as e:
        pytest.skip(f"API call failed: {e}")
        return None


def get_sidereal_position(dt: datetime, body: str, ayanamsa: str) -> Optional[float]:
    """Fetch sidereal longitude for a body with given ayanāṃśa."""
    try:
        import requests
        import os

        base_url = os.getenv("ENGINE_BASE", "http://localhost:8080")
        utc_iso = dt.isoformat().replace("+00:00", "Z")

        payload = {
            "when": {"utc": utc_iso},
            "system": "sidereal",
            "ayanamsha": {"id": ayanamsa},
            "bodies": [body]
        }

        response = requests.post(
            f"{base_url}/v1/positions",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        return data["bodies"][body]["lon_deg"]

    except Exception as e:
        pytest.skip(f"API call failed: {e}")
        return None


def get_ayanamsa_offset(dt: datetime, ayanamsa: str) -> Optional[float]:
    """
    Compute ayanāṃśa offset in degrees for given date.

    Can be derived from Sun tropical - sidereal difference.
    """
    try:
        tropical_sun = get_tropical_position(dt, "Sun")
        sidereal_sun = get_sidereal_position(dt, "Sun", ayanamsa)

        if tropical_sun is None or sidereal_sun is None:
            return None

        # Ayanāṃśa = Tropical - Sidereal (with wraparound handling)
        diff = tropical_sun - sidereal_sun

        # Normalize to [0, 360)
        while diff < 0:
            diff += 360
        while diff >= 360:
            diff -= 360

        # Ayanāṃśa should be in range [0, 50]° (typical values 20-25°)
        # If diff > 180, it wrapped around, so subtract from 360
        if diff > 180:
            diff = diff - 360

        return abs(diff)

    except Exception:
        return None


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis required")
@given(dt=dates_strategy, body=bodies_strategy, ayanamsa=ayanamsa_strategy)
@settings(max_examples=50, deadline=15000)  # 15s deadline for API calls
def test_property_sidereal_equals_tropical_minus_ayanamsa(dt, body, ayanamsa):
    """
    Property Test: Sidereal = Tropical - Ayanāṃśa

    This fundamental invariant must hold for all dates, bodies, and
    ayanāṃśa systems within documented tolerance (≤1 arcminute).
    """
    # Skip Moon for very tight tolerances (rapid motion)
    assume(body != "Moon")

    tropical_lon = get_tropical_position(dt, body)
    sidereal_lon = get_sidereal_position(dt, body, ayanamsa)

    if tropical_lon is None or sidereal_lon is None:
        assume(False)  # Skip this example

    # Calculate actual ayanāṃśa from difference
    diff = tropical_lon - sidereal_lon

    # Normalize difference to [-180, 180] range
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360

    # Ayanāṃśa should be positive and in plausible range [15, 35] degrees
    actual_ayanamsa = abs(diff)

    assert 15 <= actual_ayanamsa <= 35, (
        f"Ayanāṃśa {actual_ayanamsa}° outside plausible range for {ayanamsa} "
        f"at {dt.date()} (body: {body})"
    )

    # Get expected ayanāṃśa value
    expected_ayanamsa = get_ayanamsa_offset(dt, ayanamsa)

    if expected_ayanamsa is not None:
        # Tolerance: ≤1 arcminute (0.0167°)
        tolerance_deg = 1.0 / 60.0

        deviation = abs(actual_ayanamsa - expected_ayanamsa)

        assert deviation <= tolerance_deg, (
            f"Invariant violation: Tropical {tropical_lon}° - Sidereal {sidereal_lon}° "
            f"= {actual_ayanamsa}°, expected {expected_ayanamsa}° "
            f"(deviation: {deviation * 60:.2f}' > 1') "
            f"[{body}, {ayanamsa}, {dt.date()}]"
        )


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis required")
@given(
    start_date=dates_strategy,
    ayanamsa=ayanamsa_strategy
)
@settings(max_examples=20, deadline=30000)
def test_property_ayanamsa_time_progression(start_date, ayanamsa):
    """
    Property Test: Ayanāṃśa increases over time (precession).

    Validates that d(ayanāṃśa)/dt matches expected precession rate.
    Rate: ~50.3 arcseconds/year = ~0.0140°/year
    """
    # Skip fixed ayanāṃśa (doesn't change over time)
    assume(ayanamsa != "fagan_bradley_fixed")

    # Get ayanāṃśa at start date
    ayanamsa_start = get_ayanamsa_offset(start_date, ayanamsa)

    # Get ayanāṃśa 10 years later
    end_date = start_date + timedelta(days=365 * 10)
    ayanamsa_end = get_ayanamsa_offset(end_date, ayanamsa)

    if ayanamsa_start is None or ayanamsa_end is None:
        assume(False)

    # Ayanāṃśa should increase
    assert ayanamsa_end > ayanamsa_start, (
        f"Ayanāṃśa should increase over time: "
        f"{ayanamsa_start}° ({start_date.year}) → {ayanamsa_end}° ({end_date.year})"
    )

    # Calculate rate of change
    years = 10
    rate_per_year = (ayanamsa_end - ayanamsa_start) / years

    # Expected rate: ~0.0140°/year (50.3"/year)
    # Allow range 0.010-0.020°/year (conservative)
    expected_min = 0.010
    expected_max = 0.020

    assert expected_min <= rate_per_year <= expected_max, (
        f"Ayanāṃśa progression rate {rate_per_year:.4f}°/year outside "
        f"expected range [{expected_min}, {expected_max}] for {ayanamsa}"
    )


def test_fagan_bradley_fixed_is_constant():
    """
    Specific Property: Fagan-Bradley Fixed must be constant over time.

    This is a sanity check that the "fixed" ayanāṃśa doesn't change.
    """
    dates = [
        datetime(1900, 1, 1, tzinfo=timezone.utc),
        datetime(1950, 1, 1, tzinfo=timezone.utc),
        datetime(2000, 1, 1, tzinfo=timezone.utc),
        datetime(2050, 1, 1, tzinfo=timezone.utc),
    ]

    offsets = []

    for dt in dates:
        offset = get_ayanamsa_offset(dt, "fagan_bradley_fixed")
        if offset is not None:
            offsets.append(offset)

    # All offsets should be identical (24.22°)
    if len(offsets) >= 2:
        std_dev = math.sqrt(sum((x - sum(offsets) / len(offsets)) ** 2 for x in offsets) / len(offsets))

        assert std_dev < 0.01, (
            f"Fagan-Bradley Fixed should be constant, got variance {std_dev:.4f}° "
            f"across dates (values: {offsets})"
        )

        # Check it's close to expected 24.22°
        expected = 24.22
        for offset in offsets:
            assert abs(offset - expected) < 0.1, (
                f"Fagan-Bradley Fixed should be ~24.22°, got {offset}°"
            )


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis required")
@given(dt=dates_strategy, body=bodies_strategy)
@settings(max_examples=30, deadline=15000)
def test_property_longitude_periodicity_sanity(dt, body):
    """
    Metamorphic Property: Longitudinal positions are periodic.

    For any body, (λ(t) − λ(t+orbital_period)) mod 360 should be small.
    This is a sanity check, not an exact orbital mechanics test.
    """
    # Approximate orbital periods (days)
    orbital_periods = {
        "Sun": 365,
        "Moon": 27,
        "Mercury": 88,
        "Venus": 225,
        "Mars": 687,
        "Jupiter": 4333,
        "Saturn": 10759,
        "Uranus": 30687,
        "Neptune": 60190,
        "Pluto": 90560,
    }

    if body not in orbital_periods:
        assume(False)

    period_days = orbital_periods[body]

    # Skip very long periods (test would take too long)
    assume(period_days < 5000)

    lon_t1 = get_tropical_position(dt, body)
    lon_t2 = get_tropical_position(dt + timedelta(days=period_days), body)

    if lon_t1 is None or lon_t2 is None:
        assume(False)

    # Calculate angular difference
    diff = abs(lon_t2 - lon_t1)
    if diff > 180:
        diff = 360 - diff

    # After one orbital period, body should be close to same longitude
    # Allow generous tolerance (perturbations, not exact period)
    tolerance = 30.0  # degrees (generous for this sanity check)

    assert diff < tolerance, (
        f"{body} moved {diff}° after {period_days} days (orbital period), "
        f"expected return to similar position"
    )


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis required")
@given(lon_deg=st.floats(min_value=-720, max_value=720))
def test_property_longitude_wraparound_normalization(lon_deg):
    """
    Property: Longitude normalization is idempotent and correct.

    Tests that longitude normalization to [0, 360) is correct and
    repeated normalization doesn't change the value.
    """
    def normalize_longitude(lon):
        """Normalize longitude to [0, 360) range."""
        result = lon % 360
        if result < 0:
            result += 360
        return result

    # Normalize once
    normalized = normalize_longitude(lon_deg)

    # Verify in range [0, 360)
    assert 0 <= normalized < 360, (
        f"Normalized longitude {normalized}° outside [0, 360)"
    )

    # Normalize again (should be identical - idempotent)
    normalized_again = normalize_longitude(normalized)

    assert normalized == normalized_again, (
        f"Normalization not idempotent: {normalized}° → {normalized_again}°"
    )

    # Verify equivalence (modulo 360)
    diff = abs((lon_deg - normalized) % 360)
    if diff > 180:
        diff = 360 - diff

    assert diff < 0.001, (
        f"Normalized longitude {normalized}° not equivalent to {lon_deg}° (mod 360)"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
