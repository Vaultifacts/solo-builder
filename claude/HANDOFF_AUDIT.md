# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-275

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (568 tests, 0 failures; +5 new)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/blueprints/subtasks.py` — `?min_age=N` added to both `subtasks_all()` and `subtasks_export()`: skips non-Running subtasks and Running subtasks with age < N; changed `_load_dag()` → `_load_state()` to access `step`; docstrings updated
- `solo_builder/api/test_app.py` — 5 new tests in `TestSubtasksAll`: stalled running returned, fresh running excluded, non-running excluded, min_age=0 returns all, at-boundary included

## Implementation Detail
`min_age=0` (default) is a no-op — the `if min_age > 0` guard prevents any filtering.
Filter applied after status/name/task/branch filters, so `?status=running&min_age=5` composes correctly.
`age = step - st_data.get("last_update", 0)` matches the stall computation in core.py and subtasks.py stalled().
