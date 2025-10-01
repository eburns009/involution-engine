"""
Tests for the ayanāṃśa registry system.

Tests YAML-based registry loading, ayanāṃśa resolution,
and validation of supported ayanāṃśa systems.
"""

import pytest
import tempfile
import os
from unittest.mock import patch

from app.ephemeris.ayanamsha import (
    load_registry, resolve_ayanamsha, get_available_ayanamshas,
    validate_ayanamsha_for_system, get_ayanamsha_value,
    calculate_fixed_ayanamsha, calculate_formula_ayanamsha
)


class TestAyanamshaRegistry:
    """Tests for ayanāṃśa registry loading and management."""

    def test_load_registry_from_yaml(self, tmp_path):
        """Test loading registry from YAML file."""
        # Create test YAML file
        yaml_content = """
lahiri:
  type: formula
  formula: lahiri

fagan_bradley_fixed:
  type: fixed
  value_deg: 24.2166666667

test_custom:
  type: formula
  formula: custom_formula
"""
        yaml_file = tmp_path / "test_ayanamsas.yaml"
        yaml_file.write_text(yaml_content)

        # Load registry
        load_registry(str(yaml_file))

        # Test that entries were loaded
        available = get_available_ayanamshas()
        assert "lahiri" in available
        assert "fagan_bradley_fixed" in available
        assert "test_custom" in available

    def test_load_registry_file_not_found(self):
        """Test fallback behavior when YAML file doesn't exist."""
        load_registry("/nonexistent/path/ayanamsas.yaml")

        # Should load built-in defaults
        available = get_available_ayanamshas()
        assert "lahiri" in available
        assert "fagan_bradley_dynamic" in available
        assert "fagan_bradley_fixed" in available

    def test_resolve_known_ayanamsha(self):
        """Test resolving known ayanāṃśa IDs."""
        # Load default registry
        load_registry("/nonexistent/path")

        # Test Lahiri
        config = resolve_ayanamsha("lahiri")
        assert config["id"] == "lahiri"
        assert config["type"] == "formula"
        assert config["formula"] == "lahiri"

        # Test Fagan-Bradley fixed
        config = resolve_ayanamsha("fagan_bradley_fixed")
        assert config["id"] == "fagan_bradley_fixed"
        assert config["type"] == "fixed"
        assert config["value_deg"] == 24.2166666667

    def test_resolve_unknown_ayanamsha(self):
        """Test error handling for unknown ayanāṃśa IDs."""
        load_registry("/nonexistent/path")

        with pytest.raises(ValueError) as exc_info:
            resolve_ayanamsha("unknown_ayanamsha")

        assert "AYANAMSHA.UNSUPPORTED" in str(exc_info.value)
        assert "unknown_ayanamsha" in str(exc_info.value)

    def test_resolve_none_returns_default(self):
        """Test that None returns default ayanāṃśa."""
        load_registry("/nonexistent/path")

        config = resolve_ayanamsha(None)
        assert config["id"] == "lahiri"
        assert config["type"] == "formula"

    def test_case_insensitive_resolution(self):
        """Test case-insensitive ayanāṃśa resolution."""
        load_registry("/nonexistent/path")

        config1 = resolve_ayanamsha("LAHIRI")
        config2 = resolve_ayanamsha("lahiri")
        config3 = resolve_ayanamsha("Lahiri")

        assert config1["id"] == config2["id"] == config3["id"] == "lahiri"

    def test_get_available_ayanamshas(self):
        """Test getting list of available ayanāṃśas."""
        load_registry("/nonexistent/path")

        available = get_available_ayanamshas()
        assert isinstance(available, dict)
        assert "lahiri" in available
        assert available["lahiri"] == "formula"
        assert available["fagan_bradley_fixed"] == "fixed"


class TestAyanamshaValidation:
    """Tests for ayanāṃśa validation."""

    def setup_method(self):
        """Setup for each test."""
        load_registry("/nonexistent/path")

    def test_validate_tropical_without_ayanamsha(self):
        """Test tropical system without ayanāṃśa (valid)."""
        # Should not raise exception
        validate_ayanamsha_for_system("tropical", None)

    def test_validate_tropical_with_ayanamsha(self):
        """Test tropical system with ayanāṃśa (invalid)."""
        with pytest.raises(ValueError) as exc_info:
            validate_ayanamsha_for_system("tropical", "lahiri")

        assert "SYSTEM.INCOMPATIBLE" in str(exc_info.value)

    def test_validate_sidereal_with_ayanamsha(self):
        """Test sidereal system with ayanāṃśa (valid)."""
        # Should not raise exception
        validate_ayanamsha_for_system("sidereal", "lahiri")

    def test_validate_sidereal_without_ayanamsha(self):
        """Test sidereal system without ayanāṃśa (invalid)."""
        with pytest.raises(ValueError) as exc_info:
            validate_ayanamsha_for_system("sidereal", None)

        assert "AYANAMSHA.REQUIRED" in str(exc_info.value)

    def test_validate_unknown_ayanamsha(self):
        """Test validation with unknown ayanāṃśa ID."""
        with pytest.raises(ValueError) as exc_info:
            validate_ayanamsha_for_system("sidereal", "unknown")

        assert "AYANAMSHA.UNSUPPORTED" in str(exc_info.value)


