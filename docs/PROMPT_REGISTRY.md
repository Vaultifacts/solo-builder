# Prompt Registry
**TASK-321 | Audit ref: AI-004, AI-005**
Last updated: 2026-03-10

---

## Purpose

This registry captures the canonical text of every prompt template used by Solo Builder.
Each entry includes a stable identifier, the source location, and a SHA-256 hash of the
template body (whitespace-normalised). The hashes are also checked by
`solo_builder/tests/test_prompt_registry.py` as a regression guard.

A hash change requires updating **both** this file and the corresponding entry in
`test_prompt_registry.py`. That two-step requirement ensures prompt changes are
intentional and documented.

---

## Templates

### PROMPT-001 — Project Context Prefix
**Source:** `solo_builder/solo_builder_cli.py:87` (`_PROJECT_CONTEXT`)
**Applied by:** All three execution paths (SDK direct, SDK tool-use, subprocess) — prepended to every prompt.

```
Context: Solo Builder is a Python terminal CLI that uses six AI agents (Planner,
ShadowAgent, SelfHealer, Executor, Verifier, MetaOptimizer) and the Anthropic SDK
to manage DAG-based software project tasks.
```

**Hash:** `sha256:b50fef6cbf1ce0485e13157f9be83f09639fe2f09dfb322de01cd2fef630ee00`

---

### PROMPT-002 — SDK Direct Fallback
**Source:** `solo_builder/runners/executor.py:199` (`raw_prompt` fallback)
**Applied by:** `execute_step()` SDK direct path when subtask has no description.

```
You completed subtask '{st_name}' in task '{task_name}'. Write one concrete sentence
describing what was accomplished.
```

**Hash:** `sha256:1d2d6e658297d0dbebcd9329d02d08fcff249eb3bf0f72a89b949f7d2a352fc3`

---

### PROMPT-003 — Task Decomposition (add_task)
**Source:** `solo_builder/commands/dag_cmds.py:74` (`decomp_prompt` in `add_task`)
**Applied by:** `DagCmds.add_task()` via `ClaudeRunner.run()`.

```
{_PROJECT_CONTEXT}Break this task into 2-5 concrete subtasks for a solo developer AI
project.

Task: {spec}

Reply with a JSON array only — no explanation, no markdown fences:
[{"name": "{letter}1", "description": "actionable prompt"}, ...]

Rules:
- name: uppercase letter '{letter}' + digit, e.g. {letter}1 {letter}2 {letter}3
- description: a self-contained question or instruction Claude can answer headlessly
- 2 to 5 items
```

**Hash:** `sha256:4a7e2dda2984658fc63af21acfa2f5e6e258497a3246d2749fb2a1aabdedcfab`

---

### PROMPT-004 — Branch Decomposition (add_branch)
**Source:** `solo_builder/commands/dag_cmds.py:193` (`decomp_prompt` in `add_branch`)
**Applied by:** `DagCmds.add_branch()` via `ClaudeRunner.run()`.

```
{_PROJECT_CONTEXT}Break this concern into 2-4 concrete subtasks for a solo developer
project.

Concern: {spec}

Reply with a JSON array only — no explanation, no markdown fences:
[{"name": "{branch_letter}1", "description": "actionable prompt"}, ...]

Rules:
- name: uppercase '{branch_letter}' + digit, e.g. {branch_letter}1 {branch_letter}2
- description: self-contained question or instruction Claude can answer headlessly
- 2 to 4 items
```

**Hash:** `sha256:bd0fd460b3a775acc9e43337c12b772adfcf3723820923602d0e1c810d6c9fd4`

---

## Hash Update Process

When a prompt template is intentionally changed:

1. Recompute the hash:
   ```python
   import hashlib, re
   text = "...template body..."
   normalised = re.sub(r'\s+', ' ', text).strip()
   print(hashlib.sha256(normalised.encode()).hexdigest())
   ```
2. Update the hash in this file.
3. Update the expected hash in `solo_builder/tests/test_prompt_registry.py`.
4. Commit both changes together with a message explaining why the prompt changed.

Changing a hash in only one location will fail the regression test.

---

## Known Gaps

| Gap ID | Description | Status |
|---|---|---|
| AI-004 | No prompt version control | **Resolved by TASK-321** |
| AI-005 | No prompt change detection | **Resolved by TASK-321** |

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial registry (TASK-321). 4 templates catalogued, hashes computed. AI-004 and AI-005 resolved. |
