# Changelog

All notable changes to Solo Builder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v2.1.13] — 2026-03-02

### Added
- **`TestVerifyDescribeTools`** — 13 unit tests covering `_cmd_verify` (flip status,
  default note, unknown subtask, empty arg), `_cmd_describe` (sets description +
  Running, propagates to branch/task, missing text, unknown subtask), `_cmd_tools`
  (set list, clear to empty, requeue Verified, missing arg, unknown subtask)
- **`profiler_harness.py --dry-run`** — runs 3 steps then exits with PASS; asserts
  executor and planner patches fire; wired as CI step "Profiler dry-run"
- **CI step** — "Profiler dry-run (patch smoke test)" added to `smoke-test.yml`

### Fixed
- **`datetime.utcnow()` deprecation** — replaced with
  `datetime.now(datetime.timezone.utc)` in `_fire_completion` webhook error log
- **`TestFireCompletion` ResourceWarning** — class-level `subprocess.Popen` mock
  added to `setUp` prevents real `powershell.exe` spawns in non-notify tests;
  unclosed file handle in failure test closed with `with` block

### Changed
- **Test count** — 48 → 61; all clean (no warnings)
- **`smoke-test.yml` bot step label** — "(48 tests)" → "(61 tests)"
- **README CI table** — updated test count, functions list, added Profiler row

---

## [v2.1.12] — 2026-03-02

### Added
- **`test_notify_calls_popen_with_message`** — asserts `_fire_completion` launches
  `powershell.exe` with the correct `verified/total` and `steps` message via
  `subprocess.Popen` (mocked; no PowerShell required)
- **`TestCLICommands`** — 9 unit tests for `_cmd_add_task` and `_cmd_add_branch`:
  fallback subtask creation, Claude JSON decomposition, empty spec cancel,
  dependency wiring, unknown task usage, digit-arg resolution, max-branch limit,
  branch fallback, re-open Verified task. Total: **48 tests**, 2.4 s

### Changed
- **README CI table** — test count updated 38 → 48
- **`smoke-test.yml`** step label updated to "(48 tests)"

---

## [v2.1.11] — 2026-03-02

### Added
- **`TestFireCompletion`** — 3 unit tests for `_fire_completion` webhook logic:
  empty URL → no POST, correct payload/headers, failure → `webhook_errors.log`
  written. Total: **38 tests**, 1.1 s

### Changed
- **README CI table** — added Export and Webhook POST rows; updated bot test
  count from 21 → 35 → 38; added `_fire_completion` to covered functions list
- **`smoke-test.yml` step name** — "Run bot unit tests" annotated with "(38 tests)"

---

## [v2.1.10] — 2026-03-02

### Fixed
- **CI webhook test** — replaced full `--auto 99` subprocess (which never
  completed in time) with a direct `import solo_builder_cli; m._fire_completion()`
  call; test is now instant and deterministic

### Added
- **`--output-format json` `--export` integration** — JSON output now includes
  `"export": {"path": ..., "count": ...}` when `--export` is passed
- **`TestHandleTextCommand`** — 10 async unit tests covering every bot command
  (`status`, `run`, `auto N`, `stop`, `verify`, `help`); total **35 tests**, 0.07 s

### Changed
- **`_cmd_export` prints to `sys.stderr`** — all export progress/warnings now
  go to stderr so `--quiet` suppresses them and stdout stays clean for JSON
- **`_cmd_export` returns `(path, count)` tuple** — enables JSON mode to report
  export metadata
- **CONTRIBUTING.md** — added headless/scripted flags table; updated test count to 35
- **README** — updated CLI usage with `--export`, `--quiet`, `--output-format json`
  and `--webhook` examples

---

## [v2.1.9] — 2026-03-02

### Fixed
- **`_cmd_export` always writes the file** — previously returned early when
  no Claude outputs existed (`count == 0`), causing the CI export step to fail
  with "file not created". Now writes a header-only file with a placeholder note.

### Added
- **`--export` flag** — `python solo_builder_cli.py --headless --auto N --export`
  calls `_cmd_export()` after the run and exits; no stdin piping required
- **CI webhook smoke test** — `smoke-test.yml` starts a Python `http.server`
  in a background thread, runs `--auto 99 --no-resume --webhook <url>`,
  asserts the completion payload (`event=complete`) was received and
  `state/webhook_errors.log` was not created
- **`TestRunAuto` async test class** — 4 tests via `IsolatedAsyncioTestCase`
  covering: no-work → completion message; step advances → ticker + n-step
  summary; step timeout → warning; pipeline completes mid-run → completion
  message. Total: **25 tests**, 0.07 s

### Changed
- **CI export test** — now uses `--headless --export --no-resume --auto 2`
  instead of piping `y\nexport\nexit` to interactive mode; assertion
  lowered to `size > 30` (header-only export is ~150 bytes)

