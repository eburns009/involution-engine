# SPICE Service Module Structure

## Overview
The SPICE service has been refactored into a modular architecture for better maintainability and clarity.

## Module Organization

### 📦 `models.py` (170 lines)
**Purpose**: Pydantic models and type definitions

**Exports**:
- `ChartRequest`, `PlanetPosition`, `ApiMeta`, `CalculationResponse`
- `HousesRequest`, `HousesResponse`
- `TimeResolveRequest`, `TimeResolveResponse`
- `AVAILABLE_BODIES` - Available celestial bodies
- Type aliases: `Zodiac`, `HouseSystem`, `McHemisphere`

**Usage**:
```python
from models import ChartRequest, PlanetPosition, Zodiac
```

### 🏠 `houses.py` (329 lines)
**Purpose**: House system calculations (Placidus, Whole Sign, Equal)

**Key Functions**:
- `_asc_mc_tropical_and_sidereal()` - Calculate ASC/MC
- `_placidus_cusps()` - Placidus house cusps
- `_whole_sign_cusps()` - Whole Sign cusps
- `_equal_cusps()` - Equal house cusps
- `_wrap360()`, `_atan2d()` - Math helpers
- `_obliquity_deg()`, `_jd_from_iso_utc()`, `_gmst_deg()` - Astronomical helpers

**Dependencies**: `spiceypy`, `fastapi`

### 🌍 `time_resolution.py` (256 lines)
**Purpose**: Timezone resolution with historical accuracy

**Key Features**:
- GeoNames database (32,668 cities) with KDTree spatial index
- Regional timezone overrides (Kentucky, Indiana, Michigan, North Dakota)
- Historical DST handling

**Key Functions**:
- `get_historical_timezone()` - Three-tier timezone resolution
- `parse_local_datetime()` - Parse ISO datetime strings
- `localize_datetime_with_dst_handling()` - Handle DST edge cases
- `find_nearest_city_timezone()` - KDTree nearest neighbor search

**Dependencies**: `pytz`, `timezonefinder`, `scipy`

### 🚀 `main.py` (1,106 lines)
**Purpose**: FastAPI application, SPICE calculations, endpoints

**Key Components**:
- FastAPI app initialization
- SPICE kernel management
- Planetary position calculations
- Metrics and logging
- API endpoints: `/health`, `/v1/chart`, `/v1/time/resolve`, `/houses`

**Dependencies**: All of the above modules + `spiceypy`, `fastapi`, `slowapi`

## Dependency Graph

```
models.py          (no internal deps)
   ↑
houses.py          (no internal deps)
   ↑
time_resolution.py (no internal deps)
   ↑
main.py            (imports all above)
```

✅ **No circular dependencies**

## Import Examples

```python
# Import models
from models import ChartRequest, PlanetPosition, AVAILABLE_BODIES

# Import house calculations
from houses import _placidus_cusps, _asc_mc_tropical_and_sidereal

# Import time resolution
from time_resolution import get_historical_timezone, parse_local_datetime
```

## Benefits

1. **Clearer API structure** - Easy to find what you need
2. **Better testability** - Each module can be tested independently
3. **Faster development** - Smaller, focused files
4. **No circular dependencies** - Clean import graph
5. **UI-friendly** - Clear separation makes API integration easier

## File Size Reduction

- **Before**: `main.py` = 1,579 lines
- **After**: `main.py` = 1,106 lines (30% reduction)
- **Total**: 1,861 lines across 4 files

---

*Last updated: 2025-10-04 (File split refactoring)*
