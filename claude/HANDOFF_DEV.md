# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
The deterministic Solo Builder workflow is currently enforced by scripts plus conventions, but there is no single canonical written specification that clearly documents the full lifecycle and distinguishes script-enforced rules from operator conventions.

## Root cause
Workflow knowledge is distributed across multiple files (`tools/*.ps1`, `claude/*.md`, prompts, and historical journal/task patterns). This creates avoidable ambiguity for agents and operators, especially around branch baseline discipline, closeout cleanup, and runtime artifact handling.

## Minimal fix strategy
1. Create one canonical specification file at `claude/WORKFLOW_SPEC.md` that documents current behavior only.
2. Structure the spec to explicitly separate:
   - Script-enforced behavior
   - Convention/operator-required behavior
3. Document, without changing semantics:
   - task lifecycle
   - branch lifecycle
   - workflow phases and roles
   - closeout procedure
   - merge-first baseline rule
   - local-only runtime artifact handling
4. Keep this task documentation-only; do not edit scripts, orchestration logic, or product code.

## Allowed files to modify
- claude/WORKFLOW_SPEC.md

## Files that must not be modified
- Any files under `solo_builder/*`
- All `tools/*.ps1` scripts
- `claude/STATE.json`
- `claude/NEXT_ACTION.md`
- `claude/TASK_QUEUE.md`
- `claude/TASK_ACTIVE.md`
- `claude/JOURNAL.md`
- `claude/HANDOFF_ARCHITECT.md`
- Any workflow semantics or state-machine behavior

## Risks
- If wording is not precise, the spec could accidentally imply new semantics instead of documenting existing ones.
- If enforced vs convention sections are mixed, future agents may misinterpret optional practices as script guarantees.
- Over-documenting edge cases could add noise and reduce operational clarity.

## Acceptance criteria
- `claude/WORKFLOW_SPEC.md` exists.
- The spec documents:
  - task lifecycle
  - branch lifecycle
  - workflow phases and roles
  - closeout procedure
  - merge-first baseline rule
  - local-only runtime artifact handling
- The spec matches currently enforced behavior and current conventions in the repo.
- The spec clearly separates script-enforced rules from conventions.
- No workflow semantics are changed.
- No product-code changes are introduced.

## Verification commands
1. `git diff -- claude/WORKFLOW_SPEC.md`
2. `Get-Content -Raw claude/WORKFLOW_SPEC.md`
3. Confirm the spec explicitly contains sections for:
   - task lifecycle
   - branch lifecycle
   - workflow phases and roles
   - closeout procedure
   - merge-first baseline rule
   - local-only runtime artifact handling
4. Confirm wording distinguishes script-enforced behavior from convention/operator policy.
5. `git status --short --branch`
