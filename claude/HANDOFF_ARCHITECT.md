# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-015`
- Goal: fix post-close role rendering mismatch in `tools/claude_orchestrate.ps1` for `phase=done`.
- Scope: workflow/orchestrator behavior only.

## Evidence collected
- `tools/advance_state.ps1` behavior:
  - Accepts `-ToPhase done -ToRole <role>` without phase-role mapping restriction for `done`.
  - Persists both `state.phase` and `state.next_role` exactly as passed.
  - Therefore, when called with `done/ARCHITECT`, persisted machine state is expected to be `phase=done`, `next_role=ARCHITECT`.
- `tools/claude_orchestrate.ps1` behavior:
  - Summary output (`Current task`, `Phase`, `Next role`) is written from `$state.*`.
  - Contract/prompt output is produced by `Get-RoleContract`.
  - In `Get-RoleContract`, when `$Phase -eq 'done'`, the returned prompt is hardcoded to `You are AUDITOR...` regardless of `$Role`.
  - This creates a done-phase terminal prompt mismatch with persisted `next_role`.
- `NEXT_ACTION.md` rendering in orchestrator:
  - Uses `{{ROLE}}` replacement from `$state.next_role`.
  - Uses other placeholders from `$state` and contract fields.
  - Done-phase prompt contract and rendered role can therefore diverge if contract is hardcoded.

## Current role-rendering logic
- Displayed summary role source: `state.next_role`.
- Rendered contract role source in `done` branch: hardcoded AUDITOR prompt text, independent of `state.next_role`.
- Non-done phases: contract selection follows role switch (`RESEARCH|ARCHITECT|DEV|AUDITOR`) using passed role.

## Mismatch cause
- Done-phase handling in `Get-RoleContract` is treated as a special branch that ignores role-specific prompt semantics.
- This branch returns an AUDITOR prompt unconditionally, which conflicts with expected post-close `done/ARCHITECT` state used by lifecycle.

## Likely minimal safe fix direction (research-level)
- Keep lifecycle semantics unchanged.
- Narrow fix surface to `tools/claude_orchestrate.ps1` done-phase contract rendering:
  - make done-phase prompt/role rendering consistent with persisted `state.next_role`, or
  - make terminal done contract explicitly role-neutral and consistent across both summary and prompt output.
- Ensure `NEXT_ACTION.md` role and copy/paste prompt align in done-phase.

## Files involved
- `tools/claude_orchestrate.ps1` (primary)
- `claude/templates/NEXT_ACTION_TEMPLATE.md` only if needed for a stable terminal contract wording (likely not required)

## Possible regression risks
- Changing done-phase prompt behavior could unintentionally affect expected closeout operator habits.
- If done-phase becomes role-neutral, downstream scripts/prompts expecting explicit role labels may need to be verified.
- Non-done role prompts must remain unchanged.

## Constraints / non-negotiables
- No product-code changes under `solo_builder/*`.
- No task lifecycle semantic changes.
- Preserve deterministic workflow conventions.
- Keep fix minimal and done-phase focused.
