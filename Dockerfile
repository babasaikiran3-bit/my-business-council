FROM node:24-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./backend/
COPY main.py CLAUDE.md README.md header.jpg ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001
VOLUME ["/app/data"]

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
