# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
When workflow state is `done`, `tools/claude_orchestrate.ps1` shows summary fields from persisted state but emits a hardcoded AUDITOR copy/paste prompt. This produces inconsistent terminal output after closeout transitions that set `done/ARCHITECT`.

## Root cause
In `Get-RoleContract`, the `if ($Phase -eq 'done')` branch returns a fixed contract with `Prompt = "You are AUDITOR..."`, ignoring the persisted `next_role` value passed as `$Role`.

## Minimal fix strategy
1. Update only the done-phase branch in `tools/claude_orchestrate.ps1` so prompt rendering respects persisted `$Role` (or is made role-neutral in a way that remains consistent with displayed `Next role`).
2. Keep all non-done role contracts unchanged (`RESEARCH`, `ARCHITECT`, `DEV`, `AUDITOR`).
3. Preserve existing state validation and transition semantics; change only terminal rendering consistency.

## Allowed files to modify
- tools/claude_orchestrate.ps1

## Files that must not be modified
- Any files under `solo_builder/*`
- tools/advance_state.ps1
- tools/audit_check.ps1
- claude/templates/NEXT_ACTION_TEMPLATE.md
- claude/STATE.json
- claude/VERIFY.json
- Any lifecycle/phase mapping semantics outside done-phase rendering

## Risks
- Over-correcting done behavior could unintentionally change expected post-close operator workflow.
- Modifying shared prompt-generation logic could affect non-done phases if not tightly scoped.
- Inconsistent wording between `Next role` summary and copy/paste prompt may persist if only one path is updated.

## Acceptance criteria
- With persisted state `done/ARCHITECT`, orchestrator displays `Next role: ARCHITECT` and emits a matching terminal prompt contract (no AUDITOR mismatch).
- With persisted state `done/AUDITOR`, orchestrator displays and emits consistent AUDITOR terminal contract.
- Non-done phases (`triage`, `research`, `plan`, `build`, `verify`) preserve existing behavior.
- No product-code changes are introduced.

## Verification commands
1. `pwsh tools/advance_state.ps1 -ToPhase done -ToRole ARCHITECT -TaskId TASK-015 -Note "terminal render test"`
2. `pwsh tools/claude_orchestrate.ps1`
3. Confirm summary `Next role` and copy/paste prompt role are consistent.
4. `pwsh tools/advance_state.ps1 -ToPhase done -ToRole AUDITOR -TaskId TASK-015 -Note "terminal render test"`
5. `pwsh tools/claude_orchestrate.ps1`
6. Reconfirm consistency.
7. `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail`
8. `git diff --stat`
