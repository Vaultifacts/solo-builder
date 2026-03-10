# Technical Debt Register
**TASK-317 | Audit ref: ME-003**
Last updated: 2026-03-10

---

## Purpose

This register makes technical debt visible and manageable. Every known debt
item has an owner (the project), a priority, and a resolution path. Debt that
is not recorded tends to compound silently.

Debt is categorised by type and prioritised by the product of likelihood of
it causing a problem and the cost of fixing it later vs. now.

---

## Debt Categories

| Code | Category |
|---|---|
| TD-ARCH | Architectural debt — structural decisions that limit extensibility |
| TD-TEST | Test coverage gaps — missing tests for known behaviours |
| TD-SEC | Security debt — known risks not yet mitigated |
| TD-OPS | Operational debt — observability, tooling, process gaps |
| TD-DEP | Dependency debt — outdated or unpinned dependencies |
| TD-DOC | Documentation debt — missing or stale docs |

---

## Active Debt Items

### TD-ARCH-001 — `solo_builder_cli.py` god file
**Priority:** Medium | **Added:** 2026-03-10

`solo_builder_cli.py` is ~665 lines and acts as the application entry point,
config loader, mixin host, and CLI dispatcher simultaneously. It contains
five globals (`_PDF_OK`, `_CFG_PATH`, `STATE_PATH`, `JOURNAL_PATH`,
`WEBHOOK_URL`) that must remain there for test patching to work.

**Impact:** Hard to extend; test patches are brittle; onboarding cost high.

**Resolution path:** Extract config loading to `solo_builder/config/loader.py`;
move CLI dispatch to `commands/dispatcher.py` (already partially exists).
Estimated scope: Medium. Prerequisite: update all test patches.

---

### TD-ARCH-002 — `hitl_gate.py` not wired into executor dispatch
**Priority:** High | **Added:** 2026-03-10

`hitl_gate.py` exists and is tested, but `executor.py` does not call
`evaluate()` before dispatching jobs. The HITL gate is inert.

**Impact:** T-003 (unscoped tool grant) residual risk remains.

**Resolution path:** Phase 3 of HITL design — call `evaluate(st_tools, description)`
in `Executor.execute_step()` before each `claude_jobs`/`sdk_tool_jobs` dispatch.
Estimated scope: Small (10–15 lines). Tracked: AI-032.

---

### TD-ARCH-003 — Subprocess `ClaudeRunner` as unreliable fallback
**Priority:** Low | **Added:** 2026-03-10

`ClaudeRunner` (the `claude -p` subprocess) is used as a fallback when the
Anthropic SDK is unavailable. It depends on a local `claude` CLI installation
and returns unstructured JSON. It's slower, less reliable, and harder to test
than the SDK path.

**Impact:** Inconsistent behaviour when SDK is unavailable; harder to mock in tests.

**Resolution path:** Make the SDK path the only supported path; demote
`ClaudeRunner` to a clearly-labelled "local development override" with a
warning. Estimated scope: Small.

---

### TD-TEST-001 — No integration tests for executor routing logic
**Priority:** Medium | **Added:** 2026-03-10

`executor.py` routing (which path fires for which subtask type) is not tested
end-to-end. Tests mock the runners but don't verify that the correct runner
receives the correct prompt under each condition.

**Impact:** A routing regression (e.g., SDK path falling through to subprocess
silently) would not be caught by CI.

**Resolution path:** Add `TestExecutorRouting` class to `test_runners.py` with
mocked runners; verify prompt content and runner selection for each path.
Estimated scope: Small–Medium.

---

### TD-TEST-002 — No tests for `hitl_gate.py`
**Priority:** High | **Added:** 2026-03-10

`hitl_gate.py` has no test file. The evaluation rules are untested.

**Impact:** Rule regressions (wrong level returned) are invisible.

**Resolution path:** Create `solo_builder/tests/test_hitl_gate.py` covering all
6 evaluation rules plus boundary cases. Estimated scope: Small.

---

### TD-SEC-001 — No path allowlist on `Read` tool
**Priority:** Medium | **Added:** 2026-03-10

`SdkToolRunner` exposes a `Read` tool with no path validation. Claude could
read any file accessible to the process (e.g., `.env`, `~/.ssh/id_rsa` if
paths allow).

**Impact:** T-005 residual risk — key exfiltration via Read tool.

**Resolution path:** Add path validation in `SdkToolRunner._handle_read()` to
restrict reads to `repo_root` and below. Estimated scope: Small.

---

### TD-SEC-002 — No dependency lockfile
**Priority:** Medium | **Added:** 2026-03-10

`requirements.txt` uses `>=` version constraints. `pip install` may install
a newer version with vulnerabilities.

**Impact:** T-006 (supply chain) residual risk.

**Resolution path:** Run `pip freeze > requirements-lock.txt` and add it to
`allowed_files.txt`. Pin to exact versions for reproducibility. Estimated scope: Trivial.

---

### TD-OPS-001 — No executor metrics instrumentation
**Priority:** Medium | **Added:** 2026-03-10

SLO-003 (SDK success rate) and SLO-005 (step latency) cannot be measured
because `executor.py` emits no structured metrics. Only human-readable
`print()` output exists.

**Impact:** SLOs defined but not measurable.

**Resolution path:** Add timing and outcome counters to `execute_step()`;
write to a JSON metrics log after each session. Estimated scope: Small.

---

### TD-DEP-001 — `anthropic` SDK version unpinned
**Priority:** Low | **Added:** 2026-03-10

`solo_builder/` has no `requirements.txt` (only `tools/requirements.txt`
exists). The `anthropic` SDK version in use is whatever `pip install anthropic`
resolved at install time.

**Impact:** Silent API behaviour changes on SDK upgrades.

**Resolution path:** Add `solo_builder/requirements.txt` pinning `anthropic>=0.x`.
Estimated scope: Trivial.

---

## Resolved Debt

| ID | Description | Resolved in |
|---|---|---|
| TD-DOC-001 | No prompt engineering standard | TASK-311 |
| TD-DOC-002 | No HITL trigger criteria | TASK-312 |
| TD-DOC-003 | No tool scope design | TASK-313 |
| TD-DOC-004 | No threat model | TASK-314 |
| TD-DOC-005 | No SLO definitions | TASK-315 |
| TD-DOC-006 | No context window strategy | TASK-316 |
| TD-ARCH-004 | AI-002: subprocess path missing project context | TASK-312 |

---

## Debt Summary

| Category | Open items | High priority |
|---|---|---|
| TD-ARCH | 3 | 1 (hitl_gate not wired) |
| TD-TEST | 2 | 1 (hitl_gate tests missing) |
| TD-SEC | 2 | 0 |
| TD-OPS | 1 | 0 |
| TD-DEP | 1 | 0 |
| **Total** | **9** | **2** |

---

## Process

- This register is updated when new debt is identified (during task work or audit).
- Resolved items move to the Resolved section with the task that fixed them.
- Priority is reviewed at the start of each Layer 3 task cycle.

---

## Known Gaps

| Gap ID | Description | Status |
|---|---|---|
| ME-003 | No technical debt register | **Resolved by TASK-317** |

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial register (TASK-317). 9 open items across 5 categories. ME-003 resolved. |
