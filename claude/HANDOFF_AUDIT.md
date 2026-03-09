# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-249

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (512 tests, 0 failures; +5 new)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/blueprints/history.py` — added ?branch= filter to history_export(); updated docstring
- `solo_builder/api/test_app.py` — 5 new tests in TestHistoryExport: branch match, no match, case-insensitive, compose with status, CSV branch filter

## Implementation Detail
GET /history/export accepted ?subtask=, ?status=, ?task= but NOT ?branch=.
The JS (_updateHistoryExportLinks) already appended &branch=X to export hrefs when branch filter active — the server silently ignored it.
Fix: added branch_q = request.args.get("branch") and filter step alongside the other filters.
Parity with GET /history/count which already supported ?branch=.
