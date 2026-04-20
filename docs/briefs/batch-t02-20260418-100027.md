# Benchmark Brief — T-02: Score Formatting with Commas

## Requirements
- Add a Jinja2 filter registered in `app.py` that formats integer score values with comma separators. Apply it to rendered score fields on existing templates only. No new routes.

## Constraints
- No schema changes.
- Follow existing project conventions and styles.
- Prefer minimal scope matching the task only.

## Scope
- backend+frontend

## Visual QA Target
- Score values on the scoreboard, player page, history page, and tournament standings render as `1,240,500` instead of `1240500`.

## Acceptance Criteria
- The described user-visible or API behavior is implemented.
- The change stays within the stated task scope.
- Tests are added or updated when the task requires code verification.
