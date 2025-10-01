from pydantic import BaseModel, Field, validator
from typing import List, Optional
import yaml
import os


class APIConfig(BaseModel):
    cors_origins: List[str] = []
    rate_limit: str = "200/minute"
    workers: int = 4


class KernelConfig(BaseModel):
    bundle: str = "de440-1900"  # de440-full | de440-1900 | de440-modern
    path: str = "/opt/kernels"
    checksums_file: str = "/opt/kernels/checksums.json"

    @validator('bundle')
    def validate_bundle(cls, v):
        allowed = ["de440-full", "de440-1900", "de440-modern"]
        if v not in allowed:
            raise ValueError(f"Invalid kernel bundle: {v}. Must be one of {allowed}")
        return v


class RedisCacheConfig(BaseModel):
    enabled: bool = False
    url: str = "redis://redis:6379/0"
    ttl_seconds: int = 3600


class CacheConfig(BaseModel):
    inproc_lru_enabled: bool = True
    inproc_lru_size: int = 2048
    inproc_ttl_seconds: int = 3600
    redis: RedisCacheConfig = RedisCacheConfig()

    @validator('inproc_lru_size')
    def validate_cache_size(cls, v):
        if v < 1:
            raise ValueError("Cache size must be positive")
        return v


class GeocodeConfig(BaseModel):
    base_url: str = "http://nominatim-nginx"
    timeout_ms: int = 2000

    @validator('timeout_ms')
    def validate_timeout(cls, v):
        if v < 100 or v > 30000:
            raise ValueError("Timeout must be between 100ms and 30s")
        return v


class TimeConfig(BaseModel):
    base_url: str = "http://localhost:9000"  # your time resolver
    tzdb_version: str = "2025.1"
    parity_profile_default: str = "strict_history"

    @validator('parity_profile_default')
    def validate_parity_profile(cls, v):
        allowed = ["strict_history", "best_effort", "modern_only"]
        if v not in allowed:
            raise ValueError(f"Invalid parity profile: {v}. Must be one of {allowed}")
        return v


class RateLimitRule(BaseModel):
    key: str = "ip"
    limit: str = "200/minute"  # parse as tokens/minute


class RateLimitConfig(BaseModel):
    enabled: bool = False
    redis_url: str = "redis://redis:6379/1"
    rules: List[RateLimitRule] = [RateLimitRule()]


class EphemerisConfig(BaseModel):
    policy: str = "auto"  # auto | de440 | de441
    de440_start: str = "1550-01-01T00:00:00Z"
    de440_end: str = "2650-01-01T00:00:00Z"
    default: str = "de441"
    ayanamsa_registry_file: str = "server/app/ephemeris/ayanamsas.yaml"

    @validator('policy')
    def validate_policy(cls, v):
        allowed = ["auto", "de440", "de441"]
        if v not in allowed:
            raise ValueError(f"Invalid ephemeris policy: {v}. Must be one of {allowed}")
        return v


class FixedStarsConfig(BaseModel):
    enabled: bool = False
    catalog: str = "bsc5"  # "bsc5" (Yale Bright Star) or "hipparcos"
    mag_limit: float = 2.5
    topocentric: bool = False  # v1: geocentric only; topocentric in a later phase

    @validator('catalog')
    def validate_catalog(cls, v):
        allowed = ["bsc5", "hipparcos"]
        if v not in allowed:
            raise ValueError(f"Invalid star catalog: {v}. Must be one of {allowed}")
        return v

    @validator('mag_limit')
    def validate_mag_limit(cls, v):
        if v < -2.0 or v > 10.0:
            raise ValueError("Magnitude limit must be between -2.0 and 10.0")
        return v


class FeaturesConfig(BaseModel):
    fixed_stars: FixedStarsConfig = FixedStarsConfig()


class AppConfig(BaseModel):
    api: APIConfig = APIConfig()
    kernels: KernelConfig = KernelConfig()
    cache: CacheConfig = CacheConfig()
    geocoding: GeocodeConfig = GeocodeConfig()
    time: TimeConfig = TimeConfig()
    ephemeris: EphemerisConfig = EphemerisConfig()
    ratelimit: RateLimitConfig = RateLimitConfig()
    features: FeaturesConfig = FeaturesConfig()

    class Config:
        extra = "forbid"  # Prevent unexpected config keys


