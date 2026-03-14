"""
agents/repo_analyzer.py
RepoAnalyzer agent — scans the repository for technical debt and generates
new DAG subtasks dynamically.

Runs BEFORE Planner in the step pipeline:
    RepoAnalyzer → Planner → ShadowAgent → SelfHealer → Executor
    → Verifier → ShadowAgent → MetaOptimizer

Safety features (Dynamic Task Safety Guard):
    - Persistent finding deduplication via FindingHistory
    - Configurable cooldown between analyses
    - Per-analysis and global dynamic task caps
    - Optional AI budget integration
"""

import ast
import os
import re
from typing import Any, Dict, List, Tuple

from utils.helper_functions import (
    CYAN, DIM, GREEN, RESET, YELLOW,
    add_memory_snapshot,
    validate_dag,
)
from utils.safety import FindingHistory, StepBudget


# ── Finding dataclass ────────────────────────────────────────────────────────
class Finding:
    """A single technical-debt finding from repository analysis."""

    __slots__ = ("category", "filepath", "detail")

    def __init__(self, category: str, filepath: str, detail: str) -> None:
        self.category = category   # "todo" | "large_file" | "missing_docstring" | "missing_test"
        self.filepath = filepath
        self.detail   = detail

    def __repr__(self) -> str:
        return f"Finding({self.category!r}, {self.filepath!r}, {self.detail!r})"


# ── Category → subtask description templates ─────────────────────────────────
_TEMPLATES: Dict[str, str] = {
    "todo":             "Resolve TODO/FIXME in {filepath}: {detail}",
    "large_file":       "Refactor {filepath} ({detail}) — break into smaller modules",
    "missing_docstring": "Add docstring to function {detail} in {filepath}",
    "missing_test":     "Create test file for {filepath} ({detail})",
}


