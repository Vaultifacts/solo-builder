# Human-in-the-Loop Trigger Design
**TASK-312 | Audit refs: AI-026, AI-032**
Last updated: 2026-03-10

---

## Purpose

This document defines the formal criteria for when Solo Builder must pause and
require human approval before proceeding. It replaces the current practice of
running with `--dangerouslySkipPermissions` (or equivalent unconditional tool
grant) with a structured decision model.

Changing any HITL trigger without updating this document and the relevant test
coverage is a process violation.

---

## Current State

Solo Builder's `ClaudeRunner` launches `claude -p <prompt> --output-format json`
with an optional `--allowedTools` list. No mechanism currently:

- Pauses execution before a destructive or irreversible action
- Requests human sign-off for high-risk subtask types
- Distinguishes between read-only and write/execute tool grants

The audit findings AI-026 and AI-032 flag this as a gap: the system operates in
a mode where Claude can use any permitted tool without a human checkpoint, even
for operations outside the intended task scope.

---

## HITL Trigger Model

### Trigger levels

| Level | Name | Meaning |
|---|---|---|
| 0 | Auto | Proceed without human input. Safe for read-only, idempotent, or reversible operations. |
| 1 | Notify | Log the action and continue. Human reviews asynchronously (e.g. via Discord or journal). |
| 2 | Pause | Halt execution. Print the pending action. Resume only after explicit `y` confirmation. |
| 3 | Block | Reject the action entirely. Require the user to re-scope the task before retrying. |

### Trigger criteria

The following conditions determine the minimum level required before execution:

| Condition | Minimum Level | Rationale |
|---|---|---|
| Tool list contains `Bash` | 2 — Pause | Shell execution can have unbounded side-effects |
| Tool list contains `Write` or `Edit` | 1 — Notify | File mutations are reversible via git but affect workspace |
| Tool list contains `WebFetch` or `WebSearch` | 1 — Notify | External network calls; data exfiltration risk |
| Description contains file path outside repo root | 2 — Pause | Out-of-scope path traversal |
| Description requests deletion, drop, or purge | 2 — Pause | Irreversible data loss |
| Task type is `force-push`, `branch -D`, `reset --hard` | 3 — Block | Destructive git operations forbidden without explicit user instruction |
| Subtask runs in `CLAUDE_LOCAL=1` mode with no allowed tools | 0 — Auto | Pure text generation; no file system access |
| No tool list (SDK direct or SDK tool-use with Read/Glob/Grep only) | 0 — Auto | Read-only operations; no side-effects |

---

## Implementation Plan

### Phase 1 — Criteria document (this file)

Define the model. No code changes yet. Establishes the shared vocabulary and
decision table that Phase 2 will implement.

### Phase 2 — `hitl_gate.py` (future task)

Create `solo_builder/runners/hitl_gate.py` with:

```python
def evaluate(tools: str, description: str, mode: str = "auto") -> int:
    """Return the minimum HITL level required for this operation.

    0 = Auto, 1 = Notify, 2 = Pause, 3 = Block
    """
```

Called by `Executor.execute_step()` before dispatching any `claude_jobs` or
`sdk_tool_jobs` entry. If the returned level is:
- 0: proceed immediately
- 1: log to journal and proceed
- 2: print pending action, wait for `input("Approve? [y/N] ")`
- 3: raise `HITLBlockError` with a message explaining why the action is blocked

### Phase 3 — Replace `--dangerouslySkipPermissions` in CI / orchestration scripts

Audit every script that passes `--dangerouslySkipPermissions` to `claude`:

| Location | Current | Replacement |
|---|---|---|
| `ClaudeRunner` (headless) | No flag (uses `--allowedTools`) | Add HITL gate before dispatch |
| `claude_orchestrate.ps1` | Review for any skip-permissions usage | Use explicit `--allowedTools` list |
| Any CI workflow `.yml` | Review for skip-permissions | Require explicit tool scope per step |

---

## Scope Constraints

The following operations are **permanently out of scope** for autonomous execution
regardless of HITL level — they require a human to initiate explicitly:

1. `git push` to any remote
2. `git reset --hard` on uncommitted work
3. `rm -rf` or equivalent recursive delete outside `generated/` or `tmp/`
4. Any operation that modifies `.git/hooks/` or CI pipeline files
5. Any operation that writes to `~/.claude/` or global config paths
6. Any Notion write that modifies Layer 1 deliverable status

---

## Relationship to Existing Safety Mechanisms

| Mechanism | Gap it addresses | HITL interaction |
|---|---|---|
| `--allowedTools` list | Limits which tools Claude can call | HITL gate fires before tools are granted |
| `new_file_guard.ps1` | Blocks new staged files without override | Complementary — HITL at runtime, gate at commit |
| `enforce_allowed_files.ps1` | Restricts files in commit scope | Complementary — post-hoc check |
| `secret_scan.ps1` | Prevents secrets in commits | Complementary — HITL does not replace secret scan |
| `ANTHROPIC_MAX_TOKENS = 300` | Limits output length | Orthogonal — budget control only |

---

## Known Gaps (not addressed by this document)

| Gap ID | Description | Status |
|---|---|---|
| AI-026 | No formal HITL trigger criteria | **Resolved by TASK-312 (Phase 1)** |
| AI-032 | `--dangerouslySkipPermissions` used without criteria | **Partially resolved — criteria defined; code gate is Phase 2** |
| AI-033 | No tool permission scoping per task type | Open — addressed by AIActionScopeEnforcementDesign |

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial design document (TASK-312). HITL trigger levels and criteria table defined. Phase 2/3 plan documented. AI-026 resolved, AI-032 partially resolved. |
