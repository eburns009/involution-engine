#!/usr/bin/env python3
"""
Drift Detection System for Involution Engine

Compares engine output against Swiss Ephemeris golden reference data
to detect calculation drift over time. Runs weekly and fails on
tolerance breaches.
"""

import os
import json
import time
import pandas as pd
import numpy as np
import requests
import pathlib
import sys
from typing import Dict, Any, Tuple

ENGINE_BASE = os.getenv("ENGINE_BASE", "http://localhost:8080")
REF_PATH = os.getenv("DRIFT_REF", "tests/goldens/golden_positions.csv")
OUT_DIR = os.getenv("DRIFT_OUT", "ops/drift/out")

BODIES = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "TrueNode", "MeanNode"
]

# Tolerance thresholds (arcminutes)
TOLERANCES = {
    "Moon": 30.0,       # Moon: 30 arcminutes
    "TrueNode": 5.0,    # Nodes: 5 arcminutes
    "MeanNode": 5.0,
    "default": 1.0      # All other bodies: 1 arcminute
}


def fetch_positions(row: pd.Series) -> Tuple[float, Dict[str, Any]]:
    """
    Fetch position from engine for a given test case.

    Args:
        row: Test case row with utc, system, body, etc.

    Returns:
        Tuple of (longitude_degrees, provenance_dict)
    """
    payload = {
        "when": {"utc": row["utc"]},
        "system": row["system"],
        "bodies": [row["body"]],
    }

    # Add ayanāṃśa for sidereal system
    if row["system"] == "sidereal":
        ayanamsha_id = row.get("ayanamsha_id", "lahiri")
        payload["ayanamsha"] = {"id": ayanamsha_id}

    try:
        response = requests.post(
            f"{ENGINE_BASE}/v1/positions",
            json=payload,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        # Extract longitude from first body
        body_data = data["bodies"][0]
        longitude = body_data["lon_deg"]
        provenance = data.get("provenance", {})

        return longitude, provenance

    except requests.RequestException as e:
        print(f"Error fetching position for {row['name']}: {e}")
        raise
    except (KeyError, IndexError) as e:
        print(f"Error parsing response for {row['name']}: {e}")
        raise


def arcmin_diff(a: float, b: float) -> float:
    """
    Calculate angular difference in arcminutes on circle [0..360).

    Args:
        a: First angle in degrees
        b: Second angle in degrees

    Returns:
        Absolute difference in arcminutes
    """
    # Normalize difference to [-180, 180] degrees, then to arcminutes
    diff = (a - b + 540) % 360 - 180
    return abs(diff) * 60.0


def get_tolerance(body: str) -> float:
    """Get tolerance threshold for a body in arcminutes."""
    return TOLERANCES.get(body, TOLERANCES["default"])


def analyze_drift() -> Dict[str, Any]:
    """
    Main drift analysis function.

    Returns:
        Summary dictionary with results
    """
    print(f"Starting drift analysis...")
    print(f"Engine base URL: {ENGINE_BASE}")
    print(f"Reference data: {REF_PATH}")
    print(f"Output directory: {OUT_DIR}")

    # Ensure output directory exists
    os.makedirs(OUT_DIR, exist_ok=True)

    # Load reference data
    if not os.path.exists(REF_PATH):
        raise FileNotFoundError(f"Reference data not found: {REF_PATH}")

    ref_df = pd.read_csv(REF_PATH)
    print(f"Loaded {len(ref_df)} reference positions")

    # Analyze each test case
    results = []
    failures = 0
    total_tests = len(ref_df)

    for idx, row in ref_df.iterrows():
        try:
            # Fetch position from engine
            engine_lon, provenance = fetch_positions(row)

            # Calculate difference
            ref_lon = row["lon_deg"]
            diff_arcmin = arcmin_diff(engine_lon, ref_lon)

            # Check tolerance
            tolerance = get_tolerance(row["body"])
            is_failure = diff_arcmin > tolerance

            if is_failure:
                failures += 1
                print(f"FAIL: {row['name']} - {diff_arcmin:.2f}' > {tolerance:.1f}' tolerance")

            # Store result
            result = {
                "name": row["name"],
                "system": row["system"],
                "utc": row["utc"],
                "body": row["body"],
                "ref_lon_deg": ref_lon,
                "engine_lon_deg": engine_lon,
                "diff_arcmin": diff_arcmin,
                "tolerance_arcmin": tolerance,
                "is_failure": is_failure,
                "ayanamsha_id": row.get("ayanamsha_id", ""),
                "provenance": json.dumps(provenance, separators=(',', ':'))
            }
            results.append(result)

        except Exception as e:
            print(f"ERROR: Failed to process {row['name']}: {e}")
            failures += 1

            # Add error result
            result = {
                "name": row["name"],
                "system": row["system"],
                "utc": row["utc"],
                "body": row["body"],
                "ref_lon_deg": row["lon_deg"],
                "engine_lon_deg": None,
                "diff_arcmin": None,
                "tolerance_arcmin": get_tolerance(row["body"]),
                "is_failure": True,
                "ayanamsha_id": row.get("ayanamsha_id", ""),
                "provenance": json.dumps({"error": str(e)})
            }
            results.append(result)

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    # Calculate statistics
    valid_diffs = results_df["diff_arcmin"].dropna()

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "engine_base_url": ENGINE_BASE,
        "reference_data": REF_PATH,
        "total_tests": total_tests,
        "successful_tests": len(valid_diffs),
        "failed_tests": failures,
        "error_rate_percent": round((failures / total_tests) * 100, 2),
        "max_diff_arcmin": float(valid_diffs.max()) if len(valid_diffs) > 0 else None,
        "mean_diff_arcmin": float(valid_diffs.mean()) if len(valid_diffs) > 0 else None,
        "p95_diff_arcmin": float(np.percentile(valid_diffs, 95)) if len(valid_diffs) > 0 else None,
        "p99_diff_arcmin": float(np.percentile(valid_diffs, 99)) if len(valid_diffs) > 0 else None,
        "tolerance_breaches": int(results_df["is_failure"].sum()),
        "tolerances_used": TOLERANCES
    }

    # Generate output files
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(OUT_DIR, f"drift_report_{timestamp}.csv")
    json_path = os.path.join(OUT_DIR, f"drift_summary_{timestamp}.json")

    # Save detailed results
    results_df.to_csv(csv_path, index=False)
    print(f"Detailed results saved to: {csv_path}")

    # Save summary
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to: {json_path}")

    # Print summary
    print("\n" + "="*60)
    print("DRIFT DETECTION SUMMARY")
    print("="*60)
    print(f"Total tests: {summary['total_tests']}")
    print(f"Successful: {summary['successful_tests']}")
    print(f"Failed: {summary['failed_tests']} ({summary['error_rate_percent']}%)")
    print(f"Tolerance breaches: {summary['tolerance_breaches']}")

    if len(valid_diffs) > 0:
        print(f"Max difference: {summary['max_diff_arcmin']:.2f}'")
        print(f"Mean difference: {summary['mean_diff_arcmin']:.2f}'")
        print(f"P95 difference: {summary['p95_diff_arcmin']:.2f}'")
        print(f"P99 difference: {summary['p99_diff_arcmin']:.2f}'")

    print("\nTolerance thresholds:")
    for body, tolerance in TOLERANCES.items():
        print(f"  {body}: {tolerance:.1f}'")

    return summary


def main():
    """Main entry point."""
    try:
        summary = analyze_drift()

        # Print final status
        if summary["tolerance_breaches"] > 0:
            print(f"\n❌ DRIFT DETECTED: {summary['tolerance_breaches']} tolerance breaches")
            print("Review the detailed report and investigate drift causes.")
            sys.exit(1)
        else:
            print(f"\n✅ NO DRIFT DETECTED: All positions within tolerance")
            sys.exit(0)

    except Exception as e:
        print(f"\n💥 DRIFT CHECK FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()