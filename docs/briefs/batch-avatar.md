---
noteId: "6998d4c037e811f19682db1af2e416db"
tags: []

---

# Batch: Player Profile Avatar

## Ticket #77: Player profile avatar circle with initials

### Requirements

Add a circular avatar above the player name heading on the `/players/<name>` page.

**Visual:**
- 72×72px circle, background `#1a1a2e`, border `2px solid #4ade80`, `border-radius: 50%`
- Initials text: `#4ade80`, `1.6rem`, bold, `Courier New` monospace, centered in circle
- Displayed using `display: flex; align-items: center; justify-content: center`

**Initials logic (Jinja2):**
- Multi-word names (contain spaces): take first char of each word, join, uppercase, max 2 chars
  - `"Pixel Knight"` → `"PK"`
- Single-word names: take first 2 chars, uppercase
  - `"PixelKnight"` → `"PI"` (or `"PK"` if split on caps — either acceptable)
- Simplest correct approach: `player_name.split()` gives words; take `word[0]` for each, join first 2

**Placement:** immediately before `<h1 class="player-heading">{{ player_name }}</h1>` (line ~122)

### Implementation Notes

- Modify `templates/player.html` only
- Add CSS in the existing `<style>` block
- Add avatar HTML before the `<h1 class="player-heading">` line
- No backend changes — `player_name` is already in template context

### Acceptance Criteria

1. `/players/PixelKnight` shows a green-bordered circle above the player name
2. Circle contains 2 uppercase initials in green monospace font
3. Circle is centered on the page (matches the page's existing layout alignment)
4. Avatar appears on all player pages, not just PixelKnight
5. Page otherwise unchanged — stats, chart, history table all intact below
