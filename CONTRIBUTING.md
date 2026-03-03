# Contributing to Solo Builder

This is a personal project but contributions are welcome.

---

## Project layout

```
solo_builder_cli.py     (~2500 lines) — all six agents + four execution tiers
api/app.py              — Flask REST API
api/dashboard.html      — live SPA dashboard
discord_bot/bot.py      — Discord bot (slash + plain-text commands)
discord_bot/test_bot.py — 21 unit tests, no Discord connection required
utils/helper_functions.py
config/settings.json    — runtime config (do not commit local edits)
profiler_harness.py     — standalone perf benchmark
```

---

## Running tests

```bash
# Fast unit tests (no API key, no Discord, ~0.03 s)
python discord_bot/test_bot.py

# Full headless smoke test (mirrors CI)
python solo_builder_cli.py --headless --auto 10 --no-resume
```

CI runs automatically on every push to `master` via GitHub Actions.

---

## Four-tier executor routing

Every Running subtask is dispatched to one of four paths, in priority order:

| Tier | Condition | Mechanism |
|---|---|---|
| **SdkToolRunner** | subtask has tools + `ANTHROPIC_API_KEY` set | async SDK tool-use (Read/Glob/Grep), `asyncio.gather` |
| **ClaudeRunner** | subtask has tools, no API key (or SdkToolRunner fails) | `claude -p` subprocess with `--allowedTools` |
| **AnthropicRunner** | no tools + `ANTHROPIC_API_KEY` set | direct SDK call, `asyncio.gather` |
| **Dice roll** | no API key, no CLI | probability-based fallback (`EXECUTOR_VERIFY_PROBABILITY`) |

Only `ClaudeRunner` (subprocess) uses `ThreadPoolExecutor`. All SDK paths use `asyncio.gather`.

---

## DAG structure

```
Task 0 (8 subtasks: Branch A×5, Branch B×3)
   └──> Tasks 1–5 (parallel fan-out, unlocked when Task 0 is Verified)
             └──> Task 6 (fan-in, uses Read/Glob/Grep tools on live state file)
```

The **Planner priority cache** refreshes every `DAG_UPDATE_INTERVAL` steps *and* immediately whenever the count of fully-Verified tasks increases. This prevents newly-unlocked tasks from being invisible to the executor until the next scheduled refresh.

---

## REVIEW_MODE

When `REVIEW_MODE=true`, subtasks pause at `Review` status instead of auto-verifying. Advance them with:

```
solo-builder > verify <SUBTASK> [optional note]
```

Both the SDK paths and the dice-roll fallbacks respect this setting.

---

## Adding a new CLI command

1. Add a `_cmd_<name>` method to the `SoloBuilderCLI` class.
2. Add a dispatch branch in `handle_command`.
3. Add a `("syntax", "description")` row in `_cmd_help`.
4. Add the command name to the footer hint string near the `_cmd_help` call.

---

## Commit style

Conventional commits with `[AUTO]` prefix when Claude commits:

```
feat: add new feature
fix: correct a bug
docs: documentation only
chore: tooling / CI
```

---

## What not to do

- Do not commit `.env`, API keys, or `state/` files.
- `journal.md` is auto-generated — it is `.gitignore`-d.
- Do not add error handling or comments for code you did not change.
- Do not introduce abstractions for one-off operations.
