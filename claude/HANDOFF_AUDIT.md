# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-260

## Verdict: PASS

## Verification Results
- lint_dashboard_handlers.js: PASS (47 handler calls, 0 gaps)
- unittest-discover (api): PASS (548 tests, 0 failures; +0 new tests, UI-only change)
- git-status: PASS (clean working tree)

## Scope Check
One file modified:
- `solo_builder/api/static/dashboard_panels.js` — `switchTab()` calls `_updateSubtasksExportLinks()` when switching to "subtasks" tab, ensuring CSV/JSON export hrefs reflect the current active filters without needing a fresh poll

## Implementation Detail
Before this fix, if a user set a name/status/task/branch filter, navigated away, and returned to the Subtasks tab, the export link hrefs would still reflect the pre-filter default (no params) until the next poll cycle.
Fix: add `if (name === "subtasks") { _updateSubtasksExportLinks(); }` in `switchTab()`, parallel to the existing `if (name === "export")` block.
No new API, no new tests needed — `_updateSubtasksExportLinks` is a pure DOM update function.
