FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./backend/

# Railway injects PORT. MCP_PATH must carry a long random secret in production.
ENV MCP_TRANSPORT=streamable-http
USER 1000
# Run the venv python directly - uv at runtime would try to write a cache
# into /app, which the non-root user cannot do.
CMD ["/app/.venv/bin/python", "-m", "backend.mcp_server"]
