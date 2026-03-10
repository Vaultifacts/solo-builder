# Prompt Engineering Standard
**TASK-311 | Audit refs: AI-002, AI-003**
Last updated: 2026-03-09

---

## Purpose

This document defines the standard structure for every Claude prompt issued by
Solo Builder. It is the single source of truth for:

- How prompts are assembled today (current state)
- What every prompt must contain (the standard)
- Known gaps and which task will resolve them
- How to add new prompts correctly
- How regression testing works

Changing any prompt-affecting constant without updating `test_prompt_standard.py`
will cause CI to fail. That is the intended behaviour.

---

## Current Prompt Architecture

### The project context prefix

Every SDK prompt is prefixed with `_PROJECT_CONTEXT` from `solo_builder_cli.py:87`:

```
"Context: Solo Builder is a Python terminal CLI that uses six AI agents
(Planner, ShadowAgent, SelfHealer, Executor, Verifier, MetaOptimizer)
and the Anthropic SDK to manage DAG-based software project tasks. "
```

**Purpose:** Prevents "I don't know what X is" responses when a subtask
description references a Solo Builder concept without explaining it.

**Rule:** Must end with a space so concatenation with the description is clean.

---

### Three execution paths (executor.py)

| Path | Runner | Prompt assembled as | Context prepended? |
|---|---|---|---|
| SDK tool-use | `SdkToolRunner.arun()` | `_project_context + description` | ✅ Yes |
| SDK direct | `AnthropicRunner.arun()` | `_project_context + description` | ✅ Yes |
| Claude subprocess | `ClaudeRunner.run()` | `_project_context + description` | ✅ Yes — **resolved d9f96e1** |

The subprocess path is the fallback when the Anthropic SDK is unavailable
or when `CLAUDE_LOCAL=1` is set. Context is prepended at the `pool.submit`
call site in `executor.py` line 213: `self._project_context + st_data.get("description", "")`.

**Decomposition prompts** in `dag_cmds.py` (`add_task` and `add_branch`) also
prepend `self.executor._project_context` before calling the Anthropic API.
AI-002 is fully resolved across all execution paths.

---

### Fallback prompt (empty description)

When a subtask has an empty `description` field, the SDK-direct path uses:

```python
f"You completed subtask '{st_name}' in task '{task_name}'. "
f"Write one concrete sentence describing what was accomplished."
```

This fallback produces generic output. The standard says: **descriptions
must never be empty.** The fallback exists only as a safety net.

---

## Prompt Standard — Required Fields

Every subtask `description` that will be used as a Claude prompt MUST:

| Rule | Rationale |
|---|---|
| Non-empty | The fallback produces low-quality output |
| ≥ 20 characters | Prevents trivially short descriptions |
| ≤ 2,000 characters | Prevents context-window exhaustion on a single subtask |
| End with `.`, `?`, or `!` | Clean sentence boundary; avoids awkward concatenation with context |
| Reference what to produce | e.g. "List 3 …", "Write one paragraph …", "Describe in 2 sentences …" |
| Specify output format/length | Prevents unbounded verbose responses that exceed `ANTHROPIC_MAX_TOKENS` |

---

## Prompt Template

Use this template when writing new subtask descriptions:

```
[Action verb] [specific output] [format constraint].
[Optional: any relevant constraint or scope].
```

**Good examples (from INITIAL_DAG):**
```
List 5 key features a solo developer AI project management tool needs. Bullet points.
Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.
Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.
```

**Bad examples (violate the standard):**
```
Do the thing.                          ← too short, no format spec
Explain Solo Builder.                  ← no output format, no scope
Analyse every aspect of the system and provide a comprehensive report covering all agents, runners, the cache, API, Discord bot, dashboard, and historical performance, with recommendations. ← exceeds 2,000 chars
```

---

## Token Budget Awareness

`ANTHROPIC_MAX_TOKENS` defaults to `300` (settings.json). Descriptions must
request output that fits comfortably within that budget.

**Rule:** If a description requests output likely to exceed 200 tokens (roughly
150 words), either raise `ANTHROPIC_MAX_TOKENS` for that task or split the
subtask into smaller units.

The current default of 300 tokens is intentionally conservative. It is
appropriate for bullet-point and 1–2 sentence responses. It will truncate
multi-paragraph outputs silently.

---

## System Prompt Policy

**Current state:** Solo Builder does not use a `system=` parameter on any
Anthropic SDK call. All role context is carried in the user-turn message via
`_PROJECT_CONTEXT`.

**This is intentional:** The context prefix is short (one sentence), readable,
and stored in one place. Adding a separate system prompt would split the context
across two locations without benefit at the current scale.

**If a system prompt is added in future:** it must be stored as a named constant
(not an inline string), covered by a snapshot test, and this section updated.

---

## Regression Testing

The snapshot tests live in:

```
solo_builder/tests/test_prompt_standard.py
```

Tests check:

| Test class | What it guards |
|---|---|
| `TestProjectContextSnapshot` | `_PROJECT_CONTEXT` exact text + required keywords + trailing space |
| `TestPromptConstruction` | SDK-path assembly, fallback prompt format, subprocess gap documentation |
| `TestPromptSnapshots` | Exact full prompt for known subtasks (A1 and the default fallback) |
| `TestDagDescriptionQuality` | All `INITIAL_DAG` descriptions meet length, non-empty, terminator rules |

**When to update a snapshot:** Any intentional change to `_PROJECT_CONTEXT` or a
DAG description must be accompanied by an update to the relevant `_EXPECTED_*`
constant in the test file. Do not update snapshots silently — the commit message
must explain why the prompt changed and whether quality was verified.

---

## Known Gaps

| Gap ID | Description | Status |
|---|---|---|
| AI-002 | Claude subprocess path does not prepend `_PROJECT_CONTEXT` | **Resolved by d9f96e1** |
| AI-003 | No prompt regression testing before this task | **Resolved by TASK-311** |

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-09 | Initial standard created (TASK-311). Snapshot tests added. Gaps AI-002, AI-003 documented. |
| 2026-03-09 | AI-002 marked resolved (d9f96e1). Executor subprocess path and dag_cmds decomp prompts confirmed to prepend `_PROJECT_CONTEXT`. All 23 regression tests pass. |
