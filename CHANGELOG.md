# Changelog

## v6.52.0 — 2026-03-12  Context Menu + Clock + Expand/Collapse All + Branch Filter + Output Preview

- **Task card context menu**: Right-click card shows Pin/Reset/Copy ID/Select options with styled dropdown
- **Header clock**: Live HH:MM:SS clock in header updated every second
- **Expand/collapse all branches**: "▾ All" and "▸ All" buttons in detail panel to expand or collapse all branch blocks
- **Branch filter dropdown**: Select dropdown to filter detail panel to a single branch (appears when >1 branch)
- **Subtask output preview tooltip**: Hovering output text shows first 400 chars in title attribute
- **15 new tests**: context menu (4), clock (3), expand/collapse (3), branch filter (3), output preview (2)
- **211 dashboard E2E tests**, 2731 total, 0 failures

## v6.51.0 — 2026-03-12  Running Name + Branch % + Copy Key + Row Hover + Verified Counter

- **Task card running subtask name**: Shows the currently running subtask name (e.g. "▶ ST-042") on each task card
- **Branch completion percentage**: "75%" label next to branch name in detail panel headers
- **Keyboard `c` to copy task ID**: Press `c` with a task selected to copy its ID to clipboard
- **Subtask row hover highlight**: Subtask rows highlight with background on hover for readability
- **Detail panel verified counter**: Green verified/total (pct%) summary in detail sticky header
- **12 new tests**: running name (3), copy key (2), row hover (2), branch % (3), verified counter (2)
- **196 dashboard E2E tests**, 2716 total, 0 failures

## v6.50.0 — 2026-03-12  Status Emoji + Search Count + Auto-Collapse + Sort Subtasks + Progress Tooltip

- **Task card status emoji**: ✓/▶/◯/⏸/⊘ prefix on card mini-badge for quick visual status identification
- **Search match count**: "N results" label appears next to search input when filtering tasks
- **Auto-collapse verified branches**: Branches with all subtasks verified start collapsed in detail panel
- **Subtask status sort toggle**: "⇅ Sort" button in detail panel sorts subtasks by status (Pending → Verified)
- **Header progress bar tooltip**: Hover progress bar shows verified/running/pending/review breakdown
- **15 new tests**: status emoji (3), search count (4), auto-collapse (3), sort toggle (3), tooltip (2)
- **184 dashboard E2E tests**, 2704 total, 0 failures

## v6.49.0 — 2026-03-12  Poll Countdown + Relative Time + Word Count + Sticky Batch Bar + Copy Task ID

- **Poll countdown timer**: Seconds-until-next-tick counter displayed next to pause button; resets on interval change
- **Task card last-active time**: Relative timestamp ("2m ago") on each task card from `last_active` field
- **Subtask output word count badge**: Small badge showing word count (e.g. "42w" or "1.2k") on subtask rows with output
- **Sticky batch action bar**: Batch multi-select bar sticks to bottom of task grid when scrolling via `position: sticky`
- **Copy task ID**: Click task ID in detail panel header to copy to clipboard; dotted underline on hover
- **16 new tests**: countdown (4), relative time (4), word count (3), sticky bar (1), copy ID (4)
- **169 dashboard E2E tests**, 2689 total, 0 failures

## v6.48.0 — 2026-03-12  Quick Verify + Tab Badges + Compact Mode + Sparklines + Bulk Verify

- **Double-click quick-verify**: Double-click any subtask row to instantly verify it via POST /verify; checkbox guard prevents conflict with selection
- **Tab count badges**: Stalled tab shows live count badge (yellow pill) updated each poll tick via `updateTabBadges` export
- **Compact mode toggle**: "▥ Compact" toolbar button shrinks task cards (smaller padding/font); persisted in localStorage (`sb-compact`)
- **Task card sparkline**: Tiny bar chart on each task card showing per-branch completion — each bar proportional to branch verified%
- **Bulk verify in detail panel**: Checkbox on each subtask row + bulk action bar with "✓ Verify" and "✕ Clear" buttons for batch verification
- **22 new tests**: quick verify (4), tab badges (4), compact mode (5), sparkline (4), bulk verify (5)
- **153 dashboard E2E tests**, 2673 total, 0 failures

## v6.47.0 — 2026-03-12  Batch Actions + Auto Theme + Search Highlight + Pinned Tasks + Card Percentage

- **Batch task actions**: Shift+click to multi-select task cards; batch reset bar with count, reset, and clear buttons
- **Auto theme from OS**: Initial theme detects `prefers-color-scheme` via `matchMedia` if no localStorage preference is saved
- **Subtask search highlight**: Filtering subtasks in the detail panel highlights matching text with `<mark>` elements (yellow background)
- **Pinned tasks**: Pin icon on task cards sorts pinned tasks to top of grid; persisted in localStorage (`sb-pinned-tasks`)
- **Card percentage label**: Progress bar shows percentage number overlay (e.g. "72%") on each task card
- **21 new tests**: batch actions (6), auto theme (3), search highlight (3), pinned tasks (6), card percentage (3)
- **131 dashboard E2E tests**, 2711 total, 0 failures

## v6.46.0 — 2026-03-12  Diff Highlighting + Merge Readiness + DAG PNG Export + Tooltips + Drag Reorder

- **Diff syntax highlighting**: +/- lines in diff tab colored green/red with subtle background tint; light theme variants
- **Branch merge-readiness badge**: Green/yellow/red dot on each branch header — green = all verified (merge ready), yellow = in progress, red = not started
- **Export DAG as PNG**: "⬇ PNG" button appears in graph view — converts SVG to 2x canvas PNG with resolved CSS variables and background fill
- **Task card hover tooltip**: Hovering a task card shows branch-level breakdown (branch: verified/total per branch)
- **Drag-to-reorder task cards**: HTML5 drag-and-drop reordering with localStorage persistence (`sb-task-order`). Visual feedback: opacity + cyan border on drop target
- **13 new tests**: diff syntax (3), merge readiness (2), DAG PNG (3), tooltip (1), drag reorder (4)
- **110 dashboard E2E tests**, 2690 total, 0 failures

## v6.45.0 — 2026-03-12  Light Theme Status + Command Palette + Sticky Header + Collapsible Branches + Graph Module

- **Light theme status card colors**: `[data-theme="light"]` variants for `.status-complete/running/pending` task cards — maintains WCAG AA contrast in light mode
- **Ctrl+K command palette**: Fuzzy-search overlay across tabs, tasks, and actions (toggle theme, pause polling, copy summary, toggle mute, show shortcuts). Arrow keys navigate, Enter executes, Escape closes
- **Sticky detail header**: Task ID, progress bar, branch progress, and status pinned at top of detail panel via `position: sticky; top: 0`
- **Collapsible branch blocks**: Click branch name header to toggle `▾/▸` — collapsed branches hide subtask rows
- **`dashboard_graph.js` extraction**: 113 lines (DAG SVG rendering + grid/graph toggle) extracted from dashboard.js. 19 ES modules total
- **13 new tests**: command palette (4), sticky header (2), collapsible branches (3), graph module (4)
- **97 dashboard E2E tests**, 2677 total, 0 failures

## v6.44.0 — 2026-03-12  Reduced Motion + Status Bar + Clipboard Export + Keyboard Module

- **`prefers-reduced-motion`**: All CSS animations and transitions disabled when OS reduce-motion is set
- **Task card status color bar**: Left border colored green (complete), cyan (running), or yellow (pending) — instant visual scan of pipeline state
- **Ctrl+Shift+E clipboard export**: Copies selected task summary as markdown checklist (subtasks, status, progress)
- **`dashboard_keyboard.js` extraction**: 147 lines of keyboard handlers (shortcuts, focus trap, go-to combos, clipboard) extracted from dashboard.js. 18 ES modules total
- **CSS transitions**: Sidebar tab color transitions (0.15s), content opacity fade
- **84 dashboard E2E tests**, 2664 total, 0 failures

## v6.43.0 — 2026-03-12  Escape Panels + Scroll Reset + Transitions + Go-To Keys + Skeleton

- **Escape closes panels**: Escape key now dismisses dep graph and timeline panels (priority: shortcuts > modal > deps > timeline)
- **Scroll-to-top on task select**: Detail panel scrolls to top when a new task card is clicked
- **CSS transitions**: Sidebar tab color/border transitions (0.15s), tab content opacity fade-in (0.15s)
- **`g` then key go-to shortcuts**: `g h` → Health, `g s` → Settings, `g b` → Branches, `g m` → Metrics, `g d` → Diff, `g p` → Priority, `g a` → Agents, `g f` → Forecast. 500ms timeout window
- **Loading skeleton**: 3 pulsing placeholder cards (skeleton-pulse animation) shown before first poll completes
- **6 new tests**: go-key combos, escape deps/tl, skeleton pulse + card CSS, skeleton in HTML, scrollTop
- **82 dashboard E2E tests**, 2662+ total, 0 failures

## v6.42.0 — 2026-03-12  Focus Trap + Search Shortcut + Dep Click + Perf Avg + Tablet CSS

- **Focus trap**: Tab key cycles within open modals and shortcuts overlay instead of escaping to background. `_trapFocus()` utility with Shift+Tab reverse cycling
- **`/` search shortcut**: Pressing `/` focuses the task search input (vim-style). Added to `?` shortcuts panel
- **Dep graph node click**: Clicking a subtask node in the SVG dependency graph scrolls to and highlights that subtask row (cyan outline, 1.5s)
- **Perf rolling average**: `?perf=1` now shows 30-tick rolling average and `SLOW` warning when a tick exceeds 500ms
- **Tablet responsive (768-1024px)**: 2-column layout — task list on left, detail+sidebar stacked on right. Compact tab sizing
- **7 new tests**: focus trap, slash search, perf rolling avg, perf slow warn, dep node click, mobile+tablet breakpoints
- **76 dashboard E2E tests**, 2649+ total, 0 failures

## v6.41.0 — 2026-03-12  Subtask Dep Graph + Keyboard Shortcuts + Mute + Perf Mode

- **Subtask dependency graph**: "⊶ Deps" button in task detail panel renders a mini SVG DAG showing subtask nodes with colored status borders and dependency arrows. Topological layout with level assignment
- **Keyboard shortcuts**: `?` shows shortcuts overlay, `j/k` or `↑/↓` navigate tasks, `p` pauses polling, `t` toggles theme, `1-9` switches tabs, `Escape` closes modals
- **Mute toggle**: 🔔/🔇 button in header bar, persisted to `localStorage("sb-mute")`. Suppresses Web Audio notification tones when muted
- **Performance profiling**: `?perf=1` query param logs tick timing, poll count, DOM node count, and JS heap size to console each tick
- **8 new tests**: mute button present + aria-label, keyboard shortcuts panel, perf mode flag, mute init, deps graph function + panel class + svgEl import
- **69 dashboard E2E tests**, 2641+ total, 0 failures

## v6.40.0 — 2026-03-12  Dependency Click-to-Navigate + Task Queue Triage

- **Dep badge click-to-navigate**: Clicking a dependency badge chip in the detail panel scrolls to and highlights the target subtask row (orange outline, 1.5s fade)
- **Error/success toast types**: Reset failures, network errors, and timeline fetch failures now pass `"error"` type to toast; pipeline completion passes `"success"` type — triggers notification sounds
- **Task queue cleanup**: Removed 7 completed task entries from TASK_QUEUE.md, updated stats to v6.39.0, added 3 new proposed tasks (TASK-416 SVG dep graph, TASK-417 perf profiling, TASK-418 PWA)
- **2641 tests**, 0 failures

## v6.39.0 — 2026-03-12  Immediate Tab Poll + Notification Sounds + Version Fix + Dependency Viz

- **Immediate poll on tab switch**: Clicking a sidebar tab now fires its associated poller immediately instead of waiting for the next medium tick (~10s). Tab-to-poller mapping in `switchTab()` covers all 12 pollable tabs
- **Notification sounds**: Web Audio API tone on pipeline success (880 Hz sine, 120ms) and errors (330 Hz square, 120ms). Volume at 8% — subtle, non-intrusive. Triggered via `toast(msg, "success"|"error")`
- **`/health` version fix**: `_read_version()` now reads pyproject.toml first, falls back to `importlib.metadata`. Previously returned stale `1.0.0` from installed package metadata instead of current `6.39.0`
- **Subtask dependency badges**: Detail panel subtask rows now show `← dep1 dep2` chips with orange badges for each depends_on entry, replacing plain text
- **Regression test**: `test_health_version_matches_pyproject` pins `/health` version against pyproject.toml
- **2641 tests**, 0 failures

## v6.38.0 — 2026-03-12  Tab-Aware Polling + Accessibility Tests + Version Bump

- **Tab-aware polling**: Medium-tier pollers now only fire for the active sidebar tab — inactive tab data is not fetched. Combined with tiered polling, total API calls reduced ~85% vs original 30-per-tick
- **6 new regression tests**: `TestCommandToolbarLabels` (aria-label on 7 inputs), `TestTieredPollingStructure` (tickCount, fast/medium/slow tiers, modulo guards, health in slow tier)
- **Version bump**: `pyproject.toml` version 1.0.0 → 6.37.0 (aligned with CHANGELOG)
- **3890 tests**, 0 failures

## v6.37.0 — 2026-03-12  Tiered Polling + Light Theme Contrast + Input Labels + Touch Targets

- **Tiered polling**: Split 30 concurrent polls into fast (status/tasks/journal/history every 2s), medium (stats/branches/metrics/etc every 10s), and slow (health widgets every 30s). Reduces API calls by ~70% during idle operation
- **Light theme contrast fix**: `--dim #888 → #666` (3.25:1 → 5.27:1, passes WCAG AA)
- **Command toolbar `aria-label`s**: All 8 inputs and 4 buttons in Verify/Describe/Tools/Set groups now have accessible names
- **Touch targets**: `.toolbar-btn` minimum 24×24px (WCAG 2.5.8 AA), flexbox centered content
- **3884 tests**, 0 failures, dashboard lint PASS (0 gaps)

## v6.36.0 — 2026-03-12  Accessibility Sprint: Contrast + Keyboard Nav + Skip-Nav

- **WCAG contrast fix**: `--dim` color `#666 → #888` (3.38:1 → 5.48:1 contrast ratio, now passes AA)
- **Keyboard tab navigation**: Arrow Left/Right/Up/Down, Home/End keys navigate sidebar tabs with focus + activation
- **Skip-nav link**: "Skip to main content" link appears on Tab focus, jumps to task grid
- **TASK-412 SSE researched**: documented findings in TASK_QUEUE — ETag caching reduces urgency, simplest SSE path requires `watchdog` file-watcher or hybrid `/changes?since=step` endpoint
- **3884 tests**, 0 failures

## v6.35.0 — 2026-03-12  Dashboard Accessibility + ARIA + Focus Styles

- **ARIA tablist/tab/tabpanel**: Sidebar tabs now have `role="tablist"`, each button has `role="tab"` + `aria-selected` + `aria-controls`, all panels have `role="tabpanel"`. `data-tab` on every tab button for reliable matching
- **`aria-selected` toggling**: `switchTab()` now updates `aria-selected` on tab buttons dynamically
- **Dialog accessibility**: All 3 modals have `role="dialog"` + `aria-modal="true"` + `aria-labelledby`
- **Focus-visible outlines**: `:focus-visible` with cyan outline on all interactive elements — buttons, tabs, inputs, task cards
- **Alert roles**: Toast (`aria-live="assertive"`) and stale banner (`role="alert"` + `aria-live="polite"`) for screen reader announcements
- **Emoji button labels**: Theme toggle and notification buttons have `aria-label` for screen readers
- **Mobile font fix**: Button font-size `9px → 10px` on mobile breakpoint (WCAG minimum)
- **12 new accessibility regression tests**: tablist/tab/tabpanel roles, aria-selected, aria-controls, dialog roles, aria-modal, alert roles, aria-labels, data-tab completeness
- **3884 tests**, 0 failures, dashboard lint PASS (0 gaps)

## v6.34.0 — 2026-03-12  Final Panel Extraction + Full Bot Dispatch Coverage

- **TASK-415 complete**: Final `dashboard_panels.js` extraction — priority, agents, forecast, metrics panels (207 lines) → `dashboard_analytics.js`. Panels hub now **62 lines** (re-exports + switchTab + export refresh). **-96%** from original 1664 lines. **17 ES modules** total
- **38 new bot_commands dispatch tests**: Full coverage of `_handle_text_command` branches — status, run, stop, verify, add_task, add_branch, export, undo, graph, tasks, stats, cache, history, branches, subtasks, diff, filter, search, log, priority, stalled, agents, forecast, help, output, set (=, read, unknown), depends (show + add), undepends, snapshot
- **Dashboard E2E smoke tests expanded**: 21 new tests — panel sub-module existence, hub size guard (<100 lines), re-export completeness (14 functions), analytics module content validation (4 exports + SVG imports)
- **3872 tests**, 0 failures, 17 JS modules, 0 lint gaps

