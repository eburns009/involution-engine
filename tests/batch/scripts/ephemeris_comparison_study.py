#!/usr/bin/env python3
"""
Enhanced Ephemeris Comparison Study
Automated testing framework for tropical & sidereal accuracy verification
"""

import csv
import json
import os
import sys
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


@dataclass
class TestChart:
    chart_id: int
    date: str
    time: str
    location: str
    latitude: float
    longitude: float
    era: str
    timezone_offset: float = 0.0  # UTC offset
    is_lmt: bool = False  # Local Mean Time

@dataclass
class PlanetPosition:
    planet: str
    longitude_deg: float
    longitude_dms: str
    zodiac_system: str
    ephemeris: str

@dataclass
class ChartResult:
    chart: TestChart
    tropical_positions: list[PlanetPosition]
    sidereal_positions: list[PlanetPosition]
    ayanamsa_value: float
    calculation_time: float
    errors: list[str]

# Test chart data from the study
TEST_CHARTS = [
    TestChart(1, "1953-01-15", "12:00:00", "London, England", 51.5, -0.116667, "1950s"),
    TestChart(2, "1958-07-23", "06:30:00", "New York, USA", 40.716667, -74.0, "1950s"),
    TestChart(3, "1951-11-08", "21:15:00", "Tokyo, Japan", 35.683333, 139.7, "1950s"),
    TestChart(4, "1982-03-12", "15:45:00", "Sydney, Australia", -33.866667, 151.2, "1980s"),
    TestChart(5, "1987-09-04", "11:20:00", "Cairo, Egypt", 30.05, 31.25, "1980s"),
    TestChart(6, "1985-12-21", "07:00:00", "Mexico City, Mexico", 19.433333, -99.133333, "1980s"),
    TestChart(7, "2003-05-18", "14:30:00", "Mumbai, India", 19.066667, 72.883333, "2000s"),
    TestChart(8, "2007-08-11", "22:45:00", "São Paulo, Brazil", -23.55, -46.633333, "2000s"),
    TestChart(9, "2004-02-29", "04:15:00", "Berlin, Germany", 52.516667, 13.4, "2000s"),
    TestChart(10, "1906-04-06", "08:30:00", "San Francisco, USA", 37.783333, -122.416667, "1900s"),
    TestChart(11, "1912-10-14", "13:20:00", "Paris, France", 48.85, 2.283333, "1900s"),
    TestChart(12, "1908-06-30", "17:45:00", "St. Petersburg, Russia", 59.95, 30.316667, "1900s"),
    TestChart(13, "1543-03-25", "12:00:00", "Rome, Italy", 41.9, 12.483333, "1500s", is_lmt=True),
    TestChart(14, "1565-09-12", "06:00:00", "Madrid, Spain", 40.416667, -3.7, "1500s", is_lmt=True),
    TestChart(15, "1587-11-03", "15:30:00", "London, England", 51.5, -0.116667, "1500s", is_lmt=True),
    TestChart(16, "0001-01-01", "12:00:00", "Jerusalem", 31.783333, 35.216667, "Year 1", is_lmt=True),
    TestChart(17, "0001-06-21", "06:00:00", "Rome, Italy", 41.9, 12.483333, "Year 1", is_lmt=True),
    TestChart(18, "0001-12-25", "15:00:00", "Bethlehem", 31.7, 35.2, "Year 1", is_lmt=True),
    TestChart(19, "-1000-03-20", "12:00:00", "Babylon", 32.533333, 44.416667, "1000 BCE", is_lmt=True),
    TestChart(20, "-1000-07-15", "09:00:00", "Memphis, Egypt", 29.85, 31.25, "1000 BCE", is_lmt=True),
    TestChart(21, "-1000-10-31", "18:30:00", "Athens, Greece", 37.966667, 23.716667, "1000 BCE", is_lmt=True),
]

