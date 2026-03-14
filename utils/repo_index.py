"""
utils/repo_index.py
RepoIndex — builds and loads a structural index of the repository for
risk-aware planning.

Metrics per Python file:
    file_size      — line count
    todo_density   — TODO/FIXME count per 100 lines
    code_ownership — number of distinct git authors (or 1 if git unavailable)
    dep_depth      — number of local imports (intra-project dependency depth)

The index is persisted to ``repo_index.json`` so the Planner can load it
without re-scanning every step.
"""

import ast
import json
import os
import re
import subprocess
from typing import Any, Dict, List


# Directories to skip during scanning
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
              "env", ".eggs", "snapshots", "state"}

_TODO_RE = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


class RepoIndex:
    """
    Builds and queries a per-file repository structure index.

    Usage:
        idx = RepoIndex(root="/path/to/repo")
        idx.build()            # scan and compute metrics
        idx.save()             # write repo_index.json
        idx.load()             # read from disk (fast path)
        score = idx.file_risk("utils/helper_functions.py")
    """

    def __init__(self, root: str | None = None, index_path: str | None = None) -> None:
        self.root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.index_path = index_path or os.path.join(self.root, "repo_index.json")
        self.files: Dict[str, Dict[str, Any]] = {}

    # ── Build ────────────────────────────────────────────────────────────
    def build(self) -> "RepoIndex":
        """Scan the repository and compute metrics for every Python file."""
        py_files = self._collect_py_files()
        git_available = self._git_available()

        for fpath in py_files:
            rel = os.path.relpath(fpath, self.root)
            entry: Dict[str, Any] = {}

            lines = self._count_lines(fpath)
            entry["file_size"] = lines

            todo_count = self._count_todos(fpath)
            entry["todo_density"] = round(todo_count / max(lines, 1) * 100, 2)

            if git_available:
                entry["code_ownership"] = self._count_authors(fpath)
            else:
                entry["code_ownership"] = 1

            entry["dep_depth"] = self._count_local_imports(fpath)

            self.files[rel] = entry

        return self

    # ── Persistence ──────────────────────────────────────────────────────
    def save(self) -> str:
        """Write the index to repo_index.json. Returns the path."""
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.files, f, indent=2, sort_keys=True)
        return self.index_path

    def load(self) -> bool:
        """Load repo_index.json from disk. Returns True on success."""
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.files = json.load(f)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    # ── Query ────────────────────────────────────────────────────────────
    def file_risk(self, filepath: str) -> int:
        """
        Compute a risk bonus for a file based on repo structure metrics.

        Scoring:
            +10 per 100 lines over 200       (large files are riskier)
            +15 per TODO-density point        (debt-heavy files)
            +5  per additional author         (shared ownership = coordination risk)
            +8  per local import              (high coupling = ripple risk)
        """
        entry = self.files.get(filepath, {})
        if not entry:
            return 0

        risk = 0

        # File size bonus: +10 per 100 lines above 200
        size = entry.get("file_size", 0)
        if size > 200:
            risk += ((size - 200) // 100) * 10

        # TODO density bonus: +15 per density point
        density = entry.get("todo_density", 0.0)
        risk += int(density * 15)

        # Code ownership bonus: +5 per author beyond the first
        owners = entry.get("code_ownership", 1)
        if owners > 1:
            risk += (owners - 1) * 5

        # Dependency depth bonus: +8 per local import
        deps = entry.get("dep_depth", 0)
        risk += deps * 8

        return risk

    def subtask_risk(self, description: str) -> int:
        """
        Compute aggregate risk bonus for a subtask by matching file
        references in its description against the index.
        """
        if not self.files or not description:
            return 0

        total = 0
        for filepath in self.files:
            # Match if the filepath (or its basename) appears in the description
            basename = os.path.basename(filepath)
            if filepath in description or basename in description:
                total += self.file_risk(filepath)

        return total

    # ── Private scanners ─────────────────────────────────────────────────
    def _collect_py_files(self) -> List[str]:
        result: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                if fname.endswith(".py"):
                    result.append(os.path.join(dirpath, fname))
        return result

    @staticmethod
    def _count_lines(fpath: str) -> int:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0

    @staticmethod
    def _count_todos(fpath: str) -> int:
        count = 0
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if _TODO_RE.search(line):
                        count += 1
        except OSError:
            pass
        return count

    def _count_authors(self, fpath: str) -> int:
        try:
            r = subprocess.run(
                ["git", "log", "--format=%ae", "--", fpath],
                capture_output=True, text=True, timeout=10,
                cwd=self.root,
            )
            if r.returncode != 0:
                return 1
            authors = set(line.strip() for line in r.stdout.splitlines() if line.strip())
            return max(len(authors), 1)
        except Exception:
            return 1

    def _count_local_imports(self, fpath: str) -> int:
        """Count import statements that reference local project modules."""
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            tree = ast.parse(source, filename=fpath)
        except (OSError, SyntaxError):
            return 0

        # Collect top-level package names in the project
        project_packages = set()
        for item in os.listdir(self.root):
            item_path = os.path.join(self.root, item)
            if os.path.isdir(item_path) and os.path.exists(
                os.path.join(item_path, "__init__.py")
            ):
                project_packages.add(item)
            elif item.endswith(".py") and item != "__init__.py":
                project_packages.add(item[:-3])

        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in project_packages:
                        count += 1
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in project_packages:
                        count += 1
                elif node.level > 0:
                    # Relative import — always local
                    count += 1

        return count

    def _git_available(self) -> bool:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True, timeout=5, cwd=self.root,
            )
            return r.returncode == 0
        except Exception:
            return False
