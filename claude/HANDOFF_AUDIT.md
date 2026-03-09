# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-255

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (534 tests, 0 failures)
- node tools/lint_dashboard_handlers.js: PASS (0 gaps; 45 handler calls, 58 window.* exposed)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/static/dashboard_panels.js` — _subtasksTaskFilter state, pollSubtasks() includes ?task=X, _updateSubtasksExportLinks builds qs with task filter, window._applySubtasksTaskFilter handler
- `solo_builder/api/dashboard.html` — #subtasks-task-filter input (width:60px) added beside #subtasks-filter; oninput="_applySubtasksTaskFilter()"

## Implementation Detail
The server (GET /subtasks, /subtasks/export) already supports ?task= filter (TASK-251).
This task wires the UI: a small "Task…" text input in the Subtasks tab filter row.
On input, _applySubtasksTaskFilter() sets _subtasksTaskFilter, resets page to 1, and calls pollSubtasks() for server-side re-fetch.
Export links automatically include &task=X via _updateSubtasksExportLinks() parity.
