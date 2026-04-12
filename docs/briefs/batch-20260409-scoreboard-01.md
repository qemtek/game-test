---
noteId: "scoreboard-brief-20260409"
tags: []
---

# Briefing — batch-20260409-scoreboard-01
## Live Scoreboard Feature

---

## Overview

Add a live scoreboard page (`/scoreboard`) and a supporting JSON API (`/api/scoreboard`) to the game-test Flask app. The page shows the global top-10 leaderboard, auto-refreshing every 5 seconds, a player name filter, and the standings of any currently active tournament.

Also add a data seed script for QA purposes, and tests for the new endpoints.

---

## Architecture

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/scoreboard` | Returns HTML scoreboard page |
| GET | `/api/scoreboard` | Returns JSON scoreboard data |

### Key Files

| File | Role |
|------|------|
| `app.py` | Add new routes here |
| `templates/scoreboard.html` | New HTML template |
| `scripts/seed_scoreboard.py` | New seed script |
| `test_api_scores.py` | Add tests here |

---

## Endpoints

### GET /api/scoreboard
Returns:
```json
{
  "scores": [
    {"id": 1, "name": "Alice", "score": 9999, "created_at": "..."},
    ...
  ],
  "active_tournament": {
    "id": 1,
    "name": "Spring Cup",
    "status": "active",
    "standings": [
      {"rank": 1, "name": "Alice", "best_score": 1500, "submitted_at": "..."},
      ...
    ]
  }
}
```
- `scores`: top-10 global scores ordered by score DESC (same as GET /api/scores with default params)
- `active_tournament`: the first tournament with status `active` (after dynamic open→active check), or `null` if none. Include full standings.

### GET /scoreboard
- Returns 200 HTML
- Uses `templates/scoreboard.html`
- Calls `get_scoreboard_data()` helper (shared with `/api/scoreboard`) to pass data to the template
- The page auto-refreshes scores every 5 seconds via `fetch('/api/scoreboard')` and updates the DOM
- Includes a text input to filter the scores table by player name (client-side JS)
- Shows the active tournament standings section only if `active_tournament` is not null

---

## Template: scoreboard.html

- Extend or match the style of `templates/index.html`
- Score table columns: Rank, Name, Score, Date
- Tournament section: Tournament name, standings table (Rank, Player, Best Score)
- Filter input above the scores table: `<input id="filter" placeholder="Filter by name..." />`
- Auto-refresh script: every 5000ms, fetch `/api/scoreboard`, update scores + tournament DOM in-place

---

## Seed Script: scripts/seed_scoreboard.py

- Seeds 15 players with varied scores (use realistic game names like "PixelKnight", "NeonRacer", etc.)
- Creates one active tournament named "QA Sprint" with `starts_at` set to 1 hour ago and `ends_at` set to 1 hour from now
- Joins 5 of the players to the tournament and submits scores for them
- Idempotent: safe to run multiple times (use INSERT OR IGNORE where possible)
- Usage: `python scripts/seed_scoreboard.py`
- Reads DB_PATH from environment, defaults to `game.db`

---

## Tests (add to test_api_scores.py)

### TestGetApiScoreboard
- `test_returns_200` — GET /api/scoreboard returns 200
- `test_scores_field_present` — response has `scores` key
- `test_active_tournament_null_when_none` — `active_tournament` is null when no active tournament
- `test_scores_top_10` — scores array has at most 10 entries ordered score DESC
- `test_active_tournament_populated` — when an active tournament exists, `active_tournament` has id, name, status, standings

### TestGetScoreboard (HTML)
- `test_returns_200` — GET /scoreboard returns 200
- `test_returns_html` — content-type is text/html
- `test_contains_scores` — response body contains score data

---

## Conventions

- Same as rest of codebase: `@app.route`, `jsonify`, `with database.get_db() as conn:`
- Use `_tournament_row_with_status()` helper for dynamic open→active check
- `_get_standings()` helper already exists for tournament standings

---

## Tasks

| ID | Title | Difficulty |
|----|-------|------------|
| 49 | Live Scoreboard page — leaderboard UI with real-time updates | Hard |
| 50 | Data seed script for scoreboard visual QA | Medium |
| 51 | Tests: /scoreboard and /api/scoreboard endpoints | Medium |

All tasks in group `group-20260409-scoreboard-1`, batch `batch-20260409-scoreboard-01`.
