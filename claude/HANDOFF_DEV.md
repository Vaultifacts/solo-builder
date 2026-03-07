# HANDOFF TO DEV (from ARCHITECT)

## Task
TASK-023

## Change
In `solo_builder/discord_bot/test_bot.py`, find `test_stalled_empty` in `TestStalledCommand`
and add a `patch("pathlib.Path.read_text", return_value=mock_cfg)` context manager,
matching the pattern used in `test_stalled_shows_stuck`.

## Allowed changes
- solo_builder/discord_bot/test_bot.py

## Acceptance criteria
- `python -m unittest discover` → 195 tests, 0 failures
- `test_stalled_empty` explicitly mocks config rather than passing coincidentally
