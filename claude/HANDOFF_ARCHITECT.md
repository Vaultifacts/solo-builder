# HANDOFF: RESEARCH -> ARCHITECT
Task: TASK-103
Goal: Refactor solo_builder_cli.py (2965 lines) into focused modules

---

## File Structure Summary

`solo_builder/solo_builder_cli.py` is 2965 lines containing:
- ~195 lines of pure data (`INITIAL_DAG`)
- `TerminalDisplay` class (lines 394-534, ~140 lines)
- `SoloBuilderCLI` class (lines 540-2660, ~2120 lines, 50+ methods)
- Module-level helpers + `main()` (lines 1-393, 2662-2965)

---

## Logical Groupings (proposed modules)

| Group | Current Lines | Candidate Module |
|-------|--------------|-----------------|
| A. Constants + config loading | 1-120 | stays in cli (init-time) |
| B. INITIAL_DAG data | 123-317 | `dag_definition.py` |
| C. Journal helpers | 320-378 | `journal.py` |
| D. TerminalDisplay | 394-534 | `display.py` |
| E. Core step / orchestration | 540-678 | stays in `SoloBuilderCLI` |
| F. Persistence (save/load/backup) | 680-841 | persistence mixin |
| G. Trigger IPC + auto-loop | 843-1067 | `ipc/trigger_poller.py` |
| H. Command dispatcher + start() | 1069-1261 | stays in `SoloBuilderCLI` |
| I. DAG mutation commands | 1284-1570 | `commands/dag_cmds.py` |
| J. Subtask commands | 1916-2060 | `commands/subtask_cmds.py` |
| K. Config/settings commands | 1572-1742 | `commands/settings_cmds.py` |
| L. Export | 1744-1777 | `commands/export_cmds.py` |
| M. Read-only query commands | 1828-2543 | `commands/query_cmds.py` |
| N. Entry point helpers | 2662-2965 | `entrypoint.py` |

---

## Top 5 Largest Functions

| Rank | Function | Size |
|------|----------|------|
| 1 | `main()` | ~209 lines |
| 2 | `_cmd_auto` | ~207 lines |
| 3 | `_cmd_set` | ~137 lines |
| 4 | `_cmd_add_task` | ~106 lines |
| 5 | `run_step` | ~94 lines |

---

## Critical Dependency Risks

1. **`_cmd_set` mutates module-level globals** (`STALL_THRESHOLD`, `AUTO_STEP_DELAY`, `WEBHOOK_URL`, etc.) AND simultaneously mutates agent instance attributes (`self.healer`, `self.planner`, `self.display`, `self.executor.*`). Any split must centralise config state in an object or pass references explicitly.

2. **`_cmd_auto` is the hub** -- calls every `_cmd_*` method. Cannot be split without a stable method-dispatch protocol already in place.

3. **`_fire_completion`** references module-level `WEBHOOK_URL` global -- needs config object access.

4. **`_cmd_add_task` / `_cmd_add_branch`** call `self.executor.claude.run(...)` directly -- access runner internals.

5. **`run_step` and `_cmd_verify`** both call `self.executor._roll_up(...)` -- internal runner method accessed from CLI layer.

---

## Key Findings

- `INITIAL_DAG` (lines 123-317) is 195 lines of pure data with zero logic dependencies -- cleanest extraction candidate, no risk.
- `TerminalDisplay` (lines 394-534) has no intra-class dependencies on `SoloBuilderCLI` -- clean extraction to `display.py`.
- `_cmd_auto`'s trigger-poll block (lines 927-1048, ~120 lines) is self-contained inline logic -- candidate for a `TriggerPoller` class.
- All read-only query commands (group M, ~20 methods) only read `self.dag` and call display -- safe to extract as a mixin after display is separated.
- The mutable globals pattern is the biggest structural risk for splitting `_cmd_set`.

---

## Hypotheses

1. Safe to extract `INITIAL_DAG` and `TerminalDisplay` in a single commit with no behavioural change.
2. A `RuntimeConfig` dataclass replacing the scattered module-level globals would unblock splitting `_cmd_set` and `_cmd_config` cleanly.
3. Mixin classes (no `__init__`, just methods) are the lowest-risk way to split `SoloBuilderCLI` commands -- avoids import cycle issues since all methods still access `self` from the one class.
4. `_cmd_auto` should be split last; it depends on all other commands being stable.
5. All 305 existing API tests (`test_app.py`) plus agent/runner/cache unit tests must pass after every incremental commit.

---

## Recommended Incremental Order

1. Extract `INITIAL_DAG` to `solo_builder/dag_definition.py` -- zero risk
2. Extract `TerminalDisplay` to `solo_builder/display.py` -- zero risk
3. Extract journal helpers to `solo_builder/journal.py` -- low risk
4. Introduce `RuntimeConfig` dataclass in `solo_builder/runtime_config.py` -- replaces module globals; refactor `_cmd_set` to use it
5. Extract trigger-poll block from `_cmd_auto` to `solo_builder/ipc/trigger_poller.py`
6. Extract read-only query commands (group M) as a mixin `solo_builder/commands/query_cmds.py`
7. Extract DAG mutation commands (group I) as a mixin `solo_builder/commands/dag_cmds.py`
8. Extract subtask commands (group J) as a mixin `solo_builder/commands/subtask_cmds.py`
9. Extract entry-point helpers to `solo_builder/entrypoint.py`
10. Run full test suite after each step; commit individually
