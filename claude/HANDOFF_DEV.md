# HANDOFF TO DEV (from ARCHITECT)

## Problem summary
`tools/extract_allowed_files.ps1` currently fails to extract allowed files when `claude/HANDOFF_DEV.md` uses heading variants outside a single strict pattern. This caused manual fallback during TASK-010.

## Root cause
The parser is overly strict:
- Section start requires exact `## Allowed changes` match.
- It is effectively case-sensitive and heading-level specific.
- It does not recognize common alias labels like `Allowed files`.

Because of this, valid handoffs with slightly different heading text/format are treated as missing.

## Minimal fix strategy
Implement a narrow alias-based heading parser in `tools/extract_allowed_files.ps1` that:
1. Accepts a small explicit set of section-start labels (not free-form):
   - `## Allowed changes`
   - `## Allowed files`
   - `Allowed changes:`
   - `Allowed files:`
   (case-insensitive)
2. Keeps existing bullet extraction semantics (`- path` lines only).
3. Uses bounded section termination so extraction stops at the next heading/section marker and does not over-capture from `Disallowed changes`, `Implementation plan`, `Verification steps`.
4. Preserves existing output contract and failure behavior when no valid paths are found.

## Allowed files to modify
- tools/extract_allowed_files.ps1

## Files that must not be modified
- Any files under `solo_builder/`
- `tools/dev_gate.ps1` and other workflow scripts
- `claude/VERIFY.json` and verification contract files
- Any unrelated documentation or task files

## Risks
- Overly permissive alias matching could capture wrong sections.
- Incorrect section-end handling could include non-path bullets.
- Behavioral drift in error handling could break existing guardrail expectations.

## Acceptance criteria
- `pwsh tools/extract_allowed_files.ps1` writes `claude/allowed_files.txt` when handoff uses common heading variants.
- Heading variants including `## Allowed changes` and `Allowed files` parse correctly.
- Extraction remains limited to intended section and bullet path lines.
- Existing failure contract remains: empty/missing valid section still exits non-zero and instructs manual fill.
- No product-code changes.

## Verification commands
1. `pwsh tools/extract_allowed_files.ps1`
2. Validate with fixture handoff text variants (at minimum):
   - `## Allowed changes`
   - `## Allowed files`
   - `Allowed changes:`
   - `Allowed files:`
3. `Get-Content claude/allowed_files.txt`
4. `pwsh tools/dev_gate.ps1 -Mode Manual -SnapshotOnFail`
5. `pwsh tools/audit_check.ps1`
