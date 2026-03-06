# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
The workflow now renders `claude/NEXT_ACTION.md` from `claude/STATE.json`, but verification does not currently enforce that these two views stay consistent. Agents can therefore act on stale or drifted rendered state without a fail-fast signal.

## Root cause
`tools/audit_check.ps1` validates command results and working-tree cleanliness, but has no preflight check that compares machine state (`STATE.json`) with rendered agent-facing state (`NEXT_ACTION.md`) for core routing fields.

## Minimal fix strategy
1. Add a dedicated helper script that parses `claude/STATE.json` and `claude/NEXT_ACTION.md`, then compares:
   - `task_id` vs `Task`
   - `phase` vs `Phase`
   - `next_role` vs `Role`
2. Keep parsing deterministic and narrow:
   - parse `NEXT_ACTION.md` by exact heading labels (`## Task`, `## Phase`, `## Role`)
   - trim whitespace; do not parse unrelated sections
3. Integrate helper at the start of `tools/audit_check.ps1` (before verify command loop):
   - fail immediately with clear mismatch details if check fails
   - preserve all existing audit behavior when check passes

## Allowed files to modify
- tools/check_next_action_consistency.ps1
- tools/audit_check.ps1

## Files that must not be modified
- Any files under `solo_builder/*`
- tools/claude_orchestrate.ps1
- claude/templates/NEXT_ACTION_TEMPLATE.md
- claude/AGENT_ENTRY.md
- claude/CONTROL.md
- claude/RULES.md
- claude/VERIFY.json
- Any workflow state-machine semantics or phase mappings

## Risks
- Brittle parsing if helper depends on markdown layout beyond required headings.
- False negatives if newline/whitespace normalization is not handled.
- Overreach if helper checks fields outside task/phase/role contract.

## Acceptance criteria
- Helper exits 0 when `STATE.json` and `NEXT_ACTION.md` match on required fields.
- Helper exits nonzero on mismatch and prints clear expected/actual values.
- `tools/audit_check.ps1` invokes helper early and exits nonzero on mismatch.
- Existing audit semantics remain unchanged when consistency check passes.
- No product-code changes under `solo_builder/*`.

## Verification commands
1. `pwsh tools/claude_orchestrate.ps1`
2. `pwsh tools/check_next_action_consistency.ps1`
3. Introduce controlled mismatch (edit local `claude/NEXT_ACTION.md` role/task/phase) and rerun helper to confirm nonzero exit.
4. Restore `claude/NEXT_ACTION.md` by rerunning orchestrator.
5. `pwsh tools/audit_check.ps1`
6. `git diff --stat`
