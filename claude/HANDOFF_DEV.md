# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
Workflow handoff headings are not consistently generated in canonical form. `TASK-012` requires canonical schema so tools and prompts converge on one format:
- `## Allowed changes`
- `## Files that must not be modified`
- `## Acceptance criteria`
- `## Verification commands`

## Root cause
Schema drift comes from generation sources:
- `claude/templates/HANDOFF_DEV_TEMPLATE.md` does not include all canonical headings.
- `claude/prompts/architect_prompt.txt` does not enforce canonical section names.
This allows handoffs like `## Allowed files to modify` and other variants to persist.

## Minimal fix strategy
1. Update the DEV handoff template to canonical section headings required by `TASK-012`.
2. Update the architect role prompt so generated `claude/HANDOFF_DEV.md` explicitly uses the canonical heading names.
3. Keep `tools/extract_allowed_files.ps1` unchanged; parser aliases from TASK-011 remain as backward-compatible support.
4. Do not rewrite historical handoff artifacts; normalize generation points only.

## Allowed files to modify
- claude/templates/HANDOFF_DEV_TEMPLATE.md
- claude/prompts/architect_prompt.txt

## Files that must not be modified
- Any files under `solo_builder/`
- `tools/extract_allowed_files.ps1` and other `tools/*` scripts
- `claude/VERIFY.json`, orchestrator/state semantics files, and unrelated task artifacts
- Historical handoff files not needed for current template/prompt normalization

## Risks
- If canonical headings are updated in only one generation source, drift can continue.
- Over-editing prompt text may unintentionally change role behavior beyond heading schema.
- Removing parser aliases would break backward compatibility (must not be done in this task).

## Acceptance criteria
- `claude/templates/HANDOFF_DEV_TEMPLATE.md` contains canonical headings:
  - `## Allowed changes`
  - `## Files that must not be modified`
  - `## Acceptance criteria`
  - `## Verification commands`
- `claude/prompts/architect_prompt.txt` explicitly instructs canonical handoff headings for `claude/HANDOFF_DEV.md`.
- `tools/extract_allowed_files.ps1` remains unchanged and continues to parse canonical headings.
- No product-code changes under `solo_builder/*`.
- No orchestrator/state semantic changes.

## Verification commands
1. `git diff -- claude/templates/HANDOFF_DEV_TEMPLATE.md claude/prompts/architect_prompt.txt`
2. `Get-Content -Raw claude/templates/HANDOFF_DEV_TEMPLATE.md`
3. `Get-Content -Raw claude/prompts/architect_prompt.txt`
4. `pwsh tools/extract_allowed_files.ps1`
5. `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail`
