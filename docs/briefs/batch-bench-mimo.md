---
noteId: "7c701d40373611f19682db1af2e416db"
tags: []

---

# Batch: Player Streak Tracker

## Ticket #69: Player streak tracker — consecutive day scoring

### Requirements
- GET /api/streaks — JSON array: {player, current_streak, best_streak, last_played}
- A streak = consecutive calendar days with at least 1 score submitted
- GET /streaks — HTML table sorted by current_streak DESC
- Highlight rows where current_streak >= 3
- Dark theme matching existing pages

### Implementation Notes
- All code in app.py only, tests in test_api_scores.py only
- Query scores grouped by player and date: SELECT name, date(created_at) as day FROM scores GROUP BY name, day ORDER BY name, day
- Streak logic in Python: iterate days per player, count consecutive
- No new dependencies

### Acceptance Criteria
1. /api/streaks returns 200 with correct JSON shape
2. /streaks shows HTML table sorted by current streak
3. Rows with streak >= 3 are visually highlighted
4. Players with no scores don't appear
