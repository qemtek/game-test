---
noteId: "5f70400037bb11f19682db1af2e416db"
tags: []

---

# Briefing: Player Stats API
**Group:** pare/group-stats  
**Branch:** pare/group-stats → development  
**Worktree:** `../worktrees/pare-group-stats`

---

## Tasks

| ID | Title | Difficulty |
|----|-------|------------|
| PARE-37 | Paginated & Filtered Score List (`GET /api/scores` extensions) | Medium |
| PARE-38 | Fetch Score by ID (`GET /api/scores/<int:id>`) | Low |
| PARE-39 | Player List (`GET /api/players`) | Medium |
| PARE-40 | Player Profile (`GET /api/players/<name>`) | Hard |

All tasks in this batch ship in a **single PR** from `pare/group-stats`.

---

## Constraints (apply to all tasks)

- All route code goes in **`app.py` only** — no new modules or files
- All tests go in **`test_api_scores.py` only** — no new test files
- Conventions: `@app.route`, `jsonify`, `with database.get_db() as conn`, raw SQL, `dict(row)`
- Flask 3.x (`flask>=3.0.0`) — `sqlite3.Row` already has context manager support via `database.get_db()`

---

## Codebase Overview

```
game-test/
├── app.py              ← ALL route code lives here
├── database.py         ← DB helper: get_db(), init_db()
├── test_api_scores.py  ← ALL new tests go here
├── test_api_health.py  ← Health tests (do not touch)
├── pytest.ini          ← test config
└── requirements.txt    ← flask>=3.0.0
```

### `database.py` pattern
```python
import database

with database.get_db() as conn:
    rows = conn.execute('SELECT ...', (param,)).fetchall()
    # conn.commit() needed after INSERT/UPDATE/DELETE
return jsonify([dict(row) for row in rows])
```

### Existing routes (do not modify)
- `GET /` → renders index.html
- `GET /health` → `{"status": "ok", "version": "1.0.0"}`
- `GET /api/health` → `{"status": "ok"}`
- `GET /api/scores` → top-10 scores ordered by score DESC (**will be extended**)
- `POST /api/scores` → insert score, returns 201 with full row

### DB Schema
```sql
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    score INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

---

## PARE-37 — Paginated & Filtered Score List (Medium)

**Extend** the existing `GET /api/scores` handler. Add optional query params:

| Param | Type | Default | Max | Behaviour |
|-------|------|---------|-----|-----------|
| `name` | str | — | — | Filter by player name (case-sensitive exact match) |
| `limit` | int | 10 | 100 | Max results |
| `offset` | int | 0 | — | Skip N results |

Always ordered by `score DESC`. Invalid param types → HTTP 400.

### Implementation sketch
```python
@app.route('/api/scores', methods=['GET'])
def get_scores():
    name   = request.args.get('name')
    raw_limit  = request.args.get('limit',  '10')
    raw_offset = request.args.get('offset', '0')

    try:
        limit  = int(raw_limit)
        offset = int(raw_offset)
    except (ValueError, TypeError):
        return jsonify({"error": "limit and offset must be integers"}), 400

    if limit < 0 or offset < 0:
        return jsonify({"error": "limit and offset must be non-negative"}), 400
    limit = min(limit, 100)

    if name is not None:
        sql = 'SELECT id, name, score, created_at FROM scores WHERE name = ? ORDER BY score DESC LIMIT ? OFFSET ?'
        params = (name, limit, offset)
    else:
        sql = 'SELECT id, name, score, created_at FROM scores ORDER BY score DESC LIMIT ? OFFSET ?'
        params = (limit, offset)

    with database.get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify([dict(row) for row in rows])
```

### Test cases to cover
- No params → first 10 by score DESC (existing behaviour preserved)
- `?limit=5` → at most 5 rows
- `?limit=200` → capped at 100
- `?offset=5` → skips first 5
- `?name=Alice` → only Alice's scores
- `?name=Alice&limit=2` → combination
- `?limit=abc` → 400
- `?offset=abc` → 400
- `?limit=1.5` → 400 (non-integer string)

---

## PARE-38 — Fetch Score by ID (Low)

New route: `GET /api/scores/<int:id>`

Returns single score entry or 404.

### Implementation sketch
```python
@app.route('/api/scores/<int:score_id>', methods=['GET'])
def get_score_by_id(score_id):
    with database.get_db() as conn:
        row = conn.execute(
            'SELECT id, name, score, created_at FROM scores WHERE id = ?',
            (score_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "score not found"}), 404
    return jsonify(dict(row))
