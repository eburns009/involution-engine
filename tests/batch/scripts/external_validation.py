#!/usr/bin/env python3
"""
External Validation Tool
Cross-reference calculations with external ephemeris sources
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import requests


class ExternalValidator:
    def __init__(self, spice_url: str = "http://localhost:8000"):
        self.spice_url = spice_url
        self.validation_results = []

    def fetch_astro_com_data(self, date: str, time_str: str, lat: float, lon: float) -> dict | None:
        """
        Fetch data from Astro.com (placeholder - would need actual API access)
        This is a template for how external validation would work
        """
        # Note: Astro.com doesn't provide a public API
        # This is a placeholder for the methodology
        print(f"🌐 Would fetch from Astro.com: {date} {time_str} at {lat}, {lon}")
        return None

    def calculate_swiss_ephemeris_reference(self, date: str, time_str: str) -> dict[str, float]:
        """
        Calculate reference positions using Swiss Ephemeris
        This would use pyephem or similar library for independent verification
        """
        try:
            # Placeholder for Swiss Ephemeris calculation
            # In actual implementation, would use pyephem or swisseph library
            print(f"📊 Calculating Swiss Ephemeris reference for {date} {time_str}")

            # Simulate reference calculation (replace with actual Swiss Ephemeris)
            reference_positions = {
                "sun": 295.123,      # Example positions in tropical longitude
                "moon": 156.789,
                "mercury": 278.456,
                "venus": 312.234,
                "mars": 89.567,
                "jupiter": 203.890,
                "saturn": 167.123,
                "uranus": 45.678,
                "neptune": 321.234,
                "pluto": 289.567
            }

            return reference_positions

        except Exception as e:
            print(f"⚠️  Swiss Ephemeris reference calculation failed: {e}")
            return {}

    def validate_chart_against_references(self, chart_data: dict) -> dict[str, Any]:
        """
        Validate a chart against multiple reference sources
        """
        chart_id = chart_data.get("chart_id")
        date = chart_data.get("date")
        time_str = chart_data.get("time")
        lat = chart_data.get("latitude")
        lon = chart_data.get("longitude")

        print(f"\n🔍 Validating Chart #{chart_id}: {date} {time_str}")

        validation_result = {
            "chart_id": chart_id,
            "date": date,
            "time": time_str,
            "location": {"lat": lat, "lon": lon},
            "spice_positions": {},
            "reference_positions": {},
            "differences": {},
            "validation_status": "unknown",
            "accuracy_metrics": {}
        }

        try:
            # Get positions from our spice service
            birth_data = {
                "birth_date": date,
                "birth_time": time_str,
                "birth_lat": lat,
                "birth_lon": lon,
                "birth_tz": 0.0
            }

            spice_response = requests.post(f"{self.spice_url}/positions",
                                         json=birth_data, timeout=30)

            if spice_response.status_code == 200:
                spice_data = spice_response.json()
                validation_result["spice_positions"] = spice_data.get("positions", {})
            else:
                validation_result["spice_error"] = f"HTTP {spice_response.status_code}"

            # Get reference positions (Swiss Ephemeris)
            reference_positions = self.calculate_swiss_ephemeris_reference(date, time_str)
            validation_result["reference_positions"] = reference_positions

            # Calculate differences
            differences = {}
            spice_positions = validation_result["spice_positions"]

            for planet in reference_positions:
                if planet in spice_positions:
                    spice_lon = spice_positions[planet].get("longitude", 0)
                    ref_lon = reference_positions[planet]
                    diff = abs(spice_lon - ref_lon)

                    # Handle longitude wraparound (0° = 360°)
                    if diff > 180:
                        diff = 360 - diff

                    differences[planet] = {
                        "spice_longitude": spice_lon,
                        "reference_longitude": ref_lon,
                        "difference_degrees": diff,
                        "difference_arcminutes": diff * 60,
                        "within_1_arcmin": diff < (1/60),
                        "within_5_arcmin": diff < (5/60),
                        "within_30_arcmin": diff < (30/60)
                    }

            validation_result["differences"] = differences

            # Calculate accuracy metrics
            if differences:
                total_planets = len(differences)
                within_1_arcmin = sum(1 for d in differences.values() if d["within_1_arcmin"])
                within_5_arcmin = sum(1 for d in differences.values() if d["within_5_arcmin"])
                avg_difference = sum(d["difference_arcminutes"] for d in differences.values()) / total_planets

                validation_result["accuracy_metrics"] = {
                    "total_planets": total_planets,
                    "within_1_arcmin": within_1_arcmin,
                    "within_5_arcmin": within_5_arcmin,
                    "accuracy_1min_percent": (within_1_arcmin / total_planets) * 100,
                    "accuracy_5min_percent": (within_5_arcmin / total_planets) * 100,
                    "average_difference_arcmin": avg_difference
                }

                # Determine validation status
                if avg_difference < 1.0 and within_5_arcmin >= total_planets * 0.9:
                    validation_result["validation_status"] = "excellent"
                elif avg_difference < 5.0 and within_5_arcmin >= total_planets * 0.8:
                    validation_result["validation_status"] = "good"
                elif avg_difference < 15.0:
                    validation_result["validation_status"] = "acceptable"
                else:
                    validation_result["validation_status"] = "poor"

            print(f"  Status: {validation_result['validation_status']}")
            if validation_result.get("accuracy_metrics"):
                metrics = validation_result["accuracy_metrics"]
                print(f"  Accuracy: {metrics['accuracy_5min_percent']:.1f}% within 5 arcmin")
                print(f"  Average difference: {metrics['average_difference_arcmin']:.2f} arcmin")

        except Exception as e:
            validation_result["error"] = str(e)
            validation_result["validation_status"] = "error"
            print(f"  ❌ Validation error: {e}")

        return validation_result

    def create_validation_report(self, charts_to_validate: list[dict]) -> dict[str, Any]:
        """
        Create comprehensive validation report
        """
        print("🔍 Creating External Validation Report")
        print("====================================")

        all_results = []
        for chart in charts_to_validate:
            result = self.validate_chart_against_references(chart)
            all_results.append(result)
            self.validation_results.append(result)
            time.sleep(1)  # Rate limiting

        # Aggregate statistics
        successful_validations = [r for r in all_results if r["validation_status"] != "error"]
        total_charts = len(all_results)

        if successful_validations:
            avg_accuracy_5min = sum(r["accuracy_metrics"]["accuracy_5min_percent"]
                                  for r in successful_validations) / len(successful_validations)
            avg_difference = sum(r["accuracy_metrics"]["average_difference_arcmin"]
                               for r in successful_validations) / len(successful_validations)

            status_counts = {}
            for status in ["excellent", "good", "acceptable", "poor"]:
                status_counts[status] = sum(1 for r in successful_validations
                                          if r["validation_status"] == status)
        else:
            avg_accuracy_5min = 0
            avg_difference = 0
            status_counts = {}

        report = {
            "validation_summary": {
                "timestamp": datetime.now().isoformat(),
                "total_charts_tested": total_charts,
                "successful_validations": len(successful_validations),
                "validation_success_rate": len(successful_validations) / total_charts if total_charts else 0,
                "average_accuracy_5min_percent": avg_accuracy_5min,
                "average_difference_arcmin": avg_difference,
                "status_distribution": status_counts
            },
            "individual_results": all_results,
            "recommendations": self.generate_validation_recommendations(all_results)
        }

        return report

    def generate_validation_recommendations(self, results: list[dict]) -> dict[str, str]:
        """Generate recommendations based on validation results"""
        recommendations = {}

        successful = [r for r in results if r["validation_status"] != "error"]

        if not successful:
            recommendations["overall"] = "Validation failed - check spice service and calculations"
            return recommendations

        avg_accuracy = sum(r["accuracy_metrics"]["accuracy_5min_percent"]
                          for r in successful) / len(successful)

        if avg_accuracy >= 95:
            recommendations["accuracy_assessment"] = "Excellent - suitable for precision astrology"
            recommendations["confidence_level"] = "High confidence in calculations"
        elif avg_accuracy >= 85:
            recommendations["accuracy_assessment"] = "Good - suitable for most astrological work"
            recommendations["confidence_level"] = "Good confidence in calculations"
        elif avg_accuracy >= 70:
            recommendations["accuracy_assessment"] = "Acceptable - suitable for general astrology"
            recommendations["confidence_level"] = "Moderate confidence in calculations"
        else:
            recommendations["accuracy_assessment"] = "Poor - consider ephemeris improvements"
            recommendations["confidence_level"] = "Low confidence - validation recommended"

        # Identify most problematic planets
        planet_errors = {}
        for result in successful:
            for planet, diff_data in result.get("differences", {}).items():
                if planet not in planet_errors:
                    planet_errors[planet] = []
                planet_errors[planet].append(diff_data["difference_arcminutes"])

        if planet_errors:
            worst_planet = max(planet_errors.items(),
                             key=lambda x: sum(x[1]) / len(x[1]))
            recommendations["most_error_prone_planet"] = f"{worst_planet[0]} (avg: {sum(worst_planet[1])/len(worst_planet[1]):.1f} arcmin)"

        return recommendations

    def export_validation_report(self, report: dict, filename: str = "external_validation_report.json"):
        """Export validation report to file"""
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n💾 Validation report exported to {filename}")

def create_sample_validation_charts() -> list[dict]:
    """Create sample charts for validation testing"""
    return [
        {
            "chart_id": 1,
            "date": "1953-01-15",
            "time": "12:00:00",
            "latitude": 51.5,
            "longitude": -0.116667,
            "location": "London, England"
        },
        {
            "chart_id": 4,
            "date": "1982-03-12",
            "time": "15:45:00",
            "latitude": -33.866667,
            "longitude": 151.2,
            "location": "Sydney, Australia"
        },
        {
            "chart_id": 7,
            "date": "2003-05-18",
            "time": "14:30:00",
            "latitude": 19.066667,
            "longitude": 72.883333,
            "location": "Mumbai, India"
        }
    ]

def main():
    """Main execution for external validation"""
    print("🔍 External Ephemeris Validation")
    print("===============================")

    # Check spice service
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

    validator = ExternalValidator(spice_url)

    # Create sample validation charts
    validation_charts = create_sample_validation_charts()

    print(f"\n📊 Validating {len(validation_charts)} sample charts against external references")

    # Run validation
    report = validator.create_validation_report(validation_charts)

    # Display summary
    summary = report["validation_summary"]
    print("\n📈 Validation Summary:")
    print(f"  Charts tested: {summary['total_charts_tested']}")
    print(f"  Success rate: {summary['validation_success_rate']:.1%}")
    print(f"  Average 5-arcmin accuracy: {summary['average_accuracy_5min_percent']:.1f}%")
    print(f"  Average difference: {summary['average_difference_arcmin']:.2f} arcminutes")

    print("\n🎯 Recommendations:")
    for key, rec in report["recommendations"].items():
        print(f"  {key.replace('_', ' ').title()}: {rec}")

    # Export report
    validator.export_validation_report(report)

    print("\n✅ External validation complete!")
    print("Note: This demo uses simulated reference data.")
    print("For production use, integrate with Swiss Ephemeris library or external APIs.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
