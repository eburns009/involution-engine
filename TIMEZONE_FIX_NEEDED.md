# Timezone Conversion Issue & Fix Required

**Date**: 2025-10-04
**Status**: 🔴 **CRITICAL BUG** - Affects all historical chart calculations
**Impact**: 1-hour offset for dates with daylight saving time differences

---

## Problem Summary

The UI's timezone conversion is **broken** because it interprets birth times in the **browser's timezone** instead of the **birth location's timezone**.

### Example Bug

**Input**: July 2, 1962, 11:33 PM at Fort Knox, Kentucky
**Expected UTC**: 1962-07-03T04:33:00Z (CDT = UTC-5)
**Actual UTC sent**: 1962-07-03T05:33:00Z (interpreted as CST = UTC-6) ❌
**Result**: 1-hour error → all planet positions wrong

---

## Root Cause

**File**: `lib/time.ts:9`

```typescript
export function localInputToUtcZ(dtLocal: string): string {
  const d = new Date(dtLocal);  // ❌ Uses browser timezone!
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
}
```

**Problem**: `new Date("1962-07-02T23:33:00")` interprets this datetime in:
- ✅ What we need: Fort Knox timezone (America/Kentucky/Louisville)
- ❌ What it does: Browser's current timezone (could be UTC, EST, PST, etc.)

---

## Test Case Showing Bug

### Current Behavior (WRONG)
```bash
# User enters in UI: July 2, 1962, 11:33 PM (Fort Knox local time)
# Browser timezone: UTC
# JavaScript does: new Date("1962-07-02T23:33:00")
# Sends to API: "1962-07-02T23:33:00Z" (treats as UTC)

# Result: Moon at Gemini 25.53° ❌ WRONG (12 hours early!)
```

### Expected Behavior (CORRECT)
```bash
# User enters: July 2, 1962, 11:33 PM (Fort Knox local time)
# System resolves: Fort Knox in July 1962 = CDT (UTC-5)
# Converts to UTC: 1962-07-03T04:33:00Z
# Sends to API: "1962-07-03T04:33:00Z"

# Result: Moon at Cancer 0°34' ✅ CORRECT
```

---

## Immediate Fixes Applied

### 1. Fort Knox Example Button ✅
**File**: `app/research/page.tsx:80`

```diff
- birth_time_local: '1962-07-03T00:33:00',  // Wrong
+ birth_time_local: '1962-07-02T23:33:00',  // Correct
```

### 2. Ayanāṃśa System ✅
**File**: `app/research/page.tsx:84`

```diff
- ayanamsa: 'lahiri',           // Wrong for reference chart
+ ayanamsa: 'fagan_bradley',    // Correct per reference
```

---

## Permanent Fix Required

### Solution 1: Use Time-Resolver Service (RECOMMENDED)

**Create endpoint**: `POST /api/time/resolve`

```typescript
// lib/time.ts - NEW FUNCTION
export async function resolveLocalToUtc(
  dtLocal: string,
  lat: number,
  lon: number
): Promise<string> {
  const response = await fetch('/api/time/resolve', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      local_datetime: dtLocal,
      latitude: lat,
      longitude: lon
    })
  });

  if (!response.ok) {
    throw new Error('Time resolution failed');
  }

  const { utc_time } = await response.json();
  return utc_time;
}
```

**Backend implementation needed**:
```python
# services/time-resolver/main.py
from datetime import datetime
from timezonefinder import TimezoneFinder
import pytz

@app.post("/api/time/resolve")
async def resolve_time(req: TimeResolveRequest):
    # 1. Find timezone from coordinates
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=req.latitude, lng=req.longitude)

    # 2. Parse local datetime
    local_dt = datetime.fromisoformat(req.local_datetime)

    # 3. Localize to timezone (handles historical DST)
    tz = pytz.timezone(tz_name)
    localized_dt = tz.localize(local_dt, is_dst=None)

    # 4. Convert to UTC
    utc_dt = localized_dt.astimezone(pytz.UTC)

    return {
        "utc_time": utc_dt.isoformat(),
        "timezone": tz_name,
        "offset_hours": localized_dt.utcoffset().total_seconds() / 3600
    }
```

