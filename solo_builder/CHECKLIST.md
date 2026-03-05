# Solo Builder — Project Checklist
<!-- AUTO-UPDATED: This checklist is maintained by Claude Code during development sessions. -->

Last updated: **v2.1.51** · 2026-03-05 · 289 tests (194 bot + 95 API) · ~99% complete

---

## Legend
- [x] Complete
- [ ] Remaining

---

## 1. Core Engine (`solo_builder_cli.py` — 3,533 lines)

### 1.1 Agent Pipeline
- [x] Planner — risk-based priority scoring with adjustable weights
- [x] Executor — 4-tier execution (SdkToolRunner → ClaudeRunner → AnthropicRunner → dice roll)
- [x] ShadowAgent — expected-state tracking, conflict detection/resolution
- [x] Verifier — branch/task status roll-up, DAG consistency
- [x] SelfHealer — stalled subtask detection + auto-reset after threshold
- [x] MetaOptimizer — per-step metrics, weight adaptation, completion forecast

### 1.2 Execution Runners
- [x] SdkToolRunner — async SDK tool-use with 8-round loop, rate-limit retry (3× exponential backoff)
- [x] ClaudeRunner — subprocess fallback with ThreadPoolExecutor
- [x] AnthropicRunner — async SDK without tools (asyncio.gather)
- [x] Dice-roll fallback — final fallback when no API key/CLI available

### 1.3 DAG & State
- [x] INITIAL_DAG — 7 tasks, diamond fan-out/fan-in, 70 subtasks
- [x] State persistence — JSON auto-save every 5 steps + on exit
- [x] Resume on startup — detects save file, prompts Y/n
- [x] Lockfile — PID-based with stale detection (`state/solo_builder.lock`)
- [x] Backup system — pre-step backup for undo support
- [x] Priority cache — refreshed every DAG_UPDATE_INTERVAL steps or on task completion

### 1.4 CLI Commands (42 commands)
- [x] `run` — execute one step
- [x] `auto [N]` — run N steps (or until complete)
- [x] `pause` — pause auto-run
- [x] `resume` — resume paused auto-run
- [x] `stop` — (via trigger file only, no direct CLI stop)
- [x] `snapshot` — PDF timeline snapshot
- [x] `save` — manual state save
- [x] `load` — load saved state
- [x] `load_backup` — load pre-step backup
- [x] `undo` — restore from backup
- [x] `diff` — show changes since last save
- [x] `timeline <ST>` — subtask status history
- [x] `reset` — reset DAG to initial state
- [x] `status` — detailed DAG statistics
- [x] `stats` — per-task breakdown
- [x] `history [N]` — last N status transitions
- [x] `add_task [spec]` — add new task (inline or prompted)
- [x] `add_branch <task> [spec]` — add branch to task
- [x] `prioritize_branch <task> <branch>` — boost branch priority
- [x] `export` — write all Claude outputs to markdown
- [x] `depends [<T> <dep>]` — add/show dependencies
- [x] `undepends <T> <dep>` — remove dependency
- [x] `describe <ST> <text>` — set Claude prompt for subtask
- [x] `verify <ST> [note]` — manually verify subtask
- [x] `tools <ST> <list>` — set allowed tools
- [x] `output <ST>` — show Claude output
- [x] `branches [Task N]` — list branches with detail
- [x] `rename <ST> <text>` — update subtask description
- [x] `search <text>` — find subtasks by keyword
- [x] `filter <status>` — show subtasks by status
- [x] `graph` — ASCII dependency graph
- [x] `log [ST]` — show journal entries
- [x] `set KEY=VALUE` — change runtime config
- [x] `config` — display all settings
- [x] `priority` — show planner's priority queue
- [x] `stalled` — show stuck subtasks
- [x] `heal <ST>` — manually reset Running subtask
- [x] `agents` — show all agent stats
- [x] `forecast` — detailed completion forecast
- [x] `tasks` — per-task summary table
- [x] `help` — show help
- [x] `exit` — save and quit

