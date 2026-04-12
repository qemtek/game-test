---
noteId: "ecb1af60333f11f19682db1af2e416db"
tags: []

---

# Project Brief — batch-20260408-test
## Smoke test: /api/health endpoint

This is a smoke test of the pipeline determinism fixes. One trivial task.

## Architecture Context

The project is a Flask app with SQLite. See `app.py` for existing routes.
The leaderboard endpoints (`/api/scores` GET/POST) already exist as a reference.

## Task

Add a `GET /api/health` route that returns `{"status": "ok"}` as JSON with HTTP 200.

- No auth, no validation, no DB queries
- Return `jsonify({"status": "ok"})`
- Add a minimal test that asserts:
  - status_code == 200
  - response.get_json() == {"status": "ok"}

## Conventions to Follow

- Use `@app.route` decorator (matches existing routes in app.py)
- Use `jsonify` for the response (existing convention)
- Pytest is the test framework — see `test_api_scores.py` for the pattern
- Stay within app.py and the existing test files; do not create new modules

## Out of Scope

- Do not modify existing routes
- Do not add a database table
- Do not change requirements.txt
