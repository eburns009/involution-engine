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


class CacheConfig(BaseModel):
    inproc_lru_enabled: bool = True
    inproc_lru_size: int = 2048
    inproc_ttl_seconds: int = 3600

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


class EphemerisPolicy(BaseModel):
    policy: str = "auto"  # auto | de440 | de441
    de440_start: str = "1550-01-01T00:00:00Z"
    de440_end: str = "2650-01-01T00:00:00Z"
    default: str = "de441"

    @validator('policy')
    def validate_policy(cls, v):
        allowed = ["auto", "de440", "de441"]
        if v not in allowed:
            raise ValueError(f"Invalid ephemeris policy: {v}. Must be one of {allowed}")
        return v


class AppConfig(BaseModel):
    api: APIConfig = APIConfig()
    kernels: KernelConfig = KernelConfig()
    cache: CacheConfig = CacheConfig()
    geocoding: GeocodeConfig = GeocodeConfig()
    time: TimeConfig = TimeConfig()
    ephemeris: EphemerisPolicy = EphemerisPolicy()

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
    print(f"Cache Size: {config.cache.inproc_lru_size} (TTL: {config.cache.inproc_ttl_seconds}s)")
    print(f"Time Resolver: {config.time.base_url}")
    print(f"TZDB Version: {config.time.tzdb_version}")
    print(f"Parity Profile: {config.time.parity_profile_default}")
    print(f"Geocoding: {config.geocoding.base_url}")
    print(f"Ephemeris Policy: {config.ephemeris.policy}")
    print(f"DE440 Range: {config.ephemeris.de440_start} to {config.ephemeris.de440_end}")
    print("=" * 45)