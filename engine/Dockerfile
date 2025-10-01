# Involution Engine - Multi-stage Dockerfile
# Optimized for security, performance, and minimal attack surface

# Build stage
FROM python:3.12-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Add metadata
LABEL maintainer="Involution Engine Team" \
      version="${VERSION}" \
      description="Research-grade astrological calculation engine" \
      build-date="${BUILD_DATE}" \
      vcs-ref="${VCS_REF}"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn uvicorn

# Production stage
FROM python:3.12-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories
RUN mkdir -p /app/logs /app/kernels /tmp/claude \
    && chown -R appuser:appuser /app /tmp/claude

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TMPDIR=/tmp/claude \
    PORT=8000 \
    WORKERS=4 \
    WORKER_TIMEOUT=30

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER appuser

# Default command with kernel download
CMD ["sh", "-c", "bash download_kernels.sh && gunicorn main:app -k uvicorn.workers.UvicornWorker --workers $WORKERS --bind 0.0.0.0:$PORT --timeout $WORKER_TIMEOUT --access-logfile - --error-logfile -"]

# Development stage
FROM production as development

# Switch back to root for development tools installation
USER root

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    htop \
    strace \
    && rm -rf /var/lib/apt/lists/*

# Install development Python packages
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    pytest-asyncio \
    black \
    ruff \
    mypy \
    ipython

# Development environment variables
ENV ENV=development \
    DEBUG=1 \
    LOG_LEVEL=DEBUG

# Switch back to appuser
USER appuser

# Development command with auto-reload
CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]