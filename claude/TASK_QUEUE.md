# Task Queue

## TASK-001
Goal: Create the first real end-to-end workflow task for this repo that is small but meaningful.

Constraints:
- Must exercise Research -> Architect -> Dev -> Auditor loop.
- Must touch only a few files.
- Must have clear acceptance criteria that can be validated by audit_check.

Acceptance Criteria:
- `claude/HANDOFF_ARCHITECT.md` contains a research handoff for `TASK-001` with at least one evidence-backed hypothesis and one explicit unknown.
- `claude/HANDOFF_DEV.md` contains an implementation plan for `TASK-001` with an `Allowed changes` section listing exact file paths.
- `claude/allowed_files.txt` can be generated from `HANDOFF_DEV.md` by running `pwsh tools/extract_allowed_files.ps1` without error.
- `pwsh tools/audit_check.ps1` exits with code 0 after task handoff files are prepared.

Priority: High

## TASK-002
Goal: Repair the `dev_gate` blocker caused by a syntax/runtime error in `tools/secret_scan.ps1`.

Constraints:
- Scope limited to guardrail reliability.
- Fix must remain PowerShell 5.1 compatible.
- No behavior expansion beyond correcting the broken guard execution path.

Acceptance Criteria:
- `pwsh tools/secret_scan.ps1` runs without syntax/parsing errors.
- `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail` proceeds past `secret_scan.ps1` on a clean staging set.
- No files outside TASK-002 allowed scope are modified for the fix.

Priority: Urgent

## TASK-003
Goal: Make `tools/precommit_gate.ps1` non-blocking by default and robust on Windows.

Constraints:
- Scope limited to `tools/precommit_gate.ps1`.
- Keep behavior deterministic and PowerShell 5.1 compatible.
- Do not run optional Python/unittest commands from precommit gate.

Acceptance Criteria:
- If no safe fast command is available, `precommit_gate` exits 0 with guidance.
- `precommit_gate` runs at most one safe fast command (name-filtered and timeout <= 300s).
- `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail` no longer fails in `precommit_gate` due optional unittest execution.

Priority: Urgent

## TASK-004
Goal: Identify exactly which command mutates `solo_builder/config/settings.json` and why.

Acceptance criteria:
- A minimal reproduction sequence (exact commands, in order)
- Evidence: before/after diff summary
- Recommendation: one of (ignore file, stop tool from writing, redirect writes elsewhere)

## TASK-005
Goal: Identify which verification sub-command executed by `tools/audit_check.ps1` writes `solo_builder/config/settings.json`, and eliminate or isolate that write.

Acceptance criteria:
- Exact mutating sub-command identified
- Minimal reproduction sequence documented
- Recommendation for fix path:
  - stop command from writing config, or
  - redirect writes to temp/state file, or
  - mock/isolate config in tests

## TASK-006
Goal: Identify the next remaining unittest path outside `solo_builder/api/test_app.py` that mutates `solo_builder/config/settings.json` during `python -m unittest discover`.

Acceptance criteria:
- exact mutating test module/class/function identified (not just unittest-discover generically)
- minimal reproduction sequence documented
- before/after evidence captured
- recommendation for the next minimal fix path

## TASK-007
Goal: Isolate and eliminate the remaining config writer path in `solo_builder.discord_bot.test_bot`, with primary focus on `TestHandleTextCommandExtra.test_set_trigger_consumed_by_cli` and directly related fixture/setup code.

Acceptance criteria:
- exact remaining mutating test method/class confirmed
- minimal reproduction sequence documented
- recommendation for the smallest fix path
- no change to production code yet unless absolutely required

## TASK-008
Goal: Fix one existing failing unittest by making CLI status output robust on Windows console encoding paths.

Acceptance criteria:
- Running `python -m unittest solo_builder.discord_bot.test_bot.TestAddTaskInlineSpec` no longer fails due to UnicodeEncodeError from CLI output formatting.
- Running `python -m unittest solo_builder.discord_bot.test_bot.TestAddBranchInlineSpec` no longer fails due to UnicodeEncodeError from CLI output formatting.
- Verification includes `pwsh tools/audit_check.ps1` and no mutation of `solo_builder/config/settings.json`.

Constraints:
- Keep scope narrow
- Prefer touching as few files as possible
- No unrelated refactors

## TASK-009
Goal: Fix the remaining optional unittest UnicodeEncodeError in the `_cmd_undo` output path.

Acceptance criteria:
- The affected unittest no longer fails with UnicodeEncodeError.
- `pwsh tools/audit_check.ps1` passes.
- No mutation of `solo_builder/config/settings.json`.

Constraints:
- Keep scope narrow
- Prefer touching as few files as possible
- No unrelated refactors
