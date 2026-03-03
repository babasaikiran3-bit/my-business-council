#!/bin/bash

# LLM Council - Start script
# Ports are configurable via .env (BACKEND_PORT, FRONTEND_PORT)

# Load .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

BACKEND_PORT=${BACKEND_PORT:-8001}
FRONTEND_PORT=${FRONTEND_PORT:-5173}

echo "Starting LLM Council..."
echo ""

# Start backend
echo "Starting backend on http://localhost:$BACKEND_PORT..."
uv run python -m backend.main &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend (install deps if needed)
echo "Starting frontend on http://localhost:$FRONTEND_PORT..."
cd frontend
if [ ! -d node_modules ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
VITE_BACKEND_PORT=$BACKEND_PORT npx vite --port $FRONTEND_PORT --host &
FRONTEND_PID=$!
cd ..

echo ""
echo "LLM Council is running!"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
