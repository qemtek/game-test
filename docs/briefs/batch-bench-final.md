---
noteId: "batch-bench-final"
tags: []

---

# Batch: Leaderboard Badges (bench-final)

## Ticket: Leaderboard badge system

### Requirements
- GET /api/badges — JSON array of {player, badge, best_score} based on thresholds: gold>=8000, silver 5000-7999, bronze 2000-4999
- GET /badges — HTML page with badge grid, colored icons, count summary
- Dark theme matching existing pages
- Results sorted by best_score descending (highest scores first)

### Implementation Notes
- All code in app.py only, tests in test_api_scores.py only
- Query: SELECT name, MAX(score) as best_score FROM scores GROUP BY name
- Badge assignment in Python based on thresholds
- Sort results by best_score descending before returning
- No new dependencies

### Acceptance Criteria
1. /api/badges returns correct JSON with badge assignments
2. /badges shows HTML grid with gold/silver/bronze colored elements
3. Badge count summary at top (e.g. '3 Gold, 5 Silver, 7 Bronze')
4. Players below 2000 get no badge and don't appear
5. Results are ordered by best_score descending
