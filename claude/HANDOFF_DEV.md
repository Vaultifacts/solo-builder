# HANDOFF TO DEV (from ARCHITECT)

## Objective
Fix the `dev_gate` blocker by repairing the parsing/runtime error in `tools/secret_scan.ps1` while preserving existing secret-scan behavior.

## In-scope area
`tools/`

## Allowed changes
- tools/secret_scan.ps1

## Disallowed changes
- No unrelated refactors
- No dependency/version bumps unless absolutely required and explicitly justified
- No edits outside Allowed changes

## Implementation plan
1. Inspect `tools/secret_scan.ps1` and identify the exact malformed expression causing the `-join` syntax/runtime failure.
2. Replace the failing expression with a PowerShell 5.1-safe string-join approach that preserves current scan output semantics.
3. Keep all pattern checks and exit-code behavior unchanged except for eliminating the parser/runtime failure.

## Acceptance criteria
- `pwsh tools/secret_scan.ps1` runs without syntax/parsing error.
- `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail` proceeds past `secret_scan.ps1` on a clean staging set.
- The script still fails with clear messaging when potential secrets are detected.

## Verification steps
1. Run: `pwsh tools/secret_scan.ps1`.
2. Run: `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail`.
3. Capture command output in `claude/HANDOFF_AUDIT.md` for auditor traceability.

## Risks / notes
- Keep the fix minimal to avoid changing policy behavior.
- This task is a guardrail reliability fix and should complete before resuming TASK-001 implementation flow.
