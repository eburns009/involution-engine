# Engine Parity Knobs

The Involution Engine supports multiple **parity profiles** to ensure compatibility with different astrological software systems and historical accuracy requirements. These profiles control how civil time → UTC conversion is performed.

## Parity Profiles

### `strict_history` (Default)
**IANA tzdb + Historical Patches**

- Uses IANA Time Zone Database as the authoritative source
- Applies historical patches for US pre-1967 Standard Time Act era
- Provides maximum historical accuracy for birth times
- **Best for**: Serious astrological work requiring historical precision

**Behavior:**
- Coordinate-based timezone lookup via TimezoneFinder
- Historical patches for 10 US regions (1883-1967)
- Fort Knox, Louisville, Michigan UP, Arizona, Hawaii patches
- War Time and year-round DST handling
- Confidence warnings for edge cases

**Example:**
```json
{
  "parity_profile": "strict_history",
  "birth_time": "1943-06-15T14:30:00",
  "latitude": 37.8917,
  "longitude": -85.9623
}
```

### `astro_com`
**Astrodienst Compatibility Mode**

- Mimics Astro.com (Astrodienst) timezone conventions
- Uses standard IANA tzdb without historical patches
- No custom US pre-1967 corrections applied
- **Best for**: Compatibility with Astrodienst calculations

**Behavior:**
- Standard IANA timezone lookup only
- No historical patches applied
- Modern timezone rules projected backwards
- Maintains consistency with Astro.com results

### `clairvision`
**Clairvision Compatibility Mode**

- Reserved for future Clairvision-specific rules
- Currently behaves similar to `astro_com`
- Placeholder for specialized compatibility needs
- **Best for**: Clairvision software compatibility

### `as_entered`
**Trust User Input Mode**

- Accepts user-provided timezone or offset as authoritative
- Issues warnings when conflicts detected
- Lower confidence ratings for manual overrides
- **Best for**: When user has authoritative local knowledge

**Behavior:**
- Honors `user_provided_zone` field (e.g., "EST", "PDT")
- Honors `user_provided_offset` field (seconds)
- Warns about conflicts with calculated values
- Supports timezone abbreviations (EST, EDT, PST, etc.)
- Sets confidence to "low" due to manual override

**Example:**
```json
{
  "parity_profile": "as_entered",
  "birth_time": "1943-06-15T14:30:00",
  "latitude": 37.8917,
  "longitude": -85.9623,
  "user_provided_zone": "EST"
}
```

## API Integration

### Request Payload
```json
{
  "birth_time": "1987-04-15T09:30:00",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "parity_profile": "strict_history",
  "user_provided_zone": "EST",
  "user_provided_offset": -18000
}
```

### Response Payload
```json
{
  "chart": { ... },
  "meta": {
    "time_resolution": {
      "utc": "1987-04-15T13:30:00Z",
      "zone_id": "America/New_York",
      "offset_seconds": -14400,
      "dst_active": true,
      "confidence": "high",
      "reason": "IANA tzdb historical rules for America/New_York",
      "provenance": {
        "resolution_mode": "strict_history",
        "sources": ["coordinate_lookup", "IANA_tzdb"],
        "patches_applied": []
      }
    },
    "parity_profile": "strict_history"
  }
}
```

## UI Settings

The parity profile should be exposed in the UI settings with clear descriptions:

```typescript
interface ParityProfile {
  value: 'strict_history' | 'astro_com' | 'clairvision' | 'as_entered';
  label: string;
  description: string;
  recommended: boolean;
}

const PARITY_PROFILES: ParityProfile[] = [
  {
    value: 'strict_history',
    label: 'Historical Accuracy (Recommended)',
    description: 'IANA timezone database with historical US patches for maximum accuracy',
    recommended: true
  },
  {
    value: 'astro_com',
    label: 'Astro.com Compatible',
    description: 'Standard IANA rules without patches, matches Astrodienst calculations',
    recommended: false
  },
  {
    value: 'clairvision',
    label: 'Clairvision Compatible',
    description: 'Specialized compatibility mode for Clairvision software',
    recommended: false
  },
  {
    value: 'as_entered',
    label: 'User Override',
    description: 'Trust manually entered timezone/offset with warnings',
    recommended: false
  }
];
```

## Auditability Requirements

Every chart response must include:

1. **Chosen Profile**: The `parity_profile` used for calculations
2. **Resolution Metadata**: Complete time resolution provenance
3. **Warnings**: Any conflicts or low confidence indicators
4. **Sources**: Data sources used (IANA, patches, user input)

This ensures full transparency and reproducibility of all calculations.

## Implementation Notes

- Default to `strict_history` for new charts
- Preserve user's chosen profile in chart metadata
- Log profile usage for analytics
- Validate profile values in API requests
- UI should remember user's preferred profile
- Show confidence warnings prominently when < 0.9

## Migration Strategy

1. Add `parity_profile` field to all chart creation endpoints
2. Default existing charts to `strict_history`
3. Add UI settings panel for profile selection
4. Update documentation and examples
5. Add analytics tracking for profile usage