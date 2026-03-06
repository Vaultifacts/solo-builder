# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-006`
- Goal: isolate the remaining unittest writer path outside `solo_builder/api/test_app.py` that mutates `solo_builder/config/settings.json`.
- Evidence source: `claude/logs/task006_testmodule_probe.txt`

## Evidence collected
- Exact mutating unittest module from probe:
  - `MUTATED by: python -m unittest solo_builder.discord_bot.test_bot`
- Minimal reproduction sequence:
  1. `git restore --source=HEAD --worktree --staged solo_builder/config/settings.json`
  2. `python -m unittest solo_builder.discord_bot.test_bot`
  3. `git diff -- solo_builder/config/settings.json`
- Before/after evidence:
  - BEFORE hash/time: `A0AD6BA6DD5216C3AF861923A13B1C09707846057545C76F1A7B1EA00DCA7592` / `2026-03-06T02:26:56.6285348Z`
  - AFTER hash/time: `5E4E9349A5C6F9A95D943D9E0EC5ED4890252DFB6A8E182A5CB8896440D09B52` / `2026-03-06T02:36:59.7590779Z`
- Diff summary:
  - File: `solo_builder/config/settings.json`
  - Change: `"STALL_THRESHOLD"` from `99` to `10`

## Observations
- Stable/true:
  - Mutation occurs when running `solo_builder.discord_bot.test_bot` directly.
  - The API test module is not needed to trigger this mutation.
  - Output shows test paths calling CLI set/config behavior (`_cmd_set`) and multiple failing tests in `discord_bot/test_bot.py`.
- Uncertain:
  - Exact class/method in `discord_bot/test_bot.py` responsible for persisting `STALL_THRESHOLD=10`.
  - Whether mutation is from a direct `_cmd_set("STALL_THRESHOLD=10")` path, shared setup/teardown side effect, or another helper call.

## Hypotheses (ranked)
- H1: `TestSetCommand.test_set_stall_threshold_updates_module_and_agents` (or nearby tests) calls `_cmd_set("STALL_THRESHOLD=10")` without isolating `_CFG_PATH`, writing to tracked settings.
- H2: Another class in `discord_bot/test_bot.py` indirectly calls `_cmd_set`/persist path and writes the same key during async command handling tests.
- H3: A shared fixture or CLI initialization path writes normalized settings when run under these unittest scenarios.

## Recommended next narrowing step
1. Class-level isolation in `solo_builder.discord_bot.test_bot`:
   - Run specific classes (starting with `TestSetCommand`) and re-check settings hash after each.
2. Method-level isolation:
   - Within first mutating class, run individual test methods until exact mutator is identified.
3. Direct search pivot:
   - Trace config write helpers and `_cmd_set` call sites in `discord_bot/test_bot.py` to map tests that patch `_CFG_PATH` vs tests that do not.

## Non-implementation recommendation
- Keep this phase at evidence narrowing only; implementation planning should start only after exact class/method is identified.
