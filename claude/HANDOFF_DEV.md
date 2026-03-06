# HANDOFF TO DEV (from ARCHITECT)

## Objective
Stop `python -m unittest discover` from mutating tracked `solo_builder/config/settings.json` by isolating config writes to test-only files.

## In-scope area
`solo_builder/api/` unittest suite and its test fixture setup for config endpoints.

## Allowed changes
- solo_builder/api/test_app.py

## Disallowed changes
- No unrelated refactors
- No dependency/version bumps
- No edits outside Allowed changes

## Implementation plan
1. In `_Base.setUp` inside `solo_builder/api/test_app.py`, create a temp `settings.json` under `self._tmp` seeded from current app settings (or minimal required keys).
2. Patch `app_module.SETTINGS_PATH` in the existing `_patches` list so `/config` GET/POST in tests reads/writes the temp settings file, not repository `solo_builder/config/settings.json`.
3. Keep existing config endpoint tests (`TestConfig`) unchanged in intent; they should validate API behavior against isolated temp settings.

## Acceptance criteria
- Running `python -m unittest discover` does not modify `solo_builder/config/settings.json`.
- `TestConfig.test_post_updates_setting` still passes by updating only the temp test settings file.
- `pwsh tools/audit_check.ps1` no longer fails due to `solo_builder/config/settings.json` mutation.

## Verification steps
1. Reset and baseline:
   - `git restore --source=HEAD --worktree --staged solo_builder/config/settings.json`
   - `git status --short --branch`
2. Run unittest command directly:
   - `python -m unittest discover`
3. Confirm no config mutation:
   - `git diff -- solo_builder/config/settings.json`
   - `git status --short --branch`
4. Run full verifier:
   - `pwsh tools/audit_check.ps1`
5. Confirm verifier result is not failing for settings mutation:
   - `Get-Content -Raw claude/verify_last.json`

## Risks / notes
- If any non-API tests also write settings, this change may reduce but not eliminate all mutations; isolate additional writers only in follow-up tasks.
- Keep test fixture deterministic; avoid reading user-local files outside repo paths.
