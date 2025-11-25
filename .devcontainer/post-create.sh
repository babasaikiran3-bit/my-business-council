#!/bin/bash
# Runs once when the Codespace is created

set -e

echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "Installing dependencies..."
make install

echo "Creating .env from template..."
cp .env.example .env

echo "Setup complete!"
