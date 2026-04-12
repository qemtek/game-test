#!/bin/bash
# Stop the game-test Flask app (port 5000)

echo "Stopping app on port 5000..."
lsof -ti:5000 | xargs kill -9 2>/dev/null && echo "Done." || echo "Nothing running on port 5000."
