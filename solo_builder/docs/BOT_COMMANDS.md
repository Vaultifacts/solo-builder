# Solo Builder Discord Bot — Command Reference

All commands work as both plain-text (no prefix) and slash commands (prefix with `/`).
Channel restriction: set `DISCORD_CHANNEL_ID` in `.env` to restrict to one channel.

---

## Status & Monitoring

| Command | Description |
|---|---|
| `status` / `/status` | DAG progress summary with per-branch bar charts. Shows auto-run indicator if running. |
| `heartbeat` / `/heartbeat` | Live counters from `state/step.txt` without parsing state JSON |
| `tasks` / `/tasks` | Per-task summary table — task name, verified/total count, %, status |
| `stats` / `/stats` | Per-task breakdown: verified count, total, %, average steps |
| `agents` / `/agents` | All agent statistics: Planner cache, Executor throughput, SelfHealer, MetaOptimizer |
| `forecast` / `/forecast` | Completion forecast: % done, verified/step rate, ETA in steps |
| `priority` / `/priority` | Priority queue — which subtasks will execute next, ranked by risk score |
| `stalled` / `/stalled` | Subtasks stuck longer than STALL_THRESHOLD steps |
| `history [N]` / `/history [n]` | Last N status transitions (default 20) |
| `diff` / `/diff` | Changes since last save |
| `config` / `/config` | All current runtime settings |
| `graph` / `/graph` | Visual ASCII DAG dependency graph |

---

## Execution Control

| Command | Description |
|---|---|
| `run` / `/run` | Trigger one CLI step |
| `auto [N]` / `/auto [n]` | Run N steps automatically (omit N for full run until complete) |
| `stop` / `/stop` | Cancel auto-run — CLI halts after the current step |
| `pause` / `/pause` | Pause auto-run (can be resumed) |
| `resume` / `/resume` | Resume a paused auto-run |

---

## Subtask Management

| Command | Description |
|---|---|
| `verify <ST> [note]` / `/verify` | Approve a Review-gated subtask. Advances from Review → Verified. |
| `output <ST>` / `/output` | Show Claude output for a specific subtask |
| `describe <ST> <prompt>` / `/describe` | Set a custom Claude prompt; subtask re-runs at next step |
| `tools <ST> <tool,list>` / `/tools` | Set allowed tools (e.g. `Read,Glob,Grep` or `none`) |
| `rename <ST> <desc>` / `/rename` | Update a subtask's description field |
| `heal <ST>` / `/heal` | Reset a stuck Running subtask to Pending |
| `timeline <ST>` / `/timeline` | Status history timeline for a subtask |
| `output <ST>` / `/output` | Show Claude output (truncated to 1800 chars) |

---

## Task & Branch Management

| Command | Description |
|---|---|
| `add_task <spec>` / `/add_task` | Queue a new task — CLI adds it at the next step boundary |
| `add_branch <task> <spec>` / `/add_branch` | Queue a new branch on an existing task |
| `prioritize_branch <task> <branch>` / `/prioritize_branch` | Boost a branch's subtasks to front of execution queue |
| `depends [<task> <dep>]` / `/depends` | Add a dependency or show the dep graph (bare command = show graph) |
| `undepends <task> <dep>` / `/undepends` | Remove a dependency |
| `branches [task]` / `/branches` | List branches for a task (or overview of all) |

---

## Search & Filter

| Command | Description |
|---|---|
| `search <keyword>` / `/search` | Find subtasks by keyword in name/description/output |
| `filter <status>` / `/filter` | Show subtasks matching a status: `Verified`, `Running`, `Pending`, `Review` |
| `log [ST]` / `/log` | Show journal entries (optionally filtered to one subtask) |

---

## Settings & Config

| Command | Description |
|---|---|
| `set KEY=VALUE` / `/set key value` | Change a runtime setting (queued — takes effect at next step boundary) |
| `set KEY` / `/set key` | Show current value of a setting (reads `config/settings.json` directly) |

**Known settable keys:** `STALL_THRESHOLD`, `SNAPSHOT_INTERVAL`, `VERBOSITY`, `VERIFY_PROB`,
`AUTO_STEP_DELAY`, `AUTO_SAVE_INTERVAL`, `CLAUDE_ALLOWED_TOOLS`, `ANTHROPIC_MAX_TOKENS`,
`ANTHROPIC_MODEL`, `CLAUDE_SUBPROCESS`, `REVIEW_MODE`, `WEBHOOK_URL`

---

## Persistence & Export

| Command | Description |
|---|---|
| `export` / `/export` | Download `solo_builder_outputs.md` as a file attachment |
| `snapshot` / `/snapshot` | Trigger a PDF timeline snapshot (attaches latest PDF if available) |
| `undo` / `/undo` | Undo last step (restore from pre-step backup) |
| `reset confirm` / `/reset confirm:yes` | Reset DAG to initial state — **destructive, requires confirmation** |

---

## Help

| Command | Description |
|---|---|
| `help` / `?` / `/help` | Show plain-text command list |

---

## REVIEW_MODE

When `REVIEW_MODE=true`, subtasks that would auto-verify are paused at `Review` status (shown as ⏸).
Use `verify <ST>` to advance them individually. Useful for human-in-the-loop approval workflows.

---

## Auto-run Tickers

During `auto` runs, the bot posts a per-step ticker:
```
Step 42 — 35✅ 4▶ 3⏸ 28⏳ / 70 (50.0%)
```

After the run completes (or all subtasks reach Verified), a 🎉 completion notification is sent.

---

## Notes

- All plain-text commands work without the `/` prefix
- Messages longer than 1950 characters are automatically paginated
- All bot interactions are logged to `discord_bot/chat.log` with UTC timestamps
- Trigger-file-based commands (add_task, describe, verify, etc.) take effect at the **next CLI step boundary**, not immediately
