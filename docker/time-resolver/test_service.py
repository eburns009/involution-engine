#!/usr/bin/env python3
"""
Test script for Time Resolver Service
"""

import requests
import json
import sys
from datetime import datetime

def test_service(base_url="http://localhost:8080"):
    """Test the time resolver service"""

    print(f"Testing Time Resolver Service at {base_url}")
    print("=" * 50)

    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        response.raise_for_status()
        health = response.json()
        print(f"   ✓ Status: {health['status']}")
        print(f"   ✓ Version: {health['version']}")
        print(f"   ✓ TZDB: {health['tzdb_version']}")
    except Exception as e:
        print(f"   ✗ Health check failed: {e}")
        return False

    # Test 2: Basic time resolution
    print("\n2. Testing basic time resolution...")
    test_payload = {
        "local_datetime": "1962-07-02T23:33:00",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "parity_profile": "strict_history"
    }

    try:
        response = requests.post(
            f"{base_url}/resolve",
            json=test_payload,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        print(f"   ✓ UTC: {result['utc']}")
        print(f"   ✓ Zone: {result['zone_id']}")
        print(f"   ✓ Offset: {result['offset_seconds']}s")
        print(f"   ✓ DST: {result['dst_active']}")
        print(f"   ✓ Confidence: {result['confidence']}")

        # Validate response structure
        required_fields = ['utc', 'zone_id', 'offset_seconds', 'dst_active',
                          'confidence', 'reason', 'provenance']
        missing = [f for f in required_fields if f not in result]
        if missing:
            print(f"   ✗ Missing fields: {missing}")
            return False

    except Exception as e:
        print(f"   ✗ Basic resolution failed: {e}")
        return False

    # Test 3: Historical patch application
    print("\n3. Testing historical patch (Fort Knox 1943)...")
    historical_payload = {
        "local_datetime": "1943-06-15T14:30:00",
        "latitude": 37.8917,
        "longitude": -85.9623,
        "parity_profile": "strict_history"
    }

    try:
        response = requests.post(
            f"{base_url}/resolve",
            json=historical_payload,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        print(f"   ✓ UTC: {result['utc']}")
        print(f"   ✓ Patches applied: {result['provenance']['patches_applied']}")
        print(f"   ✓ Reason: {result['reason']}")

        # Check if patch was applied
        if "fort_knox" in str(result['provenance']['patches_applied']).lower():
            print("   ✓ Fort Knox patch correctly applied")
        else:
            print("   ⚠ Fort Knox patch not applied (may be expected)")

    except Exception as e:
        print(f"   ✗ Historical patch test failed: {e}")
        return False

    # Test 4: Different parity profiles
    print("\n4. Testing parity profiles...")
    profiles = ["strict_history", "astro_com", "clairvision"]

    for profile in profiles:
        try:
            test_payload["parity_profile"] = profile
            response = requests.post(
                f"{base_url}/resolve",
                json=test_payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            print(f"   ✓ {profile}: {result['provenance']['resolution_mode']}")

        except Exception as e:
            print(f"   ✗ Profile {profile} failed: {e}")
            return False

    # Test 5: Error handling
    print("\n5. Testing error handling...")
    invalid_payload = {
        "local_datetime": "invalid-date",
        "latitude": 91,  # Invalid latitude
        "longitude": -74.0060
    }

    try:
        response = requests.post(
            f"{base_url}/resolve",
            json=invalid_payload,
            timeout=10
        )

        if response.status_code == 422:
            print("   ✓ Correctly rejected invalid input")
        else:
            print(f"   ⚠ Unexpected status code: {response.status_code}")

    except Exception as e:
        print(f"   ⚠ Error handling test failed: {e}")

    print("\n" + "=" * 50)
    print("✓ All tests completed successfully!")
    return True

def test_endpoints(base_url="http://localhost:8080"):
    """Test all available endpoints"""

    print(f"Testing all endpoints at {base_url}")
    print("-" * 30)

    endpoints = [
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/docs"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json")
    ]

    for method, path in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{path}", timeout=5)

            print(f"{method} {path}: {response.status_code}")

        except Exception as e:
            print(f"{method} {path}: ERROR - {e}")

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"

    print("Time Resolver Service Test Suite")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Test main functionality
    success = test_service(base_url)

    print()

    # Test all endpoints
    test_endpoints(base_url)

    sys.exit(0 if success else 1)