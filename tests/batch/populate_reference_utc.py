#!/usr/bin/env python3
"""
Populates UTC timestamps in reference data by resolving local datetimes
through the time resolver API.
"""

import csv
import os

import requests

# Environment variables with defaults
ENGINE_BASE = os.getenv('ENGINE_BASE', 'http://localhost:8080')
IN_CHARTS = os.getenv('IN_CHARTS', '/mnt/data/batch_positions/charts_input_template.csv')
IN_REF = os.getenv('IN_REF', '/mnt/data/batch_positions/reference_prefilled.csv')
OUT_REF = os.getenv('OUT_REF', '/mnt/data/batch_positions/reference_prefilled_with_utc.csv')

def geocode_place(place_name: str) -> dict | None:
    """Geocode a place name using the engine's geocoding API."""
    try:
        url = f"{ENGINE_BASE}/v1/geocode/search"
        params = {'q': place_name}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            return data[0]  # Return first result
        return None
    except Exception as e:
        print(f"Warning: Failed to geocode {place_name}: {e}")
        return None

def resolve_time(local_datetime: str, lat: float, lon: float) -> str | None:
    """Resolve local datetime to UTC using the time resolver API."""
    try:
        url = f"{ENGINE_BASE}/v1/time/resolve"
        payload = {
            "local_datetime": local_datetime,
            "latitude": lat,
            "longitude": lon,
            "parity_profile": "strict_history"
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('utc')
    except Exception as e:
        print(f"Warning: Failed to resolve time for {local_datetime} at {lat},{lon}: {e}")
        return None

def load_charts_data() -> dict[str, dict]:
    """Load charts input data and resolve UTC timestamps."""
    charts_data = {}

    # Use the current working directory path since /mnt/data doesn't exist
    charts_path = IN_CHARTS.replace('/mnt/data/batch_positions/', 'batch_positions/')

    try:
        with open(charts_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row['name']
                local_datetime = row['local_datetime']
                place_name = row['place_name']
                lat = row['lat']
                lon = row['lon']

                # Use provided coordinates or geocode place name
                if lat and lon:
                    lat, lon = float(lat), float(lon)
                elif place_name:
                    geo_result = geocode_place(place_name)
                    if geo_result:
                        lat = geo_result.get('lat')
                        lon = geo_result.get('lon')
                    else:
                        print(f"Warning: Could not geocode {place_name} for {name}")
                        continue
                else:
                    print(f"Warning: No coordinates or place name for {name}")
                    continue

                # Resolve UTC timestamp
                utc = resolve_time(local_datetime, lat, lon)
                if utc:
                    charts_data[name] = {
                        'utc': utc,
                        'lat': lat,
                        'lon': lon,
                        'local_datetime': local_datetime
                    }
                    print(f"Resolved {name}: {local_datetime} -> {utc}")
                else:
                    print(f"Warning: Could not resolve time for {name}")

    except FileNotFoundError:
        print(f"Error: Charts input file not found: {charts_path}")
        return {}
    except Exception as e:
        print(f"Error loading charts data: {e}")
        return {}

    return charts_data

def update_reference_with_utc(charts_data: dict[str, dict]):
    """Update reference CSV with UTC timestamps from charts data."""

    # Use current working directory paths
    ref_input_path = IN_REF.replace('/mnt/data/batch_positions/', 'batch_positions/')
    ref_output_path = OUT_REF.replace('/mnt/data/batch_positions/', 'batch_positions/')

    try:
        # If input reference doesn't exist, use template
        if not os.path.exists(ref_input_path):
            ref_input_path = 'batch_positions/reference_template.csv'

        with open(ref_input_path) as infile, open(ref_output_path, 'w', newline='') as outfile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                name = row['name']

                # Update UTC if we have data for this name
                if name in charts_data:
                    row['utc'] = charts_data[name]['utc']

                writer.writerow(row)

        print(f"Updated reference file written to: {ref_output_path}")

    except FileNotFoundError as e:
        print(f"Error: Reference file not found: {e}")
    except Exception as e:
        print(f"Error updating reference file: {e}")

def main():
    """Main execution function."""
    print(f"Using ENGINE_BASE: {ENGINE_BASE}")
    print(f"Input charts: {IN_CHARTS}")
    print(f"Input reference: {IN_REF}")
    print(f"Output reference: {OUT_REF}")
    print()

    # Load charts data and resolve UTC timestamps
    print("Loading charts data and resolving UTC timestamps...")
    charts_data = load_charts_data()

    if not charts_data:
        print("No charts data loaded. Exiting.")
        return

    print(f"Successfully processed {len(charts_data)} entries.")
    print()

    # Update reference file with UTC data
    print("Updating reference file with UTC timestamps...")
    update_reference_with_utc(charts_data)
    print("Done.")

if __name__ == "__main__":
    main()
