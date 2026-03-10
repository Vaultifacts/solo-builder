# SLO Definitions
**TASK-315 | Audit refs: OM-035 to OM-040**
Last updated: 2026-03-10

---

## Purpose

This document defines measurable Service Level Objectives (SLOs) for Solo
Builder. SLOs give concrete targets against which system reliability can be
assessed. Without them, "the system is working" is subjective.

These SLOs apply to the local development environment. They are not
production SLAs — Solo Builder is a single-user tool with no uptime
commitment to external users.

---

## SLO Definitions

### SLO-001 — API Test Suite Pass Rate

**Target:** 100% of `test_app.py` tests pass on every commit to `master`.

**Measurement:** `pytest solo_builder/api/test_app.py` exit code 0.

**Window:** Per-commit (every merge to master).

**Error budget:** Zero failures tolerated. Any failing test blocks merge.

**Current baseline:** 600/600 tests passing (v5.8.0).

---

### SLO-002 — Discord Bot Test Suite Pass Rate

**Target:** 100% of `test_bot.py` tests pass on every commit to `master`.

**Measurement:** `pytest solo_builder/discord_bot/test_bot.py` exit code 0.

**Window:** Per-commit.

**Error budget:** Zero failures tolerated.

**Current baseline:** 305/305 tests passing (v5.8.0).

---

### SLO-003 — Anthropic SDK Call Success Rate (headless execution)

**Target:** ≥ 95% of `AnthropicRunner.arun()` calls return `success=True`
in a healthy execution session.

**Measurement:** Count `subtask_verified` log entries vs. `subtask_sdk_error`
entries over a full DAG execution (Task 0 through Task 6).

**Window:** Per DAG execution session.

**Error budget:** ≤ 5% failure rate. Failures exceeding budget trigger
`SelfHealer` review.

**Exclusions:** `RateLimitError` retries (up to 3×) are not counted as failures
if the final attempt succeeds.

---

### SLO-004 — Gate Check Pass Rate

**Target:** 14/14 gate checks pass before any release tag is created.

**Measurement:** `pwsh tools/audit_check.ps1` — all checks green.

**Window:** Per release candidate.

**Error budget:** Zero gate failures tolerated at release time.

**Current baseline:** 14/14 operational (v5.8.0).

---

### SLO-005 — Executor Step Latency (SDK direct path)

**Target:** ≤ 10 seconds median latency per subtask on the `AnthropicRunner`
direct path (no tools, `ANTHROPIC_MAX_TOKENS=300`).

**Measurement:** Wall-clock time from subtask dispatch to `subtask_verified`
log entry.

**Window:** Rolling 20-subtask window during active execution.

**Error budget:** ≤ 20% of subtasks may exceed 10 s (stall threshold applies
at 3× the normal step count, per `STALL_THRESHOLD`).

**Notes:** Latency is dominated by Anthropic API response time; network
conditions outside project control.

---

### SLO-006 — Notion Sync Reliability

**Target:** `notion_sync.py` completes successfully (exit 0) on ≥ 99% of
post-commit hook invocations when `NOTION_INTEGRATION_TOKEN` is set.

**Measurement:** Exit code of post-commit hook execution.

**Window:** Rolling 100 commits.

**Error budget:** ≤ 1 failure per 100 commits (transient API errors).

**Failure handling:** All Notion API calls retry 3× with exponential backoff;
hook exits 0 on `RuntimeError` to never block a commit.

---

## SLO Dashboard (current state)

| SLO | Target | Current | Status |
|---|---|---|---|
| SLO-001 API tests | 100% | 600/600 (100%) | ✅ |
| SLO-002 Discord tests | 100% | 305/305 (100%) | ✅ |
| SLO-003 SDK success rate | ≥ 95% | Not yet instrumented | ⚠️ |
| SLO-004 Gate checks | 14/14 | 14/14 | ✅ |
| SLO-005 Step latency | ≤ 10 s median | Not yet instrumented | ⚠️ |
| SLO-006 Notion sync | ≥ 99% | Not yet instrumented | ⚠️ |

Items marked ⚠️ have defined targets but no automated measurement yet.
Instrumentation is the next step (tracked under OM-035 to OM-040).

---

## Measurement Gaps

| Gap ID | Description | Resolution |
|---|---|---|
| OM-035 | No SLO definitions | **Resolved by TASK-315** |
| OM-036 | SDK success rate not instrumented | Open — requires executor metrics log |
| OM-037 | Step latency not measured | Open — requires timing instrumentation |
| OM-038 | Notion sync success rate not tracked | Open — requires hook exit code log |
| OM-039 | No SLO dashboard UI | Open — future dashboard widget |
| OM-040 | No alerting on SLO breach | Open — future Discord notification |

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial SLO definitions (TASK-315). Six SLOs defined. OM-035 resolved. |