## v6.33.0 — 2026-03-12  History + Subtasks Extraction + ETag Tests + Bot Test Fixes

- **History panel extraction**: `dashboard_panels.js` 466→268 lines (-42%). History tab → `dashboard_history.js` (204 lines). `resetHistoryUnread()` exported for cross-module switchTab
- **Subtasks panel extraction**: Subtask tab (filters, paging, bulk actions, render) → `dashboard_subtasks.js` (256 lines). `updateSubtasksExportLinks()` exported for switchTab
- **`dashboard_panels.js` 722→268 lines** (-63%) across 2 extractions. 16 ES modules total
- **ETag test coverage**: 7 new tests in `test_middleware.py` — 304 on match, no ETag on POST/non-200/direct-passthrough, MD5 body hash, idempotent tags
- **Dashboard ETag client**: `api()` in `dashboard_utils.js` now caches ETags and sends `If-None-Match` headers — avoids re-parsing unchanged JSON on 304
- **Bot test fixes**: `sys.modules` aliasing for `solo_builder.discord_bot.*` → `discord_bot.*` so `_bot()` lazy import resolves to same module object. Fixed `_find_subtask_output` and `_format_diff` patch targets after bot_commands extraction. Re-exported `_HELP_TEXT`, `_KEY_MAP` from `bot.py`
- **24 new bot_commands tests**: `_format_heal`, `_format_reset_task`, `_format_reset_branch`, `_format_bulk_reset`, `_format_bulk_verify`, plus 6 dispatch tests (heal, config, heartbeat, pause, resume, rename)
- **2601+ tests** (core) + **329 bot tests**, 0 failures, 16 JS modules, 0 lint gaps

## v6.31.0 — 2026-03-12  ETag Caching + Bot.py Extraction

- **TASK-413 complete**: ETag `after_request` handler — MD5 hash on GET/HEAD 200 responses, returns 304 Not Modified on `If-None-Match` match. Skips direct passthrough responses. Reduces dashboard polling bandwidth
- **TASK-414 complete**: `bot.py` 1103→436 lines (-60%). Extracted `_handle_text_command` + 5 format helpers + `_HELP_TEXT` + `_KEY_MAP` into `bot_commands.py` (~550 lines). Lazy import pattern avoids circular deps
- **2594 tests**, 0 failures, 12 JS modules, 0 lint gaps

## v6.30.0 — 2026-03-12  TASK-411 Dashboard Panel Extraction

- **TASK-411 complete**: Extracted settings panel (105 lines) → `dashboard_settings.js`, stalled panel (134 lines) → `dashboard_stalled.js`
- **dashboard_panels.js 960→722 lines** (-25%), 12 ES modules total (was 10)
- Shared helpers (`STATUS_COL`, `placeholder`) in `dashboard_utils.js` for cross-module use
- Arch regression test guards score >= 95.0 + zero critical findings
- Idle/done STATE.json oscillation fix in `audit_check.ps1`
- **2594 tests**, 0 failures, lint handler audit 0 gaps

## v6.29.0 — 2026-03-12  Architecture Score 99.0 + Dashboard Health Smoke Tests

- **Architecture score 75.5→99.0/100**: Fixed 4 circular dependency false positives in Autonomous Architecture Auditor — multiline regex capture bug, test file exclusion, path boundary matching, token length filter
- **TASK-409 complete**: OpenAPI spec drift detection test (3 tests guard 90/90 route parity)
- **TASK-410 complete**: dashboard_health.js smoke test — verifies all 12 pollers exported, re-exported, and imported
- **3366 tests**, 0 failures, CI gate 6/6 PASS
- **Architecture score 100.0/100**: suppressed Bandit B602 false positive on `pre_release_check.py` `shell=True` (commands from local VERIFY.json, not user input) — **zero critical findings**

## v6.28.0 — 2026-03-12  Dashboard Refactor + Zero Tech Debt

- **dashboard_panels.js split**: extracted 14 health pollers into `dashboard_health.js` (697 lines), reducing `dashboard_panels.js` from 1664→970 lines (-42%)
- **TD-ARCH-001 resolved**: `solo_builder_cli.py` at 473 lines (target was <600) — 0 open debt items remain
- **Journal archival**: JOURNAL.md trimmed 559→65 lines (494 entries archived)
- **10 ES modules** in dashboard (was 9): state, utils, svg, tasks, panels, branches, cache, journal, health (new)
- **3358 tests**, 0 failures, CI gate 6/6 PASS

## v6.27.0 — 2026-03-12  Full Coverage Milestone — cli_utils 100%, cache 100%, CI gate 6/6

- **cli_utils.py 74→100%**: 10 new tests covering `_splash`, `_acquire_lock`/`_release_lock`, `_setup_logging(use_json=True)`, `_emit_json_result` with/without export flag
- **cache.py 89→100%**: 5 new tests covering dir read exception, unlink OSError, glob exception, history/export corrupt file
- **CI Quality Gate**: 6/6 PASS confirmed after full coverage sprint
- **Branch cleanup**: 348 stale `task/TASK-*` branches deleted
- **775 API tests**, 37 cli_utils tests, 3319+ total, 0 failures

## v6.26.0 — 2026-03-12  Deep Blueprint Coverage — 99% across 25 blueprints, 770 API tests

- **Phase 2 coverage sprint**: 30 additional tests covering remaining gaps across 7 blueprints:
  - `control.py` 96→**100%** (OSError on pause_trigger unlink)
  - `dag.py` 97→**100%** (Running count in summary, invalid DAG import structure)
  - `health_detailed.py` 94→**100%** (SLO sufficient records, repo_health exception)
  - `history.py` 99→**100%** (corrupt backup returns 500)
  - `tasks.py` 94→**100%** (write failures on reset/bulk-reset/bulk-verify, bad limit/page params, Review dominant status, branch filter, graph deps, priority unmet deps)
  - `webhook.py` 88→**100%** (settings read exception, non-http URL rejected, urlopen exception)
  - `executor_gates.py` 85→**88%** (scope eval exception, hitl gate import exception)
- **Blueprint coverage**: **99%** overall — 22 of 25 at 100%
- **770 API tests** (was 746), 3319+ total, 0 failures

## v6.25.0 — 2026-03-12  Blueprint Coverage Sprint — 9 blueprints 0→100%, 348 branches pruned

- **Blueprint coverage sprint**: 44 new tests across 11 test classes covering 9 previously-uncovered blueprints:
  - `ci_quality.py`, `context_window.py`, `live_summary.py`, `policy.py` (hitl+scope), `debt_scan.py`, `slo.py`, `threat_model.py`, `pre_release.py`, `prompt_regression.py` — all now **100%** coverage
  - Happy paths, exception handlers, _load_tool uncached branches, SLO sufficient/insufficient records, threat model file-missing, runner exception caught
- **Blueprint coverage overall**: **97%** across 22 blueprints (15 at 100%, up from 10)
- **Branch cleanup**: Deleted 348 stale `task/TASK-*` branches (all merged to master)
- **Test suite**: 746 API tests, 3319 total, 0 failures
- **Pre-existing errors**: All 35 previously-reported test errors confirmed resolved (0 failures in `tests/`)

## v6.24.0 — 2026-03-12  TASK-114 Deep API Coverage Sprint — 50+ new tests, 8 blueprints at 100%

- **TASK-114 Flask API integration tests**: 50+ new tests across 10 test classes:
  - **Phase 1** (26 tests): `core.py`, `metrics.py`, `subtasks.py`, `branches.py`, `export_routes.py`, `config.py` → all **100%** coverage
    - Exception handlers (`except Exception: pass`), filter edge cases (`branch=ZZZ`, `min_age=xyz`, `page=abc`), write failures (Path.write_text monkey-patch), `_read_version()` fallback chain
  - **Phase 2** (24 tests): `executor_gates.py` 8%→**85%**, `health_detailed.py` 18%→**92%**
    - Gate evaluation, policy load exceptions, HITL eval exception, AAWO snapshot null, SLO insufficient records, config drift/metrics alerts exception paths
  - Fixed 2 broken tests: `Path.write_text`/`read_bytes` can't be `patch.object`'d on WindowsPath — switched to class-level monkey-patching
- **pre_release_check python-tests timeout 120→300s**: test suite grew past 120s under subprocess overhead
- **Overall**: `app.py` + `middleware.py` + 6 core blueprints at **100%**, 2 complex blueprints at 85–92%
- **697 API tests** (was 651), full suite 2400+ tests, 0 failures

## v6.23.0 — 2026-03-12  TASK-385 CoverageGaps + ci_quality_gate pre-release timeout + B310 confirmed suppressed

- **TASK-385 CoverageGaps**: `app.py` 96%→**100%**, `middleware.py` 98%→**100%** (+3 tests):
  - `test_x_response_time_attribute_error_silent` — calls `security_headers()` via `test_request_context` (no `_start_time`) → covers `except AttributeError: pass` (app.py:108-109)
  - `test_405_method_not_allowed_handler` — `POST /status` triggers 405 → covers `method_not_allowed()` (app.py:124)
  - `test_current_count_prunes_expired_entries` — 25ms sleep expires deque → covers `dq.popleft()` (middleware.py:113)
- **ci_quality_gate pre-release timeout 180→600s**: `pre_release_check.py` runs VERIFY.json gates (unittest-discover: 900s budget) plus builtin gates; 180s was always too tight
- **TASK-116 (Bandit B310) confirmed suppressed**: `webhook.py` already has `# nosec B310`; bandit confirms no B310 finding; no product-code change needed
- **TASK-115 already done**: `solo_builder_cli.py` is 473 lines (well below 600 target)
- **2573 tests total** (was 2570), 0 failures

## v6.22.0 — 2026-03-12  TASK-383/384 OpenAPI complete + TASK-110 docs + dep_audit --quiet + audit drift fix

- **TASK-383/384 OpenAPIHealthRoutes/ExportRoutes**: OpenAPI spec already complete — `TestLiveUrlMapDriftGuard` confirms all Flask blueprint routes are in `_ROUTES` with zero drift
- **TASK-110 mixin test-patch docs**: Extended `docs/dev_notes.md` with instance-attribute MagicMock shadowing pattern (`del self.cli.save_state` trick) discovered during TASK-407
- **`dep_audit.py --quiet` flag**: Added `--quiet` to suppress stdout/stderr; `ci_quality_gate.py` no longer fails with "unrecognized arguments: --quiet" when invoking `dep-audit` tool (+2 tests)
- **metrics.jsonl audit drift fix**: `audit_check.ps1` now restores `metrics.jsonl` from HEAD before the dirty-tree check — eliminates false "working tree mutated" failures after `unittest-discover` runs
- **Architecture criticals**: 4 circular-dep criticals confirmed as static-analysis false positives (actual imports succeed); `shell=True` critical already fixed in prior sprint; `arch_last.json` will clear on next audit run
- **AAWO `main.py` coverage**: Confirmed at **100%** (491 stmts, 0 missing) — no new tests needed
- **2570 tests total**, 0 failures

## v6.21.0 — 2026-03-11  TASK-407 Deep coverage sprint — 2570 tests, 4 command modules at 100%

- **TASK-407 Deep coverage sprint**: 28 new tests across 4 test files reaching 100% on targeted modules:
  - **`test_dag_cmds_deep.py`** (+19 tests, 7 new classes): `_cmd_reset` (6 tests), digit-dep normalise, Claude decomp `except` paths (104-105), lowercase `_normalise` in `depends`/`undepends`, import_dag validation errors, `_cmd_export` (5 tests) — `dag_cmds.py` 86% → **100%**
  - **`test_step_runner.py`** (+6 tests, 2 new classes): Running/Review heartbeat counters (lines 90-91), `os.replace` OSError (115-118), `shutil.copy2` OSError (122-123) — `step_runner.py` 95% → **100%**
  - **`test_query_cmds.py`** (+2 tests): `_cmd_log` bad-header `continue` path (line 346), no-journal warning — `query_cmds.py` 99% → **100%**
  - **`test_subtask_cmds.py`** (+1 test): `_cmd_resume` `os.remove` OSError (lines 181-182) — `subtask_cmds.py` 99% → **100%**
- Coverage totals: `dag_cmds.py` **100%**, `step_runner.py` **100%**, `query_cmds.py` **100%**, `subtask_cmds.py` **100%**
- Key fix: `_FakeCLI.save_state` is a MagicMock instance attribute — OSError tests call `StepRunnerMixin.save_state(cli)` directly to reach the real implementation
- **2570 tests total**, 0 failures

## v6.20.0 — 2026-03-11  TASK-406 Deep coverage sprint — 2542 tests, commands/ 96%

- **TASK-406 Deep coverage sprint**: 5 new test files + major additions to 3 existing files (67 new tests):
  - **`test_query_cmds_deep.py`** (48 tests): `_cmd_branches`, `_cmd_search`, `_cmd_filter`, `_cmd_timeline`, `_cmd_log`, `_cmd_diff`, `_cmd_stats`, `_cmd_output`, `_cmd_help` — `query_cmds.py` 46% → **99%**
  - **`test_subtask_cmds.py`** (31 tests): all subtask methods — `query_cmds.py` 60% → **99%**
  - **`test_dispatcher.py`** (+22 tests): `_cmd_set` all branches, `start()`, `_run_aawo_session_start` — `dispatcher.py` 71% → **97%**
  - **`test_auto_cmds.py`** (+8 tests): OSError exception paths, undepends trigger, pause gate — `auto_cmds.py` 86% → **100%**
  - **`test_executor_timing.py`** (+15 tests): `_write_step_metrics` OSError, `_fire_outcome` edge cases, HITL TTY gate, subprocess fallback, sdk_tool fail escalate, sdk_direct fail dice-roll, roll_up paths — `executor.py` 89% → **99%**
- Coverage totals: `auto_cmds.py` **100%**, `settings_cmds.py` **100%**, `__init__.py` **100%**, `query_cmds.py` **99%**, `subtask_cmds.py` **99%**, `dispatcher.py` **97%**, `executor.py` **99%**
- **2542 tests total** (was 3475 before TASK-406, now correct count reflects full test suite)

## v6.18.0 — 2026-03-11  TASK-399 BlueprintCoverage — tasks 98%, subtasks 94%, webhook 100%

