# Task Queue

## Completed Tasks (TASK-001 through TASK-414)
All tasks merged to `master`. See `claude/JOURNAL.md` and journal archive for history.
Latest: **v6.31.0** (2026-03-12)

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

Current stats: 3366 tests, 0 failures, 90 API routes, 0 open tech debt items, CI gate 6/6 PASS, arch score 99.0/100

---

## Backlog (proposed)

### TASK-408 (proposed)
Goal: Extract history panel from dashboard_panels.js into dashboard_history.js

Notes: Lines 8-193 (~186 lines) plus switchTab (lines 194-215) reference history state.
Would require refactoring switchTab to accept callbacks or using a shared state module.
Deferred due to cross-cutting complexity — 970-line file is acceptable.

Priority: Low

### TASK-409 (done — v6.28.0)
### TASK-410 (done — v6.29.0)

### TASK-411 (done — v6.30.0)
Extracted settings (105 lines) → dashboard_settings.js, stalled (134 lines) → dashboard_stalled.js.
dashboard_panels.js 960→722 lines. Subtasks deferred (cross-cutting switchTab refs).

### TASK-412 (proposed)
Goal: Add WebSocket support for real-time dashboard updates

Notes: Replace polling with SSE or WebSocket push for status/history/subtasks.
Would reduce API load and improve dashboard responsiveness.

Priority: Medium

### TASK-413 (done — v6.31.0)
ETag after_request handler. MD5 hash of response body, 304 on If-None-Match match.

### TASK-414 (done — v6.31.0)
bot.py 1103→436 lines. _handle_text_command + helpers → bot_commands.py (~550 lines).
