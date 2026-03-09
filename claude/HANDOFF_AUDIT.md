# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-252

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (522 tests, 0 failures)
- node tools/lint_dashboard_handlers.js: PASS (0 gaps)
- git-status: PASS (clean working tree)

## Scope Check
One file modified:
- `solo_builder/api/static/dashboard_panels.js` — _subtasksNameFilter state, pollSubtasks() includes ?name=X, _updateSubtasksExportLinks builds qs from both filters, renderSubtasks() routes non-status text to server ?name= re-fetch, _renderSubtasks() removes client-side text filter

## Implementation Detail
Previously, typing non-status text in #subtasks-filter did client-side-only filtering (missed subtasks on other pages).
Now: non-status text sets _subtasksNameFilter and triggers pollSubtasks() with ?name=X (server-side, paginates correctly).
Status values still route to ?status=X (unchanged).
Empty input clears both filters and re-fetches.
Export links now include &name=X when _subtasksNameFilter is set (parity with status filter).
_renderSubtasks() simplified: no client-side filter loop; server already filtered _subtasksAll.
