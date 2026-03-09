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
