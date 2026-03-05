# HANDOFF TO DEV (from ARCHITECT)

## Objective
Create a small, meaningful `solo_builder`-scoped improvement for TASK-001 by adding a deterministic local smoke test for repository readiness and documenting how to run it, without changing product behavior.

## In-scope area
`solo_builder/`

## Allowed changes
- solo_builder/tests/test_task001_smoke.py
- solo_builder/tests/__init__.py
- solo_builder/README.md

## Disallowed changes
- No unrelated refactors
- No dependency/version bumps unless absolutely required and explicitly justified
- No edits outside Allowed changes

## Implementation plan
1. Add `solo_builder/tests/test_task001_smoke.py` with minimal `unittest` coverage that validates repository-readiness invariants only (for example: required workflow/project files exist and are readable).
2. Add `solo_builder/tests/__init__.py` (if needed) so test discovery is stable in local and CI environments.
3. Update `solo_builder/README.md` with a short “TASK-001 smoke test” section showing exact command(s) to run this test, keeping documentation concise and scoped to the new test only.

## Acceptance criteria
- `solo_builder/tests/test_task001_smoke.py` exists and is runnable with `python -m unittest`.
- `solo_builder/README.md` includes the exact command for running the new smoke test.
- `pwsh tools/audit_check.ps1` exits with code `0` after the change set is complete.
- Latest `claude/verify_last.json` shows `"passed": true` for required verification commands after DEV verification.

## Verification steps
1. Run targeted test: `python -m unittest solo_builder.tests.test_task001_smoke -v`.
2. Run full contract verification: `pwsh tools/audit_check.ps1`.
3. Confirm verification artifact indicates success: inspect `claude/verify_last.json` for `"passed": true` and no required command failures.

## Risks / notes
- Keep test assertions lightweight and deterministic; avoid network, time-dependent, or environment-specific checks.
- Do not touch existing bot/API suites in this task; this handoff is intentionally minimal to exercise the full role loop safely.
- Before committing, ensure `claude/allowed_files.txt` is derived from this handoff so dev-gate scope enforcement remains strict.
