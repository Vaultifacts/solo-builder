# CLI God File Refactor Design
**TASK-322 | TD-ARCH-001**
Last updated: 2026-03-10

---

## Problem

`solo_builder_cli.py` (~665 lines) acts simultaneously as:
- Application entry point (`if __name__ == "__main__"`)
- Config loader (reads `settings.json`, sets globals)
- CLI command dispatcher (`do_step`, `do_auto`, etc.)
- Mixin host (`_inject_host_globals_into_mixins`)

This makes it hard to extend, test in isolation, or onboard new contributors.

---

## Constraint: Five Frozen Globals

Five globals **must remain** in `solo_builder_cli.py` because test patches target
`solo_builder_cli.X` by name. Moving them breaks ~400 test assertions.

| Global | Reason frozen |
|---|---|
| `_PDF_OK` | Patched in PDF-related tests |
| `_CFG_PATH` | Patched to redirect config loading |
| `STATE_PATH` | Patched to use temp state files |
| `JOURNAL_PATH` | Patched to use temp journal |
| `WEBHOOK_URL` | Patched to suppress real webhooks |

**Rule:** These five globals stay in `solo_builder_cli.py` until all test patches
are updated — that is a separate, larger task.

---

## Global Mutability Analysis (TASK-323)

Investigation of `do_set()` and `global` declarations reveals three categories:

**Mutable at runtime via `do_set` — cannot move without `global` cascade:**
`STALL_THRESHOLD`, `SNAPSHOT_INTERVAL`, `VERBOSITY`, `AUTO_STEP_DELAY`,
`AUTO_SAVE_INTERVAL`, `CLAUDE_ALLOWED_TOOLS`

**Frozen by test-patch — cannot move:**
`_PDF_OK`, `_CFG_PATH`, `STATE_PATH`, `JOURNAL_PATH`, `WEBHOOK_URL`

**Truly read-only after init — not patched, not mutated by `do_set`:**
`DAG_UPDATE_INTERVAL`, `PDF_OUTPUT_PATH`, `BAR_WIDTH`, `MAX_ALERTS`,
`EXEC_MAX_PER_STEP`, `EXEC_VERIFY_PROB`, `MAX_SUBTASKS_PER_BRANCH`,
`MAX_BRANCHES_PER_TASK`, `CLAUDE_TIMEOUT`, `ANTHROPIC_MODEL`,
`ANTHROPIC_MAX_TOKENS`, `REVIEW_MODE`, `_PROJECT_CONTEXT`

The read-only subset could be moved to `solo_builder/config/loader.py` and
re-imported in `solo_builder_cli.py` to preserve `solo_builder_cli.X` access.
However no other module currently imports them from `solo_builder_cli`, so the
benefit is marginal (~12-line reduction). Phase 1 is feasible but low-priority
until another module needs them directly.

---

## Proposed Split

### Phase 1 — Extract truly read-only config constants

Move the 13 read-only constants listed above to `solo_builder/config/loader.py`.
Re-import them in `solo_builder_cli.py` for backwards compatibility.

**Risk:** Low — no test patches target them; no `global` mutations involved.
**Value:** Low — no other module currently needs them.
**Trigger:** Promote to active when a second consumer appears.

### Phase 2 — CLI command dispatch

Move `do_*` command methods to `solo_builder/commands/dispatcher.py`. The
`solo_builder_cli.py` entry point delegates to the dispatcher.

**Risk:** Medium — requires verifying all 534+ tests still patch the right module.

### Phase 3 — Mixin host refactor

The `_inject_host_globals_into_mixins` function and the five frozen globals stay
in `solo_builder_cli.py` until a separate task updates all test patches.

---

## Decision

Phases 1, 2, and 3 deferred. Phase 1 requires correcting the initial
"read-only" premise: only 13 truly read-only constants qualify, and extraction
is low-value without a second consumer. Phases 2–3 require the patch-update
task estimated at 3–5 hours.

**Status:** Design spike complete. TD-ARCH-001 remains open. Extraction deferred
until there is a concrete second-module consumer for the read-only constants.

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial design spike (TASK-322). TD-ARCH-001 constraint analysis complete. Phase 1 scoped; Phases 2–3 deferred. |
| 2026-03-10 | TASK-323: corrected Phase 1 — `do_set` mutates 6 constants originally listed as read-only. Three-category classification added. Phase 1 demoted to low-priority. |
