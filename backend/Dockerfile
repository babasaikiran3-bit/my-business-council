FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for uv + httpx TLS
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# Install uv (used by this repo)
RUN pip install --no-cache-dir uv

# Install python deps
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

# Copy backend code
COPY backend/ /app/backend/

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]


