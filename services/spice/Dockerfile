FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching (from services/spice since dockerContext is repo root)
COPY services/spice/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code from services/spice (relative to dockerContext which is repo root)
COPY services/spice/*.py ./
COPY services/spice/tests/ ./tests/

# Copy SPICE kernels from repo root (dockerContext is ".")
# This ensures kernels are baked into the image for Render's ephemeral disk
COPY kernels/ ./kernels/

# Debug: List what was copied to verify kernels are present
RUN echo "=== Kernel files in image ===" && \
    ls -laR /app/kernels/ && \
    echo "=== End kernel listing ==="

# Security: Create non-root user and cache directory
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app /tmp/cache \
    && chown -R appuser:appuser /app /tmp/cache

# Switch to non-root user
USER appuser

# Expose port (Render will override with $PORT)
EXPOSE 8000

# Health check - use $PORT if set, otherwise 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:${PORT:-8000}/health || exit 1

# Environment for multi-process model (CSPICE isn't thread-safe)
ENV WORKERS=${WORKERS:-2}

# Run with gunicorn - bind to $PORT (Render requirement)
CMD ["sh", "-c", "gunicorn main:app -k uvicorn.workers.UvicornWorker --workers $WORKERS --bind 0.0.0.0:${PORT:-8000} --timeout 30"]