#!/usr/bin/env python3
"""
Time Resolver Audit Runner
Tests the Time Resolver API against expected results
"""

import argparse
import csv
import json
import requests
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional


def parse_args():
    parser = argparse.ArgumentParser(description='Run Time Resolver audit tests')
    parser.add_argument('--base-url', default='http://localhost:8000',
                       help='Base URL for the Time Resolver API')
    parser.add_argument('--input-csv', required=True,
                       help='Input CSV file with test cases')
    parser.add_argument('--out-csv', required=True,
                       help='Output CSV file for results')
    return parser.parse_args()


def load_test_cases(csv_file: str) -> List[Dict[str, Any]]:
    """Load test cases from CSV file"""
    test_cases = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)
    return test_cases


def run_test_case(base_url: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single test case against the API"""
    endpoint = f"{base_url}/v1/time/resolve"

    # Build request payload
    payload = {
        "local_datetime": test_case["local_datetime"],
        "latitude": float(test_case["latitude"]),
        "longitude": float(test_case["longitude"]),
        "parity_profile": test_case["parity_profile"]
    }

    # Add optional fields if present
    if test_case.get("user_provided_zone"):
        payload["user_provided_zone"] = test_case["user_provided_zone"]

    if test_case.get("user_provided_offset"):
        payload["user_provided_offset"] = int(test_case["user_provided_offset"])

    # Make API call
    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        # Compare with expected results
        comparisons = {
            "utc_match": result.get("utc") == test_case.get("expected_utc"),
            "zone_id_match": result.get("zone_id") == test_case.get("expected_zone_id"),
            "offset_match": result.get("offset_seconds") == int(test_case.get("expected_offset_seconds", 0)),
            "dst_match": result.get("dst_active") == (test_case.get("expected_dst_active", "").lower() == "true")
        }

        # Calculate overall pass/fail
        all_match = all(comparisons.values())

        return {
            "test_name": test_case["test_name"],
            "status": "PASS" if all_match else "FAIL",
            "api_response": result,
            "comparisons": comparisons,
            "error": None
        }

    except Exception as e:
        return {
            "test_name": test_case["test_name"],
            "status": "ERROR",
            "api_response": None,
            "comparisons": {},
            "error": str(e)
        }


def write_results(results: List[Dict[str, Any]], output_file: str):
    """Write results to CSV file"""
    fieldnames = [
        "test_name", "status", "utc_match", "zone_id_match", "offset_match", "dst_match",
        "actual_utc", "expected_utc", "actual_zone_id", "expected_zone_id",
        "actual_offset", "expected_offset", "actual_dst", "expected_dst",
        "confidence", "reason", "warnings", "patches_applied", "error"
    ]

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            row = {
                "test_name": result["test_name"],
                "status": result["status"],
                "error": result.get("error", "")
            }

            if result["api_response"]:
                api = result["api_response"]
                row.update({
                    "actual_utc": api.get("utc", ""),
                    "actual_zone_id": api.get("zone_id", ""),
                    "actual_offset": api.get("offset_seconds", ""),
                    "actual_dst": api.get("dst_active", ""),
                    "confidence": api.get("confidence", ""),
                    "reason": api.get("reason", ""),
                    "warnings": "; ".join(api.get("warnings", [])),
                    "patches_applied": "; ".join(api.get("provenance", {}).get("patches_applied", []))
                })

                # Add comparison results
                for key, value in result["comparisons"].items():
                    row[key] = "YES" if value else "NO"

            writer.writerow(row)


def main():
    args = parse_args()

    print(f"Loading test cases from {args.input_csv}")
    test_cases = load_test_cases(args.input_csv)
    print(f"Loaded {len(test_cases)} test cases")

    print(f"Running tests against {args.base_url}")
    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"Running test {i}/{len(test_cases)}: {test_case['test_name']}")
        result = run_test_case(args.base_url, test_case)
        results.append(result)

        status_emoji = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
        print(f"  {status_emoji} {result['status']}")

        if result["status"] == "ERROR":
            print(f"    Error: {result['error']}")
        elif result["status"] == "FAIL":
            failed_checks = [k for k, v in result["comparisons"].items() if not v]
            print(f"    Failed: {', '.join(failed_checks)}")

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    print(f"\n📊 Test Summary:")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  ⚠️  Errors: {errors}")
    print(f"  📊 Total:  {len(results)}")

    print(f"\nWriting results to {args.out_csv}")
    write_results(results, args.out_csv)

    # Exit with error code if any tests failed
    sys.exit(0 if failed == 0 and errors == 0 else 1)


if __name__ == "__main__":
    main()