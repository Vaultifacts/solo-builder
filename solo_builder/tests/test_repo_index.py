"""Tests for utils/repo_index.py"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.repo_index import RepoIndex


class TestRepoIndexBasics(unittest.TestCase):
    """Test RepoIndex initialization and basic operations."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "repo_index.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_instance(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        self.assertEqual(idx.root, self.temp_dir)
        self.assertEqual(idx.index_path, self.index_path)
        self.assertEqual(len(idx.files), 0)

    def test_init_defaults_to_parent_dir(self):
        idx = RepoIndex()
        # Should default to parent of utils/repo_index.py
        self.assertTrue(os.path.isdir(idx.root))

    def test_build_returns_self(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        result = idx.build()
        self.assertIs(result, idx)

    def test_save_creates_file(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["test.py"] = {"file_size": 100, "todo_density": 0.0}
        path = idx.save()
        self.assertTrue(os.path.exists(path))
        self.assertEqual(path, self.index_path)

    def test_load_reads_saved_index(self):
        # Write an index
        idx1 = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx1.files["test.py"] = {"file_size": 100, "todo_density": 0.0}
        idx1.save()

        # Load it
        idx2 = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        result = idx2.load()
        self.assertTrue(result)
        self.assertIn("test.py", idx2.files)
        self.assertEqual(idx2.files["test.py"]["file_size"], 100)

    def test_load_returns_false_when_file_not_found(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        result = idx.load()
        self.assertFalse(result)

    def test_load_returns_false_for_corrupt_json(self):
        with open(self.index_path, "w") as f:
            f.write("{invalid")
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        result = idx.load()
        self.assertFalse(result)


class TestRepoIndexScanners(unittest.TestCase):
    """Test the individual scanner methods."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "repo_index.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_count_lines_counts_correctly(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("line 1\nline 2\nline 3\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_lines(test_file)
        self.assertEqual(count, 3)

    def test_count_lines_returns_0_for_missing_file(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_lines("/nonexistent/file.py")
        self.assertEqual(count, 0)

    def test_count_todos_finds_todos(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix this\ncode\n# FIXME: and this\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_todos(test_file)
        self.assertEqual(count, 2)

    def test_count_todos_finds_hack_and_xxx(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# HACK: quick fix\n# XXX: weird\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_todos(test_file)
        self.assertEqual(count, 2)

    def test_count_todos_case_insensitive(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# todo: lower\n# TODO: upper\n# ToDo: mixed\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_todos(test_file)
        self.assertEqual(count, 3)

    def test_count_todos_ignores_non_comment_todos(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write('s = "TODO: not a comment"\n# TODO: this is\n')

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_todos(test_file)
        self.assertEqual(count, 1)

    def test_count_local_imports_simple(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        os.makedirs(os.path.join(self.temp_dir, "mymodule"), exist_ok=True)
        with open(os.path.join(self.temp_dir, "mymodule", "__init__.py"), "w") as f:
            f.write("")

        with open(test_file, "w") as f:
            f.write("import mymodule\nfrom mymodule import foo\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_local_imports(test_file)
        self.assertEqual(count, 2)

    def test_count_local_imports_relative(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("from . import foo\nfrom .. import bar\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_local_imports(test_file)
        self.assertEqual(count, 2)

    def test_count_local_imports_returns_0_on_syntax_error(self):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("this is not valid python ::::")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        count = idx._count_local_imports(test_file)
        self.assertEqual(count, 0)


class TestRepoIndexRiskScoring(unittest.TestCase):
    """Test file risk scoring logic."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "repo_index.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_risk_returns_0_for_unknown_file(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        risk = idx.file_risk("unknown.py")
        self.assertEqual(risk, 0)

    def test_file_risk_scores_large_files(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["large.py"] = {
            "file_size": 400,
            "todo_density": 0.0,
            "code_ownership": 1,
            "dep_depth": 0,
        }
        risk = idx.file_risk("large.py")
        # +10 per 100 lines over 200: (400-200)/100 * 10 = 20
        self.assertEqual(risk, 20)

    def test_file_risk_scores_todo_density(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["messy.py"] = {
            "file_size": 100,
            "todo_density": 5.0,
            "code_ownership": 1,
            "dep_depth": 0,
        }
        risk = idx.file_risk("messy.py")
        # +15 per density point: 5 * 15 = 75
        self.assertEqual(risk, 75)

    def test_file_risk_scores_code_ownership(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["shared.py"] = {
            "file_size": 100,
            "todo_density": 0.0,
            "code_ownership": 4,
            "dep_depth": 0,
        }
        risk = idx.file_risk("shared.py")
        # +5 per author beyond first: (4-1) * 5 = 15
        self.assertEqual(risk, 15)

    def test_file_risk_scores_dep_depth(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["coupled.py"] = {
            "file_size": 100,
            "todo_density": 0.0,
            "code_ownership": 1,
            "dep_depth": 3,
        }
        risk = idx.file_risk("coupled.py")
        # +8 per local import: 3 * 8 = 24
        self.assertEqual(risk, 24)

    def test_file_risk_combines_all_factors(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["complex.py"] = {
            "file_size": 500,  # (500-200)/100 * 10 = 30
            "todo_density": 2.0,  # 2 * 15 = 30
            "code_ownership": 3,  # (3-1) * 5 = 10
            "dep_depth": 2,  # 2 * 8 = 16
        }
        risk = idx.file_risk("complex.py")
        self.assertEqual(risk, 30 + 30 + 10 + 16)

    def test_subtask_risk_returns_0_for_empty_description(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        risk = idx.subtask_risk("")
        self.assertEqual(risk, 0)

    def test_subtask_risk_matches_filepath_in_description(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["utils/foo.py"] = {
            "file_size": 300,  # > 200 so it gets risk score
            "todo_density": 0.0,
            "code_ownership": 1,
            "dep_depth": 0,
        }
        risk = idx.subtask_risk("Refactor utils/foo.py")
        self.assertGreater(risk, 0)

    def test_subtask_risk_matches_basename_in_description(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["utils/foo.py"] = {
            "file_size": 300,  # > 200 so it gets risk score
            "todo_density": 0.0,
            "code_ownership": 1,
            "dep_depth": 0,
        }
        # Just mentioning the basename should match
        risk = idx.subtask_risk("Fix issues in foo.py")
        self.assertGreater(risk, 0)

    def test_subtask_risk_aggregates_multiple_files(self):
        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.files["foo.py"] = {
            "file_size": 100,
            "todo_density": 0.0,
            "code_ownership": 1,
            "dep_depth": 0,
        }
        idx.files["bar.py"] = {
            "file_size": 200,
            "todo_density": 0.0,
            "code_ownership": 1,
            "dep_depth": 0,
        }
        risk = idx.subtask_risk("Refactor foo.py and bar.py")
        # foo.py = 0, bar.py = 0 + (200-200)/100*10 = 0
        # Both files contribute but neither is > 200 lines
        self.assertEqual(risk, 0)


class TestRepoIndexIntegration(unittest.TestCase):
    """Integration tests with actual files."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "repo_index.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_and_save_roundtrip(self):
        # Create a test Python file
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("# TODO: fix\ncode\n")

        idx1 = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx1.build()
        idx1.save()

        # Load it back
        idx2 = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx2.load()

        self.assertIn("test.py", idx2.files)
        self.assertEqual(idx2.files["test.py"]["file_size"], 2)
        self.assertGreater(idx2.files["test.py"]["todo_density"], 0)

    def test_build_skips_ignored_directories(self):
        # Create files in various directories
        os.makedirs(os.path.join(self.temp_dir, "api"))
        os.makedirs(os.path.join(self.temp_dir, "__pycache__"))

        with open(os.path.join(self.temp_dir, "api", "test.py"), "w") as f:
            f.write("code\n")
        with open(os.path.join(self.temp_dir, "__pycache__", "test.py"), "w") as f:
            f.write("code\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.build()

        # api/test.py should be included
        self.assertTrue(any("api" in f for f in idx.files))
        # __pycache__/test.py should NOT be included
        self.assertFalse(any("__pycache__" in f for f in idx.files))

    @patch("utils.repo_index.RepoIndex._git_available", return_value=False)
    def test_build_defaults_code_ownership_when_git_unavailable(self, mock_git):
        test_file = os.path.join(self.temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("code\n")

        idx = RepoIndex(root=self.temp_dir, index_path=self.index_path)
        idx.build()

        self.assertEqual(idx.files["test.py"]["code_ownership"], 1)


if __name__ == "__main__":
    unittest.main()
