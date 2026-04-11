#!/bin/bash
# Reset the database and restart the Flask app for QA.
# Called by the QA pipeline's reset_command.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "Stopping Flask app..."
lsof -ti:5000 | xargs kill 2>/dev/null || true
sleep 1
# Force kill if still alive
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

echo "Removing old database..."
rm -f scores.db scores.db-wal scores.db-shm

echo "Initializing fresh database..."
source .venv/bin/activate 2>/dev/null || true
python3 -c "import database; database.init_db(); print('DB initialized')"

echo "Starting Flask app in background..."
nohup python3 app.py > /tmp/game-test-app.log 2>&1 &
echo "App PID: $!"

echo "Reset complete."
