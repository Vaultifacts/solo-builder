# State Schema

Allowed phases:
- `triage`
- `research`
- `plan`
- `build`
- `verify`
- `done`

Allowed roles:
- `RESEARCH`
- `ARCHITECT`
- `DEV`
- `AUDITOR`

Required `STATE.json` keys:
- `task_id` (string)
- `phase` (enum)
- `next_role` (enum)
- `attempt` (integer >= 0)
- `max_attempts` (integer >= 1)
- `last_verify_pass` (boolean)
- `run_id` (string)
- `last_snapshot_path` (string)
- `updated_at` (ISO-8601 UTC)

Transitions:
- `triage` -> `research` (next_role `RESEARCH`)
- `research` -> `plan` (next_role `ARCHITECT`)
- `plan` -> `build` (next_role `DEV`)
- `build` -> `verify` (next_role `AUDITOR`)
- `verify` -> `done` when pass
- `verify` -> `verify` on fail with `attempt + 1`, `next_role = ARCHITECT`

Invalid transitions must be rejected by orchestration.