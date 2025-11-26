#!/bin/bash

# LLM Council - Start script

# Function to kill process on a port
kill_port() {
    local port=$1
    echo "  Checking port $port..."
    if command -v fuser >/dev/null 2>&1; then
        fuser -k -n tcp "$port" >/dev/null 2>&1
    elif command -v lsof >/dev/null 2>&1; then
        lsof -ti:"$port" | xargs -r kill -9
    fi
}

echo "Starting LLM Council..."
echo ""

# Cleanup existing processes
echo "Cleaning up ports 8001 and 5173..."
kill_port 8001
kill_port 5173
sleep 2

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Start backend
echo "Starting backend on http://localhost:8001..."
if [ -d ".venv" ]; then
    python -m backend.main &
else
    uv run python -m backend.main &
fi
BACKEND_PID=$!

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if python3 -c "import socket; s = socket.socket(); s.connect(('localhost', 8001))" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

echo ""
echo "✓ LLM Council is running!"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
