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
`EXEC_MAX_PER_STEP`, `MAX_SUBTASKS_PER_BRANCH`, `MAX_BRANCHES_PER_TASK`,
`CLAUDE_TIMEOUT`, `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`, `REVIEW_MODE`,
`_PROJECT_CONTEXT`

**Bug fixed (TASK-324):** `EXEC_VERIFY_PROB` was listed as read-only but
`do_set VERIFY_PROB` only updated `self.executor.verify_prob`, not the global.
Fixed: `EXEC_VERIFY_PROB` now declared in the `global` statement and kept in sync.

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

**Status: ~95% complete (TASK-107).** `commands/dispatcher.py` already contains
`DispatcherMixin.handle_command()` and `start()` with dispatch to all `_cmd_*`
methods. Only one `_cmd_*` implementation remains in `solo_builder_cli.py`:

| Method | Location | Blocker |
|---|---|---|
| `_cmd_set` | `solo_builder_cli.py` | Uses `global STALL_THRESHOLD, SNAPSHOT_INTERVAL, ...` — `global` writes to defining module's namespace; moving breaks mutation semantics |

**Phase 2 test-patch audit (TASK-324):** 0 tests patch or invoke `_cmd_*`
methods by name. Test-patch risk is Low.

**Remaining work:** Move `_cmd_set` by replacing the module-global mutation
pattern with a mutable config dict (`_runtime_cfg`) stored on the `SoloBuilderCLI`
instance. `_cmd_set` can then live anywhere and modify `self._runtime_cfg`
instead of raw module globals. Estimated scope: Small (1–2 hours).

### Phase 3 — Mixin host refactor

The `_inject_host_globals_into_mixins` function and the five frozen globals stay
in `solo_builder_cli.py` until a separate task updates all test patches.

---

## Decision

Phases 1, 2, and 3 deferred. Phase 1 requires correcting the initial
"read-only" premise: only 13 truly read-only constants qualify, and extraction
is low-value without a second consumer. Phases 2–3 require the patch-update
task estimated at 3–5 hours.

**Status:** Design spike complete. TD-ARCH-001 remains open. Phase 2 is ~95%
done from TASK-107 — only `_cmd_set` remains, blocked by the module-global
mutation pattern. Path forward: introduce `self._runtime_cfg` dict on
`SoloBuilderCLI` and route all `_cmd_set` mutations through it. Phase 1
remains low-priority (no second consumer for read-only constants).

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial design spike (TASK-322). TD-ARCH-001 constraint analysis complete. Phase 1 scoped; Phases 2–3 deferred. |
| 2026-03-10 | TASK-323: corrected Phase 1 — `do_set` mutates 6 constants originally listed as read-only. Three-category classification added. Phase 1 demoted to low-priority. |
| 2026-03-10 | TASK-324: Phase 2 risk downgraded — 0 tests patch `do_*` methods. EXEC_VERIFY_PROB global drift fixed. |
| 2026-03-10 | TASK-325: Phase 2 found ~95% done from TASK-107; only _cmd_set remains, blocked by module-global mutation; path forward via self._runtime_cfg documented. |
