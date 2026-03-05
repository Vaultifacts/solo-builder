# Rules

Scope discipline:
- Use smallest safe change set.
- Keep changes within declared allowed files for Dev work.
- Update handoff documents when ownership changes.

Evidence discipline:
- Every verification run must produce `claude/verify_last.json`.
- Failure runs should create a snapshot via `tools/claude_snapshot.ps1`.
- Triage should use `claude/logs/latest.txt`, artifacts, and parsed summaries.

Stateless mode:
- Assume agent memory is ephemeral.
- Repo files are the only trusted state.
- Do not rely on hidden context.