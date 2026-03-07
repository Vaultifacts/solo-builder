# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-019`
- Goal: design CI integration for Solo Builder workflow invariants (state consistency, preflight checks, verification contract enforcement).
- Scope: workflow infrastructure only; no product-code changes.

## 1) Problem framing
Current workflow invariants are enforced reliably in local scripted flows (`audit_check`, `workflow_preflight`, orchestrator/state contracts), but merge safety still depends on operators manually running those checks before push/merge. CI integration is needed to make invariant verification automatic at integration boundaries (push/PR), so broken workflow-state contracts or guard regressions cannot be merged silently.

## 2) Invariants to protect
Evidence-backed invariants currently present in repo logic:
- `STATE.json` <-> `NEXT_ACTION.md` consistency:
  - enforced by `tools/check_next_action_consistency.ps1` (Task/Phase/Role matching).
  - currently called by both `tools/workflow_preflight.ps1` and `tools/audit_check.ps1`.
- Preflight guarantees before task initialization:
  - `tools/workflow_preflight.ps1` enforces clean tree, runtime artifact cleanliness, state/contract consistency, and conservative baseline ancestry checks.
  - `tools/start_task.ps1` invokes preflight before new task branch creation.
- Verification contract execution:
  - `tools/audit_check.ps1` executes commands from `claude/VERIFY.json`, writes `claude/verify_last.json`, and fails nonzero when required checks fail.
- Deterministic lifecycle integrity:
  - orchestrator and state scripts assume phase/role progression consistency and consume the above checks as safety rails.

## 3) CI execution model options
### Option A: GitHub Actions only (current baseline-ready)
- Repo already contains `.github/workflows/ci.yml` running:
  - `pwsh tools/bootstrap_verify.ps1`
  - `pwsh tools/audit_check.ps1`
- Pros: native PR/push enforcement, lowest operator burden.
- Risk: CI environment differences (Windows vs Linux shell behavior) can surface false negatives if scripts are platform-sensitive.

### Option B: Local CI mirror only
- Rely on local preflight/audit gates without hosted CI enforcement.
- Pros: deterministic local behavior, no external dependency.
- Cons: does not protect against unsafe merges when local discipline slips.

### Option C: Hybrid (recommended direction for ARCHITECT evaluation)
- Keep local scripted gates as developer controls.
- Keep/strengthen hosted CI as merge gate using same invariant checks.
- Pros: strongest defense-in-depth with minimal semantic change.

## 4) Safety constraints for CI (must-hold)
CI must remain verification-only. CI must NOT:
- mutate workflow state (`claude/STATE.json`) as durable repo state,
- run `tools/advance_state.ps1`,
- initialize tasks (`tools/start_task.ps1`),
- create/switch/merge branches.

CI should only execute invariant/verification checks and fail/pass accordingly.

## 5) Existing workflow checks and integration surface
### Files/scripts inspected
- `claude/AGENT_ENTRY.md`
- `claude/CONTROL.md`
- `claude/NEXT_ACTION.md`
- `claude/TASK_QUEUE.md`
- `claude/TASK_ACTIVE.md`
- `claude/VERIFY.json`
- `claude/WORKFLOW_SPEC.md`
- `tools/research_extract.ps1`
- `tools/check_next_action_consistency.ps1`
- `tools/workflow_preflight.ps1`
- `tools/audit_check.ps1`
- `tools/start_task.ps1`
- `.github/workflows/ci.yml`

### Observed current CI behavior
- CI workflow already exists and invokes `bootstrap_verify` then `audit_check` on push/PR.
- This means CI integration is partially present; TASK-019 likely concerns making invariant coverage explicit, stable, and policy-aligned with workflow rules (not introducing product-code testing changes).

## 6) Conventions vs script-enforced behavior (relevant to CI)
Script-enforced today:
- state/contract consistency check command behavior,
- preflight failure conditions,
- verification command execution from `VERIFY.json`.

Convention-driven today:
- operator interpretation of which checks are required for merge readiness,
- explicit CI policy language tying workflow invariants to merge gates.

## 7) Risks and edge cases
- `audit_check.ps1` updates local state artifacts (`STATE.json`, `verify_last.json`) as part of its local workflow contract; CI usage must avoid treating those writes as semantic lifecycle transitions.
- Cross-platform shell differences can affect git/status parsing and path handling.
- If CI and local `VERIFY.json` contract diverge over time, developers may get pass locally/fail in CI drift.

## 8) Research hypotheses for ARCHITECT to evaluate
- H1: Reusing existing invariant scripts (`check_next_action_consistency`, `workflow_preflight`, `audit_check`) is the minimal-risk path; avoid new checker duplication.
- H2: CI should enforce invariant checks at PR/push while preserving local deterministic role lifecycle semantics.
- H3: The correct design boundary is to keep CI verification-only and explicitly prohibit lifecycle-mutating workflow actions in CI.
- H4: A small workflow-doc and CI-contract alignment change can close current convention gaps without changing orchestration/state semantics.

## 9) Recommended high-level direction (research-level)
Architect should design a minimal CI contract alignment that:
- uses existing scripts as primary check engines,
- codifies verification-only CI behavior,
- ensures invariant checks are explicit and reproducible in CI and local runs,
- preserves current deterministic lifecycle semantics unchanged.

## Non-goals (for TASK-019)
- No product-code changes under `solo_builder/*`.
- No role-mapping or lifecycle semantic changes.
- No automatic state advancement in CI.