def load_config(path: str = "config.yaml") -> AppConfig:
    """Load configuration from YAML file with environment variable overrides."""
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Warning: Config file {path} not found, using defaults")
        data = {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file {path}: {e}")

    # Basic environment variable overrides
    env_overrides = {}

    # API overrides
    if "CORS_ORIGINS" in os.environ:
        env_overrides.setdefault("api", {})["cors_origins"] = os.environ["CORS_ORIGINS"].split(",")
    if "WORKERS" in os.environ:
        env_overrides.setdefault("api", {})["workers"] = int(os.environ["WORKERS"])

    # Kernel overrides
    if "KERNEL_BUNDLE" in os.environ:
        env_overrides.setdefault("kernels", {})["bundle"] = os.environ["KERNEL_BUNDLE"]
    if "KERNEL_PATH" in os.environ:
        env_overrides.setdefault("kernels", {})["path"] = os.environ["KERNEL_PATH"]

    # Time resolver overrides
    if "TIME_RESOLVER_URL" in os.environ:
        env_overrides.setdefault("time", {})["base_url"] = os.environ["TIME_RESOLVER_URL"]
    if "TZDB_VERSION" in os.environ:
        env_overrides.setdefault("time", {})["tzdb_version"] = os.environ["TZDB_VERSION"]

    # Geocoding overrides
    if "GEOCODE_URL" in os.environ:
        env_overrides.setdefault("geocoding", {})["base_url"] = os.environ["GEOCODE_URL"]

    # Redis cache overrides
    if "REDIS_CACHE_ENABLED" in os.environ:
        env_overrides.setdefault("cache", {}).setdefault("redis", {})["enabled"] = os.environ["REDIS_CACHE_ENABLED"].lower() == "true"
    if "REDIS_CACHE_URL" in os.environ:
        env_overrides.setdefault("cache", {}).setdefault("redis", {})["url"] = os.environ["REDIS_CACHE_URL"]

    # Rate limiting overrides
    if "RATELIMIT_ENABLED" in os.environ:
        env_overrides.setdefault("ratelimit", {})["enabled"] = os.environ["RATELIMIT_ENABLED"].lower() == "true"
    if "RATELIMIT_REDIS_URL" in os.environ:
        env_overrides.setdefault("ratelimit", {})["redis_url"] = os.environ["RATELIMIT_REDIS_URL"]

    # Fixed stars feature overrides
    if "FIXED_STARS_ENABLED" in os.environ:
        env_overrides.setdefault("features", {}).setdefault("fixed_stars", {})["enabled"] = os.environ["FIXED_STARS_ENABLED"].lower() == "true"
    if "FIXED_STARS_CATALOG" in os.environ:
        env_overrides.setdefault("features", {}).setdefault("fixed_stars", {})["catalog"] = os.environ["FIXED_STARS_CATALOG"]
    if "FIXED_STARS_MAG_LIMIT" in os.environ:
        env_overrides.setdefault("features", {}).setdefault("fixed_stars", {})["mag_limit"] = float(os.environ["FIXED_STARS_MAG_LIMIT"])

    # Merge environment overrides into config data
    def merge_dict(base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                merge_dict(base[key], value)
            else:
                base[key] = value

    merge_dict(data, env_overrides)

    try:
        return AppConfig(**data)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")


def print_config(config: AppConfig) -> None:
    """Print effective configuration on startup."""
    print("=== Involution Engine v1.1 Configuration ===")
    print(f"API Workers: {config.api.workers}")
    print(f"CORS Origins: {config.api.cors_origins}")
    print(f"Rate Limit: {config.api.rate_limit}")
    print(f"Kernel Bundle: {config.kernels.bundle}")
    print(f"Kernel Path: {config.kernels.path}")
    print(f"Cache In-Proc: {config.cache.inproc_lru_size} entries (TTL: {config.cache.inproc_ttl_seconds}s)")
    print(f"Cache Redis: {'enabled' if config.cache.redis.enabled else 'disabled'} ({config.cache.redis.url})")
    print(f"Rate Limiting: {'enabled' if config.ratelimit.enabled else 'disabled'} ({config.ratelimit.redis_url})")
    print(f"Time Resolver: {config.time.base_url}")
    print(f"TZDB Version: {config.time.tzdb_version}")
    print(f"Parity Profile: {config.time.parity_profile_default}")
    print(f"Geocoding: {config.geocoding.base_url}")
    print(f"Ephemeris Policy: {config.ephemeris.policy}")
    print(f"DE440 Range: {config.ephemeris.de440_start} to {config.ephemeris.de440_end}")
    print(f"Ayanāṃśa Registry: {config.ephemeris.ayanamsa_registry_file}")
    print(f"Fixed Stars: {'enabled' if config.features.fixed_stars.enabled else 'disabled'} (catalog: {config.features.fixed_stars.catalog}, mag ≤ {config.features.fixed_stars.mag_limit})")
    print("=" * 45)