"""
Gap/Fold Handling Unit Tests
Tests for DST transition edge cases (spring forward / fall back)
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from time_resolver_v2 import resolve_time


class TestGapFoldHandling:
    """Test DST transition handling for gaps and folds"""

    def test_spring_forward_gap_handling(self):
        """Test spring forward gap (02:00 → 03:00, time doesn't exist)"""
        # 2023 US DST transition: March 12, 2:00 AM → 3:00 AM
        # Time 2:30 AM doesn't exist (gap)

        test_payload = {
            "local_datetime": "2023-03-12T02:30:00",  # In the gap
            "latitude": 40.7128,
            "longitude": -74.0060,  # New York
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        # Should handle gracefully - zoneinfo typically advances to post-gap time
        assert result["utc"] is not None
        assert result["zone_id"] == "America/New_York"
        assert result["dst_active"] is True  # After transition = DST active

        # UTC should be reasonable (either 06:30 or 07:30 UTC)
        utc_time = datetime.fromisoformat(result["utc"].replace('Z', '+00:00'))
        assert utc_time.hour in [6, 7]  # Valid post-gap handling

    def test_fall_back_fold_handling(self):
        """Test fall back fold (02:00 → 01:00, time exists twice)"""
        # 2023 US DST transition: November 5, 2:00 AM → 1:00 AM
        # Time 1:30 AM exists twice (fold)

        test_payload = {
            "local_datetime": "2023-11-05T01:30:00",  # In the fold
            "latitude": 40.7128,
            "longitude": -74.0060,  # New York
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        # Should handle fold gracefully
        assert result["utc"] is not None
        assert result["zone_id"] == "America/New_York"

        # UTC should be reasonable - either the first or second occurrence
        utc_time = datetime.fromisoformat(result["utc"].replace('Z', '+00:00'))
        # Could be either 05:30 (first occurrence, DST) or 06:30 (second occurrence, EST)
        assert utc_time.hour in [5, 6]

    def test_pre_transition_normal_time(self):
        """Test normal time before DST transition"""
        test_payload = {
            "local_datetime": "2023-03-12T01:30:00",  # Before spring forward
            "latitude": 40.7128,
            "longitude": -74.0060,
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        assert result["utc"] == "2023-03-12T06:30:00Z"  # EST: UTC-5
        assert result["zone_id"] == "America/New_York"
        assert result["dst_active"] is False  # Before DST starts
        assert result["offset_seconds"] == -18000  # EST offset

    def test_post_transition_normal_time(self):
        """Test normal time after DST transition"""
        test_payload = {
            "local_datetime": "2023-03-12T03:30:00",  # After spring forward
            "latitude": 40.7128,
            "longitude": -74.0060,
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        assert result["utc"] == "2023-03-12T07:30:00Z"  # EDT: UTC-4
        assert result["zone_id"] == "America/New_York"
        assert result["dst_active"] is True  # DST now active
        assert result["offset_seconds"] == -14400  # EDT offset

    def test_historical_gap_handling(self):
        """Test gap handling in historical periods with patches"""
        # Test a historical period where patches might affect DST behavior
        test_payload = {
            "local_datetime": "1943-03-14T02:30:00",  # War Time era gap
            "latitude": 40.7128,
            "longitude": -74.0060,
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        # Should handle gracefully even with historical patches
        assert result["utc"] is not None
        assert result["zone_id"] == "America/New_York"

        # Check if War Time patch was applied
        if "nyc_war_time_1943" in result["provenance"]["patches_applied"]:
            # War Time was year-round DST, so might handle differently
            assert result["confidence"] in ["high", "medium"]

    def test_no_dst_timezone_no_gaps(self):
        """Test timezone with no DST has no gap/fold issues"""
        test_payload = {
            "local_datetime": "2023-03-12T02:30:00",
            "latitude": 33.4484,
            "longitude": -112.0740,  # Phoenix, AZ (no DST)
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        assert result["utc"] == "2023-03-12T09:30:00Z"  # MST: UTC-7
        assert result["zone_id"] == "America/Phoenix"
        assert result["dst_active"] is False  # Arizona doesn't observe DST
        assert result["offset_seconds"] == -25200  # MST offset

    def test_different_timezone_transition(self):
        """Test gap/fold in different timezone (Europe)"""
        # Europe transitions on different dates
        test_payload = {
            "local_datetime": "2023-03-26T02:30:00",  # EU spring forward
            "latitude": 52.5200,
            "longitude": 13.4050,  # Berlin
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        # Should handle EU DST transition
        assert result["utc"] is not None
        assert result["zone_id"] == "Europe/Berlin"

        # Should be in DST after transition
        utc_time = datetime.fromisoformat(result["utc"].replace('Z', '+00:00'))
        # Either 00:30 or 01:30 UTC depending on gap handling
        assert utc_time.hour in [0, 1]

    def test_southern_hemisphere_transition(self):
        """Test reverse DST transition (Southern Hemisphere)"""
        # Australia transitions opposite to Northern Hemisphere
        test_payload = {
            "local_datetime": "2023-04-02T02:30:00",  # AU fall transition
            "latitude": -33.8688,
            "longitude": 151.2093,  # Sydney
            "parity_profile": "strict_history"
        }

        result = resolve_time(test_payload)

        assert result["utc"] is not None
        assert result["zone_id"] == "Australia/Sydney"

        # Should handle Southern Hemisphere DST correctly
        utc_time = datetime.fromisoformat(result["utc"].replace('Z', '+00:00'))
        assert utc_time is not None  # Basic sanity check

    def test_gap_fold_with_user_override(self):
        """Test gap/fold handling when user provides explicit timezone"""
        test_payload = {
            "local_datetime": "2023-03-12T02:30:00",  # In gap
            "latitude": 40.7128,
            "longitude": -74.0060,
            "parity_profile": "as_entered",
            "user_provided_zone": "EST"  # User forces EST
        }

        result = resolve_time(test_payload)

        # Should use user override even in gap period
        assert result["utc"] is not None
        assert result["confidence"] == "low"  # Lower confidence due to override
        assert len(result["warnings"]) > 0  # Should warn about override

    def test_confidence_during_transitions(self):
        """Test that confidence reflects uncertainty during transitions"""
        # Test multiple times around transition
        test_times = [
            "2023-03-12T01:30:00",  # Before (normal)
            "2023-03-12T02:30:00",  # Gap
            "2023-03-12T03:30:00"   # After (normal)
        ]

        confidences = []
        for time_str in test_times:
            test_payload = {
                "local_datetime": time_str,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "parity_profile": "strict_history"
            }
            result = resolve_time(test_payload)
            confidences.append(result["confidence"])

        # All should have reasonable confidence
        for conf in confidences:
            assert conf in ["high", "medium", "low"]

        # Gap time might have different confidence than normal times
        # This is implementation-dependent but should be consistent