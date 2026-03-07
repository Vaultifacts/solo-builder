# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-020`
- Goal: Add automated validation that workflow contracts reference only existing tools/scripts,
  and that lifecycle scripts only write files declared in `claude/allowed_files.txt`.
- Scope: workflow infrastructure only; no product-code changes.

## 1) Problem framing

Workflow contract drift can occur in two directions and neither is currently caught at authoring time:

**Direction A — command-reference integrity:**
A workflow contract file (NEXT_ACTION.md, WORKFLOW_SPEC.md, AGENT_ENTRY.md, VERIFY.json, ci.yml)
references a script under `tools/` that no longer exists or was renamed. Example:
- `tools/plan_extract.ps1` was referenced in prompting but does not exist in the repo.
  Documented as a known gap in TASK-019 HANDOFF_AUDIT.md, never caught automatically.

**Direction B — allowed-file declaration integrity:**
A lifecycle script writes to a file not declared in `claude/allowed_files.txt`. The
pre-commit hook (`enforce_allowed_files.ps1`) catches this, but only at commit time — it
blocks the commit rather than catching the gap earlier. Concrete confirmed instance:
- `start_task.ps1` writes `claude/TASK_ACTIVE.md` and `claude/TASK_QUEUE.md`.
- Neither was in `allowed_files.txt` until TASK-020 init hit the blocker and required
  an inline fix. This was not detected by any earlier automated check.

## 2) Evidence gathered

### Contract sources surveyed
- `claude/AGENT_ENTRY.md` — references `audit_check.ps1`, `dev_gate.ps1`
- `claude/NEXT_ACTION.md` — references `research_extract.ps1` (phase-specific)
- `claude/WORKFLOW_SPEC.md` — references `advance_state.ps1`, `claude_orchestrate.ps1`,
  `audit_check.ps1`, `start_task.ps1`, `workflow_preflight.ps1`, `ci_invariant_check.ps1`
- `.github/workflows/ci.yml` — references `bootstrap_verify.ps1`, `ci_invariant_check.ps1`
- `claude/RULES.md` — references `claude_snapshot.ps1`
- `claude/checklists/AUDITOR.md` — references `audit_check.ps1`
- `claude/checklists/DEV.md` — references `precommit_gate.ps1`

### Script-reference integrity check (Direction A)
All contract-referenced scripts verified against `tools/`:
- `advance_state.ps1` ✓, `audit_check.ps1` ✓, `bootstrap_verify.ps1` ✓,
  `ci_invariant_check.ps1` ✓, `claude_orchestrate.ps1` ✓, `claude_snapshot.ps1` ✓,
  `dev_gate.ps1` ✓, `precommit_gate.ps1` ✓, `research_extract.ps1` ✓,
  `start_task.ps1` ✓, `workflow_preflight.ps1` ✓
- No currently-active contract references point to missing scripts.
- Historical gap (`plan_extract.ps1`): present only in HANDOFF_AUDIT.md as a documented
  note; not machine-read by any current contract file. Low-priority, but a `workflow_contract_check`
  script would surface it.

### Lifecycle script → file write inventory (Direction B)
`start_task.ps1` confirmed writes:
- `claude/TASK_QUEUE.md` — was missing from `allowed_files.txt` (now fixed)
- `claude/TASK_ACTIVE.md` — was missing from `allowed_files.txt` (now fixed)
- `claude/JOURNAL.md` — present ✓
- `claude/STATE.json` — present ✓

`claude_orchestrate.ps1` writes: `claude/NEXT_ACTION.md` — present ✓
`audit_check.ps1` writes: `claude/verify_last.json` — present ✓
`extract_allowed_files.ps1` writes: `claude/allowed_files.txt` — present ✓

Current `allowed_files.txt` (after TASK-020 fix):
```
claude/templates/NEXT_ACTION_TEMPLATE.md
claude/HANDOFF_ARCHITECT.md
claude/HANDOFF_DEV.md
claude/HANDOFF_AUDIT.md
claude/JOURNAL.md
claude/STATE.json
claude/allowed_files.txt
claude/NEXT_ACTION.md
claude/verify_last.json
claude/TASK_ACTIVE.md
claude/TASK_QUEUE.md
```

### Enforcement gap
- `enforce_allowed_files.ps1` (pre-commit hook) catches Direction B at commit time.
- Nothing catches Direction A (missing referenced scripts) at any automated boundary.
- Nothing catches Direction B before commit time (no CI-level or pre-task check).
- `ci_invariant_check.ps1` (TASK-019 deliverable) does not cover either direction.

## 3) Hypotheses for implementation

**H1 — New script `tools/workflow_contract_check.ps1`:**
Performs both checks:
- Phase A: grep contract source files for `tools/[a-z_]+\.ps1` patterns; assert each
  referenced file exists on disk.
- Phase B: grep lifecycle scripts for `Set-Content`, `Add-Content`, `Out-File`
  patterns targeting `claude/`; assert each matched file appears in `allowed_files.txt`.
Exit 0 if all pass; exit 1 with descriptive error listing each violation.

**H2 — Wire into CI (`ci.yml`):**
Add a step before `ci_invariant_check.ps1`:
```yaml
- name: Workflow contract check
  shell: pwsh
  run: pwsh tools/workflow_contract_check.ps1
```

**H3 — Update `claude/WORKFLOW_SPEC.md`:**
Add a section: "Workflow Contract Integrity" documenting the two drift directions and
the canonical check command.

## 4) Scope constraints
- Do not modify product code (`solo_builder/`).
- New script: `tools/workflow_contract_check.ps1` only.
- Modify: `.github/workflows/ci.yml`, `claude/WORKFLOW_SPEC.md`,
  `claude/allowed_files.txt` (already updated in init commit).
- No changes to `enforce_allowed_files.ps1` or other existing hooks.
- Implementation decisions (exact grep patterns, error format, whether to integrate
  into `workflow_preflight.ps1`) are ARCHITECT decisions, not RESEARCH decisions.