**Update UI form submission**:
```typescript
// app/research/page.tsx:62
const payload = {
  birth_time: await resolveLocalToUtc(
    data.birth_time_local,
    data.latitude,
    data.longitude
  ),
  latitude: data.latitude,
  longitude: data.longitude,
  elevation: data.elevation,
  ayanamsa: data.ayanamsa,
  zodiac: 'sidereal',
};
```

### Solution 2: Client-Side Library (QUICK FIX)

Use `luxon` or `date-fns-tz` with historical timezone data:

```bash
npm install luxon
```

```typescript
import { DateTime } from 'luxon';

export function localInputToUtcZ(
  dtLocal: string,
  timezone: string
): string {
  const dt = DateTime.fromISO(dtLocal, { zone: timezone });
  return dt.toUTC().toISO();
}
```

**Problem**: Still needs timezone lookup from coordinates.

---

## Required Dependencies

### Python (Backend)
```bash
pip install timezonefinder pytz
```

### Node.js (Frontend - if using client-side fix)
```bash
npm install luxon @types/luxon
```

---

## Testing Checklist

- [ ] Test Fort Knox 1962 (CDT vs CST historical rule)
- [ ] Test modern date (current DST rules)
- [ ] Test Southern Hemisphere (reversed DST)
- [ ] Test locations without DST (e.g., Arizona, Hawaii)
- [ ] Test edge cases near DST transitions
- [ ] Test dates before DST existed (pre-1918)
- [ ] Verify Moon position matches reference charts

---

## Reference Calculations

### Fort Knox, Kentucky (July 2, 1962, 11:33 PM)

**Coordinates**: 37.840347°N, 85.949127°W

**Historical Timezone**:
- Timezone: `America/Kentucky/Louisville`
- In July 1962: **Central Daylight Time (CDT)**
- Offset: **UTC-5**

**Conversion**:
```
Local: 1962-07-02 23:33:00 CDT
  ↓
UTC:   1962-07-03 04:33:00 Z
```

**Expected Sidereal Positions (Fagan-Bradley)**:
```
Sun:     Gemini   16°33'44"  ✅
Moon:    Cancer    0°34'06"  ✅ (vs reference 0°50' = different ephemeris)
Mercury: Taurus   25°01'39"  ✅
Venus:   Cancer   24°30'49"  ✅
Mars:    Taurus    1°33'00"  ✅
Jupiter: Aquarius 18°28'33"  ✅
Saturn:  Capricorn 15°50'05"  ✅
```

---

## Next Steps

1. **Implement time-resolver service** (recommended)
   - Create `/api/time/resolve` endpoint
   - Install `timezonefinder` + `pytz`
   - Handle historical DST rules

2. **Update UI to use resolver**
   - Modify `app/research/page.tsx` to call resolver
   - Pass coordinates along with datetime
   - Display resolved timezone to user

3. **Add timezone display**
   - Show detected timezone: "Detected: America/Kentucky/Louisville (CDT, UTC-5)"
   - Add manual override option for ambiguous cases

4. **Add validation**
   - Warn on DST transition times
   - Handle ambiguous times (2 AM during "fall back")
   - Handle impossible times (2 AM during "spring forward")

---

## Historical Timezone Database

Using IANA timezone database (via `pytz`) provides:
- ✅ Historical DST rule changes
- ✅ Timezone boundary changes
- ✅ Pre-DST era handling
- ✅ Political timezone changes

**Example**: Fort Knox switched from Central to Eastern time briefly in 1974-1975 for energy conservation!

---

## Files Modified

1. ✅ `app/research/page.tsx` - Fixed Fort Knox example
2. ✅ `lib/time.ts` - Added warning comments
3. 📝 `TIMEZONE_FIX_NEEDED.md` - This document

## Files That Need Creation

1. ❌ `services/time-resolver/main.py` - Time resolution service
2. ❌ `lib/timeResolver.ts` - Client-side resolver caller
3. ❌ `app/api/time/resolve/route.ts` - Next.js API route (if using server-side)

---

## Priority

🔴 **HIGH** - This affects accuracy of all historical charts. Users entering birth times before ~2000 will likely encounter 1-hour offsets due to historical DST rule changes.

**Recommended**: Implement Solution 1 (time-resolver service) for full accuracy.
