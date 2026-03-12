# Solo Builder — Developer Notes

## Mixin Architecture & Test-Patch Constraints

`SoloBuilderCLI` is composed from multiple mixin classes to keep each file focused:

```
SoloBuilderCLI(
    DispatcherMixin,        # commands/dispatcher.py  — handle_command, start
    AutoCommandsMixin,      # commands/auto_cmds.py   — _cmd_auto
    StepRunnerMixin,        # commands/step_runner.py — run_step, save/load_state
    QueryCommandsMixin,     # commands/query_cmds.py  — status, history, graph …
    SubtaskCommandsMixin,   # commands/subtask_cmds.py
    DagCommandsMixin,       # commands/dag_cmds.py
    SettingsCommandsMixin,  # commands/settings_cmds.py — _cmd_config
)
```

### How globals are shared with mixin modules

`_inject_host_globals_into_mixins()` (called once at module load) copies every
module-level name from `solo_builder_cli` into each mixin module using
`dict.setdefault()`.  This means:

- **Values are copied once at import time.**
- If a test patches `solo_builder_cli.FOO`, the mixin module still holds the
  original value — the patch does **not** propagate.

### The five test-patched globals

| Global | Patched by | Affected functions |
|---|---|---|
| `_PDF_OK` | `test_bot.TestSnapshotCommand` | `_take_snapshot` |
| `_CFG_PATH` | `test_bot.TestSetCommand` | `_persist_setting` |
| `STATE_PATH` | `test_bot.TestLoadBackup` | `load_state`, `save_state` |
| `JOURNAL_PATH` | `test_cache.TestAppendCacheSessionStats` | `_append_journal`, `_append_cache_session_stats` |
| `WEBHOOK_URL` | `test_bot.TestSetCommand` (indirectly) | `_fire_completion` |

### Rule: stay in `solo_builder_cli.py`

Any function that reads one of the above globals **must be defined directly in
`solo_builder_cli.py`** (on `SoloBuilderCLI` or at module level) — not in a mixin
file. Extraction to a mixin would cause the function to read the injected copy, not
the test-patched one, breaking tests silently.

Current functions that must stay in cli.py for this reason:

| Function | Reason |
|---|---|
| `_take_snapshot` | reads `_PDF_OK` |
| `_persist_setting` | reads `_CFG_PATH` |
| `_cmd_set` | writes `global STALL_THRESHOLD` etc. — globals live in this module |
| `_append_journal` | reads `JOURNAL_PATH` |
| `_append_cache_session_stats` | reads `JOURNAL_PATH` |
| `_fire_completion` | reads `WEBHOOK_URL` which is mutated at runtime |
| `main()` | writes `global WEBHOOK_URL`; also creates `SoloBuilderCLI()` — circular import if extracted |

### Safe to extract

Functions that take all their inputs as arguments (no module-global reads) are safe
to move to `cli_utils.py` or other helper modules:

- `_setup_logging(log_path)` ✓
- `_splash(pdf_ok)` ✓
- `_acquire_lock(lock_path)` / `_release_lock(lock_path)` ✓
- `_handle_status_subcommand(state_path)` ✓
- `_handle_watch_subcommand(state_path, interval)` ✓

### Instance-attribute MagicMock shadowing (TASK-407 discovery)

When `_FakeCLI` (or any test double) assigns a `MagicMock` as an **instance attribute**
with the same name as a real mixin method, the instance attribute silently wins:

```python
class _FakeCLI(StepRunnerMixin):
    def __init__(self):
        self.save_state = MagicMock()  # shadows StepRunnerMixin.save_state!
```

Calling `self.cli.save_state()` calls the mock — the real method is never reached,
leaving lines inside `StepRunnerMixin.save_state` permanently uncovered.

**Fix**: delete the instance attribute before calling the real method:

```python
del self.cli.save_state          # remove instance shadow → real method is exposed
StepRunnerMixin.save_state(self.cli)  # call directly via unbound call
```

This pattern is needed whenever you need to cover code inside a mixin method that
was previously masked by a test-double instance attribute.

### How to test this constraint

If you're extracting a function and unsure whether it's safe, run:

```bash
cd solo_builder
python -m unittest discover -s . -p "test_*.py"
```

Then grep the test that patches the relevant global and confirm it still passes.
The key test classes:

- `TestSnapshotCommand` → `_PDF_OK`
- `TestSetCommand` → `_CFG_PATH`, `WEBHOOK_URL`
- `TestAppendCacheSessionStats` → `JOURNAL_PATH`
