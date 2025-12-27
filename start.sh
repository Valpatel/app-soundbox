#!/bin/bash
# Start Sound Box server
# Usage: ./start.sh

cd "$(dirname "$0")"
./venv/bin/python app.py
