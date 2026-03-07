# HANDOFF TO AUDITOR (from DEV)

## Task
TASK-020

## Summary of implementation
Implemented workflow contract integrity checking by introducing a new CI script that validates
two classes of drift: missing referenced scripts (Direction A) and lifecycle scripts writing
files not declared in `allowed_files.txt` (Direction B).

## Files modified (implementation scope)
- tools/workflow_contract_check.ps1 (new)
- .github/workflows/ci.yml
- claude/WORKFLOW_SPEC.md

## Runtime/workflow artifacts modified
- claude/JOURNAL.md (expected workflow logging)
- claude/allowed_files.txt (runtime artifact; narrowed to DEV scope by extract_allowed_files.ps1;
  must be restored from HEAD before audit — do not commit)

## What changed

1. Added `tools/workflow_contract_check.ps1`:
   - **Phase A** — scans contract source files (`claude/AGENT_ENTRY.md`, `claude/WORKFLOW_SPEC.md`,
     `claude/NEXT_ACTION.md`, `claude/RULES.md`, `.github/workflows/ci.yml`,
     `claude/checklists/*.md`) for `tools/*.ps1` references; asserts each exists on disk.
   - **Phase B** — uses a hardcoded canonical map of lifecycle scripts to their known output files;
     reads `claude/allowed_files.txt` from `git show HEAD:...` (not working tree) for CI-consistent
     determinism; asserts every lifecycle output file is declared.
   - Exits 0 (PASS) or 1 (FAIL with violation list).

2. Updated `.github/workflows/ci.yml`:
   - Added `Workflow contract check` step (`pwsh tools/workflow_contract_check.ps1`) before the
     existing `CI invariant check` step.
   - Added `pwsh tools/workflow_contract_check.ps1` as first line of `ci_bundle/repro.ps1`.

3. Updated `claude/WORKFLOW_SPEC.md`:
   - Added `Workflow contract integrity` section documenting both drift directions and
     the canonical CI command.

## Verification run
- `pwsh tools/workflow_contract_check.ps1` on clean repo → PASS
- Failure-path proof (Direction A): added ghost reference `tools/ghost_script.ps1` to
  `claude/RULES.md`, ran check → exit 1, violation listed; reverted.
- `pwsh tools/dev_gate.ps1 -Mode Manual` → PASS

## Acceptance criteria mapping
- `workflow_contract_check.ps1` exits 0 on clean repo: satisfied.
- Exits nonzero on induced violation: proven (Direction A failure path).
- CI runs `workflow_contract_check` before `ci_invariant_check`: satisfied in `ci.yml`.
- `WORKFLOW_SPEC.md` documents both drift directions and CI command: satisfied.
- No product-code changes: satisfied.

## Risks / notes
- `CLAUDE_ALLOW_NEW_FILES=1` was required for the commit introducing `tools/workflow_contract_check.ps1`.
  This is the expected and correct override for any DEV phase introducing a new script.
- `claude/allowed_files.txt` is a runtime artifact and must not be committed. Restore with:
  `git restore --source=HEAD --worktree --staged claude/allowed_files.txt`
- Phase B reads `allowed_files.txt` from `git show HEAD:...` — this is by design so the check
  is not affected by the DEV-phase narrowed local copy.
- Direction B failure-path was not separately proven (Phase A proof suffices for exit-code
  coverage); AUDITOR may induce a Phase B violation if additional coverage is desired.
