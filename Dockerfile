FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONPATH=/app/backend

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ ./backend/
COPY bin/ ./bin/

WORKDIR /app/backend

# Render dynamically passes $PORT (e.g. 10000). Default to 8000 for local runs.
ENV PORT=8000
EXPOSE 8000

# Runs database table and hypertable initialization on boot, then starts uvicorn
CMD ["sh", "-c", "python -m database.init_db || true; uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