### 1.5 IPC Trigger Files (17 triggers)
- [x] `run_trigger` — dashboard Run Step
- [x] `stop_trigger` — stop auto-run
- [x] `verify_trigger.json` — verify subtask
- [x] `describe_trigger.json` — set description
- [x] `tools_trigger.json` — set tools
- [x] `rename_trigger.json` — rename subtask
- [x] `add_task_trigger.json` — add task
- [x] `add_branch_trigger.json` — add branch
- [x] `prioritize_branch_trigger.json` — boost branch
- [x] `set_trigger.json` — change setting
- [x] `depends_trigger.json` — add dependency
- [x] `undepends_trigger.json` — remove dependency
- [x] `reset_trigger` — reset DAG
- [x] `snapshot_trigger` — PDF snapshot
- [x] `undo_trigger` — undo step
- [x] `pause_trigger` — pause auto-run
- [x] `heal_trigger.json` — heal subtask

---

## 2. REST API (`api/app.py` — 724 lines)

### 2.1 GET Endpoints (18)
- [x] `GET /` — serve dashboard HTML
- [x] `GET /status` — DAG summary stats
- [x] `GET /tasks` — all tasks as JSON
- [x] `GET /tasks/<id>` — single task detail
- [x] `GET /heartbeat` — live step.txt counters
- [x] `GET /export` — Claude outputs as markdown
- [x] `GET /stats` — per-task statistics
- [x] `GET /search` — keyword search
- [x] `GET /history` — status transitions
- [x] `GET /diff` — changes since last save
- [x] `GET /branches/<id>` — branch detail
- [x] `GET /timeline/<st>` — subtask timeline
- [x] `GET /journal` — journal entries
- [x] `GET /config` — settings.json contents
- [x] `GET /graph` — dependency graph as JSON
- [x] `GET /priority` — priority queue as JSON
- [x] `GET /stalled` — stalled subtasks as JSON
- [x] `GET /agents` — agent statistics as JSON
- [x] `GET /forecast` — completion forecast as JSON

### 2.2 POST Endpoints (11)
- [x] `POST /run` — trigger one step
- [x] `POST /stop` — write stop trigger
- [x] `POST /verify` — verify subtask
- [x] `POST /describe` — set description
- [x] `POST /tools` — set tools
- [x] `POST /set` — change setting
- [x] `POST /rename` — rename subtask
- [x] `POST /export` — generate export file
- [x] `POST /config` — update settings
- [x] `POST /tasks/<id>/trigger` — task-specific trigger
- [x] `POST /heal` — heal subtask

### 2.3 Error Handling
- [x] 404 handler → JSON
- [x] 405 handler → JSON
- [x] CORS headers (`Access-Control-Allow-Origin: *`)

---

## 3. Dashboard (`api/dashboard.html` — 1,718 lines)

### 3.1 Main Layout
- [x] Dark theme with CSS variables
- [x] Header bar with step counter, progress bar, verified/running/pending/total
- [x] Auto-run controls (Auto button + step count input)
- [x] Stop button (⏹)
- [x] Task grid (clickable task cards with status colors)
- [x] Task detail modal (status, description, output, verify/describe/tools forms)
- [x] Graph view toggle (SVG DAG with progress bars in nodes)

### 3.2 Sidebar Tabs (10)
- [x] Journal — journal.md entries
- [x] Diff — changes since last save
- [x] Stats — per-task breakdown
- [x] History — status transitions
- [x] Branches — branch listing with subtask counts
- [x] Settings — editable settings with inline save
- [x] Priority — priority queue with risk bars
- [x] Stalled — stuck subtasks with age bars + heal buttons
- [x] Agents — agent stats with forecast gauge SVG
- [x] Forecast — dedicated forecast tab with progress/rates/ETA display (added v2.1.50)

### 3.3 Dashboard Features
- [x] 2-second auto-polling loop (tick)
- [x] Toast notifications
- [x] Modal rename/describe/verify/tools actions
- [x] Heartbeat-based counter updates during auto-run
- [x] Heal button on stalled items → POST /heal
- [x] Editable settings → POST /config
- [x] Task search/filter in grid view (search-input + applyFilter() — pre-existing)
- [x] Export download button (btn-export + exportOutputs() — pre-existing)
- [x] Dark/light theme toggle (persistent via localStorage — pre-existing)
- [x] Keyboard shortcuts: Esc (close modal), j/k (navigate tasks), v (verify), Enter (open modal), r (run step), g (toggle graph)