class RepoAnalyzer:
    """
    Scans the project tree for technical debt signals and converts them
    into new DAG tasks/subtasks using the existing dynamic-task pattern.

    Configurable via settings keys:
        REPO_ANALYZER_ENABLED            (bool, default True)
        REPO_ANALYZER_INTERVAL           (int,  default 10 — run every N steps)
        REPO_ANALYZER_COOLDOWN_STEPS     (int,  default 15 — min steps between analyses)
        REPO_ANALYZER_MAX_FINDINGS       (int,  default 20)
        REPO_ANALYZER_LARGE_FILE         (int,  default 500 — line threshold)
        REPO_ANALYZER_SCAN_DIRS          (list[str])
        MAX_DYNAMIC_TASKS_PER_ANALYSIS   (int,  default 5)
        MAX_DYNAMIC_TASKS_TOTAL          (int,  default 50)
    """

    # ── Directories / extensions to always skip ──────────────────────────
    _SKIP_DIRS  = {".git", "__pycache__", "node_modules", ".venv", "venv",
                   "env", ".eggs", "*.egg-info", "snapshots", "state"}
    _PY_EXT     = ".py"

    def __init__(self, settings: Dict[str, Any] | None = None) -> None:
        cfg = settings or {}
        self.enabled       = cfg.get("REPO_ANALYZER_ENABLED", True)
        self.interval      = cfg.get("REPO_ANALYZER_INTERVAL", 10)
        self.cooldown      = cfg.get("REPO_ANALYZER_COOLDOWN_STEPS", 15)
        self.max_findings  = cfg.get("REPO_ANALYZER_MAX_FINDINGS", 20)
        self.max_per_analysis = cfg.get("MAX_DYNAMIC_TASKS_PER_ANALYSIS", 5)
        self.max_total     = cfg.get("MAX_DYNAMIC_TASKS_TOTAL", 50)
        self.large_file    = cfg.get("REPO_ANALYZER_LARGE_FILE", 500)
        self.scan_dirs: List[str] = cfg.get(
            "REPO_ANALYZER_SCAN_DIRS", [".", "utils", "api", "agents"]
        )
        self._root = cfg.get("REPO_ANALYZER_ROOT", os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        ))
        self._last_run_step: int = -max(self.interval, self.cooldown)  # force first run
        self._seen_findings: set = set()             # in-memory dedup (volatile)
        self._dynamic_tasks_created: int = 0         # running total across all runs

        # Persistent finding history (sidecar JSON)
        history_path = cfg.get("REPO_ANALYZER_HISTORY_PATH",
                               os.path.join("state", "finding_history.json"))
        self._history = FindingHistory(path=history_path)

    # ── Observability ────────────────────────────────────────────────────
    @property
    def dynamic_tasks_created(self) -> int:
        return self._dynamic_tasks_created

    @property
    def cooldown_remaining(self) -> int:
        """Steps remaining before next allowed analysis (0 = ready)."""
        elapsed = 0  # unknown until step is passed
        return 0

    def cooldown_remaining_at(self, step: int) -> int:
        """Steps remaining before next analysis at the given step."""
        effective = max(self.interval, self.cooldown)
        elapsed = step - self._last_run_step
        return max(0, effective - elapsed)

    # ── Public API ───────────────────────────────────────────────────────
    def should_run(self, step: int, force: bool = False) -> bool:
        """Return True when it's time for another scan."""
        if not self.enabled:
            return False
        if force:
            return True
        # Respect cooldown (uses the greater of interval and cooldown)
        effective = max(self.interval, self.cooldown)
        return (step - self._last_run_step) >= effective

    def analyze(
        self,
        dag: Dict,
        memory_store: Dict,
        step: int,
        alerts: List[str],
        budget: StepBudget | None = None,
        force: bool = False,
    ) -> int:
        """
        Scan the repo, generate findings, and inject new tasks into *dag*.
        Returns the number of new subtasks added.
        """
        if not self.should_run(step, force=force):
            return 0

        # Check global cap
        if self._dynamic_tasks_created >= self.max_total:
            alerts.append(
                f"  {YELLOW}[RepoAnalyzer]{RESET} global cap reached "
                f"({self._dynamic_tasks_created}/{self.max_total}) — skipping"
            )
            return 0

        self._last_run_step = step
        findings = self._scan(step)

        if not findings:
            return 0

        added = self._inject_tasks(dag, memory_store, step, findings)

        if added > 0:
            self._dynamic_tasks_created += added
            # Persist finding history after injection
            self._history.save()

            # Validate after mutation
            warnings = validate_dag(dag)
            for w in warnings:
                alerts.append(f"  {YELLOW}[RepoAnalyzer DAG Warning] {w}{RESET}")
            alerts.append(
                f"  {GREEN}[RepoAnalyzer]{RESET} +{added} tech-debt subtask(s) injected"
                f" ({self._dynamic_tasks_created}/{self.max_total} total)"
            )

        return added

    # ── Scanning ─────────────────────────────────────────────────────────
    def _scan(self, step: int) -> List[Finding]:
        """Run all scanners and return de-duped findings capped at limits."""
        findings: List[Finding] = []
        py_files = self._collect_py_files()

        for fpath in py_files:
            rel = os.path.relpath(fpath, self._root)
            findings.extend(self._scan_todos(fpath, rel))
            findings.extend(self._scan_large_file(fpath, rel))
            findings.extend(self._scan_missing_docstrings(fpath, rel))

        findings.extend(self._scan_missing_tests(py_files))

        # De-dup against persistent history AND in-memory set
        new_findings: List[Finding] = []
        for f in findings:
            # Check persistent history first (normalized dedup)
            if self._history.is_known(f.category, f.filepath, f.detail):
                continue
            # Check volatile in-memory dedup (exact match)
            key = (f.category, f.filepath, f.detail)
            if key in self._seen_findings:
                continue
            self._seen_findings.add(key)
            # Record in persistent history
            self._history.record(f.category, f.filepath, f.detail, step)
            new_findings.append(f)

        # Apply per-analysis cap (tighter of max_findings and max_per_analysis)
        effective_cap = min(self.max_findings, self.max_per_analysis)
        # Also respect remaining global budget
        remaining_global = max(0, self.max_total - self._dynamic_tasks_created)
        effective_cap = min(effective_cap, remaining_global)

        return new_findings[:effective_cap]

    def _collect_py_files(self) -> List[str]:
        """Gather all .py files under configured scan dirs."""
        result: List[str] = []
        for scan_dir in self.scan_dirs:
            base = os.path.join(self._root, scan_dir) if scan_dir != "." else self._root
            if not os.path.isdir(base):
                continue
            for dirpath, dirnames, filenames in os.walk(base):
                # Prune skipped dirs in-place
                dirnames[:] = [
                    d for d in dirnames if d not in self._SKIP_DIRS
                ]
                for fname in filenames:
                    if fname.endswith(self._PY_EXT):
                        result.append(os.path.join(dirpath, fname))
        return result

    # ── Individual scanners ──────────────────────────────────────────────
    _TODO_RE = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b[:\s]*(.*)", re.IGNORECASE)

    def _scan_todos(self, fpath: str, rel: str) -> List[Finding]:
        findings: List[Finding] = []
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    m = self._TODO_RE.search(line)
                    if m:
                        tag = m.group(1).upper()
                        msg = m.group(2).strip() or "(no description)"
                        findings.append(Finding(
                            "todo", rel,
                            f"L{lineno} {tag}: {msg}"
                        ))
        except OSError:
            pass
        return findings

    def _scan_large_file(self, fpath: str, rel: str) -> List[Finding]:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                count = sum(1 for _ in fh)
            if count > self.large_file:
                return [Finding("large_file", rel, f"{count} lines")]
        except OSError:
            pass
        return []

    def _scan_missing_docstrings(self, fpath: str, rel: str) -> List[Finding]:
        findings: List[Finding] = []
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=fpath)
        except (OSError, SyntaxError):
            return []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private/dunder helpers
                if node.name.startswith("_"):
                    continue
                docstring = ast.get_docstring(node)
                if not docstring:
                    findings.append(Finding(
                        "missing_docstring", rel,
                        f"{node.name}() at line {node.lineno}"
                    ))
        return findings

    def _scan_missing_tests(self, py_files: List[str]) -> List[Finding]:
        findings: List[Finding] = []
        test_basenames: set = set()

        # Collect existing test file basenames
        for fpath in py_files:
            bname = os.path.basename(fpath)
            if bname.startswith("test_") or bname.endswith("_test.py"):
                # Normalise: test_foo.py → foo.py
                if bname.startswith("test_"):
                    test_basenames.add(bname[5:])
                else:
                    test_basenames.add(bname[:-8] + ".py")

        # Check which source modules lack a test file
        for fpath in py_files:
            bname = os.path.basename(fpath)
            if bname.startswith("test_") or bname.endswith("_test.py"):
                continue
            if bname in ("__init__.py", "conftest.py", "setup.py"):
                continue
            rel = os.path.relpath(fpath, self._root)
            if bname not in test_basenames:
                findings.append(Finding(
                    "missing_test", rel,
                    f"no test_{{}} found for {bname}"
                ))
        return findings

    # ── DAG injection ────────────────────────────────────────────────────
    def _inject_tasks(
        self,
        dag: Dict,
        memory_store: Dict,
        step: int,
        findings: List[Finding],
    ) -> int:
        """
        Convert findings into new DAG tasks/subtasks following the
        existing _cmd_add_task pattern.
        """
        if not findings:
            return 0

        task_idx  = len(dag)
        task_name = f"Task {task_idx}"
        # Avoid collision
        while task_name in dag:
            task_idx += 1
            task_name = f"Task {task_idx}"

        letter      = chr(ord("A") + task_idx % 26)
        branch_name = f"Branch {letter}"

        subtasks: Dict[str, Dict[str, Any]] = {}
        for i, finding in enumerate(findings, 1):
            st_name = f"{letter}{i}"
            template = _TEMPLATES.get(finding.category, "{detail}")
            description = template.format(
                filepath=finding.filepath,
                detail=finding.detail,
            )
            subtasks[st_name] = {
                "status":      "Pending",
                "shadow":      "Pending",
                "last_update": step,
                "description": description,
                "output":      "",
            }

        # Wire dependency to the last existing task
        last_task = list(dag.keys())[-1] if dag else None

        dag[task_name] = {
            "status":     "Pending",
            "depends_on": [last_task] if last_task else [],
            "branches": {
                branch_name: {
                    "status":   "Pending",
                    "subtasks": subtasks,
                }
            },
        }

        # Initialise memory store for the new branch
        if branch_name not in memory_store:
            memory_store[branch_name] = []
        add_memory_snapshot(
            memory_store, branch_name,
            f"RepoAnalyzer: {len(findings)} tech-debt finding(s)", step,
        )

        return len(subtasks)
