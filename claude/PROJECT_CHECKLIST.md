# Solo Builder — Project Completion Checklist
Last updated: 2026-03-07

## Definition of Done

The project is considered complete when:
- The current product is stable and reliable for operator use.
- The full test suite passes with no known recurring failures.
- The workflow hardening layer is complete and self-enforcing.
- Remaining work is roadmap, not blocker.

---

## 1. Product Completeness

**Status target:** Feature-frozen for this version. Major new capabilities are post-v1 roadmap.

- [x] `solo_builder_cli.py` — 6 agents, 3 runners, 70-subtask DAG, full CLI command set
- [x] Discord bot — 26 commands (slash + plain-text), IPC trigger files, heartbeat, chat log
- [x] Flask REST API + dark-theme dashboard (`api/app.py`, `api/dashboard.html`)
- [x] PDF snapshot exporter (`solo_builder_live_multi_snapshot.py`)
- [x] Profiler harness (`profiler_harness.py`) with `--dry-run` CI mode
- [x] Demo casts (`demo.gif`, `gen_demo_cast.py`, `gen_review_cast.py`)
- [ ] Known usability gaps fixed (only if they block real operation — assessed per task)

**Post-v1 / out of scope for completion:**
- Multi-model routing (Claude + reasoning model + Codex)
- Autonomous scheduling / cron-driven runs
- New agent types beyond current 6
- Advanced dashboard features (graphs, timeline, richer metrics)

---

## 2. Testing and CI

**Target:** All tests pass, no known recurring failures, CI green.

- [x] Full test suite passes (current: 195 tests, 0 failures — reached TASK-021)
- [x] No recurring optional test failures in audit runs
- [x] No known flaky tests in normal verification flow
- [x] `python -m unittest discover` clean in CI environment
- [x] CI runs canonical workflow checks (`bootstrap_verify`, `workflow_contract_check`, `ci_invariant_check`)
- [ ] CI green on push/PR with no false positives
- [ ] No coverage tooling required (reliability of existing suite is the bar, not coverage %)

---

## 3. Workflow / Infrastructure

**Target:** Deterministic task lifecycle, contract enforcement, and preflight all stable.

### Task lifecycle
- [x] Deterministic role flow: RESEARCH → ARCHITECT → DEV → AUDITOR → done
- [x] `advance_state.ps1` transitions enforced
- [x] `claude_orchestrate.ps1` renders correct NEXT_ACTION.md per phase/role
- [x] Post-close role rendering correct (TASK-015)
- [x] Task initialization via `start_task.ps1` with automated preflight gating (TASK-018)

### State / contract integrity
- [x] STATE.json ↔ NEXT_ACTION.md consistency verified on every preflight and CI run (TASK-014)
- [x] Workflow contract check: referenced scripts exist (Direction A) (TASK-020)
- [x] Workflow contract check: lifecycle outputs declared in `allowed_files.txt` (Direction B) (TASK-020)
- [ ] `workflow_contract_check.ps1` integrated into `workflow_preflight.ps1` — catches drift before task init (TASK-022)

### CI enforcement
- [x] CI is verification-only — no lifecycle mutations (TASK-019)
- [x] CI fails nonzero on required-check failures (TASK-019)
- [x] `workflow_contract_check.ps1` runs in CI before `ci_invariant_check` (TASK-020)
- [x] `workflow_contract_check.ps1` wired into `ci_bundle/repro.ps1` (TASK-020)

### Dev-time guards
- [x] `enforce_allowed_files.ps1` — blocks commits outside task scope
- [x] `secret_scan.ps1` — no credential leaks (TASK-002)
- [x] `precommit_gate.ps1` — non-blocking, Windows-robust (TASK-003)
- [x] `extract_allowed_files.ps1` — reliable heading parsing (TASK-011)
- [x] `new_file_guard.ps1` — blocks accidental new-file commits (override via `CLAUDE_ALLOW_NEW_FILES=1`)

### Documentation
- [x] `claude/WORKFLOW_SPEC.md` — canonical workflow specification (TASK-016)
- [x] `claude/WORKFLOW_SPEC.md` — CI verification-only contract documented (TASK-019)
- [x] `claude/WORKFLOW_SPEC.md` — workflow contract integrity section added (TASK-020)
- [ ] `claude/PROJECT_CONTEXT.md` — product/architecture summary filled in
- [ ] `claude/PROJECT_CHECKLIST.md` — this file, kept current

---

## 4. Known Remaining Items

| # | Item | Task | Priority |
|---|---|---|---|
| 1 | Integrate `workflow_contract_check.ps1` into preflight | TASK-022 | High |
| 2 | Fill in `claude/PROJECT_CONTEXT.md` | — | Medium |
| 3 | Confirm full loop runs repeatedly without manual patching | — | Medium |
| 4 | `test_stalled_empty` config mock (coincidentally passing, not explicitly isolated) | — | Low |

---

## 5. Completion Gate

The project is **done** when all boxes above are checked and the Known Remaining Items table is empty or contains only Low-priority items deferred to post-v1.

**Current state:** ~90% complete. Primary blocker: TASK-022 preflight integration.
