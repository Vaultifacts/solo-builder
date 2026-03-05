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
