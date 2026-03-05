# Control Boundaries

- `RESEARCH`: gather evidence, summarize failures, propose hypotheses; no production code edits.
- `ARCHITECT`: choose implementation approach, constraints, and acceptance criteria.
- `DEV`: implement only files allowed by handoff and `claude/allowed_files.txt`.
- `AUDITOR`: execute verification contract and report pass/fail with evidence.

Cross-role rules:
- Do not skip roles by default.
- All role outputs go in `/claude/*` files.
- State transitions must match `claude/STATE_SCHEMA.md`.