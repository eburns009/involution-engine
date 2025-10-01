#!/usr/bin/env python3
"""
Quick Accuracy Check
Simple validation script for regular system accuracy monitoring
"""

import json
import os
import sys
from datetime import datetime

import requests

# Quick test charts for validation
VALIDATION_CHARTS = [
    {
        "name": "Modern Reference 1",
        "birth_time": "1975-06-15T14:30:00Z",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "expected_sun_tropical": 84.25,  # Approximate
        "expected_ayanamsa": 23.7,       # Approximate Fagan-Bradley for 1975
        "tolerance_deg": 0.5
    },
    {
        "name": "Modern Reference 2",
        "birth_time": "1990-12-25T12:00:00Z",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "expected_sun_tropical": 273.5,  # Approximate
        "expected_ayanamsa": 24.0,       # Approximate Fagan-Bradley for 1990
        "tolerance_deg": 0.5
    },
    {
        "name": "Modern Reference 3",
        "birth_time": "2000-01-01T00:00:00Z",
        "latitude": 35.6762,
        "longitude": 139.6503,
        "expected_sun_tropical": 280.0,  # Approximate
        "expected_ayanamsa": 24.2,       # Approximate Fagan-Bradley for 2000
        "tolerance_deg": 0.5
    }
]

def quick_system_check(spice_url: str = "http://localhost:8000") -> dict:
    """Perform quick system accuracy check"""
    print("🔍 Quick System Accuracy Check")
    print("=============================")

    results = {
        "timestamp": datetime.now().isoformat(),
        "service_status": "unknown",
        "total_tests": len(VALIDATION_CHARTS),
        "passed_tests": 0,
        "failed_tests": 0,
        "accuracy_issues": [],
        "performance_metrics": {
            "avg_response_time": 0,
            "total_time": 0
        },
        "detailed_results": []
    }

    start_time = datetime.now()

    # Check service health
    try:
        health_response = requests.get(f"{spice_url}/health", timeout=5)
        if health_response.status_code == 200:
            results["service_status"] = "healthy"
            print("✅ Service health check passed")
        else:
            results["service_status"] = "unhealthy"
            print(f"❌ Service unhealthy: {health_response.status_code}")
            return results
    except Exception as e:
        results["service_status"] = "unreachable"
        print(f"❌ Service unreachable: {e}")
        return results

    # Test each validation chart
    response_times = []

    for i, chart in enumerate(VALIDATION_CHARTS, 1):
        print(f"\n📊 Test {i}: {chart['name']}")

        test_result = {
            "chart_name": chart["name"],
            "success": False,
            "errors": [],
            "measurements": {}
        }

        try:
            # Test tropical calculation
            calc_start = datetime.now()
            tropical_response = requests.post(
                f"{spice_url}/calculate",
                json={
                    "birth_time": chart["birth_time"],
                    "latitude": chart["latitude"],
                    "longitude": chart["longitude"],
                    "zodiac": "tropical"
                },
                timeout=10
            )
            calc_time = (datetime.now() - calc_start).total_seconds()
            response_times.append(calc_time)

            if tropical_response.status_code != 200:
                test_result["errors"].append(f"Tropical calculation failed: {tropical_response.status_code}")
                print("  ❌ Tropical calculation failed")
                results["detailed_results"].append(test_result)
                results["failed_tests"] += 1
                continue

            tropical_data = tropical_response.json()

            # Test sidereal calculation
            sidereal_response = requests.post(
                f"{spice_url}/calculate",
                json={
                    "birth_time": chart["birth_time"],
                    "latitude": chart["latitude"],
                    "longitude": chart["longitude"],
                    "zodiac": "sidereal",
                    "ayanamsa": "fagan_bradley"
                },
                timeout=10
            )

            if sidereal_response.status_code != 200:
                test_result["errors"].append(f"Sidereal calculation failed: {sidereal_response.status_code}")
                print("  ❌ Sidereal calculation failed")
                results["detailed_results"].append(test_result)
                results["failed_tests"] += 1
                continue

            sidereal_data = sidereal_response.json()

            # Validate results
            tropical_sun = tropical_data["data"]["Sun"]["longitude"]
            sidereal_sun = sidereal_data["data"]["Sun"]["longitude"]
            ayanamsa = sidereal_data["meta"]["ayanamsa_deg"]

            # Check sun position accuracy
            sun_error = abs(tropical_sun - chart["expected_sun_tropical"])
            if sun_error > 180:  # Handle 360° wraparound
                sun_error = 360 - sun_error

            # Check ayanamsa accuracy
            ayanamsa_error = abs(ayanamsa - chart["expected_ayanamsa"])

            # Check tropical vs sidereal consistency
            tropical_sidereal_diff = abs(tropical_sun - sidereal_sun)
            if tropical_sidereal_diff > 180:
                tropical_sidereal_diff = 360 - tropical_sidereal_diff
            ayanamsa_consistency_error = abs(tropical_sidereal_diff - ayanamsa)

            test_result["measurements"] = {
                "tropical_sun_longitude": tropical_sun,
                "sidereal_sun_longitude": sidereal_sun,
                "ayanamsa": ayanamsa,
                "sun_position_error_deg": sun_error,
                "ayanamsa_error_deg": ayanamsa_error,
                "consistency_error_deg": ayanamsa_consistency_error,
                "response_time_sec": calc_time
            }

            # Determine if test passed
            tolerance = chart["tolerance_deg"]
            if (sun_error <= tolerance and
                ayanamsa_error <= tolerance and
                ayanamsa_consistency_error <= 0.1):  # 6 arcminutes
                test_result["success"] = True
                results["passed_tests"] += 1
                print(f"  ✅ Passed (Sun: {sun_error:.3f}°, Ayanamsa: {ayanamsa_error:.3f}°)")
            else:
                test_result["success"] = False
                results["failed_tests"] += 1
                accuracy_issue = f"{chart['name']}: Sun error {sun_error:.3f}°, Ayanamsa error {ayanamsa_error:.3f}°"
                results["accuracy_issues"].append(accuracy_issue)
                print(f"  ❌ Failed (Sun: {sun_error:.3f}°, Ayanamsa: {ayanamsa_error:.3f}°)")

        except Exception as e:
            test_result["errors"].append(str(e))
            results["failed_tests"] += 1
            print(f"  ❌ Test error: {e}")

        results["detailed_results"].append(test_result)

    # Calculate performance metrics
    total_time = (datetime.now() - start_time).total_seconds()
    results["performance_metrics"]["total_time"] = total_time
    if response_times:
        results["performance_metrics"]["avg_response_time"] = sum(response_times) / len(response_times)

    return results

