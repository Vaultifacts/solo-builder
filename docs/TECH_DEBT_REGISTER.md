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
| TD-SEC-003 | API `@after_request` hook missing HSTS header | TASK-322 |
| TD-TEST-001 | No integration tests for executor routing logic | TASK-318 |
| TD-TEST-003 | No end-to-end Flask test-client assertions for security headers | TASK-323 |
| TD-TEST-002 | No tests for hitl_gate.py | TASK-317 |
| TD-DEP-001 | anthropic SDK version unpinned in solo_builder/ | TASK-318 |
| TD-OPS-001 | No executor metrics instrumentation | TASK-319 |

---

## Debt Summary

| Category | Open items | High priority |
|---|---|---|
| TD-ARCH | 1 | 0 |
| TD-TEST | 0 | 0 |
| TD-SEC | 0 | 0 |
| TD-OPS | 0 | 0 |
| TD-DEP | 0 | 0 |
| **Total** | **1** | **0** |

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
| 2026-03-10 | TASK-319: Resolved TD-OPS-001 — executor metrics JSONL (elapsed_s, sdk_success_rate). 1 open item remains (TD-ARCH-001). |
| 2026-03-10 | TASK-322: Resolved TD-SEC-003 — HSTS header added to SecurityHeadersMiddleware. |
| 2026-03-10 | TASK-323: Resolved TD-TEST-003 — 5 Flask test-client integration tests assert all security headers end-to-end. TD-ARCH-001 Phase 1 analysis corrected: 6 of 8 "read-only" constants are mutable via do_set. |

---

## Code-Level Debt Scan (auto-generated 2026-03-11)

Scanned 13 files; found 18 inline debt markers.

| File | Line | Marker | Note |
|---|---|---|---|
| `solo_builder/api/blueprints/context_window.py` | 52 | NOQA | PLC0415 |
| `solo_builder/api/blueprints/prompt_regression.py` | 51 | NOQA | PLC0415 |
| `solo_builder/api/blueprints/webhook.py` | 56 | NOQA | S310  # nosec B310 |
| `solo_builder/cli_utils.py` | 9 | NOQA | dag_stats used by _handle_watch/_status |
| `solo_builder/discord_bot/test_bot.py` | 46 | NOQA | E402 |
| `solo_builder/runners/anthropic_runner.py` | 41 | NOQA | PLC0415 |
| `solo_builder/solo_builder_cli.py` | 352 | NOQA | S310  # nosec B310 |
| `solo_builder/tests/test_cache.py` | 419 | NOQA | — needed to pick up patched JOURNAL_PATH |
| `solo_builder/tests/test_debt_scan.py` | 34 | TODO | fix this\ny = 2\n") |
| `solo_builder/tests/test_debt_scan.py` | 42 | FIXME | broken\n") |
| `solo_builder/tests/test_debt_scan.py` | 48 | HACK | workaround\n") |
| `solo_builder/tests/test_debt_scan.py` | 54 | TODO | lower case\n") |
| `solo_builder/tests/test_debt_scan.py` | 67 | TODO | one\nx = 1\n# FIXME: two\n" |
| `solo_builder/tests/test_debt_scan.py` | 74 | TODO | here\n") |
| `solo_builder/tests/test_generate_openapi.py` | 330 | NOQA | PLC0415 |
| `tools/cache_stats.py` | 26 | NOQA | E402 |
| `tools/debt_scan.py` | 36 | TODO | |FIXME|HACK|XXX|NOQA)\b[:\s]*(.*)", re.IGNORECASE) |
| `tools/session_context_report.py` | 20 | NOQA | E402 |