---

## [v2.1.8] — 2026-03-03

### Added
- **`review_mode_demo.gif`** — 126-frame animated GIF (monokai theme) showing
  the full REVIEW_MODE workflow: `set REVIEW_MODE=true` → `run` → Review subtasks
  appear → `verify` advances them → Verified; embedded in README Development section
- **CI export test** — `smoke-test.yml` step pipes `export\nexit` to CLI after
  the 10-step run; asserts `solo_builder_outputs.md` exists and is > 100 bytes

### Fixed
- **Webhook failures now logged** — `_fire_completion` `except Exception: pass`
  was silently swallowing all POST errors; failures are now appended to
  `state/webhook_errors.log` with UTC timestamp (stays auditable, never interrupts
  the user, gitignored via `state/`)

---

## [v2.1.7] — 2026-03-03

### Added
- **`CONTRIBUTING.md`** — four-tier executor routing table, DAG structure,
  how to add CLI commands, commit style guide
- **README Development section** — CI test table, profiler usage, priority cache
  architecture note, REVIEW_MODE usage example; version badge bumped to 2.1.6

### Changed
- **CI smoke test** — `Run bot unit tests` step added
  (`PYTHONIOENCODING=utf-8 python discord_bot/test_bot.py`)

---

## [v2.1.6] — 2026-03-03

### Fixed
- **Priority cache stale after task unlock** — when Task 0 completes
  mid-interval, Tasks 1–5 were invisible to the executor until the next
  5-step cache refresh, causing wasted steps. The Planner cache now also
  refreshes immediately whenever the count of fully-Verified tasks increases
  (task-level, not subtask-level — negligible overhead)
- **Dice-roll fallback ignores REVIEW_MODE** — both dice-roll paths in
  `execute_step` hardcoded `"Verified"` regardless of `self.review_mode`.
  Now consistent with the SDK/Claude paths: uses `"Review"` when
  `REVIEW_MODE=True` and skips `_roll_up` so the gate is actually enforced

### Changed
- **CI smoke test** — all three new test steps now pass (green ✅):
  - 10-step headless run asserts `>= 15` verified; prints per-task breakdown
  - stop_trigger startup-cleanup: asserts trigger consumed + any subtask
    Running/Verified (corrected from `>= 1 Verified`, which wasn't reachable
    in 1 step)
  - REVIEW_MODE step: works end-to-end with the dice-roll fix
- **Bot unit tests** (`discord_bot/test_bot.py`) — 21 tests, 0.03 s,
  no Discord connection; covers `_has_work`, `_format_status`,
  `_auto_running`, `_read_heartbeat`, `_format_step_line`, `_load_state`

---

## [v2.1.5] — 2026-03-03

### Fixed
- **Priority cache stale after task unlock** (initial fix — superseded by v2.1.6)
- **Force-save on pipeline completion** — `save_state(silent=True)` called
  before `_fire_completion()` so JSON is always current when bot reads it

### Added
- `discord_bot/test_bot.py` — 21 unit tests (see v2.1.6 above)

---

## [v2.1.4] — 2026-03-03

### Fixed
- **Force-save on pipeline completion** — `save_state(silent=True)` called
  immediately before `_fire_completion()` in `_cmd_auto` so the JSON is
  always up-to-date by the time the Discord bot reads it — eliminates the
  stale-count root cause

### Added
- `discord_bot/test_bot.py` — 21 unit tests covering bot helper functions,
  no Discord connection required; run with `python discord_bot/test_bot.py`

### Changed
- **CI smoke test** — `python-dotenv` added to pip install; headless run
  bumped to `--auto 10`, assertion `>= 15`; REVIEW_MODE and stop_trigger
  steps added (full green reached in v2.1.6)

---

## [v2.1.3] — 2026-03-03

### Fixed
- **Stale completion summary (100%)** — `_run_auto` now waits up to **30 s** (was 6 s)
  for the auto-save JSON to reflect all-Verified; if JSON still lags, falls back to
  `step.txt` heartbeat data for the final counts so the completion message always
  shows the correct 70/70 instead of 69/70

### Changed
- **CI smoke test** (`smoke-test.yml`) — three improvements:
  - `python-dotenv` added to `pip install` (it is now a declared dependency)
  - Headless run bumped from `--auto 3` → `--auto 5`; assertion raised from
    `>= 6` → `>= 12` verified subtasks
  - New **stop_trigger startup-cleanup** step: plants a stale `state/stop_trigger`
    before the CLI starts, then asserts the trigger was silently consumed and the
    pipeline still advanced at least one step

---

## [v2.1.2] — 2026-03-03

### Fixed
- **`on_ready` log buffering** — added `flush=True` to both `print()` calls in
  `SoloBuilderBot.on_ready`; the ready message now appears immediately when the
  bot runs redirected to a file instead of sitting in the stdout buffer
