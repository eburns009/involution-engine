"""
Time Resolver V2 - Streamlined Implementation
Based on the Python sketch for historical timezone resolution
"""

import json
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

# Global instances
TF = TimezoneFinder()

# Load patches from the prepared file
PATCHES_PATH = Path(__file__).parent.parent.parent / "time_resolver_kit" / "patches_us_pre1967.json"
try:
    with open(PATCHES_PATH) as f:
        PATCHES = json.load(f)
        print(f"✓ Loaded {len(PATCHES.get('patches', {}))} patches from {PATCHES_PATH}")
except FileNotFoundError:
    print(f"✗ Patches file not found at {PATCHES_PATH}")
    PATCHES = {"patches": {}, "dst_rules": {}}

# Log TZDB version on module import
try:
    _tzdb_version = get_tzdb_version()
    print(f"✓ TZDB Version: {_tzdb_version}")
except Exception as e:
    print(f"⚠ Could not determine TZDB version: {e}")

def latlon_to_zone(lat: float, lon: float) -> str:
    """Fast path via timezonefinder (uses TZBB polygons)"""
    z = TF.timezone_at(lat=lat, lng=lon)
    if not z:
        # Fallback (rare): use nearest zone or a default
        z = TF.closest_timezone_at(lat=lat, lng=lon) or "Etc/UTC"
    return z

def apply_patches(lat: float, lon: float, local_dt: datetime, context: dict) -> list[dict]:
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

def resolve_time(payload: dict[str, Any]) -> dict[str, Any]:
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
    except Exception:
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
        reason = "User-provided values used as requested (as_entered mode)"

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

    return response

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
