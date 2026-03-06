# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-012`
- Scope: workflow documentation and prompt/template schema normalization.
- Goal constraint: canonical handoff heading schema without workflow semantic changes.

## Evidence collected
- Canonical schema is explicitly defined in `claude/TASK_QUEUE.md` under `TASK-012` acceptance criteria:
  - `## Allowed changes`
  - `## Files that must not be modified`
  - `## Acceptance criteria`
  - `## Verification commands`
- Current template mismatch in `claude/templates/HANDOFF_DEV_TEMPLATE.md`:
  - Contains `## Allowed changes`, `## Constraints`, `## Acceptance criteria`
  - Does not contain canonical `## Files that must not be modified`
  - Does not contain canonical `## Verification commands`
- Current in-repo drift example in `claude/HANDOFF_DEV.md`:
  - Uses `## Allowed files to modify` instead of canonical `## Allowed changes`
  - Includes `## Verification commands` and `## Files that must not be modified`
  - Demonstrates mixed heading vocabulary across active workflow artifacts.
- Prompt guidance currently available in `claude/prompts/dev_prompt.txt` is minimal and does not define canonical handoff heading schema.
- `pwsh tools/research_extract.ps1` generated `claude/RESEARCH_DRAFT.md`, but provided no CI artifacts or direct schema guidance for this task (local file-structure research was required).

## Observations
- Stable/confirmed:
  - TASK-012 already defines the canonical schema in task acceptance criteria.
  - Existing template(s) and live handoff files are not consistently aligned to that schema.
  - Heading drift has historically occurred during normal role output generation.
- Uncertain:
  - Whether all role prompts/templates that can produce handoff files are present on this branch.
  - Whether any off-template/manual generation paths will continue introducing non-canonical headings after normalization.

## Heading drift patterns
- Equivalent intent represented by different section names:
  - `Allowed changes` vs `Allowed files to modify`
  - `Verification commands` vs `Verification steps`
  - `Constraints` vs `Files that must not be modified` (overlap but not equivalent semantics)
- Drift appears to come from:
  - Template/schema inconsistency
  - Prompt text that does not enforce explicit required section names
  - Human/agent free-form edits in handoff artifacts

## Tooling assumptions relevant to schema
- `tools/extract_allowed_files.ps1` is now alias-tolerant (from TASK-011), so extraction can succeed across non-canonical labels.
- TASK-012 objective is schema normalization; alias tolerance should be treated as backward compatibility, not target format.
- Verification should ensure canonical schema is used at source (templates/prompts/docs), not only tolerated by parser.

## Risks and edge cases
- Over-normalizing historical handoff files may create unnecessary churn and noise.
- If prompts/templates diverge, future handoffs can regress despite canonical definitions in `TASK_QUEUE.md`.
- Canonical schema requirements must remain explicit and synchronized wherever handoff format is generated.

## Minimal documentation/template scope candidates
- Files directly defining handoff format expectations:
  - `claude/templates/HANDOFF_DEV_TEMPLATE.md`
  - Workflow prompt/template files under `claude/prompts/` that instruct handoff structure
  - Any workflow docs that describe required handoff sections (if present on branch)
- Out-of-scope for TASK-012 research findings:
  - Product code under `solo_builder/*`
  - Orchestrator/state semantics changes

## Hypotheses (ranked)
- H1: Schema drift is primarily caused by incomplete/inconsistent handoff templates and prompt wording, not parser behavior.
- H2: Establishing one canonical heading set in all handoff-producing templates/prompts will prevent most recurrence.
- H3: Keeping parser aliases while enforcing canonical generation provides compatibility without changing workflow semantics.

## Constraints / Non-negotiables
- No product-code changes.
- No orchestrator/state-machine semantic changes.
- Preserve deterministic role workflow while normalizing section names at documentation/template layer.
