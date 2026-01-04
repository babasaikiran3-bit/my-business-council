#!/bin/bash

# LLM Council - Start script

set -e

echo "========================================"
echo "       LLM Council - Start Script"
echo "========================================"
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "[ERROR] 'uv' is not installed. Please install it first: https://docs.astral.sh/uv/"
    exit 1
fi

# Check for npm
if ! command -v npm &> /dev/null; then
    echo "[ERROR] 'npm' is not installed. Please install Node.js first."
    exit 1
fi

# 1. Backend Setup
echo "[Backend] Syncing dependencies..."
uv sync

# 2. Frontend Setup
if [ ! -d "frontend/node_modules" ]; then
    echo "[Frontend] Installing dependencies..."
    cd frontend
    npm install
    cd ..
fi

# 3. Check Environment
if [ ! -f ".env" ]; then
    echo ""
    echo "[WARNING] .env file not found!"
    echo "Please create a .env file in the root directory with:"
    echo "OPENROUTER_API_KEY=sk-or-v1-..."
    echo ""
    read -p "Press Enter to continue anyway..."
fi

echo ""
echo "Starting services..."

# Start backend
echo "Starting backend on http://localhost:8001..."
uv run python -m backend.main &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ LLM Council is running!"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
