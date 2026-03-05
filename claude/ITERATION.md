# Iteration Governor

- Maximum attempts per task: read `STATE.json:max_attempts`.
- If `attempt >= max_attempts`, stop and write escalation notes to `claude/NEEDS_HUMAN.md`.
- Each failed verify increments `attempt`.
- Successful verify resets workflow to `phase=done`.