class EphemerisComparator:
    def __init__(self, spice_url: str = "http://localhost:8000"):
        self.spice_url = spice_url
        self.results: list[ChartResult] = []

    def deg_to_dms(self, degrees: float) -> str:
        """Convert decimal degrees to degrees, minutes, seconds format"""
        deg = int(degrees)
        minutes_float = (degrees - deg) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        return f"{deg:02d}°{minutes:02d}'{seconds:05.2f}\""

    def calculate_chart_positions(self, chart: TestChart) -> ChartResult:
        """Calculate both tropical and sidereal positions for a chart"""
        print(f"Processing Chart #{chart.chart_id}: {chart.date} {chart.time} - {chart.location}")

        start_time = datetime.now().timestamp()
        errors = []

        try:
            # Convert to ISO format required by the API
            birth_datetime = f"{chart.date}T{chart.time}Z"  # Assume UTC for now

            # Prepare base request data
            base_request = {
                "birth_time": birth_datetime,
                "latitude": chart.latitude,
                "longitude": chart.longitude,
                "elevation": 0.0
            }

            # Calculate tropical positions
            tropical_request = {**base_request, "zodiac": "tropical"}
            tropical_response = requests.post(f"{self.spice_url}/calculate", json=tropical_request, timeout=30)

            if tropical_response.status_code != 200:
                errors.append(f"Tropical calculation failed: {tropical_response.status_code}")
                tropical_data = {}
            else:
                tropical_data = tropical_response.json()

            # Calculate sidereal positions (Fagan-Bradley)
            sidereal_request = {**base_request, "zodiac": "sidereal", "ayanamsa": "fagan_bradley"}
            sidereal_response = requests.post(f"{self.spice_url}/calculate", json=sidereal_request, timeout=30)

            if sidereal_response.status_code != 200:
                errors.append(f"Sidereal calculation failed: {sidereal_response.status_code}")
                sidereal_data = {}
            else:
                sidereal_data = sidereal_response.json()

            # Extract positions
            tropical_positions = []
            sidereal_positions = []
            ayanamsa_value = 0.0

            if tropical_data.get("data"):
                for planet, pos_data in tropical_data["data"].items():
                    longitude = pos_data.get("longitude", 0.0)
                    tropical_positions.append(PlanetPosition(
                        planet=planet,
                        longitude_deg=longitude,
                        longitude_dms=self.deg_to_dms(longitude),
                        zodiac_system="tropical",
                        ephemeris="spice_de440"
                    ))

            if sidereal_data.get("data"):
                ayanamsa_value = sidereal_data.get("meta", {}).get("ayanamsa_deg", 0.0)
                for planet, pos_data in sidereal_data["data"].items():
                    longitude = pos_data.get("longitude", 0.0)
                    sidereal_positions.append(PlanetPosition(
                        planet=planet,
                        longitude_deg=longitude,
                        longitude_dms=self.deg_to_dms(longitude),
                        zodiac_system="sidereal",
                        ephemeris="spice_de440"
                    ))

            calculation_time = datetime.now().timestamp() - start_time

            return ChartResult(
                chart=chart,
                tropical_positions=tropical_positions,
                sidereal_positions=sidereal_positions,
                ayanamsa_value=ayanamsa_value,
                calculation_time=calculation_time,
                errors=errors
            )

        except Exception as e:
            errors.append(f"Calculation error: {str(e)}")
            return ChartResult(
                chart=chart,
                tropical_positions=[],
                sidereal_positions=[],
                ayanamsa_value=0.0,
                calculation_time=datetime.now().timestamp() - start_time,
                errors=errors
            )

    def run_baseline_study(self, chart_range: tuple[int, int] = (1, 9)) -> list[ChartResult]:
        """Run the baseline modern era study (charts 1-9 by default)"""
        print(f"Running baseline study for charts {chart_range[0]}-{chart_range[1]}")

        start_idx = chart_range[0] - 1
        end_idx = chart_range[1]
        test_charts = TEST_CHARTS[start_idx:end_idx]

        results = []
        for chart in test_charts:
            result = self.calculate_chart_positions(chart)
            results.append(result)
            self.results.append(result)

            # Print quick summary
            if result.errors:
                print(f"  ⚠️  Chart #{chart.chart_id}: {len(result.errors)} errors")
                for error in result.errors:
                    print(f"     - {error}")
            else:
                tropical_count = len(result.tropical_positions)
                sidereal_count = len(result.sidereal_positions)
                print(f"  ✅ Chart #{chart.chart_id}: {tropical_count} tropical, {sidereal_count} sidereal positions")
                print(f"     Ayanamsa: {result.ayanamsa_value:.4f}°")

        return results

    def analyze_consistency(self, results: list[ChartResult]) -> dict[str, Any]:
        """Analyze consistency patterns in the results"""
        analysis = {
            "total_charts": len(results),
            "successful_charts": len([r for r in results if not r.errors]),
            "failed_charts": len([r for r in results if r.errors]),
            "average_calculation_time": sum(r.calculation_time for r in results) / len(results),
            "ayanamsa_range": {},
            "tropical_sidereal_differences": {},
            "era_analysis": {}
        }

        # Ayanamsa analysis
        ayanamsa_values = [r.ayanamsa_value for r in results if not r.errors and r.ayanamsa_value > 0]
        if ayanamsa_values:
            analysis["ayanamsa_range"] = {
                "min": min(ayanamsa_values),
                "max": max(ayanamsa_values),
                "mean": sum(ayanamsa_values) / len(ayanamsa_values)
            }

        # Era-based analysis
        era_groups = {}
        for result in results:
            era = result.chart.era
            if era not in era_groups:
                era_groups[era] = []
            era_groups[era].append(result)

        for era, era_results in era_groups.items():
            successful = [r for r in era_results if not r.errors]
            analysis["era_analysis"][era] = {
                "total": len(era_results),
                "successful": len(successful),
                "success_rate": len(successful) / len(era_results) if era_results else 0,
                "avg_ayanamsa": sum(r.ayanamsa_value for r in successful) / len(successful) if successful else 0
            }

        return analysis

    def export_results(self, filename: str = "ephemeris_comparison_results.json"):
        """Export results to JSON file"""
        export_data = {
            "study_info": {
                "timestamp": datetime.now().isoformat(),
                "spice_url": self.spice_url,
                "total_charts": len(self.results)
            },
            "results": [asdict(result) for result in self.results],
            "analysis": self.analyze_consistency(self.results)
        }

        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        print(f"Results exported to {filename}")

    def create_comparison_csv(self, filename: str = "ephemeris_positions.csv"):
        """Create CSV file suitable for external software comparison"""
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                "Chart_ID", "Date", "Time", "Location", "Latitude", "Longitude", "Era",
                "Planet", "Tropical_Deg", "Tropical_DMS", "Sidereal_Deg", "Sidereal_DMS",
                "Ayanamsa", "Calculation_Time", "Errors"
            ])

            for result in self.results:
                chart = result.chart

                # Create planet lookup
                tropical_lookup = {p.planet: p for p in result.tropical_positions}
                sidereal_lookup = {p.planet: p for p in result.sidereal_positions}

                # Get all unique planets
                all_planets = set(tropical_lookup.keys()) | set(sidereal_lookup.keys())

                for planet in sorted(all_planets):
                    tropical_pos = tropical_lookup.get(planet)
                    sidereal_pos = sidereal_lookup.get(planet)

                    writer.writerow([
                        chart.chart_id,
                        chart.date,
                        chart.time,
                        chart.location,
                        chart.latitude,
                        chart.longitude,
                        chart.era,
                        planet,
                        tropical_pos.longitude_deg if tropical_pos else "",
                        tropical_pos.longitude_dms if tropical_pos else "",
                        sidereal_pos.longitude_deg if sidereal_pos else "",
                        sidereal_pos.longitude_dms if sidereal_pos else "",
                        result.ayanamsa_value,
                        result.calculation_time,
                        "; ".join(result.errors) if result.errors else ""
                    ])

        print(f"CSV export created: {filename}")

