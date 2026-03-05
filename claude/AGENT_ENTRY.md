# Agent Entry (Tool-Agnostic)

Read these files in order:
1. `claude/WHO_HAS_CONTROL.md`
2. `claude/CONTROL.md`
3. `claude/RULES.md`
4. `claude/STATE.json`
5. `claude/VERIFY.json`
6. Role handoff file for your role.

Execution model:
- Roles: `RESEARCH`, `ARCHITECT`, `DEV`, `AUDITOR`.
- All outputs must be written to `/claude/*`.
- Verification is contract-driven by `claude/VERIFY.json`.
- Run verification with `pwsh tools/audit_check.ps1`.
- Dev safety runs through `pwsh tools/dev_gate.ps1` and git pre-commit hook.

If unclear, update `claude/ASSUMPTIONS.md` and continue with the safest minimal change.