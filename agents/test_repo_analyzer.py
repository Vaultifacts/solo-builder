#!/usr/bin/env python3
"""
Tests for agents/repo_analyzer.py — RepoAnalyzer agent.

Run:
    python agents/test_repo_analyzer.py
    python -m pytest agents/test_repo_analyzer.py -v
"""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.repo_analyzer import RepoAnalyzer, Finding
from utils.helper_functions import validate_dag


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content))


def _make_dag() -> dict:
    """Minimal valid DAG for testing."""
    return {
        "Task 0": {
            "status": "Pending",
            "depends_on": [],
            "branches": {
                "Branch A": {
                    "status": "Pending",
                    "subtasks": {
                        "A1": {
                            "status": "Pending",
                            "shadow": "Pending",
                            "last_update": 0,
                            "description": "Seed subtask",
                            "output": "",
                        }
                    },
                }
            },
        }
    }


def _ra_cfg(tmp: str, **overrides) -> dict:
    """Standard test config for RepoAnalyzer with safety defaults."""
    cfg = {
        "REPO_ANALYZER_ROOT": tmp,
        "REPO_ANALYZER_SCAN_DIRS": ["."],
        "REPO_ANALYZER_INTERVAL": 1,
        "REPO_ANALYZER_COOLDOWN_STEPS": 1,
        "REPO_ANALYZER_HISTORY_PATH": os.path.join(tmp, "finding_history.json"),
        "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 20,
        "MAX_DYNAMIC_TASKS_TOTAL": 50,
    }
    cfg.update(overrides)
    return cfg


class TestFinding(unittest.TestCase):
    def test_repr(self):
        f = Finding("todo", "foo.py", "L10 TODO: fix this")
        self.assertIn("todo", repr(f))
        self.assertIn("foo.py", repr(f))


class TestShouldRun(unittest.TestCase):
    def test_respects_interval(self):
        ra = RepoAnalyzer({
            "REPO_ANALYZER_INTERVAL": 5,
            "REPO_ANALYZER_COOLDOWN_STEPS": 5,
        })
        self.assertTrue(ra.should_run(step=5))
        ra._last_run_step = 5
        self.assertFalse(ra.should_run(step=6))
        self.assertTrue(ra.should_run(step=10))

    def test_disabled(self):
        ra = RepoAnalyzer({"REPO_ANALYZER_ENABLED": False})
        self.assertFalse(ra.should_run(step=100))


class TestScanTodos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write(os.path.join(self.tmp, "sample.py"), """\
            import os
            # TODO: refactor this later
            x = 1
            # FIXME: broken edge case
            y = 2
        """)
        self.ra = RepoAnalyzer(_ra_cfg(self.tmp))

    def test_finds_todos(self):
        findings = self.ra._scan(step=1)
        todo_findings = [f for f in findings if f.category == "todo"]
        self.assertGreaterEqual(len(todo_findings), 2)
        details = [f.detail for f in todo_findings]
        self.assertTrue(any("refactor" in d for d in details))
        self.assertTrue(any("broken" in d for d in details))


class TestScanLargeFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Create a file with 600 lines
        big = "\n".join(f"line_{i} = {i}" for i in range(600))
        with open(os.path.join(self.tmp, "big.py"), "w") as f:
            f.write(big)
        # Create a small file
        with open(os.path.join(self.tmp, "small.py"), "w") as f:
            f.write("x = 1\n")
        self.ra = RepoAnalyzer(_ra_cfg(self.tmp, REPO_ANALYZER_LARGE_FILE=500))

    def test_flags_large_file(self):
        findings = self.ra._scan(step=1)
        large = [f for f in findings if f.category == "large_file"]
        self.assertEqual(len(large), 1)
        self.assertIn("600", large[0].detail)


class TestScanMissingDocstrings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write(os.path.join(self.tmp, "funcs.py"), """\
            def public_func():
                pass

            def documented_func():
                \"\"\"Has a docstring.\"\"\"
                pass

            def _private():
                pass
        """)
        self.ra = RepoAnalyzer(_ra_cfg(self.tmp))

    def test_flags_undocumented_public(self):
        findings = self.ra._scan(step=1)
        docstring = [f for f in findings if f.category == "missing_docstring"]
        names = [f.detail for f in docstring]
        self.assertTrue(any("public_func" in n for n in names))
        self.assertFalse(any("documented_func" in n for n in names))
        self.assertFalse(any("_private" in n for n in names))


class TestScanMissingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write(os.path.join(self.tmp, "module_a.py"), "x = 1\n")
        _write(os.path.join(self.tmp, "module_b.py"), "y = 2\n")
        _write(os.path.join(self.tmp, "test_module_a.py"),
               "import unittest\n")
        self.ra = RepoAnalyzer(_ra_cfg(self.tmp))

    def test_flags_untested_module(self):
        findings = self.ra._scan(step=1)
        missing = [f for f in findings if f.category == "missing_test"]
        paths = [f.filepath for f in missing]
        self.assertTrue(any("module_b" in p for p in paths))
        self.assertFalse(any("module_a" in p for p in paths))


class TestDedup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write(os.path.join(self.tmp, "dup.py"), """\
            # TODO: same thing twice
        """)
        self.ra = RepoAnalyzer(_ra_cfg(self.tmp))

    def test_dedup_across_runs(self):
        f1 = self.ra._scan(step=1)
        f2 = self.ra._scan(step=2)
        self.assertGreater(len(f1), 0)
        self.assertEqual(len(f2), 0, "Second scan should return 0 (all deduped)")


class TestInjectTasks(unittest.TestCase):
    def test_injects_into_dag(self):
        tmp = tempfile.mkdtemp()
        _write(os.path.join(tmp, "debt.py"), """\
            # TODO: fix memory leak
            # FIXME: handle timeout
        """)
        ra = RepoAnalyzer(_ra_cfg(tmp))
        dag = _make_dag()
        memory = {"Branch A": []}
        alerts: list = []

        added = ra.analyze(dag, memory, step=1, alerts=alerts)

        self.assertGreater(added, 0)
        self.assertIn("Task 1", dag)
        # Validate DAG still passes
        warnings = validate_dag(dag)
        self.assertEqual(warnings, [], f"DAG validation failed: {warnings}")

    def test_dag_dependency_wired(self):
        tmp = tempfile.mkdtemp()
        _write(os.path.join(tmp, "todo.py"), "# TODO: wire test\n")
        ra = RepoAnalyzer(_ra_cfg(tmp))
        dag = _make_dag()
        memory = {"Branch A": []}
        ra.analyze(dag, memory, step=1, alerts=[])

        new_task = dag["Task 1"]
        self.assertEqual(new_task["depends_on"], ["Task 0"])

    def test_memory_store_updated(self):
        tmp = tempfile.mkdtemp()
        _write(os.path.join(tmp, "mem.py"), "# TODO: memory test\n")
        ra = RepoAnalyzer(_ra_cfg(tmp))
        dag = _make_dag()
        memory = {"Branch A": []}
        ra.analyze(dag, memory, step=1, alerts=[])

        # New branch memory should be initialised
        self.assertIn("Branch B", memory)
        self.assertGreater(len(memory["Branch B"]), 0)

    def test_no_inject_when_disabled(self):
        ra = RepoAnalyzer({"REPO_ANALYZER_ENABLED": False})
        dag = _make_dag()
        added = ra.analyze(dag, {}, step=1, alerts=[])
        self.assertEqual(added, 0)
        self.assertEqual(len(dag), 1)


class TestMaxFindings(unittest.TestCase):
    def test_caps_findings(self):
        tmp = tempfile.mkdtemp()
        # Generate 30 TODOs
        lines = "\n".join(f"# TODO: item {i}" for i in range(30))
        _write(os.path.join(tmp, "many.py"), lines)
        ra = RepoAnalyzer(_ra_cfg(tmp, REPO_ANALYZER_MAX_FINDINGS=5))
        dag = _make_dag()
        added = ra.analyze(dag, {"Branch A": []}, step=1, alerts=[])
        # Should be capped at 5 subtasks
        self.assertLessEqual(added, 5)


if __name__ == "__main__":
    unittest.main()
