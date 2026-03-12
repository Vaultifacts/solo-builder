# Task Queue

## Completed Tasks (TASK-001 through TASK-415)
All tasks merged to `master`. See `claude/JOURNAL.md` and journal archive for history.
Latest: **v6.39.0** (2026-03-12)

Key milestones:
- TASK-103: solo_builder_cli.py 2965→1393 lines (mixin extraction)
- TASK-104: api/app.py 1729→84 lines (Flask Blueprints)
- TASK-105: dashboard.html 2587→349 lines (static CSS/JS)
- TASK-106: discord_bot/bot.py 2086→925 lines (bot_formatters + bot_slash)
- TASK-107: solo_builder_cli.py 1393→665 lines (dispatcher, auto_cmds, step_runner, cli_utils)
- TASK-300+: Tools layer (20+ tools: state_validator, lint, ci_quality, threat_model, etc.)
- TASK-400+: AAWO bridge, OpenAPI, blueprint coverage, architecture polish
- TASK-411–415: Dashboard panel extraction sprint (panels 1664→100 lines, -94%), ETag caching, bot extraction
- v6.35–6.39: Accessibility (ARIA, WCAG AA contrast, keyboard nav, skip-nav), tiered+tab-aware polling, notification sounds, dep viz

Current stats: 2641 tests, 0 failures, 90+ API routes, arch score 100.0/100, 17 ES modules

---

## Backlog (proposed)

### TASK-412 — SSE Real-Time Updates (Low priority)
Goal: Add Server-Sent Events for real-time dashboard updates

Research findings (v6.35.0):
- Flask reads state from `state.json` on disk per request (no in-memory event source)
- SSE needs `watchdog` file-watcher or state-change hook to push events
- Alternative: lightweight `/changes?since=<step>` endpoint (hybrid, no new deps)
- ETag caching + tiered polling + tab-aware polling already reduce API load ~85%

Priority: **Low** — existing optimizations make this non-urgent

### TASK-416 — Subtask Dependency Graph SVG (Medium priority)
Goal: Render a mini DAG visualization showing subtask dependency edges as SVG arrows in the detail panel

- Basic dep badges already exist (v6.39.0) with click-to-navigate
- Full SVG graph would show dependency chains visually (useful for complex multi-branch tasks)
- Use existing `dashboard_svg.js` helpers (svgBar, sparklineSvg) as foundation

### TASK-417 — Dashboard Performance Profiling (Low priority)
Goal: Add a hidden `?perf=1` mode that logs poll timing, DOM mutation counts, and memory usage

- Would help identify remaining optimization opportunities
- Console.time/timeEnd around each poller + MutationObserver count
- No production impact (behind query param flag)

### TASK-418 — Offline/PWA Support (Low priority)
Goal: Service worker for offline dashboard access

- Cache static assets (CSS, JS, HTML)
- Show last-known state when server is unreachable
- Stale banner already exists for connectivity loss detection
