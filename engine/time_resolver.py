"""
Time Resolver Module
Historical timezone resolution for astrological calculations
"""

import json
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytz

# Try to import the timezonefinder library for coordinate-to-timezone lookup
try:
    from timezonefinder import TimezoneFinder
    TIMEZONE_FINDER_AVAILABLE = True
except ImportError:
    TIMEZONE_FINDER_AVAILABLE = False
    TimezoneFinder = None

@dataclass
class TimeResolveRequest:
    local_datetime: str
    latitude: float
    longitude: float
    parity_profile: str = "strict_history"
    user_provided_zone: str | None = None
    user_provided_offset: int | None = None

@dataclass
class Provenance:
    tzdb_version: str
    sources: list[str]
    resolution_mode: str
    patches_applied: list[str]

@dataclass
class TimeResolveResponse:
    utc: str
    zone_id: str
    offset_seconds: int
    dst_active: bool
    confidence: str
    reason: str
    notes: list[str]
    provenance: Provenance
    warnings: list[str]

class TimeResolver:
    def __init__(self, patches_file: str = None):
        """Initialize the time resolver with patch data"""
        self.patches_data = {}
        self.tf = None

        # Initialize timezone finder if available
        if TIMEZONE_FINDER_AVAILABLE:
            try:
                self.tf = TimezoneFinder()
            except Exception as e:
                print(f"Warning: Could not initialize TimezoneFinder: {e}")

        # Load patches file
        if patches_file:
            self.load_patches(patches_file)
        else:
            # Try to load from default location
            default_patches = Path(__file__).parent.parent / "time_resolver_kit" / "patches_us_pre1967.json"
            if default_patches.exists():
                self.load_patches(str(default_patches))
            else:
                # Fallback to old location for compatibility
                old_default_patches = Path(__file__).parent.parent.parent / "time_resolver_kit" / "patches_us_pre1967.json"
                if old_default_patches.exists():
                    self.load_patches(str(old_default_patches))

    def load_patches(self, patches_file: str):
        """Load historical timezone patches"""
        try:
            with open(patches_file) as f:
                self.patches_data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load patches file {patches_file}: {e}")
            self.patches_data = {}

    def coordinate_to_timezone(self, lat: float, lon: float) -> str | None:
        """Map coordinates to IANA timezone using TimezoneFinder"""
        if self.tf:
            try:
                return self.tf.timezone_at(lat=lat, lng=lon)
            except Exception:
                pass

        # Fallback: Simple coordinate-based mapping for major regions
        return self._fallback_coordinate_mapping(lat, lon)

    def _fallback_coordinate_mapping(self, lat: float, lon: float) -> str:
        """Fallback coordinate to timezone mapping"""
        # Simple fallback based on longitude zones
        if -180 <= lon < -157.5:
            return "Pacific/Honolulu"
        elif -157.5 <= lon < -142.5:
            return "America/Anchorage"
        elif -142.5 <= lon < -127.5:
            return "America/Los_Angeles"
        elif -127.5 <= lon < -112.5:
            return "America/Denver"
        elif -112.5 <= lon < -97.5:
            return "America/Chicago"
        elif -97.5 <= lon < -82.5:
            return "America/New_York"
        elif -82.5 <= lon < -67.5:
            return "America/Halifax"
        elif -67.5 <= lon < 0:
            return "UTC"
        elif 0 <= lon < 15:
            return "Europe/London"
        elif 15 <= lon < 30:
            return "Europe/Paris"
        elif 30 <= lon < 45:
            return "Europe/Moscow"
        else:
            # Default fallback
            return "UTC"

    def check_patches(self, lat: float, lon: float, dt: datetime) -> dict | None:
        """Check if any historical patches apply to this location and time"""
        if not self.patches_data.get("patches"):
            return None

        for patch_id, patch in self.patches_data["patches"].items():
            coords = patch.get("coordinates", {})
            date_range = patch.get("date_range", {})

            # Check coordinate bounds
            if not (coords.get("min_lat", -90) <= lat <= coords.get("max_lat", 90) and
                    coords.get("min_lon", -180) <= lon <= coords.get("max_lon", 180)):
                continue

            # Check date range
            start_date = datetime.fromisoformat(date_range.get("start", "1800-01-01"))
            end_date = datetime.fromisoformat(date_range.get("end", "2100-01-01"))

            if start_date <= dt <= end_date:
                return {
                    "patch_id": patch_id,
                    "patch_data": patch
                }

        return None

    def apply_parity_profile(self, request: TimeResolveRequest, base_result: dict) -> dict:
        """Apply parity profile adjustments"""
        result = base_result.copy()

        # For as_entered mode, check if historical patches would have applied
        historical_patch_info = None
        if request.parity_profile == "as_entered":
            local_dt = datetime.fromisoformat(request.local_datetime.replace('Z', ''))
            patch_result = self.check_patches(request.latitude, request.longitude, local_dt)
            if patch_result:
                historical_patch_info = patch_result

        if request.parity_profile == "astro_com":
            # Astro.com legacy assumptions
            result["notes"].append("Applied Astro.com compatibility mode")
            # Astro.com tends to use standard time zones without detailed historical research
            if "patch" in result.get("sources", []):
                result["confidence"] = "medium"
                result["notes"].append("Simplified historical rules for Astro.com compatibility")

        elif request.parity_profile == "clairvision":
            # Clairvision legacy assumptions
            result["notes"].append("Applied Clairvision compatibility mode")
            # Similar simplifications as astro.com
            if "patch" in result.get("sources", []):
                result["confidence"] = "medium"

        elif request.parity_profile == "as_entered":
            # Trust user input even if it conflicts
            if request.user_provided_zone or request.user_provided_offset is not None:
                original_zone = result["zone_id"]
                original_offset = result["offset_seconds"]

                if request.user_provided_zone:
                    try:
                        # Try zoneinfo first (IANA tzdb authoritative source)
                        user_tz = ZoneInfo(request.user_provided_zone)
                        result["zone_id"] = request.user_provided_zone
                        # Recalculate with user timezone
                        local_dt = datetime.fromisoformat(request.local_datetime)
                        localized_dt = local_dt.replace(tzinfo=user_tz)
                        result["utc"] = localized_dt.astimezone(UTC).isoformat()
                        result["offset_seconds"] = int(localized_dt.utcoffset().total_seconds())
                        result["dst_active"] = localized_dt.dst().total_seconds() > 0
                    except Exception as e:
                        # Fallback to pytz for compatibility
                        try:
                            user_tz = pytz.timezone(request.user_provided_zone)
                            result["zone_id"] = request.user_provided_zone
                            local_dt = datetime.fromisoformat(request.local_datetime)
                            localized_dt = user_tz.localize(local_dt)
                            result["utc"] = localized_dt.astimezone(UTC).isoformat()
                            result["offset_seconds"] = int(localized_dt.utcoffset().total_seconds())
                            result["dst_active"] = localized_dt.dst().total_seconds() > 0
                            result["warnings"].append(f"Used pytz fallback for user zone '{request.user_provided_zone}'")
                        except Exception as e2:
                            result["warnings"].append(f"Invalid user-provided zone '{request.user_provided_zone}': {e}, {e2}")

                if request.user_provided_offset is not None:
                    # Use user-provided offset directly
                    local_dt = datetime.fromisoformat(request.local_datetime)
                    utc_dt = local_dt - timedelta(seconds=request.user_provided_offset)
                    result["utc"] = utc_dt.replace(tzinfo=UTC).isoformat()
                    result["offset_seconds"] = request.user_provided_offset

                # Add warnings about conflicts
                if request.user_provided_offset and abs(request.user_provided_offset - original_offset) > 3600:
                    result["warnings"].append(f"User offset ({request.user_provided_offset}s) differs significantly from calculated ({original_offset}s)")

                if request.user_provided_zone and request.user_provided_zone != original_zone:
                    base_warning = f"User zone '{request.user_provided_zone}' differs from calculated '{original_zone}'"
                    if historical_patch_info:
                        patch_data = historical_patch_info["patch_data"]
                        historical_reason = patch_data.get("reason", "historical rule")
                        base_warning += f". Corrected to EST per {historical_reason}"
                    result["warnings"].append(base_warning)

                result["confidence"] = "low"
                result["reason"] = f"User-provided values used as requested ({request.parity_profile} mode)"

        return result

    def resolve_time(self, request: TimeResolveRequest) -> TimeResolveResponse:
        """Main time resolution function"""
        try:
            # Parse the local datetime
            local_dt = datetime.fromisoformat(request.local_datetime.replace('Z', ''))

            # Initialize response data
            sources = ["coordinate_lookup"]
            notes = []
            warnings = []
            patches_applied = []

            # Get base timezone from coordinates
            base_zone_id = self.coordinate_to_timezone(request.latitude, request.longitude)
            if not base_zone_id:
                base_zone_id = "UTC"
                warnings.append("Could not determine timezone from coordinates, using UTC")

            # Check for historical patches
            patch_result = self.check_patches(request.latitude, request.longitude, local_dt)

            if patch_result and request.parity_profile == "strict_history":
                # Apply historical patch
                patch_data = patch_result["patch_data"]
                zone_id = patch_data["override"]["zone_id"]
                offset_seconds = patch_data["override"]["offset_seconds"]
                reason = patch_data["reason"]
                confidence = patch_data["confidence"]

                sources.extend(["TZDB", "historical_patches"])
                notes.append(f"Applied patch: {patch_result['patch_id']}")
                notes.extend(patch_data.get("sources", []))
                patches_applied.append(patch_result["patch_id"])

                # Calculate UTC time using patch offset
                utc_dt = local_dt - timedelta(seconds=offset_seconds)
                utc_time = utc_dt.replace(tzinfo=UTC)

                # Determine DST status (simplified)
                dst_active = self._calculate_dst_status(local_dt, patch_data.get("override", {}).get("dst_rules", "none"))

            else:
                # Use standard IANA tzdb lookup via zoneinfo
                try:
                    tz = ZoneInfo(base_zone_id)
                    localized_dt = local_dt.replace(tzinfo=tz)
                    utc_time = localized_dt.astimezone(UTC)
                    offset_seconds = int(localized_dt.utcoffset().total_seconds())
                    dst_active = localized_dt.dst() is not None and localized_dt.dst().total_seconds() > 0
                    zone_id = base_zone_id
                    reason = f"IANA tzdb historical rules for {base_zone_id}"
                    confidence = "high"
                    sources.append("IANA_tzdb")

                except Exception as e:
                    # Fallback to pytz if zoneinfo fails, then to UTC
                    try:
                        tz = pytz.timezone(base_zone_id)
                        localized_dt = tz.localize(local_dt)
                        utc_time = localized_dt.astimezone(UTC)
                        offset_seconds = int(localized_dt.utcoffset().total_seconds())
                        dst_active = localized_dt.dst() is not None and localized_dt.dst().total_seconds() > 0
                        zone_id = base_zone_id
                        reason = f"pytz fallback for {base_zone_id}"
                        confidence = "medium"
                        sources.append("pytz_fallback")
                        warnings.append(f"Using pytz fallback: {e}")
                    except Exception as e2:
                        # Final fallback to UTC
                        utc_time = local_dt.replace(tzinfo=UTC)
                        offset_seconds = 0
                        dst_active = False
                        zone_id = "UTC"
                        reason = f"Fallback to UTC due to timezone error: {e2}"
                        confidence = "low"
                        warnings.append(f"All timezone lookups failed: {e}, {e2}")

            # Create base result
            base_result = {
                "utc": utc_time.isoformat(),
                "zone_id": zone_id,
                "offset_seconds": offset_seconds,
                "dst_active": dst_active,
                "confidence": confidence,
                "reason": reason,
                "notes": notes,
                "warnings": warnings,
                "sources": sources,
                "patches_applied": patches_applied
            }

            # Apply parity profile adjustments
            final_result = self.apply_parity_profile(request, base_result)

            # Build provenance
            provenance = Provenance(
                tzdb_version=self._get_tzdb_version(),
                sources=final_result["sources"],
                resolution_mode=request.parity_profile,
                patches_applied=final_result["patches_applied"]
            )

            return TimeResolveResponse(
                utc=final_result["utc"],
                zone_id=final_result["zone_id"],
                offset_seconds=final_result["offset_seconds"],
                dst_active=final_result["dst_active"],
                confidence=final_result["confidence"],
                reason=final_result["reason"],
                notes=final_result["notes"],
                provenance=provenance,
                warnings=final_result["warnings"]
            )

        except Exception as e:
            # Error fallback
            return TimeResolveResponse(
                utc=datetime.now(UTC).isoformat(),
                zone_id="UTC",
                offset_seconds=0,
                dst_active=False,
                confidence="unknown",
                reason=f"Error in time resolution: {str(e)}",
                notes=[],
                provenance=Provenance(
                    tzdb_version=self._get_tzdb_version(),
                    sources=["error_fallback"],
                    resolution_mode=request.parity_profile,
                    patches_applied=[]
                ),
                warnings=[f"Time resolution failed: {str(e)}"]
            )

    def _calculate_dst_status(self, local_dt: datetime, dst_rules: str) -> bool:
        """Calculate DST status based on rules"""
        if dst_rules == "none":
            return False

        # Simplified DST calculation for US standard rules
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

    def _get_tzdb_version(self) -> str:
        """Get IANA tzdb version from zoneinfo"""
        try:
            # Get the actual IANA tzdb version from zoneinfo
            import zoneinfo
            # The IANA tzdb version is available via the IANA_VERSION attribute
            if hasattr(zoneinfo, 'IANA_VERSION'):
                return zoneinfo.IANA_VERSION
            # Fallback: try to get it from tzdata package
            try:
                import tzdata
                if hasattr(tzdata, '__version__'):
                    return f"tzdata-{tzdata.__version__}"
            except ImportError:
                pass
            # Last fallback: try pytz version
            try:
                import pytz
                return f"pytz-{getattr(pytz, '__version__', 'unknown')}"
            except ImportError:
                pass
            return "unknown"
        except Exception:
            return "unknown"

# Global instance
time_resolver = TimeResolver()
