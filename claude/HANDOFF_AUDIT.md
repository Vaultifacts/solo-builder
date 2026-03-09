# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-251

## Verdict: PASS

## Verification Results
- unittest-discover (api): PASS (522 tests, 0 failures; +10 new)
- git-status: PASS (clean working tree)

## Scope Check
Two files modified:
- `solo_builder/api/blueprints/subtasks.py` — ?name= filter added to subtasks_all() and subtasks_export()
- `solo_builder/api/test_app.py` — 5 tests in TestSubtasksAll + 5 in TestSubtasksExport for ?name= filter

## Implementation Detail
GET /subtasks and GET /subtasks/export accepted ?task=, ?branch=, ?status= but had no filter for subtask name.
Added ?name= (case-insensitive substring on st_name) to both endpoints.
The dashboard #subtasks-filter placeholder already says "Filter subtask/status/branch…" implying name filtering is expected.
Tests cover: exact match, substring, no-match, case-insensitive, compose with status.
