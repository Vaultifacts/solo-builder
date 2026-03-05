# Repo Workflow Contract

This repository uses `/claude/*` as the single source of truth for autonomous, multi-role delivery.

Start here:
1. `pwsh tools/bootstrap_verify.ps1`
2. `pwsh tools/install_git_hooks.ps1`
3. `pwsh tools/audit_check.ps1`
4. `pwsh tools/claude_orchestrate.ps1`

Primary references:
- `claude/AGENT_ENTRY.md`
- `claude/STATE.json`
- `claude/VERIFY.json`
- `claude/RULES.md`