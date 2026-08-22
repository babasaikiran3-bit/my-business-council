FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./backend/

# Railway injects PORT. MCP_PATH must carry a long random secret in production.
ENV MCP_TRANSPORT=streamable-http
USER 1000
CMD ["uv", "run", "python", "-m", "backend.mcp_server"]
