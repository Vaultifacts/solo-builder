# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-265

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (553 tests, 0 failures; +5 new)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/blueprints/core.py` — `GET /status` now includes `stalled_by_branch` list: one entry per branch with stalled subtasks, each `{task, branch, count}`; iteration refactored to track per-task/branch names
- `solo_builder/api/test_app.py` — 5 new tests in `TestGetStatus`: key present, empty when no stall, populated when stalled, count matches stalled total, not-stalled branch excluded; `_set_threshold_in_settings()` helper added inline

## Implementation Detail
`stalled_by_branch` accumulates an entry per branch where `branch_stalled > 0`; `stalled` top-level total still equals `sum(e["count"] for e in stalled_by_branch)`.
Tests use `_set_threshold_in_settings(5)` + `step=10` + `last_update=0` to force stall (age=10 ≥ 5).
Not-stalled test: `last_update=9`, `step=10` → age=1 < 5 → empty list.
Response is backward-compatible: all existing keys unchanged, `stalled_by_branch` is additive.
