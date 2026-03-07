# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-022`
- Goal: Integrate `workflow_contract_check.ps1` into `workflow_preflight.ps1` so workflow
  contract drift is caught before task initialization, not just in CI.
- Scope: `tools/workflow_preflight.ps1` only. `workflow_contract_check.ps1` is unchanged.

## 1) Current preflight check sequence

`tools/workflow_preflight.ps1` runs five checks in order:
1. Assert `check_next_action_consistency.ps1` exists.
2. Resolve current branch (fail on detached HEAD).
3. Assert runtime artifacts clean (`allowed_files.txt`, `verify_last.json`).
4. Assert working tree clean.
5. Run `check_next_action_consistency.ps1`.
6. Run baseline ancestry check (master contains prior task branch).
7. Print `workflow_preflight: PASS` and exit 0.

## 2) workflow_contract_check.ps1 behavior relevant to placement

Phase B of `workflow_contract_check.ps1` reads `allowed_files.txt` via
`git show HEAD:claude/allowed_files.txt` — it reads from committed HEAD, not working tree.

This has one important implication:
- The contract check is only meaningful after the working tree is clean (i.e., after step 4
  above). If the tree were dirty, HEAD might not reflect current `allowed_files.txt` state.
- But by step 4, the clean-tree assertion has already passed — HEAD IS authoritative.

Therefore the correct insertion point is **after the clean-tree check (step 4), before
`check_next_action_consistency.ps1` (step 5)**.

Rationale: structural integrity failures (missing scripts, undeclared outputs) should be caught
before semantic consistency failures. The contract check is a static integrity check; the
consistency check is a semantic state check.

## 3) Integration points

Two additions to `workflow_preflight.ps1`:

**Addition 1** — declare `$contractCheck` path alongside `$consistencyCheck` at top of script:
```powershell
$contractCheck = Join-Path $PSScriptRoot 'workflow_contract_check.ps1'
```

**Addition 2** — call it after the clean-tree check, before the consistency check:
```powershell
if (!(Test-Path $contractCheck)) {
  Fail "Missing required helper: $contractCheck"
}
& $contractCheck
if ($LASTEXITCODE -ne 0) {
  Fail 'Workflow contract integrity check failed. Run pwsh tools/workflow_contract_check.ps1 for details.'
}
```

## 4) Scope
- Modify only `tools/workflow_preflight.ps1`.
- Do not modify `tools/workflow_contract_check.ps1`.
- No other files in scope.
- `claude/WORKFLOW_SPEC.md` does not need updating (the spec already documents
  `workflow_contract_check.ps1` as the canonical check command; preflight integration
  is an execution detail, not a new contract).

## 5) Verification
- `pwsh tools/workflow_preflight.ps1` on clean repo → PASS (contract check passes,
  all subsequent checks pass).
- Failure-path proof: temporarily reference a missing script in a contract source file,
  run `pwsh tools/workflow_preflight.ps1`, confirm it fails before the consistency check
  with a contract-integrity error; revert.
- `pwsh tools/start_task.ps1 -DryRun -TaskId TASK-999 -Goal test` → succeeds through
  preflight (dry-run mode exercises the preflight call).
- Full test suite: `python -m unittest discover` → 195 tests, 0 failures.
