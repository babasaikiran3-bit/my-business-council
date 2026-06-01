# Parenting Roundtable backend — single-worker container for a PaaS with a persistent disk.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies from the lockfile via uv (reproducible).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend ./backend

EXPOSE 8001

# Liveness: the PaaS / orchestrator hits /health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health').status==200 else 1)"

# SINGLE worker is load-bearing: the in-process asyncio.Lock storage guard, the in-memory
# rate limiter, and the disk-backed daily quota all assume one process. See DEPLOYMENT.md.
CMD ["uv", "run", "--no-dev", "gunicorn", "backend.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-b", "0.0.0.0:8001", \
     "--timeout", "400", "--graceful-timeout", "30"]
