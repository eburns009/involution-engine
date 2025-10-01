import yaml
import os
from typing import Optional, Dict, Any
import math


# Global registry loaded from YAML
_REGISTRY: Dict[str, dict] = {}


def load_registry(path: str) -> None:
    """
    Load ayanāṃśa registry from YAML file.

    Args:
        path: Path to ayanamsas.yaml file
    """
    global _REGISTRY

    if not os.path.exists(path):
        # Fallback built-in registry
        _REGISTRY = {
            "lahiri": {"type": "formula", "formula": "lahiri"},
            "fagan_bradley_dynamic": {"type": "formula", "formula": "fagan_bradley_dynamic"},
            "fagan_bradley_fixed": {"type": "fixed", "value_deg": 24.2166666667},
        }
        return

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _REGISTRY = data


def get_available_ayanamshas() -> Dict[str, str]:
    """Get list of available ayanāṃśa IDs with types."""
    return {id: data.get("type", "unknown") for id, data in _REGISTRY.items()}


def resolve_ayanamsha(id: Optional[str]) -> Dict[str, Any]:
    """
    Resolve ayanāṃśa configuration from ID.

    Args:
        id: Ayanāṃśa identifier or None for default

    Returns:
        Dict with ayanāṃśa configuration

    Raises:
        ValueError: If ayanāṃśa ID is not supported
    """
    if id is None:
        return {"id": "lahiri", "type": "formula", "formula": "lahiri"}

    key = id.strip().lower()

    if key not in _REGISTRY:
        available = ", ".join(_REGISTRY.keys())
        raise ValueError(f"AYANAMSHA.UNSUPPORTED: '{id}' not in registry. Available: {available}")

    config = _REGISTRY[key].copy()
    config["id"] = key
    return config


def calculate_fixed_ayanamsha(ayanamsha_config: Dict[str, Any]) -> float:
    """
    Calculate ayanāṃśa value for fixed type.

    Args:
        ayanamsha_config: Configuration dict from resolve_ayanamsha

    Returns:
        Ayanāṃśa value in degrees

    Raises:
        ValueError: If ayanāṃśa type is not 'fixed'
    """
    if ayanamsha_config.get("type") != "fixed":
        raise ValueError("calculate_fixed_ayanamsha only works with 'fixed' type ayanāṃśas")

    return ayanamsha_config["value_deg"]


def calculate_formula_ayanamsha(ayanamsha_config: Dict[str, Any], jd: float) -> float:
    """
    Calculate ayanāṃśa value for formula type at given Julian Date.

    This is a placeholder implementation. In a full implementation,
    you would integrate with SPICE or Swiss Ephemeris to get the
    proper ayanāṃśa calculation for the given formula.

    Args:
        ayanamsha_config: Configuration dict from resolve_ayanamsha
        jd: Julian Date for calculation

    Returns:
        Ayanāṃśa value in degrees

    Raises:
        ValueError: If ayanāṃśa type is not 'formula'
    """
    if ayanamsha_config.get("type") != "formula":
        raise ValueError("calculate_formula_ayanamsha only works with 'formula' type ayanāṃśas")

    formula = ayanamsha_config.get("formula") or ayanamsha_config.get("id")

    # Placeholder calculations - in real implementation, use SPICE/Swiss Ephemeris
    # Time in Julian centuries since J2000.0
    t = (jd - 2451545.0) / 36525.0

    if formula == "lahiri":
        # Simplified Lahiri calculation (approximate)
        # Real implementation would use precise IAU precession formulas
        return 23.85 + 0.3964 * t  # Very simplified!

    elif formula == "fagan_bradley_dynamic":
        # Simplified Fagan-Bradley calculation (approximate)
        # Real implementation would use Spica position calculations
        return 24.04 + 0.3962 * t  # Very simplified!

    elif formula == "krishnamurti":
        # Krishnamurti ayanāṃśa (KP system)
        # Similar to Lahiri but with slight differences
        return 23.51 + 0.3964 * t

    elif formula == "raman":
        # B.V. Raman ayanāṃśa
        # Based on Revati star system
        return 21.98 + 0.3964 * t

    elif formula == "yukteshwar":
        # Sri Yukteshwar ayanāṃśa
        # From "The Holy Science"
        return 22.46 + 0.3964 * t

    else:
        raise ValueError(f"Formula calculation not implemented for ayanāṃśa: {formula}")


def get_ayanamsha_value(ayanamsha_config: Dict[str, Any], jd: Optional[float] = None) -> float:
    """
    Get ayanāṃśa value for any type.

    Args:
        ayanamsha_config: Configuration dict from resolve_ayanamsha
        jd: Julian Date (required for formula type, ignored for fixed type)

    Returns:
        Ayanāṃśa value in degrees
    """
    ayanamsha_type = ayanamsha_config.get("type")

    if ayanamsha_type == "fixed":
        return calculate_fixed_ayanamsha(ayanamsha_config)
    elif ayanamsha_type == "formula":
        if jd is None:
            raise ValueError("Julian Date required for formula-type ayanāṃśa calculations")
        return calculate_formula_ayanamsha(ayanamsha_config, jd)
    else:
        raise ValueError(f"Unknown ayanāṃśa type: {ayanamsha_type}")


def apply_ayanamsha(tropical_longitude: float, ayanamsha_value: float) -> float:
    """
    Apply ayanāṃśa to convert tropical longitude to sidereal.

    Args:
        tropical_longitude: Longitude in tropical zodiac (degrees)
        ayanamsha_value: Ayanāṃśa value in degrees

    Returns:
        Sidereal longitude in degrees (0-360)
    """
    sidereal = tropical_longitude - ayanamsha_value
    # Normalize to 0-360 range
    while sidereal < 0:
        sidereal += 360
    while sidereal >= 360:
        sidereal -= 360
    return sidereal


# Validation function for API usage
def validate_ayanamsha_for_system(system: str, ayanamsha_id: Optional[str]) -> None:
    """
    Validate ayanāṃśa configuration for zodiac system.

    Args:
        system: Zodiac system ('tropical' or 'sidereal')
        ayanamsha_id: Ayanāṃśa ID or None

    Raises:
        ValueError: If configuration is invalid
    """
    if system == "tropical" and ayanamsha_id is not None:
        raise ValueError("SYSTEM.INCOMPATIBLE: Ayanāṃśa specified for tropical system. "
                        "Remove ayanāṃśa for tropical calculations or use sidereal system.")

    if system == "sidereal" and ayanamsha_id is None:
        raise ValueError("AYANAMSHA.REQUIRED: Sidereal system requires ayanāṃśa specification.")

    if ayanamsha_id:
        # This will raise ValueError if not found
        resolve_ayanamsha(ayanamsha_id)