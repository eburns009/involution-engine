#!/usr/bin/env python3
"""
System Accuracy Analyzer
Comprehensive tool for analyzing ephemeris accuracy and generating recommendations
for astrological system testing and validation.
"""

import json
import sys
from datetime import datetime
from typing import Any

import numpy as np


class SystemAccuracyAnalyzer:
    def __init__(self):
        self.baseline_data = None
        self.analysis_results = {}

    def load_baseline_data(self, filename: str = "baseline_ephemeris_study.json"):
        """Load baseline ephemeris study data"""
        try:
            with open(filename) as f:
                self.baseline_data = json.load(f)
            print(f"✅ Loaded baseline data: {filename}")
            return True
        except FileNotFoundError:
            print(f"❌ Baseline data file not found: {filename}")
            return False
        except Exception as e:
            print(f"❌ Error loading baseline data: {e}")
            return False

    def analyze_tropical_sidereal_consistency(self) -> dict[str, Any]:
        """Analyze consistency between tropical and sidereal calculations"""
        if not self.baseline_data:
            return {"error": "No baseline data loaded"}

        differences = []
        ayanamsa_consistency = []

        for result in self.baseline_data.get("results", []):
            if result.get("errors"):
                continue

            chart_id = result["chart"]["chart_id"]
            ayanamsa = result["ayanamsa_value"]
            tropical_pos = result.get("tropical_positions", [])
            sidereal_pos = result.get("sidereal_positions", [])

            # Match planets between tropical and sidereal
            tropical_dict = {p["planet"]: p["longitude_deg"] for p in tropical_pos}
            sidereal_dict = {p["planet"]: p["longitude_deg"] for p in sidereal_pos}

            chart_differences = {}
            for planet in tropical_dict:
                if planet in sidereal_dict:
                    tropical_lon = tropical_dict[planet]
                    sidereal_lon = sidereal_dict[planet]

                    # Calculate difference (handling 360° wraparound)
                    diff = tropical_lon - sidereal_lon
                    if diff > 180:
                        diff -= 360
                    elif diff < -180:
                        diff += 360

                    chart_differences[planet] = {
                        "tropical": tropical_lon,
                        "sidereal": sidereal_lon,
                        "difference": diff,
                        "expected_ayanamsa": ayanamsa,
                        "actual_difference": abs(diff),
                        "within_1_arcmin": abs(abs(diff) - ayanamsa) < (1/60),
                        "within_5_arcmin": abs(abs(diff) - ayanamsa) < (5/60)
                    }

            differences.append({
                "chart_id": chart_id,
                "ayanamsa": ayanamsa,
                "planet_differences": chart_differences
            })

            # Check ayanamsa consistency
            planet_diffs = [abs(diff["actual_difference"]) for diff in chart_differences.values()]
            if planet_diffs:
                avg_planet_diff = np.mean(planet_diffs)
                ayanamsa_error = abs(avg_planet_diff - ayanamsa)
                ayanamsa_consistency.append({
                    "chart_id": chart_id,
                    "ayanamsa": ayanamsa,
                    "avg_planet_difference": avg_planet_diff,
                    "ayanamsa_error": ayanamsa_error * 60,  # Convert to arcminutes
                    "consistent": ayanamsa_error < (1/60)  # Within 1 arcminute
                })

        # Calculate overall statistics
        if ayanamsa_consistency:
            consistent_count = sum(1 for ac in ayanamsa_consistency if ac["consistent"])
            avg_ayanamsa_error = np.mean([ac["ayanamsa_error"] for ac in ayanamsa_consistency])
            max_ayanamsa_error = max([ac["ayanamsa_error"] for ac in ayanamsa_consistency])
        else:
            consistent_count = 0
            avg_ayanamsa_error = 0
            max_ayanamsa_error = 0

        return {
            "total_charts_analyzed": len(differences),
            "ayanamsa_consistency_rate": consistent_count / len(ayanamsa_consistency) if ayanamsa_consistency else 0,
            "average_ayanamsa_error_arcmin": avg_ayanamsa_error,
            "maximum_ayanamsa_error_arcmin": max_ayanamsa_error,
            "chart_differences": differences,
            "ayanamsa_consistency": ayanamsa_consistency
        }

    def analyze_era_based_accuracy(self) -> dict[str, Any]:
        """Analyze accuracy by historical era"""
        if not self.baseline_data:
            return {"error": "No baseline data loaded"}

        era_analysis = {}
        for result in self.baseline_data.get("results", []):
            era = result["chart"]["era"]
            chart_id = result["chart"]["chart_id"]

            if era not in era_analysis:
                era_analysis[era] = {
                    "charts": [],
                    "success_count": 0,
                    "total_count": 0,
                    "ayanamsa_values": [],
                    "avg_positions_per_chart": 0
                }

            era_data = era_analysis[era]
            era_data["total_count"] += 1
            era_data["charts"].append(chart_id)

            if not result.get("errors"):
                era_data["success_count"] += 1
                era_data["ayanamsa_values"].append(result["ayanamsa_value"])

                # Count positions
                tropical_count = len(result.get("tropical_positions", []))
                sidereal_count = len(result.get("sidereal_positions", []))
                era_data["avg_positions_per_chart"] += (tropical_count + sidereal_count) / 2

        # Calculate era statistics
        for era, data in era_analysis.items():
            data["success_rate"] = data["success_count"] / data["total_count"] if data["total_count"] else 0
            if data["ayanamsa_values"]:
                data["ayanamsa_range"] = {
                    "min": min(data["ayanamsa_values"]),
                    "max": max(data["ayanamsa_values"]),
                    "mean": np.mean(data["ayanamsa_values"]),
                    "std": np.std(data["ayanamsa_values"])
                }
                data["avg_positions_per_chart"] /= data["success_count"]
            else:
                data["ayanamsa_range"] = None
                data["avg_positions_per_chart"] = 0

        return era_analysis

    def analyze_planetary_accuracy(self) -> dict[str, Any]:
        """Analyze accuracy by individual planet"""
        if not self.baseline_data:
            return {"error": "No baseline data loaded"}

        planet_stats = {}

        for result in self.baseline_data.get("results", []):
            if result.get("errors"):
                continue

            # Analyze tropical positions
            for pos in result.get("tropical_positions", []):
                planet = pos["planet"]
                if planet not in planet_stats:
                    planet_stats[planet] = {
                        "total_calculations": 0,
                        "tropical_longitudes": [],
                        "sidereal_longitudes": [],
                        "position_ranges": {},
                        "ephemeris_consistency": []
                    }

                planet_stats[planet]["total_calculations"] += 1
                planet_stats[planet]["tropical_longitudes"].append(pos["longitude_deg"])

            # Analyze sidereal positions
            for pos in result.get("sidereal_positions", []):
                planet = pos["planet"]
                if planet in planet_stats:
                    planet_stats[planet]["sidereal_longitudes"].append(pos["longitude_deg"])

        # Calculate planetary statistics
        for planet, stats in planet_stats.items():
            if stats["tropical_longitudes"]:
                stats["tropical_range"] = {
                    "min": min(stats["tropical_longitudes"]),
                    "max": max(stats["tropical_longitudes"]),
                    "span": max(stats["tropical_longitudes"]) - min(stats["tropical_longitudes"])
                }

            if stats["sidereal_longitudes"]:
                stats["sidereal_range"] = {
                    "min": min(stats["sidereal_longitudes"]),
                    "max": max(stats["sidereal_longitudes"]),
                    "span": max(stats["sidereal_longitudes"]) - min(stats["sidereal_longitudes"])
                }

        return planet_stats

    def generate_system_recommendations(self) -> dict[str, Any]:
        """Generate comprehensive recommendations for system testing"""

        # Analyze all aspects
        tropical_sidereal = self.analyze_tropical_sidereal_consistency()
        era_accuracy = self.analyze_era_based_accuracy()
        planetary_accuracy = self.analyze_planetary_accuracy()

        recommendations = {
            "timestamp": datetime.now().isoformat(),
            "overall_assessment": {},
            "testing_recommendations": {},
            "accuracy_thresholds": {},
            "reliability_zones": {},
            "known_limitations": {},
            "best_practices": {}
        }

        # Overall Assessment
        if tropical_sidereal.get("ayanamsa_consistency_rate", 0) > 0.9:
            overall_quality = "excellent"
        elif tropical_sidereal.get("ayanamsa_consistency_rate", 0) > 0.7:
            overall_quality = "good"
        elif tropical_sidereal.get("ayanamsa_consistency_rate", 0) > 0.5:
            overall_quality = "acceptable"
        else:
            overall_quality = "poor"

        recommendations["overall_assessment"] = {
            "quality_rating": overall_quality,
            "ayanamsa_consistency": f"{tropical_sidereal.get('ayanamsa_consistency_rate', 0):.1%}",
            "average_ayanamsa_error": f"{tropical_sidereal.get('average_ayanamsa_error_arcmin', 0):.1f} arcminutes",
            "charts_analyzed": tropical_sidereal.get("total_charts_analyzed", 0)
        }

        # Era-based reliability
        reliable_eras = []
        unreliable_eras = []

        for era, data in era_accuracy.items():
            if data["success_rate"] >= 0.8:
                reliable_eras.append(f"{era} ({data['success_rate']:.1%})")
            else:
                unreliable_eras.append(f"{era} ({data['success_rate']:.1%})")

        recommendations["reliability_zones"] = {
            "highly_reliable": reliable_eras,
            "unreliable": unreliable_eras,
            "recommended_date_range": "1550-2650 CE (DE440 coverage)",
            "optimal_testing_range": "1900-2100 CE"
        }

        # Testing recommendations
        if overall_quality in ["excellent", "good"]:
            recommendations["testing_recommendations"] = {
                "suitable_for_precision_astrology": True,
                "recommended_zodiac_system": "Both tropical and sidereal supported",
                "minimum_test_sample_size": 100,
                "validation_frequency": "Monthly",
                "confidence_level": "High"
            }
        else:
            recommendations["testing_recommendations"] = {
                "suitable_for_precision_astrology": False,
                "recommended_zodiac_system": "Tropical only (lower ayanamsa dependency)",
                "minimum_test_sample_size": 500,
                "validation_frequency": "Weekly",
                "confidence_level": "Low - requires external validation"
            }

        # Accuracy thresholds
        avg_error = tropical_sidereal.get('average_ayanamsa_error_arcmin', 0)
        if avg_error < 1:
            position_tolerance = "±30 arcseconds"
            timing_tolerance = "±2 minutes"
        elif avg_error < 5:
            position_tolerance = "±2 arcminutes"
            timing_tolerance = "±10 minutes"
        else:
            position_tolerance = "±5 arcminutes"
            timing_tolerance = "±30 minutes"

        recommendations["accuracy_thresholds"] = {
            "planetary_position_tolerance": position_tolerance,
            "birth_time_tolerance": timing_tolerance,
            "location_tolerance": "±0.1 degrees",
            "ayanamsa_tolerance": f"±{avg_error:.1f} arcminutes"
        }

        # Known limitations
        limitations = []
        if unreliable_eras:
            limitations.append(f"Limited accuracy for: {', '.join(unreliable_eras)}")
        if avg_error > 30:
            limitations.append("Significant systematic ayanamsa offset detected")
        if tropical_sidereal.get("total_charts_analyzed", 0) < 10:
            limitations.append("Limited test coverage - expand validation dataset")

        recommendations["known_limitations"] = limitations

        # Best practices
        recommendations["best_practices"] = {
            "input_validation": [
                "Validate birth times to nearest minute",
                "Use decimal degrees for coordinates",
                "Specify timezone explicitly",
                "Verify location coordinates independently"
            ],
            "calculation_verification": [
                "Cross-check critical charts with external sources",
                "Monitor ayanamsa consistency across calculations",
                "Validate position consistency between zodiac systems",
                "Test edge cases (near pole, ancient dates)"
            ],
            "system_monitoring": [
                "Log calculation times for performance monitoring",
                "Track error rates by era and planet",
                "Maintain baseline accuracy test suite",
                "Alert on significant accuracy degradation"
            ]
        }

        return recommendations

    def create_accuracy_report(self, output_filename: str = "system_accuracy_report.json"):
        """Create comprehensive accuracy report"""
        if not self.baseline_data:
            print("❌ No baseline data loaded")
            return False

        print("📊 Generating comprehensive accuracy analysis...")

        report = {
            "report_metadata": {
                "timestamp": datetime.now().isoformat(),
                "analyzer_version": "1.0.0",
                "baseline_data_source": "baseline_ephemeris_study.json"
            },
            "tropical_sidereal_analysis": self.analyze_tropical_sidereal_consistency(),
            "era_accuracy_analysis": self.analyze_era_based_accuracy(),
            "planetary_accuracy_analysis": self.analyze_planetary_accuracy(),
            "system_recommendations": self.generate_system_recommendations()
        }

        try:
            with open(output_filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"✅ Accuracy report saved: {output_filename}")
            return True
        except Exception as e:
            print(f"❌ Error saving report: {e}")
            return False

    def print_executive_summary(self):
        """Print executive summary of findings"""
        if not self.baseline_data:
            print("❌ No baseline data loaded")
            return

        recommendations = self.generate_system_recommendations()

        print("\n" + "="*60)
        print("🎯 EPHEMERIS ACCURACY - EXECUTIVE SUMMARY")
        print("="*60)

        # Overall Assessment
        assessment = recommendations["overall_assessment"]
        print(f"\n📊 OVERALL QUALITY: {assessment['quality_rating'].upper()}")
        print(f"   • Ayanamsa Consistency: {assessment['ayanamsa_consistency']}")
        print(f"   • Average Error: {assessment['average_ayanamsa_error']}")
        print(f"   • Charts Analyzed: {assessment['charts_analyzed']}")

        # Reliability Zones
        reliability = recommendations["reliability_zones"]
        print("\n🌍 RELIABILITY BY ERA:")
        if reliability["highly_reliable"]:
            print(f"   ✅ Highly Reliable: {', '.join(reliability['highly_reliable'])}")
        if reliability["unreliable"]:
            print(f"   ⚠️  Unreliable: {', '.join(reliability['unreliable'])}")
        print(f"   📅 Recommended Range: {reliability['recommended_date_range']}")

        # Testing Recommendations
        testing = recommendations["testing_recommendations"]
        print("\n🧪 SYSTEM TESTING RECOMMENDATIONS:")
        print(f"   • Precision Astrology: {'✅ Suitable' if testing['suitable_for_precision_astrology'] else '❌ Not Recommended'}")
        print(f"   • Zodiac System: {testing['recommended_zodiac_system']}")
        print(f"   • Minimum Test Sample: {testing['minimum_test_sample_size']} charts")
        print(f"   • Confidence Level: {testing['confidence_level']}")

        # Accuracy Thresholds
        thresholds = recommendations["accuracy_thresholds"]
        print("\n🎯 RECOMMENDED ACCURACY THRESHOLDS:")
        print(f"   • Planetary Positions: {thresholds['planetary_position_tolerance']}")
        print(f"   • Birth Time: {thresholds['birth_time_tolerance']}")
        print(f"   • Location: {thresholds['location_tolerance']}")
        print(f"   • Ayanamsa: {thresholds['ayanamsa_tolerance']}")

        # Known Limitations
        limitations = recommendations["known_limitations"]
        if limitations:
            print("\n⚠️  KNOWN LIMITATIONS:")
            for limitation in limitations:
                print(f"   • {limitation}")

        print("\n" + "="*60)
        print("📋 Full analysis available in system_accuracy_report.json")
        print("="*60)

def main():
    """Main execution function"""
    print("🔍 System Accuracy Analyzer")
    print("==========================")

    analyzer = SystemAccuracyAnalyzer()

    # Load baseline data
    if not analyzer.load_baseline_data():
        return 1

    # Generate comprehensive report
    if analyzer.create_accuracy_report():
        print("📊 Analysis complete!")

    # Print executive summary
    analyzer.print_executive_summary()

    return 0

if __name__ == "__main__":
    sys.exit(main())
