---
noteId: "69959fc0369011f19682db1af2e416db"
tags: []

---

# Batch: Player Achievements

## Ticket #67: Player achievements system — milestone tracking

### Requirements
- GET /api/achievements — JSON array of {player, achievements: [str], total_scores}
- Milestones: "First Blood" (1+ scores), "Veteran" (10+ scores), "Champion" (score >= 9000)
- GET /achievements — HTML table of players with checkmark icons for earned achievements
- Dark theme matching existing pages

### Implementation Notes
- All code in app.py only, tests in test_api_scores.py only
- Query: SELECT name, COUNT(*) as total, MAX(score) as best FROM scores GROUP BY name
- No new dependencies

### Acceptance Criteria
1. /api/achievements returns correct JSON with milestone assignments
2. /achievements shows HTML table with player rows and achievement columns
3. Checkmarks for earned achievements, empty for unearned
4. Players with no scores don't appear
