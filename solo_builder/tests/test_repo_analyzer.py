"""Tests for agents/repo_analyzer.py"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.repo_analyzer import Finding, RepoAnalyzer


class TestFinding(unittest.TestCase):
    """Test Finding class."""

    def test_finding_init(self):
        f = Finding("todo", "utils/foo.py", "L1 TODO: fix")
        self.assertEqual(f.category, "todo")
        self.assertEqual(f.filepath, "utils/foo.py")
        self.assertEqual(f.detail, "L1 TODO: fix")

    def test_finding_repr(self):
        f = Finding("todo", "utils/foo.py", "L1 TODO: fix")
        repr_str = repr(f)
        self.assertIn("todo", repr_str)
        self.assertIn("utils/foo.py", repr_str)

    def test_finding_to_dict(self):
        f = Finding("todo", "utils/foo.py", "L1 TODO: fix")
        d = f.to_dict()
        self.assertEqual(d["category"], "todo")
        self.assertEqual(d["filepath"], "utils/foo.py")
        self.assertEqual(d["detail"], "L1 TODO: fix")


class TestRepoAnalyzerBasics(unittest.TestCase):
    """Test RepoAnalyzer initialization and basic operations."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_with_defaults(self):
        analyzer = RepoAnalyzer()
        self.assertTrue(analyzer.enabled)
        self.assertEqual(analyzer.max_findings, 20)
        self.assertEqual(analyzer.large_file, 500)
        self.assertEqual(analyzer.dynamic_tasks_created, 0)

    def test_init_with_settings(self):
        settings = {
            "REPO_ANALYZER_ENABLED": False,
            "REPO_ANALYZER_MAX_FINDINGS": 10,
            "REPO_ANALYZER_LARGE_FILE": 300,
            "REPO_ANALYZER_ROOT": self.temp_dir,
        }
        analyzer = RepoAnalyzer(settings=settings)
        self.assertFalse(analyzer.enabled)
        self.assertEqual(analyzer.max_findings, 10)
        self.assertEqual(analyzer.large_file, 300)

    def test_analyze_returns_empty_when_disabled(self):
        settings = {"REPO_ANALYZER_ENABLED": False, "REPO_ANALYZER_ROOT": self.temp_dir}
        analyzer = RepoAnalyzer(settings=settings)
        findings = analyzer.analyze()
        self.assertEqual(findings, [])

    def test_analyze_returns_list_of_findings(self):
        # Create a test file with a TODO
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix this\ncode\n")

        settings = {"REPO_ANALYZER_ROOT": self.temp_dir}
        analyzer = RepoAnalyzer(settings=settings)
        findings = analyzer.analyze()

        self.assertIsInstance(findings, list)
        if findings:  # May find the TODO
            self.assertIsInstance(findings[0], Finding)

    def test_dynamic_tasks_created_increments(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix\n")

        settings = {"REPO_ANALYZER_ROOT": self.temp_dir}
        analyzer = RepoAnalyzer(settings=settings)

        self.assertEqual(analyzer.dynamic_tasks_created, 0)
        findings = analyzer.analyze()
        if findings:
            self.assertGreater(analyzer.dynamic_tasks_created, 0)


class TestRepoAnalyzerScanners(unittest.TestCase):
    """Test individual scanner methods."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.settings = {"REPO_ANALYZER_ROOT": self.temp_dir}
        self.analyzer = RepoAnalyzer(settings=self.settings)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_todos_finds_todo(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix this\n")

        findings = self.analyzer._scan_todos(test_file, "test.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "todo")
        self.assertIn("TODO", findings[0].detail)

    def test_scan_todos_finds_fixme(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# FIXME: broken\n")

        findings = self.analyzer._scan_todos(test_file, "test.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].detail.count("FIXME"), 1)

    def test_scan_todos_finds_hack_and_xxx(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# HACK: quick fix\n# XXX: weird\n")

        findings = self.analyzer._scan_todos(test_file, "test.py")
        self.assertEqual(len(findings), 2)

    def test_scan_todos_includes_line_numbers(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("code\n# TODO: fix\nmore\n")

        findings = self.analyzer._scan_todos(test_file, "test.py")
        self.assertEqual(len(findings), 1)
        self.assertIn("L2", findings[0].detail)

    def test_scan_large_file_detects_over_threshold(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            for i in range(600):
                f.write(f"line {i}\n")

        self.analyzer.large_file = 500
        findings = self.analyzer._scan_large_file(test_file, "test.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "large_file")
        self.assertIn("600", findings[0].detail)

    def test_scan_large_file_ignores_under_threshold(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            for i in range(100):
                f.write(f"line {i}\n")

        self.analyzer.large_file = 500
        findings = self.analyzer._scan_large_file(test_file, "test.py")
        self.assertEqual(len(findings), 0)

    def test_scan_missing_docstrings_finds_undocumented(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("def foo():\n    pass\n")

        findings = self.analyzer._scan_missing_docstrings(test_file, "test.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "missing_docstring")
        self.assertIn("foo", findings[0].detail)

    def test_scan_missing_docstrings_ignores_private_functions(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("def _private():\n    pass\n")

        findings = self.analyzer._scan_missing_docstrings(test_file, "test.py")
        self.assertEqual(len(findings), 0)

    def test_scan_missing_docstrings_ignores_documented(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write('def foo():\n    """Documented."""\n    pass\n')

        findings = self.analyzer._scan_missing_docstrings(test_file, "test.py")
        self.assertEqual(len(findings), 0)

    def test_scan_missing_tests_detects_no_test_file(self):
        source_file = os.path.join(self.temp_dir, "mymodule.py")
        with open(source_file, "w") as f:
            f.write("def foo(): pass\n")

        py_files = [source_file]
        findings = self.analyzer._scan_missing_tests(py_files)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "missing_test")
        self.assertIn("mymodule.py", findings[0].detail)

    def test_scan_missing_tests_ignores_existing_test_files(self):
        source_file = os.path.join(self.temp_dir, "mymodule.py")
        test_file = os.path.join(self.temp_dir, "test_mymodule.py")
        with open(source_file, "w") as f:
            f.write("def foo(): pass\n")
        with open(test_file, "w") as f:
            f.write("def test_foo(): pass\n")

        py_files = [source_file, test_file]
        findings = self.analyzer._scan_missing_tests(py_files)
        # Should not report missing_test for mymodule.py
        self.assertEqual(len(findings), 0)

    def test_scan_missing_tests_ignores_special_files(self):
        init_file = os.path.join(self.temp_dir, "__init__.py")
        setup_file = os.path.join(self.temp_dir, "setup.py")
        with open(init_file, "w") as f:
            f.write("")
        with open(setup_file, "w") as f:
            f.write("")

        py_files = [init_file, setup_file]
        findings = self.analyzer._scan_missing_tests(py_files)
        self.assertEqual(len(findings), 0)


class TestRepoAnalyzerDedup(unittest.TestCase):
    """Test deduplication behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.settings = {"REPO_ANALYZER_ROOT": self.temp_dir}
        self.analyzer = RepoAnalyzer(settings=self.settings)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_dedupes_findings(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix\n")

        # First call
        findings1 = self.analyzer.analyze()
        first_count = len(findings1)

        # Second call should find nothing (deduped)
        findings2 = self.analyzer.analyze()
        self.assertEqual(len(findings2), 0)

    def test_analyze_persists_findings_to_history(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix\n")

        analyzer1 = RepoAnalyzer(settings=self.settings)
        findings1 = analyzer1.analyze()

        # New analyzer instance should still see deduped findings
        analyzer2 = RepoAnalyzer(settings=self.settings)
        findings2 = analyzer2.analyze()
        self.assertEqual(len(findings2), 0)

    def test_analyze_normalizes_line_numbers_for_dedup(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        # Write the TODO at a specific line
        with open(test_file, "w") as f:
            f.write("# TODO: fix this\n")

        analyzer = RepoAnalyzer(settings=self.settings)
        findings1 = analyzer.analyze()

        # Modify the file to move the TODO
        with open(test_file, "w") as f:
            f.write("code\n# TODO: fix this\n")

        # Should still be deduped (line number differs but normalized away)
        findings2 = analyzer.analyze()
        self.assertEqual(len(findings2), 0)


class TestRepoAnalyzerRiskScoring(unittest.TestCase):
    """Test analyze_with_risk_score method."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.settings = {"REPO_ANALYZER_ROOT": self.temp_dir}
        self.analyzer = RepoAnalyzer(settings=self.settings)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_with_risk_score_returns_tuples(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix\n")

        results = self.analyzer.analyze_with_risk_score()
        self.assertIsInstance(results, list)
        if results:
            finding, risk = results[0]
            self.assertIsInstance(finding, Finding)
            self.assertIsInstance(risk, int)

    def test_analyze_with_risk_score_sorts_by_risk_descending(self):
        # Create two files with different TODO densities
        test_file1 = os.path.join(self.temp_dir, "messy.py")
        test_file2 = os.path.join(self.temp_dir, "clean.py")

        # Clear existing findings
        self.analyzer._history._entries.clear()

        with open(test_file1, "w") as f:
            for _ in range(5):
                f.write("# TODO: fix\n")
            f.write("code\n" * 100)

        with open(test_file2, "w") as f:
            f.write("# TODO: fix\n")
            f.write("code\n" * 100)

        results = self.analyzer.analyze_with_risk_score()

        if len(results) >= 2:
            # First result should have higher or equal risk
            risk1 = results[0][1]
            risk2 = results[1][1]
            self.assertGreaterEqual(risk1, risk2)


class TestRepoAnalyzerIntegration(unittest.TestCase):
    """Integration tests."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_analysis_workflow(self):
        # Create a small project structure
        os.makedirs(os.path.join(self.temp_dir, "utils"))
        os.makedirs(os.path.join(self.temp_dir, "__pycache__"), exist_ok=True)

        with open(os.path.join(self.temp_dir, "utils", "foo.py"), "w") as f:
            f.write("# TODO: refactor\ndef bar():\n    pass\n")

        with open(os.path.join(self.temp_dir, "api.py"), "w") as f:
            f.write("code\n" * 600)

        settings = {
            "REPO_ANALYZER_ROOT": self.temp_dir,
            "REPO_ANALYZER_SCAN_DIRS": [".", "utils"],
        }
        analyzer = RepoAnalyzer(settings=settings)
        findings = analyzer.analyze()

        # Should find TODO and large_file
        categories = [f.category for f in findings]
        self.assertIn("todo", categories)
        self.assertIn("large_file", categories)

    def test_collect_py_files_respects_scan_dirs(self):
        os.makedirs(os.path.join(self.temp_dir, "utils"))
        os.makedirs(os.path.join(self.temp_dir, "api"))
        os.makedirs(os.path.join(self.temp_dir, "excluded"))

        with open(os.path.join(self.temp_dir, "root.py"), "w") as f:
            f.write("code\n")
        with open(os.path.join(self.temp_dir, "utils", "util.py"), "w") as f:
            f.write("code\n")
        with open(os.path.join(self.temp_dir, "excluded", "skip.py"), "w") as f:
            f.write("code\n")

        settings = {
            "REPO_ANALYZER_ROOT": self.temp_dir,
            "REPO_ANALYZER_SCAN_DIRS": ["utils"],
        }
        analyzer = RepoAnalyzer(settings=settings)
        py_files = analyzer._collect_py_files()

        # Normalize paths to forward slashes for cross-platform testing
        paths = [os.path.relpath(f, self.temp_dir).replace("\\", "/") for f in py_files]
        self.assertIn("utils/util.py", paths)
        self.assertNotIn("excluded/skip.py", paths)


if __name__ == "__main__":
    unittest.main()
