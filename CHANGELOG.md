# Changelog

## v4.0.0 — 2026-03-09  Milestone: 180 Tasks Complete

### Summary
- **180 tasks** merged to master (TASK-001 through TASK-180)
- **451 API tests** (test_app.py), **439 total tests** across all test files — 0 failures
- **Architecture score**: 97.7 / 100 (effective ceiling — remaining majors are intentional autonomy patterns)
- **Zero innerHTML** across all 7 ES module dashboard files (all DOM API)

### Major Features Added (selected highlights)

#### API
- Flask app refactored from 1729-line monolith → 13 blueprints in `api/blueprints/`
- Endpoints added: `/dag/summary`, `/branches`, `/branches/<task>`, `/subtasks`, `/subtasks/export`,
  `/tasks/<id>/subtasks`, `/tasks/<id>/branches`, `/tasks/<id>/progress` (with per-branch `branches[]`),
  `/tasks/<id>/timeline`, `/tasks/<id>/bulk-reset`, `/tasks/<id>/bulk-verify`, `/tasks/<id>/reset`,
  `/config/export`, `/config/reset`, `/health`, `/shortcuts`, `/dag/export`, `/tasks/export`
- `GET /tasks/<id>/progress` now returns `branches[]` breakdown per branch

#### Dashboard (ES modules)
- `dashboard.js` (1664 lines) split into 7 ES modules: `dashboard_state.js`, `dashboard_utils.js`,
  `dashboard_tasks.js`, `dashboard_panels.js`, `dashboard_branches.js`, `dashboard_cache.js`,
  `dashboard_svg.js`
- Keyboard shortcuts: `j/k` nav, `←/→` history paging, `r` run, `g` graph, `v` verify,
  `p` pause, `b` branches, `s` subtasks, `h` history, `?` help, `Esc` close
- Task detail panel: per-branch mini progress rows (TASK-176)
- `pollTaskProgress()` — in-place progress bar update via stable element IDs (TASK-180)
- Bulk-select UI in Branches and Subtasks tabs; 3-second auto-clear feedback (TASK-157/166)
- Pipeline Overview in Branches all-tasks view with per-task mini bars (TASK-121)
- SVG sparkline in subtask modal from `/timeline/<id>` (TASK-094)
- Toast notification history (max 20, 🔔 button) (TASK-098)
- Dark/light theme toggle persisted to `localStorage` (TASK-093)

#### Discord Bot
- 40+ slash commands extracted to `bot_slash.py`; formatters to `bot_formatters.py`
- New commands: `/task_progress`, `/bulk_reset`, `/bulk_verify`, `/branches`, `/forecast`,
  `/tasks`, `/filter`, `/agents`, `/heartbeat`, `/cache`
- `_format_task_progress()` — per-branch block-bar progress table

#### CLI / Runners
- `solo_builder_cli.py` refactored 2965 → 665 lines via mixin classes + 4 extracted modules
- `api/app.py` refactored 1729 → 84 lines
- `discord_bot/bot.py` refactored 2086 → 925 lines
- Response cache with SHA-256 keying, hit/miss stats, session stats in JOURNAL
- Async SDK runner (`AnthropicRunner` + `SdkToolRunner`) with rate-limit retry

### Test Coverage Additions (selected)
- `test_api_integration.py` (52 tests) — TASK-114
- `tests/test_utils_standalone.py` (30 tests) — TASK-117
- `test_cli_utils.py` (+20 tests) — TASK-122
- `TestBulkResetCommand`, `TestBulkVerifyCommand`, slash command variants — TASK-156/171
- `TestFormatTaskProgress` (7 direct unit tests) — TASK-178

### Architecture Notes
- **`/branches/<task>`** kept alongside `/tasks/<id>/branches` — former includes `subtasks[]` array
  needed by dashboard detail view; latter is the paginated branch-counts endpoint
- **`POST /tasks/<id>/reset`** (destructive, clears output) kept alongside `/bulk-reset`
  (preserves output, has `include_verified` flag) — different semantics, both valid
- **Test-patch gotcha** for CLI mixins: patch `solo_builder_cli.X` not mixin module globals;
  five globals (`_PDF_OK`, `_CFG_PATH`, `STATE_PATH`, `JOURNAL_PATH`, `WEBHOOK_URL`) must
  remain in `solo_builder_cli.py` or test patches won't take effect

---

## v3.x.x — 2025–2026  (TASK-001 through TASK-139)

See git log for individual task entries.
