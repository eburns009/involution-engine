#!/usr/bin/env python3
"""
Batch Position Computation Script
Computes planetary positions for multiple charts using the SPICE engine.
"""

import csv
import os
import sys
import time
from pathlib import Path

import requests


def resolve_time(local_datetime, lat, lon, engine_base="http://localhost:8000"):
    """Resolve local time to UTC using the time resolver."""
    payload = {
        "local_datetime": local_datetime,
        "latitude": lat,
        "longitude": lon,
        "parity_profile": "strict_history"
    }

    response = requests.post(f"{engine_base}/v1/time/resolve", json=payload)
    response.raise_for_status()
    return response.json()

def compute_positions(utc_time, lat, lon, zodiac, ayanamsa, engine_base="http://localhost:8000"):
    """Compute planetary positions for a given UTC time and location."""
    payload = {
        "birth_time": utc_time,
        "latitude": lat,
        "longitude": lon,
        "elevation": 0.0,
        "zodiac": zodiac,
        "ayanamsa": ayanamsa,
        "parity_profile": "strict_history"
    }

    response = requests.post(f"{engine_base}/calculate", json=payload)
    response.raise_for_status()
    return response.json()

def process_chart(row, engine_base="http://localhost:8000"):
    """Process a single chart from the input CSV."""
    name = row['name']
    local_datetime = row['local_datetime']
    lat = float(row['lat'])
    lon = float(row['lon'])
    systems = row['systems'].split(',')

    print(f"Processing {name}...")

    # Resolve time
    time_info = resolve_time(local_datetime, lat, lon, engine_base)
    utc_time = time_info['utc']

    results = []

    for system in systems:
        system = system.strip()

        if system == 'tropical':
            zodiac = 'tropical'
            ayanamsa = 'lahiri'  # Doesn't matter for tropical
        elif system == 'sidereal_fb':
            zodiac = 'sidereal'
            ayanamsa = 'fagan_bradley'
        else:
            print(f"Unknown system: {system}")
            continue

        # Compute positions
        positions = compute_positions(utc_time, lat, lon, zodiac, ayanamsa, engine_base)
        time.sleep(0.5)  # Small delay between systems

        # Extract planetary data
        for body, data in positions['data'].items():
            results.append({
                'name': name,
                'system': system,
                'utc': utc_time,
                'body': body,
                'lon_deg': data['longitude'],
                'lat_deg': data['latitude'],
                'distance': data['distance']
            })

    return results

def main():
    if len(sys.argv) != 3:
        print("Usage: python batch_compute_positions.py <input_csv> <output_dir>")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    engine_base = os.getenv('ENGINE_BASE', 'http://localhost:8000')

    print(f"Reading input from: {input_csv}")
    print(f"Output directory: {output_dir}")
    print(f"Engine base: {engine_base}")

    all_results = []

    with open(input_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                chart_results = process_chart(row, engine_base)
                all_results.extend(chart_results)
                time.sleep(1.0)  # Longer delay to avoid rate limits
            except Exception as e:
                print(f"Error processing {row['name']}: {e}")

    # Write tidy format
    tidy_file = output_dir / 'positions_tidy.csv'
    with open(tidy_file, 'w', newline='') as f:
        if all_results:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)

    print(f"Tidy output written to: {tidy_file}")

    # Write wide format (pivot by body)
    wide_file = output_dir / 'positions_wide.csv'

    # Group by name and system
    wide_data = {}
    for result in all_results:
        key = (result['name'], result['system'])
        if key not in wide_data:
            wide_data[key] = {
                'name': result['name'],
                'system': result['system'],
                'utc': result['utc']
            }
        wide_data[key][f"{result['body']}_lon"] = result['lon_deg']
        wide_data[key][f"{result['body']}_lat"] = result['lat_deg']
        wide_data[key][f"{result['body']}_dist"] = result['distance']

    if wide_data:
        with open(wide_file, 'w', newline='') as f:
            # Get all possible fieldnames
            all_fields = set()
            for row in wide_data.values():
                all_fields.update(row.keys())

            fieldnames = ['name', 'system', 'utc'] + sorted([f for f in all_fields if f not in ['name', 'system', 'utc']])

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(wide_data.values())

    print(f"Wide output written to: {wide_file}")
    print(f"Processed {len(set((r['name'], r['system']) for r in all_results))} charts")

if __name__ == '__main__':
    main()
