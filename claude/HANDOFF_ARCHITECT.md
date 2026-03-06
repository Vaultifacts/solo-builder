# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-014`
- Goal: add fail-fast consistency verification between machine state (`claude/STATE.json`) and rendered agent-facing state (`claude/NEXT_ACTION.md`).
- Scope: workflow scripts/docs only.

## Evidence collected
- `tools/claude_orchestrate.ps1` now renders `claude/NEXT_ACTION.md` from `STATE.json` each run.
  - Rendering placeholders are deterministic: `{{TASK_ID}}`, `{{PHASE}}`, `{{ROLE}}`, etc.
  - Role source is direct from state: `{{ROLE}}` = `$state.next_role`.
  - Phase source is direct from state: `{{PHASE}}` = `$state.phase`.
  - Task source is direct from state: `{{TASK_ID}}` = `$state.task_id`.
- Current `claude/NEXT_ACTION.md` structure is stable markdown with explicit sections:
  - `## Task`
  - `## Phase`
  - `## Role`
  - plus additional contract fields.
- `tools/audit_check.ps1` currently validates command execution and working-tree cleanliness, but does not validate `STATE.json` vs `NEXT_ACTION.md` consistency.
- No dedicated helper exists today for state/render consistency (`tools/*check*.ps1` currently only includes `audit_check.ps1`).

## Current field mappings
- `STATE.json.task_id` <-> `NEXT_ACTION.md` section `## Task`
- `STATE.json.phase` <-> `NEXT_ACTION.md` section `## Phase`
- `STATE.json.next_role` <-> `NEXT_ACTION.md` section `## Role`

These are currently one-way rendered by orchestrator but not independently verified during audit.

## Parsing/normalization observations
- `Role` text in NEXT_ACTION is currently exact role tokens (`RESEARCH|ARCHITECT|DEV|AUDITOR`) and does not require normalization in normal flow.
- `Phase` text is currently exact lower-case state phase values (`triage|research|plan|build|verify|done`) and does not require normalization in normal flow.
- For robustness, consistency checks should still trim whitespace and handle trailing newline differences.
- Because `NEXT_ACTION.md` is template-backed markdown, parsers should avoid brittle line-number assumptions and instead extract by heading labels.

## Likely mismatch/failure modes
- Orchestrator not run after state transition leaves stale `NEXT_ACTION.md`.
- Manual edits to `NEXT_ACTION.md` (even though gitignored) can diverge from state.
- Template changes that alter heading text could break naive parser extraction.
- Role mismatch after `done` transitions (observed earlier) can be detected quickly if consistency check is enforced before/within audit path.

## Minimal safe implementation direction (research-level)
- Add a dedicated workflow helper script to compare `STATE.json` and `NEXT_ACTION.md` on the three required fields and exit nonzero on mismatch.
- Invoke that helper from `tools/audit_check.ps1` as an early guard (before verify command loop), preserving existing audit semantics otherwise.
- Keep check narrowly scoped to required fields only (`task_id/task`, `phase/phase`, `next_role/role`) to avoid over-coupling to other markdown text.

## Files involved (candidate scope)
- `tools/audit_check.ps1` (integration point)
- new helper script under `tools/` for consistency check
- `claude/templates/NEXT_ACTION_TEMPLATE.md` only if extraction labels need to be explicitly locked (currently labels already explicit)

## Risks / edge cases
- If parser ties to exact markdown formatting beyond headings, small template formatting edits could cause false negatives.
- If check runs before orchestrator in some flows, stale NEXT_ACTION may intentionally exist; guard behavior must align with existing workflow expectations.
- Check should report actionable mismatch details (expected vs actual values) to reduce debugging time.

## Constraints / non-negotiables
- No product-code changes under `solo_builder/*`.
- No task lifecycle semantic changes.
- Preserve deterministic workflow conventions; add verification, do not alter role progression.
