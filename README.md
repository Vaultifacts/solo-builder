# Solo Builder

Autonomous AI agent CLI that decomposes a user-defined goal into a directed acyclic graph (DAG)
of subtasks and executes them using Claude (API or subprocess).

## Quick start

```bash
cd solo_builder
python solo_builder_cli.py
```

For the dashboard (in a second terminal):
```bash
python api/app.py   # open http://127.0.0.1:5000
```

## What's inside

| Path | Description |
|---|---|
| `solo_builder/solo_builder_cli.py` | Main entry — 6 agents, 3 runners, 70-subtask DAG |
| `solo_builder/discord_bot/bot.py` | Discord bot (26 commands, IPC, heartbeat) |
| `solo_builder/api/` | Flask REST API + dark-theme SPA dashboard |
| `tools/` | PowerShell workflow enforcement scripts |
| `claude/` | Workflow state and agent handoff artifacts |
| `.github/workflows/ci.yml` | GitHub Actions CI |

## Architecture and runtime details

See [`claude/PROJECT_CONTEXT.md`](claude/PROJECT_CONTEXT.md) for the full product/architecture
summary, runtime constraints, and known operational risks.

## Workflow (for contributors / agents)

See [`CLAUDE.md`](CLAUDE.md) for the workflow contract and agent entry instructions.

## Tests

```bash
python -m unittest discover
```

195 tests, 0 failures expected.

## Version

v2.1.51 — feature-frozen.
