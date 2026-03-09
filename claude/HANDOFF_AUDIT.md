# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-268

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (558 tests, 0 failures; +5 new)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/blueprints/subtasks.py` — `GET /stalled` now includes `by_branch: [{task, branch, count}]` sorted by count desc; computed from the existing `stuck` list before returning
- `solo_builder/api/test_app.py` — 5 new tests in `TestStalled`: key present, empty when no stall, populated from multi-task state (fields check), sum equals total count, sorted desc

## Implementation Detail
`by_branch` mirrors the shape of `stalled_by_branch` in `GET /status` (task/branch/count) for API parity.
Sort: highest stall count first (same as `GET /status` after TASK-270).
Backward-compatible: existing `stalled`, `count`, `step`, `threshold` keys unchanged.