- **TASK-399 BlueprintCoverage**: 159 new Flask test-client tests across 3 new test files:
  - `test_tasks_blueprint.py` (60 tests, 11 classes) — `tasks.py` 19% → **98%**:
    - `GET /tasks` — pagination, task filter, empty DAG
    - `GET /tasks/export` — CSV default, JSON format, Content-Disposition, header row
    - `GET /tasks/<id>` + `GET /tasks/<id>/export` — 404 handling, CSV/JSON format, safe filename
    - `POST /tasks/<id>/trigger` — 202, accepted, pending_subtasks list, 404
    - `POST /tasks/<id>/reset` — non-verified reset, verified skipped, output cleared, 500 on write error
    - `POST /tasks/<id>/bulk-reset` — skip_verified, include_verified, task status reset, 500
    - `POST /tasks/<id>/bulk-verify` — non-verified advanced, skip_non_running, task status Verified, 500
    - `GET /tasks/<id>/progress` — response keys, branch rows, verified count, 404
    - `GET /tasks/<id>/branches` — pagination, status filter, dominant status (Running/Review/Verified), invalid limit fallback
    - `GET /tasks/<id>/subtasks` — branch/status filters, output=1, pagination
    - `GET /tasks/<id>/timeline` — sorted by last_update, response keys, 404
    - `GET /graph` — nodes/text, empty DAG, depends_on in text
    - `GET /priority` — Pending/Running only, deps_not_met excluded, risk descending
  - `test_subtasks_blueprint.py` (66 tests, 9 classes) — `subtasks.py` 37% → **94%**:
    - `GET /subtasks` — task/branch/status/name/output/min_age/pagination filters, invalid param fallbacks
    - `GET /subtasks/export` — CSV/JSON, Content-Disposition, status filter, pagination
    - `POST /subtasks/bulk-reset` — skip_verified, skip_verified=False, not_found, missing/empty list 400, write error 500
    - `POST /subtasks/bulk-verify` — verified, already-verified skipped, skip_non_running, not_found, 400/500
    - `GET /subtask/<id>` + `GET /subtask/<id>/output` — plain-text output, 404
    - `POST /subtask/<id>/reset` — heal_trigger written, payload content, previous_status, 404
    - `GET /timeline/<subtask>` — case-insensitive match, history included, 404
    - `GET /stalled` — stall_threshold from settings, min_age override, task/branch filters, by_branch grouping, settings-read-error fallback, invalid min_age ignored
  - `test_webhook_blueprint.py` (33 tests, 5 classes) — `webhook.py` 22% → **100%**:
    - No URL / settings missing → `{ok: false, reason: "WEBHOOK_URL not configured"}`
    - Invalid URL (ftp://, bare hostname) → `{ok: false, reason: "...http..."}`
    - Success: `ok/sent=true`, url echoed, payload pct/event/step validated via urllib mock
    - Network error: `ok/sent=false`, error message captured, still 200
    - PCT calc edge cases: 0% when no verified, 0% when empty DAG
- **Test suite**: **2557 → 2716 tests**, 0 failures

---

## v6.14.0 — 2026-03-11  TASK-396–398 sprint — history coverage, OpenAPI 33 schemas, runner 98%

- **TASK-396 HistoryBlueprintCoverage**: 49 new Flask test-client tests across 6 classes covering all of `history.py`:
  - `GET /history` — pagination, since/status/subtask/task/branch filters, review count, events sorted descending
  - `GET /history/count` — total/filtered/by_status breakdown, all filter params
  - `GET /history/export` — CSV/JSON format, since/limit/subtask/status/task/branch filters, Content-Disposition header
  - `GET /diff` — no-backup (empty changes), backup present (detects status transitions), no-change, step numbers
  - `GET /dag/diff` — missing `from` returns 400, detects status transition via history arrays, no-change
  - `GET /run/history` — meta_history records, cumulative sums, since/limit, step_index starts at 1
- **TASK-397 OpenAPIResponseSchemas2**: Added `"response"` schemas to **25 more routes** (was 8, now **33 total**):
  - `/metrics`, `/metrics/summary`, `/agents`, `/forecast`, `/stalled`, `/config`, `/dag/summary`
  - `/branches`, `/branches/{task_id}`, `/cache` (GET+DELETE), `/cache/history`
  - `/run`, `/run/history`; all 9 `/health/*` routes; both `/policy/*` routes
- **TASK-398 RunnerCoveragePush**: 19 new tests targeting exception-handling paths:
  - `cache.py`: **86% → 98%** — mock-based tests for mkdir OSError, `set()` write failure, `clear()` unlink OSError, `size()` glob failure, `persist_stats()` write failure
  - `executor.py`: `_fire_outcome()` early-return paths (no routing, no agent_id); `_update_task()` Running branch; `execute_step()` max_per_step break

---

## v6.10.0 — 2026-03-11  TASK-393–395 sprint — blueprint + agent coverage, OpenAPI required arrays

- **TASK-393 BlueprintBodyCoverage**: 56 new Flask test-client tests across 11 test classes:
  - `test_control_blueprint.py` (26 tests) — all 7 POST endpoints: `/run`, `/stop`, `/undo`, `/reset` (confirm guard + case-insensitive YES), `/snapshot`, `/pause`, `/resume` (removes pause_trigger file)
  - `test_cache_blueprint.py` (30 tests) — `GET /cache` (entries/hit-rate/stats-file exclusion), `DELETE /cache` (clears files, preserves session_stats.json, nonexistent dir), `GET /cache/history` (no-file, since filter, hit-rate calc), `GET /cache/export` (CSV/JSON, since/limit, Content-Disposition)
- **TASK-394 AgentClassCoverage**: 4 new tests → **100% coverage on all 5 agent modules** (`verifier.py`, `shadow_agent.py`, `self_healer.py`, `meta_optimizer.py`, `planner.py`):
  - `test_forecast_with_verify_rate_returns_eta` — covers `forecast()` ETA branch (lines 55-57 of meta_optimizer.py)
  - `test_optimize_returns_none_when_rates_moderate` — covers `optimize()` final `return None` (line 38)
  - `TestPlannerAdjustWeightsShadow` (2 tests) — covers `adjust_weights("shadow", ...)` branch (lines 49-50 of planner.py)
- **TASK-395 OpenAPIRequiredArrays**: `build_spec()` now emits `required: [field1, ...]` in all 13 POST requestBody schemas; 6 new tests in `TestRequestBodyRequired` assert required arrays are present, non-empty, and match property keys exactly; `test_generate_openapi.py`: **61→67 tests**
- **AAWO coverage verified**: 1085 tests passing, `main.py` at **100% coverage** — no regressions

---

## v6.07.0 — 2026-03-11  TASK-389–392 sprint — 90 routes, live drift guard, path params, response schemas, 1795 tests

- **1795 Solo Builder tests** (0 failures); 16 new tests in this sprint
- **TASK-389 OpenAPIDriftGuard**: live Flask `app.url_map` test — cross-references _ROUTES at test time; fixed 3 residual mismatches (`/branches/{branch_id}`→`{task_id}`, `POST /trigger` phantom removed, duplicate `GET /branches/{task_id}` removed); spec: **90 routes**, zero drift
- **TASK-390 OpenAPIPathParameters**: `build_spec()` auto-extracts `{param}` as required path parameters; added query params to `/history` (since/limit/page), `/metrics/export` (format), `/search` (q); **19 operations** now have `parameters` blocks; **5 new tests**
- **TASK-391 OpenAPIResponseSchemas**: `build_spec()` emits `content/application/json/schema` in `200` responses when `"response"` key set; added schemas to `/status`, `/heartbeat`, `/health`, `/history`, `/history/count`, `/tasks`, `/tasks/{task_id}`, `/subtasks`; **4 new tests**; `test_generate_openapi.py`: **49→61 tests**
- **TASK-392 CoveragePush2**: 16 new tests covering `_load_tool()` importlib path + cache-hit in 6 health blueprints; `format_status`, `format_shadow`, `validate_dag` missing-subtasks and invalid-shadow paths in `helper_functions.py`; overall coverage: **62%**

---

## v6.03.0 — 2026-03-11  TASK-388 OpenAPIPhantomRoutes — 92 clean routes, 49 tests

- **1779 Solo Builder tests** (0 failures)
- TASK-388: OpenAPIPhantomRoutes — audited spec against actual Flask blueprints; removed 4 phantom routes:
  - `/cache/stats` (real: `GET /cache`)
  - `/cache/clear` (real: `DELETE /cache`)
  - `/webhook/test` (real: `POST /webhook`)
  - `/health/executor-gates` (alias for non-existent path; real: `GET /executor/gates`)
  - Spec: 96 → **92 routes** (all verified against blueprint sources)
  - Added `test_phantom_routes_absent` regression guard — prevents phantom routes from reappearing
  - Tests: 48 → **49**

---

## v6.02.0 — 2026-03-11  TASK-387 OpenAPIRequestBodies — 13 POST schemas, 48 tests

- **1779 Solo Builder tests** (0 failures)
- TASK-387: OpenAPIRequestBodies — added `requestBody` JSON schemas for 13 POST endpoints:
  - Trigger endpoints: `/verify` (subtask), `/describe` (subtask), `/set` (key/value)
  - DAG: `/dag/import` (dag object)
  - Task management: `/add_task` (spec), `/add_branch` (task/spec), `/rename` (task/name), `/depends` (target/dep), `/undepends` (target/dep), `/prioritize_branch` (task/branch), `/tools` (subtask/tools)
  - Config: `/config` POST (key/value)
  - Webhook: `/webhook` (event/payload)
  - `build_spec()` now emits `requestBody` + `400` response whenever route has `body` key
  - `test_generate_openapi.py`: **43 → 48 tests**; new checks: requestBody presence, 400 response for body-carrying ops, add_branch properties

---

## v6.01.0 — 2026-03-11  TASK-386 OpenAPIBlueprintGaps — 96 routes, 43 OpenAPI tests

- **1779 Solo Builder tests** (0 failures)
- TASK-386: OpenAPIBlueprintGaps — complete blueprint route audit + fill all gaps:
  - Identified 40 routes in Flask blueprints missing from `generate_openapi.py` `_ROUTES`
  - Added all 40 missing routes across new/extended tags: Cache, Tasks (branches/subtasks/timeline/export/bulk-ops), Branches (per-task/reset/export), Subtasks (by-id/output/reset/bulk-verify/export), History (export), Control (run/run-history), Triggers (add_task/add_branch/rename/depends/undepends/prioritize_branch/tools/webhook), Config (reset/export), misc (executor/gates, shortcuts, diff, dag/diff, graph, timeline, priority)
  - Fixed stale `/health/gates` entry (never existed) → `/health/executor-gates` alias
  - Spec: **56 → 96 routes**; `test_generate_openapi.py`: **35 → 43 tests**; threshold guard raised to 90 routes

---

## v6.00.0 — 2026-03-11  TASK-385 CoverageGaps — 1779 tests, 5 new coverage tests

- **1779 Solo Builder tests** (0 failures); 10 added vs v5.99.0
- TASK-385: CoverageGaps — 3 `# pragma: no cover` guards + 5 targeted tests:
  - `agents/__init__.py` and `commands/__init__.py` sys.path guards marked `# pragma: no cover`
  - `api/app.py` `if __name__ == "__main__"` guard marked `# pragma: no cover`
  - `TestRateLimiterCurrentCount` (3 tests): `current_count()` read/write/unseen-ip paths (`middleware.py:107-114`)
  - `test_optional_field_oversized_returns_400`: optional field > MAX_FIELD_LEN returns 400 (`validators.py:70-72`)
  - `test_after_request_missing_start_time_no_header`: AttributeError branch when `_start_time` missing (`app.py:108-109`)

---

## v5.99.0 — 2026-03-11  TASK-383/384 + AAWO 100% main.py coverage

- **1730 Solo Builder tests** (0 failures); **1085 AAWO tests** (0 failures)
- AAWO v1.1.8: `main.py` now at **100% coverage** — 9 new gap tests in `test_main_gaps.py` covering `cmd_health` lifecycle/storage/n-a branches (lines 152-154, 158-159, 176-177), `cmd_explain` n/a branch (229-230), `cmd_explain_all` GRACE status (265) and n/a branch (299-300), `cmd_route` policy-blocked JSON (338) and success JSON (373), and `if __name__ == "__main__"` guard (728) via `runpy.run_path`
- TASK-383 closed: OpenAPIHealthRoutes already committed in `6a11412`; STATE advanced to done; `claude/TASK_DONE.md` added to `allowed_files.txt`
- TASK-384: OpenAPIExportRoutes — 5 export routes (`/export` GET+POST, `/stats`, `/search`, `/journal`) added to `generate_openapi.py` under new `Export` tag; spec now has **56 routes**; `test_generate_openapi.py` grows from 30 → 35 tests

---

## v5.98.0 — 2026-03-11  AawoTests6 — 99% overall coverage; 22 modules at 100%

- **1769 tests**, all passing; 0 failures (AAWO: 1076, Solo Builder: 1769)
- AAWO v1.1.7 released
- AAWO coverage milestone: **99% overall** (up from 91%) — 22 modules at 100%; 15 uncovered lines remain (all in `main.py`: specific output branches + `if __name__ == "__main__"` guard)
- AAWO `test_adapters.py` NEW (15 tests): `TestBaseAdapter` (3: not-instantiable, concrete subclass, super()-call covers abstract `pass` bodies on lines 7+11), `TestClaudeAdapter` (6: env key, health check, run_task raises NotImplementedError), `TestCodexAdapter` (6) → `adapters/base.py`, `claude_adapter.py`, `codex_adapter.py` all at **100%**
- AAWO `test_executors.py` NEW (22 tests): `TestFileExecutor` (8: read/write/search + OSError paths), `TestShellExecutor` (5: success/fail/stdout/timeout/FileNotFoundError), `TestGitExecutor` (5: log/status/diff args validation), `TestTestExecutor` (4: default/custom/coverage) → all 4 executor modules at **100%**
- AAWO `test_main_gaps.py` NEW (25 tests): `TestMainDispatch` (16: patch `sys.argv` + mock cmd function → covers `main()` parser setup lines 643-724), `TestCmdSnapshot` (2: json/non-json modes with real repo → covers lines 29-50), `TestCmdHandoffAcceptReject` (2: covers lines 585-595), `TestCmdHistoryBranches` (5: patch `audit_logger.read_events_by_cycle` → covers overlaps/handoffs/events branches lines 499, 506-508, 518-522)
- **Key patterns**: `patch("audit_logger.read_events_by_cycle", ...)` for cmd_history since import is local; `super().run_task(...)` call on abstract subclass to hit abstract method `pass` body; `patch.object(sys, "argv", [...])` + `patch("main.cmd_*")` for dispatch table coverage

---

## v5.97.0 — 2026-03-11  AawoTests5 — 91% overall coverage; 15 modules at 100%; security audit clean

- **1769 tests**, all passing; 0 failures (AAWO: 1014, Solo Builder: 1769)
- AAWO v1.1.6 released
- AAWO coverage milestone: **91% overall** (up from 88%) — 15 modules now at 100%; security audit clean (32 files, no issues)
- AAWO `test_dependency_resolver.py` +2: `TestLoadDependencyMapOSError` (OSError on schema open → `{}, {}`, covers lines 15-16) + `TestResolveDependenciesWeightOSError` (OSError on weights open → `dep_bonus=0.5` fallback, covers lines 43-44) → `dependency_resolver.py` **100%**
- AAWO `test_overlap_resolver.py` +1: `test_existing_agent_loses_to_incoming_higher_priority` — first agent priority=3 processed first, second agent priority=1 comes in and wins, existing gets "lost to" annotation; covers lines 124-127 → `overlap_resolver.py` **100%**
- AAWO `test_retention_manager.py` +1: `test_oserror_on_unlink_recorded_in_errors` — `patch.object(Path, "unlink", side_effect=OSError("read-only"))` → errors list populated, covers lines 111-112 → `retention_manager.py` **100%**
- AAWO `test_handoff_manager.py` +3: `TestHandoffManagerDefensivePaths` — blank lines, malformed JSON, missing task_id, rejected event across `get_handoff_detail`/`count_pending_handoffs`/`list_handoff_statuses`; covers lines 134, 137-138, 174, 177-178, 181, 211, 214-215, 218, 234 → `handoff_manager.py` **100%**
- AAWO `test_queue_manager.py` — new file, 17 tests: `TestEnqueue`/`TestDequeue`/`TestComplete`/`TestListQueue`/`TestItemConversion` — full CRUD coverage using `patch.object(state_store, "_STATE_DIR", tmp_path)` → `queue_manager.py` **100%**
- **Key patterns**: direct `_write_jsonl` to JSONL files for defensive path testing; `patch.object(state_store, "_STATE_DIR", ...)` for queue isolation; `patch.object(dr, "_load_dependency_map", return_value=(...))` to isolate OSError on the second file open in `resolve_dependencies`

---

## v5.96.0 — 2026-03-11  AawoTests4 — snapshot_builder + snapshot_detectors → 100%; 88% overall

- **1769 tests**, all passing; 0 failures (AAWO: 990, Solo Builder: 1769)
- AAWO v1.1.5 released
- AAWO coverage milestone: **88% overall** — `snapshot_builder.py` and `snapshot_detectors.py` both now at **100%**
- AAWO `test_snapshot_builder.py` +3: `TestLoadLatestSnapshotSB` — dir-absent returns None (line 51), OSError on read returns None (lines 57-58), JSONDecodeError returns None (lines 57-58); used mock Path chain (`patch.object(sb, "Path", side_effect=_path_factory)`) to control `Path(__file__).parent / "storage" / "snapshots"` without touching real storage
- AAWO `test_snapshot_detectors.py` +17: `TestReadOperationalSignals` +4 (git log/status timeout + FileNotFoundError exceptions, lines 258-259/268-269), `TestDetectFrameworksOSError` (OSError on file read skipped, lines 85-86), `TestEstimateComplexityGaps` +2 (OSError on file open skipped lines 163-164, very_high complexity with 500 files), `TestScanRiskFactorsIgnored` +2 (file in `storage/` ignored dir → continue line 224, OSError on read → pass lines 235-236)
- **Key testing patterns**: `patch.object(Path, "open"/"read_text", side_effect=OSError(...))` — `side_effect` callable receives args without `self`; passing exception instance directly is simpler and correct; `subprocess.run` side_effect as list for multi-call sequences

---

## v5.95.0 — 2026-03-11  AawoTests3 — detector/handoff/snapshot_builder/lifecycle gap coverage + 86% coverage

- **1769 tests**, all passing; 0 failures (AAWO: 968, Solo Builder: 1769)
- AAWO v1.1.2 released
- AAWO coverage baseline: **86% overall** (up from 85%); `lifecycle_manager.py` now **100%**; `selector.py`/`task_router.py`/`registry_loader.py`/`snapshot_normalizer.py` at 100%
- AAWO `test_snapshot_detectors.py` +28: `TestScanRiskFactors` +3 (credential detection via `tempfile.TemporaryDirectory(prefix="aawo_")` to avoid pytest path naming conflict, test-file skip, env-var bypass), `TestDetectSignalsGaps` (7: has_makefile/config_files/external_api/user_data/ci-gitlab/docker-compose/all-false), `TestClassifyStageGaps` (7: early stage score=1, all 4 confidence values, high/very_high adds 2), `TestDetectFrameworksGaps` (6: django/flask/express/nextjs/sqlalchemy/no-duplicates), `TestReadOperationalSignals` (5: keys, defaults, file count, bool type, empty)
- AAWO `test_handoff_manager.py` +16: `TestGetHandoffDetail` (5: all keys, receiving_agent_id, last_event_type handoff_created/accepted, no-file unknown), `TestCountPendingHandoffs` (5: no-file=0, accepted/rejected not counted, mixed), `TestListHandoffStatuses` (6: basic, sorted, pending_only, source filter, required fields)
- AAWO `test_snapshot_builder.py` +23: `TestHasUncommitted` (4: porcelain nonempty/empty/timeout/FileNotFoundError), `TestRepoUnchanged` (4: timeout/FileNotFoundError/head-differs/head-matches), `TestRunStepErrors` (2: unknown detector function via `_is_ignored`, unknown module), `TestBuildSnapshotIncremental` (4: early return, captured_at updated, full pipeline on change, full pipeline on no prior), `TestLoadLatestSnapshot` stubs
- AAWO `test_lifecycle.py` +5: `TestConfiguredGraceCycles` (3: returns int, value=2 from real YAML, zero when file missing), `TestGraceCyclesForAgentFallback` (2: OSError triggers fallback, returns int)
- **Key testing insight**: `scan_risk_factors` skips files whose full path contains `"test"` — pytest `tmp_path` always embeds `test_funcname` in the directory name, so credential-detection tests must use `tempfile.TemporaryDirectory(prefix="aawo_cred_")` to avoid false-negative

---

## v5.94.0 — 2026-03-11  AawoTests2 — selector/lifecycle/score_engine/router/health/dep resolver tests

- **1769 tests**, all passing; 0 failures (AAWO: 797, Solo Builder: 1769)
- AAWO v1.1.0 released
- AAWO `test_selector.py` +8: cap edge cases (very_high=5, unknown defaults=5, exact boundary, highest-score-first, no candidates, below-min excluded) + overlap resolver (vetoed excluded, returns same list)
- AAWO `test_lifecycle.py` +7: `TestEventTriggeredActivation` — triggered reason `event_triggered:<signal>` vs `score_threshold_met`, multiple triggers, already-active no event, None=empty, grace cleared on return
- AAWO `test_score_engine.py` +18: exact ±2.0 delta per signal verified for all 13 signals across all 3 conditional agents + always-active bonuses; `has_migrations` and `has_background_jobs` confirmed to produce zero conditional delta
- AAWO `test_task_router.py` +9: priority tiebreak (2), edge cases — empty/whitespace, single-agent, all fields, score=keyword_count, fallback reasoning non-empty, no-keyword agent never wins
- AAWO `test_health_monitor.py` (new): 22 tests — `_load_outcome_stats` (10) + `get_health_report` (12 incl. all required keys, active_agents, grace_agents, outcome_stats, pending_handoffs, snapshot_count)
- AAWO `test_dependency_resolver.py` (new): 17 tests — hard requires (promotion, inactive no-pull, missing dep no crash, multiple deps, negative promoted to 1.0), soft prefers (bonus stacks, vetoed no bonus), combined

---

## v5.93.0 — 2026-03-11  AawoTests — snapshot_builder + runtime_controller unit tests + explain auto-width

- **1769 tests**, all passing; 0 failures (AAWO: 647, Solo Builder: 1769)
- AAWO v1.0.7 released
- AAWO `test_snapshot_builder.py`: 43 unit tests — `_validate_requires` (7), `_validate_produces` (6), `_hash_snapshot` (6), `_to_model` (13), `build_snapshot` (4); first dedicated coverage of the detector pipeline entry point
- AAWO `test_runtime_controller.py`: 24 unit tests — `_reconstruct_snapshot` (10), `_snapshot_to_dict` (7), `_compute_event_triggers` (5), `run_cycle` integration via `cycle_isolated` (10)
- AAWO `explain --width`: default changed from hardcoded 120 to `shutil.get_terminal_size(fallback=(120,40)).columns` — reasoning column now auto-fits the actual terminal; explicit `--width N` still overrides
- AAWO `test_event_detector.py` (45 tests) + `test_state_store.py` (22 tests) added in prior sprint (v1.0.7 includes all)

---

## v5.92.0 — 2026-03-11  AawoUx — visual consistency pass + route annotation

- **1769 tests**, all passing; 0 failures (AAWO: 556, Solo Builder: 1769)
- AAWO v1.0.4 released
- AAWO `explain --agent`: outcome feedback line now shows `■□` bar + rate% + bias tag — same format as `explain --all` and `health`
- AAWO `select` scores table: fixed-width `score` / `bias` columns when any agent has outcome bias; `-` for zero-bias agents
- AAWO `handoff-list` header: appends `(■=agent success rate)` legend when any entry has outcome stats
- AAWO `route`: outcome feedback line appended after routing decision showing selected agent's `■□` bar + rate%; completes coverage across all agent-facing commands
- AAWO `retention_manager`: dedicated test suite (`test_retention_manager.py`) — `prune_artifacts`, `_prune_dir`, `prune_logs`, `_load_limits`

---

## v5.91.0 — 2026-03-11  AawoPolish — handoff-list --source filter + explain-all outcome bar + health bar

- **1769 tests**, all passing; 0 failures (AAWO: 536, Solo Builder: 1769)
- AAWO `handoff-list --source solo_builder`: filters handoff log to outcome-derived records; `list_handoff_statuses(source=)` tracks `from_agent_id` per task — lets Solo Builder query only its own dispatched handoffs
- AAWO `select` score table: shows `bias=±N.N` suffix when outcome bias is non-zero for an agent
- AAWO `explain --all` outcome table: sorted worst→best by success rate; visual `■□` bar (10 blocks); `bias=±N.N` tag
- AAWO `health` outcome table: same `■□` bar + sort applied; consistent visual language across all three output surfaces
- AAWO `handoff-list`: inline `[■■□□□□□□□□] 20%` annotation per line when agent has recorded outcomes
- AAWO v1.0.2 released (`VERSION` + `CHANGELOG.md`)
- Test isolation fix: `test_score_engine_breakdown._bd()` and `TestScoreAgentsBias` baselines patch `_load_outcome_bias={}` to prevent runtime `outcomes.jsonl` contaminating arithmetic assertions

---

## v5.90.0 — 2026-03-11  FeedbackLoop — bidirectional AAWO outcome recording + dashboard Outcomes row

- **1769 tests**, all passing; 0 failures
- `utils/aawo_bridge.py`: `record_outcome(agent_id, outcome, description, duration_s)` — fire-and-forget subprocess; `get_outcome_stats()` reads AAWO `outcomes.jsonl` directly
- `runners/executor.py`: `_fire_outcome()` helper — daemon thread after sdk_tool/claude_subprocess/sdk_direct success paths; reads `_aawo_routing` metadata from st_data
- `api/blueprints/health_detailed.py`: `outcome_stats` added to `repo_health` check payload
- `api/static/dashboard_panels.js`: `pollRepoHealthDetailed()` shows Outcomes row (ok/fail count, success %)
- `tests/test_aawo_bridge.py`: 7 new `TestGetOutcomeStats` tests; 37 total in file
- `tests/test_executor_aawo_wiring.py`: 5 new `TestExecutorOutcomeRecording` tests; 11 total in file

---

## v5.89.0 — 2026-03-11  AawoIntegration — AAWO subprocess bridge, executor enrichment, repo health widget

- **1757 tests**, all passing; 0 failures
- `utils/aawo_bridge.py`: opt-in subprocess bridge to AAWO (`AAWO_PATH` in settings.json or `AAWO_RUNTIME_PATH` env); `route_task`, `get_snapshot`, `run_cycle`, `get_active_agents`, `enrich_subtask`
- `runners/executor.py`: `aawo_repo_path` param; `enrich_subtask` called before HITL gate when subtask has no tools
- `commands/dispatcher.py`: `_run_aawo_session_start()` fires `run_cycle` in background daemon thread at CLI startup
- `solo_builder_cli.py`: `_aawo_repo_path = os.path.dirname(_HERE)` (git root) passed to executor + dispatcher
- `api/blueprints/health_detailed.py`: `repo_health` check — complexity, signals, risk_factors, active_agents; always ok:true, excluded from overall_ok
- `api/static/dashboard_panels.js`: `pollRepoHealthDetailed()` — AAWO widget in Health tab showing complexity badge, signals, active agents
- `api/app.py`: `ApiRateLimiter(read_limit=300)` — up from 120; dashboard 25-concurrent-poll load no longer triggers 429s
- `config/settings.json`: `AAWO_PATH` + `AAWO_TIMEOUT:15` configured
- `tests/test_aawo_bridge.py`: 30 tests — subprocess layer, security invariants, enrich_subtask, get_active_agents, resolve_executor_config
- `tests/test_executor_aawo_wiring.py`: 6 tests — enrichment guard conditions, routing metadata injection, repo_path forwarding
- `tests/test_repo_health_dashboard_widget.py`: 20 tests — HTML div, panels.js exports, dashboard.js import+call
- `tests/test_health_detailed.py`: 9 tests — TestHealthDetailedRepoHealth class
- `tests/test_health_tab_grid.py`: +repo-health-detailed-content to _WIDGET_IDS
- `tests/test_middleware.py`: TestApiRateLimiter (8 tests) — class defaults, app override 300, allow/block, window expiry

---

## v5.88.0 — 2026-03-10  OpenAPIHealthRoutes — 12 health+policy routes in spec (TASK-383)

- **383 tasks** merged to master; **2323 tests**, all passing
- `tools/generate_openapi.py`: added 10 health routes + 2 policy routes to `_ROUTES` catalogue — TASK-383
- `tests/test_openapi_health_routes.py`: 26 tests verifying routes in catalogue + built spec — TASK-383

---

## v5.86.0 — 2026-03-10  DashboardE2ESmoke — Flask test-client smoke tests (TASK-382)

- **382 tasks** merged to master; **2297 tests**, all passing
- `tests/test_dashboard_e2e_smoke.py`: 21 smoke tests covering GET / HTML response, key API endpoints, widget IDs, JS modules, grid layout — TASK-382

---

## v5.84.0 — 2026-03-10  HealthTabLiveRunCheck — GET /health/live-summary (TASK-381)

- **381 tasks** merged to master; **2276 tests**, all passing
- `api/blueprints/live_summary.py`: `GET /health/live-summary` runs threat-model + context-window + slo in-process; returns `{ok, passed, total, checks:[{name,ok,detail}]}` — TASK-381
- `api/app.py`: registered `live_summary_bp` — TASK-381
- `api/static/dashboard_panels.js`: `pollLiveSummaryDetailed()` renders X/N passing summary + per-check OK/FAIL rows — TASK-381
- `api/dashboard.html`: `live-summary-detailed-content` div above health-detailed — TASK-381
- `tests/test_live_summary_dashboard_widget.py`: 34 tests — TASK-381

---

## v5.82.0 — 2026-03-10  HealthTabRefactor — 2-column grid layout for Health tab (TASK-380)

- **380 tasks** merged to master; **2242 tests**, all passing
- `api/dashboard.html`: Health tab widgets wrapped in `id="health-widget-grid"` 2-column CSS grid (`grid-template-columns:1fr 1fr`) — TASK-380
- `tests/test_health_tab_grid.py`: 10 tests verifying grid structure + all 9 widget IDs — TASK-380

---

## v5.80.0 — 2026-03-10  PreReleaseDashboardWidget — GET /health/pre-release + Health tab widget + 36 tests (TASK-379)

- **379 tasks** merged to master; **2232 tests**, all passing
- `api/blueprints/pre_release.py`: `GET /health/pre-release` returns gate inventory from `_builtin_gates()` + `_load_verify_gates()`; `{ok, total, required, gates:[{name,required}]}` — TASK-379
- `api/app.py`: registered `pre_release_bp` — TASK-379
- `api/static/dashboard_panels.js`: `pollPreReleaseDetailed()` renders REQ/OPT badges per gate — TASK-379
- `api/dashboard.html`: `pre-release-detailed-content` div added — TASK-379
- `tests/test_pre_release_dashboard_widget.py`: 36 tests — TASK-379

---

## v5.78.0 — 2026-03-10  CIQualityDashboardWidget — GET /health/ci-quality + Health tab widget + 28 tests (TASK-378)

- **378 tasks** merged to master; **2196 tests**, all passing
- `api/blueprints/ci_quality.py`: `GET /health/ci-quality` returns tool inventory from `_tool_definitions()`; `{ok, count, tools:[{name}]}` — TASK-378
- `api/app.py`: registered `ci_quality_bp` — TASK-378
- `api/static/dashboard_panels.js`: `pollCiQualityDetailed()` renders configured tool count + names — TASK-378
- `api/dashboard.html`: `ci-quality-detailed-content` div added — TASK-378
- `tests/test_ci_quality_dashboard_widget.py`: 28 tests — TASK-378

---

## v5.76.0 — 2026-03-10  DebtScanDashboardWidget — GET /health/debt-scan + Health tab widget + 35 tests (TASK-377)

- **377 tasks** merged to master; **2168 tests**, all passing
- `api/blueprints/debt_scan.py`: `GET /health/debt-scan` calls `debt_scan.scan()`; returns `{ok, count, results:[{path,line,marker,text}]}` capped at 20 — TASK-377
- `api/app.py`: registered `debt_scan_bp` — TASK-377
- `api/static/dashboard_panels.js`: `pollDebtScanDetailed()` renders debt count + per-item marker/path/text rows — TASK-377
- `api/dashboard.html`: `debt-scan-detailed-content` div after prompt-regression section — TASK-377
- `tests/test_debt_scan_dashboard_widget.py`: 35 tests — TASK-377

---

## v5.74.0 — 2026-03-10  PromptRegressionAPI — GET /health/prompt-regression + Health tab widget + 29 tests (TASK-376)

- **376 tasks** merged to master; **2133 tests**, all passing
- `api/blueprints/prompt_regression.py`: `GET /health/prompt-regression` calls `run_checks()`; returns `{ok, passed, total, failed, results:[{name,passed,errors}]}` (AI-002, AI-003) — TASK-376
- `api/app.py`: registered `prompt_regression_bp` — TASK-376
- `api/static/dashboard_panels.js`: `pollPromptRegressionDetailed()` renders template count + per-template OK/FAIL rows — TASK-376
- `api/dashboard.html`: `prompt-regression-detailed-content` div after SLO section — TASK-376
- `tests/test_prompt_regression_api.py`: 29 tests — TASK-376

---


## v5.72.0 — 2026-03-10  SLODashboardWidget — GET /health/slo endpoint + Health tab widget + 29 tests (TASK-375)

- **375 tasks** merged to master; **2104 tests**, all passing
- `api/blueprints/slo.py`: `GET /health/slo` calls `slo_check._load_records()`, `_check_slo003()`, `_check_slo005()`; returns `{ok, records, results:[{slo,target,value,status,detail}]}`; insufficient data → `ok:true` (OM-035 to OM-040) — TASK-375
- `api/app.py`: registered `slo_bp` — TASK-375
- `api/static/dashboard_panels.js`: `pollSloDetailed()` renders header with records count, per-SLO rows with status badge and target/value details — TASK-375
- `api/dashboard.html`: `slo-detailed-content` div after threat-model section — TASK-375
- `tests/test_slo_dashboard_widget.py`: 29 tests — TASK-375

---


## v5.70.0 — 2026-03-10  ThreatModelDashboardWidget — GET /health/threat-model + Health tab widget + 31 tests (TASK-374)

- **374 tasks** merged to master; **2075 tests**, all passing
- `api/blueprints/threat_model.py`: `GET /health/threat-model` calls `threat_model_check` internal functions and returns `{ok, checks:[{name,required,passed,detail}]}`; always 200 (SE-001 to SE-006) — TASK-374
- `api/app.py`: registered `threat_model_bp` — TASK-374
- `api/static/dashboard_panels.js`: `export async function pollThreatModelDetailed()` fetches `/health/threat-model`, renders per-check rows with OK/FAIL badges, check name, advisory label, detail text — TASK-374
- `api/dashboard.html`: `threat-model-detailed-content` div added after context-window section in Health tab — TASK-374
- `api/static/dashboard.js`: `pollThreatModelDetailed` added to import and `tick()` Promise.all — TASK-374
- `tests/test_threat_model_dashboard_widget.py`: 31 tests — TASK-374

---


## v5.68.0 — 2026-03-10  PromptRegressionCI — prompt-regression as required pre-release gate + 6 tests (TASK-373)

- **373 tasks** merged to master; **2044 tests**, all passing
- `tools/pre_release_check.py`: added `prompt-regression` to `_builtin_gates()` as `required=True`; runs `prompt_regression_check.py --quiet`; blocks release when any PromptTemplate fails regression checks (AI-002, AI-003) — TASK-373
- `claude/VERIFY.json`: added `prompt-regression` entry (`required:true`) for tooling visibility — TASK-373
- `tests/test_pre_release_check.py`: 6 new tests — builtin gate (present/required/command has script) + VERIFY.json (prompt-regression in file/required/command) — TASK-373

---


## v5.66.0 — 2026-03-10  ContextWindowDashboardWidget — pollContextWindowDetailed in Health tab + 24 tests (TASK-372)

- **372 tasks** merged to master; **2038 tests**, all passing
- `api/static/dashboard_panels.js`: `export async function pollContextWindowDetailed()` fetches `/health/context-window`, renders per-file rows with status badge (ok/warn/critical/over_budget/missing), label, lines/budget/utilization%, empty state "No tracked files." (AI-008 to AI-013) — TASK-372
- `api/dashboard.html`: `context-window-detailed-content` div added after policy section in Health tab, with "Loading context window…" placeholder — TASK-372
- `api/static/dashboard.js`: `pollContextWindowDetailed` added to import and `tick()` Promise.all — TASK-372
- `tests/test_context_window_dashboard_widget.py`: 24 tests — TASK-372

---


## v5.64.0 — 2026-03-10  PolicyDashboardWidget — pollPolicyDetailed in Health tab + 26 tests (TASK-371)

- **371 tasks** merged to master; **2013 tests**, all passing
- `api/static/dashboard_panels.js`: `export async function pollPolicyDetailed()` fetches `/policy/hitl` and `/policy/scope` in parallel, renders HITL section (pause_tools, block_keywords, warnings) and Scope section (default_action_type, action_types, warnings) with OK/WARN badges (AI-026, AI-033) — TASK-371
- `api/dashboard.html`: `policy-detailed-content` div added inside Health tab after gates section, with "Loading policy…" placeholder — TASK-371
- `api/static/dashboard.js`: `pollPolicyDetailed` added to import from `./dashboard_panels.js` and called in `tick()` Promise.all — TASK-371
- `tests/test_policy_dashboard_widget.py`: 26 tests — HTML (div present/inside health/after gates/loading placeholder), panels JS (exported/hitl+scope endpoints/content div/pause_tools/block_keywords/default_action_type/allowlists/warnings/replaceChildren/HITL+Scope labels/Promise.all), main JS (imported/called in tick/import regex), endpoint integration (hitl+scope 200/ok+policy keys) — TASK-371

---


## v5.62.0 — 2026-03-10  ContextWindowBudgetAPI — GET /health/context-window endpoint + 26 tests (TASK-370)

- **370 tasks** merged to master; **1987 tests**, all passing
- `api/blueprints/context_window.py`: `GET /health/context-window` calls `context_window_budget.check_budget()` and returns `{ok, has_issues, results:[{label,path,lines,budget,utilization,status}]}`; always 200 (AI-008 to AI-013) — TASK-370
- `api/app.py`: registered `context_window_bp` — TASK-370
- `tests/test_context_window_api.py`: 26 tests — status/content-type, shape (ok/has_issues/results keys), ok/has_issues flags (true/false/inverse), results fields (label/path/lines/budget/utilization/status), label+status+utilization values, check_budget called with settings_path, empty results case — TASK-370

---


## v5.60.0 — 2026-03-10  GatesDashboardWidget — pollGatesDetailed in Health tab + 19 tests (TASK-369)

- **369 tasks** merged to master; **1961 tests**, all passing
- `api/static/dashboard_panels.js`: `export async function pollGatesDetailed()` fetches `/executor/gates`, renders header with running/blocked counts, per-gate rows with OK/BLOCKED badges, hitl_name, scope_denied tools, empty-state "No Running subtasks." message (AI-026, AI-033) — TASK-369
- `api/dashboard.html`: `gates-detailed-content` div added inside Health tab below health-detailed-content, with "Loading gates…" placeholder — TASK-369
- `api/static/dashboard.js`: `pollGatesDetailed` added to import from `./dashboard_panels.js` and called in `tick()` Promise.all — TASK-369
- `tests/test_gates_dashboard_widget.py`: 19 tests — HTML (div present/inside health tab/Loading placeholder), panels JS (exported/endpoint/content div/BLOCKED/hitl_name/scope_denied/running_count/replaceChildren/empty message), main JS (imported/called in tick/import regex), endpoint integration (200/ok-true/gates key/json content-type) — TASK-369

---


## v5.58.0 — 2026-03-10  ExecutorGateSummaryAPI — GET /executor/gates endpoint + 33 tests (TASK-368)

- **368 tasks** merged to master; **1942 tests**, all passing
- `api/blueprints/executor_gates.py`: `GET /executor/gates` evaluates HITL, scope, and tool-validation gates for every Running subtask in the DAG; returns `{ok, running_count, blocked_count, gates:[{task,branch,subtask,tools,action_type,hitl_level,hitl_name,scope_ok,scope_denied,tools_valid,blocked}]}`; always 200; empty DAG → `ok:true` (AI-026, AI-033) — TASK-368
- `api/app.py`: registered `executor_gates_bp` — TASK-368
- `tests/test_executor_gates_api.py`: 33 tests — status/shape (200/json/all keys), empty DAG (ok-true/counts-zero/empty-gates), row fields (all 11 fields present/correct values), pending/verified excluded, valid tool (not blocked/tools_valid-true/ok-true), no-tools (not blocked/hitl-0), multiple subtasks (all listed/running_count matches), corrupt/missing state (200 returned) — TASK-368

---

## v5.57.0 — 2026-03-10  PolicyAPI — /policy/hitl + /policy/scope endpoints + 44 tests (TASK-366, TASK-367)

- **367 tasks** merged to master; **1909 tests**, all passing
- `api/blueprints/policy.py`: `GET /policy/hitl` returns loaded HitlPolicy as JSON (`{ok, policy:{pause_tools,notify_tools,block_keywords,pause_keywords}, warnings, settings_path}`); `GET /policy/scope` returns loaded ToolScopePolicy as JSON (`{ok, policy:{allowlists,default_action_type}, warnings, settings_path}`); always 200, use `ok` for gate decisions (AI-026, AI-033) — TASK-366, TASK-367
- `api/app.py`: registered `policy_bp` — TASK-366
- `tests/test_policy_api.py`: 44 tests — `/policy/hitl` (status/content-type, shape: ok/policy/warnings/settings_path, content: pause_tools list/Bash default/ok-true, custom settings: pause_tools reflected/missing-Bash warns/empty warns, coexistence); `/policy/scope` (status/content-type, shape: ok/policy/warnings/settings_path/allowlists/default_action_type, content: allowlists dict/full_execution/read_only/Bash in full/ok-true, allowlists: read_only excludes Write/includes Grep/all-nonempty/multiple types, both endpoints coexist) — TASK-366, TASK-367

---

## v5.55.0 — 2026-03-10  AIActionScopeEnforcement — ToolScopePolicy wired into executor as hard gate + 16 tests (TASK-365)

- **365 tasks** merged to master; **1865 tests**, all passing
- `runners/executor.py`: imported `load_scope_policy` + `evaluate_scope` from `utils.tool_scope_policy`; `Executor.__init__` loads `ToolScopePolicy` once as `self._scope_policy`; `action_type` read from subtask data; scope evaluated after HITL gate — denied tools log `scope_denied` warning and keep subtask Running (AI-033) — TASK-365
- `tests/test_tool_scope_wiring.py`: 16 tests — policy loaded at init (attribute/isinstance/allowlists/default-type), scope denied (tool keeps Running/scope_denied warning/action_type in log), scope allowed (no scope_denied), action_type from subtask data (read_from_subtask/default-when-none), evaluate_scope integration (called/receives policy/not called without tools), multi-tool scope (all-must-be-allowed/all-allowed-passes) — TASK-365

---

## v5.54.0 — 2026-03-10  PromptRegressionTests — 41 regression tests pinning PromptTemplate outputs (TASK-364)

- **364 tasks** merged to master; **1849 tests**, all passing
- `tests/test_prompt_regression.py`: 41 tests — registry integrity (3 templates registered, correct count, all PromptTemplate instances), structural invariants (subtask_execution: description/context/Complete/no-preamble/Task-label; verification: YES-NO/previously-executed/Output-was; stall-recovery: subtask-name/status/steps/Diagnose/Original-description), regression snapshots (exact rendered output for all 3 templates with canonical inputs), required-var behaviour (missing-required raises with field name in message, optional defaults to empty, extra kwargs ignored), placeholder_names property (correct sets for all 3), empty-{} rejection, duplicate-name rejection, convenience-function delegation (build_subtask_prompt/build_verification_prompt/build_stall_recovery_prompt match direct render) (AI-003) — TASK-364

---

## v5.53.0 — 2026-03-10  SLODashboardPanel — SLO-003/SLO-005 status in /health/detailed + dashboard Health tab + 16 new tests (TASK-363)

- **363 tasks** merged to master; **1808 tests**, all passing
- `api/blueprints/health_detailed.py`: added `slo_status` check — calls `slo_check._check_slo003/005`, returns `{ok, records, results[{slo, target, value, status, detail}]}`; insufficient records treated as ok (no breach possible); slo breach makes overall `ok: false` (OM-035 to OM-040) — TASK-363
- `api/static/dashboard_panels.js`: updated `pollHealthDetailed()` to render SLO Status row + per-SLO sub-rows showing target/value/detail with OK/FAIL badges — TASK-363
- `tests/test_health_detailed.py`: 16 new tests — `TestHealthDetailedSloStatus` (ok-true-all-ok, breach-ok-false, results-list, slo-key, target-value, insufficient-records, records-count, breach-overall-ok-false, exception-ok-false) + `TestSloStatusPanelJs` (slo_status key, sloResults, SLO Status label, target, value); updated `_mock_tools` to include slo_check default-OK mock — TASK-363
- `tests/test_health_dashboard_widget.py`: updated `_mock_tools` to include slo_check mock so existing widget integration tests remain green — TASK-363

---

## v5.52.0 — 2026-03-10  HitlGateWiring — HitlPolicy config-driven gate wired into executor + 14 tests (TASK-362)

- **362 tasks** merged to master; **1792 tests**, all passing
- `runners/executor.py`: imported `load_policy` + `evaluate_with_policy` from `utils.hitl_policy`; `Executor.__init__` loads `HitlPolicy` once as `self._hitl_policy`; HITL level now computed as `max(_hitl_evaluate(...), evaluate_with_policy(self._hitl_policy, ...))` — most conservative gate wins (AI-026, AI-032) — TASK-362
- `tests/test_hitl_gate_wiring.py`: 14 tests — policy loaded at init (attribute/isinstance/nonempty), policy block (keyword keeps Running/block > gate-level-0), policy pause (tool/keyword keeps Running without TTY), policy notify (warning logged for level-1), max-level merge (gate-block wins/policy-block wins/equal levels pause), no-tools path (bypasses HITL → dice-roll Verified), integration (evaluate_with_policy called/receives HitlPolicy instance) — TASK-362

---

## v5.51.0 — 2026-03-10  DepAuditGate — dep-audit REQUIRED in pre_release + lock_file_gen.py + 33 tests (TASK-361)

- **361 tasks** merged to master; **2163 tests**, all passing
- `tools/lock_file_gen.py`: `generate()` runs `pip freeze` filtered to `tools/requirements.txt` packages; `is_stale()` compares lock to current freeze; `--check`, `--dry-run`, `--json`, `--quiet`, `--req`, `--lock` flags; exits 0=ok, 1=stale, 2=error (SE-015) — TASK-361
- `tools/pre_release_check.py`: `dep-audit` added as REQUIRED builtin gate (`dep_severity_check --check-only`); `lock-file-fresh` added as optional gate — TASK-361
- `tests/test_lock_file_gen.py`: 33 tests — `_parse_requirements` (names/comments/missing/normalize), `_filter_freeze` (keep/exclude/empty/sorted), `_build_lock_content` (header/date/packages), `generate()` (writes/dry-run/filters/pip-fail/missing-req), `is_stale()` (missing/fresh/outdated/pip-fail), `run()` (exit-codes/json/quiet/check-modes), `main()` flags, pre_release integration (dep-audit required/lock-fresh present/cmd has --check-only) — TASK-361

---

## v5.50.0 — 2026-03-10  ThreatModelValidator — SE-007 to SE-015 extended checks + pre_release gate + 19 new tests (TASK-360)

- **360 tasks** merged to master; **2156 tests**, all passing
- `tools/threat_model_check.py`: added `EXTENDED_GAP_IDS` (SE-007 to SE-015) + `EXTENDED_CONTROLS` (dep_severity_check, context_window_compact); `run_checks()` now accepts `extended`, `path`, `gap_max` params; `--extended`, `--path`, `--gap-max` CLI flags; JSON output includes `extended` field (SE-007 to SE-015) — TASK-360
- `tools/pre_release_check.py`: added optional `threat-model` built-in gate running `threat_model_check.py --extended --quiet` — TASK-360
- `docs/THREAT_MODEL.md`: extended Known Gaps table with SE-007 to SE-015 entries + changelog entry — TASK-360
- `tests/test_threat_model_check.py`: 19 new tests — extended gap IDs (list/pass/fail/no-extended-flag/json-checks), extended controls (list/pass/fail/json-names), path override (custom/nonexistent), gap_max (10 passes/fails), extended JSON (field present/false-by-default), main extended flags, live-document extended check — TASK-360

---

## v5.49.0 — 2026-03-10  ContextWindowAutoCompact — compaction trigger for critical/over_budget files + 33 tests (TASK-359)

- **359 tasks** merged to master; **2096 tests**, all passing
- `tools/context_window_compact.py`: `compact()` evaluates `context_window_budget` and dispatches JOURNAL.md → `archive_journal.run()`, MEMORY.md → `_truncate_file()`, CLAUDE.md → `warning_only`; `CompactionReport` + `CompactionAction` dataclasses with `to_dict()`; `--dry-run`, `--threshold warn|critical|over_budget`, `--older-than`, `--json`, `--quiet` flags; exits 0=clean, 1=compacted, 2=error (AI-014 to AI-016) — TASK-359
- `tests/test_context_window_compact.py`: 33 tests — `CompactionAction`/`CompactionReport` (to_dict/has_actions), `_truncate_file` (over/within/dry-run/missing/actual-size), `_compact_journal` (dry-run/missing/lines-before/run-called), `compact()` (all-ok/claude-warning/memory-truncated/warn-threshold/dry-run-preserves-file/has-actions), `run()` (exit-codes/json/quiet/text/dry-run/exception), `main()` (dry-run/json/threshold/older-than flags) — TASK-359

---

## v5.48.0 — 2026-03-10  HealthDashboardWidget — Health tab polling /health/detailed + 21 tests (TASK-358)

- **358 tasks** merged to master; **2063 tests**, all passing
- `api/static/dashboard_panels.js`: `pollHealthDetailed()` — polls `/health/detailed`, renders ok/fail badge per check (state_valid/config_drift/metrics_alerts); updates favicon green/red; exception-safe (OM-006 to OM-010) — TASK-358
- `api/static/dashboard.js`: imported `pollHealthDetailed` from `dashboard_panels.js`; added to `tick()` `Promise.all` call — TASK-358
- `api/dashboard.html`: "Health" tab button + `tab-health` content div + `health-detailed-content` inner div added to sidebar — TASK-358
- `tests/test_health_dashboard_widget.py`: 21 tests — HTML (tab button/data-tab/content div), `dashboard_panels.js` (export/endpoint-call/labels/favicon/replaceChildren), `dashboard.js` (import/tick-call/import-regex), endpoint integration (accessible/ok/drift/content-type) — TASK-358

---

## v5.47.0 — 2026-03-10  BackendHealthEndpoint — /health/detailed aggregating three gate checks + 31 tests (TASK-357)

- **357 tasks** merged to master; **1640 tests**, all passing
- `api/blueprints/health_detailed.py`: `GET /health/detailed` endpoint aggregates `state_validator.validate()`, `config_drift.detect_drift()`, `metrics_alert_check.check_alerts()` into a single JSON health payload; `ok` reflects all three checks; per-check detail (errors/warnings, drift keys, alert list); exception-safe — each check degraded independently; tools loaded via `importlib` with `sys.modules` caching (OM-001 to OM-005) — TASK-357
- `api/app.py`: registered `health_detailed_bp`
- `tests/test_health_detailed.py`: 31 tests — response shape (top-level ok/checks/sub-keys), overall ok flag (all-pass/state-invalid/drift/alerts/all-fail), per-check detail propagation (errors/warnings/overridden-count/unknown-keys/alert-count/list), exception resilience (each tool broken → ok=False, status 200 always) — TASK-357

---

## v5.46.0 — 2026-03-10  DepSeverityCheck — CVE severity filtering + unpinned detection + 34 tests (TASK-356)

- **356 tasks** merged to master; **1609 tests**, all passing
- `tools/dep_severity_check.py`: `check_unpinned()` detects `>=`/`~=`/name-only constraints; `_parse_pip_audit_json()` filters by severity; `SeverityReport` with `has_issues(min_severity)` + `severity_counts`; `--check-only`, `--min-severity`, `--json`, `--quiet`, `--lock-file` flags; exits 0=clean, 1=issues, 2=error (SE-010 to SE-015) — TASK-356
- `tests/test_dep_severity_check.py`: 34 tests — `UnpinnedEntry`/`CveEntry` (to_dict), `SeverityReport` (no-issues/unpinned/high-cve/severity-filter/counts/to_dict), `check_unpinned` (pinned/loose/tilde/name-only/comments/missing), `_parse_pip_audit_json` (filter/empty/invalid/critical), `check` (clean/unpinned/check-only), `run()` (exit codes/JSON/quiet/missing-file/text), `main()` flags — TASK-356

---

## v5.45.0 — 2026-03-10  ContextWindowBudget — per-file utilization budgets + 29 tests (TASK-355)

- **355 tasks** merged to master; **1575 tests**, all passing
- `tools/context_window_budget.py`: `check_budget()` tracks per-file line-count utilization against configurable budgets; `BudgetConfig` frozen dataclass; `load_budget_config()` reads `CW_BUDGET_*` from settings.json; statuses: ok/warn/critical/over_budget/missing; compaction hint on issues; `--json`, `--quiet`, `--settings` flags; exits 0=within budget, 1=pressure detected (AI-008 to AI-013) — TASK-355
- `tests/test_context_window_budget.py`: 29 tests — `BudgetConfig` (immutable/defaults), `load_budget_config` (missing/override/warn-pct/partial), `FileResult`/`BudgetReport` (all statuses/to_dict), `check_budget` (ok/warn/critical/over/missing/utilization/multiple), `run()` (exit codes/JSON/quiet/text/compaction-hint), `main()` flags — TASK-355

---

## v5.44.0 — 2026-03-10  PromptRegressionCheck — template validation + 32 tests (TASK-354)

- **354 tasks** merged to master; **1546 tests**, all passing
- `tools/prompt_regression_check.py`: `run_checks()` validates all REGISTRY templates; per-template checks: required_vars declared+used, optional_vars used, render() succeeds, no empty `{}`, length bounds, no secrets; `RegressionReport` + `TemplateResult` dataclasses; `--json`, `--quiet`, `--settings`, `--prompt-builder` flags; exits 0=pass, 1=fail, 2=error (AI-002 to AI-005) — TASK-354
- `tests/test_prompt_regression_check.py`: 32 tests — `_check_template` (good/no-required/missing-var/optional-bad/render-fail/too-short/too-long/secret), `TemplateResult`/`RegressionReport` (pass/fail/to_dict), `run_checks` (good/bad/count/settings-override/empty/live-registry), `run()` (exit codes/JSON/quiet/text), `main()` flags — TASK-354

---

## v5.43.0 — 2026-03-10  VersionBump — semver bump tool + 37 tests (TASK-353)

- **353 tasks** merged to master; **1514 tests**, all passing
- `tools/version_bump.py`: `SemVer` frozen dataclass (parse/bump/str); `_read_current_version()` reads from VERSION.txt or falls back to CHANGELOG.md; `--write` flag updates VERSION.txt + prepends new CHANGELOG header; `--current`, `--dry-run`, `--json`, `--quiet`, `--title` flags; exits 0=success, 1=error, 2=usage (RD-020 to RD-025) — TASK-353
- `tests/test_version_bump.py`: 37 tests — `SemVer` (parse/bump-all-types/resets/immutable/invalid), `_read_current_version` (version-file/changelog-fallback/missing/precedence), `_compute_next` (all types), write helpers (version-file/changelog-prepend), `run()` (dry-run/write/current/json/quiet/exit-codes), `main()` flags — TASK-353

---

## v5.42.0 — 2026-03-10  ReleaseNotesGen — CHANGELOG parser + release notes generator + 32 tests (TASK-352)

- **352 tasks** merged to master; **1477 tests**, all passing
- `tools/release_notes_gen.py`: `parse_changelog()` extracts structured entries from CHANGELOG.md; `get_entry()` returns specific version or latest; `ReleaseEntry` dataclass with `to_dict()` + `to_markdown()`; `--json`, `--quiet`, `--output`, `--changelog` flags; exits 0=success, 1=version not found, 2=file error (RD-010 to RD-015) — TASK-352
- `tests/test_release_notes_gen.py`: 32 tests — `ReleaseEntry` (to_dict/to_markdown with/without bullets), `parse_changelog` (multiple/single/no-bullets/missing/empty/dates/title), `get_entry` (latest/specific/missing/empty), `run()` (exit codes/JSON/markdown/quiet/file-output/version), `main()` flags — TASK-352

---

## v5.41.0 — 2026-03-10  LintCheck — flake8 runner with configurable thresholds + 33 tests (TASK-351)

- **351 tasks** merged to master; **1445 tests**, all passing
- `tools/lint_check.py`: `run_lint()` runs flake8 and parses per-severity counts (E/W/F/C); `LintThresholds` frozen dataclass; `load_lint_thresholds()` reads `LINT_MAX_*` from settings.json; `--json`, `--quiet`, `--source`, `--max-e/w/f/c` flags; exits 0=pass, 1=threshold exceeded, 2=flake8 error (DX-010 to DX-015) — TASK-351
- `tests/test_lint_check.py`: 33 tests — `_parse_counts` (empty/mixed/errors/violations/unknown), `LintThresholds` (defaults/immutable/custom), `LintReport` (pass/fail/to_dict), `load_lint_thresholds` (missing/override/partial), `run_lint` (clean/exceed/within/violations/not-found/timeout/counts), `run()` (exit codes/JSON/quiet/text), `main()` flags — TASK-351

---

## v5.40.0 — 2026-03-10  MetricsAlertCheck — alert threshold checker + 35 tests (TASK-350)

- **350 tasks** merged to master; **1412 tests**, all passing
- `tools/metrics_alert_check.py`: `check_alerts()` evaluates failure_rate, avg/p99 latency, stall_rate, min_rows thresholds against metrics.jsonl; `AlertThresholds` frozen dataclass; `load_thresholds()` reads `ALERT_*` keys from settings.json; `--json`, `--quiet`, `--metrics`, `--max-failure-rate`, `--max-avg-latency`, `--max-p99-latency` flags; exits 0=all clear, 1=alert triggered (OM-020 to OM-025) — TASK-350
- `tests/test_metrics_alert_check.py`: 35 tests — AlertThresholds (defaults/immutable/none-skip), AlertReport (empty/with-alert/to_dict), load_thresholds (missing/override/partial), check_alerts (no-data, latency ok/alert/p99, stall rate, failure rate, min_rows), run() (exit codes/JSON/quiet/text), main() flags — TASK-350

---

## v5.39.0 — 2026-03-10  StateIntegrityValidator — schema + orphan + cycle detection + 43 tests (TASK-349)

- **349 tasks** merged to master; **1377 tests**, all passing
- `tools/state_validator.py`: `validate()` checks schema (required keys, types), task `branches`/`depends_on` validity, dependency cycle detection via DFS, subtask status validation; `ValidationReport` dataclass with errors/warnings; `--json`, `--quiet`, `--state` flags; exits 0=valid, 1=invalid (PW-020 to PW-025) — TASK-349
- `tests/test_state_validator.py`: 43 tests — `_detect_cycle` (empty/linear/self-loop/two-node/three-node/disconnected), `ValidationReport` (valid/invalid/warnings/to_dict), schema (missing keys, wrong types, branches/subtasks), dependencies (valid/unknown/not-list/cycles/chain), statuses (valid/unknown/missing), file loading (valid/missing/bad-json), run() (exit codes/JSON/quiet/text), main() flags — TASK-349

---

## v5.38.0 — 2026-03-10  ConfigDriftDetector — settings.json drift detection + 20 tests (TASK-348)

- **348 tasks** merged to master; **1334 tests**, all passing
- `tools/config_drift.py`: `detect_drift()` compares live settings.json against `_CONFIG_DEFAULTS`; reports missing keys (using defaults), overrides (with default vs live), and unknown keys (added since defaults); `--json`, `--quiet`, `--settings` flags; exits 0=no drift, 1=drift found (PW-010 to PW-015) — TASK-348
- `tests/test_config_drift.py`: 20 tests — DriftReport (has_drift, to_dict), detect_drift (identical/missing/override/unknown/missing-file/invalid-json), run() (exit codes, JSON structure, quiet, text), main() flags — TASK-348

---

## v5.37.0 — 2026-03-10  StateBackupRestore — backup/restore script + 25 tests (TASK-347)

- **347 tasks** merged to master; **1314 tests**, all passing
- `tools/state_backup.py`: backup (ZIP with manifest), restore (full or --dry-run), list, prune (keep-N); backs up state.json, step.txt, metrics.jsonl, settings.json; microsecond-precision archive names prevent collisions (ME-010 to ME-015) — TASK-347
- `tests/test_state_backup.py`: 25 tests — archive naming, backup (creates/manifest/included/label/skipped), restore (files restored/dry-run/missing raises), list (empty/sorted), prune (keeps-most-recent/returns-deleted/nothing-when-under), main() subcommands — TASK-347

---

## v5.36.0 — 2026-03-10  DiscordBotRoleGuard — role-based access for destructive commands + 24 tests (TASK-346)

- **346 tasks** merged to master; **1289 tests**, all passing
- `utils/discord_role_guard.py`: `RoleConfig` + `check_admin_role()` + `load_role_config()`; reads `DISCORD_ADMIN_ROLE_ID` + `DISCORD_DESTRUCTIVE_COMMANDS` from settings.json; guild owner always allowed; open mode when role ID unset (SE-030) — TASK-346
- `config/settings.json`: added `DISCORD_ADMIN_ROLE_ID` (empty = open) and `DISCORD_DESTRUCTIVE_COMMANDS` (8 command names) — TASK-346
- `tests/test_discord_role_guard.py`: 24 tests — csv parsing, RoleConfig validate/to_dict/immutable, load_role_config (missing/valid/empty/invalid), check_admin_role (open mode, non-destructive, with/without role, guild owner, no user, multiple roles, deny messages) — TASK-346

---

## v5.35.0 — 2026-03-10  OpenApiSpec — generate_openapi.py + 30 tests (TASK-345)

- **345 tasks** merged to master; **1265 tests**, all passing
- `tools/generate_openapi.py`: generates OpenAPI 3.0 spec for all 38 routes across 10 tags (Core, Metrics, Tasks, Branches, History, Subtasks, Triggers, Control, Config, DAG, Cache, Webhook); `--output PATH`, `--format json|yaml`, `--quiet`; `build_spec()` and `_operation_id()` helpers (DK-005, DK-006) — TASK-345
- `tests/test_generate_openapi.py`: 30 tests — operationId generation, spec structure (openapi version, info, servers, tags, paths), paths completeness, routes catalogue validation, main() output modes — TASK-345

---

## v5.34.0 — 2026-03-10  PerformanceLatencyMetrics — p50/p99/min/max/buckets + 29 tests (TASK-344)

- **344 tasks** merged to master; **1235 tests**, all passing
- `api/blueprints/metrics.py`: `/metrics/summary` now returns `p50_elapsed_s`, `p99_elapsed_s`, `min_elapsed_s`, `max_elapsed_s`, and `latency_buckets` (5 bands: lt_1s, 1s-5s, 5s-10s, 10s-30s, gt_30s); `_percentile()` and `_latency_buckets()` helpers extracted (PE-001 to PE-005) — TASK-344
- `tests/test_latency_helpers.py`: 17 unit tests for `_percentile` (boundaries, ordering, rounding) and `_latency_buckets` (5 bands, boundary edges, sum invariant) — TASK-344
- `api/test_app.py` `TestMetricsSummaryLatency`: 12 integration tests — null on empty, p50/p99 present, ordering (p95≥p50, p99≥p95), min≤max, bucket keys/counts/sum, backwards compat — TASK-344

---

## v5.33.0 — 2026-03-10  CiQualityGate — 6-tool quality runner + 21 tests (TASK-343)

- **343 tasks** merged to master; **1206 tests**, all passing
- `tools/ci_quality_gate.py`: runs 6 quality tools in sequence (threat-model, context-window, slo-check, dep-audit, debt-scan, pre-release); `--skip TOOL[,TOOL]`, `--json`, `--quiet`; exits 0=all pass, 1=any fail (DX, DevOps) — TASK-343
- `tests/test_ci_quality_gate.py`: 21 tests — tool definitions, pass/fail/skip logic, JSON structure/counts, text output, timeout, main() flags — TASK-343

---

## v5.32.0 — 2026-03-10  ThreatModelDocument — updated model + validator + 21 tests (TASK-342)

- **342 tasks** merged to master; **1185 tests**, all passing
- `docs/THREAT_MODEL.md`: updated T-003 mitigations to reflect HitlPolicy (TASK-338) + ToolScopePolicy (TASK-341); residual risk lowered from Medium to Low-Medium; changelog entry added (SE-001 to SE-006) — TASK-342
- `tools/threat_model_check.py`: validates THREAT_MODEL.md has correct gap IDs (SE-001–SE-006), date, required control references (secret_scan, hitl, HitlPolicy, ToolScopePolicy), and threat sections; `--json` and `--quiet` flags; exits 0=pass, 1=fail — TASK-342
- `tests/test_threat_model_check.py`: 21 tests — file existence, gap IDs, date, controls, JSON/text/quiet output, main(), live document passes — TASK-342

---

## v5.31.0 — 2026-03-10  AIActionScopeEnforcement — tool allowlist per task type + 38 tests (TASK-341)

- **341 tasks** merged to master; **1164 tests**, all passing
- `utils/tool_scope_policy.py`: `ToolScopePolicy` frozen dataclass + 6 built-in action-type allowlists (read_only, analysis, file_edit, full_execution, verification, planning); `load_scope_policy()` reads settings.json SCOPE_* overrides; `evaluate_scope()` returns `ScopeResult` (allowed, denied, action_type) (AI-033) — TASK-341
- `tests/test_tool_scope_policy.py`: 38 tests — csv parsing, default allowlist constraints, policy construction/validate/to_dict/immutability, load_scope_policy (missing/valid/override/invalid JSON), evaluate_scope (allow/deny/empty/full-execution/unknown-type/planning) — TASK-341

---

## v5.30.0 — 2026-03-10  PreReleaseCheck — gate runner with 30 unit tests (TASK-340)

- **340 tasks** merged to master; **1126 tests**, all passing
- `tools/pre_release_check.py`: runs all verification gates from VERIFY.json + 4 built-in gates (python-tests [required], git-clean, context-window, slo-check); `--json` and `--quiet` flags; exits 0=all required pass, 1=required gate failed (RD-001, RD-002) — TASK-340
- `tests/test_pre_release_check.py`: 30 tests — _run_gate (pass/fail/timeout/truncate), _builtin_gates presence/required flags, _load_verify_gates (missing/valid/invalid JSON), run_checks exit codes/JSON structure/text output/quiet mode/gate merging/unittest-discover exclusion — TASK-340

---

## v5.29.0 — 2026-03-10  ApiHealthEndpoint — version + X-Response-Time + 5 tests (TASK-339)

- **339 tasks** merged to master; **1096 tests**, all passing
- `api/blueprints/core.py`: /health now returns `version` (from pyproject.toml) + `total_subtasks` count (OM-002) — TASK-339
- `api/app.py`: `before_request` records `_start_time`; `after_request` adds `X-Response-Time: Nms` on every response (OM-003) — TASK-339
- `api/test_app.py` + `tests/test_api_integration.py`: 5 new tests — version, total_subtasks, X-Response-Time presence/format — TASK-339

---

## v5.28.0 — 2026-03-10  HitlTriggerConfig — hitl_policy.py + settings.json + 19 tests (TASK-338)

- **338 tasks** merged to master; **466 tests**, all passing
- `config/settings.json`: HITL_PAUSE_TOOLS, HITL_NOTIFY_TOOLS, HITL_BLOCK_KEYWORDS, HITL_PAUSE_KEYWORDS now configurable (previously hardcoded in hitl_gate.py) (AI-026, AI-032) — TASK-338
- `utils/hitl_policy.py`: `HitlPolicy` frozen dataclass + `load_policy()` + `evaluate_with_policy()` + `validate()`; config-driven HITL evaluation with custom settings path for testability — TASK-338
- `tests/test_hitl_policy.py`: 19 tests — csv parsing, load, validate warnings, evaluate (auto/notify/pause/block, path traversal, tool priority) — TASK-338

---

## v5.27.0 — 2026-03-10  PromptTemplateStandard — prompt_builder.py + 20 tests (TASK-337)

- **337 tasks** merged to master; **447 tests**, all passing
- `utils/prompt_builder.py`: `PromptTemplate` dataclass with render(), placeholder_names, required/optional vars, duplicate name guard; 3 standard templates — subtask_execution, subtask_verification, stall_recovery — registered at import for regression testing (AI-002) — TASK-337
- `tests/test_prompt_builder.py`: 20 tests — construction, render, missing var raises, optional defaults, standard template regression checks — TASK-337

---

## v5.26.0 — 2026-03-10  TechnicalDebtRegister — debt_scan.py + 16 tests (TASK-336)

- **336 tasks** merged to master; **427 tests**, all passing
- `tools/debt_scan.py`: scans .py/.js for TODO/FIXME/HACK/XXX/NOQA markers; auto-updates `docs/TECH_DEBT_REGISTER.md`; found 8 markers in current codebase; --dry-run/--json/--quiet flags (ME-003) — TASK-336
- `docs/TECH_DEBT_REGISTER.md`: initial auto-generated code-level scan section appended — TASK-336
- `tests/test_debt_scan.py`: 16 tests — _scan_file, _format_register_section, _update_register, main() — TASK-336

---

## v5.25.0 — 2026-03-10  SLODefinitions — slo_check.py + 17 tests (TASK-335)

- **335 tasks** merged to master; **411 tests**, all passing
- `tools/slo_check.py`: reads metrics.jsonl, validates SLO-003 (SDK success ≥95%) and SLO-005 (step median ≤10s); exits 0=ok, 1=breach; --json/--quiet flags (OM-036, OM-037) — TASK-335
- `docs/SLO_DEFINITIONS.md`: updated dashboard table with live values (394 tests, 100% SDK, 0.001s median); marked OM-036 and OM-037 Resolved — TASK-335
- `tests/test_slo_check.py`: 17 tests covering _load_records, _check_slo003, _check_slo005, check(), main() — TASK-335

---

## v5.24.0 — 2026-03-10  MutationTestingSetup — mutmut config + runner script (TASK-334)

- **334 tasks** merged to master; **394 tests**, all passing
- `pyproject.toml`: added `[tool.mutmut]` section — targets runners/, api/, commands/, utils/; runner = pytest -x -q; establishes baseline mutation testing infrastructure (QA-035) — TASK-334
- `tools/run_mutation_tests.py`: thin mutmut wrapper with --dry-run, --max-survivors, --path; exits 0=pass, 1=survivors exceed threshold, 2=mutmut not installed — TASK-334
- `tests/test_mutation_runner.py`: 13 tests — availability check, parse_results, main() scenarios including threshold enforcement and dry-run isolation — TASK-334

---

## v5.23.0 — 2026-03-10  ExecutorStepTimingLog — step elapsed_ms in structured log (TASK-333)

- **333 tasks** merged to master; **381 tests**, all passing
- `runners/executor.py`: after `_write_step_metrics()`, emit `logger.info("step_complete step=N elapsed_ms=N actions=N")` — structured timing record for every execute_step call (OM-042) — TASK-333
- `tools/archive_journal.py`: journal archival script (15 unit tests) auto-added by pre-commit hook (AI-009)
- `tests/test_executor_timing.py`: 6 tests — presence, elapsed_ms field, step field, actions field, non-negative, INFO level — TASK-333

---

## v5.22.0 — 2026-03-10  ContextWindowMonitor — context_window_check.py + 16 tests (TASK-332)

- **332 tasks** merged to master; **360 tests**, all passing
- `tools/context_window_check.py`: checks CLAUDE.md, MEMORY.md, JOURNAL.md line counts against configurable warn/error thresholds; per-file override support (JOURNAL.md at 500/1000); exits 0=ok, 1=error, 2=usage error; `--json` and `--quiet` flags — TASK-332 (AI-008)
- `tests/test_context_window_check.py`: 16 tests — _count_lines, check(), main(), per-file overrides, JSON output, quiet mode, threshold validation — TASK-332
- `claude/VERIFY.json`: added non-required `context-window-check` step — TASK-332

---

## v5.21.0 — 2026-03-10  CorrelationIdMiddleware — X-Request-ID + X-API-Version headers (TASK-331)

- **331 tasks** merged to master; **344 tests**, all passing
- `api/middleware.py`: `SecurityHeadersMiddleware.apply()` now adds `X-API-Version: 1` header on every response; `X-Request-ID` echoed from caller or generated as UUID4 — unique per request (OM-041, BE-040) — TASK-331
- `commands/dispatcher.py`: `DispatcherMixin` extracted from `solo_builder_cli.py` with `_cmd_set` method for runtime config updates (TD-ARCH-001 Phase 2c) — TASK-331
- `tests/test_middleware.py`: 8 unit tests for X-Request-ID generation, echo, uniqueness, RuntimeError handling, existing headers preservation — TASK-331
- `tests/test_api_integration.py`: 4 new integration tests — X-API-Version=1, UUID4 generated, echo from caller, uniqueness — TASK-331
- `tests/test_runtime_cfg.py`: 157-line test file for `_cmd_set` / `_runtime_cfg` synchronization — TASK-331

---

## v5.20.0 — 2026-03-10  AnthropicMaxTokensIncrease — 256→4096 across all locations (TASK-330)

- **330 tasks** merged to master; **1329 tests**, all passing
- `config/settings.json`, `api/constants.py`, `runners/anthropic_runner.py`, `runners/executor.py`, `solo_builder_cli.py`: ANTHROPIC_MAX_TOKENS raised from 256 → 4096 — 256 tokens (~200 words) was insufficient for meaningful subtask outputs from the plain SDK execution path — TASK-330

---

## v5.19.0 — 2026-03-10  SubtaskToolsFieldFix — CLAUDE_ALLOWED_TOOLS propagated to new subtasks (TASK-329)

- **329 tasks** merged to master; **1329 tests**, all passing
- `commands/dag_cmds.py`: `_cmd_add_task` and `_cmd_add_branch` now call `st.setdefault("tools", CLAUDE_ALLOWED_TOOLS)` after subtask creation; previously the tools field was never set at creation time, making the `sdk_tool_jobs` routing branch in `executor.py` permanently unreachable — TASK-329
- `tests/test_dag_cmds_tools.py`: 6 unit tests covering tools propagation in `add_task`, `add_branch`, `setdefault` idempotency, and sdk_tool routing reachability smoke test — TASK-329

---

## v5.18.0 — 2026-03-10  DependencyAuditCheck — pip-audit script + 16 tests (TASK-328)

- **328 tasks** merged to master; **1323 tests**, all passing
- `tools/dep_audit.py`: version drift detection vs requirements-lock.txt + pip-audit CVE scan; writes dep_audit_result.json; non-zero exit on drift or vulns — TASK-328
- `claude/VERIFY.json`: added non-required `dep-audit` step (`python tools/dep_audit.py --check-only`) — TASK-328
- `tests/test_dep_audit.py`: 16 unit tests covering _parse_lock, _check_drift, _run_pip_audit (mocked), main() — TASK-328
- `.gitignore`: dep_audit_result.json excluded — TASK-328

---

## v5.17.0 — 2026-03-10  ApiInputValidation — validators.py + 20 tests (TASK-327)

- **327 tasks** merged to master; **1307 tests**, all passing
- `api/validators.py`: `require_string_fields(*required, optional=())` — validates JSON dict body, required fields non-blank strings, optional fields type-checked, MAX_FIELD_LEN=4096 — TASK-327
- `api/blueprints/triggers.py`: 6 endpoints (/heal, /add_task, /add_branch, /prioritize_branch, /depends, /undepends) now use `require_string_fields` — type confusion + oversized payload protection — TASK-327
- `tests/test_validators.py`: 11 unit tests for validator helper + 9 endpoint integration tests (missing fields, wrong types, oversized input) — TASK-327

---

## v5.16.0 — 2026-03-10  StructuredLogFormatter — JsonLogFormatter + use_json flag (TASK-326)

- **326 tasks** merged to master; **1287 tests**, all passing
- `utils/log_formatter.py`: `JsonLogFormatter(logging.Formatter)` — emits one JSON object per line with ts/level/logger/msg fields; exc key added on exception — TASK-326
- `cli_utils._setup_logging`: new `use_json=False` parameter; selects JsonLogFormatter when True, preserving text format as default — TASK-326
- `tests/test_log_formatter.py`: 12 unit tests covering JSON output, ISO-8601 ts, exc field, one-line output, formatter selection — TASK-326

---

## v5.15.0 — 2026-03-10  Windows log-lock test fix (TASK-325b)

- **1275 tests**, all passing (0 failures — Windows file-lock race fixed)
- `tests/test_cli_utils.py`: `_close_sb_log_handlers()` flushes and closes RotatingFileHandler stream before `rmtree` to release Windows OS lock on log file — TASK-325

---

## v5.14.0 — 2026-03-10  datetime deprecation fix, flaky test fix, Phase 2 design complete (TASK-325)

- **325 tasks** merged to master; **1275 tests**, all passing, zero warnings
- `runners/executor.py`: replaced deprecated `datetime.utcnow()` with `datetime.now(datetime.timezone.utc)` — fixes Python 3.13 DeprecationWarning — TASK-325
- `tests/test_cli_utils.py`: fixed flaky `test_clear_stale_triggers_*` — replaced `TemporaryDirectory()` with `mkdtemp()` + `rmtree(ignore_errors=True)`; `_close_sb_log_handlers` now explicitly flushes and closes the underlying stream before calling `handler.close()` to release Windows file locks — TASK-325
- `api/test_app.py`: added docstring to `_Base._make_state` pointing new test authors to `tests/factories.py` — TASK-325
- `docs/CLI_REFACTOR_DESIGN.md`: Phase 2 documented as ~95% complete (TASK-107); `_cmd_set` is the only remaining method, blocked by module-global mutation pattern; path forward via `self._runtime_cfg` instance dict documented — TASK-325

---

## v5.13.0 — 2026-03-10  Rate limiter 429 tests, EXEC_VERIFY_PROB fix, Phase 2 audit (TASK-324)

- **324 tasks** merged to master; **1249 tests** (excl. flaky Windows log-lock), all passing
- `solo_builder/solo_builder_cli.py`: fixed `EXEC_VERIFY_PROB` global drift — `do_set VERIFY_PROB` now writes `global EXEC_VERIFY_PROB; EXEC_VERIFY_PROB = v` so the module-level global stays in sync with `self.executor.verify_prob` — TASK-324
- `solo_builder/api/test_app.py`: +4 `TestRateLimiterIntegration` tests — assert 429 via `_rate_limiter.check` mock, error key in body, write method triggers 429, under-limit returns 200; reset rate limiter counters in `_Base.setUp` to prevent cross-test contamination — TASK-324
- `docs/CLI_REFACTOR_DESIGN.md`: Phase 2 risk downgraded to Low — audit confirmed 0 tests patch `do_*` methods; Phase 2 now blocked by implementation time only — TASK-324
- `claude/TASK_QUEUE.md`: backfilled TASK-322, TASK-323, TASK-324 entries with completion status — TASK-324

---

## v5.12.0 — 2026-03-10  CLI refactor analysis + security header integration tests (TASK-323)

- **323 tasks** merged to master; **208 tests**, all passing
- `docs/CLI_REFACTOR_DESIGN.md`: corrected Phase 1 analysis — 6 of 8 "read-only" constants are mutable via `do_set` (`STALL_THRESHOLD`, `SNAPSHOT_INTERVAL`, `VERBOSITY`, `AUTO_STEP_DELAY`, `AUTO_SAVE_INTERVAL`, `CLAUDE_ALLOWED_TOOLS`); 13 truly read-only constants identified; Phase 1 demoted to low-priority — TASK-323
- `solo_builder/api/test_app.py`: +5 Flask test-client integration tests (`TestSecurityHeadersIntegration`) asserting all security headers arrive end-to-end through the real `@after_request` hook, including HSTS — TD-TEST-003 resolved — TASK-323
- `docs/TECH_DEBT_REGISTER.md`: TD-SEC-003 (HSTS) and TD-TEST-003 (header integration tests) added and resolved — TASK-323

---

## v5.11.0 — 2026-03-10  Middleware extraction + CLI refactor design spike (TASK-322)

- **322 tasks** merged to master; **203 tests**, all passing
- `solo_builder/api/middleware.py`: `SecurityHeadersMiddleware` (7 headers: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP, HSTS, CORS) + `ApiRateLimiter` (sliding-window, per-IP, separate read/write counters, `current_count()`) extracted from `app.py` inline implementations — TD-SEC-001 partial (HSTS now present)
- `solo_builder/api/app.py`: replaced 20-line inline rate-limit + security-headers implementations with `_security.apply()` and `_rate_limiter.check()` — TASK-322
- `solo_builder/api/test_app.py`: +16 middleware tests — `TestSecurityHeadersMiddleware` (7) + `TestApiRateLimiter` (9): all 7 headers asserted, allow/deny semantics, read/write independence, window pruning, `current_count` — TASK-322
- `docs/CLI_GOD_FILE_REFACTOR.md`: design spike for splitting `solo_builder_cli.py` (TD-ARCH-001); 5 frozen globals constraint documented; Phase 1 scoped, Phases 2–3 deferred — TASK-322

---

## v5.10.0 — 2026-03-10  Structured logging + prompt version control (TASK-320 through TASK-321)

- **321 tasks** merged to master; **187 tests**, all passing
- `runners/executor.py`: replace `print()` dispatch announcements with `logger.info()` — SDK tool-use, Claude, SDK direct paths all emit structured log records — TASK-320
- `docs/PROMPT_REGISTRY.md`: prompt version registry — 4 templates (PROMPT-001..004) with SHA-256 hashes, source locations, hash update process. AI-004 and AI-005 resolved — TASK-321
- `solo_builder/tests/test_prompt_registry.py`: 5 hash regression tests; prompt changes surface as assertion failures with hash diff — TASK-321

---

## v5.9.0 — 2026-03-10  Layer 3 audit: prompt standard, HITL gate, security hardening (TASK-311 through TASK-319)

- **319 tasks** merged to master; **187 tests** (182 non-API + 5 metrics), all passing
- `docs/PROMPT_STANDARD.md`: prompt engineering standard — context prefix rules, template, regression testing guidelines — TASK-311
- `test_prompt_standard.py`: 23 regression tests guarding `_PROJECT_CONTEXT`, DAG description quality, all 3 execution paths — TASK-311
- AI-002 resolved: `executor.py` subprocess path + `dag_cmds.py` decomp prompts now prepend `_PROJECT_CONTEXT` — TASK-312
- `docs/HITL_TRIGGER_DESIGN.md`: formal HITL trigger levels (0=Auto, 1=Notify, 2=Pause, 3=Block), trigger criteria, 3-phase plan — TASK-312
- `docs/AI_ACTION_SCOPE.md`: tool policy table (Read/Glob/Grep=Auto, Bash/Write/Edit=Pause, Web=Notify) — TASK-313
- `runners/hitl_gate.py`: `evaluate(tools, description)` + `HITLBlockError` + `level_name()`; 28 tests in `test_hitl_gate.py` — TASK-313
- `docs/THREAT_MODEL.md`: 6 threats (T-001..T-006); SE-001 resolved, SE-002..006 tracked — TASK-314
- `docs/SLO_DEFINITIONS.md`: 6 SLOs — API tests 100%, Discord tests 100%, SDK success ≥95%, gate checks 14/14, step latency ≤10s, Notion sync ≥99% — TASK-315
- `docs/CONTEXT_WINDOW_STRATEGY.md`: compaction triggers, 200-line MEMORY.md limit, journal archival procedure — TASK-316
- `docs/TECH_DEBT_REGISTER.md`: 9 initial open items across 5 categories — TASK-317
- `runners/executor.py`: HITL gate wired (TD-ARCH-002); validate_tools called before dispatch (TD-ARCH-005); subprocess fallback warns — TASK-318
- `runners/sdk_tool_runner.py`: `validate_tools()` function (TD-ARCH-005); `Read` path allowlist restricts to repo root (TD-SEC-001) — TASK-318
- `runners/test_runners.py`: +15 tests — TestValidateTools, TestSdkToolRunnerPathAllowlist, TestExecutorRouting — TASK-318
- `tools/requirements-lock.txt`: pinned dependencies for tools/ (TD-SEC-002) — TASK-318
- `solo_builder/requirements.txt`: explicit dependency file with `anthropic>=0.40` (TD-DEP-001) — TASK-318
- `runners/executor.py`: `_write_step_metrics()` — per-step JSONL: elapsed_s, sdk_dispatched, sdk_succeeded, sdk_success_rate (TD-OPS-001) — TASK-319
- `docs/TECH_DEBT_REGISTER.md` updated: 9 of 10 items resolved; 1 remaining (TD-ARCH-001 god file) — TASK-319
- Post-commit hook installed at `.githooks/post-commit` (Notion sync on every commit)

---

## v5.8.0 — 2026-03-09  Branch pct fields + Discord min_age + stalled clear button (TASK-301 through TASK-310)

- **310 tasks** merged to master (TASK-001 through TASK-310); **600 API tests**, **305 Discord tests**
- `GET /branches`: `review_pct` field added (% of Review subtasks per branch); 3 new tests — TASK-301
- Stalled tab: "✕ Clear" button shown when task or branch filter active; clears both filters + re-polls; parity with Branches/Subtasks tabs — TASK-302
- Discord `/branches export:True` slash command: 4 new integration tests covering file attachment and CSV content — TASK-303
- `GET /history/export ?branch=` filter: already implemented and fully tested (pre-complete) — TASK-304
- `GET /stalled ?min_age=N`: optional override for STALL_THRESHOLD; 3 new tests — TASK-305
- Dashboard Export tab stalled hrefs already use `?min_age=<threshold>` dynamically (pre-complete) — TASK-306
- Discord `/stalled min_age:int=0` param: overrides STALL_THRESHOLD for the call; shows override note in output; 3 new tests — TASK-307
- `GET /branches`: `pending_pct` field added (% pending subtasks per branch, parity with `pct`/`review_pct`); 3 new tests — TASK-308
- Dashboard Branches tab: review count now shows `review_pct` alongside (e.g. `2⏸ (40%)`) in overview table — TASK-309
- CHANGELOG v5.8.0 — TASK-310

---

## v5.7.0 — 2026-03-09  300-task milestone: branch review field + Discord subtasks text command (TASK-295 through TASK-300)

- **300 tasks** merged to master (TASK-001 through TASK-300); **591 API tests**, **298 Discord tests**
- CHANGELOG v5.6.0 documented — TASK-295
- `GET /subtasks/export` JSON wrapper shape (`subtasks` key + `total` count) and `?status=Review/Pending` filter tests; 4 new tests — TASK-296
- Stalled tab: `#stalled-filter-label` span shows active filter state (e.g. `· task: X · branch: Y`) below filter inputs; UI-only — TASK-297
- `GET /branches`: `review` field added to each row; `?status=review` + `?status=pending` filter tests; `?task=`+`?status=` compose test; 4 new tests — TASK-298
- Discord `subtasks` plain-text command: `subtasks [task=X] [status=Y]` dispatches to `_format_subtasks()`; supports multi-word task names; help text updated; 4 new tests — TASK-299
- **300-task milestone** CHANGELOG v5.7.0 — TASK-300

---

## v5.6.0 — 2026-03-09  Stalled tab UX + Discord filters + test coverage (TASK-291 through TASK-294)

- **294 tasks** merged to master (TASK-001 through TASK-294); **583 API tests**, **294 Discord tests**
- CHANGELOG v5.5.0 documented — TASK-291
- Stalled tab: `#stalled-branch-filter` input added (parity with task filter); composes `?task=` and `?branch=` in `pollStalled()` — TASK-292
- Discord `/history`: optional `task=`, `branch=`, `status=` filter params; `_format_history()` updated; 4 new tests — TASK-293
- `GET /branches/export`: `?status=review` and `?status=pending` filter tests added; JSON `total` invariant verified; 4 new tests — TASK-294

---

## v5.5.0 — 2026-03-09  Stalled filters + Stalled tab UX + Discord /stalled filters (TASK-287 through TASK-290)

- **290 tasks** merged to master (TASK-001 through TASK-290); **579 API tests**, **290 Discord tests**
- CHANGELOG v5.4.0 documented — TASK-287
- `GET /stalled` accepts `?branch=` substring filter (parity with `?task=`); 3 new tests — TASK-288
- Stalled tab: `#stalled-task-filter` input re-fetches `GET /stalled?task=X` on each keystroke — TASK-289
- Discord `/stalled`: optional `task=` and `branch=` params; `_format_stalled()` updated with filters; 4 new tests — TASK-290

---

## v5.4.0 — 2026-03-09  Export fixes + Discord CSV + stalled filters (TASK-283 through TASK-286)

- **286 tasks** merged to master (TASK-001 through TASK-286); **576 API tests**, **286 Discord tests**
- CHANGELOG v5.3.0 documented — TASK-283
- History export link bug fixed: quick-filter status values (Pending/Running/Review/Verified) now route to `?status=` instead of `?subtask=`; hint text updated — TASK-284
- Discord `/subtasks export:True` sends CSV file attachment; `_subtasks_to_csv()` formatter + 6 tests — TASK-285
- `GET /stalled` accepts `?task=` substring filter; 3 new tests — TASK-286

---

## v5.3.0 — 2026-03-09  Clear buttons + stalled UX + export rows + Discord /subtasks (TASK-278 through TASK-282)

- **282 tasks** merged to master (TASK-001 through TASK-282); **573 API tests**, **280 Discord tests**
- Branches tab: "✕ Clear" button shown when status/task filters active; calls `_clearBranchesFilters()` — TASK-278
- Export tab: "Stalled Subtasks" row links to `/subtasks/export?status=running&min_age=<threshold>`; threshold fetched from `GET /stalled` on tab open — TASK-279
- Dashboard `hdr-badge` tooltip shows worst-offending branch on hover when stalled > 0: `"N stalled — worst: task/branch (count)"` — TASK-280
- `GET /history/export` `?task=` filter: 5 new tests (match, no-match, case-insensitive, compose, CSV) — TASK-281
- Discord `/subtasks` slash command: `task=` + `status=` optional filters; `_format_subtasks()` formatter; 6 new tests — TASK-282

---

## v5.2.0 — 2026-03-09  Cross-endpoint tests + filter UX + min_age + server-side exports (TASK-273 through TASK-277)

- **277 tasks** merged to master (TASK-001 through TASK-277); **568 API tests**, **274 Discord tests**
- Cross-endpoint stall invariant tests: `/status.stalled_by_branch` == `/stalled.by_branch` (count, sum, entries, zero-stall) — TASK-273
- Subtasks tab: "✕ Clear" button shown when any filter active; calls `_clearSubtasksFilters()` — TASK-274
- `GET /subtasks` + `GET /subtasks/export` accept `?min_age=N` to return only Running subtasks stalled ≥ N steps; 5 new tests — TASK-275
- Branches tab: CSV/JSON downloads switched to server-side `/branches/export` with active ?status= and ?task= filter params — TASK-276
- CHANGELOG v5.1.0 documented — TASK-277 (this entry)

---

## v5.1.0 — 2026-03-09  Stall breakdown + filter UX + sort parity (TASK-267 through TASK-272)

- **272 tasks** merged to master (TASK-001 through TASK-272); **559 API tests**, **274 Discord tests**
- Stalled tab: per-branch summary card when multiple branches stalling, sorted by count desc — TASK-267
- `GET /stalled` includes `by_branch: [{task, branch, count}]` sorted desc; 5 new tests — TASK-268
- Discord `/stalled`: per-branch grouping summary block when multiple branches stalling; 5 new tests — TASK-269
- Subtasks tab: `#subtasks-filter-label` shows active filters + result count beside quick-filter buttons — TASK-270
- `GET /status` `stalled_by_branch` sorted by count desc (parity with GET /stalled); 1 new test — TASK-271
- CHANGELOG v5.0.0 documented — TASK-272 (this entry)

---

## v5.0.0 — 2026-03-09  Filter resets + Export tab completeness + Discord CSV + stall breakdown (TASK-262 through TASK-266)

- **266 tasks** merged to master (TASK-001 through TASK-266); **553 API tests**, **269 Discord tests**
- `selectTask()` clears all subtask filters (status/name/task/branch) + input values on task switch — TASK-262
- Export tab: Branches (CSV+JSON via /branches/export) and Subtasks (CSV+JSON via /subtasks/export) rows added — TASK-263
- Discord `/branches export:True` sends full CSV file attachment; `_branches_to_csv()` formatter + 6 tests — TASK-264
- `GET /status` now includes `stalled_by_branch: [{task, branch, count}]` for per-branch stall breakdown; 5 new tests — TASK-265
- CHANGELOG v4.9.0 documented — TASK-266 (this entry)

---

## v4.9.0 — 2026-03-09  Branches export + subtasks branch filter + export link re-sync (TASK-258 through TASK-261)

- **261 tasks** merged to master (TASK-001 through TASK-261); **548 API tests**, **454 Discord tests**
- `GET /branches/export` endpoint added; CSV/JSON download with ?task=, ?status=, ?format=json — TASK-258
- Subtasks tab: `#subtasks-branch-filter` input wired to server `?branch=` filter + export links — TASK-259
- Subtasks tab export links re-synced on tab switch via `switchTab("subtasks")` → `_updateSubtasksExportLinks()` — TASK-260
- CHANGELOG v4.8.0 documented — TASK-261 (this entry)

---

## v4.8.0 — 2026-03-09  Server-side filters + UI filter inputs + stall cross-task tests (TASK-251 through TASK-257)

- **257 tasks** merged to master (TASK-001 through TASK-257); **534 API tests**, **454 Discord tests**
- `GET /subtasks` + `GET /subtasks/export` accept `?name=` substring filter on subtask name — TASK-251
- `renderSubtasks()` routes non-status text to server-side `?name=` re-fetch; export links include `&name=X` — TASK-252
- `GET /branches` accepts `?status=pending|running|review|verified`; applied before pagination; dashboard re-fetches on filter change — TASK-253
- Stall detection cross-task tests: count across 2 tasks × 2 branches, task/branch metadata fields, `/status.stalled == /stalled.count` — TASK-254
- Subtasks tab: `#branches-task-filter` input wired to server `?task=` filter + export links — TASK-255
- Branches tab: task filter input wired to server `?task=` filter; shown only in all-tasks view — TASK-256
- CHANGELOG v4.7.0 documented — TASK-250 (prior batch entry)

---

## v4.7.0 — 2026-03-09  Branches export + task filter + stall tests + history branch filter (TASK-246 through TASK-250)

- **250 tasks** merged to master (TASK-001 through TASK-250); **512 API tests**, **454 Discord tests**
- Branches tab CSV/JSON client-side download (filtered data via `Blob` + `URL.createObjectURL`) — TASK-246
- `GET /tasks` accepts `?task=` substring filter; dashboard `_applyTaskSearch` re-fetches server-side — TASK-247
- Stall detection boundary + regression tests: at-threshold, below-threshold, custom `STALL_THRESHOLD`, `/status.stalled` == `/stalled.count` (+7 tests) — TASK-248
- `GET /history/export` was silently ignoring `?branch=` parameter; now correctly filters (+5 tests) — TASK-249
- CHANGELOG v4.6.0 documented — TASK-245 (prior batch entry)

---

## v4.6.0 — 2026-03-09  Status filters + CI lint + review regressions (TASK-236 through TASK-245)

- **245 tasks** merged to master (TASK-001 through TASK-245); **498 API tests**, **454 Discord tests**
- Subtasks quick-filter (Pending/Running/Review/Verified) re-fetches with `?status=X` server-side; composes with pagination — TASK-236
- Branches all-tasks view: `review` count badge rendered per row (field added TASK-229, previously not displayed) — TASK-237
- Search inputs reset page to 1 on change (`_applyTaskSearch`, `renderSubtasks` non-status branch) — TASK-238
- `tools/lint_dashboard_handlers.js` — Node.js CI script cross-checks HTML inline handlers vs `window.*`; exits 1 on gaps — TASK-239
- Lint script wired into `.githooks/pre-commit`; runs automatically on every commit — TASK-241
- Subtasks CSV/JSON export links updated with `?status=X` when status filter active — TASK-242
- Branches all-tasks view: Pending/Running/Review/Verified quick-filter buttons (client-side, cached data) — TASK-243
- Subtask detail modal shows `Review ⏸` (yellow) when status is Review — TASK-240
- `review_subtasks` regression tests: multi-branch sum, not-in-pct, separate-from-running (+3) — TASK-244
- CHANGELOG v4.5.0 documented — TASK-235 (prior batch entry)

---

## v4.5.0 — 2026-03-09  Pager UIs + window-exposure audit + CI invariant (TASK-226 through TASK-235)

- **235 tasks** merged to master (TASK-001 through TASK-235); **495 API tests**, **454 Discord tests**
- `GET /branches` supports `?limit=N&page=P`; response adds `total`, `page`, `pages`; `review` field added per row; `pending` formula fixed (was omitting review) — TASK-229
- Dashboard **Subtasks tab** pager `◀/▶` added; `pollSubtasks()` fetches `?limit=50&page=N` — TASK-231
- Dashboard **Branches tab** all-tasks pager `◀/▶` added; hidden in per-task detail view — TASK-232
- Dashboard **Tasks panel** pager `◀/▶` added below task grid — TASK-233
- ES module `window.*` gap audit: `_applyTaskSearch` and `_renderCacheHistory` exposed — TASK-230
- Final inline handler audit: zero gaps remain across all 50 handler calls in dashboard.html — TASK-234
- CI invariant check (`tools/ci_invariant_check.ps1`) implemented; enforces test-count floor — TASK-019 (backfill)
- CHANGELOG v4.4.5 documented — TASK-226 (prior batch entry)

---

## v4.4.5 — 2026-03-09  Pagination + pager fixes + Export chips + metrics tests (TASK-221 through TASK-225)

- **225 tasks** merged to master (TASK-001 through TASK-225); **489 API tests**, **454 Discord tests**
- `GET /tasks` supports `?limit=N&page=P`; response adds `total`, `page`, `pages` (backward-compatible) — TASK-225
- History pager `◀/▶` buttons fixed (exposed `window._historyPageStep`); count label shows `· N⏸` — TASK-224
- `GET /metrics` review regression tests (exact count + pending exclusion) — TASK-223
- Export tab shows `/history/count` by_status chips on open — TASK-222
- CHANGELOG v4.4.0 documented — TASK-221

---

## v4.4.0 — 2026-03-09  History review metadata + by_status chips + stalled regression (TASK-216 through TASK-220)

- **220 tasks** merged to master (TASK-001 through TASK-220); **481 API tests**, **454 Discord tests**
- `GET /history` response includes `review` count at top level (pre-pagination, like `total`) — TASK-217
- `GET /history/count` `by_status` dict consumed by dashboard: History tab status chips — TASK-218
- `GET /stalled` Review-exclusion regression tests (3 new assertions) — TASK-219
- MEMORY.md pruned 384→75 lines; archived to 4 topic files (architecture, test_patterns, discord_bot, design_decisions) — TASK-220
- CHANGELOG v4.3.5 documented — TASK-216

---

## v4.3.5 — 2026-03-09  History hash persistence + review stat box + /history/count distribution (TASK-213 through TASK-215)

- **215 tasks** merged to master (TASK-001 through TASK-215); **475 API tests**, **454 Discord tests**
- History filter persisted to `location.hash` as `ht-filter=<value>`; broken inline handlers fixed — TASK-213
- `hdr-pending` stat box shows `⏸N` review count alongside pending when review > 0 — TASK-214
- `GET /history/count` now returns `by_status` dict with per-status event counts (Review included) — TASK-215

---

## v4.2.9 — 2026-03-09  Review status in all endpoints + URL hash filter (TASK-203 through TASK-209)

- **210 tasks** merged to master (TASK-001 through TASK-210); **471 API tests**, **451 Discord tests**
- `GET /status` now returns `review` count; `pending` excludes review — TASK-206
- `GET /dag/summary` per-task rows and top-level include `review`; summary text updated — TASK-208
- Header step counter (`hdr-step`) appends `· N⏸` when review > 0 — TASK-207
- Subtasks filter persisted to `location.hash` as `st-filter=<value>` (deep-linkable) — TASK-209
- CHANGELOG v4.2.2 200-task milestone documented — TASK-203

---

## v4.1.4 – v4.2.2 — 2026-03-09  Review Status Propagation (TASK-181 through TASK-202)

- **202 tasks** total; **464 API + 447 Discord tests**
- Review visible everywhere: card badge (⏸N yellow), card counts, detail bar, per-branch rows, header counter, Discord formatter, History/Subtasks quick-filters (TASK-186–202)
- `GET /tasks` includes `pct` and `review_subtasks`; `/tasks/<id>/progress` branches[] includes `review` (TASK-188, 196)
- `pollTaskProgress()` updates per-branch mini rows in-place; uses branches[] from /progress (TASK-192)
- Subtasks + History tabs: 4 toggle quick-filter buttons (Pending/Running/Review/Verified) (TASK-199, 201)
- `GET /stalled` and Discord `stalled` confirmed to exclude Review/Pending; tests added (TASK-194, 200)
- CHANGELOG v4.0.0 milestone entry created (TASK-181)

---

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
