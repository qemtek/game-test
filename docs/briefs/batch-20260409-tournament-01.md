---
noteId: "1c52759033fb11f19682db1af2e416db"
tags: []

---

# Briefing — batch-20260409-tournament-01
## Tournament System

---

## Overview

Add a full tournament system to the game-test Flask app. Tournaments have a lifecycle (open → active → completed), players join and submit scores during the active window, and standings are computed from each player's best score.

---

## Architecture

### New DB Tables (add to `database.init_db()`)

```sql
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',  -- open | active | completed
    starts_at TEXT NOT NULL,              -- ISO8601 UTC string
    ends_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tournament_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
    name TEXT NOT NULL,       -- player name
    best_score INTEGER,       -- NULL until first score submitted
    submitted_at TEXT,        -- when best_score was last updated
    joined_at TEXT NOT NULL,
    UNIQUE(tournament_id, name)
);
```

### Key Files

| File | Role |
|------|------|
| `app.py` | All routes go here — no new modules |
| `database.py` | Add new tables to `init_db()` only |
| `test_api_scores.py` | All tests go here — no new test files |

---

## Endpoints

### POST /api/tournaments
Create a tournament.
- **Body:** `{"name": "Spring Cup", "starts_at": "2026-04-10T00:00:00Z", "ends_at": "2026-04-11T00:00:00Z"}`
- **Validation:** name non-empty string; `ends_at > starts_at`; `starts_at` must be in the future
- **Returns:** 201 with tournament object: `{"id":1,"name":"Spring Cup","status":"open","starts_at":"...","ends_at":"...","created_at":"..."}`
- **Errors:** 400 for missing/invalid fields

### GET /api/tournaments
List all tournaments.
- **Optional:** `?status=open|active|completed` filter
- **Ordered:** `starts_at DESC`
- **Dynamic status:** on each request, if a tournament's `starts_at` has passed and its stored status is `open`, update it to `active` in the DB and return `active`
- **Returns:** array of tournament objects (no standings)

### POST /api/tournaments/\<int:id\>/join
Join a tournament.
- **Body:** `{"name": "Alice"}`
- **Allowed:** only when tournament status is `open` or `active` (after dynamic status computation)
- **Idempotent:** if player already joined, return 200 with existing entry; new join returns 201
- **404** if tournament not found
- **422** if tournament is `completed`
- **Returns:** entry object: `{"id":1,"tournament_id":1,"name":"Alice","best_score":null,"submitted_at":null,"joined_at":"..."}`

### POST /api/tournaments/\<int:id\>/score
Submit a score.
- **Body:** `{"name": "Alice", "score": 1500}`
- **Player must have joined:** 409 if not
- **Tournament must be active:** 422 if `open` or `completed`
- **Score validation:** positive integer, not bool (same pattern as `POST /api/scores`)
- **Best-score tracking:** only update `best_score` and `submitted_at` if new score > current `best_score`
- **Returns:** updated entry object (200 always, even if score not improved)

### GET /api/tournaments/\<int:id\>
Tournament detail with standings.
- **404** if not found
- **Dynamic status:** same as GET /api/tournaments — update `open`→`active` if needed
- **Returns:**
```json
{
  "id": 1,
  "name": "Spring Cup",
  "status": "active",
  "starts_at": "...",
  "ends_at": "...",
  "created_at": "...",
  "standings": [
    {"rank": 1, "name": "Alice", "best_score": 1500, "submitted_at": "..."},
    {"rank": 2, "name": "Bob",   "best_score": 1200, "submitted_at": "..."},
    {"rank": 3, "name": "Carol", "best_score": null,  "submitted_at": null}
  ]
}
```
- **Standings order:** by `best_score DESC`, with `NULL` scores last. Players who joined but haven't scored appear at the bottom.
- **Rank:** 1-indexed, dense (no gaps for ties — shared rank is fine).

### POST /api/tournaments/\<int:id\>/complete
Mark a tournament as completed.
- **No body required**
- **404** if not found
- **422** if `now < ends_at` (can't complete early)
- **422** if already `completed`
- Sets `status = 'completed'` in the DB
- **Returns:** same format as GET /api/tournaments/\<id\> with final standings

---

## Status Lifecycle

```
open  ──(now >= starts_at, on read)──►  active  ──(POST /complete)──►  completed
```

- The `open → active` transition happens **lazily on read** — whenever any endpoint fetches a tournament, it checks if `starts_at <= now` and if so, updates the DB to `active` before returning.
- The `active → completed` transition only happens via explicit `POST /complete`. Never auto-complete.

---

## Conventions

- `@app.route(...)` plain functions — no blueprints
- `jsonify(...)` for all responses
- `with database.get_db() as conn:` for DB access (auto-commit/rollback)
- Raw SQL only — no ORM
- `dict(row)` for row serialisation
- `datetime.now(timezone.utc).isoformat()` for timestamps
- Validate name with `isinstance(name, str) and name.strip()`
- Validate score with `isinstance(score, int) and not isinstance(score, bool) and score > 0`

---

## Gotchas

1. **`context manager` on `get_db()`**: The existing `get_db()` returns a plain `sqlite3.Connection`. Use `with database.get_db() as conn:` — SQLite connections support the context manager protocol (commits on success, rolls back on exception).

2. **Timestamp comparisons**: Store and compare timestamps as ISO8601 strings. SQLite's string comparison works correctly for ISO8601 (`"2026-04-10T00:00:00Z" < "2026-04-11T00:00:00Z"`).

3. **NULL scores in standings**: Use `ORDER BY best_score DESC NULLS LAST` (SQLite supports this syntax).

4. **Idempotent join**: Use `INSERT OR IGNORE INTO tournament_entries ...` then fetch the row. This avoids race conditions.

5. **Dynamic status update**: Do this in a helper function to avoid duplicating the logic across GET list, GET detail, join, and score endpoints.

---

## Tasks

| ID | Title | Difficulty |
|----|-------|------------|
| 41 | Add tournament DB tables to database.init_db() | Low |
| 42 | POST /api/tournaments — create tournament | Low |
| 43 | GET /api/tournaments — list with dynamic status | Medium |
| 44 | POST /api/tournaments/<id>/join — join tournament | Medium |
| 45 | POST /api/tournaments/<id>/score — submit score | Hard |
| 46 | GET /api/tournaments/<id> — detail + standings | Medium |
| 47 | POST /api/tournaments/<id>/complete — mark completed | Low |
| 48 | Tests: full tournament system in test_api_scores.py | Hard |

All tasks are in group `group-20260409-tournament-1`, batch `batch-20260409-tournament-01`.
