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

## TASK-171
Goal: Add edge-case tests for POST /tasks/<id>/bulk-reset: all-Verified + include_verified, empty task, no branches

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-172
Goal: Add h keyboard shortcut to switch to History tab; add to _SHORTCUTS constant; 2 tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-173
Goal: Extract _format_task_progress to bot_formatters.py; add task_progress to plain-text help in bot.py

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-174
Goal: Add GET /tasks/<id>/timeline endpoint aggregating all subtask timeline events for a task

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-175
Goal: Add GET /tasks/<id>/progress endpoint with per-branch subtask counts (verified/running/pending/total/pct)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-176
Goal: Wire GET /tasks/<id>/progress branches[] into dashboard task detail progress bar; remove inline per-branch computation

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-177
Goal: Audit GET/POST /tasks/<id>/reset endpoint: verify it is still needed or can be removed; update tests if deprecated

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-178
Goal: Verify TestTaskProgressCommand tests call bot_formatters._format_task_progress directly; add direct formatter unit tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-179
Goal: Add deprecation comment on GET /branches/<task> noting /tasks/<id>/branches as the preferred paginated endpoint

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-180
Goal: Add pollTaskProgress() in dashboard_tasks.js that fetches GET /tasks/<id>/progress and updates the detail progress bar without a full task reload

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-181
Goal: Tag v4.0.0 milestone: add CHANGELOG entry summarising 180 tasks, 451 API tests, arch score 97.7/100

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-182
Goal: Add integration tests for GET /tasks/<id>/progress verifying branches[] field and in-place DOM update logic

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-183
Goal: Call pollTaskProgress inside window.runAuto step loop for real-time progress bar updates during auto-run

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-184
Goal: Audit GET /tasks endpoint response: verify it includes all fields dashboard_tasks.js needs to avoid the double-fetch per-task in tick()

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-185
Goal: Enhance _format_task_progress in bot_formatters.py to show per-branch block-bar table with branch names and counts

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-186
Goal: Add Review count to renderDetail() progress bar in dashboard_tasks.js; show as N⏸ alongside running▶

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-214
Goal: hdr-pending stat box shows review count separately when review > 0

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-215
Goal: GET /history/count returns review in status distribution

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-216
Goal: CHANGELOG v4.3.x entry documenting TASK-213 through TASK-215

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-217
Goal: GET /history response includes review count in top-level metadata

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-218
Goal: Dashboard History tab shows by_status chips from /history/count response

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-219
Goal: GET /stalled regression test confirming Review subtasks are excluded

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-220
Goal: Prune MEMORY.md to under 200 lines by archiving detail to topic files

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-221
Goal: CHANGELOG v4.4.0 entry documenting TASK-216 through TASK-220

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-222
Goal: Dashboard Export tab shows /history/count by_status summary alongside history export links

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-223
Goal: GET /metrics health summary includes review count field

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-224
Goal: History tab pager shows review count alongside page/total info

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-225
Goal: GET /tasks supports server-side pagination via limit and page query params

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-226
Goal: CHANGELOG v4.4.5 entry documenting TASK-221 through TASK-225

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-227
Goal: Dashboard task grid uses GET /tasks pagination — total and pages fields shown in grid header

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-228
Goal: GET /subtasks supports limit and page query params for server-side pagination

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-229
Goal: GET /branches supports limit and page query params for server-side pagination

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-230
Goal: Audit and fix branches tab inline handlers for ES module window exposure gaps

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-231
Goal: Add pager UI to Subtasks tab (◀/▶ buttons + count label) using GET /subtasks pagination

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-232
Goal: Add pager UI to Branches tab all-branches view (◀/▶ + count label) using GET /branches pagination

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-233
Goal: Add pager UI to Tasks tab (◀/▶ nav buttons) using GET /tasks pagination

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-234
Goal: Final audit of dashboard.html inline handlers vs window.* assignments; fix any remaining gaps

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-235
Goal: Document TASK-226 through TASK-235 in CHANGELOG.md as v4.5.0

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-236
Goal: Subtasks tab status quick-filter passes ?status=X to server so filter composes with pagination across all pages

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-237
Goal: Render review count in Branches all-tasks rows (field added in TASK-229 but not displayed)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-238
Goal: Reset page to 1 when task-search, subtasks-filter (non-status), or branch task-search input changes

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-239
Goal: Add Node.js CI lint script that parses dashboard.html inline handlers and cross-checks window.* assignments

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-240
Goal: Add yellow Review badge in subtask detail modal when status is Review

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-241
Goal: Wire lint_dashboard_handlers.js into pre-commit hook chain

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-242
Goal: Subtasks CSV/JSON export links include ?status=X when status filter is active

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-243
Goal: Add status quick-filter buttons to Branches all-tasks view (Pending/Running/Review/Verified)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-244
Goal: Add regression test: task card review_subtasks badge verified present and correct in GET /tasks response

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-245
Goal: Document TASK-236 through TASK-245 in CHANGELOG.md as v4.6.0

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-246
Goal: Add CSV/JSON download links to Branches all-tasks view respecting active status filter

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-247
Goal: Route task-search through pollTasks(?task=X) for server-side filtering across all pages

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-248
Goal: Add stalled-subtask regression tests: boundary and multi-stall scenarios for GET /status stalled count and stall detection logic

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-249
Goal: History export hrefs include active branch filter: when branch filter is set, ?branch=X must be included in CSV and JSON export anchor hrefs

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-250
Goal: Add v4.7.0 CHANGELOG entry documenting TASK-246 through TASK-250 milestone

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-251
Goal: Add ?task= filter parity to GET /subtasks/export: currently GET /subtasks supports ?task= but GET /subtasks/export ignores it; wire filter + add tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-252
Goal: Wire ?name= server-side filter into renderSubtasks(): route non-status text from #subtasks-filter to server ?name= and include it in _updateSubtasksExportLinks hrefs

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-253
Goal: Add server-side ?status= filter to GET /branches (all-tasks view): currently client-only so pagination + filter don't compose; add ?status= parameter to backend + wire dashboard to use it + tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-254
Goal: Add GET /stalled multi-task cross-branch regression test: verify stall detection works correctly when stalled subtasks exist across multiple tasks and branches

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-255
Goal: Add task quick-filter UI to Subtasks tab: a text input that filters subtasks by task name server-side via ?task= parameter, wired into pollSubtasks and export links

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-256
Goal: Add #branches-task-filter input to Branches tab: wires to pollBranches with ?task=X server-side filter (parity with subtasks task filter)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-257
Goal: Add v4.8.0 CHANGELOG entry documenting TASK-251 through TASK-257

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-258
Goal: Add GET /branches/export endpoint: CSV and JSON download for branch data, supports same ?task= and ?status= filters as GET /branches, with Content-Disposition attachment header

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-259
Goal: Add #subtasks-branch-filter input to Subtasks tab: wires to pollSubtasks with ?branch=X server-side filter, composes with existing name/status/task filters

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-279
Goal: Export tab: add Stalled Subtasks row linking to /subtasks/export?min_age=X&status=running where X = configured STALL_THRESHOLD from GET /stalled response

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-280
Goal: Dashboard header stalled badge: show worst-offending branch name in title tooltip when stalled > 0 (e.g. 'N stalled — worst: task/branch (count)')

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-281
Goal: GET /history/export: add ?task= substring filter (parity with GET /history); 3+ new tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-282
Goal: Discord /subtasks slash command: mirrors /branches structure — lists all subtasks with optional ?task= and ?status= filters; 5+ new tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-283
Goal: CHANGELOG v5.3.0: document TASK-278 through TASK-282 (branches clear button, export stalled row, stalled badge tooltip, history/export task filter tests, Discord /subtasks command)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-284
Goal: History tab export links sync with active task/branch/status filters: update export-tab-history-csv/json hrefs on switchTab('export') to include ?task=, ?branch=, ?status= when set in the History tab

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-285
Goal: Discord /subtasks export:True — send full CSV file attachment (parity with /branches export:True); _subtasks_to_csv() formatter + 5+ tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-286
Goal: GET /stalled: add ?task= substring filter to restrict stalled results to one task; 3+ new tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-287
Goal: CHANGELOG v5.4.0: document TASK-283 through TASK-286 (changelog, history export fix, subtasks CSV export, stalled task filter)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-288
Goal: GET /stalled: add ?branch= substring filter (parity with ?task=); 3+ new tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-289
Goal: Stalled tab: add task filter input that re-fetches GET /stalled?task=X on change; clears on empty; mirrors subtasks tab filter UX

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-290
Goal: Discord /stalled: add optional task: and branch: params that forward to GET /stalled?task=X&branch=Y; update _format_stalled to accept task_filter/branch_filter; 4+ new tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-291
Goal: CHANGELOG v5.5.0: document TASK-287 through TASK-290 (stalled filters, Stalled tab task input, Discord /stalled filters)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-292
Goal: Stalled tab: add #stalled-branch-filter input (parity with #stalled-task-filter); wires to ?branch= on GET /stalled; window._applyStalledBranchFilter exposed

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-293
Goal: Discord /history slash command: add optional task:, branch:, status: filter params forwarded to _format_history; update formatter to accept and apply filters; 4+ new tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-294
Goal: GET /branches/export ?format=json: verify JSON response wraps rows in {total, branches:[...]} object instead of bare array; fix if needed and add tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-295
Goal: CHANGELOG v5.6.0: document TASK-291 through TASK-294 (stalled branch filter, Stalled tab UX, Discord /history filters, branches export tests)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-296
Goal: GET /subtasks/export ?format=json: verify wrapper shape {total,page,limit,pages,subtasks:[...]}; add ?status=review and ?status=pending filter tests; 4+ new tests

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-297
Goal: Stalled tab: show active filter label (e.g. 'task: X · branch: Y') below the filter inputs when either is set; updates after each poll

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-298
Goal: GET /branches: verify ?status=review and ?status=pending filter work correctly; add 3+ tests (parity with GET /branches/export filter tests)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-299
Goal: Discord plain-text subtasks command: add 'subtasks' to bot.py _handle_text_command dispatch; support optional task= and status= filters; reuse _format_subtasks from bot_formatters.py; 3+ new tests in test_bot.py

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-300
Goal: CHANGELOG v5.7.0: 300-task milestone entry covering TASK-295..299; include task count, API test count (591), Discord test count (298), and architecture highlights

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-301
Goal: GET /branches: add review_pct field (percentage of subtasks in Review state per branch, parity with pct/verified%); 3+ new tests in TestBranches

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-302
Goal: Dashboard Stalled tab: add '✕ Clear' button shown when _stalledTaskFilter or _stalledBranchFilter is active; clicking clears both filters and re-polls; parity with Branches/Subtasks tabs

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-303
Goal: Discord /branches slash command: add export:bool=False param; when True sends _branches_to_csv() as CSV file attachment (parity with /subtasks export:True); 4 new tests in TestHandleBranchesSlash or similar

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-305
Goal: GET /stalled: add ?min_age=N filter to return only Running subtasks stalled >= N steps; reuse min_age pattern from GET /subtasks; 3 new tests in TestStalled

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-306
Goal: Dashboard Export tab: update stalled export hrefs to use ?min_age=<threshold> (dynamically fetched from GET /stalled); update #export-stalled-threshold label to show the active threshold value

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-307
Goal: Discord /stalled slash command: add min_age:int=0 param; when >0, passes ?min_age=N to GET /stalled API call and includes note in output; 3 new tests in TestFormatStalled or similar

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-308
Goal: GET /branches: add pending_pct field (% pending subtasks per branch, parity with pct and review_pct); 3 new tests in TestBranches

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-309
Goal: Dashboard Branches tab: add review_pct column to the per-branch table alongside pct (verified%); UI-only, no new API tests needed

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-310
Goal: CHANGELOG v5.8.0: document TASK-301..309; include task count (310), API tests (600), Discord tests (305); tag v5.8.0

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-320
Goal: StructuredLoggingMigration — replace executor print() calls with Python logging; emit structured JSON events per step for SLO measurement

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-321
Goal: PromptVersionControl — create docs/PROMPT_REGISTRY.md with versioned snapshot of all prompt templates; add hash-based regression test to detect prompt drift across releases

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-322
Goal: CliGodFileRefactor spike — design doc for splitting solo_builder_cli.py; implement SecurityHeadersMiddleware (Flask X-Frame-Options, CSP, HSTS) and ApiRateLimiting as the concrete cycle-2 deliverables

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions
