#!/usr/bin/env python3
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
        print(f"\n📊 Testing {date_prefix}...")
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
    print(f"\n" + "="*50)
    print("📋 SUMMARY")
    print("="*50)
    print(f"Total bodies tested: {total_passed + total_failed}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Success rate: {total_passed/(total_passed + total_failed)*100:.1f}%")
    print(f"Max residual: {overall_max_residual:.3f}″")
    print(f"Tolerance: {tol_arcsec}″")

    if total_failed == 0:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n❌ {total_failed} TESTS FAILED")
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
