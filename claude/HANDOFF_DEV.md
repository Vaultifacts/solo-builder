# HANDOFF TO DEV (from ARCHITECT)

## Task
TASK-106

## Goal
Refactor `solo_builder/discord_bot/bot.py` (2086 lines) into focused modules.
Target: bot.py < 1000 lines. All 325 tests must pass after every commit.

---

## Critical Constraints

1. `test_bot.py` imports `discord_bot.bot as bot_module` and patches module-level names
   via `patch.object(bot_module, ...)`. Every patched name must remain importable as
   `bot_module.<name>` — this is enforced by re-exporting from `bot.py`.

2. Patched path constants (must stay in bot.py): `STATE_PATH`, `STEP_PATH`, `TRIGGER_PATH`,
   `VERIFY_TRIGGER`, `STOP_TRIGGER`, `ADD_TASK_TRIGGER`, `ADD_BRANCH_TRIGGER`,
   `PRIORITY_BRANCH_TRIGGER`, `DESCRIBE_TRIGGER`, `TOOLS_TRIGGER`, `RESET_TRIGGER`,
   `SNAPSHOT_TRIGGER`, `SNAPSHOTS_DIR`, `SETTINGS_PATH`, `JOURNAL_PATH`, `UNDO_TRIGGER`,
   `DEPENDS_TRIGGER`, `UNDEPENDS_TRIGGER`, `PAUSE_TRIGGER`, `RENAME_TRIGGER`,
   `HEAL_TRIGGER`, `SET_TRIGGER`

3. Patched functions/globals (must remain importable as `bot_module.<name>`):
   `_load_state`, `_send`, `_auto_running`, `_find_subtask_output`, `_read_heartbeat`,
   `_format_diff`, `_format_step_line`, `_handle_text_command`, `_run_auto`, `_has_work`,
   `_auto_task`, `_HELP_TEXT`

4. Slash commands (lines 1252–1897) are ENTIRELY UNTESTED — zero risk to move them.

---

## Implementation Plan

### Step 1 — Extract `bot_formatters.py` + hoist `_KEY_MAP`

**Create `solo_builder/discord_bot/bot_formatters.py`:**
- Define `_ROOT = Path(__file__).resolve().parent.parent` at module top
- Move these 16 functions verbatim (no logic changes):
  - `_has_work(dag)`
  - `_find_subtask_output(state, st_target)`
  - `_format_search(state, query)`
  - `_format_branches(state, task_filter="")`
  - `_format_history(state, limit=20)`
  - `_format_stats(state)`
  - `_format_cache(clear=False)` — uses `_ROOT` inline (not a patched constant)
  - `_format_tasks(state)`
  - `_format_priority(state)`
  - `_format_stalled(state)` — uses `_ROOT` inline (not a patched constant)
  - `_format_agents(state)` — uses `_ROOT` inline (not a patched constant)
  - `_format_forecast(state)`
  - `_format_filter(state, status)`
  - `_format_timeline(state, st_target)`
  - `_format_status(state)`
  - `_format_graph(state)`

**In `bot.py`:**
- Add import block right after module-level constants:
  ```python
  from .bot_formatters import (
      _has_work, _find_subtask_output, _format_search, _format_branches,
      _format_history, _format_stats, _format_cache, _format_tasks,
      _format_priority, _format_stalled, _format_agents, _format_forecast,
      _format_filter, _format_timeline, _format_status, _format_graph,
  )
  ```
- Remove the 16 function bodies from bot.py
- Hoist `_KEY_MAP` dict (lines 1073–1087) to module level, removing it from inside
  `_handle_text_command`; the text handler references module-level `_KEY_MAP`

**Verification:** `python -m unittest discover` — 325 tests pass

### Step 2 — Extract `bot_slash.py`

**Create `solo_builder/discord_bot/bot_slash.py`:**
- Define `register_slash_commands(bot)` function that registers all 39 slash commands
- At top of the function body: `import discord_bot.bot as _b` (lazy, runs after bot.py loads)
- Move all 39 `@bot.tree.command(...)` functions inside `register_slash_commands(bot)`
- All references to path constants → `_b.TRIGGER_PATH`, `_b.VERIFY_TRIGGER`, etc.
- All references to helpers → `_b._format_status()`, `_b._load_state()`, etc.
- `global _auto_task` assignments → `_b._auto_task = asyncio.create_task(...)`
- Check for `_auto_running()` → `_b._auto_running()`
- The `_KEY_MAP` in slash `set_cmd` → reference `_b._KEY_MAP` (hoisted in step 1)

**In `bot.py`:**
- Remove lines 1252–1897 (39 slash commands)
- Add after `bot = SoloBuilderBot()` and error handler:
  ```python
  from .bot_slash import register_slash_commands
  register_slash_commands(bot)
  ```

**Verification:** `python -m unittest discover` — 325 tests pass

---

## Allowed Changes

```
solo_builder/discord_bot/bot.py
solo_builder/discord_bot/bot_formatters.py   (NEW)
solo_builder/discord_bot/bot_slash.py        (NEW)
claude/allowed_files.txt
```

---

## Acceptance Criteria

1. `python -m unittest discover` — 325 tests pass after each commit
2. `wc -l solo_builder/discord_bot/bot.py` — fewer than 1100 lines
3. `solo_builder/discord_bot/bot_formatters.py` exists with 16 formatter functions
4. `solo_builder/discord_bot/bot_slash.py` exists with `register_slash_commands(bot)`
5. `from discord_bot.bot import _format_status, _load_state, _auto_task` all work
6. No logic changes — move code only

---

## Constraints

- Do NOT modify `test_bot.py`
- Re-export all moved functions from `bot.py` via explicit imports (not `import *`)
- `register_slash_commands(bot)` must be called in bot.py AFTER `bot = SoloBuilderBot()`
  but BEFORE `if __name__ == "__main__":`
- Commit after each step
