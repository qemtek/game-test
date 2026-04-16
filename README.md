---
noteId: "903078b0396211f184a6658df4177230"
tags: []

---

# Snake

A browser-based Snake game with a leaderboard backend.

## Stack

- **Backend:** Python / Flask
- **Database:** SQLite
- **Frontend:** Vanilla JS, HTML5 Canvas

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open http://localhost:5000

## Controls

- Arrow keys or WASD to move
- Space to start / restart
- Enter to submit score after game over

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/scores` | Top 10 leaderboard scores |
| `POST` | `/api/scores` | Submit a score `{"name": str, "score": int}` |
