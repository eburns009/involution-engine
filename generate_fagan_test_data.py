#!/usr/bin/env python3
"""
Generate Fagan-Bradley Test Data
Compute tropical and sidereal positions for all test dates
"""

import json
import requests
from datetime import datetime
import sys
import os

# Test dates and reference coordinates (using Greenwich for consistency)
TEST_DATES = [
    "1950-01-01T00:00:00Z",
    "1962-07-03T03:33:00Z",
    "2000-01-01T00:00:00Z",
    "2025-01-01T00:00:00Z"
]

# All required celestial bodies
BODIES = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "True Node", "Mean Node"
]

# Reference Fagan-Bradley ayanamsa values (approximate)
REFERENCE_AYANAMSA = {
    "1950-01-01T00:00:00Z": 23.452361,  # Standard reference
    "1962-07-03T03:33:00Z": 24.069,     # From our previous tests
    "2000-01-01T00:00:00Z": 24.184,     # Y2K reference
    "2025-01-01T00:00:00Z": 24.442      # Current era
}

def get_positions(date_str: str, zodiac: str, ayanamsa: str = None) -> dict:
    """Get positions from the spice service"""
    url = "http://localhost:8000/calculate"

    payload = {
        "birth_time": date_str,
        "latitude": 51.4769,    # Greenwich Observatory
        "longitude": -0.0005,
        "elevation": 0.0,
        "zodiac": zodiac
    }

    if ayanamsa:
        payload["ayanamsa"] = ayanamsa

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def extract_longitudes(response_data: dict) -> dict:
    """Extract longitude values from response"""
    if not response_data or "data" not in response_data:
        return {}

    longitudes = {}
    for body, data in response_data["data"].items():
        if "longitude" in data:
            longitudes[body] = data["longitude"]

    return longitudes

def create_output_files():
    """Generate all test data files"""
    suite_dir = "fagan_multi_date_suite"

    print("🔭 Generating Fagan-Bradley Multi-Date Test Suite")
    print("=" * 60)

    for date_str in TEST_DATES:
        print(f"\n📅 Processing: {date_str}")

        # Generate filename prefix
        date_prefix = date_str.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")

        # Get tropical positions
        print("  🌍 Computing tropical positions...")
        tropical_response = get_positions(date_str, "tropical")
        if tropical_response:
            tropical_longitudes = extract_longitudes(tropical_response)

            # Save tropical positions
            tropical_file = f"{suite_dir}/{date_prefix}_engine_tropical.json"
            with open(tropical_file, 'w') as f:
                json.dump(tropical_longitudes, f, indent=2)
            print(f"    ✅ Saved: {tropical_file}")
        else:
            print("    ❌ Tropical calculation failed")
            continue

        # Get sidereal positions (Fagan-Bradley)
        print("  🌟 Computing sidereal positions (Fagan-Bradley)...")
        sidereal_response = get_positions(date_str, "sidereal", "fagan_bradley")
        if sidereal_response:
            sidereal_longitudes = extract_longitudes(sidereal_response)
            ayanamsa_value = sidereal_response.get("meta", {}).get("ayanamsa_deg", 0)

            # Save sidereal positions
            sidereal_file = f"{suite_dir}/{date_prefix}_engine_sidereal_FB.json"
            with open(sidereal_file, 'w') as f:
                json.dump(sidereal_longitudes, f, indent=2)
            print(f"    ✅ Saved: {sidereal_file}")

            # Save ayanamsa reference
            ayanamsa_file = f"{suite_dir}/{date_prefix}_ayanamsha_FB_reference.json"
            ayanamsa_data = {
                "calculated_ayanamsa": ayanamsa_value,
                "reference_ayanamsa": REFERENCE_AYANAMSA.get(date_str, 0),
                "difference_arcsec": (ayanamsa_value - REFERENCE_AYANAMSA.get(date_str, 0)) * 3600
            }
            with open(ayanamsa_file, 'w') as f:
                json.dump(ayanamsa_data, f, indent=2)
            print(f"    ✅ Saved: {ayanamsa_file}")
            print(f"    📊 Ayanamsa: {ayanamsa_value:.6f}° (ref: {REFERENCE_AYANAMSA.get(date_str, 0):.6f}°)")
        else:
            print("    ❌ Sidereal calculation failed")

