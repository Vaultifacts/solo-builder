# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-017`
- Objective: define the smallest safe way to add `tools/workflow_preflight.ps1` as a baseline-safety gate before next-task initialization.
- Scope: workflow-only (no product code).

## Files consulted
- `claude/AGENT_ENTRY.md`
- `claude/CONTROL.md`
- `claude/NEXT_ACTION.md`
- `claude/WORKFLOW_SPEC.md`
- `claude/TASK_ACTIVE.md`
- `claude/STATE.json`
- `tools/research_extract.ps1`
- `tools/check_next_action_consistency.ps1`
- `tools/audit_check.ps1`
- `tools/claude_orchestrate.ps1`
- `tools/advance_state.ps1`
- tool inventory via `Get-ChildItem tools -File`

## Existing reusable checks (already available)
1. STATE/NEXT_ACTION consistency check
- Existing script: `tools/check_next_action_consistency.ps1`
- Current behavior:
  - Parses stable sections from `claude/NEXT_ACTION.md`: `## Task`, `## Phase`, `## Role`
  - Compares to `claude/STATE.json` fields: `task_id`, `phase`, `next_role`
  - Exits nonzero on mismatch with explicit mismatch lines
- Reuse value: avoids duplicating parsing/consistency logic in preflight.

2. Working-tree tracked-change detection logic
- Existing implementation pattern appears in `tools/audit_check.ps1` (`Get-TrackedChangedPaths` via `git status --porcelain`).
- Reuse value: deterministic detection of modified tracked files.

3. Orchestrator/state invariants
- `tools/claude_orchestrate.ps1` enforces valid phase/role enums and non-done mapping.
- `tools/advance_state.ps1` mutates state and journal using same model.
- Reuse value: preflight should validate baseline safety only, not redefine lifecycle semantics.

## Missing checks (gap TASK-017 must cover)
No current dedicated pre-task-init guard exists that simultaneously verifies:
- clean working tree baseline,
- runtime-artifact cleanliness for `claude/allowed_files.txt` and `claude/verify_last.json`,
- STATE/NEXT_ACTION consistency,
- branch baseline safety against `master`.

## Deterministic detection requirements

### A) Dirty working tree
Deterministic source:
- `git status --porcelain`
- fail if any tracked or untracked entries exist (for strict pre-init safety), or fail at minimum for tracked changes.

Risk note:
- If untracked files are ignored, init can still proceed with hidden clutter; strict fail is safer for deterministic workflow.

### B) Runtime artifact dirtiness
Required artifacts (explicit in task acceptance):
- `claude/allowed_files.txt`
- `claude/verify_last.json`

Deterministic checks:
- if artifact exists and appears in `git status --porcelain` as modified/staged/deleted, fail.
- if artifact is absent and untracked (common when gitignored), do not fail by absence alone.

### C) STATE/NEXT_ACTION mismatch
Deterministic method:
- invoke `tools/check_next_action_consistency.ps1`
- fail preflight if helper exits nonzero.

### D) Safe baseline (master contains previous task branch)
Observed convention from workflow history/spec:
- new task branches must start from updated `master` that already includes previous task branch.

Deterministic evaluation shape (minimal and practical):
- Resolve current branch via `git branch --show-current`.
- If on `master` for pre-init: pass merge check branch-specific condition (baseline branch itself).
- If on `task/TASK-NNN`:
  - derive previous branch by decrementing numeric suffix to `task/TASK-(NNN-1)` when it exists.
  - verify previous branch is contained in `master` using `git branch --contains <prev-branch-tip> master` or merge-base ancestry check.
  - fail if previous branch exists but is not merged into master.

Research caveat:
- branch numbers are not fully contiguous historically (`TASK-010` exists but older low numbers were not all branch-created), so the check should be conservative:
  - only enforce when derived previous branch exists locally.
  - if it does not exist, emit informative warning/pass behavior per architect decision.

## Suggested minimal integration surface
- New script: `tools/workflow_preflight.ps1` (single entry point).
- Reuse helper: `tools/check_next_action_consistency.ps1` (invoke directly).
- No mandatory changes required to `tools/audit_check.ps1` or `tools/claude_orchestrate.ps1` for this task’s core objective.

## Edge cases to handle explicitly in spec/plan
1. Running preflight from `master` vs from a task branch.
2. Missing runtime artifact files (gitignored not yet generated).
3. Non-contiguous task numbers and missing local `task/TASK-(N-1)` branches.
4. Detached HEAD or non-task branch names.
5. Repositories without upstream configured for `master` (preflight should not require network).

## Failure messaging requirements (actionable)
Messages should clearly identify:
- exact failing check,
- exact file/branch mismatch,
- one-line remediation (e.g., restore runtime artifacts, merge previous task branch into master, regenerate NEXT_ACTION via orchestrator).

## Risks
- Overly strict branch inference can block valid flows in non-contiguous branch histories.
- Coupling to branch naming assumptions must remain bounded to `task/TASK-<number>` pattern.
- Duplicating existing helper logic would increase drift risk; delegation is safer.

## Hypotheses (ranked)
- H1: A single preflight script that delegates STATE/NEXT_ACTION consistency to existing helper and performs explicit baseline checks will satisfy TASK-017 with minimal blast radius.
- H2: The highest regression risk is branch-baseline inference, not working-tree or runtime-artifact checks.
- H3: No product or lifecycle semantic changes are needed; this is a guardrail addition only.

## Constraints / non-negotiables
- No changes under `solo_builder/*`.
- No task lifecycle semantic changes.
- Preserve deterministic workflow conventions.
- Keep implementation scope to workflow scripts/docs only.
