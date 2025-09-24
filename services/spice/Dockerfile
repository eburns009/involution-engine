FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Download SPICE kernels if needed
RUN if [ ! -f kernels/spk/planets/de440.bsp ]; then \
        chmod +x tools/download_kernels.sh && \
        ./tools/download_kernels.sh; \
    fi

# Security: Create non-root user and cache directory
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app /tmp/cache \
    && chown -R appuser:appuser /app /tmp/cache

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8000/health || exit 1

# Environment for multi-process model
ENV WORKERS=${WORKERS:-4}

# Run with multi-process model and security hardening
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers $WORKERS"]