# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: TASK-008
- Scope area: `solo_builder/discord_bot` tests and the related CLI output path in `solo_builder/solo_builder_cli.py`

## Evidence collected
- Probe log: `claude/logs/task008_unicode_probe.txt`
- Reproduction commands:
  - `python -m unittest solo_builder.discord_bot.test_bot.TestAddTaskInlineSpec`
  - `python -m unittest solo_builder.discord_bot.test_bot.TestAddBranchInlineSpec`
- Failing tests (7 total):
  - `TestAddTaskInlineSpec.test_handle_command_add_task_bare_still_prompts`
  - `TestAddTaskInlineSpec.test_handle_command_add_task_with_inline_spec`
  - `TestAddTaskInlineSpec.test_inline_spec_skips_input_prompt`
  - `TestAddTaskInlineSpec.test_inline_spec_used_as_subtask_description`
  - `TestAddBranchInlineSpec.test_handle_command_add_branch_bare_still_prompts`
  - `TestAddBranchInlineSpec.test_handle_command_add_branch_with_inline_spec`
  - `TestAddBranchInlineSpec.test_inline_spec_skips_input_prompt`
- Error signature:
  - `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`
- Stack locations:
  - `solo_builder/solo_builder_cli.py:2183` in `_cmd_add_task`
  - `solo_builder/solo_builder_cli.py:2291` in `_cmd_add_branch`
  - Python encoder path: `encodings/cp1252.py`

## Observations
- Stable:
  - Failures are deterministic under current local environment.
  - Both failing groups share the same Unicode arrow character (`\u2192`) in console output.
  - Failures occur while printing success/status lines, not in core task/branch data mutation assertions.
- Uncertain:
  - Whether all terminals/environments in CI reproduce cp1252 behavior the same way.
  - Whether additional tests hit similar output paths beyond these two classes.

## Hypotheses (ranked)
- H1: The direct `print(...)` lines in `_cmd_add_task` and `_cmd_add_branch` emit non-cp1252 characters (`→`) and crash in Windows cp1252 console contexts.
- H2: A shared output formatting path is missing an encoding-safe fallback/sanitization for non-UTF-8 consoles.
- H3: Test harness output capture is not forcing UTF-8 and exposes latent console-encoding assumptions in CLI output formatting.

## Constraints / Non-negotiables
- Keep task scope narrow.
- Avoid broad refactors.
- Preserve existing command behavior and assertions.
- Verification remains through `pwsh tools/audit_check.ps1` and task-scoped test reproduction.

## Unknowns / Missing evidence
- Whether additional CLI commands also print `\u2192` and would fail under cp1252.
- Whether a single output helper exists that can resolve all affected print paths with minimal surface change.
- Whether CI/default shells enforce UTF-8 (which may hide this locally reproducible issue).
