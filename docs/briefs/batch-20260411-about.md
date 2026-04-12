---
noteId: "477a4760362211f19682db1af2e416db"
tags: []

---

# Batch: About Page

## Ticket #54: About page with app version and stats

### Requirements
- Add `GET /about` HTML page showing: app name ("Game Score Tracker"), version "1.0.0", total unique players, total scores submitted, total tournaments created
- Add `GET /api/about` returning JSON: `{name, version, total_players, total_scores, total_tournaments}`
- Dark theme matching existing pages

### Implementation Notes
- All code in `app.py` only
- Tests in `test_api_scores.py` only
- Query counts from scores and tournaments tables
- Total players = `SELECT COUNT(DISTINCT name) FROM scores`

### Acceptance Criteria
1. `/api/about` returns 200 with correct JSON shape and counts
2. `/about` renders HTML with app name, version, and all 3 counts
3. Counts are accurate (not hardcoded)
