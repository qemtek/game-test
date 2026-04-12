---
noteId: "1c4e7670358611f19682db1af2e416db"
tags: []

---

# Batch: Game History Page

## Ticket #53: Game history page — recent games log

### Requirements
- Add `GET /history` HTML page showing the 20 most recent score submissions across all players
- Each row: rank, player name, score, and relative time (e.g. "2 hours ago")
- Add `GET /api/history?limit=N` returning JSON array of recent scores (default limit=20, max=100)
- Navigation link from the main page to /history
- Style to match existing dark theme (dark navy background, green accents, monospace font)

### Implementation Notes
- All code in `app.py` only — no new modules
- Tests in `test_api_scores.py` only
- Same conventions: `@app.route`, `jsonify`, `with database.get_db() as conn`, raw SQL, `dict(row)`
- Query: `SELECT * FROM scores ORDER BY created_at DESC LIMIT ?`
- Time-ago: compute in Python using `datetime` (no external libraries)
- Add a link to /history in the existing index page

### Acceptance Criteria
1. `/api/history` returns 200 with JSON array of recent scores, default limit 20
2. `/api/history?limit=5` returns exactly 5 scores
3. `/history` renders HTML with table of recent scores
4. Each row shows player name, score, and relative time
5. Navigation link from index page to /history exists
