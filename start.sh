#!/bin/bash

# Eternal Copilot - Start script

echo "Starting Eternal Copilot..."
echo ""

# Check and install backend dependencies
echo "Checking backend dependencies..."
if ! uv run python -c "import fastapi" 2>/dev/null; then
    echo "Backend dependencies not found. Installing with 'uv sync'..."
    uv sync
else
    echo "✓ Backend dependencies OK"
fi
echo ""

# Check and install frontend dependencies
echo "Checking frontend dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    echo "Frontend dependencies not found. Installing with 'npm install'..."
    cd frontend || exit
    npm install
    cd ..
    npm install
    cd ..
else
    echo "✓ Frontend dependencies OK"
fi
echo ""

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
cd ..

echo ""
echo "✓ Eternal Copilot is running!"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
