# Gunicorn configuration for SPICE service
# IMPORTANT: CSPICE is NOT thread-safe - use process-based workers only

import multiprocessing
import os

# Process model: 2 workers per vCPU (safe starting point)
workers = int(os.getenv("WORKERS", multiprocessing.cpu_count() * 2))

# Use Uvicorn workers (async support)
worker_class = "uvicorn.workers.UvicornWorker"

# Binding
bind = f"0.0.0.0:{os.getenv('PORT', 8000)}"

# Timeouts
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100

# Process management
preload_app = False  # CRITICAL: Each worker must load SPICE independently
worker_tmp_dir = "/dev/shm"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security
limit_request_line = 2048
limit_request_fields = 32
limit_request_field_size = 4096

# Worker lifecycle for SPICE state management
def worker_int(worker):
    """Called when worker receives INT or QUIT signal"""
    worker.log.info("Worker received INT/QUIT, cleaning up SPICE kernels")

def on_exit(server):
    """Called when master exits"""
    server.log.info("Master process exiting")

# Environment-specific overrides
if os.getenv("ENVIRONMENT") == "production":
    # Production: More conservative settings
    timeout = 60
    max_requests = 500
    workers = min(workers, 8)  # Cap at 8 workers for memory management

    # Enable detailed request logging in production
    capture_output = True
    enable_stdio_inheritance = True