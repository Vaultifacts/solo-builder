# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
`tools/claude_orchestrate.ps1` already writes `claude/NEXT_ACTION.md` on every run using an inline here-string template. The orchestrator references `claude/templates/NEXT_ACTION_TEMPLATE.md` (line 8) and prefers it when present (line 212), but the file and its parent directory have never been created. The only concrete deliverable needed to satisfy TASK-013 is creating that external template file so the template is externalizable and inspectable without reading the script.

## Root cause
`claude/templates/` directory was never created. The orchestrator's `Test-Path $nextActionTemplatePath` check at line 212 always falls through to the inline fallback.

## Minimal fix strategy
1. Create directory `claude/templates/`.
2. Create `claude/templates/NEXT_ACTION_TEMPLATE.md` with the same `{{PLACEHOLDER}}` content as the inline fallback in `claude_orchestrate.ps1` (lines 181–210).
3. No other files need changes.

## Allowed changes
- claude/templates/NEXT_ACTION_TEMPLATE.md
- claude/HANDOFF_ARCHITECT.md
- claude/HANDOFF_DEV.md
- claude/HANDOFF_AUDIT.md
- claude/JOURNAL.md
- claude/STATE.json
- claude/allowed_files.txt
- claude/NEXT_ACTION.md
- claude/verify_last.json

## Files that must not be modified
- tools/claude_orchestrate.ps1
- claude/AGENT_ENTRY.md
- claude/CONTROL.md
- claude/RULES.md
- Any files under solo_builder/
- claude/VERIFY.json
- claude/STATE_SCHEMA.md

## Acceptance criteria
- `claude/templates/NEXT_ACTION_TEMPLATE.md` exists and contains all nine `{{PLACEHOLDER}}` sections matching the inline template in `claude_orchestrate.ps1`.
- `pwsh tools/claude_orchestrate.ps1` reads the external template without error and produces identical `claude/NEXT_ACTION.md` output.
- `pwsh tools/audit_check.ps1` exits 0.
- No files under `solo_builder/*` are modified.
- `STATE.json` remains the machine-readable source of workflow state.

## Verification commands
1. `Test-Path claude/templates/NEXT_ACTION_TEMPLATE.md`
2. `pwsh tools/claude_orchestrate.ps1`
3. `Get-Content claude/NEXT_ACTION.md`
4. `pwsh tools/audit_check.ps1`
5. `git diff --stat`
