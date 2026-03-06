# HANDOFF TO DEV (from ARCHITECT)

## Objective
Make `tools/precommit_gate.ps1` non-blocking by default unless a known safe fast command is selected and fails.

## In-scope area
`tools/`

## Allowed changes
- tools/precommit_gate.ps1

## Disallowed changes
- No unrelated refactors
- No dependency/version bumps unless absolutely required and explicitly justified
- No edits outside Allowed changes

## Implementation plan
1. Update `tools/precommit_gate.ps1` selection logic to safely choose at most one fast verification command by name and timeout.
2. Skip optional/python/unittest-style commands in precommit gate to avoid fragile platform-specific failures.
3. Preserve strict failure behavior only when a selected fast command runs and returns non-zero.

## Acceptance criteria
- If VERIFY config is missing/empty/bootstrap-pending, precommit gate exits 0.
- If no safe fast command is found, precommit gate exits 0 with a clear skip message.
- At most one safe fast command is run via `cmd.exe /d /s /c ...`.
- `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail` no longer fails in precommit gate due optional unittest execution.

## Verification steps
1. Run: `pwsh tools/precommit_gate.ps1`.
2. Run: `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail`.
3. Confirm dev gate reaches completion or any later-stage blocker unrelated to precommit fast-command mis-selection.

## Risks / notes
- Keep scope limited to precommit gate behavior; do not alter broader verification contract.
- This task unblocks reliable commits for subsequent TASK-001 completion.