- **Stale `run_trigger` cleared on startup** — symmetrical with the
  `stop_trigger` cleanup added in v2.1.1; both stale triggers are now removed
  together in a single loop at `main()` startup

### Changed
- `python-dotenv>=1.0` added to `requirements.txt` and `pyproject.toml`
  `[project.dependencies]` — it was already a de-facto dependency for `.env`
  loading in both the CLI and the Discord bot but was not declared

---

## [v2.1.1] — 2026-03-03

### Added
- **Auto-run indicator in `/status`** — when a bot auto-run is in progress,
  status replies append `▶ Auto-run in progress — use stop to cancel`
  (both plain-text and `/status` slash command)

### Fixed
- **Stale `stop_trigger` cleared on startup** — a leftover `state/stop_trigger`
  from a crashed or interrupted run would silently halt the very first `auto`
  command. CLI now removes it during `main()` startup before acquiring the
  lockfile.

### Changed
- Version bumped to **2.1** in `pyproject.toml` and CLI splash banner

---

## [v2.1] — 2026-03-03

### Added
- **Discord bot** (`discord_bot/bot.py`) — replaces Telegram integration;
  supports both slash commands and plain-text (no `/` prefix required)
- **Natural language commands** — `status`, `run`, `auto [n]`, `stop`,
  `verify <ST> [note]`, `export`, `help` all work without a `/` prefix
- **Two-way chat logging** — every user message and every bot reply is
  appended to `discord_bot/chat.log` with UTC timestamp, channel, and author
- **Per-step progress tickers** — during `auto` runs the bot posts a one-line
  ticker after each step: `Step N — X✅ Y▶ Z⏸ W⏳ / 70 (pct%)`
- **Heartbeat file** (`state/step.txt`) — CLI writes
  `step,verified,total,pending,running,review` after every step so the bot
  always reads live counters instead of the 5-step-stale JSON
- **`stop` / `/stop` command** — two-layer stop: cancels the bot's `_run_auto`
  asyncio task AND writes `state/stop_trigger`; CLI checks the trigger in the
  inter-step delay window and halts after the current step completes
- **Duplicate auto guard** — `_auto_task` module variable tracks the running
  coroutine; a second `auto`/`/auto` while one is active replies with a
  warning instead of spawning a second concurrent run

### Fixed
- **`verify_trigger` blocked by `run_trigger`** — CLI auto loop previously
  checked `run_trigger` first and broke immediately, skipping any pending
  `verify_trigger.json`. Now `verify_trigger` is processed before the
  `run_trigger` break, so Discord verify commands work during active auto runs.
- **Stale completion summary** — `_run_auto` now waits up to 6 s for the
  auto-save JSON flush before posting the final `✅ Pipeline complete` message,
  eliminating the "69/70" count that appeared when the JSON hadn't caught up.
- **`SdkToolRunner` rate limit retry** — `arun` retries up to 3× on
  `anthropic.RateLimitError` with exponential backoff (5 s → 10 s → 20 s,
  capped at 60 s). Root cause: O1's large state-file read hit rate limits
  during high-concurrency runs and previously silently left the subtask stuck.
- **Dice-roll escape for failed tool subtasks** — when `SdkToolRunner` fails
  and `ClaudeRunner` subprocess is unavailable, a `verify_prob` dice roll is
  applied so tools-bearing subtasks don't stay blocked in `Running` indefinitely.

---

## [v2.0.1] — 2026-03-02

### Fixed
- **CI `NameError` on import** — `PdfPages` was used as a type annotation in
  `solo_builder_live_multi_snapshot.py` but is only imported under a
  `try/except ImportError` block for matplotlib. Without matplotlib installed
  (CI only installs `anthropic flask`), Python evaluated the annotation at
  import time and raised `NameError`. Added `from __future__ import annotations`
  to make all annotations lazy — resolves all 13 CI smoke-test failures.

### Changed
- `_PROJECT_CONTEXT` constant prepended to every Claude prompt so responses
  always know they are working within Solo Builder — eliminates "I don't know
  what Solo Builder is" replies when subtask descriptions lack project context.
  Applied to both the `AnthropicRunner` (no-tools) path and the
  `SdkToolRunner` (tool-use) path via `_gather_sdktool`.
- Splash banner and `pyproject.toml` version bumped to **2.0.1**.

---

## [v2.0] — 2026-03-01

### Milestone — production-ready async SDK pipeline

**Summary:** Full async Anthropic SDK integration, live web dashboard with
export/auto-run, profiler harness, human-gate `verify` command, and
`--headless` flag for scripted use.

### Added
- `--headless`, `--auto N`, `--no-resume` CLI flags for non-interactive /
  CI use (`python solo_builder_cli.py --headless --auto 50 --no-resume`)
- `POST /export` Flask endpoint — regenerates `solo_builder_outputs.md` from
  live DAG state without needing the CLI
- `GET /export` Flask endpoint — download previously generated export file
- Dashboard "⬇ Export" button (uses `POST /export`)
- Dashboard "⏩ Auto N" button with step-count input
- Dynamic `<title>` — updates to `Solo Builder — Step N (pct%)` on each poll
- `profiler_harness.py` — standalone async performance benchmark; patches both
  `arun` (async) and `run` (sync) paths; full concurrency/timing report
- Smoke Test CI badge in `README.md`
- `CHANGELOG.md` (this file)

### Changed
- Async gather helpers promoted from per-call closures to
  `Executor._gather_sdk` / `Executor._gather_sdktool` class-level
  `@staticmethod` — eliminates function allocation per step
- Smoke Test assertion raised from `>= 3` to `>= 6` verified subtasks
- Splash banner updated to v2.0

---

## [v1.7] — 2026-02-28

### Added
- `POST /export` endpoint (regenerate export from state on demand)
- Dynamic dashboard `<title>` reflecting current step and completion %
- `Executor._gather_sdk` and `_gather_sdktool` as `@staticmethod` methods

### Changed
- Export button switched from `GET` to `POST /export`
- Smoke Test threshold raised to `>= 6`

---

## [v1.6] — 2026-02-28

### Fixed
- **Python 3.13 asyncio compat** — `asyncio.run(asyncio.gather(...))` raises
  `ValueError` because `gather()` returns `_GatheringFuture`, not a coroutine.
  Wrapped both SDK gather calls in `async def` helpers.

### Added
- `profiler_harness.py` updated to patch async `arun` paths (before/after
  count approach, module-level monkey-patching)

---

## [v1.5] — 2026-02-27

### Added
- **Async SDK calls** — `AnthropicRunner` and `SdkToolRunner` each gain an
  `arun()` async method; `Executor.execute_step` uses `asyncio.gather` for
  parallel subtask execution instead of `ThreadPoolExecutor`
- `anthropic.AsyncAnthropic` client stored alongside sync client
- `GET /export` Flask endpoint — serve `solo_builder_outputs.md` as download
- Dashboard "⬇ Export" button

---

## [v1.4] — 2026-02-27

### Changed
- `EXECUTOR_MAX_PER_STEP` tuned to **6** (optimal sweet spot, −41% wall time
  vs baseline; 8 was slower due to subprocess cost at fan-out boundary)

---

## [v1.3] — 2026-02-27

### Added
- **AnthropicRunner** — direct Anthropic SDK runner for subtasks without tools
  (activated when `ANTHROPIC_API_KEY` is set, no subprocess required)
- **SdkToolRunner** — SDK-based tool-use runner (Read, Glob, Grep) for
  subtasks that previously required the `claude` CLI subprocess
- `verify <ST> [note]` command — human gate to hard-set any subtask Verified
- `journal.md` added to `.gitignore` (generated output, grows every run)
- `ANTHROPIC_MODEL` and `ANTHROPIC_MAX_TOKENS` config keys
- `BLUE` ANSI colour for SDK execution lines

### Changed
- Three-tier execution routing: ClaudeRunner → AnthropicRunner → dice roll

---

## [v1.2] — 2026-02-26

### Added
- `profiler_harness.py` (initial version) — baseline timing at MAX_PER_STEP=2

### Changed
- `EXECUTOR_MAX_PER_STEP` default raised from 2 → 4 (−34% wall time)
- Planner: Running subtasks get base risk 1000+ to always beat Pending
  (fixes priority inversion that could stall in-flight subtasks)

---

## [v1.1] — 2026-02-25

### Added
- **Process lockfile** (`state/solo_builder.lock`) — prevents two CLI
  instances from corrupting the shared state file
- `auto-save` every `AUTO_SAVE_INTERVAL` steps (default 5)
- `journal.md` auto-created under configured `JOURNAL_PATH`

---

## [v1.0] — 2026-02-24

### Initial release

- Seven-task diamond DAG (Task 0 → Tasks 1–5 → Task 6), 70 subtasks total
- Six AI agents: Planner, ShadowAgent, SelfHealer, Executor, Verifier,
  MetaOptimizer
- Interactive CLI with `run`, `auto`, `reset`, `save`, `load`, `describe`,
  `tools`, `output`, `export`, `snapshot`, `set`, `help`, `exit`
- Flask REST API (`/status`, `/tasks`, `/journal`, `/run`)
- Dark-theme live dashboard polling every 2 s
- PDF 4-page snapshots via matplotlib
- State persistence (`state/solo_builder_state.json`)
- GitHub Actions Smoke Test CI
