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

### TD-OPS-001 — No executor metrics instrumentation
**Priority:** Medium | **Added:** 2026-03-10

SLO-003 (SDK success rate) and SLO-005 (step latency) cannot be measured
because `executor.py` emits no structured metrics. Only human-readable
`print()` output exists.

**Impact:** SLOs defined but not measurable.

**Resolution path:** Add timing and outcome counters to `execute_step()`;
write to a JSON metrics log after each session. Estimated scope: Small.

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
| TD-ARCH-002 | hitl_gate.py not wired into executor dispatch | TASK-318 |
| TD-ARCH-003 | Subprocess ClaudeRunner as unreliable fallback — now warns | TASK-318 |
| TD-ARCH-005 | Unknown tool names silently no-op in SdkToolRunner | TASK-318 |
| TD-SEC-001 | No path allowlist on Read tool | TASK-318 |
| TD-SEC-002 | No dependency lockfile for tools/ | TASK-318 |
| TD-TEST-001 | No integration tests for executor routing logic | TASK-318 |
| TD-TEST-002 | No tests for hitl_gate.py | TASK-317 |
| TD-DEP-001 | anthropic SDK version unpinned in solo_builder/ | TASK-318 |

---

## Debt Summary

| Category | Open items | High priority |
|---|---|---|
| TD-ARCH | 1 | 0 |
| TD-TEST | 0 | 0 |
| TD-SEC | 0 | 0 |
| TD-OPS | 1 | 0 |
| TD-DEP | 0 | 0 |
| **Total** | **2** | **0** |

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
| 2026-03-10 | TASK-318: Resolved 8 items — TD-ARCH-002/003/005, TD-SEC-001/002, TD-TEST-001/002, TD-DEP-001. 2 open items remain. |
