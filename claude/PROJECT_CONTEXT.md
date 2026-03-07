# Project Context

## Product
Solo Builder is an autonomous AI agent CLI that decomposes user-defined goals into a
directed acyclic graph (DAG) of subtasks and executes them using Claude (API or subprocess).

Core capabilities:
- 6 agents: Planner, ShadowAgent, SelfHealer, Executor, Verifier, MetaOptimizer
- 3 execution tiers: SdkToolRunner (async, tool-use), ClaudeRunner (subprocess), AnthropicRunner (SDK)
- 70-subtask initial DAG with fan-out/fan-in topology (Tasks 0–6)
- REVIEW_MODE: subtasks pause for manual verification before advancing
- Discord bot: 26 commands (slash + plain-text), IPC trigger files, heartbeat, chat.log
- Flask REST API + dark-theme SPA dashboard (polling, Run Step button)
- PDF snapshot exporter (4-page matplotlib report)

Current version: v2.1.51 — feature-frozen for this release.

## Architecture

```
solo_builder/
  solo_builder_cli.py       — main entry: all 6 agents + 3 runners (~2400 lines)
  discord_bot/bot.py        — Discord integration (26 commands, IPC, heartbeat)
  api/app.py                — Flask REST API (GET/POST endpoints)
  api/dashboard.html        — dark-theme SPA dashboard
  config/settings.json      — runtime config (18 keys)
  state/                    — runtime state files (state JSON, trigger files, lockfile)
  utils/helper_functions.py — ANSI codes, bars, DAG stats, validators
  profiler_harness.py       — benchmark harness (--dry-run for CI)

tools/                      — workflow enforcement scripts (PowerShell)
  start_task.ps1            — task initialization with preflight gating
  advance_state.ps1         — phase/role state transitions
  claude_orchestrate.ps1    — renders NEXT_ACTION.md from STATE.json
  workflow_preflight.ps1    — pre-init safety checks (clean tree, contract, consistency, ancestry)
  workflow_contract_check.ps1 — Direction A/B contract integrity checks
  ci_invariant_check.ps1    — CI-only verification (no lifecycle mutations)
  audit_check.ps1           — executes VERIFY.json commands, writes verify_last.json
  dev_gate.ps1              — pre-commit guard runner
  enforce_allowed_files.ps1 — blocks commits outside task scope

claude/                     — workflow state and agent handoff artifacts
  STATE.json                — machine-readable workflow state (task, phase, role, attempt)
  NEXT_ACTION.md            — rendered agent-facing contract (from orchestrator)
  VERIFY.json               — verification command contract
  WORKFLOW_SPEC.md          — canonical workflow specification
  PROJECT_CHECKLIST.md      — project completion tracking

.github/workflows/ci.yml    — GitHub Actions: contract check → invariant check → bundle
```

## Runtime

- Python 3.13, Node 24 (Windows 10 / Git Bash)
- Anthropic SDK: async `AsyncAnthropic` client; `SdkToolRunner` uses `asyncio.gather`
- Discord bot: `discord.py>=2.0`, `python-dotenv>=1.0`; runs in separate venv
- IPC: 12 trigger files under `state/` (presence-only or JSON); polled every 50ms in auto loop
- Lockfile: `state/solo_builder.lock` (PID-based, stale detection via `os.kill`)
- Config persistence: `config/settings.json` (18 keys, written on `set KEY=VALUE`)

## Constraints

- Windows 10 + Git Bash primary environment; all tools must be PowerShell 5.1+ compatible
- No PyPI publishing — personal use only
- Product code (`solo_builder/`) is feature-frozen at v2.1.51
- Workflow infrastructure hardening is complete as of TASK-022
- Major new capabilities (multi-model routing, scheduling, new agents) are post-v1 roadmap

## Risks

- Multiple background processes writing to the same state file can cause step-number drift
  in the dashboard — always `pkill -f solo_builder_cli.py` before starting a new run
- `O1` subtask (SdkToolRunner, reads large state file) can hit rate limits during
  high-concurrency runs; retried with exponential backoff (5s → 10s → 20s, capped 60s)
- `STALL_THRESHOLD` persists to `config/settings.json`; tests must mock config reads
  to avoid live-state interference (resolved in TASK-021)
