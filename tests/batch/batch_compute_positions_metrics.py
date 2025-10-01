#!/usr/bin/env python3
"""
Batch Position Computation Metrics Script
Measures performance and payload size for batch position calculations.
"""

import csv
import json
import logging
import os
import statistics
import sys
import time
from pathlib import Path

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def resolve_time_with_metrics(local_datetime, lat, lon, engine_base="http://localhost:8000"):
    """Resolve local time to UTC with timing metrics."""
    payload = {
        "local_datetime": local_datetime,
        "latitude": lat,
        "longitude": lon,
        "parity_profile": "strict_history"
    }

    start_time = time.time()
    response = requests.post(f"{engine_base}/v1/time/resolve", json=payload)
    end_time = time.time()

    response.raise_for_status()
    result = response.json()

    return result, {
        'duration_ms': (end_time - start_time) * 1000,
        'payload_size_bytes': len(json.dumps(payload).encode('utf-8')),
        'response_size_bytes': len(response.content)
    }

def compute_positions_with_metrics(utc_time, lat, lon, zodiac, ayanamsa, engine_base="http://localhost:8000"):
    """Compute planetary positions with timing and size metrics."""
    payload = {
        "birth_time": utc_time,
        "latitude": lat,
        "longitude": lon,
        "elevation": 0.0,
        "zodiac": zodiac,
        "ayanamsa": ayanamsa,
        "parity_profile": "strict_history"
    }

    start_time = time.time()
    response = requests.post(f"{engine_base}/calculate", json=payload)
    end_time = time.time()

    response.raise_for_status()
    result = response.json()

    return result, {
        'duration_ms': (end_time - start_time) * 1000,
        'payload_size_bytes': len(json.dumps(payload).encode('utf-8')),
        'response_size_bytes': len(response.content)
    }

def process_chart_with_metrics(row, engine_base="http://localhost:8000"):
    """Process a single chart with comprehensive metrics."""
    name = row['name']
    local_datetime = row['local_datetime']
    lat = float(row['lat'])
    lon = float(row['lon'])
    systems = row['systems'].split(',')

    logger.info(f"Processing {name} for metrics...")

    chart_start_time = time.time()

    # Resolve time with metrics
    time_info, time_metrics = resolve_time_with_metrics(local_datetime, lat, lon, engine_base)
    utc_time = time_info['utc']

    system_metrics = []

    for system in systems:
        system = system.strip()

        if system == 'tropical':
            zodiac = 'tropical'
            ayanamsa = 'lahiri'
        elif system == 'sidereal_fb':
            zodiac = 'sidereal'
            ayanamsa = 'fagan_bradley'
        else:
            continue

        # Compute positions with metrics
        positions, pos_metrics = compute_positions_with_metrics(utc_time, lat, lon, zodiac, ayanamsa, engine_base)

        system_metrics.append({
            'name': name,
            'system': system,
            'time_resolve_duration_ms': time_metrics['duration_ms'],
            'time_resolve_payload_bytes': time_metrics['payload_size_bytes'],
            'time_resolve_response_bytes': time_metrics['response_size_bytes'],
            'positions_duration_ms': pos_metrics['duration_ms'],
            'positions_payload_bytes': pos_metrics['payload_size_bytes'],
            'positions_response_bytes': pos_metrics['response_size_bytes'],
            'total_duration_ms': time_metrics['duration_ms'] + pos_metrics['duration_ms'],
            'total_payload_bytes': time_metrics['payload_size_bytes'] + pos_metrics['payload_size_bytes'],
            'total_response_bytes': time_metrics['response_size_bytes'] + pos_metrics['response_size_bytes'],
            'planet_count': len(positions.get('data', {})),
            'utc': utc_time
        })

    chart_end_time = time.time()
    chart_duration = (chart_end_time - chart_start_time) * 1000

    return system_metrics, chart_duration

def main():
    if len(sys.argv) != 3:
        logger.error("Usage: python batch_compute_positions_metrics.py <input_csv> <output_dir>")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    engine_base = os.getenv('ENGINE_BASE', 'http://localhost:8000')

    logger.info(f"Reading input from: {input_csv}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Engine base: {engine_base}")

    all_metrics = []
    chart_durations = []

    batch_start_time = time.time()

    with open(input_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                system_metrics, chart_duration = process_chart_with_metrics(row, engine_base)
                all_metrics.extend(system_metrics)
                chart_durations.append(chart_duration)
                time.sleep(0.1)  # Small delay
            except Exception as e:
                logger.error(f"Error processing {row['name']}: {e}")

    batch_end_time = time.time()
    batch_duration = (batch_end_time - batch_start_time) * 1000

    # Write per-chart metrics
    metrics_file = output_dir / 'metrics_per_chart.csv'
    if all_metrics:
        with open(metrics_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_metrics[0].keys())
            writer.writeheader()
            writer.writerows(all_metrics)

    logger.info(f"Per-chart metrics written to: {metrics_file}")

    # Calculate summary statistics
    if all_metrics:
        total_durations = [m['total_duration_ms'] for m in all_metrics]
        total_payloads = [m['total_payload_bytes'] for m in all_metrics]
        total_responses = [m['total_response_bytes'] for m in all_metrics]

        total_charts = len(set(m['name'] for m in all_metrics))
        charts_per_second = total_charts / (batch_duration / 1000) if batch_duration > 0 else 0

        summary = {
            'batch_summary': {
                'total_charts': total_charts,
                'total_systems': len(all_metrics),
                'batch_duration_ms': batch_duration,
                'charts_per_second': charts_per_second
            },
            'duration_stats': {
                'mean_ms': statistics.mean(total_durations),
                'median_ms': statistics.median(total_durations),
                'p95_ms': statistics.quantiles(total_durations, n=20)[18] if len(total_durations) >= 20 else max(total_durations),
                'min_ms': min(total_durations),
                'max_ms': max(total_durations)
            },
            'payload_stats': {
                'mean_bytes': statistics.mean(total_payloads),
                'median_bytes': statistics.median(total_payloads),
                'total_bytes': sum(total_payloads)
            },
            'response_stats': {
                'mean_bytes': statistics.mean(total_responses),
                'median_bytes': statistics.median(total_responses),
                'total_bytes': sum(total_responses)
            }
        }

        # Write summary
        summary_file = output_dir / 'metrics_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Summary metrics written to: {summary_file}")

        # Log key stats
        logger.info("\n=== PERFORMANCE SUMMARY ===")
        logger.info(f"Total charts: {total_charts}")
        logger.info(f"Charts per second: {charts_per_second:.2f}")
        logger.info(f"Mean duration per chart: {statistics.mean(total_durations):.1f}ms")
        logger.info(f"P95 duration: {summary['duration_stats']['p95_ms']:.1f}ms")
        logger.info(f"Total payload size: {sum(total_payloads):,} bytes")
        logger.info(f"Total response size: {sum(total_responses):,} bytes")

if __name__ == '__main__':
    main()
