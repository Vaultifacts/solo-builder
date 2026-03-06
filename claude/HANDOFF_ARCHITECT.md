# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-004` (state set to triage/research flow).
- Investigation target: unintended mutation of `solo_builder/config/settings.json`.
- Evidence source: `claude/logs/settings_mutation_probe.txt`.

## Evidence collected
- Baseline snapshot recorded:
  - hash: `A0AD6BA6DD5216C3AF861923A13B1C09707846057545C76F1A7B1EA00DCA7592`
  - time: `2026-03-06T00:57:24.0085141Z`
- Probe command sequence executed one-by-one with reset between runs.
- Mutation identified by probe:
  - `MUTATED by: pwsh tools/audit_check.ps1`
- Before/after for mutating command:
  - BEFORE hash/time: `A0AD6BA6DD5216C3AF861923A13B1C09707846057545C76F1A7B1EA00DCA7592` / `2026-03-06T00:57:24.0085141Z`
  - AFTER hash/time: `5E4E9349A5C6F9A95D943D9E0EC5ED4890252DFB6A8E182A5CB8896440D09B52` / `2026-03-06T01:04:27.7796177Z`
- Diff excerpt summary:
  - `solo_builder/config/settings.json`
  - key changed: `"STALL_THRESHOLD"` from `99` to `10`.

## Observations
- Stable/true:
  - `pwsh tools/bootstrap_verify.ps1` does not mutate `settings.json`.
  - `pwsh tools/audit_check.ps1` consistently mutates `settings.json` in this environment.
  - Mutation is semantic (actual value change), not only formatting.
- Uncertain:
  - Exact sub-command inside `audit_check` path causing mutation (likely from optional `python -m unittest discover` execution).
  - Whether mutation is intentional test fixture behavior or unintended side effect.

## Hypotheses (ranked)
- H1: `python -m unittest discover` (invoked by `audit_check`) runs tests that write runtime defaults into `solo_builder/config/settings.json`.
  - Rationale: mutation appears during `audit_check`, and config value shift matches “test default/reset” style behavior.
- H2: A `solo_builder` initialization path during tests rewrites settings on import/boot when file values are out of expected range.
  - Rationale: only one key changed to a lower operational value (`99` -> `10`) suggests normalization logic.
- H3: Mutation originates from test cleanup/teardown routines that persist temporary test config to real config path.
  - Rationale: deterministic post-test mutation with no direct config-edit command in probe script.

## Suggested next validation steps (no implementation)
1. Re-run each `audit_check` sub-command manually in isolation (`python -m unittest discover`, `git status`, `git diff --stat`) and compare hashes after each sub-step.
2. Run unittest subsets (`solo_builder/discord_bot/test_bot.py`, `solo_builder/api/test_app.py`) independently to isolate which suite triggers the config write.
3. Capture call-path evidence by logging file writes to `solo_builder/config/settings.json` during test run (process/file-write tracing or targeted instrumentation in test mode only).
4. Confirm whether mutation is produced by application runtime code vs test helper/setup/teardown by searching for writes targeting `config/settings.json`.