def print_summary(results: dict):
    """Print test summary"""
    print(f"\n{'='*50}")
    print("📋 QUICK ACCURACY CHECK SUMMARY")
    print(f"{'='*50}")

    passed = results["passed_tests"]
    total = results["total_tests"]
    success_rate = (passed / total * 100) if total > 0 else 0

    print(f"🎯 Overall: {passed}/{total} tests passed ({success_rate:.1f}%)")
    print(f"⏱️  Total time: {results['performance_metrics']['total_time']:.2f}s")
    print(f"📡 Avg response: {results['performance_metrics']['avg_response_time']:.3f}s")

    if results["accuracy_issues"]:
        print("\n⚠️  Accuracy Issues:")
        for issue in results["accuracy_issues"]:
            print(f"   • {issue}")

    # Status recommendation
    if success_rate >= 100:
        status = "🟢 EXCELLENT"
        recommendation = "System accuracy is optimal"
    elif success_rate >= 80:
        status = "🟡 GOOD"
        recommendation = "System accuracy is acceptable"
    elif success_rate >= 60:
        status = "🟠 FAIR"
        recommendation = "Consider accuracy review"
    else:
        status = "🔴 POOR"
        recommendation = "Immediate accuracy investigation required"

    print(f"\n{status}")
    print(f"💡 Recommendation: {recommendation}")
    print(f"{'='*50}")

def main():
    """Main execution function"""
    spice_url = os.environ.get("SPICE_URL", "http://localhost:8000")

    # Run quick check
    results = quick_system_check(spice_url)

    # Print summary
    print_summary(results)

    # Save results
    output_file = f"quick_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Detailed results saved: {output_file}")

    # Return exit code based on results
    success_rate = (results["passed_tests"] / results["total_tests"] * 100) if results["total_tests"] > 0 else 0
    if success_rate >= 80:
        return 0  # Success
    else:
        return 1  # Failure

if __name__ == "__main__":
    sys.exit(main())