### 3.4 Dashboard Polls (12 pollers)
- [x] pollStatus
- [x] pollTasks
- [x] pollJournal
- [x] pollDiff
- [x] pollStats
- [x] pollHistory
- [x] pollBranches
- [x] pollSettings
- [x] pollPriority
- [x] pollStalled
- [x] pollAgents
- [x] pollForecast (added v2.1.50)

---

## 4. Discord Bot (`discord_bot/bot.py` — 1,944 lines)

### 4.1 Bot Infrastructure
- [x] discord.py 2.0+ integration
- [x] Channel restriction (DISCORD_CHANNEL_ID)
- [x] Two-way chat.log with UTC timestamps
- [x] Per-step tickers in auto-run
- [x] 30s JSON flush wait after auto-run
- [x] Auto-run indicator on /status
- [x] `flush=True` on all on_ready prints
- [x] _auto_task guard preventing duplicate concurrent auto runs

### 4.2 Plain-Text Commands (30+)
- [x] status, run, auto [n], stop, verify, output, describe, tools
- [x] add_task, add_branch, prioritize_branch, set, depends, undepends
- [x] reset (with confirm gate), snapshot, export, undo
- [x] pause, resume, config, graph, diff
- [x] filter, priority, stalled, heal, agents, forecast
- [x] timeline, stats, history, search, log, branches, heartbeat
- [x] rename, help
- [x] tasks (plain-text + slash — added v2.1.50)

### 4.3 Slash Commands (34)
- [x] /help, /status, /run, /auto, /stop, /verify, /output
- [x] /describe, /tools, /add_task, /add_branch, /prioritize_branch
- [x] /set, /depends, /undepends, /reset, /snapshot, /export, /undo
- [x] /config, /branches, /graph, /filter, /priority, /stalled
- [x] /heal, /agents, /forecast, /history, /rename, /diff
- [x] /timeline, /heartbeat, /search, /log
- [x] /tasks (added v2.1.50)
- [x] /pause, /resume (slash commands already existed — checklist was wrong)

### 4.4 Helper Functions (16)
- [x] _format_status, _format_graph, _format_diff, _format_filter
- [x] _format_priority, _format_stalled, _format_agents, _format_forecast
- [x] _format_heal, _format_timeline, _format_stats, _format_history
- [x] _format_search, _format_branches, _format_log, _format_step_line

---

## 5. Test Suite (265 tests total)

### 5.1 API Tests (`api/test_app.py` — 113 tests)
- [x] TestGetStatus (3), TestGetTasks (2), TestGetTaskDetail (2)
- [x] TestPostRun (2), TestPostVerify (3), TestPostDescribe (2)
- [x] TestPostTools (2), TestPostSet (2), TestHeartbeat (3)
- [x] TestExport (5), TestJournal (3), TestStats (3)
- [x] TestSearch (3), TestHistory (3), TestDiff (3)
- [x] TestBranches (3), TestRename (3), TestTimeline (3)
- [x] TestConfig (5), TestGraph (3), TestStop (1)
- [x] TestPriority (3), TestStalled (3), TestHeal (2)
- [x] TestAgents (3), TestForecast (3), TestErrorHandlers (2)
- [x] Test for GET / (root endpoint) — TestGetRoot added v2.1.50
- [x] Test for POST /tasks/<id>/trigger — TestPostTaskTrigger added v2.1.50
- [x] Test for POST /export — already covered in TestExport (pre-existing)

### 5.2 Bot Tests (`discord_bot/test_bot.py` — 194 tests)
- [x] TestHasWork, TestFormatStatus, TestAutoRunning
- [x] TestReadHeartbeat, TestFormatStepLine, TestLoadState
- [x] TestHandleTextCommand (10+), TestRunAuto (4)
- [x] TestFireCompletion (4), TestCLICommands
- [x] TestVerifyDescribeTools, TestSetCommand
- [x] TestResetCommand, TestExportCommand, TestStatusCommand
- [x] TestDependsUndepends (10), TestOutputCommand (4)
- [x] TestSaveLoadState (5), TestSnapshotCommand
- [x] TestPrioritizeBranch, TestAddTaskInlineSpec
- [x] TestAddTaskDepWiring, TestAddBranchInlineSpec
- [x] TestFindSubtaskOutput, TestHandleTextCommandExtra
- [x] TestTimelineCommand, TestFilterCommand
- [x] TestPriorityCommand (2), TestStalledCommand (2)
- [x] TestHealCommand (3), TestAgentsCommand (2)
- [x] TestForecastCommand (2), TestHistoryCommand
- [x] TestSearchCommand, TestStatsCommand
- [x] TestLogCommand, TestBranchesCommand
- [x] TestRenameCommand, TestUndoCommand

---

## 6. CI/CD (`.github/workflows/smoke-test.yml`)
- [x] GitHub Actions on push (Ubuntu, Python 3.13)
- [x] Headless CLI run (15 steps)
- [x] Assert 18+ subtasks verified
- [x] Export command test
- [x] stop_trigger cleared on startup test
- [x] Bot unit tests (194)
- [x] API unit tests (71)
- [x] Profiler dry-run
- [x] REVIEW_MODE test
- [x] add_task inline spec test
- [x] add_task dep wiring test
- [x] add_branch inline spec test
- [x] Webhook POST test
- [x] CI badge in README reflects current test counts — CI step labels updated to "194 tests" (bot) and "95 tests" (API) (v2.1.50)
- [x] Integration test: dashboard → API → CLI round-trip — Flask test client POST /verify → trigger written → CLI consumes → A1 Verified (v2.1.51)
- [x] Integration test: bot → trigger → CLI round-trip — write verify_trigger.json → CLI --headless --auto 2 consumes → A2 Verified (v2.1.51)

---

## 7. Documentation
- [x] README.md — install, setup, usage, architecture, troubleshooting
- [x] CHANGELOG.md — all versions from v2.1.0 to v2.1.49
- [x] CONTRIBUTING.md — contribution guidelines
- [x] README test count — updated to 194 bot / 74 API / 268 total (v2.1.50)
- [x] README command list — added all newer commands to bot table + key commands section (v2.1.50)
- [x] README architecture section — updated line counts, endpoint counts, test counts (v2.1.50)
- [x] API endpoint documentation — `docs/API.md` — all 30 GET+POST endpoints with request/response examples (v2.1.50)
- [x] Bot command reference page — `docs/BOT_COMMANDS.md` — all 37 slash + 31 plain-text commands (v2.1.50)
- [x] Dashboard user guide — `docs/DASHBOARD.md` — layout, all 10 tabs, keyboard shortcuts, API poller reference (v2.1.51)

---

## 8. Configuration (`config/settings.json` — 21 keys)
- [x] STALL_THRESHOLD, SNAPSHOT_INTERVAL, DAG_UPDATE_INTERVAL
- [x] PDF_OUTPUT_PATH, STATE_PATH, JOURNAL_PATH
- [x] AUTO_SAVE_INTERVAL, AUTO_STEP_DELAY
- [x] MAX_SUBTASKS_PER_BRANCH, MAX_BRANCHES_PER_TASK
- [x] VERBOSITY, BAR_WIDTH, MAX_ALERTS
- [x] EXECUTOR_MAX_PER_STEP, EXECUTOR_VERIFY_PROBABILITY
- [x] CLAUDE_TIMEOUT, CLAUDE_ALLOWED_TOOLS
- [x] ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS
- [x] REVIEW_MODE, WEBHOOK_URL

---

## 9. Supporting Files
- [x] `profiler_harness.py` — monkey-patching benchmark with --dry-run
- [x] `solo_builder_live_multi_snapshot.py` — 4-page PDF via matplotlib
- [x] `gen_demo_cast.py` — synthetic v2.1 demo cast
- [x] `gen_review_cast.py` — synthetic REVIEW_MODE cast
- [x] `demo.gif` — v2.1 demo recording
- [x] `review_mode_demo.gif` — REVIEW_MODE demo
- [x] `utils/helper_functions.py` — ANSI codes, bars, DAG stats, validators
- [x] `__init__.py` — package init
- [x] `journal.md` — journal entries

---

## 10. Feature Parity Gaps (cross-surface)
> Items where a feature exists on one surface but not all applicable surfaces.

- [x] **Bot `tasks`** — added plain-text + slash /tasks (v2.1.50)
- [x] **Bot `/pause` `/resume` slash** — pre-existing (checklist was wrong)
- [x] **Dashboard forecast tab** — added v2.1.50
- [x] **Dashboard task search/filter** — pre-existing (search-input + applyFilter, checklist was wrong)
- [x] **Dashboard export button** — pre-existing (btn-export + exportOutputs, checklist was wrong)
- [x] **API POST /add_task** — added v2.1.50
- [x] **API POST /add_branch** — added v2.1.50
- [x] **API POST /prioritize_branch** — added v2.1.50
- [x] **API POST /depends** — added v2.1.50
- [x] **API POST /undepends** — added v2.1.50
- [x] **API POST /undo** — added v2.1.50
- [x] **API POST /reset** — added v2.1.50 (requires `{"confirm":"yes"}`)
- [x] **API POST /snapshot** — added v2.1.50
- [x] **API POST /pause** — added v2.1.50
- [x] **API POST /resume** — added v2.1.50

---

## 11. Polish & Hardening
- [x] README.md update — synced test counts, command lists, architecture (v2.1.50)
- [x] Dashboard responsive design (mobile-friendly) — `@media (max-width: 768px)` single-column layout (v2.1.50)
- [x] Dashboard keyboard shortcuts — Esc, j/k, v, Enter, r (run), g (graph toggle) (v2.1.50)
- [x] Dashboard notification sound on completion — Web Audio API three ascending beeps (v2.1.50)
- [x] Bot error handling for Discord API rate limits — `on_app_command_error` + `on_error` handler, `_send` retries on 429 (v2.1.50)
- [x] Bot pagination for long outputs (>2000 chars) — `_send` chunks at 1950 chars on newlines (v2.1.50)
- [x] CLI input validation hardening — settings range/type validation; `_cmd_tools` warns on unknown tool names (v2.1.50)
- [x] Settings validation (type checking, range validation) — STALL_THRESHOLD ≥1, VERIFY_PROB 0–1, VERBOSITY enum, MAX_TOKENS 1–8192, etc. (v2.1.50)
- [x] Graceful shutdown on SIGINT/SIGTERM — SIGTERM handler saves state + releases lock (v2.1.50); SIGINT (KeyboardInterrupt) already handled
- [x] State file corruption recovery — `load_state` tries primary → .1 → .2 → .3 backups on JSONDecodeError (v2.1.50)
- [x] Concurrent state file access protection — atomic write via temp file + os.replace prevents mid-write corruption (v2.1.50)
- [x] Logging to file (structured, not just print) — `RotatingFileHandler` → `state/solo_builder.log`; key events logged (startup, state save/load, subtask lifecycle, heals, errors) (v2.1.51)

---

## 12. Nice-to-Have / Future
- [x] Dashboard subtask output viewer (inline expandable) — `▶`/`▼` toggle per subtask row; `st-expand-content` panel with full output, max-height scroll (v2.1.52)
- [x] Custom DAG import/export (JSON) — `export_dag [file]` / `import_dag <file>` CLI commands; `GET /dag/export` + `POST /dag/import` API; `dag_import_trigger.json` IPC for live CLI (v2.1.52)
- [x] Metrics/analytics endpoint — `GET /metrics` returns full meta_history time-series + summary stats; dashboard Metrics tab with SVG sparkline (v2.1.52)
- [ ] WebSocket for real-time dashboard updates (replace polling)
- [ ] Dashboard task drag-and-drop reordering
- [ ] Multi-project support (multiple DAGs)
- [ ] User authentication for dashboard/API
- [ ] Notification integrations (Slack, email, webhook templates)
- [ ] Plugin system for custom agents
- [ ] Rate limit dashboard (Anthropic API usage tracking)

---

## Summary

| Category | Done | Remaining |
|----------|------|-----------|
| Core Engine | 100% | — |
| CLI Commands | 42/42 | — |
| API Endpoints | 40/40 | — |
| Dashboard Tabs | 10/10 | — |
| Dashboard Features | 10/10 | — |
| Bot Plain-Text | 31/31 | — |
| Bot Slash Commands | 37/37 | — |
| API Tests | 113/113 | — |
| Bot Tests | 194/194 | — |
| CI/CD | 16/16 | — |
| Documentation | 9/9 | — |
| Feature Parity | 15/15 | — |
| Polish | 12/12 | — |
| Nice-to-Have | 3/10 | 7 (deferred) |
| **Total** | **~100%** | **7 (Nice-to-Have, deferred)** |
