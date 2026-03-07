# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
The workflow currently relies on manual discipline to validate baseline safety before initializing a new task branch. Missing preflight enforcement can allow initialization from an unsafe repo state (dirty tree, stale runtime artifacts, state/contract drift, or unmerged prior task branch).

## Root cause
There is no single pre-init guard script that combines all required baseline checks in one deterministic pass. Existing checks are spread across scripts (for example, STATE/NEXT_ACTION consistency and verification-time git checks) and are not explicitly composed for task initialization safety.

## Minimal fix strategy
1. Add `tools/workflow_preflight.ps1` as a single pre-init safety gate script.
2. In `workflow_preflight.ps1`, perform these checks only:
   - clean working tree check via `git status --porcelain` (fail on any entries)
   - runtime artifact dirtiness check for tracked modifications of:
     - `claude/allowed_files.txt`
     - `claude/verify_last.json`
   - STATE/NEXT_ACTION consistency check by invoking `tools/check_next_action_consistency.ps1`
   - conservative baseline merge check against `master`:
     - on `master`: pass baseline branch check
     - on `task/TASK-<N>`: derive `task/TASK-(N-1)`; if that branch exists, require it be contained in `master`; if not present locally, skip with explicit informational output
3. Keep script output explicit and actionable for each failure mode (what failed and how to fix).
4. Do not modify lifecycle/state semantics, orchestrator behavior, or product code.

## Allowed files to modify
- tools/workflow_preflight.ps1

## Files that must not be modified
- Any files under `solo_builder/*`
- tools/claude_orchestrate.ps1
- tools/advance_state.ps1
- tools/audit_check.ps1
- tools/check_next_action_consistency.ps1
- claude/STATE.json
- claude/NEXT_ACTION.md
- claude/TASK_QUEUE.md
- claude/TASK_ACTIVE.md
- claude/JOURNAL.md

## Risks
- Branch baseline detection can be brittle if task numbers are non-contiguous.
- Overly strict cleanliness checks could block valid workflows if intentionally untracked files are present.
- Ambiguous failure messages can reduce operator trust in preflight outcomes.

## Acceptance criteria
- `tools/workflow_preflight.ps1` fails if the current branch is not clean.
- `tools/workflow_preflight.ps1` fails if runtime artifacts are dirty (`claude/allowed_files.txt`, `claude/verify_last.json`).
- `tools/workflow_preflight.ps1` invokes `tools/check_next_action_consistency.ps1` and fails on mismatch.
- `tools/workflow_preflight.ps1` verifies safe baseline conservatively (master contains previous task branch when applicable).
- `tools/workflow_preflight.ps1` exits `0` only when all preflight checks pass.
- No workflow semantics are changed.
- No product-code changes are introduced.

## Verification commands
1. `pwsh tools/workflow_preflight.ps1` (clean/safe baseline expected PASS).
2. Simulate dirty runtime artifact and confirm nonzero exit:
   - modify `claude/allowed_files.txt`, run preflight, then restore.
3. Simulate STATE/NEXT_ACTION mismatch and confirm nonzero exit:
   - temporary edit one field in local `claude/STATE.json`, run preflight, then restore via orchestrator/state correction.
4. Baseline branch safety check:
   - run from `task/TASK-017` and verify conservative branch check messaging/behavior.
5. `git status --short --branch` confirms no unintended file changes after validation cleanup.
