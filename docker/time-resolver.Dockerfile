FROM python:3.12-slim

# 1) System deps
# tzdata: ensures consistent IANA tzdb across environments
# ca-certificates: for HTTPS requests
# curl: for health checks
# gcc/g++/make: for building some Python packages if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata ca-certificates curl gcc g++ make \
    && rm -rf /var/lib/apt/lists/*

# 2) Python deps
# tzdata bundles IANA tzdb when OS lacks it; timezonefinder uses TZBB polygons.
WORKDIR /app
COPY docker/time-resolver/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 3) App code + our patches/specs
COPY docker/time-resolver/time_resolver/ /app/time_resolver/
COPY docker/time-resolver/config/patches_us_pre1967.json /app/config/patches_us_pre1967.json
COPY docker/time-resolver/openapi.yaml /app/openapi.yaml

# 4) Create non-root user for security
RUN groupadd -r timeresolver && useradd -r -g timeresolver timeresolver
RUN chown -R timeresolver:timeresolver /app
USER timeresolver

# 5) Env flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC \
    RESOLVER_PATCH_FILE=/app/config/patches_us_pre1967.json \
    PORT=8080 \
    HOST=0.0.0.0

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the application
CMD ["python", "-m", "time_resolver.api"]