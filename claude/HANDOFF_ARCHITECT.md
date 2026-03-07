# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-018`
- Goal: integrate preflight into task initialization so it runs automatically (not optional/manual).
- Scope: workflow scripts/docs only.

## Files/scripts inspected
- `claude/AGENT_ENTRY.md`
- `claude/CONTROL.md`
- `claude/NEXT_ACTION.md`
- `claude/WORKFLOW_SPEC.md`
- `claude/TASK_QUEUE.md`
- `claude/TASK_ACTIVE.md`
- `claude/STATE.json`
- `tools/research_extract.ps1`
- `tools/workflow_preflight.ps1`
- `tools/check_next_action_consistency.ps1`
- `tools/claude_orchestrate.ps1`
- `tools/advance_state.ps1`
- `tools/task_lock.ps1`

## Current task initialization flow (as practiced)
1. Verify clean repo.
2. Checkout `master` and merge previous task branch.
3. (Currently manual) run `pwsh tools/workflow_preflight.ps1`.
4. Create next `task/TASK-<N>` branch.
5. Update workflow metadata (`TASK_QUEUE`, `TASK_ACTIVE`, local `STATE.json`, `JOURNAL`).
6. Run `pwsh tools/claude_orchestrate.ps1`.
7. Commit initialization metadata.

## Existing checks available
- `tools/workflow_preflight.ps1` already enforces:
  - clean working tree
  - runtime artifact cleanliness (`claude/allowed_files.txt`, `claude/verify_last.json`)
  - STATE/NEXT_ACTION consistency (delegated to `tools/check_next_action_consistency.ps1`)
  - conservative master-baseline ancestry rule
- `tools/claude_orchestrate.ps1` renders role prompts/contracts but does not perform task-creation side effects.
- No dedicated `start_task`/`init_task` script exists in `tools/`.

## Candidate integration points

### Option A (recommended): add a dedicated initialization script entry point
- Introduce a single workflow script for task bootstrap (for example `tools/start_task.ps1`) that performs the deterministic init sequence and *always* calls `workflow_preflight.ps1` after switching to `master` and before creating the new task branch.
- Pros:
  - true automatic enforcement
  - deterministic sequence encoded in one place
  - easy to audit and reuse across chats/agents
- Risk:
  - new script must be narrowly scoped to avoid semantic drift.

### Option B: enforce via orchestrator prompt/contracts only
- Update done-phase ARCHITECT prompt text to include preflight command before branch creation.
- Pros:
  - minimal code touch
- Cons:
  - still operator/agent optional; not true automatic enforcement
  - does not satisfy strong interpretation of “runs automatically”.

### Option C: embed preflight in existing unrelated scripts
- Add preflight execution to `claude_orchestrate.ps1` or `advance_state.ps1`.
- Cons:
  - mixes concerns (state rendering/transition vs branch bootstrap)
  - higher regression risk to lifecycle semantics.

## Recommended approach (high-level)
- Prefer Option A: create a dedicated initialization workflow script that owns task bootstrap and invokes preflight at the required point.
- Keep orchestration/state semantics unchanged; do not alter role mapping/transition logic.
- Optionally update docs/prompts to direct operators to the new script as canonical initialization path.

## Integration requirements to preserve
- Preflight invocation order must be fixed:
  - checkout/update `master` -> run preflight -> create `task/TASK-<N>`.
- Initialization must abort immediately on nonzero preflight exit.
- No product-code changes under `solo_builder/*`.
- Deterministic lifecycle remains unchanged.

## Edge cases and risks
- Existing branch `task/TASK-<N>` already exists: initializer should fail cleanly with actionable message.
- Missing upstream on `master`: init flow should not require network; pull remains optional.
- Non-contiguous task numbering: baseline check remains conservative via existing preflight behavior.
- Worktree dirtiness from expected runtime artifacts: should still block init unless resolved.

## Hypotheses
- H1: Encoding init flow in one script is the smallest path to *automatic* preflight enforcement.
- H2: Prompt-only enforcement is insufficient for acceptance criteria requiring automatic execution.
- H3: Minimal script + docs update will satisfy task with low regression risk.

## Constraints / non-negotiables
- No lifecycle semantic changes.
- No role transition changes.
- No product-code modifications.
- Keep implementation scope narrow and deterministic.
