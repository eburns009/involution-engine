#!/usr/bin/env python3
"""
Historical Accuracy Testing Extension
Tests ephemeris accuracy across different historical eras
"""

import json
import os
import sys
from datetime import datetime
from typing import Any

import requests
from ephemeris_comparison_study import TEST_CHARTS
from ephemeris_comparison_study import EphemerisComparator


class HistoricalAccuracyTester(EphemerisComparator):
    def __init__(self, spice_url: str = "http://localhost:8000"):
        super().__init__(spice_url)

        # Expected ayanamsa values for verification (Fagan-Bradley)
        self.expected_ayanamsa = {
            1953: 24.06,   # 1950s reference
            1987: 24.42,   # 1980s
            2003: 25.00,   # 2000s
            1906: 22.28,   # 1900s
            1543: 17.5,    # 1500s (approximate)
            1: 5.0,        # 1 CE (approximate)
            -1000: -2.0    # 1000 BCE (negative ayanamsa)
        }

    def calculate_expected_ayanamsa(self, year: int) -> float:
        """Calculate expected Fagan-Bradley ayanamsa for a given year"""
        # Fagan-Bradley ayanamsa increases ~50.3" per year from a baseline
        # Using 1950.0 as reference point: 23°27'8.5" = 23.452361°
        reference_year = 1950.0
        reference_ayanamsa = 23.452361
        annual_rate = 50.3 / 3600.0  # 50.3 arcseconds per year in degrees

        return reference_ayanamsa + (year - reference_year) * annual_rate

    def verify_ayanamsa_accuracy(self, result) -> dict[str, Any]:
        """Verify ayanamsa calculation accuracy against expected values"""
        chart_year = int(result.chart.date.split('-')[0])
        if chart_year < 0:  # Handle BCE dates
            chart_year = abs(chart_year)

        expected = self.calculate_expected_ayanamsa(chart_year)
        actual = result.ayanamsa_value
        difference = abs(actual - expected)

        # Tolerance levels based on era
        if chart_year >= 1900:
            tolerance = 0.1  # 6 arcminutes for modern era
        elif chart_year >= 1500:
            tolerance = 0.5  # 30 arcminutes for historical
        else:
            tolerance = 2.0  # 2 degrees for ancient era

        return {
            "chart_year": chart_year,
            "expected_ayanamsa": expected,
            "actual_ayanamsa": actual,
            "difference_deg": difference,
            "difference_arcmin": difference * 60,
            "tolerance_deg": tolerance,
            "within_tolerance": difference <= tolerance,
            "accuracy_rating": "excellent" if difference <= tolerance/4 else
                             "good" if difference <= tolerance/2 else
                             "acceptable" if difference <= tolerance else
                             "poor"
        }

    def test_era_group(self, era_name: str, chart_indices: list[int]) -> dict[str, Any]:
        """Test a specific era group of charts"""
        print(f"\n🏛️  Testing {era_name} Era")
        print("=" * 50)

        results = []
        for chart_idx in chart_indices:
            if chart_idx > len(TEST_CHARTS):
                print(f"⚠️  Chart index {chart_idx} out of range")
                continue

            chart = TEST_CHARTS[chart_idx - 1]  # Convert to 0-based index
            result = self.calculate_chart_positions(chart)
            results.append(result)
            self.results.append(result)

            # Verify ayanamsa accuracy
            ayanamsa_check = self.verify_ayanamsa_accuracy(result)

            print(f"Chart #{chart.chart_id} ({chart.date}):")
            print(f"  Positions: {len(result.tropical_positions)} tropical, {len(result.sidereal_positions)} sidereal")
            print(f"  Ayanamsa: {result.ayanamsa_value:.4f}° (expected: {ayanamsa_check['expected_ayanamsa']:.4f}°)")
            print(f"  Accuracy: {ayanamsa_check['accuracy_rating']} ({ayanamsa_check['difference_arcmin']:.1f}' difference)")

            if result.errors:
                print(f"  ⚠️  Errors: {', '.join(result.errors)}")

        # Era summary
        successful = [r for r in results if not r.errors]
        ayanamsa_checks = [self.verify_ayanamsa_accuracy(r) for r in successful]

        within_tolerance_count = sum(1 for check in ayanamsa_checks if check['within_tolerance'])
        avg_accuracy = sum(check['difference_arcmin'] for check in ayanamsa_checks) / len(ayanamsa_checks) if ayanamsa_checks else 0

        era_summary = {
            "era_name": era_name,
            "total_charts": len(results),
            "successful_charts": len(successful),
            "success_rate": len(successful) / len(results) if results else 0,
            "ayanamsa_accuracy_rate": within_tolerance_count / len(ayanamsa_checks) if ayanamsa_checks else 0,
            "average_ayanamsa_error_arcmin": avg_accuracy,
            "chart_results": results,
            "ayanamsa_checks": ayanamsa_checks
        }

        print(f"\n{era_name} Era Summary:")
        print(f"  Success rate: {era_summary['success_rate']:.1%}")
        print(f"  Ayanamsa accuracy: {era_summary['ayanamsa_accuracy_rate']:.1%}")
        print(f"  Average error: {avg_accuracy:.1f} arcminutes")

        return era_summary

    def run_comprehensive_historical_test(self) -> dict[str, Any]:
        """Run comprehensive historical accuracy test across all eras"""
        print("🔍 Comprehensive Historical Accuracy Test")
        print("=========================================")

        # Define era groups
        era_groups = {
            "Modern (1950s-2000s)": [1, 2, 3, 4, 5, 6, 7, 8, 9],
            "Early Modern (1900s)": [10, 11, 12],
            "Renaissance (1500s)": [13, 14, 15],
            "Ancient (1 CE)": [16, 17, 18],
            "Deep Ancient (1000 BCE)": [19, 20, 21]
        }

        era_results = {}
        for era_name, chart_indices in era_groups.items():
            era_results[era_name] = self.test_era_group(era_name, chart_indices)

        # Overall analysis
        print("\n📊 Overall Historical Analysis")
        print("=" * 50)

        total_charts = sum(era['total_charts'] for era in era_results.values())
        total_successful = sum(era['successful_charts'] for era in era_results.values())
        overall_success_rate = total_successful / total_charts if total_charts else 0

        print(f"Total charts tested: {total_charts}")
        print(f"Overall success rate: {overall_success_rate:.1%}")

        print("\nAccuracy by Era:")
        for era_name, era_data in era_results.items():
            print(f"  {era_name:20}: {era_data['success_rate']:.1%} success, "
                  f"{era_data['ayanamsa_accuracy_rate']:.1%} ayanamsa accuracy, "
                  f"{era_data['average_ayanamsa_error_arcmin']:.1f}' avg error")

        # Identify accuracy cutoff
        accuracy_cutoff = None
        for era_name, era_data in era_results.items():
            if era_data['ayanamsa_accuracy_rate'] < 0.5:  # Less than 50% accuracy
                accuracy_cutoff = era_name
                break

        analysis = {
            "timestamp": datetime.now().isoformat(),
            "total_charts": total_charts,
            "total_successful": total_successful,
            "overall_success_rate": overall_success_rate,
            "era_results": era_results,
            "accuracy_cutoff": accuracy_cutoff,
            "recommendations": self.generate_recommendations(era_results)
        }

        return analysis

    def generate_recommendations(self, era_results: dict[str, Any]) -> dict[str, str]:
        """Generate recommendations based on test results"""
        recommendations = {}

        # Find most accurate era for baseline
        best_era = max(era_results.items(),
                      key=lambda x: x[1]['ayanamsa_accuracy_rate'])

        recommendations["best_baseline_era"] = best_era[0]
        recommendations["best_baseline_accuracy"] = f"{best_era[1]['ayanamsa_accuracy_rate']:.1%}"

        # Determine historical accuracy cutoff
        reliable_eras = [era for era, data in era_results.items()
                        if data['ayanamsa_accuracy_rate'] >= 0.8]

        if reliable_eras:
            recommendations["reliable_historical_range"] = f"Reliable for {', '.join(reliable_eras)}"
        else:
            recommendations["reliable_historical_range"] = "Limited historical reliability"

        # Ephemeris recommendations
        avg_error = sum(era['average_ayanamsa_error_arcmin'] for era in era_results.values()) / len(era_results)

        if avg_error < 1.0:
            recommendations["ephemeris_quality"] = "Excellent - suitable for precision astrology"
        elif avg_error < 5.0:
            recommendations["ephemeris_quality"] = "Good - suitable for most astrological work"
        elif avg_error < 15.0:
            recommendations["ephemeris_quality"] = "Fair - acceptable for general astrology"
        else:
            recommendations["ephemeris_quality"] = "Poor - consider alternative ephemeris"

        return recommendations

    def export_historical_analysis(self, analysis: dict[str, Any],
                                 filename: str = "historical_accuracy_analysis.json"):
        """Export comprehensive historical analysis"""
        with open(filename, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"\n💾 Historical analysis exported to {filename}")

def main():
    """Main execution for historical accuracy testing"""
    print("🏛️  Historical Ephemeris Accuracy Testing")
    print("=========================================")

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

    tester = HistoricalAccuracyTester(spice_url)

    # Run comprehensive test
    analysis = tester.run_comprehensive_historical_test()

    # Export results
    tester.export_historical_analysis(analysis)
    tester.export_results("comprehensive_historical_results.json")
    tester.create_comparison_csv("historical_positions.csv")

    print("\n🎯 Recommendations for Your System:")
    for key, recommendation in analysis['recommendations'].items():
        print(f"  {key.replace('_', ' ').title()}: {recommendation}")

    print("\n✅ Historical accuracy testing complete!")

    return 0

if __name__ == "__main__":
    sys.exit(main())
