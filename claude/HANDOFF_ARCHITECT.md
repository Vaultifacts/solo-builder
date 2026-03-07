# HANDOFF TO ARCHITECT (from RESEARCH)

## Task
TASK-025

## Finding
claude_heal.ps1 mutates STATE.json and downloads CI artifacts on every
run. There is no way to preview what it would do without side effects.
Adding a -DryRun switch allows safe diagnostic use: the operator sees
what would be triaged (run ID, workflow name, branch) without STATE.json
being changed or any gh download/log calls being made.

## Scope
- tools/claude_heal.ps1 only
- No other files modified
