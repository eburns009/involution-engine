"""
Time Resolver Core - Historical timezone resolution logic
Based on time_resolver_v2.py with standalone packaging
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones
from timezonefinder import TimezoneFinder
from typing import Dict, List, Optional, Any
from pathlib import Path

# Configure structured logging for provenance tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("time_resolver")

# Global instances
TF = TimezoneFinder()

def load_patches() -> Dict[str, Any]:
    """Load historical patches from configuration file"""
    patch_file = os.getenv("RESOLVER_PATCH_FILE", "/app/config/patches_us_pre1967.json")

    try:
        with open(patch_file) as f:
            patches = json.load(f)
            print(f"✓ Loaded {len(patches.get('patches', {}))} patches from {patch_file}")
            return patches
    except FileNotFoundError:
        print(f"⚠ Patches file not found at {patch_file}")
        return {"patches": {}, "dst_rules": {}}

# Load patches on module import
PATCHES = load_patches()

def get_tzdb_version() -> str:
    """Get IANA tzdb version"""
    try:
        import tzdata
        if hasattr(tzdata, '__version__'):
            return f"tzdata-{tzdata.__version__}"
    except ImportError:
        pass

    try:
        import zoneinfo
        if hasattr(zoneinfo, 'IANA_VERSION'):
            return zoneinfo.IANA_VERSION
    except:
        pass

    return "system-tzdb"

def get_patch_version() -> str:
    """Get patch file version/checksum for cache invalidation"""
    patch_file = os.getenv("RESOLVER_PATCH_FILE", "/app/config/patches_us_pre1967.json")
    try:
        import hashlib
        with open(patch_file, 'rb') as f:
            content = f.read()
            checksum = hashlib.md5(content).hexdigest()[:8]
            return f"patches-{checksum}"
    except:
        return "patches-unknown"

def get_system_health() -> dict:
    """Get comprehensive system health information"""
    # Get cache statistics
    cache_info = latlon_to_zone_cached.cache_info()

    return {
        "status": "healthy",
        "tzdb_version": get_tzdb_version(),
        "patch_version": get_patch_version(),
        "patches_loaded": len(PATCHES.get("patches", {})),
        "timezonefinder_ready": hasattr(TF, 'timezone_at'),
        "cache_stats": {
            "cache_hits": cache_info.hits,
            "cache_misses": cache_info.misses,
            "cache_size": cache_info.currsize,
            "cache_max_size": cache_info.maxsize,
            "hit_rate": round(cache_info.hits / (cache_info.hits + cache_info.misses), 3) if (cache_info.hits + cache_info.misses) > 0 else 0.0
        },
        "environment": {
            "patch_file": os.getenv("RESOLVER_PATCH_FILE", "default"),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        }
    }

@lru_cache(maxsize=1024)
def latlon_to_zone_cached(lat_rounded: float, lon_rounded: float) -> str:
    """Cached timezone lookup with coordinate rounding to improve cache hits"""
    z = TF.timezone_at(lat=lat_rounded, lng=lon_rounded)
    if not z:
        # Fallback (rare): use nearest zone or a default
        z = TF.closest_timezone_at(lat=lat_rounded, lng=lon_rounded) or "Etc/UTC"
    return z

def latlon_to_zone(lat: float, lon: float) -> str:
    """
    Fast path via timezonefinder with LRU cache for hot paths

    Round coordinates to ~1km precision for better cache hits while
    maintaining timezone boundary accuracy (most TZ boundaries are
    much larger than 1km)
    """
    # Round to 3 decimal places (~111m precision at equator, adequate for TZ boundaries)
    lat_rounded = round(lat, 3)
    lon_rounded = round(lon, 3)

    return latlon_to_zone_cached(lat_rounded, lon_rounded)

def apply_patches(lat: float, lon: float, local_dt: datetime, context: dict) -> List[Dict]:
    """
    Apply historical patches based on coordinates and date
    Returns list of matching patches
    """
    hits = []

    if not PATCHES.get("patches"):
        return hits

    for patch_id, patch in PATCHES["patches"].items():
        coords = patch.get("coordinates", {})
        date_range = patch.get("date_range", {})

        # Check coordinate bounds
        if not (coords.get("min_lat", -90) <= lat <= coords.get("max_lat", 90) and
                coords.get("min_lon", -180) <= lon <= coords.get("max_lon", 180)):
            continue

        # Check date range
        start_date = datetime.fromisoformat(date_range.get("start", "1800-01-01")).date()
        end_date = datetime.fromisoformat(date_range.get("end", "2100-01-01")).date()

        if start_date <= local_dt.date() <= end_date:
            hit = {
                "patch_id": patch_id,
                "patch_data": patch,
                "override": patch.get("override", {}),
                "reason": patch.get("reason", "Historical patch applied"),
                "confidence": patch.get("confidence", "medium"),
                "sources": patch.get("sources", [])
            }
            hits.append(hit)

    context["patch_hits"] = hits
    return hits

def _calculate_dst_status(local_dt: datetime, dst_rules: str) -> bool:
    """Calculate DST status based on historical rules"""
    if dst_rules == "none":
        return False

    if dst_rules in ["us_standard", "chicago_historical"]:
        # Last Sunday in April to last Sunday in October (1942-1966)
        year = local_dt.year

        # Find last Sunday in April
        april_last = datetime(year, 4, 30)
        while april_last.weekday() != 6:  # Sunday = 6
            april_last = april_last.replace(day=april_last.day - 1)

        # Find last Sunday in October
        oct_last = datetime(year, 10, 31)
        while oct_last.weekday() != 6:
            oct_last = oct_last.replace(day=oct_last.day - 1)

        return april_last <= local_dt <= oct_last

    return False

def resolve_time(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main resolver function matching the API specification
    """
    # Extract payload data
    ld_str = payload["local_datetime"]
    lat = float(payload["latitude"])
    lon = float(payload["longitude"])
    parity = payload.get("parity_profile", "strict_history")
    user_provided_zone = payload.get("user_provided_zone", "")
    user_provided_offset = payload.get("user_provided_offset")

    # Initialize context
    context = {
        "lat": lat,
        "lon": lon,
        "parity": parity,
        "user_provided_zone": user_provided_zone,
        "user_provided_offset": user_provided_offset
    }

    # Log chart request with full provenance information
    request_id = f"{hash((ld_str, lat, lon, parity, user_provided_zone))}"
    logger.info(
        f"CHART_REQUEST request_id={request_id} "
        f"local_datetime={ld_str} lat={lat:.6f} lon={lon:.6f} "
        f"parity_profile={parity} tzdb_version={get_tzdb_version()} "
        f"patch_version={get_patch_version()}"
    )

    # 1) Get timezone from coordinates
    zone_id = latlon_to_zone(lat, lon)
    context["zone_id"] = zone_id

    # 2) Parse local civil time (naive)
    local_dt = datetime.fromisoformat(ld_str)

    # 3) Determine if we should apply patches
    apply_patch = (parity == "strict_history")

    # 4) Initial UTC computation using IANA zone
    try:
        zi = ZoneInfo(zone_id)
        aware = local_dt.replace(tzinfo=zi)
        utc_dt = aware.astimezone(ZoneInfo("UTC"))
        offset_seconds = int(aware.utcoffset().total_seconds())
        dst_active = bool(aware.dst() and aware.dst().total_seconds() > 0)
    except Exception as e:
        # Fallback to UTC
        utc_dt = local_dt.replace(tzinfo=ZoneInfo("UTC"))
        offset_seconds = 0
        dst_active = False
        zone_id = "UTC"

    # Initialize response components
    notes = []
    warnings = []
    reason = f"IANA tzdb historical rules for {zone_id}"
    confidence = "high"
    sources = ["coordinate_lookup", "IANA_tzdb"]
    patches_applied = []

    # 5) Apply historical patches if strict_history mode
    if apply_patch:
        hits = apply_patches(lat, lon, local_dt, context)
        if hits:
            # Use the first (most specific) patch
            patch = hits[0]
            patch_data = patch["patch_data"]
            override = patch["override"]

            # Override timezone and offset if specified
            if "zone_id" in override:
                zone_id = override["zone_id"]
                offset_seconds = override.get("offset_seconds", offset_seconds)

            # Handle DST override
            if "dst_rules" in override:
                dst_rules = override["dst_rules"]
                if dst_rules == "none":
                    dst_active = False
                    # Recalculate UTC without DST
                    utc_dt = local_dt - timedelta(seconds=offset_seconds)
                    utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
                elif dst_rules in ["us_standard", "chicago_historical"]:
                    # Calculate DST based on historical US rules
                    dst_active = _calculate_dst_status(local_dt, dst_rules)
                    if dst_active:
                        offset_seconds += 3600  # Add DST hour
                    utc_dt = local_dt - timedelta(seconds=offset_seconds)
                    utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))

            # Update response metadata
            reason = patch["reason"]
            confidence = patch["confidence"]
            notes.append(f"Applied patch: {patch['patch_id']}")
            notes.extend(patch["sources"])
            sources.extend(["historical_patches"])
            patches_applied.append(patch["patch_id"])

    # 6) Handle parity profiles
    if parity == "astro_com":
        # Astro.com compatibility: use standard TZDB without patches
        if patches_applied:
            # Recalculate without patches
            try:
                zi = ZoneInfo(context["zone_id"])  # Original zone
                aware = local_dt.replace(tzinfo=zi)
                utc_dt = aware.astimezone(ZoneInfo("UTC"))
                offset_seconds = int(aware.utcoffset().total_seconds())
                dst_active = bool(aware.dst() and aware.dst().total_seconds() > 0)
                reason = f"IANA tzdb historical rules for {context['zone_id']} (Astro.com compatibility)"
                patches_applied = []
                sources = ["coordinate_lookup", "IANA_tzdb"]
            except:
                pass
        notes.append("Applied Astro.com compatibility mode")

    elif parity == "clairvision":
        # Clairvision compatibility: similar to astro.com
        notes.append("Applied Clairvision compatibility mode")

    elif parity == "as_entered":
        # Trust user input with warnings about conflicts
        original_zone = zone_id
        original_offset = offset_seconds

        if user_provided_zone:
            try:
                # Try to use user-provided zone
                user_zi = ZoneInfo(user_provided_zone)
                user_aware = local_dt.replace(tzinfo=user_zi)
                utc_dt = user_aware.astimezone(ZoneInfo("UTC"))
                offset_seconds = int(user_aware.utcoffset().total_seconds())
                dst_active = bool(user_aware.dst() and user_aware.dst().total_seconds() > 0)
                zone_id = user_provided_zone

                if user_provided_zone != original_zone:
                    warnings.append(f"User zone '{user_provided_zone}' differs from calculated '{original_zone}'")

            except Exception as e:
                # Handle timezone labels like EST, EDT, etc.
                fixed_offsets = {
                    "EST": -18000, "EDT": -14400,
                    "CST": -21600, "CDT": -18000,
                    "PST": -28800, "PDT": -25200,
                    "MST": -25200, "MDT": -21600
                }

                user_zone_upper = user_provided_zone.upper()
                if user_zone_upper in fixed_offsets:
                    offset_seconds = fixed_offsets[user_zone_upper]
                    dst_active = user_zone_upper.endswith('DT')
                    utc_dt = local_dt - timedelta(seconds=offset_seconds)
                    utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
                    warnings.append(f"Used fixed offset for timezone label '{user_provided_zone}'")
                else:
                    warnings.append(f"Invalid user-provided zone '{user_provided_zone}': {e}")

        if user_provided_offset is not None:
            # Use user-provided offset directly
            offset_seconds = user_provided_offset
            utc_dt = local_dt - timedelta(seconds=offset_seconds)
            utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))

            if abs(user_provided_offset - original_offset) > 3600:
                warnings.append(f"User offset ({user_provided_offset}s) differs significantly from calculated ({original_offset}s)")

        confidence = "low"
        reason = f"User-provided values used as requested (as_entered mode)"

    # 7) Build final response
    response = {
        "utc": utc_dt.isoformat().replace("+00:00", "Z"),
        "zone_id": zone_id,
        "offset_seconds": offset_seconds,
        "dst_active": dst_active,
        "confidence": confidence,
        "reason": reason,
        "notes": notes,
        "warnings": warnings,
        "provenance": {
            "tzdb_version": get_tzdb_version(),
            "sources": sources,
            "resolution_mode": parity,
            "patches_applied": patches_applied
        }
    }

    # Log chart completion with full provenance
    logger.info(
        f"CHART_COMPLETED request_id={request_id} "
        f"utc={response['utc']} zone_id={zone_id} "
        f"offset_seconds={offset_seconds} dst_active={dst_active} "
        f"confidence={confidence} patches_applied={patches_applied} "
        f"warnings={len(warnings)}"
    )

    return response