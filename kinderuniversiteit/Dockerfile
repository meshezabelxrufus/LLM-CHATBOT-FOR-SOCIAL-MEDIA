# ── Stage 1: dependency builder ───────────────────────────────────────────────
# Installs packages into /install so the runtime stage stays minimal.
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps required by some Python packages (asyncpg, chromadb, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Same native libs needed at runtime (libpq for asyncpg).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy application source.
COPY . .

# Non-root user for security.
RUN useradd -m -u 1000 appuser \
 && mkdir -p data/knowledge data/chroma logs \
 && chown -R appuser:appuser /app

USER appuser

# Persistent data directories are expected to be mounted as volumes.
VOLUME ["/app/data", "/app/logs"]

EXPOSE 8000

# Docker HEALTHCHECK — used by docker-compose and container orchestrators.
# Waits 15 s before first check so the app has time to finish startup.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Use exec form so signals (SIGTERM from docker stop) reach uvicorn directly.
# --workers 1: use a single process inside the container; scale horizontally
#              via replicas in Docker Compose / Render / DigitalOcean.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "warning", \
     "--access-log"]
