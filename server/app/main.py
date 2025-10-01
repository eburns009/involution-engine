# server/app/main.py
import logging
import uuid
import time
import platform
import sys
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .config import load_config, print_config
from .caching import InprocCache, cache_manager
from .caching_redis import RedisCache, HybridCache
from .ephemeris.pool import pool_manager
from .ephemeris.kernels import verify_kernels, KernelBundle
from .schemas import HealthzResponse, ErrorOut
from .obs.logging import setup_logging, StructuredLogger, set_request_context
from .obs.metrics import metrics, get_metrics_content, RequestMetricsMiddleware
from .obs.tracing import setup_tracing, instrument_fastapi_tracing, TracingConfig
from .ephemeris.ayanamsha import load_registry
from .ratelimit import setup_rate_limiting
from . import api

# Will be configured in lifespan
logger = logging.getLogger(__name__)
business_logger = StructuredLogger(__name__)

# Global configuration and services
CONFIG = None
CACHE = None
POOL = None
RATE_LIMITER = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown.
    """
    # Startup
    global CONFIG, CACHE, POOL

    # Load configuration first
    CONFIG = load_config("config.yaml")

    # Setup structured logging
    log_level = getattr(CONFIG, 'log_level', 'INFO')
    setup_logging(level=log_level, enable_json=True)

    # Setup optional tracing
    tracing_config = TracingConfig.from_env()
    tracing_enabled = setup_tracing(tracing_config)
    if tracing_enabled:
        business_logger.startup_event(
            "tracing", "ready",
            details={"service_name": tracing_config.service_name, "endpoint": tracing_config.jaeger_endpoint}
        )
    else:
        business_logger.startup_event("tracing", "disabled")

    logger.info("Starting Involution Engine v1.1...")
    business_logger.startup_event("application", "starting")

    # Print configuration
    print_config(CONFIG)

    # Initialize cache system
    cache_start = time.perf_counter()

    # Initialize in-process cache
    inproc_cache = InprocCache(
        size=CONFIG.cache.inproc_lru_size,
        ttl=CONFIG.cache.inproc_ttl_seconds
    )

    # Initialize Redis cache if enabled
    redis_cache = None
    if CONFIG.cache.redis.enabled:
        try:
            redis_cache = RedisCache(
                url=CONFIG.cache.redis.url,
                ttl=CONFIG.cache.redis.ttl_seconds
            )
            business_logger.startup_event(
                "redis_cache", "ready",
                details={"url": CONFIG.cache.redis.url, "ttl": CONFIG.cache.redis.ttl_seconds}
            )
            logger.info(f"Redis cache enabled: {CONFIG.cache.redis.url}")
        except Exception as e:
            business_logger.startup_event("redis_cache", "error")
            logger.warning(f"Redis cache initialization failed: {e}, using in-process only")
            redis_cache = None
    else:
        business_logger.startup_event("redis_cache", "disabled")
        logger.info("Redis cache disabled")

    # Create hybrid cache if Redis is available, otherwise use in-process only
    if redis_cache:
        CACHE = HybridCache(inproc_cache, redis_cache)
        cache_type = "hybrid (in-process + Redis)"
    else:
        CACHE = inproc_cache
        cache_type = "in-process only"

    cache_duration = (time.perf_counter() - cache_start) * 1000

    business_logger.startup_event(
        "cache", "ready",
        duration_ms=cache_duration,
        details={
            "type": cache_type,
            "inproc_size": CONFIG.cache.inproc_lru_size,
            "inproc_ttl": CONFIG.cache.inproc_ttl_seconds,
            "redis_enabled": CONFIG.cache.redis.enabled
        }
    )
    logger.info(f"Initialized cache system: {cache_type}")

    # Load ayanāṃśa registry
    try:
        registry_start = time.perf_counter()
        load_registry(CONFIG.ephemeris.ayanamsa_registry_file)
        registry_duration = (time.perf_counter() - registry_start) * 1000

        business_logger.startup_event(
            "ayanamsa_registry", "ready",
            duration_ms=registry_duration,
            details={"registry_file": CONFIG.ephemeris.ayanamsa_registry_file}
        )
        logger.info(f"Loaded ayanāṃśa registry from {CONFIG.ephemeris.ayanamsa_registry_file}")
    except Exception as e:
        business_logger.startup_event("ayanamsa_registry", "error")
        logger.warning(f"Failed to load ayanāṃśa registry: {e}, using built-in defaults")

    # Initialize SPICE worker pool
    try:
        pool_start = time.perf_counter()
        business_logger.startup_event("spice_pool", "starting")
        logger.info(f"Initializing SPICE pool with {CONFIG.api.workers} workers...")

        # Verify kernels before starting pool
        kernel_start = time.perf_counter()
        bundle_path = f"{CONFIG.kernels.path}/{CONFIG.kernels.bundle}"
        kernels_valid = verify_kernels(bundle_path, CONFIG.kernels.checksums_file)
        kernel_duration = (time.perf_counter() - kernel_start) * 1000

        business_logger.kernel_operation(
            "verified", bundle_path, CONFIG.kernels.bundle,
            checksum_valid=kernels_valid, duration_ms=kernel_duration
        )

        # Record kernel metrics
        metrics.record_kernel_operation(CONFIG.kernels.bundle, "verify", kernels_valid)

        if kernels_valid:
            logger.info(f"Kernel verification passed for bundle: {CONFIG.kernels.bundle}")
        else:
            logger.warning(f"Kernel verification failed for bundle: {CONFIG.kernels.bundle}")

        # Initialize pool using pool manager
        success = pool_manager.initialize_pool(
            pool_id="default",
            size=CONFIG.api.workers,
            kernels_dir=CONFIG.kernels.path,
            bundle=CONFIG.kernels.bundle
        )

        pool_duration = (time.perf_counter() - pool_start) * 1000

        if success:
            POOL = pool_manager.get_pool("default")
            business_logger.startup_event(
                "spice_pool", "ready",
                duration_ms=pool_duration,
                details={"workers": CONFIG.api.workers, "bundle": CONFIG.kernels.bundle}
            )
            logger.info("SPICE pool initialized successfully")
        else:
            business_logger.startup_event("spice_pool", "error", duration_ms=pool_duration)
            logger.error("Failed to initialize SPICE pool")
            raise RuntimeError("SPICE pool initialization failed")

    except Exception as e:
        business_logger.startup_event("application", "error")
        logger.error(f"Failed to initialize services: {e}")
        raise

    # Set system info metrics
    try:
        import spiceypy
        spice_version = f"spiceypy-{spiceypy.__version__}"
    except:
        spice_version = "unknown"

    metrics.set_system_info(
        version="1.1.0",
        kernel_bundle=CONFIG.kernels.bundle,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        spice_version=spice_version
    )

    # Inject dependencies into API module
    api.CONFIG = CONFIG
    api.CACHE = CACHE
    api.POOL = POOL

    # Setup rate limiting (needs to happen during startup)
    try:
        rate_limit_start = time.perf_counter()
        global RATE_LIMITER

        if CONFIG.ratelimit.enabled:
            from .ratelimit import RedisRateLimiter, ip_key
            rule = CONFIG.ratelimit.rules[0] if CONFIG.ratelimit.rules else None
            if rule:
                RATE_LIMITER = RedisRateLimiter(CONFIG.ratelimit.redis_url, rule.limit)
                rate_limit_duration = (time.perf_counter() - rate_limit_start) * 1000

                business_logger.startup_event(
                    "rate_limiting", "ready",
                    duration_ms=rate_limit_duration,
                    details={"redis_url": CONFIG.ratelimit.redis_url, "limit": rule.limit}
                )
                logger.info(f"Rate limiting enabled: {rule.limit}")
            else:
                business_logger.startup_event("rate_limiting", "error")
                logger.warning("Rate limiting enabled but no rules configured")
        else:
            business_logger.startup_event("rate_limiting", "disabled")
            logger.info("Rate limiting disabled")

    except Exception as e:
        business_logger.startup_event("rate_limiting", "error")
        logger.error(f"Rate limiting setup failed: {e}")
        RATE_LIMITER = None

    startup_total = time.perf_counter() - (cache_start - cache_duration/1000)
    business_logger.startup_event(
        "application", "ready",
        duration_ms=startup_total * 1000
    )
    logger.info("Involution Engine v1.1 startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Involution Engine v1.1...")
    business_logger.startup_event("application", "stopping")

    # Shutdown pool
    if POOL:
        try:
            pool_manager.shutdown_all()
            business_logger.startup_event("spice_pool", "stopped")
            logger.info("SPICE pool shutdown complete")
        except Exception as e:
            logger.error(f"Error during pool shutdown: {e}")

    # Clear cache
    if CACHE:
        CACHE.clear()
        business_logger.startup_event("cache", "cleared")
        logger.info("Cache cleared")

    business_logger.startup_event("application", "stopped")
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Involution Engine",
    version="1.1.0",
    description="Research-grade astronomical calculations with professional accuracy",
    lifespan=lifespan
)

# Setup optional tracing instrumentation
# Note: This must be done after app creation but before middleware setup
instrument_fastapi_tracing(app)

# Setup rate limiting middleware
# Note: This must be done after app creation
try:
    from .ratelimit import setup_rate_limiting
    # Will be setup in startup event since we need CONFIG
except ImportError:
    logger.warning("Rate limiting not available")

# Add metrics middleware
app.add_middleware(RequestMetricsMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will be configured from CONFIG in startup
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_and_request_middleware(request: Request, call_next):
    """
    Combined rate limiting and request logging middleware.
    """
    # Apply rate limiting if enabled
    if RATE_LIMITER:
        try:
            from .ratelimit import ip_key, create_rate_limit_response
            key = ip_key(request)
            allowed, remaining, rate_limit_info = RATE_LIMITER.allow(key)

            if not allowed:
                return create_rate_limit_response(rate_limit_info)
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Continue processing (fail open)

    # Set request context for structured logging
    request_id = set_request_context()

    # Start timer
    start_time = time.perf_counter()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Log request with structured logging
    logger.info(
        "HTTP request processed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_agent": request.headers.get("user-agent", "unknown")
        }
    )

    # Add headers
    response.headers["X-Request-Id"] = request_id

    # Add rate limit headers if rate limiting is enabled
    if RATE_LIMITER and 'rate_limit_info' in locals():
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        if "reset_time" in rate_limit_info:
            response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset_time"])

    # Add cache headers if not already set
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "public, max-age=300"

    return response


@app.get("/healthz", response_model=HealthzResponse)
def healthz():
    """
    Health check endpoint with detailed service status and business metrics.
    """
    try:
        # Check kernel status
        kernels_ok = False
        kernel_info = {}

        if CONFIG:
            bundle_path = f"{CONFIG.kernels.path}/{CONFIG.kernels.bundle}"
            kernels_ok = verify_kernels(bundle_path, CONFIG.kernels.checksums_file)

            # Get kernel bundle info
            try:
                bundle = KernelBundle(bundle_path, CONFIG.kernels.bundle)
                kernel_info = {
                    "bundle": CONFIG.kernels.bundle,
                    "ok": kernels_ok,
                    "path": bundle_path,
                    "verified": bundle.is_verified,
                    "file_count": len(bundle.list_kernels()) if kernels_ok else 0
                }
            except Exception as e:
                kernel_info = {
                    "bundle": CONFIG.kernels.bundle,
                    "ok": False,
                    "error": str(e)
                }

        # Get cache stats with metrics integration
        cache_info = CACHE.get_stats() if CACHE else {"error": "Cache not initialized"}
        if CACHE and "error" not in cache_info:
            # Record cache metrics
            hit_rate = cache_info.get("hit_rate", 0.0)
            if "total_hit_rate" in cache_info:  # Hybrid cache
                hit_rate = cache_info["total_hit_rate"]

            cache_size = cache_info.get("size", 0)
            if "inproc" in cache_info:  # Hybrid cache
                cache_size = cache_info["inproc"].get("size", 0)

            metrics.record_cache_operation(
                "status_check",
                cache_size,
                hit_rate
            )

        # Get pool stats with metrics integration
        pool_info = {}
        if POOL:
            pool_stats = POOL.get_stats()
            pool_info = {
                "size": pool_stats["size"],
                "queue_depth": pool_stats["queue_depth"],
                "total_requests": pool_stats["total_requests"],
                "success_rate": pool_stats["success_rate"],
                "healthy": POOL.is_healthy()
            }
            # Record worker pool metrics
            metrics.record_worker_pool_state(
                pool_stats["size"],
                pool_stats["queue_depth"]
            )
        else:
            pool_info = {"error": "Pool not initialized"}

        # Ephemeris policy info
        ephemeris_info = {}
        if CONFIG:
            ephemeris_info = {
                "policy": CONFIG.ephemeris.policy,
                "de440_range": f"{CONFIG.ephemeris.de440_start} to {CONFIG.ephemeris.de440_end}",
                "default": CONFIG.ephemeris.default
            }

        # Time resolver info
        time_info = {}
        if CONFIG:
            time_info = {
                "tzdb_version": CONFIG.time.tzdb_version,
                "parity_profile_default": CONFIG.time.parity_profile_default,
                "base_url": CONFIG.time.base_url
            }

        # Get business metrics summary
        business_metrics = metrics.get_metrics_summary()

        # Determine overall health
        is_healthy = kernels_ok and POOL and POOL.is_healthy()

        response_data = {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.1.0",
            "kernels": kernel_info,
            "cache": cache_info,
            "cache_health": CACHE.health_check() if hasattr(CACHE, 'health_check') else {"inproc": {"healthy": True}},
            "pool": pool_info,
            "ephemeris": ephemeris_info,
            "time": time_info,
            "metrics": business_metrics,
            "rate_limiting": RATE_LIMITER.get_stats() if RATE_LIMITER else {"enabled": False}
        }

        return response_data

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error": str(e)
            }
        )


# Configure CORS with actual config after startup
@app.on_event("startup")
async def configure_cors():
    """Configure CORS with loaded configuration."""
    if CONFIG and CONFIG.api.cors_origins:
        # Update CORS middleware with actual origins
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                middleware.kwargs["allow_origins"] = CONFIG.api.cors_origins
                break


@app.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint():
    """
    Prometheus metrics endpoint.
    """
    content, content_type = get_metrics_content()
    return PlainTextResponse(content, media_type=content_type)


# Include API routes
app.include_router(api.router)


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(f"Unhandled exception in {request.method} {request.url}: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "code": "SERVER.ERROR",
            "title": "Internal server error",
            "detail": "An unexpected error occurred",
            "tip": "Please try again or contact support if the problem persists"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)