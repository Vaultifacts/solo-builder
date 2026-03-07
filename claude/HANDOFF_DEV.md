# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
TASK-019 needs CI enforcement of workflow invariants so pushes/PRs fail when core workflow contracts drift. Current CI runs `tools/audit_check.ps1`, which is built for local workflow progression and mutates local workflow runtime files (`claude/STATE.json`, `claude/verify_last.json`). For CI, we need a verification-only execution path.

## Root cause
There is no CI-dedicated invariant runner. CI currently reuses a local lifecycle script (`audit_check.ps1`) that includes side effects beyond pure verification.

## Minimal fix strategy
1. Add one CI-dedicated verification script (new file): `tools/ci_invariant_check.ps1`.
2. In that script, run only verification checks:
   - call `tools/check_next_action_consistency.ps1`
   - execute required commands listed in `claude/VERIFY.json`
   - fail nonzero when any required check fails
3. Keep CI runner side-effect free for workflow state:
   - do not call `tools/advance_state.ps1`
   - do not update `claude/STATE.json`
   - do not initialize tasks or create branches
4. Update `.github/workflows/ci.yml` to use the new CI invariant runner in place of direct `audit_check.ps1` execution.
5. Update `claude/WORKFLOW_SPEC.md` minimally to document CI as verification-only and reference the CI invariant command path.

## Allowed changes
- tools/ci_invariant_check.ps1
- .github/workflows/ci.yml
- claude/WORKFLOW_SPEC.md

## Files that must not be modified
- Any files under `solo_builder/*`
- tools/advance_state.ps1
- tools/claude_orchestrate.ps1
- tools/start_task.ps1
- tools/workflow_preflight.ps1
- tools/audit_check.ps1
- claude/STATE_SCHEMA.md
- claude/TASK_ACTIVE.md
- claude/TASK_QUEUE.md

## Risks
- Parsing/executing commands from `VERIFY.json` in CI may differ from local shell expectations.
- If CI runner diverges from local verification contract, local/CI outcomes can drift.
- Overly broad command execution in CI could introduce flaky behavior if optional commands are not handled consistently.

## Acceptance criteria
- CI runs a dedicated verification-only workflow command path.
- CI checks include STATE/NEXT_ACTION consistency and required verification commands from `claude/VERIFY.json`.
- CI fails nonzero when required checks fail.
- CI path does not mutate workflow lifecycle state (`STATE.json` phase/role transitions are not performed).
- No product-code files are changed.

## Verification commands
1. Local dry run of CI invariant runner:
   - `pwsh tools/ci_invariant_check.ps1`
2. Failure-path proof (nonzero):
   - induce a controlled required-check failure (for example temporary required command failure context), run `pwsh tools/ci_invariant_check.ps1`, confirm nonzero exit
3. CI workflow wiring check:
   - `Get-Content -Raw .github/workflows/ci.yml`
   - confirm workflow uses `pwsh tools/ci_invariant_check.ps1`
4. Spec alignment check:
   - `Get-Content -Raw claude/WORKFLOW_SPEC.md`
   - confirm CI is documented as verification-only (no state mutation, no task init/branch creation)
5. Safety/status check:
   - `git diff --stat`
   - `git status --short --branch`
