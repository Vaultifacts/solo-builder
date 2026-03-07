# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
`workflow_contract_check.ps1` runs in CI (TASK-020) but not during local preflight before
task initialization. Contract drift — missing referenced scripts or undeclared lifecycle
file writes — is therefore only caught at merge time, not before work begins.

## Fix strategy
Add two blocks to `tools/workflow_preflight.ps1`:
1. Declare `$contractCheck` path at the top of the script alongside `$consistencyCheck`.
2. Call `$contractCheck` after the clean-tree assertion (step 4) and before the
   `check_next_action_consistency.ps1` call (step 5).

Insertion point rationale: `workflow_contract_check.ps1` Phase B reads `allowed_files.txt`
from `git show HEAD:...`. The clean-tree assertion must have already passed for HEAD to be
authoritative. Structural integrity (contract check) is verified before semantic consistency.

## Exact change to `tools/workflow_preflight.ps1`

**At the top of the script, alongside `$consistencyCheck`** (after line 7):
```diff
 $consistencyCheck = Join-Path $PSScriptRoot 'check_next_action_consistency.ps1'
+$contractCheck    = Join-Path $PSScriptRoot 'workflow_contract_check.ps1'
```

**After the clean-tree check block and before the `& $consistencyCheck` call**
(between current lines 56–59):
```diff
+if (!(Test-Path $contractCheck)) {
+  Fail "Missing required helper: $contractCheck"
+}
+& $contractCheck
+if ($LASTEXITCODE -ne 0) {
+  Fail 'Workflow contract integrity check failed. Run pwsh tools/workflow_contract_check.ps1 for details.'
+}
+
 & $consistencyCheck
```

No other changes. `workflow_contract_check.ps1` and `WORKFLOW_SPEC.md` are not modified.

## Allowed changes
- tools/workflow_preflight.ps1

## Files that must not be modified
- tools/workflow_contract_check.ps1
- tools/check_next_action_consistency.ps1
- claude/WORKFLOW_SPEC.md
- Any file outside `tools/workflow_preflight.ps1`

## Acceptance criteria
- `pwsh tools/workflow_preflight.ps1` on clean repo exits 0 (PASS).
- Inducing a Direction A violation (ghost script reference in a contract source) causes
  `workflow_preflight.ps1` to fail before the consistency check line.
- `pwsh tools/start_task.ps1 -DryRun -TaskId TASK-999 -Goal test` runs through preflight
  without error.
- `python -m unittest discover` → 195 tests, 0 failures.
- `git diff --stat` shows only `tools/workflow_preflight.ps1`.

## Verification commands
1. Clean-repo run:
   `pwsh tools/workflow_preflight.ps1`
2. Failure-path proof (Direction A):
   - Add ghost reference to a contract source, run preflight, confirm nonzero exit
     with contract-integrity error message; revert.
3. Dry-run start_task:
   `pwsh tools/start_task.ps1 -DryRun -TaskId TASK-999 -Goal "test"`
4. Full suite:
   `python -m unittest discover`
5. Diff check:
   `git diff --stat`
