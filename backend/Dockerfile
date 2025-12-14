# Use official uv Docker image with Python 3.10
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim

# Set working directory
WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen

# Expose the backend port
EXPOSE 9001

# Command to run the application with hot reload
# Note: The actual source code is mounted as a volume for hot reload
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9001", "--reload"]
