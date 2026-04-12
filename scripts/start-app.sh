#!/bin/bash
# Start the game-test Flask app on port 5000

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Killing any process on port 5000..."
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

cd "$REPO_ROOT"

if [ ! -d ".venv" ]; then
  echo ".venv not found — creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo "Starting Flask app on http://localhost:5000..."
python3 app.py
