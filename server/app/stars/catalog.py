"""
Star catalog loading and management.

Handles loading star catalog data from CSV files with magnitude filtering
and data validation.
"""

import csv
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def load_catalog(path: str, mag_limit: float = 6.0) -> List[Dict]:
    """
    Load star catalog from CSV file with magnitude filtering.

    Args:
        path: Path to CSV catalog file
        mag_limit: Maximum visual magnitude to include

    Returns:
        List of star dictionaries with standardized fields

    Raises:
        FileNotFoundError: If catalog file doesn't exist
        ValueError: If catalog format is invalid
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Star catalog not found: {path}")

    stars = []
    line_count = 0

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Validate required columns
            required_cols = ["RAh", "RAm", "RAs", "DEd", "DEm", "DEs"]
            missing_cols = [col for col in required_cols if col not in reader.fieldnames]
            if missing_cols:
                raise ValueError(f"Missing required columns in catalog: {missing_cols}")

            for line_count, row in enumerate(reader, 1):
                try:
                    # Parse visual magnitude with fallback
                    vmag_str = row.get("Vmag", "99")
                    if vmag_str == "" or vmag_str is None:
                        vmag = 99.0
                    else:
                        try:
                            vmag = float(vmag_str)
                        except ValueError:
                            vmag = 99.0

                    # Skip if magnitude exceeds limit
                    if vmag > mag_limit:
                        continue

                    # Parse RA (hours, minutes, seconds)
                    ra_h = float(row.get("RAh", 0))
                    ra_m = float(row.get("RAm", 0))
                    ra_s = float(row.get("RAs", 0))
                    ra_hours = ra_h + ra_m / 60.0 + ra_s / 3600.0

                    # Parse Dec (degrees, minutes, seconds with sign)
                    de_d = float(row.get("DEd", 0))
                    de_m = float(row.get("DEm", 0))
                    de_s = float(row.get("DEs", 0))
                    de_sign = row.get("DEsign", "+")

                    dec_deg = abs(de_d) + de_m / 60.0 + de_s / 3600.0
                    if de_sign == "-" or de_d < 0:
                        dec_deg = -dec_deg

                    # Parse proper motion (milliarcseconds per year)
                    pm_ra = _safe_float(row.get("pmRA", "0"))
                    pm_dec = _safe_float(row.get("pmDE", "0"))

                    # Parse radial velocity (km/s)
                    rv = _safe_float(row.get("RV", "0"))

                    # Parse parallax (milliarcseconds)
                    parallax = _safe_float(row.get("Plx", "0"))

                    # Build star record
                    star = {
                        "id": row.get("ID") or row.get("HIP") or row.get("HR") or f"star_{line_count}",
                        "ra_hours": ra_hours,
                        "dec_deg": dec_deg,
                        "pm_ra_mas_yr": pm_ra,      # milliarcseconds/year
                        "pm_dec_mas_yr": pm_dec,    # milliarcseconds/year
                        "rv_km_s": rv,              # km/s
                        "parallax_mas": parallax,   # milliarcseconds
                        "name": row.get("Name", "").strip() or row.get("ProperName", "").strip(),
                        "vmag": vmag,
                        "catalog_line": line_count
                    }

                    # Validate coordinates
                    if not (0 <= ra_hours < 24):
                        logger.warning(f"Invalid RA for star {star['id']}: {ra_hours} hours")
                        continue

                    if not (-90 <= dec_deg <= 90):
                        logger.warning(f"Invalid Dec for star {star['id']}: {dec_deg} degrees")
                        continue

                    stars.append(star)

                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping malformed star record at line {line_count}: {e}")
                    continue

    except Exception as e:
        raise ValueError(f"Error reading catalog file {path} at line {line_count}: {e}")

    logger.info(f"Loaded {len(stars)} stars from {path} (mag ≤ {mag_limit})")
    return stars


def _safe_float(value: str, default: float = 0.0) -> float:
    """Safely parse float with fallback to default."""
    if not value or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_catalog_path(catalog_name: str) -> str:
    """
    Get full path for a named catalog.

    Args:
        catalog_name: Name of catalog ("bsc5", "hipparcos")

    Returns:
        Full path to catalog CSV file

    Raises:
        ValueError: If catalog name is not supported
    """
    catalog_files = {
        "bsc5": "bsc5_min.csv",
        "hipparcos": "hipparcos_min.csv"
    }

    if catalog_name not in catalog_files:
        available = list(catalog_files.keys())
        raise ValueError(f"Unsupported catalog '{catalog_name}'. Available: {available}")

    # Get the directory where this module is located
    module_dir = os.path.dirname(__file__)
    catalog_path = os.path.join(module_dir, "data", catalog_files[catalog_name])

    return catalog_path


def get_catalog_info(catalog_name: str) -> Dict[str, str]:
    """
    Get information about a catalog.

    Args:
        catalog_name: Name of catalog

    Returns:
        Dictionary with catalog metadata
    """
    catalog_info = {
        "bsc5": {
            "name": "Yale Bright Star Catalog (5th Edition)",
            "description": "Yale Bright Star Catalog containing stars visible to the naked eye",
            "epoch": "J2000.0",
            "total_stars": "~9100",
            "source": "Yale University Observatory",
            "version": "5th Edition"
        },
        "hipparcos": {
            "name": "Hipparcos Catalog (Subset)",
            "description": "High-precision star positions from ESA Hipparcos mission",
            "epoch": "J2000.0",
            "total_stars": "~118000",
            "source": "ESA Hipparcos Mission",
            "version": "Original Release"
        }
    }

    return catalog_info.get(catalog_name, {
        "name": f"Unknown catalog: {catalog_name}",
        "description": "Catalog information not available",
        "epoch": "Unknown",
        "total_stars": "Unknown",
        "source": "Unknown",
        "version": "Unknown"
    })