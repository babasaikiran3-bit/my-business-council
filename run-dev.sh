#!/bin/bash

# Development runner for AI Council
# Runs both backend and frontend in development mode

echo "🚀 Starting AI Council Development Environment"
echo ""

# Check if required directories exist
if [ ! -d "server" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: server or frontend directory not found"
    exit 1
fi

# Check if node_modules exist
if [ ! -d "server/node_modules" ]; then
    echo "📦 Installing server dependencies..."
    cd server && npm install && cd ..
fi

if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Check for .env file
if [ ! -f "server/.env" ]; then
    echo "⚠️  Warning: server/.env not found. Please create one based on server/.env.example"
    exit 1
fi

echo ""
echo "✨ Starting backend on port 8001..."
echo "✨ Starting frontend on port 5173..."
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Run both servers with trap to kill both on exit
trap 'kill 0' EXIT

cd server && npm run dev &
cd frontend && npm run dev &

wait
