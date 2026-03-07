# HANDOFF TO ARCHITECT (from RESEARCH)

## Task
TASK-023

## Finding
`test_stalled_empty` in `solo_builder/discord_bot/test_bot.py` passes coincidentally.
It creates state with no Running subtasks, so `_format_stalled` returns an empty result
regardless of the STALL_THRESHOLD value read from live `config/settings.json`.
The test never actually exercises the config read path, so live-config contamination
is invisible — the test passes even when settings.json has been mutated.

## Fix
Apply the same mock pattern established in TASK-021 for `test_stalled_shows_stuck`:
patch `pathlib.Path.read_text` to return a controlled JSON string with STALL_THRESHOLD=5.

## Scope
- `solo_builder/discord_bot/test_bot.py` only
- No production code changes
