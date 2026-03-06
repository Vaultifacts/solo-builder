# HANDOFF TO DEV (from ARCHITECT)

## Objective
Fix Windows `UnicodeEncodeError` in CLI add-task/add-branch success output by making those output strings encoding-safe without changing command behavior.

## In-scope area
`solo_builder/solo_builder_cli.py` output formatting in:
- `_cmd_add_task`
- `_cmd_add_branch`

## Allowed changes
- solo_builder/solo_builder_cli.py

## Disallowed changes
- No unrelated refactors
- No dependency/version bumps
- No edits outside Allowed changes

## Implementation plan
1. In `solo_builder/solo_builder_cli.py`, update the two success print paths in `_cmd_add_task` and `_cmd_add_branch` that currently emit `\u2192`.
2. Replace the unsafe glyph usage with an encoding-safe equivalent (`->`) in those two output lines only, preserving message structure, colors, and content ordering.
3. Keep all command logic and test intent unchanged; adjust only output text to prevent cp1252/charmap print failures.

## Acceptance criteria
- `python -m unittest solo_builder.discord_bot.test_bot.TestAddTaskInlineSpec` passes without `UnicodeEncodeError`.
- `python -m unittest solo_builder.discord_bot.test_bot.TestAddBranchInlineSpec` passes without `UnicodeEncodeError`.
- `pwsh tools/audit_check.ps1` passes.
- `solo_builder/config/settings.json` is not modified after verification.

## Verification steps
1. Run targeted failing suites:
   - `python -m unittest solo_builder.discord_bot.test_bot.TestAddTaskInlineSpec`
   - `python -m unittest solo_builder.discord_bot.test_bot.TestAddBranchInlineSpec`
2. Run full verifier:
   - `pwsh tools/audit_check.ps1`
3. Confirm working tree cleanliness for config file:
   - `git diff -- solo_builder/config/settings.json`
   - `git status --short --branch`

## Risks / notes
- This is a display-only compatibility fix for Windows cp1252 terminals; it should not alter task/branch creation behavior.
- Other Unicode output paths may still exist elsewhere; this task intentionally limits scope to the two proven failure sites.