class TestAyanamshaCalculation:
    """Tests for ayanāṃśa value calculation."""

    def setup_method(self):
        """Setup for each test."""
        load_registry("/nonexistent/path")

    def test_calculate_fixed_ayanamsha(self):
        """Test fixed ayanāṃśa calculation."""
        config = {
            "type": "fixed",
            "value_deg": 24.2166666667
        }

        value = calculate_fixed_ayanamsha(config)
        assert value == 24.2166666667

    def test_calculate_fixed_ayanamsha_wrong_type(self):
        """Test error when trying to calculate fixed for non-fixed type."""
        config = {
            "type": "formula",
            "formula": "lahiri"
        }

        with pytest.raises(ValueError) as exc_info:
            calculate_fixed_ayanamsha(config)

        assert "only works with 'fixed' type" in str(exc_info.value)

    def test_calculate_formula_ayanamsha(self):
        """Test formula ayanāṃśa calculation."""
        config = {
            "type": "formula",
            "formula": "lahiri"
        }

        # J2000.0 Julian Date
        jd = 2451545.0
        value = calculate_formula_ayanamsha(config, jd)

        assert isinstance(value, float)
        assert 20.0 < value < 30.0  # Reasonable range for Lahiri

    def test_calculate_formula_ayanamsha_all_formulas(self):
        """Test all supported formula ayanāṃśas."""
        jd = 2451545.0  # J2000.0

        formulas = ["lahiri", "fagan_bradley_dynamic", "krishnamurti", "raman", "yukteshwar"]

        for formula in formulas:
            config = {
                "type": "formula",
                "formula": formula
            }

            value = calculate_formula_ayanamsha(config, jd)
            assert isinstance(value, float)
            assert 15.0 < value < 30.0  # Reasonable range

    def test_calculate_formula_ayanamsha_unknown_formula(self):
        """Test error for unknown formula."""
        config = {
            "type": "formula",
            "formula": "unknown_formula"
        }

        with pytest.raises(ValueError) as exc_info:
            calculate_formula_ayanamsha(config, 2451545.0)

        assert "Formula calculation not implemented" in str(exc_info.value)

    def test_get_ayanamsha_value_fixed(self):
        """Test getting ayanāṃśa value for fixed type."""
        config = resolve_ayanamsha("fagan_bradley_fixed")
        value = get_ayanamsha_value(config)

        assert value == 24.2166666667

    def test_get_ayanamsha_value_formula(self):
        """Test getting ayanāṃśa value for formula type."""
        config = resolve_ayanamsha("lahiri")
        value = get_ayanamsha_value(config, jd=2451545.0)

        assert isinstance(value, float)
        assert 20.0 < value < 30.0

    def test_get_ayanamsha_value_formula_without_jd(self):
        """Test error when JD is required but not provided."""
        config = resolve_ayanamsha("lahiri")

        with pytest.raises(ValueError) as exc_info:
            get_ayanamsha_value(config)

        assert "Julian Date required" in str(exc_info.value)


class TestAyanamshaIntegration:
    """Integration tests for ayanāṃśa system."""

    def test_full_workflow_formula(self):
        """Test complete workflow for formula ayanāṃśa."""
        load_registry("/nonexistent/path")

        # Validate system compatibility
        validate_ayanamsha_for_system("sidereal", "lahiri")

        # Resolve configuration
        config = resolve_ayanamsha("lahiri")
        assert config["type"] == "formula"

        # Calculate value
        value = get_ayanamsha_value(config, jd=2451545.0)
        assert isinstance(value, float)

    def test_full_workflow_fixed(self):
        """Test complete workflow for fixed ayanāṃśa."""
        load_registry("/nonexistent/path")

        # Validate system compatibility
        validate_ayanamsha_for_system("sidereal", "fagan_bradley_fixed")

        # Resolve configuration
        config = resolve_ayanamsha("fagan_bradley_fixed")
        assert config["type"] == "fixed"

        # Calculate value
        value = get_ayanamsha_value(config)
        assert value == 24.2166666667

    def test_registry_persistence(self):
        """Test that registry persists between calls."""
        load_registry("/nonexistent/path")

        # First call
        config1 = resolve_ayanamsha("lahiri")

        # Second call without reloading
        config2 = resolve_ayanamsha("lahiri")

        assert config1 == config2

    def test_registry_reload(self, tmp_path):
        """Test reloading registry with different data."""
        # First registry
        yaml1 = tmp_path / "ayanamsas1.yaml"
        yaml1.write_text("""
lahiri:
  type: formula
  formula: lahiri
""")

        load_registry(str(yaml1))
        available1 = get_available_ayanamshas()
        assert len(available1) == 1

        # Second registry
        yaml2 = tmp_path / "ayanamsas2.yaml"
        yaml2.write_text("""
lahiri:
  type: formula
  formula: lahiri
raman:
  type: formula
  formula: raman
""")

        load_registry(str(yaml2))
        available2 = get_available_ayanamshas()
        assert len(available2) == 2
        assert "raman" in available2