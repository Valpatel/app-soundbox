#!/bin/bash
# Start Sound Box server
# Usage: ./start.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check venv exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# Check .env exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env from .env.example"
    fi
fi

# Create required directories
mkdir -p generated spectrograms models/voices

echo "Starting Sound Box server..."
echo "  Config: .env"
echo "  URL: http://localhost:${PORT:-5309}"
echo ""

exec "$SCRIPT_DIR/venv/bin/python" app.py "$@"
