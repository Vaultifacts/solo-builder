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

## Proposed Split

### Phase 1 — Extract pure config constants (no test-patch risk)

Move non-patched config constants that are read-only derivations to
`solo_builder/config/loader.py`:

```python
# solo_builder/config/loader.py
"""Read-only config constants derived from settings.json."""
import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(os.path.dirname(_HERE), "config", "settings.json")

def load() -> dict:
    try:
        with open(_CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
```

Constants that can safely move: `STALL_THRESHOLD`, `SNAPSHOT_INTERVAL`,
`MAX_SUBTASKS_PER_BRANCH`, `EXECUTOR_VERIFY_PROBABILITY`, `AUTO_STEP_DELAY`,
`AUTO_SAVE_INTERVAL`, `VERBOSITY`, `CLAUDE_ALLOWED_TOOLS`.

**Risk:** Low — these are read-only; no test patches target them.

### Phase 2 — CLI command dispatch

Move `do_*` command methods to `solo_builder/commands/dispatcher.py`. The
`solo_builder_cli.py` entry point delegates to the dispatcher.

**Risk:** Medium — requires verifying all 534+ tests still patch the right module.

### Phase 3 — Mixin host refactor

The `_inject_host_globals_into_mixins` function and the five frozen globals stay
in `solo_builder_cli.py` until a separate task updates all test patches.

---

## Decision

Phase 1 only in TASK-322 scope. Phases 2 and 3 deferred: the prerequisite is
a comprehensive patch-update task estimated at 3–5 hours.

**Status:** Phase 1 deferred to avoid scope creep in TASK-322. This design doc
captures the intent so Phase 1 can be picked up as an independent task.

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial design spike (TASK-322). TD-ARCH-001 constraint analysis complete. Phase 1 scoped; Phases 2–3 deferred. |
