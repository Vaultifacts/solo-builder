# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-007`
- Goal: isolate and eliminate the remaining config-writer path in `solo_builder.discord_bot.test_bot` at method level.
- Evidence source: `claude/logs/task007_method_probe.txt`

## Evidence collected
- Exact mutating unittest method from probe:
  - `MUTATED by: python -m unittest solo_builder.discord_bot.test_bot.TestHandleTextCommandExtra.test_set_trigger_consumed_by_cli`
- Minimal reproduction sequence:
  1. `git restore --source=HEAD --worktree --staged solo_builder/config/settings.json`
  2. `python -m unittest solo_builder.discord_bot.test_bot.TestHandleTextCommandExtra.test_set_trigger_consumed_by_cli`
  3. `git diff -- solo_builder/config/settings.json`
- Before/after evidence:
  - BEFORE hash/time: `A0AD6BA6DD5216C3AF861923A13B1C09707846057545C76F1A7B1EA00DCA7592` / `2026-03-06T02:49:30.2850728Z`
  - AFTER hash/time: `07DCC74AE6944753197244580502E4858E90CB27CB8A70264B269417758B7B78` / `2026-03-06T02:56:23.6678506Z`
- Diff behavior:
  - File is marked dirty in `git status` after method run.
  - No textual diff hunk is emitted by `git diff` (line-ending-only style mutation signal).

## Observations
- Stable/true:
  - Mutation occurs with one isolated method; broad module run is not required.
  - Method directly calls `cli._cmd_set("REVIEW_MODE=on")`, then `cli._cmd_set("REVIEW_MODE=off")`.
  - The method currently does not patch `_cli_module._CFG_PATH` before calling `_cmd_set`.
- Uncertain:
  - Whether mutation is only from this method or shared by nearby methods in `TestHandleTextCommandExtra`.
  - Whether line-ending-only dirty state is due read/write encoding normalization or broader serialization behavior.

## Hypotheses (ranked)
- H1: `TestHandleTextCommandExtra.test_set_trigger_consumed_by_cli` writes through `_cmd_set` to real `_CFG_PATH` because it instantiates `SoloBuilderCLI()` and calls `_cmd_set` without temp-path patching.
- H2: Additional methods in `TestHandleTextCommandExtra` may share this pattern and contribute to remaining mutation signals in full-module runs.
- H3: `_cmd_set` persistence path rewrites JSON formatting/line endings even when key/value changes are nominal.

## Recommended next narrowing step
1. Patch only the mutating method path (`TestHandleTextCommandExtra.test_set_trigger_consumed_by_cli`) or smallest method-local fixture used by it to isolate `_CFG_PATH`.
2. Re-run the same method-level command and verify no dirty `config/settings.json` state is produced.
3. Re-run module-level and audit checks to confirm mutation is eliminated end-to-end.

## Non-implementation recommendation
- Keep scope to `solo_builder/discord_bot/test_bot.py` only; no production-code changes.
