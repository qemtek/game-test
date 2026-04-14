---
noteId: "e98c95b037e111f19682db1af2e416db"
tags: []

---

# Batch: Top-3 Podium Display

## Ticket #76: Top-3 podium display on /scoreboard

### Requirements

Add a visual podium section at the top of the `/scoreboard` page, above the existing scores table.

**Layout:**
- 3-column podium: 2nd place (left), 1st place (centre — tallest), 3rd place (right)
- Classic stepped podium look: different column heights (1st: 120px, 2nd: 90px, 3rd: 70px)

**Each column shows:**
- Rank number (large, ~2rem)
- Player name (~0.85rem)
- Score (bold, ~1.1rem)

**Colour coding:**
- 1st place: gold (#fbbf24)
- 2nd place: silver (#9ca3af)
- 3rd place: bronze (#b45309)

**Edge cases:**
- If fewer than 3 scores exist, render only the available positions gracefully

**Style:**
- Dark theme: background #0f172a, card background #1a1a2e
- Font: 'Courier New', monospace (matches app)
- Section heading "TOP PLAYERS" in green (#4ade80) with letter-spacing, matching other section headings

### Implementation Notes

- Modify `templates/scoreboard.html` only — no backend changes needed
- `scores` list is already available in template context (top 10 by score DESC)
- Add podium HTML/CSS above the existing `.scoreboard-section` div
- No Python tests needed (`requires_code_testing: false`)

### Acceptance Criteria

1. `/scoreboard` shows a "TOP PLAYERS" heading above the scores table
2. Three podium columns visible: 2nd left (silver), 1st centre tallest (gold), 3rd right (bronze)
3. Each column shows rank number, player name, and score
4. Podium matches the dark theme of the rest of the app
5. Page still functions correctly with the existing scores table below
