# =====================================================================
# 🏗️ STAGE 1: Build & Dependency Compilation
# =====================================================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --user --no-warn-script-location -r requirements.txt


# =====================================================================
# 🚀 STAGE 2: Hardened Production Runtime (Non-Root, Least-Privilege)
# =====================================================================
FROM python:3.12-slim AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PORT=8000 \
    RATE_LIMIT_ENABLED=true

# Security: Install only essential runtime libraries and curl for probes
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root unprivileged service user (UID/GID 10001)
RUN groupadd --gid 10001 cloudpulse && \
    useradd --uid 10001 --gid cloudpulse --shell /bin/false --create-home cloudpulse

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/cloudpulse/.local
ENV PATH=/home/cloudpulse/.local/bin:$PATH

# Copy backend application code and set ownership
COPY --chown=cloudpulse:cloudpulse backend/ ./backend/
COPY --chown=cloudpulse:cloudpulse bin/ ./bin/

# Prepare runtime cache directory with write permissions for cloudpulse user
RUN mkdir -p /app/backend/.cloudpulse_cache /tmp/cloudpulse && \
    chown -R cloudpulse:cloudpulse /app /tmp/cloudpulse

USER cloudpulse:cloudpulse
WORKDIR /app/backend

EXPOSE 8000

# Docker native SRE liveness probe
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/healthz || exit 1

# Start uvicorn with graceful worker handling
CMD ["sh", "-c", "python -m database.init_db || true; exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --access-log"]
