# Task Queue

## TASK-001
Goal: Create the first real end-to-end workflow task for this repo that is small but meaningful.

Constraints:
- Must exercise Research -> Architect -> Dev -> Auditor loop.
- Must touch only a few files.
- Must have clear acceptance criteria that can be validated by audit_check.

Acceptance Criteria:
- `claude/HANDOFF_ARCHITECT.md` contains a research handoff for `TASK-001` with at least one evidence-backed hypothesis and one explicit unknown.
- `claude/HANDOFF_DEV.md` contains an implementation plan for `TASK-001` with an `Allowed changes` section listing exact file paths.
- `claude/allowed_files.txt` can be generated from `HANDOFF_DEV.md` by running `pwsh tools/extract_allowed_files.ps1` without error.
- `pwsh tools/audit_check.ps1` exits with code 0 after task handoff files are prepared.

Priority: High

## TASK-002
Goal: Repair the `dev_gate` blocker caused by a syntax/runtime error in `tools/secret_scan.ps1`.

Constraints:
- Scope limited to guardrail reliability.
- Fix must remain PowerShell 5.1 compatible.
- No behavior expansion beyond correcting the broken guard execution path.

Acceptance Criteria:
- `pwsh tools/secret_scan.ps1` runs without syntax/parsing errors.
- `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail` proceeds past `secret_scan.ps1` on a clean staging set.
- No files outside TASK-002 allowed scope are modified for the fix.

Priority: Urgent

## TASK-003
Goal: Make `tools/precommit_gate.ps1` non-blocking by default and robust on Windows.

Constraints:
- Scope limited to `tools/precommit_gate.ps1`.
- Keep behavior deterministic and PowerShell 5.1 compatible.
- Do not run optional Python/unittest commands from precommit gate.

Acceptance Criteria:
- If no safe fast command is available, `precommit_gate` exits 0 with guidance.
- `precommit_gate` runs at most one safe fast command (name-filtered and timeout <= 300s).
- `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail` no longer fails in `precommit_gate` due optional unittest execution.

Priority: Urgent

## TASK-004
Goal: Identify exactly which command mutates `solo_builder/config/settings.json` and why.

Acceptance criteria:
- A minimal reproduction sequence (exact commands, in order)
- Evidence: before/after diff summary
- Recommendation: one of (ignore file, stop tool from writing, redirect writes elsewhere)

## TASK-005
Goal: Identify which verification sub-command executed by `tools/audit_check.ps1` writes `solo_builder/config/settings.json`, and eliminate or isolate that write.

Acceptance criteria:
- Exact mutating sub-command identified
- Minimal reproduction sequence documented
- Recommendation for fix path:
  - stop command from writing config, or
  - redirect writes to temp/state file, or
  - mock/isolate config in tests

## TASK-006
Goal: Identify the next remaining unittest path outside `solo_builder/api/test_app.py` that mutates `solo_builder/config/settings.json` during `python -m unittest discover`.

Acceptance criteria:
- exact mutating test module/class/function identified (not just unittest-discover generically)
- minimal reproduction sequence documented
- before/after evidence captured
- recommendation for the next minimal fix path

## TASK-007
Goal: Isolate and eliminate the remaining config writer path in `solo_builder.discord_bot.test_bot`, with primary focus on `TestHandleTextCommandExtra.test_set_trigger_consumed_by_cli` and directly related fixture/setup code.

Acceptance criteria:
- exact remaining mutating test method/class confirmed
- minimal reproduction sequence documented
- recommendation for the smallest fix path
- no change to production code yet unless absolutely required

## TASK-008
Goal: Fix one existing failing unittest by making CLI status output robust on Windows console encoding paths.

Acceptance criteria:
- Running `python -m unittest solo_builder.discord_bot.test_bot.TestAddTaskInlineSpec` no longer fails due to UnicodeEncodeError from CLI output formatting.
- Running `python -m unittest solo_builder.discord_bot.test_bot.TestAddBranchInlineSpec` no longer fails due to UnicodeEncodeError from CLI output formatting.
- Verification includes `pwsh tools/audit_check.ps1` and no mutation of `solo_builder/config/settings.json`.

Constraints:
- Keep scope narrow
- Prefer touching as few files as possible
- No unrelated refactors

## TASK-009
Goal: Fix the remaining optional unittest UnicodeEncodeError in the `_cmd_undo` output path.

Acceptance criteria:
- The affected unittest no longer fails with UnicodeEncodeError.
- `pwsh tools/audit_check.ps1` passes.
- No mutation of `solo_builder/config/settings.json`.

