# Task Queue

## Completed Tasks (TASK-001 through TASK-407)
All tasks merged to `master`. See `claude/JOURNAL.md` and journal archive for history.
Latest: **v6.28.0** (2026-03-12)

Key milestones:
- TASK-103: solo_builder_cli.py 2965→1393 lines (mixin extraction)
- TASK-104: api/app.py 1729→84 lines (Flask Blueprints)
- TASK-105: dashboard.html 2587→349 lines (static CSS/JS)
- TASK-106: discord_bot/bot.py 2086→925 lines (bot_formatters + bot_slash)
- TASK-107: solo_builder_cli.py 1393→665 lines (dispatcher, auto_cmds, step_runner, cli_utils)
- TASK-108–119: cli_utils, dashboard, XSS audit, API coverage, progress bar
- TASK-300+: Tools layer (state_validator, metrics_alert, lint, release_notes, version_bump, prompt_builder, hitl_policy, tool_scope, threat_model, ci_quality, generate_openapi, discord_role_guard, state_backup, config_drift, context_window_budget, dep_severity, health_detailed, context_window_compact, lock_file_gen)
- TASK-380+: AAWO bridge, outcome stats, OpenAPI health routes, blueprint coverage
- TASK-400+: Final coverage sprints, architecture polish

Current stats: 3358 tests, 0 failures, 90 API routes, 0 open tech debt items, CI gate 6/6 PASS

---

## Backlog (proposed)

### TASK-408 (proposed)
Goal: Extract history panel from dashboard_panels.js into dashboard_history.js

Notes: Lines 8-193 (~186 lines) plus switchTab (lines 194-215) reference history state.
Would require refactoring switchTab to accept callbacks or using a shared state module.
Deferred due to cross-cutting complexity — 970-line file is acceptable.

Priority: Low

### TASK-409 (proposed)
Goal: Add automated OpenAPI spec drift detection test

Acceptance Criteria:
- Test that compares Flask `app.url_map` routes against `generate_openapi.py` `build_spec()` output
- Fails if any route exists in Flask but not in spec (or vice versa)
- Runs as part of `test_generate_openapi.py`

Priority: Medium

### TASK-410 (proposed)
Goal: Add dashboard E2E smoke test for the new dashboard_health.js module

Acceptance Criteria:
- Verify all 14 health poller functions are importable via dashboard_panels.js re-exports
- Verify dashboard.js import statement includes all health pollers

Priority: Low

### TASK-411 (proposed)
Goal: Reduce dashboard_panels.js further by extracting settings/stalled/subtasks panels

Notes: Settings (246-350), stalled (412-545), subtasks (546-826) are self-contained.
Would bring dashboard_panels.js from 970 to ~350 lines.

Priority: Low
