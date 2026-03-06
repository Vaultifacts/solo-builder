# HANDOFF TO DEV (from ARCHITECT)

## Objective
Eliminate the remaining unittest writer path in `solo_builder.discord_bot.test_bot` that mutates `solo_builder/config/settings.json` (`STALL_THRESHOLD: 99 -> 10`) by isolating settings writes to test-local temp files.

## In-scope area
`solo_builder/discord_bot/test_bot.py`, focused on tests that call `SoloBuilderCLI._cmd_set(...)` and may persist settings through `_CFG_PATH`.

## Allowed changes
- solo_builder/discord_bot/test_bot.py

## Disallowed changes
- No unrelated refactors
- No dependency/version bumps
- No edits outside Allowed changes

## Implementation plan
1. In `TestSetCommand` fixture setup, create a temp JSON settings file and patch `_cli_module._CFG_PATH` for the full fixture lifecycle (`setUp`/`tearDown`) so `_cmd_set` writes never touch repository config.
2. Keep existing persistence-specific tests valid by writing/reading through fixture temp settings path (or retaining method-local overrides where already present), while preserving original assertions and test intent.
3. Ensure no other affected tests in `solo_builder.discord_bot.test_bot` invoke `_cmd_set` against real `_CFG_PATH`; isolate only the minimal fixture/tests required by evidence.

## Acceptance criteria
- Running `python -m unittest solo_builder.discord_bot.test_bot` does not modify `solo_builder/config/settings.json`.
- Tests around `_cmd_set` in `TestSetCommand` continue to pass intent checks while using isolated temp settings storage.
- `pwsh tools/audit_check.ps1` no longer reports `solo_builder/config/settings.json` as a dirty file mutation source from `unittest-discover`.

## Verification steps
1. Reset and baseline:
   - `git restore --source=HEAD --worktree --staged solo_builder/config/settings.json`
2. Run targeted mutating module:
   - `python -m unittest solo_builder.discord_bot.test_bot`
3. Confirm no config mutation after targeted run:
   - `git diff -- solo_builder/config/settings.json`
   - `git status --short --branch`
4. Run full verifier:
   - `pwsh tools/audit_check.ps1`
5. Confirm verifier no longer attributes mutation to settings file:
   - `Get-Content -Raw claude/verify_last.json`

## Risks / notes
- There may be additional writer paths in `solo_builder.discord_bot.test_bot` outside `TestSetCommand`; if mutation persists, isolate by class/method in a follow-up task.
- Keep scope strictly test-only; do not modify production modules for this task.
