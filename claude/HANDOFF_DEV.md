# HANDOFF TO DEV (from ARCHITECT)

## Task
TASK-103

## Goal
Refactor `solo_builder/solo_builder_cli.py` (2965 lines) into focused modules.
Each step must leave tests green and the CLI fully functional.

---

## Implementation Plan

Execute steps in order. Commit after each step. Run tests after each commit.

### Step 1 -- Extract INITIAL_DAG (zero risk)
- Create `solo_builder/dag_definition.py`
- Move the `INITIAL_DAG` dict (lines 123-317) into it as a module-level constant
- In `solo_builder_cli.py`: `from solo_builder.dag_definition import INITIAL_DAG` (or relative: `from .dag_definition import INITIAL_DAG`)
- No logic changes, no behavioural change

### Step 2 -- Extract TerminalDisplay (zero risk)
- Create `solo_builder/display.py`
- Move the `TerminalDisplay` class (lines 394-534) into it
- It imports only from `utils.helper_functions` (make_bar, ANSI constants) -- no circular deps
- In `solo_builder_cli.py`: `from solo_builder.display import TerminalDisplay`

### Step 3 -- Extract journal helpers (low risk)
- Create `solo_builder/journal.py`
- Move `_append_journal` and `_append_cache_session_stats` into it as module-level functions
- They depend on: `JOURNAL_PATH` (module global), `ResponseCache` (import from runners)
- Pass `journal_path` as a parameter rather than reading the global -- cleaner interface
- In `solo_builder_cli.py` and `main()`: import and call with explicit path arg

### Step 4 -- Extract read-only query commands as a mixin (low risk)
- Create `solo_builder/commands/__init__.py` (empty)
- Create `solo_builder/commands/query_cmds.py`
- Move these methods from `SoloBuilderCLI` into a `QueryCommandsMixin` class:
  `_cmd_status`, `_cmd_graph`, `_cmd_priority`, `_cmd_stalled`, `_cmd_agents`,
  `_cmd_forecast`, `_cmd_tasks`, `_cmd_history`, `_cmd_branches`, `_cmd_search`,
  `_cmd_filter`, `_cmd_timeline`, `_cmd_log`, `_cmd_diff`, `_cmd_stats`,
  `_cmd_output`, `_cmd_help`
- Mixin has no `__init__`; all methods use `self.dag`, `self.display`, `self.state` as-is
- `SoloBuilderCLI` inherits: `class SoloBuilderCLI(QueryCommandsMixin):`
- No logic changes

### Step 5 -- Extract subtask commands as a mixin (low risk)
- Create `solo_builder/commands/subtask_cmds.py`
- Move into `SubtaskCommandsMixin`:
  `_find_subtask`, `_cmd_describe`, `_cmd_verify`, `_cmd_tools`, `_cmd_rename`,
  `_cmd_heal`, `_cmd_pause`, `_cmd_resume`
- `_cmd_verify` calls `self.executor._roll_up(...)` -- keep as-is (self still works via MRO)
- `class SoloBuilderCLI(QueryCommandsMixin, SubtaskCommandsMixin):`

### Step 6 -- Extract DAG mutation commands as a mixin (medium risk)
- Create `solo_builder/commands/dag_cmds.py`
- Move into `DagCommandsMixin`:
  `_cmd_reset`, `_cmd_add_task`, `_cmd_add_branch`, `_cmd_prioritize_branch`,
  `_cmd_depends`, `_cmd_undepends`, `_cmd_import_dag`, `_cmd_export_dag`, `_cmd_export`,
  `_cmd_cache`, `_cmd_undo`, `_cmd_load_backup`
- These call `self.executor.claude.run(...)` and `self.save_state()` -- fine via self
- `class SoloBuilderCLI(QueryCommandsMixin, SubtaskCommandsMixin, DagCommandsMixin):`

### Step 7 -- Extract settings commands as a mixin (medium risk)
- Create `solo_builder/commands/settings_cmds.py`
- Move into `SettingsCommandsMixin`:
  `_persist_setting`, `_cmd_config`, `_cmd_set`
- `_cmd_set` uses `global` for module-level constants -- keep the globals in `solo_builder_cli.py`
  and have the mixin methods use `import solo_builder.solo_builder_cli as _cli_mod` to mutate
  them, OR simply leave `_cmd_set` in `SoloBuilderCLI` for now and only move `_cmd_config`
  and `_persist_setting` -- do not force the globals issue in this task
- `class SoloBuilderCLI(..., SettingsCommandsMixin):`

### Step 8 -- Update allowed_files.txt
Add all new files created above to `claude/allowed_files.txt`.

---

## Allowed Changes

```
solo_builder/solo_builder_cli.py
solo_builder/dag_definition.py          (NEW)
solo_builder/display.py                 (NEW)
solo_builder/journal.py                 (NEW)
solo_builder/commands/__init__.py       (NEW)
solo_builder/commands/query_cmds.py     (NEW)
solo_builder/commands/subtask_cmds.py   (NEW)
solo_builder/commands/dag_cmds.py       (NEW)
solo_builder/commands/settings_cmds.py  (NEW)
claude/allowed_files.txt
```

---

## Acceptance Criteria

1. `python -m pytest solo_builder/api/test_app.py -q` -- all 305 tests pass
2. `python -m pytest solo_builder/agents/test_agents.py solo_builder/runners/test_runners.py solo_builder/tests/test_cache.py -q` -- all pass
3. `python -m pytest solo_builder/discord_bot/test_bot.py -q` -- all pass
4. `wc -l solo_builder/solo_builder_cli.py` -- reduced by at least 1000 lines from 2965
5. All new files in `claude/allowed_files.txt`
6. No new top-level imports added to `solo_builder_cli.py` beyond what is needed to re-export from the new modules
7. `python solo_builder/solo_builder_cli.py --help` executes without error

---

## Constraints

- Do NOT refactor logic -- move code only, preserve behaviour exactly
- Do NOT change any public API, method signatures, or attribute names
- Do NOT touch `solo_builder/api/app.py`, runner files, or agent files
- Commit after each step so failures are bisectable
- Use relative imports within the `solo_builder` package (e.g. `from .dag_definition import INITIAL_DAG`)
