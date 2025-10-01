#!/usr/bin/env python3
"""
Accuracy Comparison Script
Compares engine positions against reference data (Astro.com, Swiss Ephemeris, etc.)
"""

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Compare engine positions with reference data')
    parser.add_argument('--engine', required=True, help='Engine positions CSV file (tidy format)')
    parser.add_argument('--reference', required=True, help='Reference positions CSV file (tidy format)')
    parser.add_argument('--out_csv', required=True, help='Output CSV file for detailed comparison')
    parser.add_argument('--out_json', required=True, help='Output JSON file for summary statistics')
    parser.add_argument('--tol_planets_arcmin', type=float, default=1.0, help='Tolerance for planets in arcminutes')
    parser.add_argument('--tol_moon_arcmin', type=float, default=30.0, help='Tolerance for Moon in arcminutes')
    parser.add_argument('--tol_nodes_arcmin', type=float, default=5.0, help='Tolerance for nodes in arcminutes')
    return parser.parse_args()

def arcmin_difference(lon1, lon2):
    """Calculate the shortest angular distance between two longitudes in arcminutes."""
    diff = abs(lon1 - lon2)
    if diff > 180:
        diff = 360 - diff
    return diff * 60  # Convert to arcminutes

def get_tolerance(body, tol_planets, tol_moon, tol_nodes):
    """Get the appropriate tolerance for a celestial body."""
    body_lower = body.lower()
    if 'moon' in body_lower:
        return tol_moon
    elif 'node' in body_lower:
        return tol_nodes
    else:
        return tol_planets

def load_positions_csv(filename):
    """Load positions from CSV file into a dictionary keyed by (name, system, body)."""
    positions = {}

    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['name'], row['system'], row['body'])
            positions[key] = {
                'lon_deg': float(row['lon_deg']),
                'utc': row['utc']
            }

    return positions

def compare_positions(engine_positions, reference_positions, tolerances):
    """Compare engine positions against reference positions."""
    comparisons = []

    # Find all keys that exist in both datasets
    common_keys = set(engine_positions.keys()) & set(reference_positions.keys())

    if not common_keys:
        print("Warning: No common positions found between engine and reference data")
        return comparisons

    for key in sorted(common_keys):
        name, system, body = key

        engine_pos = engine_positions[key]
        ref_pos = reference_positions[key]

        # Calculate difference in arcminutes
        diff_arcmin = arcmin_difference(engine_pos['lon_deg'], ref_pos['lon_deg'])

        # Get tolerance for this body
        tolerance = get_tolerance(body, tolerances['planets'], tolerances['moon'], tolerances['nodes'])

        # Determine pass/fail
        passed = diff_arcmin <= tolerance

        comparison = {
            'name': name,
            'system': system,
            'body': body,
            'engine_lon_deg': engine_pos['lon_deg'],
            'reference_lon_deg': ref_pos['lon_deg'],
            'difference_arcmin': diff_arcmin,
            'tolerance_arcmin': tolerance,
            'passed': passed,
            'status': 'PASS' if passed else 'FAIL',
            'utc': engine_pos['utc']
        }

        comparisons.append(comparison)

    return comparisons

def calculate_summary_stats(comparisons):
    """Calculate summary statistics from comparisons."""
    if not comparisons:
        return {}

    total_comparisons = len(comparisons)
    passed_comparisons = sum(1 for c in comparisons if c['passed'])
    pass_rate = (passed_comparisons / total_comparisons) * 100

    differences = [c['difference_arcmin'] for c in comparisons]

    # Group by body type for detailed stats
    by_body = {}
    for comp in comparisons:
        body = comp['body']
        if body not in by_body:
            by_body[body] = []
        by_body[body].append(comp)

    body_stats = {}
    for body, comps in by_body.items():
        body_diffs = [c['difference_arcmin'] for c in comps]
        body_passed = sum(1 for c in comps if c['passed'])
        body_stats[body] = {
            'count': len(comps),
            'passed': body_passed,
            'pass_rate_percent': (body_passed / len(comps)) * 100,
            'mean_diff_arcmin': statistics.mean(body_diffs),
            'median_diff_arcmin': statistics.median(body_diffs),
            'max_diff_arcmin': max(body_diffs),
            'min_diff_arcmin': min(body_diffs)
        }

    summary = {
        'overall': {
            'total_comparisons': total_comparisons,
            'passed': passed_comparisons,
            'failed': total_comparisons - passed_comparisons,
            'pass_rate_percent': pass_rate
        },
        'difference_stats': {
            'mean_arcmin': statistics.mean(differences),
            'median_arcmin': statistics.median(differences),
            'p95_arcmin': statistics.quantiles(differences, n=20)[18] if len(differences) >= 20 else max(differences),
            'max_arcmin': max(differences),
            'min_arcmin': min(differences)
        },
        'by_body': body_stats
    }

    return summary

def main():
    args = parse_args()

    print(f"Loading engine positions from: {args.engine}")
    engine_positions = load_positions_csv(args.engine)

    print(f"Loading reference positions from: {args.reference}")
    reference_positions = load_positions_csv(args.reference)

    print(f"Engine positions: {len(engine_positions)}")
    print(f"Reference positions: {len(reference_positions)}")

    tolerances = {
        'planets': args.tol_planets_arcmin,
        'moon': args.tol_moon_arcmin,
        'nodes': args.tol_nodes_arcmin
    }

    print(f"Tolerances: Planets ≤{tolerances['planets']:.1f}', Moon ≤{tolerances['moon']:.1f}', Nodes ≤{tolerances['nodes']:.1f}'")

    # Compare positions
    comparisons = compare_positions(engine_positions, reference_positions, tolerances)

    if not comparisons:
        print("No comparisons could be made. Check that the data formats match.")
        return

    # Write detailed comparison CSV
    output_dir = Path(args.out_csv).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.out_csv, 'w', newline='') as f:
        if comparisons:
            writer = csv.DictWriter(f, fieldnames=comparisons[0].keys())
            writer.writeheader()
            writer.writerows(comparisons)

    print(f"Detailed comparison written to: {args.out_csv}")

    # Calculate and write summary statistics
    summary = calculate_summary_stats(comparisons)

    with open(args.out_json, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Summary statistics written to: {args.out_json}")

    # Print summary to console
    print("\n=== ACCURACY SUMMARY ===")
    print(f"Total comparisons: {summary['overall']['total_comparisons']}")
    print(f"Passed: {summary['overall']['passed']}")
    print(f"Failed: {summary['overall']['failed']}")
    print(f"Pass rate: {summary['overall']['pass_rate_percent']:.1f}%")
    print(f"Mean difference: {summary['difference_stats']['mean_arcmin']:.2f} arcmin")
    print(f"P95 difference: {summary['difference_stats']['p95_arcmin']:.2f} arcmin")
    print(f"Worst case: {summary['difference_stats']['max_arcmin']:.2f} arcmin")

    print("\n=== BY BODY ===")
    for body, stats in summary['by_body'].items():
        status = "✓" if stats['pass_rate_percent'] == 100 else "✗"
        print(f"{status} {body}: {stats['pass_rate_percent']:.1f}% pass ({stats['passed']}/{stats['count']}) - "
              f"mean {stats['mean_diff_arcmin']:.2f}', max {stats['max_diff_arcmin']:.2f}'")

    # Exit with non-zero code if any tests failed
    if summary['overall']['failed'] > 0:
        print(f"\n❌ {summary['overall']['failed']} tests failed")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")

if __name__ == '__main__':
    main()
