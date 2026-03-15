"""
agents/repo_analyzer.py
RepoAnalyzer — scans the repository for technical debt patterns and generates
findings without depending on the SDK.

Safety features:
    - Persistent finding deduplication via FindingHistory
    - Per-analysis finding caps
    - File risk scoring via RepoIndex
"""

import ast
import logging
import os
import re
from typing import Any, Dict, List

from utils.repo_index import RepoIndex
from utils.safety import FindingHistory

logger = logging.getLogger(__name__)


class Finding:
    """A single technical-debt finding from repository analysis."""

    __slots__ = ("category", "filepath", "detail")

    def __init__(self, category: str, filepath: str, detail: str) -> None:
        self.category = category   # "todo" | "large_file" | "missing_docstring" | "missing_test"
        self.filepath = filepath
        self.detail = detail

    def __repr__(self) -> str:
        return f"Finding({self.category!r}, {self.filepath!r}, {self.detail!r})"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary representation."""
        return {
            "category": self.category,
            "filepath": self.filepath,
            "detail": self.detail,
        }


# Category → subtask description templates
_TEMPLATES: Dict[str, str] = {
    "todo":             "Resolve TODO/FIXME in {filepath}: {detail}",
    "large_file":       "Refactor {filepath} ({detail}) — break into smaller modules",
    "missing_docstring": "Add docstring to function {detail} in {filepath}",
    "missing_test":     "Create test file for {filepath} ({detail})",
}


class RepoAnalyzer:
    """
    Scans the project tree for technical debt signals.

    Configurable via settings keys:
        REPO_ANALYZER_ENABLED            (bool, default True)
        REPO_ANALYZER_MAX_FINDINGS       (int,  default 20)
        REPO_ANALYZER_LARGE_FILE         (int,  default 500 — line threshold)
        REPO_ANALYZER_SCAN_DIRS          (list[str], default [., utils, api, agents])
    """

    # Directories / extensions to always skip
    _SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
                  "env", ".eggs", "*.egg-info", "snapshots", "state"}
    _PY_EXT = ".py"

    def __init__(self, settings: Dict[str, Any] | None = None) -> None:
        cfg = settings or {}
        self.enabled = cfg.get("REPO_ANALYZER_ENABLED", True)
        self.max_findings = cfg.get("REPO_ANALYZER_MAX_FINDINGS", 20)
        self.large_file = cfg.get("REPO_ANALYZER_LARGE_FILE", 500)
        self.scan_dirs: List[str] = cfg.get(
            "REPO_ANALYZER_SCAN_DIRS", [".", "utils", "api", "agents"]
        )
        self._root = cfg.get("REPO_ANALYZER_ROOT", os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        ))
        self._seen_findings: set = set()  # in-memory dedup (volatile)
        self._dynamic_tasks_created: int = 0  # running total across all runs

        # Persistent finding history
        history_path = cfg.get("REPO_ANALYZER_HISTORY_PATH",
                               os.path.join("state", "finding_history.json"))
        self._history = FindingHistory(path=history_path)

        # Repository index for risk scoring
        index_path = cfg.get("REPO_ANALYZER_INDEX_PATH",
                             os.path.join(self._root, "repo_index.json"))
        self._index = RepoIndex(root=self._root, index_path=index_path)

    # ── Observability ────────────────────────────────────────────────────
    @property
    def dynamic_tasks_created(self) -> int:
        """Return the number of tasks dynamically created so far."""
        return self._dynamic_tasks_created

    # ── Public API ───────────────────────────────────────────────────────
    def analyze(self) -> List[Finding]:
        """
        Scan the repo and return a list of findings (deduped).
        Returns at most max_findings unique findings.
        """
        if not self.enabled:
            return []

        findings = self._scan()

        # De-dup against persistent history AND in-memory set
        new_findings: List[Finding] = []
        for f in findings:
            # Check persistent history first
            if self._history.has_seen(f.category, f.filepath, f.detail):
                continue
            # Check volatile in-memory dedup (exact match)
            key = (f.category, f.filepath, f.detail)
            if key in self._seen_findings:
                continue
            self._seen_findings.add(key)
            # Record in persistent history
            self._history.record(f.category, f.filepath, f.detail)
            new_findings.append(f)

        # Apply cap
        result = new_findings[:self.max_findings]

        # Persist history after collection
        if result:
            self._history.save()
            self._dynamic_tasks_created += len(result)

        return result

    def analyze_with_risk_score(self) -> List[tuple[Finding, int]]:
        """
        Analyze and score each finding by file risk.
        Returns list of (Finding, risk_score) tuples, sorted by risk descending.
        """
        findings = self.analyze()

        # Ensure index is loaded or built
        if not self._index.files:
            if not self._index.load():
                self._index.build()

        scored = []
        for finding in findings:
            risk = self._index.file_risk(finding.filepath)
            scored.append((finding, risk))

        # Sort by risk descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ── Scanning ─────────────────────────────────────────────────────────
    def _scan(self) -> List[Finding]:
        """Run all scanners and return findings (before dedup)."""
        findings: List[Finding] = []
        py_files = self._collect_py_files()

        for fpath in py_files:
            rel = os.path.relpath(fpath, self._root)
            findings.extend(self._scan_todos(fpath, rel))
            findings.extend(self._scan_large_file(fpath, rel))
            findings.extend(self._scan_missing_docstrings(fpath, rel))

        findings.extend(self._scan_missing_tests(py_files))
        return findings

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
        """Scan for TODO/FIXME/HACK/XXX comments."""
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
        """Scan for files exceeding the line count threshold."""
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                count = sum(1 for _ in fh)
            if count > self.large_file:
                return [Finding("large_file", rel, f"{count} lines")]
        except OSError:
            pass
        return []

    def _scan_missing_docstrings(self, fpath: str, rel: str) -> List[Finding]:
        """Scan for public functions without docstrings."""
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
        """Scan for source modules lacking corresponding test files."""
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
                    f"no test_{bname[:-3]} found for {bname}"
                ))
        return findings
