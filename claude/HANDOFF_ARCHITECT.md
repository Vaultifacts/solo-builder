# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: TASK-009
- Scope area: `_cmd_undo` output path in `solo_builder/solo_builder_cli.py`

## Evidence collected
- Probe log: `claude/logs/task009_undo_unicode_probe.txt`
- Reproduction commands:
  - `python -m unittest solo_builder.discord_bot.test_bot | findstr /i undo`
  - `python -m unittest solo_builder.discord_bot.test_bot.TestUndoCommand`
  - `python -m unittest solo_builder.discord_bot.test_bot.TestHandleTextCommandExtra`
- Exact failing unittest:
  - `solo_builder.discord_bot.test_bot.TestUndoCommand.test_undo_restores_previous_step`
- Non-failing control check:
  - `solo_builder.discord_bot.test_bot.TestHandleTextCommandExtra` passes
- Error signature:
  - `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 20: character maps to <undefined>`
- Production source location:
  - `solo_builder/solo_builder_cli.py:1615` in `_cmd_undo`
  - failing line prints `Undo: step {prev_step} → {self.step}`

## Observations
- Stable:
  - The failure is deterministic in the class-targeted run.
  - The immediate trigger is console print of Unicode arrow (`\u2192`) under cp1252.
  - The failure is isolated to `_cmd_undo` output path, not the undo logic assertions themselves.
- Uncertain:
  - Whether additional non-targeted CLI print paths still contain cp1252-unsafe glyphs.
  - Whether environment-default encoding differs across shells/CI.

## Hypotheses (ranked)
- H1: `_cmd_undo` uses direct Unicode arrow in a `print(...)` string, which fails in cp1252 terminals.
- H2: Additional status/help output strings may still contain similar glyphs and could fail in other tests.
- H3: No centralized output sanitization is applied before console writes, so each string path is independently vulnerable.

## Constraints / Non-negotiables
- Keep scope minimal and task-focused.
- Prefer smallest production output-path fix in `solo_builder/solo_builder_cli.py`.
- No behavior changes beyond encoding-safe output.
- Avoid broad refactors.

## Unknowns / Missing evidence
- Whether replacing only `_cmd_undo` arrow fully addresses TASK-009 acceptance criteria in all required runs.
- Whether other failures in full unittest-discover are unrelated and should remain out-of-scope.
