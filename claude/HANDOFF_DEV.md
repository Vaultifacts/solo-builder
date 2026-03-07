# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
Two classes of workflow contract drift are currently undetected at automated boundaries:

**Direction A — script-reference integrity:** workflow contract files reference `tools/*.ps1`
scripts that do not exist on disk. Example: `tools/plan_extract.ps1` was referenced in
prompting and documented as a known gap in TASK-019; no automated check ever caught it.

**Direction B — allowed-file declaration integrity:** lifecycle scripts write `claude/` files
that are not declared in `claude/allowed_files.txt`. The pre-commit hook catches this at
commit time (blocking the commit), but no check validates the contract gap proactively.
Confirmed instance: `start_task.ps1` writes `TASK_ACTIVE.md` and `TASK_QUEUE.md`; neither
was in `allowed_files.txt` until TASK-020 init was blocked and required an inline fix.

Neither direction is currently caught by CI.

## Architectural decision
**CI-only scope.** Do not integrate into `workflow_preflight.ps1` for this task.
Rationale: preflight integration expands scope and local-run behavior surface; CI integration
alone closes the automated detection gap without increasing behavioral complexity.
Future task may add preflight integration if the CI check proves stable.

## Implementation plan

### 1. New script: `tools/workflow_contract_check.ps1`

**Phase A — Script-reference integrity check:**
- Scan the following contract source files for `tools/[A-Za-z_]+\.ps1` pattern:
  - `claude/AGENT_ENTRY.md`
  - `claude/WORKFLOW_SPEC.md`
  - `claude/NEXT_ACTION.md`
  - `claude/RULES.md`
  - `.github/workflows/ci.yml`
  - All files matching `claude/checklists/*.md` (if directory exists)
- For each matched reference, assert `Test-Path` of the resolved script path.
- Skip files that do not exist (non-fatal; warn and continue scanning present files).
- Collect all violations.

**Phase B — Lifecycle file declaration integrity check:**
Use a hardcoded canonical map of lifecycle scripts and their known output files.
Do NOT dynamically parse scripts — static map is deterministic and maintainable.

Canonical map (script → files it writes):
```
tools/start_task.ps1       → claude/TASK_ACTIVE.md, claude/TASK_QUEUE.md,
                              claude/JOURNAL.md, claude/STATE.json
tools/advance_state.ps1    → claude/JOURNAL.md, claude/STATE.json, claude/NEXT_ACTION.md
tools/claude_orchestrate.ps1 → claude/NEXT_ACTION.md
tools/audit_check.ps1      → claude/verify_last.json
tools/extract_allowed_files.ps1 → claude/allowed_files.txt
```

- Load `claude/allowed_files.txt` (if missing: fail with descriptive error).
- For each entry in the canonical map, assert each output file is present in `allowed_files.txt`.
- Collect all violations.

**Exit behavior:**
- Exit 0 if both phases have zero violations.
- Exit 1 with a descriptive listing of each violation (phase, source, missing item).
- Print a summary line: `workflow_contract_check: PASS` or `workflow_contract_check: FAIL (N violations)`.

### 2. Update `.github/workflows/ci.yml`

Add a new step **before** the existing `CI invariant check` step:

```yaml
- name: Workflow contract check
  shell: pwsh
  run: pwsh tools/workflow_contract_check.ps1
```

Also add `pwsh tools/workflow_contract_check.ps1` as the **first line** of `ci_bundle/repro.ps1`
(the inline heredoc in the `Build ci_bundle` step).

### 3. Update `claude/WORKFLOW_SPEC.md`

Add a new section **before** "Non-goals of this specification":

```
## Workflow contract integrity
Two classes of drift are checked by `pwsh tools/workflow_contract_check.ps1`:

Direction A — script-reference integrity:
- Workflow contract files must not reference tools/*.ps1 scripts that do not exist on disk.
- Checked sources: claude/AGENT_ENTRY.md, claude/WORKFLOW_SPEC.md, claude/NEXT_ACTION.md,
  claude/RULES.md, .github/workflows/ci.yml, claude/checklists/*.md.

Direction B — lifecycle file declaration integrity:
- Files written by lifecycle scripts must be declared in claude/allowed_files.txt.
- Canonical lifecycle script output declarations are maintained in tools/workflow_contract_check.ps1.

CI runs this check via: pwsh tools/workflow_contract_check.ps1
```

## Allowed changes
- tools/workflow_contract_check.ps1
- .github/workflows/ci.yml
- claude/WORKFLOW_SPEC.md

## Files that must not be modified
- Any files under `solo_builder/`
- tools/advance_state.ps1
- tools/claude_orchestrate.ps1
- tools/start_task.ps1
- tools/workflow_preflight.ps1
- tools/audit_check.ps1
- tools/enforce_allowed_files.ps1
- claude/STATE_SCHEMA.md
- claude/allowed_files.txt (DEV must NOT modify this directly; run extract_allowed_files.ps1)

## Acceptance criteria
- `pwsh tools/workflow_contract_check.ps1` exits 0 on the clean repo.
- `pwsh tools/workflow_contract_check.ps1` exits nonzero when a contract violation is induced:
  - e.g. temporarily add a reference to a nonexistent `tools/ghost_script.ps1` in a contract
    source, run check, confirm exit 1 and violation listed; then revert.
- CI workflow runs `workflow_contract_check` before `ci_invariant_check`.
- `claude/WORKFLOW_SPEC.md` documents both drift directions and the canonical CI command.
- No files outside the Allowed changes list are modified.

## Verification commands
1. Dry run on clean repo:
   - `pwsh tools/workflow_contract_check.ps1`
2. Failure-path proof:
   - Temporarily add `tools/ghost_script.ps1` reference to a contract source, rerun, confirm nonzero
3. CI wiring check:
   - `Get-Content -Raw .github/workflows/ci.yml` — confirm `workflow_contract_check` step present
     and ordered before `ci_invariant_check`
4. Spec alignment check:
   - `Get-Content -Raw claude/WORKFLOW_SPEC.md` — confirm Workflow contract integrity section present
5. Status check:
   - `git diff --stat` and `git status --short --branch`
