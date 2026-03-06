# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-011`
- Scope: workflow-maintenance only
- Target script: `tools/extract_allowed_files.ps1`

## Evidence collected
- Current parser logic in `tools/extract_allowed_files.ps1`:
  - Starts section only when line matches: `^\s*##\s+Allowed changes`
  - Stops when next H2 heading appears: `^\s*##\s+`
  - Collects only markdown bullets: `^\s*-\s+(.+)$`
- On miss, script behavior:
  - Writes empty `claude/allowed_files.txt`
  - Prints manual fill message
  - Exits with code 1
- Confirmed prior failure mode from TASK-010:
  - Parser reported: `No paths found in HANDOFF_DEV.md Allowed changes section. Fill claude/allowed_files.txt manually.`
  - Manual fallback was required.

## Current parse assumption (exact)
The script assumes all of the following are true simultaneously:
1. The heading is exactly H2 (`##`) and text is exactly `Allowed changes` (case-sensitive match as written).
2. Allowed file entries are markdown `-` bullets.
3. Section ends at the next H2 heading only.

## Heading variants to support (minimum)
- `## Allowed changes`
- `## Allowed Changes`
- `## Allowed files`
- `## Allowed Files`
- `Allowed changes` (non-heading label forms used by some agents)
- `Allowed files` (non-heading label forms)

## Edge cases to avoid
- Do not capture bullets from unrelated sections (`Disallowed changes`, `Implementation plan`, `Verification steps`).
- Do not treat narrative bullets as file paths.
- Preserve existing failure behavior when no valid file path lines are present.
- Do not change downstream workflow semantics (`allowed_files.txt` contract, exit codes, manual-fill fallback messaging).

## Candidate fixture text/examples for verification
### Example A (current canonical)
```
## Allowed changes
- tools/extract_allowed_files.ps1
```
### Example B (heading variant)
```
## Allowed files
- tools/extract_allowed_files.ps1
```
### Example C (non-heading label)
```
Allowed changes:
- tools/extract_allowed_files.ps1
```
### Example D (must not over-capture)
```
## Allowed changes
- tools/extract_allowed_files.ps1

## Disallowed changes
- No edits outside Allowed changes
```

## Hypotheses (ranked)
- H1: Heading matching is too strict (`## Allowed changes` only), causing valid handoffs with slight heading variation to fail extraction.
- H2: Section-end detection tied only to H2 boundaries allows malformed captures if agents use different heading levels or label styles.
- H3: Bullet-only extraction is acceptable but should be bounded by robust section-start/section-end detection to avoid accidental over-capture.

## Constraints / Non-negotiables
- Keep scope to `tools/extract_allowed_files.ps1` only.
- Maintain current output contract (`claude/allowed_files.txt` + nonzero exit on no paths).
- No product-code changes.
- No workflow semantic changes beyond extraction robustness.
