---
noteId: "40b8377037bc11f19682db1af2e416db"
tags: []

---

app.py (648L): all routes + logic. 24 existing routes. Pattern: @app.route, jsonify, with database.get_db() as conn, raw SQL, dict(row)
database.py (44L): get_db(), init_db(). SQLite
test_api_scores.py (2043L): main test file. Run: python -m pytest test_api_scores.py -x -q
templates/: about badges history index player scoreboard tournaments (.html)
DB (scores.db): scores(id INTEGER,name TEXT,score INTEGER,created_at TIMESTAMP) | tournaments(id INTEGER,name TEXT,status TEXT,starts_at TEXT,ends_at TEXT,created_at TEXT) | tournament_entries(id INTEGER,tournament_id INTEGER,name TEXT,best_score INTEGER,submitted_at TEXT,joined_at TEXT,REFERENCEStournaments(id),UNIQUE(tournament_id,name))
Add new routes at end of app.py. All code in app.py only. Tests in main test file only. Style: dark navy bg, green monospace headings. Copy pattern from existing templates.