# Backend Dockerfile for LLM Council
FROM python:3.11-slim

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen

# Copy backend source code
COPY backend/ ./backend/

# Expose port
EXPOSE 8001

# Run the application
CMD ["uv", "run", "python", "-m", "backend.main"]

