# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-284

## Verdict: PASS

## Verification Results
- lint_dashboard_handlers.js: PASS (47 handler calls, 0 gaps)
- unittest-discover (api): PASS (573 tests, 0 failures; +0 new, UI-only)
- git-status: PASS (clean working tree)

## Scope Check
One file modified:
- `solo_builder/api/static/dashboard_panels.js` — `_updateHistoryExportLinks()` fixed: when the history filter text matches a known status (Pending/Running/Review/Verified, case-insensitive), routes to `?status=` server param instead of `?subtask=`; hint text also updated to show `status:"X"` vs `"X"` accordingly; `_KNOWN_STATUSES` Set defined as module-level constant

## Implementation Detail
Bug: History quick-filter buttons set `#history-filter` to "Running"/"Verified"/etc. but export link used `?subtask=Running` (subtask name filter) instead of `?status=Running`. Fixed by checking filter value against known status set before building query string.
