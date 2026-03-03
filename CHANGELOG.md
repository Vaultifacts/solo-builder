# Changelog

All notable changes to Solo Builder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
