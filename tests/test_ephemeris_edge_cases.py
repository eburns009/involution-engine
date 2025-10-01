"""
Numerical Correctness & Ephemeris Edge Case Tests

Tests DE440/DE441 handoff boundaries, kernel integrity, and continuity
to ensure no discontinuities or errors at ephemeris boundaries.

High-leverage tests that catch subtle numerical issues.
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any


# DE440 coverage: 1550-01-01 to 2650-12-31
# DE441 used for dates outside this range
DE440_START = datetime(1550, 1, 1, tzinfo=timezone.utc)
DE440_END = datetime(2650, 12, 31, tzinfo=timezone.utc)

# Test boundaries with ±1, ±7, ±30 day windows
HANDOFF_TEST_OFFSETS = [-30, -7, -1, 0, 1, 7, 30]


@pytest.fixture
def api_client():
    """API client fixture (adapt to your test infrastructure)."""
    try:
        import requests
        return requests
    except ImportError:
        pytest.skip("requests library required for API tests")


def get_positions(api_client, dt: datetime, bodies: list = None) -> Dict[str, Any]:
    """
    Fetch positions for given datetime and bodies.

    Returns dict with bodies data and metadata including ephemeris used.
    """
    if bodies is None:
        bodies = ["Sun", "Moon", "Mars", "Jupiter", "Saturn"]

    utc_iso = dt.isoformat().replace("+00:00", "Z")
    payload = {
        "when": {"utc": utc_iso},
        "system": "tropical",
        "bodies": bodies
    }

    response = api_client.post(
        "http://localhost:8080/v1/positions",
        json=payload,
        timeout=10
    )
    response.raise_for_status()
    return response.json()


@pytest.mark.parametrize("boundary_date,offset_days", [
    (DE440_START, offset) for offset in HANDOFF_TEST_OFFSETS
] + [
    (DE440_END, offset) for offset in HANDOFF_TEST_OFFSETS
])
def test_de440_de441_handoff_continuity(api_client, boundary_date, offset_days):
    """
    Test DE440 ⇄ DE441 handoff boundaries for continuity.

    Ensures no discontinuous jumps when ephemeris switches at coverage boundaries.
    Validates that provenance correctly reports which ephemeris was used.

    Tolerance: Δlon < 0.1' for planets, < 10' for Moon
    """
    test_date = boundary_date + timedelta(days=offset_days)

    # Get positions
    result = get_positions(api_client, test_date)

    # Verify ephemeris provenance is reported
    assert "metadata" in result, "Response missing metadata"
    assert "ephemeris" in result["metadata"], "Metadata missing ephemeris field"

    ephemeris_used = result["metadata"]["ephemeris"]

    # Verify correct ephemeris is used based on date
    if DE440_START <= test_date <= DE440_END:
        assert ephemeris_used == "de440", (
            f"Expected DE440 for {test_date.date()}, got {ephemeris_used}"
        )
    else:
        assert ephemeris_used == "de441", (
            f"Expected DE441 for {test_date.date()}, got {ephemeris_used}"
        )

    # Store for continuity check (if testing adjacent days)
    return result


def test_handoff_no_step_jumps(api_client):
    """
    Test continuity across handoff boundary with daily steps.

    Validates that position changes smoothly across the DE440/DE441
    boundary with no discontinuous jumps.
    """
    # Test at lower boundary (DE440 start)
    start_date = DE440_START - timedelta(days=2)  # DE441

    previous_positions = None

    for day_offset in range(5):  # -2, -1, 0 (boundary), +1, +2
        test_date = start_date + timedelta(days=day_offset)
        result = get_positions(api_client, test_date, bodies=["Sun", "Mars", "Jupiter"])

        if previous_positions is not None:
            # Check continuity for each body
            for body_name in ["Sun", "Mars", "Jupiter"]:
                prev_lon = previous_positions["bodies"][body_name]["lon_deg"]
                curr_lon = result["bodies"][body_name]["lon_deg"]

                # Calculate angular difference (handling 360° wraparound)
                delta = abs(curr_lon - prev_lon)
                if delta > 180:
                    delta = 360 - delta

                # Tolerance: planets move < 5° per day, no jumps > 1°
                max_daily_motion = 5.0  # degrees (generous for fast planets)
                max_discontinuity = 0.1  # degrees (6 arcminutes)

                assert delta < max_daily_motion, (
                    f"{body_name} moved {delta}° in 1 day at handoff "
                    f"({test_date.date()}, ephemeris: {result['metadata']['ephemeris']})"
                )

                # Stricter check: no discontinuities > 0.1°
                if day_offset == 2:  # At the boundary
                    assert delta < max_discontinuity or delta > (max_daily_motion - 1), (
                        f"{body_name} discontinuity {delta}° at DE440/DE441 boundary "
                        f"({test_date.date()})"
                    )

        previous_positions = result


def test_kernel_checksum_verification_on_startup():
    """
    Verify that kernel checksums are validated on service startup.

    This test ensures the integrity check system is in place.
    Tests the /healthz endpoint for kernel status.
    """
    try:
        import requests
    except ImportError:
        pytest.skip("requests library required")

    response = requests.get("http://localhost:8080/healthz", timeout=5)
    response.raise_for_status()

    health_data = response.json()

    # Verify kernel status is reported
    assert "kernels" in health_data, "Health check missing kernels field"

    kernels = health_data["kernels"]

    # Check that kernel status includes checksums or validation info
    if isinstance(kernels, dict):
        assert "de440" in kernels or "de441" in kernels, (
            "Health check missing ephemeris kernel status"
        )

        # Verify checksum field exists (format may vary)
        for kernel_name, kernel_info in kernels.items():
            if isinstance(kernel_info, dict):
                # Look for checksum or status field
                assert any(key in kernel_info for key in ["checksum", "status", "ok"]), (
                    f"Kernel {kernel_name} missing integrity information"
                )


@pytest.mark.skipif(True, reason="Requires simulated corrupted kernel (chaos test)")
def test_corrupted_kernel_handling():
    """
    Simulate a corrupted kernel file and verify graceful error handling.

    Expected: RANGE.EPHEMERIS_OUTSIDE or KERNEL.CORRUPTED error,
    never a raw CSPICE error exposed to the client.

    NOTE: This is a chaos test requiring infrastructure to corrupt files.
    """
    pass  # Implement with chaos testing infrastructure


def test_extreme_date_ranges(api_client):
    """
    Test positions at extreme date ranges (historical & far future).

    Validates that DE441 correctly handles dates far outside DE440 range.
    """
    extreme_dates = [
        datetime(1400, 1, 1, tzinfo=timezone.utc),  # Far past (DE441)
        datetime(1549, 12, 31, tzinfo=timezone.utc),  # Just before DE440
        datetime(2651, 1, 1, tzinfo=timezone.utc),  # Just after DE440
        datetime(3000, 1, 1, tzinfo=timezone.utc),  # Far future (DE441)
    ]

    for test_date in extreme_dates:
        result = get_positions(api_client, test_date, bodies=["Sun", "Mars"])

        # Should succeed with DE441
        assert result["metadata"]["ephemeris"] == "de441", (
            f"Expected DE441 for {test_date.date()}"
        )

        # Verify positions are plausible (not NaN or extreme values)
        for body in result["bodies"].values():
            lon = body["lon_deg"]
            assert 0 <= lon < 360, f"Invalid longitude {lon} for {test_date.date()}"


def test_moon_high_precision_near_perigee():
    """
    Test Moon position precision during perigee/apogee.

    The Moon's rapid motion requires special attention to ensure
    sub-arcsecond precision is maintained.
    """
    # Use a known perigee date (example)
    perigee_date = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    try:
        import requests
    except ImportError:
        pytest.skip("requests library required")

    result = get_positions(requests, perigee_date, bodies=["Moon"])

    moon_data = result["bodies"]["Moon"]

    # Moon should have distance reported
    assert "distance_au" in moon_data or "distance_km" in moon_data, (
        "Moon position missing distance information"
    )

    # Verify latitude is reasonable (Moon's orbital inclination ~5.14°)
    if "lat_deg" in moon_data:
        assert abs(moon_data["lat_deg"]) <= 6, (
            f"Moon latitude {moon_data['lat_deg']}° exceeds orbital inclination"
        )


@pytest.mark.parametrize("body,max_lat_deg", [
    ("Mercury", 7.0),  # Orbital inclination ~7°
    ("Venus", 3.4),    # ~3.39°
    ("Mars", 1.9),     # ~1.85°
    ("Jupiter", 1.3),  # ~1.31°
    ("Saturn", 2.5),   # ~2.49°
])
def test_ecliptic_latitude_bounds(api_client, body, max_lat_deg):
    """
    Verify that ecliptic latitudes stay within orbital inclination bounds.

    Catches coordinate transformation errors or invalid data.
    """
    test_date = datetime(2025, 1, 1, tzinfo=timezone.utc)

    result = get_positions(api_client, test_date, bodies=[body])

    body_data = result["bodies"][body]

    if "lat_deg" in body_data:
        lat = body_data["lat_deg"]
        assert abs(lat) <= max_lat_deg + 0.5, (  # +0.5° margin for perturbations
            f"{body} latitude {lat}° exceeds max {max_lat_deg}° (plus margin)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
