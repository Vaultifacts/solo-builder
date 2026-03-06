# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-005`.
- Goal: isolate which verification sub-command mutates `solo_builder/config/settings.json`.
- Evidence source: `claude/logs/task005_subcommand_probe.txt`.

## Evidence collected
- Exact mutating sub-command from `claude/VERIFY.json` isolation run:
  - `MUTATED by sub-command: unittest-discover`
  - Command executed: `python -m unittest discover`
- Minimal reproduction sequence:
  1. `git restore --source=HEAD --worktree --staged solo_builder/config/settings.json`
  2. Run `cmd.exe /d /s /c "python -m unittest discover"`
  3. Inspect hash/diff for `solo_builder/config/settings.json`
- Before/after evidence:
  - BEFORE hash/time: `A0AD6BA6DD5216C3AF861923A13B1C09707846057545C76F1A7B1EA00DCA7592` / `2026-03-06T01:59:36.2841812Z`
  - AFTER hash/time: `5E4E9349A5C6F9A95D943D9E0EC5ED4890252DFB6A8E182A5CB8896440D09B52` / `2026-03-06T02:08:34.3091973Z`
- Diff summary:
  - File: `solo_builder/config/settings.json`
  - Changed field: `"STALL_THRESHOLD"` from `99` to `10`

## Observations
- Stable/true:
  - Mutation occurs during `python -m unittest discover`, before other verify sub-commands.
  - Mutation is semantic (config value rewrite), not a formatting-only update.
  - Existing `audit_check` containment catches and restores the mutation, but still fails by design.
- Uncertain:
  - Exact test case/module writing the settings file.
  - Whether write is intentional test fixture behavior or unintended runtime side effect.

## Hypotheses (ranked)
- H1: One or more unittest cases in discovered suites explicitly persist settings to `solo_builder/config/settings.json`.
  - Rationale: direct mutation occurs under unittest discovery execution.
- H2: Application bootstrap path under tests normalizes `STALL_THRESHOLD` and writes normalized settings back to disk.
  - Rationale: deterministic rewrite from `99` to `10` is characteristic of config normalization.
- H3: Test cleanup/teardown writes current runtime state back to config file path instead of temp fixture path.
  - Rationale: mutation persists after test failures and appears tied to testing side-effects.

## Recommended fix path to evaluate next
1. **Primary**: `mock/isolate config in tests` (path 3)
   - Reason: mutation originates in test execution; isolating test config path is lowest-risk to production runtime behavior.
2. **Secondary**: `redirect writes to temp/state file` (path 2)
   - Reason: acceptable fallback if tests require writable config-like state.
3. **Tertiary**: `stop command from writing config` (path 1)
   - Reason: viable only if write path is accidental and safe to disable globally in tested code paths.
