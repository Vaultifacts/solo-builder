# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-016`
- Scope: documentation-only task to add canonical workflow specification.
- Objective: document the deterministic workflow as currently enforced/practiced, without changing behavior.

## Files consulted
- `claude/AGENT_ENTRY.md`
- `claude/CONTROL.md`
- `claude/NEXT_ACTION.md`
- `claude/TASK_QUEUE.md`
- `claude/TASK_ACTIVE.md`
- `claude/JOURNAL.md`
- `claude/STATE.json`
- `claude/STATE_SCHEMA.md`
- `claude/VERIFY.json`
- `tools/claude_orchestrate.ps1`
- `tools/advance_state.ps1`
- `tools/audit_check.ps1`
- `tools/dev_gate.ps1`
- `tools/extract_allowed_files.ps1`
- `tools/precommit_gate.ps1`
- `tools/bootstrap_verify.ps1`
- `tools/install_git_hooks.ps1`
- `.githooks/pre-commit`

## Confirmed workflow rules (script-enforced)

### 1) Role/phase control surface
- `tools/claude_orchestrate.ps1` reads `claude/STATE.json`, validates phase/role enums, validates non-done phase-role mapping, and renders role prompt output.
- `tools/claude_orchestrate.ps1` writes `claude/NEXT_ACTION.md` from state + role contract on each run.
- `tools/advance_state.ps1` mutates `STATE.json` and appends transition entries to `JOURNAL.md`; it enforces phase-role mapping for non-done phases.

### 2) Phase and role model in practice
- Enforced phases: `triage`, `research`, `plan`, `build`, `verify`, `done` (`STATE_SCHEMA.md`, `advance_state.ps1`, `claude_orchestrate.ps1`).
- Enforced roles: `RESEARCH`, `ARCHITECT`, `DEV`, `AUDITOR`.
- Non-done phase mapping enforced by orchestration scripts:
  - `triage -> RESEARCH`
  - `research -> ARCHITECT`
  - `plan/build -> DEV`
  - `verify -> AUDITOR`

### 3) Verification and closeout behavior
- `tools/audit_check.ps1` is the verification runner and writes `claude/verify_last.json`.
- `audit_check.ps1` now includes fail-fast `STATE` vs `NEXT_ACTION` consistency check via `tools/check_next_action_consistency.ps1`.
- `audit_check.ps1` updates `STATE.json`:
  - pass -> `phase=done`
  - fail -> `phase=verify`, increment attempt, `next_role=ARCHITECT`
- Working-tree mutation detection/restoration is enforced in `audit_check.ps1`.

### 4) Dev safety and scope enforcement
- `.githooks/pre-commit` runs `pwsh tools/dev_gate.ps1 -Mode PreCommit` (with powershell fallback).
- `tools/dev_gate.ps1` requires non-empty `claude/allowed_files.txt` and runs guard scripts.
- `tools/extract_allowed_files.ps1` derives allowed files from `claude/HANDOFF_DEV.md`.

### 5) Runtime artifact handling (partially enforced)
- `.gitignore` marks runtime/local artifacts (including `claude/STATE.json`, `claude/NEXT_ACTION.md`, `claude/verify_last.json`, logs/snapshots) as local-only.
- Runtime artifacts are still mutable during normal operation and must be manually restored/ignored in cleanup.

## Confirmed workflow rules (convention-practice from repo history)

### 1) Branch lifecycle
- Merge-first baseline (`task/TASK-XXX` branch merged into `master` before creating next task branch) is not script-enforced; observed as operator convention in recent history and task guidance.

### 2) Closeout cleanup lifecycle
- Standard cleanup pattern appears repeatedly in practice:
  - restore runtime artifacts (`allowed_files.txt`, `verify_last.json`)
  - inspect/commit `JOURNAL.md` if durable history
- This is convention-driven and not fully automated by scripts.

### 3) Commit sequencing discipline
- Fine-grained sequence (init -> research -> architect -> dev -> audit -> journal closeout) is conventionally followed; not hard-enforced by a single script.

## Conventions vs enforcement summary
- Enforced by scripts:
  - phase/role validation and rendering
  - state mutation/update behavior
  - verify runner and verify output
  - dev-gate checks and hook invocation
  - allowed-files extraction gate
- Convention-only:
  - merge-first branch baseline
  - cleanup cadence for runtime artifacts
  - commit granularity and message discipline

## Ambiguities the specification must clarify (without changing behavior)
- Difference between machine source of truth (`STATE.json`) and rendered control artifact (`NEXT_ACTION.md`).
- Which procedures are mandatory script behavior vs operator policy.
- Explicit statement that runtime artifacts are local-only and typically excluded from commits.
- Explicit merge-first baseline rule as required operator discipline (currently not script-enforced).
- Clarify that `JOURNAL.md` can contain both durable transitions and transient test transitions; closeout guidance should state when to commit.

## Risks if spec is vague
- Agents may treat conventions as optional and reintroduce baseline drift.
- Agents may incorrectly commit local runtime artifacts.
- Future chats may infer incorrect lifecycle if mandatory vs advisory rules are not separated.

## Hypotheses (ranked)
- H1: A single canonical `claude/WORKFLOW_SPEC.md` that explicitly separates enforced rules from conventions will reduce workflow drift across chats/agents.
- H2: Most future failures will come from branch baseline and closeout cleanup steps unless these convention rules are explicitly codified.
- H3: No script changes are required for TASK-016; documentation-only implementation can satisfy acceptance criteria.

## Constraints / non-negotiables
- No changes to workflow semantics.
- No changes to orchestrator/state-machine behavior in this task.
- No product-code changes under `solo_builder/*`.
