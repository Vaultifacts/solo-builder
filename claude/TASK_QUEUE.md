# Task Queue

## TASK-001
Goal: Create the first real end-to-end workflow task for this repo that is small but meaningful.

Constraints:
- Must exercise Research -> Architect -> Dev -> Auditor loop.
- Must touch only a few files.
- Must have clear acceptance criteria that can be validated by audit_check.

Acceptance Criteria:
- `claude/HANDOFF_ARCHITECT.md` contains a research handoff for `TASK-001` with at least one evidence-backed hypothesis and one explicit unknown.
- `claude/HANDOFF_DEV.md` contains an implementation plan for `TASK-001` with an `Allowed changes` section listing exact file paths.
- `claude/allowed_files.txt` can be generated from `HANDOFF_DEV.md` by running `pwsh tools/extract_allowed_files.ps1` without error.
- `pwsh tools/audit_check.ps1` exits with code 0 after task handoff files are prepared.

Priority: High

## TASK-002
Goal: Repair the `dev_gate` blocker caused by a syntax/runtime error in `tools/secret_scan.ps1`.

Constraints:
- Scope limited to guardrail reliability.
- Fix must remain PowerShell 5.1 compatible.
- No behavior expansion beyond correcting the broken guard execution path.

Acceptance Criteria:
- `pwsh tools/secret_scan.ps1` runs without syntax/parsing errors.
- `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail` proceeds past `secret_scan.ps1` on a clean staging set.
- No files outside TASK-002 allowed scope are modified for the fix.

Priority: Urgent
