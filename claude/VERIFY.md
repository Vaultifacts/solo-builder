# Verification Contract

Source of truth: `claude/VERIFY.json`

Rules:
- Only commands in `VERIFY.json` define verification.
- `tools/audit_check.ps1` executes all commands with timeout.
- Required command failure causes overall failure.
- Optional command failure is recorded as warning.
- Always capture stdout/stderr to `claude/verify_last.json`.