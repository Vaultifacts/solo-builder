# HANDOFF TO DEV (from ARCHITECT)

## Objective
Fix the remaining Windows console `UnicodeEncodeError` in the `_cmd_undo` output path by making that output encoding-safe without changing undo behavior.

## In-scope area
`solo_builder/solo_builder_cli.py` `_cmd_undo` print output line.

## Allowed changes
- solo_builder/solo_builder_cli.py

## Disallowed changes
- No unrelated refactors
- No dependency/version bumps
- No edits outside Allowed changes

## Implementation plan
1. Locate the `_cmd_undo` status print that includes the Unicode arrow (`\u2192`).
2. Replace only the problematic glyph in that output path with an encoding-safe ASCII equivalent (`->`) while preserving message content.
3. Keep undo logic and state behavior unchanged.

## Acceptance criteria
- `python -m unittest solo_builder.discord_bot.test_bot.TestUndoCommand` no longer fails with `UnicodeEncodeError`.
- `pwsh tools/audit_check.ps1` passes.
- `solo_builder/config/settings.json` remains unchanged after verification.

## Verification steps
1. `python -m unittest solo_builder.discord_bot.test_bot.TestUndoCommand`
2. `pwsh tools/audit_check.ps1`
3. `git diff -- solo_builder/config/settings.json` and `git status --short --branch`

## Risks / notes
- This is a narrow output-compatibility fix only for `_cmd_undo`.
- Other pre-existing non-Unicode test failures (e.g., stalled threshold assertions) are out of scope for TASK-009.
