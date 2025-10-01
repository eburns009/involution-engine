from typing import Optional, Dict, Any
import math


# Minimal built-in registry (extend later or load from YAML)
REGISTRY: Dict[str, Dict[str, Any]] = {
    "FAGAN_BRADLEY_DYNAMIC": {
        "type": "formula",
        "id": "FAGAN_BRADLEY_DYNAMIC",
        "description": "Fagan-Bradley dynamic ayanāṃśa based on Spica"
    },
    "FAGAN_BRADLEY_FIXED": {
        "type": "fixed",
        "value_deg": 24.2166666667,  # 24°13'
        "description": "Fagan-Bradley fixed ayanāṃśa (24°13')"
    },
    "LAHIRI": {
        "type": "formula",
        "id": "LAHIRI",
        "description": "Lahiri (Chitrapaksha) ayanāṃśa - Indian national standard"
    },
    # Will add KRISHNAMURTI, RAMAN, YUKTESHWAR in Phase 2
}


def get_available_ayanamshas() -> Dict[str, str]:
    """Get list of available ayanāṃśa IDs with descriptions."""
    return {id: data["description"] for id, data in REGISTRY.items()}


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
    if not id:
        return {"id": "LAHIRI", "type": "formula"}

    if id not in REGISTRY:
        available = ", ".join(REGISTRY.keys())
        raise ValueError(f"AYANAMSHA.UNSUPPORTED: '{id}' not in registry. Available: {available}")

    return REGISTRY[id].copy()


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

    ayanamsha_id = ayanamsha_config.get("id")

    # Placeholder calculations - in real implementation, use SPICE/Swiss Ephemeris
    if ayanamsha_id == "LAHIRI":
        # Simplified Lahiri calculation (approximate)
        # Real implementation would use precise IAU precession formulas
        t = (jd - 2451545.0) / 36525.0  # Centuries since J2000.0
        return 23.85 + 0.3964 * t  # Very simplified!

    elif ayanamsha_id == "FAGAN_BRADLEY_DYNAMIC":
        # Simplified Fagan-Bradley calculation (approximate)
        # Real implementation would use Spica position calculations
        t = (jd - 2451545.0) / 36525.0
        return 24.04 + 0.3962 * t  # Very simplified!

    else:
        raise ValueError(f"Formula calculation not implemented for ayanāṃśa: {ayanamsha_id}")


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