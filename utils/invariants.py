"""
utils/invariants.py
Lightweight DAG invariant checks for runtime post-phase validation.

Usage in run_step():
    from utils.invariants import check_post_phase
    violations = check_post_phase(dag, "RepoAnalyzer")
    if violations:
        for v in violations:
            alerts.append(f"  {YELLOW}[Invariant]{RESET} {v}")
"""

from typing import Dict, List

from utils.helper_functions import validate_dag


def check_post_phase(dag: Dict, phase: str) -> List[str]:
    """
    Quick structural + dependency check after a pipeline phase.
    Returns list of violation strings (empty = OK).
    Designed to be cheap enough to run every step.
    """
    violations: List[str] = []

    # Structural: valid statuses, required keys
    for w in validate_dag(dag):
        violations.append(f"[{phase}] {w}")

    # Dependency references must exist
    for task_name, task_data in dag.items():
        for dep in task_data.get("depends_on", []):
            if dep not in dag:
                violations.append(
                    f"[{phase}] {task_name}: depends_on '{dep}' missing from DAG"
                )

    return violations