def create_checker_script():
    """Create the test checker script"""
    checker_content = '''#!/usr/bin/env python3
"""
Fagan-Bradley Multi-Date Test Checker
"""

import json
import glob
import argparse
import sys
import os
from typing import Dict, List, Tuple

def load_json_file(filepath: str) -> dict:
    """Load JSON file safely"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}

def calculate_angular_difference(angle1: float, angle2: float) -> float:
    """Calculate angular difference handling 360° wraparound"""
    diff = angle1 - angle2
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return abs(diff)

def check_date_consistency(suite_dir: str, date_prefix: str, tol_arcsec: float) -> Dict:
    """Check tropical vs sidereal consistency for one date"""

    tropical_file = f"{suite_dir}/{date_prefix}_engine_tropical.json"
    sidereal_file = f"{suite_dir}/{date_prefix}_engine_sidereal_FB.json"
    ayanamsa_file = f"{suite_dir}/{date_prefix}_ayanamsha_FB_reference.json"

    # Load data
    tropical_data = load_json_file(tropical_file)
    sidereal_data = load_json_file(sidereal_file)
    ayanamsa_data = load_json_file(ayanamsa_file)

    if not tropical_data or not sidereal_data:
        return {"error": f"Missing data files for {date_prefix}"}

    results = {
        "date_prefix": date_prefix,
        "total_bodies": 0,
        "passed": 0,
        "failed": 0,
        "max_residual_arcsec": 0,
        "ayanamsa_calculated": ayanamsa_data.get("calculated_ayanamsa", 0),
        "ayanamsa_reference": ayanamsa_data.get("reference_ayanamsa", 0),
        "body_results": []
    }

    # Get common bodies
    common_bodies = set(tropical_data.keys()) & set(sidereal_data.keys())

    for body in sorted(common_bodies):
        tropical_lon = tropical_data[body]
        sidereal_lon = sidereal_data[body]

        # Calculate difference
        diff_deg = calculate_angular_difference(tropical_lon, sidereal_lon)
        diff_arcsec = diff_deg * 3600

        # Expected difference should be close to ayanamsa
        expected_diff = ayanamsa_data.get("calculated_ayanamsa", 24.0)
        residual_deg = abs(diff_deg - expected_diff)
        residual_arcsec = residual_deg * 3600

        # Check tolerance
        passed = residual_arcsec <= tol_arcsec

        body_result = {
            "body": body,
            "tropical_lon": tropical_lon,
            "sidereal_lon": sidereal_lon,
            "difference_deg": diff_deg,
            "expected_ayanamsa": expected_diff,
            "residual_arcsec": residual_arcsec,
            "passed": passed
        }

        results["body_results"].append(body_result)
        results["total_bodies"] += 1

        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1

        results["max_residual_arcsec"] = max(results["max_residual_arcsec"], residual_arcsec)

    return results

def run_full_suite(suite_dir: str, tol_arcsec: float):
    """Run the complete test suite"""

    print("🔍 FAGAN-BRADLEY MULTI-DATE TEST SUITE")
    print("=" * 50)

    # Find all date prefixes
    tropical_files = glob.glob(f"{suite_dir}/*_engine_tropical.json")
    date_prefixes = []

    for filepath in tropical_files:
        filename = os.path.basename(filepath)
        date_prefix = filename.replace("_engine_tropical.json", "")
        date_prefixes.append(date_prefix)

    date_prefixes.sort()

    if not date_prefixes:
        print(f"❌ No test files found in {suite_dir}")
        return 1

    print(f"📅 Found {len(date_prefixes)} test dates")
    print(f"🎯 Tolerance: {tol_arcsec} arcseconds")

    all_results = []
    total_passed = 0
    total_failed = 0
    overall_max_residual = 0

    # Process each date
    for date_prefix in date_prefixes:
        print(f"\\n📊 Testing {date_prefix}...")
        result = check_date_consistency(suite_dir, date_prefix, tol_arcsec)

        if "error" in result:
            print(f"   ❌ {result['error']}")
            continue

        all_results.append(result)
        total_passed += result["passed"]
        total_failed += result["failed"]
        overall_max_residual = max(overall_max_residual, result["max_residual_arcsec"])

        print(f"   Results: {result['passed']}/{result['total_bodies']} passed")
        print(f"   Max residual: {result['max_residual_arcsec']:.3f}″")
        print(f"   Ayanamsa: {result['ayanamsa_calculated']:.6f}° (ref: {result['ayanamsa_reference']:.6f}°)")

    # Print summary
    print(f"\\n" + "="*50)
    print("📋 SUMMARY")
    print("="*50)
    print(f"Total bodies tested: {total_passed + total_failed}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Success rate: {total_passed/(total_passed + total_failed)*100:.1f}%")
    print(f"Max residual: {overall_max_residual:.3f}″")
    print(f"Tolerance: {tol_arcsec}″")

    if total_failed == 0:
        print("\\n✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"\\n❌ {total_failed} TESTS FAILED")
        return 1

def main():
    parser = argparse.ArgumentParser(description='Run Fagan-Bradley multi-date test suite')
    parser.add_argument('--suite-dir', required=True, help='Test suite directory')
    parser.add_argument('--tol_arcsec', type=float, default=1.0, help='Tolerance in arcseconds')

    args = parser.parse_args()

    if not os.path.exists(args.suite_dir):
        print(f"Error: Directory {args.suite_dir} does not exist")
        return 1

    return run_full_suite(args.suite_dir, args.tol_arcsec)

if __name__ == "__main__":
    sys.exit(main())
'''

    with open("fagan_multi_date_suite/run_fagan_multi_date_check.py", 'w') as f:
        f.write(checker_content)

    # Make it executable
    os.chmod("fagan_multi_date_suite/run_fagan_multi_date_check.py", 0o755)
    print("✅ Created test checker script")

def main():
    """Main execution"""
    # Create output directory
    os.makedirs("fagan_multi_date_suite", exist_ok=True)

    # Generate all test data
    create_output_files()

    # Create checker script
    create_checker_script()

    print(f"\n🎯 Test suite ready!")
    print(f"📁 Files created in: fagan_multi_date_suite/")
    print(f"🔍 Run checker with:")
    print(f"   python fagan_multi_date_suite/run_fagan_multi_date_check.py --suite-dir fagan_multi_date_suite --tol_arcsec 1")

if __name__ == "__main__":
    main()