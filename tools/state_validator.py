"""State integrity validator — TASK-349 (PW-020 to PW-025).

Validates solo_builder_state.json for:
  - Schema integrity (required top-level keys, correct types)
  - Orphaned subtasks / branches referencing non-existent tasks
  - Dependency cycles in the DAG task graph (depends_on edges)
  - Invalid task-level depends_on references (points to unknown task)
  - Invalid subtask statuses (not in the known set)

Exit codes:
  0 — state is valid
  1 — validation errors found
  2 — usage / file error
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT    = Path(__file__).resolve().parent.parent
STATE_PATH   = REPO_ROOT / "solo_builder" / "state" / "solo_builder_state.json"

VALID_STATUSES = frozenset({
    "Pending", "Running", "Verified", "Failed",
    "Review", "Skipped", "Paused",
})

REQUIRED_TOP_LEVEL = ("dag", "step")


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "is_valid":  self.is_valid,
            "errors":    self.errors,
            "warnings":  self.warnings,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_cycle(graph: dict[str, list[str]]) -> list[str]:
    """Return a list of node IDs that are part of a dependency cycle, or []."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    cycle_nodes: list[str] = []

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbour in graph.get(node, []):
            if neighbour not in color:
                continue  # unknown dependency — caught elsewhere
            if color[neighbour] == GRAY:
                cycle_nodes.append(node)
                return True
            if color[neighbour] == WHITE and dfs(neighbour):
                cycle_nodes.append(node)
                return True
        color[node] = BLACK
        return False

    for node in list(graph):
        if color[node] == WHITE:
            dfs(node)

    return list(dict.fromkeys(cycle_nodes))  # deduplicated, stable order


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

def validate(
    state_path: Path | str | None = None,
    state: dict[str, Any] | None = None,
) -> ValidationReport:
    """Validate a state dict or a state JSON file.

    Pass *state* directly (for testing) or let the function load from
    *state_path* (defaults to the canonical STATE_PATH).
    """
    report = ValidationReport()

    if state is None:
        if state_path is None:
            state_path = STATE_PATH
        state_path = Path(state_path)
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            report.errors.append(f"State file not found: {state_path}")
            return report
        except json.JSONDecodeError as exc:
            report.errors.append(f"State file is not valid JSON: {exc}")
            return report

    if not isinstance(state, dict):
        report.errors.append("State root must be a JSON object (dict).")
        return report

    # 1. Required top-level keys
    for key in REQUIRED_TOP_LEVEL:
        if key not in state:
            report.errors.append(f"Missing required top-level key: '{key}'")

    # 2. step must be a non-negative integer
    step = state.get("step")
    if step is not None:
        if not isinstance(step, int) or isinstance(step, bool):
            report.errors.append(
                f"'step' must be an integer; got {type(step).__name__!r}"
            )
        elif step < 0:
            report.errors.append(f"'step' must be >= 0; got {step}")

    dag = state.get("dag")
    if dag is None:
        # Already reported as missing; nothing more to check
        return report

    if not isinstance(dag, dict):
        report.errors.append("'dag' must be a JSON object (dict).")
        return report

    task_ids = set(dag.keys())

    # Build dependency graph for cycle detection
    dep_graph: dict[str, list[str]] = {}

    for task_id, task_data in dag.items():
        if not isinstance(task_data, dict):
            report.errors.append(
                f"Task '{task_id}': value must be a JSON object."
            )
            continue

        # 3. Each task must have 'branches'
        if "branches" not in task_data:
            report.errors.append(
                f"Task '{task_id}': missing required key 'branches'."
            )

        # 4. depends_on — must be a list of known task IDs
        depends_on = task_data.get("depends_on", [])
        if not isinstance(depends_on, list):
            report.errors.append(
                f"Task '{task_id}': 'depends_on' must be a list."
            )
            dep_graph[task_id] = []
        else:
            for dep in depends_on:
                if dep not in task_ids:
                    report.errors.append(
                        f"Task '{task_id}': 'depends_on' references unknown task '{dep}'."
                    )
            dep_graph[task_id] = [d for d in depends_on if d in task_ids]

        # 5. branches validation
        branches = task_data.get("branches", {})
        if not isinstance(branches, dict):
            report.errors.append(
                f"Task '{task_id}': 'branches' must be a JSON object."
            )
            continue

        for branch_id, branch_data in branches.items():
            if not isinstance(branch_data, dict):
                report.errors.append(
                    f"Task '{task_id}' / Branch '{branch_id}': value must be a JSON object."
                )
                continue

            if "subtasks" not in branch_data:
                report.errors.append(
                    f"Task '{task_id}' / Branch '{branch_id}': missing required key 'subtasks'."
                )

            subtasks = branch_data.get("subtasks", {})
            if not isinstance(subtasks, dict):
                report.errors.append(
                    f"Task '{task_id}' / Branch '{branch_id}': 'subtasks' must be a JSON object."
                )
                continue

            for st_id, st_data in subtasks.items():
                if not isinstance(st_data, dict):
                    report.errors.append(
                        f"Task '{task_id}' / Branch '{branch_id}' / Subtask '{st_id}': "
                        f"value must be a JSON object."
                    )
                    continue

                # 6. Status validation
                status = st_data.get("status")
                if status is None:
                    report.warnings.append(
                        f"Task '{task_id}' / Branch '{branch_id}' / Subtask '{st_id}': "
                        f"missing 'status' key."
                    )
                elif status not in VALID_STATUSES:
                    report.warnings.append(
                        f"Task '{task_id}' / Branch '{branch_id}' / Subtask '{st_id}': "
                        f"unknown status {status!r}."
                    )

    # 7. Dependency cycle detection
    cycle_nodes = _detect_cycle(dep_graph)
    if cycle_nodes:
        report.errors.append(
            f"Dependency cycle detected involving task(s): {', '.join(sorted(cycle_nodes))}."
        )

    return report


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    state_path: Path | str | None = None,
) -> int:
    try:
        report = validate(state_path=state_path)
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 0 if report.is_valid else 1

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("State Integrity Report")
            print()
            if report.errors:
                print(f"  Errors:   {len(report.errors)}")
                for e in report.errors:
                    print(f"    [ERR] {e}")
            if report.warnings:
                print(f"  Warnings: {len(report.warnings)}")
                for w in report.warnings:
                    print(f"    [WARN] {w}")
            print()
            if exit_code == 0:
                print("State is valid.")
            else:
                print("Validation failed — see above.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate solo_builder_state.json integrity."
    )
    parser.add_argument("--json",    action="store_true", dest="as_json")
    parser.add_argument("--quiet",   action="store_true")
    parser.add_argument("--state",   default="", help="Override state.json path")
    args = parser.parse_args(argv)
    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        state_path=args.state or None,
    )


if __name__ == "__main__":
    sys.exit(main())
