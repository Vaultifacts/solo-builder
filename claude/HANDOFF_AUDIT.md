# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-271

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (559 tests, 0 failures; +1 new)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/blueprints/core.py` — `stalled_by_branch` sorted by count desc before returning (one-line change wrapping list in `sorted(..., key=lambda x: x["count"], reverse=True)`)
- `solo_builder/api/test_app.py` — 1 new test `test_stalled_by_branch_sorted_desc`: two-task state with 2+1 stalled branches; asserts counts are desc-sorted and first entry has count=2

## Implementation Detail
Mirrors sort order of `GET /stalled` `by_branch` (TASK-268) and `_format_stalled` Discord formatter (TASK-269) — all three now consistently sort highest stall count first.
