# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-279

## Verdict: PASS

## Verification Results
- lint_dashboard_handlers.js: PASS (47 handler calls, 0 gaps)
- unittest-discover (api): PASS (568 tests, 0 failures; +0 new, UI-only)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/static/dashboard_panels.js` — `_refreshExportHistoryByStatus()` extended: after updating history by-status chips, fetches `GET /stalled` to get `threshold`, then sets `#export-stalled-csv` and `#export-stalled-json` hrefs to `/subtasks/export?status=running&min_age=<threshold>` (+ `&format=json`); updates `#export-stalled-threshold` label text to `≥ N steps stalled`
- `solo_builder/api/dashboard.html` — "Stalled Subtasks" row added to Export tab after Subtasks row; anchors have IDs `export-stalled-csv/json` with default `min_age=5` fallback hrefs; threshold label `#export-stalled-threshold` shown beside heading

## Implementation Detail
Threshold is fetched live from `GET /stalled` on every Export tab open (same call as the Stalled tab); links default to `min_age=5` on first render and update once the fetch resolves. No new tests needed — pure dashboard UI addition.