```

### Test cases to cover
- Valid id → 200 with correct fields (id, name, score, created_at)
- Non-existent id → 404
- Returned fields match inserted values
- Multiple inserts — retrieve each by id
- Flask's `<int:id>` converter — non-integer path segment → Flask 404 automatically (no explicit test needed)

---

## PARE-39 — Player List (Medium)

New route: `GET /api/players`

Returns all unique players ranked by best score:
```json
[{"name": "Alice", "best_score": 1500, "total_games": 4, "avg_score": 1100}, ...]
```
Ordered by `best_score DESC`.

### Implementation sketch
```python
@app.route('/api/players', methods=['GET'])
def get_players():
    with database.get_db() as conn:
        rows = conn.execute('''
            SELECT
                name,
                MAX(score)   AS best_score,
                COUNT(*)     AS total_games,
                AVG(score)   AS avg_score
            FROM scores
            GROUP BY name
            ORDER BY best_score DESC
        ''').fetchall()
    return jsonify([dict(row) for row in rows])
```

**Note on `avg_score`:** SQLite's `AVG()` returns a float. The spec shows integer examples but does not mandate rounding. Return the raw float; if the operator wants rounding, that's a follow-up. Tests should handle both int and float avg values.

### Test cases to cover
- Empty DB → `[]`
- Single player multiple games → correct best/total/avg
- Multiple players → ordered by best_score DESC
- avg_score is numeric (int or float)
- Response fields: name, best_score, total_games, avg_score

---

## PARE-40 — Player Profile (Hard)

New route: `GET /api/players/<name>`

Full profile including global rank:
```json
{
  "name": "Alice",
  "rank": 1,
  "best_score": 1500,
  "avg_score": 1100.0,
  "total_games": 4,
  "recent_scores": [
    {"id": 5, "score": 1500, "created_at": "..."},
    ...
  ]
}
```

Rules:
- `rank` = 1-indexed position in global leaderboard by best score
- `recent_scores` = last 10 scores by `created_at DESC` (id, score, created_at — **no name field**)
- 404 if player has no scores

### Architecture

This needs two queries — SQLite doesn't support window functions reliably in older builds, so compute rank in Python:

```python
@app.route('/api/players/<name>', methods=['GET'])
def get_player_profile(name):
    with database.get_db() as conn:
        # Step 1: check player exists + get their stats
        player_row = conn.execute('''
            SELECT
                name,
                MAX(score)   AS best_score,
                COUNT(*)     AS total_games,
                AVG(score)   AS avg_score
            FROM scores
            WHERE name = ?
            GROUP BY name
        ''', (name,)).fetchone()

        if player_row is None:
            return jsonify({"error": "player not found"}), 404

        # Step 2: compute rank (players ranked higher have a greater best_score)
        rank_row = conn.execute('''
            SELECT COUNT(*) + 1 AS rank
            FROM (
                SELECT name, MAX(score) AS best_score
                FROM scores
                GROUP BY name
            )
            WHERE best_score > ?
        ''', (player_row['best_score'],)).fetchone()

        # Step 3: recent scores (last 10 by created_at DESC)
        recent = conn.execute('''
            SELECT id, score, created_at
            FROM scores
            WHERE name = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (name,)).fetchall()

    return jsonify({
        "name": player_row['name'],
        "rank": rank_row['rank'],
        "best_score": player_row['best_score'],
        "avg_score": player_row['avg_score'],
        "total_games": player_row['total_games'],
        "recent_scores": [dict(r) for r in recent],
    })
```

### Rank logic explained

The subquery groups all players by their best score. We count how many players have a strictly higher best score, then add 1. This gives 1-indexed rank correctly. Ties (two players with the same best score) both get the same rank.

### Test cases to cover
- Unknown player → 404
- Single player → rank 1, correct stats, recent_scores populated
- rank=1 for top player, rank=2 for second-best
- recent_scores capped at 10
- recent_scores ordered by created_at DESC
- recent_scores fields: id, score, created_at (no name)
- avg_score is numeric
- Players with same best score get the same rank
- total_games counts all entries for that player

---

## Test File Conventions (from existing test_api_scores.py)

```python
@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_scores.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    monkeypatch.setenv("DB_PATH", str(db_file))
    database.init_db()
    yield

@pytest.fixture()
def client(isolated_db):
    import app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
```

Each test class maps to one ticket. Helper functions at module level (like the existing `post_score`).

---

## Running Tests

```bash
cd ~/Documents/GitHub/worktrees/pare-group-stats
pip install -r requirements.txt
pytest test_api_scores.py -v
```

---

## PR Checklist

- [ ] All 4 routes implemented in `app.py`
- [ ] All tests in `test_api_scores.py`, no new test files
- [ ] Existing tests still pass (`pytest test_api_scores.py test_api_health.py -v`)
- [ ] Rebased onto `origin/development` before push
- [ ] PR target: `development`
- [ ] PR title: `[PARE-37][PARE-38][PARE-39][PARE-40] Player Stats API`
