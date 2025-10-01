#!/usr/bin/env python3
"""
Planetary Position Comparator
Compare engine output against expected reference values
"""

import json
import csv
import argparse
import sys
from typing import Dict, List, Tuple

def load_json_positions(filename: str) -> Dict[str, float]:
    """Load positions from JSON file"""
    with open(filename, 'r') as f:
        data = json.load(f)

    positions = {}
    for body, info in data.items():
        if isinstance(info, dict) and 'lambda_deg' in info:
            positions[body] = info['lambda_deg']
        elif isinstance(info, (int, float)):
            positions[body] = info

    return positions

def load_csv_positions(filename: str) -> Dict[str, float]:
    """Load positions from CSV file"""
    positions = {}
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            body = row['body']
            lambda_deg = float(row['lambda_deg'])
            positions[body] = lambda_deg

    return positions

def calculate_angular_difference(angle1: float, angle2: float) -> float:
    """Calculate angular difference handling 360° wraparound"""
    diff = angle1 - angle2

    # Handle wraparound
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360

    return abs(diff)

def compare_positions(engine_positions: Dict[str, float],
                     expected_positions: Dict[str, float],
                     planet_tol_arcmin: float = 1.0,
                     moon_tol_arcmin: float = 5.0) -> Tuple[List[Dict], Dict]:
    """Compare engine vs expected positions"""

    results = []
    summary = {
        'total_bodies': 0,
        'passed': 0,
        'failed': 0,
        'planet_tolerance_arcmin': planet_tol_arcmin,
        'moon_tolerance_arcmin': moon_tol_arcmin
    }

    # Get all bodies present in both datasets
    common_bodies = set(engine_positions.keys()) & set(expected_positions.keys())

    for body in sorted(common_bodies):
        engine_deg = engine_positions[body]
        expected_deg = expected_positions[body]

        # Calculate difference in degrees
        diff_deg = calculate_angular_difference(engine_deg, expected_deg)
        diff_arcmin = diff_deg * 60.0  # Convert to arcminutes

        # Determine tolerance based on body
        tolerance_arcmin = moon_tol_arcmin if body.lower() == 'moon' else planet_tol_arcmin

        # Check if within tolerance
        status = 'PASS' if diff_arcmin <= tolerance_arcmin else 'FAIL'

        result = {
            'body': body,
            'engine_deg': engine_deg,
            'expected_deg': expected_deg,
            'diff_arcmin': diff_arcmin,
            'tolerance_arcmin': tolerance_arcmin,
            'status': status
        }

        results.append(result)
        summary['total_bodies'] += 1

        if status == 'PASS':
            summary['passed'] += 1
        else:
            summary['failed'] += 1

    return results, summary

def print_results(results: List[Dict], summary: Dict):
    """Print comparison results in table format"""

    print("\n" + "="*80)
    print("🔍 PLANETARY POSITION COMPARISON")
    print("="*80)

    # Print header
    print(f"{'Body':<10} {'Engine_deg':<12} {'Expected_deg':<13} {'Δ_arcmin':<10} {'Status':<8}")
    print("-" * 80)

    # Print results
    for result in results:
        print(f"{result['body']:<10} "
              f"{result['engine_deg']:<12.6f} "
              f"{result['expected_deg']:<13.6f} "
              f"{result['diff_arcmin']:<10.3f} "
              f"{result['status']:<8}")

    print("-" * 80)

    # Print summary
    print(f"\n📊 SUMMARY:")
    print(f"   Total bodies: {summary['total_bodies']}")
    print(f"   Passed: {summary['passed']}")
    print(f"   Failed: {summary['failed']}")
    print(f"   Success rate: {summary['passed']/summary['total_bodies']*100:.1f}%")
    print(f"   Tolerances: Moon={summary['moon_tolerance_arcmin']}′, Others={summary['planet_tolerance_arcmin']}′")

    # Overall result
    if summary['failed'] == 0:
        print(f"\n✅ ALL TESTS PASSED - Engine accuracy validated!")
    else:
        print(f"\n❌ {summary['failed']} TEST(S) FAILED - Investigation required")
        failed_bodies = [r['body'] for r in results if r['status'] == 'FAIL']
        print(f"   Failed bodies: {', '.join(failed_bodies)}")

    print("="*80)

def main():
    parser = argparse.ArgumentParser(description='Compare planetary positions')
    parser.add_argument('--engine-json', required=True, help='Engine output JSON file')
    parser.add_argument('--expected-json', help='Expected positions JSON file')
    parser.add_argument('--expected-csv', help='Expected positions CSV file')
    parser.add_argument('--planet_tol_arcmin', type=float, default=1.0,
                       help='Tolerance for planets in arcminutes (default: 1.0)')
    parser.add_argument('--moon_tol_arcmin', type=float, default=5.0,
                       help='Tolerance for Moon in arcminutes (default: 5.0)')

    args = parser.parse_args()

    # Validate arguments
    if not args.expected_json and not args.expected_csv:
        print("Error: Must specify either --expected-json or --expected-csv")
        return 1

    if args.expected_json and args.expected_csv:
        print("Error: Specify only one of --expected-json or --expected-csv")
        return 1

    try:
        # Load engine positions
        print(f"Loading engine positions from: {args.engine_json}")
        engine_positions = load_json_positions(args.engine_json)

        # Load expected positions
        if args.expected_json:
            print(f"Loading expected positions from: {args.expected_json}")
            expected_positions = load_json_positions(args.expected_json)
        else:
            print(f"Loading expected positions from: {args.expected_csv}")
            expected_positions = load_csv_positions(args.expected_csv)

        print(f"Engine bodies: {sorted(engine_positions.keys())}")
        print(f"Expected bodies: {sorted(expected_positions.keys())}")

        # Compare positions
        results, summary = compare_positions(
            engine_positions,
            expected_positions,
            args.planet_tol_arcmin,
            args.moon_tol_arcmin
        )

        # Print results
        print_results(results, summary)

        # Return appropriate exit code
        return 0 if summary['failed'] == 0 else 1

    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())