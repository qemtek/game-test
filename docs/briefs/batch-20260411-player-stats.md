---
noteId: "7c343130357f11f19682db1af2e416db"
tags: []

---

# Batch: Player Stats Page

## Ticket #52: Player stats page — show individual player history

### Requirements
- Add `GET /player/<name>` HTML page showing that player's score history (all scores, not just best)
- Include a simple bar chart using inline SVG
- Add `GET /api/player/<name>` returning JSON: `{name, scores: [{score, created_at}], total_games, best_score, average_score}`
- Style to match existing pages (dark theme, green accents, monospace font)

### Implementation Notes
- All code in `app.py` only — no new modules
- Tests in `test_api_scores.py` only — no new test files
- Same conventions: `@app.route`, `jsonify`, `with database.get_db() as conn`, raw SQL, `dict(row)`
- The scores table already has `name`, `score`, `created_at` columns
- SVG bar chart: one bar per score entry, height proportional to score, labeled with score value

### Acceptance Criteria
1. `/api/player/PixelKnight` returns 200 with correct JSON shape
2. `/api/player/NonExistent` returns 404
3. `/player/PixelKnight` renders HTML with player name heading, score list, SVG chart, and stats summary
4. SVG chart has one bar per score entry

### Visual QA Targets
- Player name heading
- Score history table or list
- SVG bar chart with bars
- Stats summary showing total games, best score, average score
