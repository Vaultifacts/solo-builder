# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
`test_stalled_shows_stuck` fails because `_format_stalled` reads `STALL_THRESHOLD` directly
from the live `config/settings.json` on disk. The live file has `STALL_THRESHOLD: 99` from a
prior interactive session. The test creates state with `step=10`, `last_update=0` (age=10),
expecting the default threshold of 5 to apply. Since 10 < 99, the subtask is not flagged as
stalled and the assertion fails.

## Root cause
Missing test isolation: the config file read inside `_format_stalled` is not mocked.
The production behavior (reading threshold from config) is correct. No production code change
is needed or permitted.

## Fix strategy
**Candidate A only.** Add a `patch` for `pathlib.Path.read_text` inside the
`test_stalled_shows_stuck` test context, returning a controlled config JSON with
`STALL_THRESHOLD: 5`. With threshold=5 and age=10, A1 is correctly identified as stalled.

The patch must be scoped to `test_stalled_shows_stuck` only. `test_stalled_empty` (step=1,
age=1 < 5) does not need this mock and must not be modified.

## Exact change

In `solo_builder/discord_bot/test_bot.py`, add one patch to `test_stalled_shows_stuck`:

```diff
     async def test_stalled_shows_stuck(self):
         """'stalled' with a Running subtask past threshold shows it."""
         state = _make_state({"A1": "Running", "A2": "Verified"}, step=10)
+        mock_cfg = json.dumps({"STALL_THRESHOLD": 5})
         with patch.object(bot_module, "_send", new=AsyncMock()) as mock_send, \
-             patch.object(bot_module, "_load_state", return_value=state):
+             patch.object(bot_module, "_load_state", return_value=state), \
+             patch("pathlib.Path.read_text", return_value=mock_cfg):
             await bot_module._handle_text_command(_make_msg("stalled"))
         text = mock_send.call_args[0][1]
         self.assertIn("A1", text)
         self.assertIn("Stalled", text)
```

`json` is already imported at the top of `test_bot.py` — no new imports needed.

## Allowed changes
- solo_builder/discord_bot/test_bot.py

## Files that must not be modified
- solo_builder/discord_bot/bot.py
- solo_builder/solo_builder_cli.py
- Any file outside `solo_builder/discord_bot/test_bot.py`

## Acceptance criteria
- `python -m unittest solo_builder.discord_bot.test_bot.TestStalledCommand` — 2 tests, 0 failures.
- `python -m unittest discover` — 0 failures (all other tests continue to pass).
- `test_stalled_empty` is unmodified and continues to pass.
- No production code files are changed.

## Verification commands
1. Targeted class run:
   `python -m unittest solo_builder.discord_bot.test_bot.TestStalledCommand`
2. Full suite:
   `python -m unittest discover`
3. Diff check:
   `git diff --stat` — must show only `solo_builder/discord_bot/test_bot.py`
