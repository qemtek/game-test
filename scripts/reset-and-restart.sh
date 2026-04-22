#!/bin/bash
# Reset the database and restart the Flask app for QA.
# Called by the QA pipeline's reset_command.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

FLASK_PORT="${FLASK_PORT:-5055}"

echo "Stopping Flask app on port $FLASK_PORT..."
lsof -ti:"$FLASK_PORT" | xargs kill 2>/dev/null || true
sleep 0.5
lsof -ti:"$FLASK_PORT" | xargs kill -9 2>/dev/null || true

echo "Removing old database..."
rm -f scores.db scores.db-wal scores.db-shm

echo "Initializing fresh database..."
source .venv/bin/activate 2>/dev/null || true
python3 -c "import database; database.init_db(); print('DB initialized')"

echo "Starting Flask app on port $FLASK_PORT..."
FLASK_PORT="$FLASK_PORT" nohup python3 app.py > /tmp/game-test-app.log 2>&1 &
echo "App PID: $!"

echo "Reset complete."
