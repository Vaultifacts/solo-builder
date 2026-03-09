# HANDOFF: RESEARCH -> ARCHITECT
Task: TASK-107
Goal: Refactor solo_builder/solo_builder_cli.py (1393 lines) into focused modules

---

## File Analysis

`solo_builder/discord_bot/bot.py` — 2086 lines:
- Lines 33–46: Imports
- Lines 48–74: Module-level path constants (20+ triggers) + TOKEN/CHANNEL_ID
- Lines 81–653: 22 helper/formatter functions (`_load_state`, `_has_work`, `_find_subtask_output`, `_format_*`)
- Lines 659–701: `SoloBuilderBot(discord.Client)` class + `bot = SoloBuilderBot()`
- Lines 704–789: Error handler, `_auto_task`, `_HELP_TEXT`
- Lines 791–820: `_send()`, `_auto_running()`
- Lines 822–1246: `_handle_text_command()` — giant if/elif dispatcher (~425 lines)
- Lines 1252–1897: 39 slash command functions (`@bot.tree.command`) (~645 lines)
- Lines 1903–2086: Background tasks (`_read_heartbeat`, `_format_step_line`, `_run_auto`, `_poll_completion`, `main`)

## Critical Test Constraint

`test_bot.py` (2488 lines) imports `discord_bot.bot as bot_module` and patches via `patch.object(bot_module, ...)`.

**Must remain importable as `bot_module.<name>`:**
- All 20+ path constants (`STATE_PATH`, `VERIFY_TRIGGER`, etc.) — patched in nearly every test
- `_load_state`, `_send`, `_auto_running`, `_find_subtask_output`, `_read_heartbeat`, `_format_diff`, `_format_step_line` — patched directly
- `_auto_task` — mutated directly (lines 132, 297, 319 of test_bot.py)
- `_HELP_TEXT` — read directly (test_bot.py line 348)
- `_handle_text_command`, `_run_auto`, `_has_work` — called directly

**Safe to move (untested):** all 39 slash command functions at lines 1252–1897.

## Evidence-Backed Hypotheses

1. **Extracting the 39 slash commands to `bot_slash.py` is zero-risk**: slash commands are entirely untested — only `_handle_text_command` (plain-text path) is tested. Moving them reduces `bot.py` by ~645 lines.

2. **Extracting the 22 `_format_*` / helper functions to `bot_formatters.py` is safe with re-export**: if `bot.py` does `from .bot_formatters import _format_status, ...`, then `bot_module._format_status` still refers to the re-exported name in `bot.py`'s namespace — test patches work correctly.

3. **Circular import is avoidable**: `bot_formatters.py` functions that need path constants (`_format_diff`, `_format_cache`, `_format_log`, `_format_heal`) must use lazy imports (`import discord_bot.bot as _b`) inside function bodies — identical to the TASK-104 Flask Blueprint pattern that proved safe.

## Explicit Unknowns

1. `_format_cache`, `_format_log`, `_format_heal`, `_format_diff` — must verify exactly which path constants they reference before extracting to `bot_formatters.py`. Lazy imports handle this but need confirmation.

2. `_KEY_MAP` duplication — appears at lines 1073–1087 (text handler) and 1810–1824 (slash handler). Safe to deduplicate into module-level constant, no test dependency on location.

## Scope Boundary

- In scope: `bot.py`, `bot_formatters.py` (NEW), `bot_slash.py` (NEW), `claude/allowed_files.txt`
- Out of scope: `test_bot.py`, all other files
- Architecture score improvement: `bot.py` drops off the large-file list
