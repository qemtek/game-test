---
noteId: "c9f9fcd0363b11f19682db1af2e416db"
tags: []

---

# Batch: Leaderboard Badges

## Ticket: Leaderboard badge system

### Requirements
- GET /api/badges — JSON array of {player, badge, best_score} based on thresholds: gold>=8000, silver 5000-7999, bronze 2000-4999
- GET /badges — HTML page with badge grid, colored icons, count summary
- Dark theme matching existing pages

### Implementation Notes
- All code in app.py only, tests in test_api_scores.py only
- Query: SELECT name, MAX(score) as best_score FROM scores GROUP BY name
- Badge assignment in Python based on thresholds
- No new dependencies

### Acceptance Criteria
1. /api/badges returns correct JSON with badge assignments
2. /badges shows HTML grid with gold/silver/bronze colored elements
3. Badge count summary at top (e.g. '3 Gold, 5 Silver, 7 Bronze')
4. Players below 2000 get no badge and don't appear