Constraints:
- Keep scope narrow
- Prefer touching as few files as possible
- No unrelated refactors

## TASK-011
Goal: Fix `tools/extract_allowed_files.ps1` heading parsing so allowed file lists are extracted reliably from `HANDOFF_DEV.md`.

Acceptance criteria:
- `pwsh tools/extract_allowed_files.ps1` produces `claude/allowed_files.txt` when `HANDOFF_DEV.md` uses common heading styles.
- Heading variants including `## Allowed changes` and `Allowed files` are parsed correctly.
- Existing workflow behavior remains unchanged outside extraction robustness.

Constraints:
- Modify only `tools/extract_allowed_files.ps1`.
- No product-code changes.

## TASK-012
Goal: Normalize workflow handoff heading schema so tooling can rely on a consistent section format.

Acceptance criteria:
- Handoff files use a canonical heading schema:
  - ## Allowed changes
  - ## Files that must not be modified
  - ## Acceptance criteria
  - ## Verification commands
- Existing workflow behavior remains unchanged.
- tools/extract_allowed_files.ps1 continues to work with the canonical schema.
- No product-code changes are introduced.

Constraints:
- Modify only workflow documentation and prompt templates if needed.
- Do not modify product code under solo_builder/*.
- Do not change orchestrator or workflow state semantics.
- Preserve deterministic task workflow conventions.

## TASK-013
Goal: Add a single authoritative `claude/NEXT_ACTION.md` file generated by the orchestrator so agents can read one deterministic next-step contract.

Acceptance criteria:
- `tools/claude_orchestrate.ps1` writes `claude/NEXT_ACTION.md` on each orchestrator run.
- `NEXT_ACTION.md` includes current task, phase, role, required reads, allowed operation, and key rules.
- Existing workflow semantics remain unchanged.
- `STATE.json` remains the machine-readable source of workflow state.
- No product-code changes are introduced.

Constraints:
- Modify only workflow scripts/docs/templates needed for NEXT_ACTION generation and consumption.
- Do not modify product code under `solo_builder/*`.
- Do not change task lifecycle semantics.
- Preserve deterministic workflow conventions.

## TASK-014
Goal: Add consistency verification between claude/STATE.json and claude/NEXT_ACTION.md so the workflow fails fast if rendered agent-facing state drifts from machine state.

Acceptance criteria:
- A workflow verification step checks consistency between claude/STATE.json and claude/NEXT_ACTION.md for:
  - task_id / Task
  - phase / Phase
  - next_role / Role
- The check exits nonzero on mismatch.
- audit_check.ps1 runs this check directly or via a dedicated helper script.
- Existing workflow semantics remain unchanged.
- No product-code changes are introduced.

Constraints:
- Modify only workflow scripts/docs needed for consistency verification.
- Do not modify product code under solo_builder/*.
- Do not change task lifecycle semantics.
- Preserve deterministic workflow conventions.

## TASK-015
Goal: Fix post-close role rendering mismatch in tools/claude_orchestrate.ps1 so phase=done renders the correct terminal next role.

Acceptance criteria:
- When workflow state is done, claude_orchestrate.ps1 renders the correct terminal next role consistently.
- Orchestrator output matches the intended post-close state after advance_state.ps1 sets done/ARCHITECT.
- Existing workflow semantics remain unchanged outside this role-rendering fix.
- No product-code changes are introduced.

Constraints:
- Modify only tools/claude_orchestrate.ps1 and any minimal workflow files needed for verification.
- Do not modify product code under solo_builder/*.
- Do not change task lifecycle semantics.
- Preserve deterministic workflow conventions.

## TASK-016
Goal: Add claude/WORKFLOW_SPEC.md as the canonical written specification for the Solo Builder deterministic workflow.

Acceptance criteria:
- claude/WORKFLOW_SPEC.md exists and documents:
  - task lifecycle
  - branch lifecycle
  - workflow phases and roles
  - closeout procedure
  - merge-first baseline rule
  - local-only runtime artifact handling
- The spec matches the workflow currently enforced in the repo.
- No workflow semantics are changed by this task.
- No product-code changes are introduced.

Constraints:
- Modify only workflow documentation files needed for the specification.
- Do not modify product code under solo_builder/*.
- Do not change orchestrator, state-machine, or task lifecycle semantics.
- Preserve deterministic workflow conventions.

## TASK-017
Goal: Add tools/workflow_preflight.ps1 to enforce baseline workflow safety checks before initializing a new task.

Acceptance criteria:
- tools/workflow_preflight.ps1 fails if the current branch is not clean.
- tools/workflow_preflight.ps1 fails if runtime artifacts are still dirty (claude/allowed_files.txt, claude/verify_last.json).
- tools/workflow_preflight.ps1 verifies STATE.json and NEXT_ACTION.md consistency by invoking tools/check_next_action_consistency.ps1.
- tools/workflow_preflight.ps1 verifies the repo is on a safe baseline for new task initialization (master contains the previous task branch).
- tools/workflow_preflight.ps1 exits 0 only when the repo is safe for next-task initialization.
- No workflow semantics are changed.
- No product-code changes are introduced.

Constraints:
- Modify only workflow scripts/docs needed for preflight enforcement.
- Do not modify product code under solo_builder/*.
- Do not change task lifecycle semantics.
- Preserve deterministic workflow conventions.

## TASK-018
Goal: Integrate `workflow_preflight.ps1` into the deterministic task initialization workflow so that preflight checks automatically run before any new task branch is created.

Acceptance criteria:
- `tools/workflow_preflight.ps1` runs automatically before new task initialization.
- Task initialization fails if preflight returns a non-zero exit code.
- Preflight execution occurs after switching to `master` but before creating `task/TASK-<N>`.
- Existing workflow semantics remain unchanged.
- No product code under `solo_builder/*` is modified.
- The deterministic workflow lifecycle remains:
  - task branch -> work -> verify -> close -> merge to master -> preflight -> new task branch

Constraints:
- Modify only workflow scripts or documentation required to integrate the preflight check.
- Do not change the task lifecycle or role transitions.
- Do not modify product code.
- Preserve deterministic workflow conventions.

## TASK-019
Goal: Design CI integration for Solo Builder workflow invariants (state consistency, preflight checks, and verification contract enforcement).

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-020
Goal: Add automated validation that workflow contracts reference only existing tools/scripts.

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-021
Goal: Fix pre-existing test_stalled_shows_stuck failure so optional unittest verification is clean.

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-022
Goal: Integrate workflow_contract_check.ps1 into workflow_preflight.ps1 so workflow contract drift is caught before task initialization.

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-023
Goal: Isolate test_stalled_empty from live config

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-024
Goal: Atomic STATE.json write in advance_state.ps1

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-025
Goal: Add -DryRun flag to claude_heal.ps1

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-026
Goal: Extract 5 clean agents to solo_builder/agents/

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-027
Goal: Extract ClaudeRunner, AnthropicRunner, SdkToolRunner, and Executor from solo_builder_cli.py into solo_builder/runners/ package

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-028
Goal: Add targeted unit tests for solo_builder/agents/ and solo_builder/runners/ packages

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-029
Goal: Add disk-backed response cache to AnthropicRunner; add CLAUDE_LOCAL=1 routing to Executor

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-030
Goal: Add hit/miss tracking to ResponseCache and a standalone cache-stats script

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-031
Goal: Log ResponseCache hit/miss stats to JOURNAL.md at CLI exit for observability

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-032
Goal: Add interactive cache stats CLI command so users can query hit/miss/size without exiting

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-033
Goal: Add 'cache' and 'cache clear' commands to Discord bot for remote cache stats visibility

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-034
Goal: Add agents/runners/cache unit tests to CI smoke-test.yml; fix stale test count comment

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-035
Goal: Add GET /cache and DELETE /cache endpoints to Flask API for dashboard cache observability

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-036
Goal: Add cache stats widget to dashboard.html: poll GET /cache, show entries/tokens, Clear button

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-037
Goal: Persist ResponseCache hit/miss stats to claude/cache/session_stats.json across CLI sessions; expose cumulative totals via GET /cache and dashboard Cache tab

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-038
Goal: Auto-scroll the dashboard journal tab to the bottom after each pollJournal() tick when the journal tab is active

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-039
Goal: Add GET /metrics/export endpoint returning CSV of step history and a Download CSV button in the dashboard Metrics tab

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-040
Goal: Surface cumulative hit rate in CLI cache command output and JOURNAL entries

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-041
Goal: Add show-more/collapse toggle to dashboard journal entries truncated beyond 300 chars

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-042
Goal: Extend GET /metrics/export to support ?format=json returning a JSON array; default remains CSV

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-043
Goal: Add GET /cache/history endpoint returning timestamped per-session stats accumulated in session_stats.json

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-044
Goal: Persist expanded journal entry state across ticks using a Set keyed by step-subtask so show-more stays open during live polling

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-045
Goal: Add ?limit=N query param to GET /metrics/export to cap returned rows (CSV and JSON both respect it)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-046
Goal: Add cache history tab to dashboard: poll GET /cache/history every tick and display a sessions table with per-session hits, misses, hit rate, and ended_at

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-047
Goal: Add ?since=step_index query param to GET /metrics/export: return only rows with step_index > since (both CSV and JSON)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-048
Goal: Add ?since=step_index query param to GET /history for incremental fetching (parity with /metrics/export)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-049
Goal: Batch: add ?since to /cache/history (049), incremental history polling in dashboard (050), cache history N-session dropdown (051)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-052
Goal: Batch: wire ?since to cache history polling (052), add /history/export endpoint (053), history tab client-side filter (054)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-055
Goal: Batch: history/export filter param (055), Export sidebar tab (056), GET /cache/export endpoint (057)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-058
Goal: Batch: history filter in export links (058), ?task/?branch on GET /history (059), metrics sparkline chart (060)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-061
Goal: Batch: /history pagination ?page=N (061), Export tab filter sync (062), dashboard favicon status badge (063)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-064
Goal: Batch: history pager UI (064), /history/count endpoint (065), stalled favicon yellow (066)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-067
Goal: Batch: wire /history/count to dashboard (067), j/k history pager shortcuts (068), stale-data banner (069)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-070
Goal: Batch: History tab unread badge (070), /status latency display (071), keyboard shortcut help overlay (072)

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-073
Goal: Batch: dashboard polling pause/resume button (073), subtask detail modal on history row click (074), GET /settings endpoint + dashboard settings panel (075)

Acceptance criteria:
- TASK-073: A Pause/Resume button in the dashboard header freezes all tick() polling when paused; tick() restarts on resume; button label toggles between Pause and Resume.
- TASK-074: Clicking a row in the History tab opens a modal showing subtask name, task, branch, status, step, and full output text; modal closes on Esc or a close button.
- TASK-075: GET /settings returns current config/settings.json as JSON; a new Settings tab in the dashboard polls it and displays all keys as a read-only table.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-076
Goal: Batch: GET /subtask/<id> endpoint (076), dashboard subtask search bar across all tabs (077), task completion webhook POST with summary payload (078)

Acceptance criteria:
- TASK-076: GET /subtask/<subtask_id> returns current status, output, history, task, branch for a named subtask (e.g. "A1"); 404 if not found.
- TASK-077: A global search input in the header filters the task list (main panel) by task name/status; clears on Escape.
- TASK-078: When all subtasks reach Verified, POST /webhook (if WEBHOOK_URL is set) with JSON {event:"complete", step, total, verified, pct, timestamp}; returns 200 with {ok, sent}.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-079
Goal: Batch: GET /subtask/<id>/output raw text endpoint (079), dashboard auto-webhook on completion (080), POST /webhook button in Export tab (081)

Acceptance criteria:
- TASK-079: GET /subtask/<id>/output returns the subtask output as plain text (Content-Type: text/plain); 404 if subtask not found.
- TASK-080: When pollStatus() detects complete=true for the first time (transition from false→true), the dashboard automatically fires POST /webhook and shows a toast notification.
- TASK-081: Export tab has a "Fire Webhook" button that calls POST /webhook and shows the response (ok/reason) as inline feedback; button is disabled when WEBHOOK_URL is not configured.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-082
Goal: Batch: GET /tasks/export full DAG JSON download (082), history branch filter UI in dashboard (083), dashboard poll interval selector (084)

Acceptance criteria:
- TASK-082: GET /tasks/export returns the full DAG as a JSON file download (Content-Disposition: attachment; filename=dag.json); includes all tasks, branches, subtasks, statuses, and outputs.
- TASK-083: History tab gains a branch filter input alongside the existing text filter; both compose (AND); branch filter syncs into /history/export hrefs and export tab links.
- TASK-084: A poll-interval dropdown in the header lets the user select 2s/5s/10s/30s; changes POLL_MS live (clears and restarts setInterval); selected value persists in localStorage.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-085
Goal: Batch: GET /branches summary endpoint (085), dashboard branch detail drill-down in Branches tab (086), GET /subtasks list endpoint with filter params (087)

Acceptance criteria:
- TASK-085: GET /branches returns a flat list of all branches across all tasks: [{task, branch, total, verified, running, pending, pct}]; supports ?task= filter.
- TASK-086: Branches tab in dashboard polls GET /branches (already exists structurally); renders a table with task/branch/progress bar/counts; clicking a row loads that task's detail panel.
- TASK-087: GET /subtasks returns a flat list of all subtasks: [{subtask, task, branch, status, output_length}]; supports ?task=, ?branch=, ?status= filters; ?output=1 includes full output field.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-088
Goal: Batch: GET /subtasks/export CSV/JSON (088), dashboard Subtasks sidebar tab (089), GET /timeline/<subtask> enhanced response with branch/task context (090)

Acceptance criteria:
- TASK-088: GET /subtasks/export returns all subtasks as CSV (default) or JSON (?format=json); supports same ?task=, ?branch=, ?status= filters as GET /subtasks; CSV columns: subtask,task,branch,status,output_length.
- TASK-089: New "Subtasks" sidebar tab polls GET /subtasks every tick; renders a filterable table with subtask/task/branch/status/output_length columns; clicking a row opens the subtask detail modal.
- TASK-090: GET /timeline/<subtask> currently returns basic history; enhance to also return task, branch, current status, current output, and description fields alongside existing history array.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-091
Goal: Batch: GET /metrics endpoint (091), live step counter widget in dashboard header (092), dark/light theme toggle for dashboard SPA (093)

Acceptance criteria:
- TASK-091: GET /metrics returns a JSON summary of run health: {step, total, verified, pending, running, review, stalled, pct, elapsed_s, steps_per_min}; sources data from state file and step history.
- TASK-092: Dashboard header displays a live step counter ("Step N / 70 — X verified") that updates every tick without a full page reload; counter reflects /status fields.
- TASK-093: A theme toggle button in the dashboard header switches between dark and light CSS variable sets; selection persists in localStorage as "sb-theme"; default remains dark.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-094
Goal: Batch: subtask timeline mini-chart in detail modal (094), POST /config/reset endpoint (095), GET /shortcuts endpoint (096)

Acceptance criteria:
- TASK-094: When the subtask detail modal opens, fetch GET /timeline/<id> and render an inline SVG sparkline of the subtask's status transitions (step on x-axis, status encoded as colour); displayed below the output field.
- TASK-095: POST /config/reset restores config/settings.json to its compiled-in defaults (same keys/values used at CLI startup); returns {ok, restored} with the resulting config; 409 if settings file is missing.
- TASK-096: GET /shortcuts returns a JSON array of {key, description} objects listing all active keyboard shortcuts; dashboard Keyboard Shortcuts modal table is rendered from this endpoint instead of being hardcoded.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-097
Goal: Batch: GET /health liveness probe (097), toast/notification history panel in dashboard (098), POST /subtask/<id>/reset endpoint (099)

Acceptance criteria:
- TASK-097: GET /health returns {ok, uptime_s, step, state_file_exists}; uptime_s is seconds since server start (Flask app_start_time); step is current step from state file; state_file_exists is true if STATE_PATH exists on disk.
- TASK-098: Dashboard maintains an in-memory list of the last 20 toast messages; a "Notifications" button in the header opens a panel showing each entry with timestamp, message, and type (info/warn/error); panel dismisses on Esc or button click.
- TASK-099: POST /subtask/<id>/reset writes a heal_trigger.json to reset the subtask to Pending; returns {ok, subtask, previous_status} with 404 if subtask not found; compose on existing heal infrastructure.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-100
Goal: Batch: GET /run/history step execution log (100), per-subtask tool override form in dashboard Settings tab (101), GET /dag/diff comparison endpoint (102)

Acceptance criteria:
- TASK-100: GET /run/history returns a list of the last N step-execution records from meta_history: [{step_index, verified, healed}]; supports ?limit=N and ?since=step_index params; mirrors /metrics/export but as JSON API.
- TASK-101: Dashboard Settings tab gains a "Tool override" form: subtask input + tools input + submit button that POSTs to /tools; form clears on success; feedback shown inline.
- TASK-102: GET /dag/diff?from=<step>&to=<step> compares two historical snapshots stored in state meta_history and returns list of subtasks that changed status between those two step indices; returns {from, to, changes:[{subtask, task, branch, from_status, to_status}]}.

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-103
Goal: Refactor solo_builder_cli.py: split the 2881-line monolith into focused modules (commands, auto-loop, triggers, IPC) to reduce file size, improve maintainability, and address architecture auditor large-file findings

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions

## TASK-104
Goal: Refactor solo_builder/api/app.py: split the large Flask app into focused modules (routes, auth, websocket, config endpoints) to reduce file size and address architecture auditor large-file findings

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions
