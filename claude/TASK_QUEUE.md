# Task Queue

## Completed Tasks (TASK-001 through TASK-108)
All tasks merged to `master`. See `claude/JOURNAL.md` for history.
Latest: **v3.38.0** (TASK-108 — cli.py 704→665 lines, subcommands extracted to cli_utils.py)

Key milestones:
- TASK-103: solo_builder_cli.py 2965→1393 lines (mixin extraction)
- TASK-104: api/app.py 1729→84 lines (Flask Blueprints)
- TASK-105: dashboard.html 2587→349 lines (static CSS/JS)
- TASK-106: discord_bot/bot.py 2086→925 lines (bot_formatters + bot_slash)
- TASK-107: solo_builder_cli.py 1393→665 lines (dispatcher, auto_cmds, step_runner, cli_utils)
- TASK-108: cli.py 704→665 lines (status/watch subcommands → cli_utils.py)

---

## TASK-109 (proposed)
Goal: Add targeted unit tests for cli_utils.py (_handle_status_subcommand, _handle_watch_subcommand)

Acceptance Criteria:
- Tests for `_handle_status_subcommand`: missing state file, valid state file, pct/complete calculation
- Tests for `_handle_watch_subcommand`: completes when verified==total, KeyboardInterrupt handling
- `pwsh tools/audit_check.ps1` exits 0

Constraints:
- Scope limited to `solo_builder/tests/` and `solo_builder/cli_utils.py`
- No product-code changes
- Keep scope narrow

Priority: Low

## TASK-110 (proposed)
Goal: Document the test-patch constraint pattern so future contributors know which globals must stay in solo_builder_cli.py

Acceptance Criteria:
- Comment block or dev note explains the `_inject_host_globals_into_mixins` pattern
- Lists the 5 patched globals: `_PDF_OK`, `_CFG_PATH`, `STATE_PATH`, `JOURNAL_PATH`, `WEBHOOK_URL`
- Documents why functions reading these must stay in `solo_builder_cli.py`

Constraints:
- Documentation only — no product-code changes
- Keep scope narrow

Priority: Low

## TASK-109
Goal: Add unit tests for cli_utils._handle_status_subcommand and _handle_watch_subcommand

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-110
Goal: Document the test-patch constraint pattern for solo_builder_cli.py mixin architecture

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-111
Goal: Split dashboard.js into focused feature modules to reduce large-file architecture finding

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-112
Goal: Prune tracked snapshot artifacts and untrack chat.log to clear large-file architecture findings

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-113
Goal: Fix XSS findings in dashboard JS modules by escaping user data and using textContent where possible

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-114
Goal: Add Flask API integration tests targeting endpoints with insufficient coverage — pollMetrics, pollForecast, pollPriority, pollStalled, GET /branches, GET /subtasks, GET /timeline/<id>, GET /shortcuts, POST /config/reset — to raise coverage score in architecture audit

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-115
Goal: Reduce solo_builder_cli.py below 600 lines by extracting remaining inline logic into existing or new modules

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-116
Goal: Fix remaining architecture major findings: Bandit B310 urllib.urlopen in webhook.py, plus other major items identified by arch auditor

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-117
Goal: Add standalone pytest-style def test_* functions to improve architecture auditor function ratio metric

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-118
Goal: Add GET /dag/summary endpoint returning markdown pipeline summary with task/branch/subtask counts and completion pct

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-119
Goal: Add inline progress bar to CLI auto-loop step ticker showing verified/total/pct on a single updating line

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-120
Goal: Wire GET /dag/summary into Discord bot status command replacing current text output with markdown summary field

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-121
Goal: Add Pipeline Overview panel to dashboard Branches tab using GET /dag/summary data

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-122
Goal: Add standalone def test_* functions for cli_utils helpers (_load_dotenv, _build_arg_parser, _clear_stale_triggers, _emit_json_result) to push function ratio above 20%

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-123
Goal: Replace innerHTML assignments in dashboard JS with textContent/DOM API calls to remove XSS false-positive findings from arch auditor

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-124
Goal: Add GET /config/export endpoint that downloads settings.json as attachment, complementing existing /config GET

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-125
Goal: Add GET /config/export download link to dashboard Settings tab

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-126
Goal: Extract branch-rendering functions from dashboard_panels.js into dashboard_branches.js to bring all modules under 500 lines

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-127
Goal: Add GET /dag/export download link to dashboard Export tab alongside existing CSV/JSON exports

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-128
Goal: Raise architecture score above 94/100 by eliminating major findings

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-129
Goal: Add POST /tasks/<id>/reset endpoint to bulk-reset all subtasks in a task to Pending via HEAL_TRIGGER

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-130
Goal: Replace innerHTML with DOM API in dashboard_branches.js and dashboard_cache.js to eliminate XSS major findings

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-131
Goal: Add task-level reset button to the dashboard task detail panel (calls POST /tasks/<id>/reset)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-132
Goal: Add POST /branches/<task>/<branch>/reset endpoint for branch-level bulk subtask reset

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-133
Goal: Extract journal, diff, and stats rendering from dashboard_tasks.js into dashboard_journal.js to reduce all modules under 300 lines

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-134
Goal: Add reset_task command to Discord bot (plain-text + slash) that calls POST /tasks/<id>/reset

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-135
Goal: Convert renderDetail innerHTML to DOM API in dashboard_tasks.js

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-136
Goal: Add GET /tasks/<id>/export endpoint for single-task JSON/CSV download

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-137
Goal: Add reset_branch command to Discord bot (plain-text + slash)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-138
Goal: Add pagination to GET /subtasks (?page=, ?limit= with total in response)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-139
Goal: Add GET /tasks/<id>/timeline endpoint aggregating all subtask status transitions

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-140
Goal: Wire GET /tasks/<id>/timeline into dashboard task detail panel as event log

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-141
Goal: Add POST /subtasks/bulk-reset endpoint to reset multiple subtasks by ID in one request

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-142
Goal: Add ?page= and ?limit= pagination to GET /subtasks/export

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-143
Goal: Add GET /tasks/export endpoint — task-level summary CSV/JSON download

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-144
Goal: Push architecture score above 97/100 by identifying and fixing remaining major findings

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-145
Goal: Add GET /tasks/<task_id>/subtasks endpoint — flat list of subtasks for a specific task with same filter params as GET /subtasks

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-146
Goal: Add POST /subtasks/bulk-verify endpoint — advance multiple subtasks to Verified in one request

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-147
Goal: Add bulk_reset command to Discord bot (plain-text + slash) that calls POST /subtasks/bulk-reset

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-148
Goal: Fix renderGraph SVG nodeColorBg hardcoded hex colors to use CSS variables for light/dark theme compatibility

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-149
Goal: Add POST /tasks/<id>/bulk-verify endpoint — advance all Running/Review subtasks in a task to Verified

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-150
Goal: Wire bulk_reset and bulk-verify into dashboard Subtasks tab with multi-select checkboxes and action buttons

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-151
Goal: Add GET /tasks/<id>/progress endpoint — lightweight single-task progress {task,verified,total,pct,status}

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-152
Goal: Add bulk_verify command to Discord bot (plain-text + slash) counterpart to bulk_reset

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-153
Goal: Extract _svgBar and _sparklineSvg SVG helpers into shared dashboard_svg.js module

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-154
Goal: Run detailed architecture audit to surface remaining innerHTML/XSS majors and push score above 98/100

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-155
Goal: Add edge-case tests for GET /tasks/<id>/subtasks: empty task, zero subtasks, 404, pagination edge cases

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-156
Goal: Add slash command integration tests for /bulk_reset and /bulk_verify in test_bot.py

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-157
Goal: Add bulk-reset/bulk-verify UI to the Branches tab in dashboard_panels.js and dashboard.html

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-158
Goal: Add GET /health uptime_s display as tooltip on the dashboard status indicator

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-159
Goal: Add edge-case tests for POST /tasks/<id>/bulk-verify: empty task, all-verified, non-existent task

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-160
Goal: Poll GET /tasks/<id>/progress and display per-task progress bar in task detail sidebar

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-161
Goal: Add per-branch Reset button in Branches tab detail view using POST /tasks/<id>/reset

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-162
Goal: Add 'b' keyboard shortcut to toggle Branches tab; register in GET /shortcuts

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-164
Goal: Add 's' keyboard shortcut for Subtasks tab; register in _SHORTCUTS and add tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-165
Goal: Add GET /tasks/<id>/branches endpoint: paginated branch list with optional status filter

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-166
Goal: Improve bulk-verify feedback in Subtasks tab: show verified count in feedback span with auto-clear after 3s

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-167
Goal: Add POST /tasks/<id>/bulk-reset endpoint: reset all non-Verified subtasks in a task to Pending

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-168
Goal: Wire POST /tasks/<id>/bulk-reset into dashboard detail panel Reset button

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-169
Goal: Use GET /tasks/<id>/branches in Branches tab detail view instead of /branches/<task>

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-170
Goal: Add Discord /task_progress slash command using GET /tasks/<id>/progress

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions
