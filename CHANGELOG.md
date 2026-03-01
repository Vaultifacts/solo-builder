# Changelog

All notable changes to Solo Builder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
