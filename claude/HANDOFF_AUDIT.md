# HANDOFF TO AUDITOR (from DEV)

## What changed
- `tools/audit_check.ps1` (hardened to detect and handle tracked working-tree mutations during verification runs)

## How to reproduce
1. Regenerate allowed-files list from Architect handoff:
   - `pwsh tools/extract_allowed_files.ps1`
   - Result: `claude/allowed_files.txt` contained only `tools/audit_check.ps1`.
2. Run dev gate:
   - `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail`
   - Result: passed; precommit gate skipped fast subset safely.
3. Run verification contract:
   - `pwsh tools/audit_check.ps1`
   - Result: failed with explicit mutation message:
     - `Working tree mutated during verification: solo_builder/config/settings.json`
   - `claude/verify_last.json` now includes:
     - `working_tree_dirty=true`
     - `dirty_files=["solo_builder/config/settings.json"]`
     - `dirty_files_remaining=[]`

## Known risks
- `audit_check` mutates `claude/verify_last.json` and appends `claude/JOURNAL.md` by design, so those runtime/workflow-local changes remain expected after runs.
- `solo_builder/config/settings.json` did not remain dirty after the run (best-effort restore succeeded), but mutation source in test/runtime path still exists and is now surfaced as an audit failure condition.
