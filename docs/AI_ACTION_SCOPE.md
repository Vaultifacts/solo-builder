# AI Action Scope Enforcement Design
**TASK-313 | Audit ref: AI-033**
Last updated: 2026-03-10

---

## Purpose

This document defines the allowed tool set for each Solo Builder task type and
the enforcement mechanism that prevents Claude from receiving broader permissions
than the task requires.

This is the companion to `HITL_TRIGGER_DESIGN.md` (TASK-312):
- HITL design answers: *when does a human need to approve?*
- This document answers: *what tools may Claude use at all?*

Changing `_TOOL_POLICY` in `hitl_gate.py` without updating this document and
adding a regression test is a process violation.

---

## Principle

**Least privilege per execution path.** Each subtask declares the tools it
needs. The system grants exactly those tools and no others. Tools not in the
declared set are never available to Claude for that execution, regardless of
what Claude might request.

---

## Execution Paths and Tool Exposure

| Path | Triggered when | Tools available | Risk |
|---|---|---|---|
| `SdkToolRunner` | `st_tools` non-empty + SDK tool-use available | Explicitly declared tools only — schema hard-coded to Read/Glob/Grep | Low |
| `AnthropicRunner` (direct) | No tools + Anthropic SDK available | None — pure text generation | None |
| `ClaudeRunner` (subprocess) | `st_tools` non-empty + SDK unavailable | `--allowedTools` list — whatever is declared | Medium |
| Decomp prompts (`dag_cmds`) | `add_task` / `add_branch` | None — routes via `ClaudeRunner.run()` with no tools | None |

The primary enforcement point is the `st_tools` field on each subtask. If a
subtask declares `"tools": "Bash,Write"`, the system grants both. The policy
table below constrains what may be declared.

---

## Allowed Tool Sets

### Registered SDK tools (hard limit)

`SdkToolRunner._SCHEMAS` defines the only tools available via the SDK tool-use
path. As of TASK-313:

| Tool | Operations | Scope |
|---|---|---|
| `Read` | Read file at path | Repo root and below |
| `Glob` | Pattern match file paths | Repo root and below |
| `Grep` | Search file content | Repo root and below |

These three are the **only tools the SDK path will ever execute**. Adding a
new tool to `_SCHEMAS` requires a separate task and security review.

### Declared tool policy per task type

| Task type | Allowed declared tools | Rationale |
|---|---|---|
| Analysis / summarise | `Read`, `Glob`, `Grep` | Read-only; no side-effects |
| Code search | `Read`, `Glob`, `Grep` | Read-only |
| Documentation generation | *(none)* | Pure text; no file access needed |
| Decomposition (`add_task`, `add_branch`) | *(none)* | JSON generation only |
| File write / edit | *(not permitted autonomously)* | Requires HITL Pause (level 2) |
| Shell / Bash execution | *(not permitted autonomously)* | Requires HITL Pause (level 2) |
| Web fetch / search | *(not permitted autonomously)* | Requires HITL Notify (level 1) |

**Rule:** Any subtask in `INITIAL_DAG` or added via `add_task`/`add_branch`
that declares tools outside the "Analysis / Code search" row must have a
corresponding HITL gate decision documented before execution.

---

## `hitl_gate.py` — Runtime Enforcement

`solo_builder/runners/hitl_gate.py` implements the evaluation function used by
`Executor` before dispatching each job.

### API

```python
def evaluate(tools: str, description: str) -> int:
    """Return the minimum HITL level for this operation.

    0 = Auto (proceed)
    1 = Notify (log + proceed)
    2 = Pause (await human confirmation)
    3 = Block (reject)

    Parameters
    ----------
    tools       : comma-separated tool list from the subtask "tools" field
    description : the subtask description (used to detect dangerous keywords)
    """

class HITLBlockError(RuntimeError):
    """Raised when evaluate() returns 3."""
```

### Evaluation rules (in priority order)

| Priority | Condition | Level |
|---|---|---|
| 1 | `Bash` in tools | 2 — Pause |
| 2 | `Write` or `Edit` in tools | 2 — Pause |
| 3 | `WebFetch` or `WebSearch` in tools | 1 — Notify |
| 4 | Description contains `delete`, `drop`, `purge`, `rm -rf` | 2 — Pause |
| 5 | Description contains path starting with `..` or outside repo | 2 — Pause |
| 6 | No tools, or tools ⊆ {Read, Glob, Grep} | 0 — Auto |

Rules are evaluated top-to-bottom; first match wins.

---

## Integration Points

### `Executor.execute_step()`

```python
# Before dispatching any claude_jobs or sdk_tool_jobs:
from .hitl_gate import evaluate, HITLBlockError

level = evaluate(st_tools, description)
if level >= 2:
    # Pause: print pending action and wait
    confirm = input(f"  [HITL] Allow '{st_name}' with tools={st_tools!r}? [y/N] ")
    if confirm.strip().lower() != "y":
        raise HITLBlockError(f"Blocked by HITL gate: {st_name}")
elif level == 1:
    logger.info("hitl_notify subtask=%s tools=%s", st_name, st_tools)
```

This integration is **Phase 3** — not yet wired into executor.py. The
`hitl_gate.py` module is present and tested; calling it at the executor
dispatch site is the remaining step.

---

## Known Runtime Behaviour — Silent No-Op on Unknown Tools

**Important:** `SdkToolRunner` filters declared tools against `_SCHEMAS` at
dispatch time. If a subtask declares tools not in `_SCHEMAS` (e.g. `"Bash,Write"`),
the schema list becomes empty and the call proceeds as a no-tool API call.
No error is raised. This means the policy table above is **not enforced at
runtime** for the SDK path — it is a design contract only.

**Fix (tracked as TD-ARCH-005):** Add `validate_tools(tools_str)` at
subtask-creation time to reject unknown tool names before they reach the executor.

---

## What Is NOT in Scope

- Tool schemas for `Write`, `Edit`, `Bash` — these are not registered in
  `SdkToolRunner._SCHEMAS` and will not be added without a separate security
  review task.
- Per-user permission profiles — Solo Builder is single-user; no ACL needed.
- Network egress controls — out of scope for the current architecture.

---

## Known Gaps

| Gap ID | Description | Status |
|---|---|---|
| AI-033 | No tool permission scoping per task type | **Resolved by TASK-313** |
| AI-032 | `hitl_gate.py` not yet wired into executor dispatch | Open — Phase 3 of HITL design |

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial design document (TASK-313). Tool policy table defined. `hitl_gate.py` created. AI-033 resolved. |