def main():
    """Main execution function"""
    print("🔭 Enhanced Ephemeris Comparison Study")
    print("=====================================")

    # Check if spice service is running
    spice_url = os.environ.get("SPICE_URL", "http://localhost:8000")

    try:
        response = requests.get(f"{spice_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Spice service not responding at {spice_url}")
            return 1
    except Exception as e:
        print(f"❌ Cannot connect to spice service at {spice_url}: {e}")
        return 1

    print(f"✅ Connected to spice service at {spice_url}")

    comparator = EphemerisComparator(spice_url)

    # Run baseline study (modern era charts 1-9)
    print("\n📊 Running Baseline Study (Modern Era: 1950s-2000s)")
    baseline_results = comparator.run_baseline_study((1, 9))

    # Analysis
    print("\n📈 Baseline Analysis")
    analysis = comparator.analyze_consistency(baseline_results)
    print(f"Charts processed: {analysis['total_charts']}")
    print(f"Successful: {analysis['successful_charts']}")
    print(f"Failed: {analysis['failed_charts']}")
    print(f"Average calculation time: {analysis['average_calculation_time']:.3f}s")

    if analysis['ayanamsa_range']:
        print(f"Ayanamsa range: {analysis['ayanamsa_range']['min']:.4f}° to {analysis['ayanamsa_range']['max']:.4f}°")

    print("\nEra Analysis:")
    for era, era_data in analysis['era_analysis'].items():
        print(f"  {era}: {era_data['successful']}/{era_data['total']} success ({era_data['success_rate']:.1%})")
        if era_data['avg_ayanamsa'] > 0:
            print(f"    Avg ayanamsa: {era_data['avg_ayanamsa']:.4f}°")

    # Export results
    print("\n💾 Exporting Results")
    comparator.export_results("baseline_ephemeris_study.json")
    comparator.create_comparison_csv("baseline_positions.csv")

    print("\n✅ Baseline study complete!")
    print("\nNext steps:")
    print("1. Review baseline_positions.csv for external software comparison")
    print("2. Run historical accuracy tests if baseline looks good")
    print("3. Use baseline_ephemeris_study.json for automated analysis")

    return 0

if __name__ == "__main__":
    sys.exit(main())
