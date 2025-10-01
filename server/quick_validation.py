#!/usr/bin/env python3
"""
Quick validation script for Involution Engine v1.1 single FastAPI service.

This script performs basic smoke tests to verify the service is working correctly.
"""

import asyncio
import httpx
import json
import sys
import time
from typing import Dict, Any


BASE_URL = "http://localhost:8080"


async def test_health_check():
    """Test the health check endpoint."""
    print("Testing /healthz endpoint...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/healthz", timeout=10)

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed")
                print(f"   Status: {data.get('status', 'unknown')}")
                print(f"   Kernels OK: {data.get('kernels', {}).get('ok', False)}")
                print(f"   Bundle: {data.get('kernels', {}).get('bundle', 'unknown')}")
                print(f"   Pool size: {data.get('pool', {}).get('size', 0)}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False


async def test_positions_tropical():
    """Test tropical positions calculation."""
    print("\nTesting tropical positions (Fort Knox 1962)...")

    payload = {
        "when": {"utc": "1962-07-03T04:33:00Z"},
        "system": "tropical",
        "bodies": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
    }

    async with httpx.AsyncClient() as client:
        try:
            start_time = time.perf_counter()
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=20)
            duration = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Tropical positions calculated successfully")
                print(f"   Response time: {duration:.1f}ms")
                print(f"   Bodies calculated: {len(data.get('bodies', []))}")
                print(f"   Ephemeris: {data.get('provenance', {}).get('ephemeris', 'unknown')}")
                print(f"   ETag: {response.headers.get('etag', 'missing')}")

                # Check Sun position (should be around 100° for Fort Knox 1962)
                sun_body = next((b for b in data.get('bodies', []) if b['name'] == 'Sun'), None)
                if sun_body:
                    print(f"   Sun longitude: {sun_body['lon_deg']:.2f}°")

                return True
            else:
                print(f"❌ Tropical positions failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Tropical positions error: {e}")
            return False


async def test_positions_sidereal():
    """Test sidereal positions calculation."""
    print("\nTesting sidereal positions with Fagan-Bradley ayanāṃśa...")

    payload = {
        "when": {"utc": "1962-07-03T04:33:00Z"},
        "system": "sidereal",
        "ayanamsha": {"id": "FAGAN_BRADLEY_DYNAMIC"},
        "bodies": ["Sun", "Moon"]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=20)

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Sidereal positions calculated successfully")
                print(f"   Ayanāṃśa: {data.get('provenance', {}).get('ayanamsha', {}).get('id', 'unknown')}")
                print(f"   Ayanāṃśa value: {data.get('provenance', {}).get('ayanamsha', {}).get('value_deg', 0):.2f}°")

                # Check Sun position (should be ~24° less than tropical)
                sun_body = next((b for b in data.get('bodies', []) if b['name'] == 'Sun'), None)
                if sun_body:
                    print(f"   Sun longitude (sidereal): {sun_body['lon_deg']:.2f}°")

                return True
            else:
                print(f"❌ Sidereal positions failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Sidereal positions error: {e}")
            return False


async def test_time_resolution():
    """Test time resolution endpoint."""
    print("\nTesting time resolution (local to UTC)...")

    payload = {
        "local_datetime": "1962-07-02T23:33:00",
        "place": {
            "name": "Fort Knox, Kentucky",
            "lat": 37.840347,
            "lon": -85.949127
        },
        "parity_profile": "strict_history"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/v1/time/resolve", json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Time resolution successful")
                print(f"   UTC result: {data.get('utc', 'unknown')}")
                print(f"   TZDB version: {data.get('provenance', {}).get('tzdb_version', 'unknown')}")

                # Should convert to 1962-07-03T04:33:00Z (CST + 6 hours)
                expected = "1962-07-03T04:33:00Z"
                if data.get('utc') == expected:
                    print(f"   ✅ Conversion correct (CST to UTC)")
                else:
                    print(f"   ⚠️  Expected {expected}, got {data.get('utc')}")

                return True
            else:
                print(f"❌ Time resolution failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Time resolution error: {e}")
            return False


async def test_geocoding():
    """Test geocoding search endpoint."""
    print("\nTesting geocoding search...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/v1/geocode/search",
                params={"q": "Fort Knox Kentucky", "limit": 3},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                print(f"✅ Geocoding search successful")
                print(f"   Results found: {len(results)}")

                if results:
                    first_result = results[0]
                    print(f"   First result: {first_result.get('name', 'unnamed')}")
                    print(f"   Coordinates: {first_result.get('lat', 0):.3f}, {first_result.get('lon', 0):.3f}")

                return True
            else:
                print(f"❌ Geocoding search failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Geocoding search error: {e}")
            return False


async def test_error_handling():
    """Test error handling with invalid request."""
    print("\nTesting error handling...")

    # Test sidereal without ayanāṃśa (should be error)
    payload = {
        "when": {"utc": "1962-07-03T04:33:00Z"},
        "system": "sidereal",  # Missing ayanamsha
        "bodies": ["Sun"]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

            if response.status_code == 400:
                error_data = response.json()
                print(f"✅ Error handling working correctly")
                print(f"   Error code: {error_data.get('code', 'unknown')}")
                print(f"   Error title: {error_data.get('title', 'unknown')}")
                print(f"   Has tip: {'tip' in error_data}")
                return True
            else:
                print(f"❌ Expected 400 error, got {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error handling test error: {e}")
            return False


async def test_caching():
    """Test caching functionality."""
    print("\nTesting caching (ETag consistency)...")

    payload = {
        "when": {"utc": "1962-07-03T04:33:00Z"},
        "system": "tropical",
        "bodies": ["Sun", "Moon"]
    }

    async with httpx.AsyncClient() as client:
        try:
            # First request
            response1 = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

            if response1.status_code == 200:
                etag1 = response1.headers.get('etag')

                # Second identical request
                response2 = await client.post(f"{BASE_URL}/v1/positions", json=payload, timeout=10)

                if response2.status_code == 200:
                    etag2 = response2.headers.get('etag')

                    if etag1 and etag2 and etag1 == etag2:
                        print(f"✅ Caching working correctly")
                        print(f"   ETag consistency: {etag1}")
                        return True
                    else:
                        print(f"❌ ETag mismatch: {etag1} vs {etag2}")
                        return False
                else:
                    print(f"❌ Second request failed: {response2.status_code}")
                    return False
            else:
                print(f"❌ First request failed: {response1.status_code}")
                return False

        except Exception as e:
            print(f"❌ Caching test error: {e}")
            return False


async def main():
    """Run all validation tests."""
    print("🚀 Involution Engine v1.1 Validation")
    print("=" * 50)

    tests = [
        ("Health Check", test_health_check),
        ("Tropical Positions", test_positions_tropical),
        ("Sidereal Positions", test_positions_sidereal),
        ("Time Resolution", test_time_resolution),
        ("Geocoding", test_geocoding),
        ("Error Handling", test_error_handling),
        ("Caching", test_caching),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if await test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Validation Summary: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Service is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the service configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))