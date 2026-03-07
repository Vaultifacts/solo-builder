# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
`workflow_preflight.ps1` exists but is currently invoked manually during task initialization. Because there is no single initialization entry script, preflight enforcement is optional in practice and can be skipped.

## Root cause
Task initialization is performed through operator convention (multiple manual commands) rather than a dedicated workflow entry point. This prevents deterministic, automatic enforcement of preflight before task branch creation.

## Minimal fix strategy
1. Add one dedicated initialization entry script: `tools/start_task.ps1`.
2. In `start_task.ps1`, implement the canonical init sequence with fixed order:
   - verify clean repo state
   - switch to `master`
   - optionally pull only when upstream exists
   - merge previous task branch (when provided/derivable)
   - run `pwsh tools/workflow_preflight.ps1`
   - if preflight passes, create `task/TASK-<N>`
   - update workflow metadata (`TASK_QUEUE`, `TASK_ACTIVE`, local `STATE.json`, `JOURNAL`)
   - run orchestrator
3. Abort immediately on any nonzero preflight result (do not create new task branch).
4. Add minimal documentation update in `claude/WORKFLOW_SPEC.md` to state the canonical initialization command/path (no semantic changes).

## Allowed files to modify
- tools/start_task.ps1
- claude/WORKFLOW_SPEC.md

## Files that must not be modified
- Any files under `solo_builder/*`
- tools/workflow_preflight.ps1
- tools/check_next_action_consistency.ps1
- tools/claude_orchestrate.ps1
- tools/advance_state.ps1
- claude/STATE_SCHEMA.md
- Any role/phase lifecycle semantics

## Risks
- Over-automating initialization could inadvertently change operator expectations if script behavior differs from existing manual sequence.
- Merge-target derivation for previous task branch can be brittle if naming is non-contiguous.
- Incorrectly handling missing upstream/pull behavior could introduce network dependency where none is required.

## Acceptance criteria
- `workflow_preflight.ps1` runs automatically during initialization via `tools/start_task.ps1`.
- Initialization stops before branch creation if preflight exits nonzero.
- Preflight execution order is guaranteed: after switching to `master`, before creating `task/TASK-<N>`.
- Existing workflow semantics remain unchanged.
- No product code under `solo_builder/*` is modified.

## Verification commands
1. Positive path (expected pass):
   - run `pwsh tools/start_task.ps1 -TaskId TASK-018 -NoCommit` (or equivalent dry-run/safe mode if implemented)
   - confirm preflight was executed before branch creation step.
2. Negative path (expected fail):
   - dirty `claude/verify_last.json` or `claude/allowed_files.txt`
   - run `pwsh tools/start_task.ps1 -TaskId TASK-018 -NoCommit`
   - confirm nonzero exit and no new task branch creation.
3. Confirm docs update:
   - `Get-Content -Raw claude/WORKFLOW_SPEC.md`
   - verify canonical init flow includes `start_task.ps1` with preflight gating.
4. Safety check:
   - `git status --short --branch`
   - confirm no product-code files changed.
