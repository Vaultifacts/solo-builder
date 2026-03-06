# HANDOFF TO DEV (from ARCHITECT)

## Allowed changes
- tools/audit_check.ps1

## Implementation plan
1. Add a working-tree cleanliness guard to `tools/audit_check.ps1`:
   - capture `git status --porcelain` before running verification commands
   - capture `git status --porcelain` after running verification commands
2. Detect tracked-file mutations by parsing status lines that are not untracked (`??`).
3. When tracked mutations are detected:
   - set `working_tree_dirty=true` and include `dirty_files` in `claude/verify_last.json`
   - best-effort restore those files with `git restore --source=HEAD --worktree --staged <files>`
   - re-check status after restore and persist post-restore dirty files if any
   - force overall verification failure with clear message: `Working tree mutated during verification`
4. Keep existing command execution and timeout behavior unchanged otherwise.
5. Ensure this logic works on PowerShell 5.1.

## Acceptance criteria
- On a clean tree, running `pwsh tools/audit_check.ps1` leaves no modified tracked files.
- If any verification command mutates tracked files, `audit_check` fails and reports mutated files in `claude/verify_last.json`.
- `claude/verify_last.json` contains:
  - `working_tree_dirty` (boolean)
  - `dirty_files` (array of tracked file paths)
- Best-effort restore attempt is executed and reflected in output metadata.

## Verification steps
1. Start from clean baseline for target file:
   - `git restore --source=HEAD --worktree --staged solo_builder/config/settings.json`
2. Run:
   - `pwsh tools/audit_check.ps1`
3. Validate:
   - If mutation occurs, command exits non-zero with message containing `Working tree mutated during verification`.
   - `claude/verify_last.json` includes `working_tree_dirty=true` and `dirty_files` contains `solo_builder/config/settings.json`.
   - `git status --short --branch` is clean or shows only non-tracked runtime files after restore attempt.

## Risks / notes
- Keep scope strictly in `tools/audit_check.ps1`; avoid changes to VERIFY contract generation or task flow.
- `git restore` is best-effort; if restore fails due external locks/permissions, verify metadata must still clearly report remaining dirty files.
- Do not include unrelated cleanup/refactors in this task.
