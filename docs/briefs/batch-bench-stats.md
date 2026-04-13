---
noteId: "32a138a0371a11f19682db1af2e416db"
tags: []

---

# Batch: Game Statistics Dashboard

## Ticket #68: Game statistics dashboard — aggregate stats page

### Requirements
- GET /api/stats — JSON: {total_games, total_players, highest_score: {name, score}, most_active_player: {name, games_played}, average_score, scores_today}
- GET /stats — HTML page with 6 stat cards in a grid layout
- Each card: label + large value
- Dark theme matching existing pages

### Implementation Notes
- All code in app.py only, tests in test_api_scores.py only
- Queries from scores table: COUNT(*), COUNT(DISTINCT name), MAX(score), etc.
- scores_today: WHERE date(created_at) = date('now')

### Acceptance Criteria
1. /api/stats returns 200 with all 6 stat fields
2. /stats shows 6 cards in a grid with correct values
3. highest_score and most_active_player show player names
4. Values are live from DB, not hardcoded
