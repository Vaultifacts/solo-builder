# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-019

## Summary of implementation
Implemented CI verification-only invariant enforcement by introducing a CI-specific checker and wiring GitHub Actions to it.

## Files modified (implementation scope)
- tools/ci_invariant_check.ps1 (new)
- .github/workflows/ci.yml
- claude/WORKFLOW_SPEC.md

## Runtime/workflow artifacts modified
- claude/JOURNAL.md (expected workflow logging)
- claude/allowed_files.txt (runtime artifact from allowed-file extraction)

## What changed
1. Added `tools/ci_invariant_check.ps1`:
   - Runs `tools/check_next_action_consistency.ps1` first.
   - Loads `claude/VERIFY.json` and executes listed commands with timeout handling.
   - Fails nonzero when any required command fails.
   - Does not mutate workflow state and does not call lifecycle-transition commands.

2. Updated `.github/workflows/ci.yml`:
   - Replaced CI step `pwsh tools/audit_check.ps1` with `pwsh tools/ci_invariant_check.ps1`.
   - Updated `ci_bundle/repro.ps1` to use `ci_invariant_check.ps1`.

3. Updated `claude/WORKFLOW_SPEC.md`:
   - Added CI verification-only contract section.
   - Documented canonical CI command path (`pwsh tools/ci_invariant_check.ps1`).
   - Explicitly prohibited lifecycle-mutating commands in CI (`advance_state`, `start_task`, branch ops).

## Verification run
- `pwsh tools/ci_invariant_check.ps1` -> PASS
  - Included: state/next_action consistency check
  - Ran required commands from `claude/VERIFY.json`
- `pwsh tools/dev_gate.ps1 -Mode Manual` -> PASS

## Acceptance criteria mapping
- Automatic CI path for invariant checks: satisfied via `.github/workflows/ci.yml` calling `tools/ci_invariant_check.ps1`.
- CI fails nonzero on required-check failures: implemented in `ci_invariant_check.ps1`.
- CI remains verification-only with no lifecycle mutations: enforced by script scope and documented in workflow spec.
- No product-code changes: satisfied.

## Risks / notes
- `tools/plan_extract.ps1` is referenced in prompting but does not exist in repo (pre-existing workflow mismatch, out of TASK-019 scope).
- `claude/allowed_files.txt` remains a runtime artifact and should not be committed.
