#!/usr/bin/env python3
"""
Tests for utils/repo_index.py — RepoIndex structure and Planner integration.

Run:
    python utils/test_repo_index.py
    python -m pytest utils/test_repo_index.py -v
"""

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.repo_index import RepoIndex


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content))


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write(os.path.join(self.tmp, "app.py"), "\n".join(
            [f"line_{i} = {i}" for i in range(300)]
        ))
        _write(os.path.join(self.tmp, "small.py"), "x = 1\n")
        _write(os.path.join(self.tmp, "debt.py"), textwrap.dedent("""\
            # TODO: fix this
            # FIXME: and this
            # TODO: also this
            x = 1
            y = 2
        """))

    def test_builds_index(self):
        idx = RepoIndex(root=self.tmp)
        idx.build()
        self.assertIn("app.py", idx.files)
        self.assertIn("small.py", idx.files)
        self.assertIn("debt.py", idx.files)

    def test_file_size(self):
        idx = RepoIndex(root=self.tmp)
        idx.build()
        self.assertEqual(idx.files["app.py"]["file_size"], 300)
        self.assertEqual(idx.files["small.py"]["file_size"], 1)

    def test_todo_density(self):
        idx = RepoIndex(root=self.tmp)
        idx.build()
        density = idx.files["debt.py"]["todo_density"]
        # 3 TODOs in 5 lines = 60.0 density
        self.assertAlmostEqual(density, 60.0, places=0)

    def test_zero_todo_density(self):
        idx = RepoIndex(root=self.tmp)
        idx.build()
        self.assertEqual(idx.files["small.py"]["todo_density"], 0.0)

    def test_code_ownership_default(self):
        # Non-git repo should default to 1
        idx = RepoIndex(root=self.tmp)
        idx.build()
        self.assertEqual(idx.files["app.py"]["code_ownership"], 1)

    def test_dep_depth(self):
        # Create a package with imports
        pkg = os.path.join(self.tmp, "mypackage")
        _write(os.path.join(pkg, "__init__.py"), "")
        _write(os.path.join(pkg, "core.py"), "x = 1\n")
        _write(os.path.join(self.tmp, "importer.py"),
               "import mypackage\nfrom mypackage import core\n")
        idx = RepoIndex(root=self.tmp)
        idx.build()
        self.assertGreaterEqual(idx.files["importer.py"]["dep_depth"], 2)

    def test_skips_hidden_dirs(self):
        _write(os.path.join(self.tmp, ".git", "config.py"), "x = 1\n")
        _write(os.path.join(self.tmp, "__pycache__", "cached.py"), "y = 2\n")
        idx = RepoIndex(root=self.tmp)
        idx.build()
        for rel in idx.files:
            self.assertNotIn(".git", rel)
            self.assertNotIn("__pycache__", rel)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write(os.path.join(self.tmp, "module.py"), "x = 1\n")

    def test_save_and_load(self):
        idx = RepoIndex(root=self.tmp)
        idx.build()
        path = idx.save()
        self.assertTrue(os.path.exists(path))

        idx2 = RepoIndex(root=self.tmp)
        self.assertTrue(idx2.load())
        self.assertEqual(idx2.files, idx.files)

    def test_load_missing_file(self):
        idx = RepoIndex(root=self.tmp, index_path="/nonexistent/path.json")
        self.assertFalse(idx.load())

    def test_save_creates_valid_json(self):
        idx = RepoIndex(root=self.tmp)
        idx.build()
        idx.save()
        with open(idx.index_path) as f:
            data = json.load(f)
        self.assertIn("module.py", data)


class TestFileRisk(unittest.TestCase):
    def test_large_file_bonus(self):
        idx = RepoIndex()
        idx.files = {"big.py": {
            "file_size": 500, "todo_density": 0.0,
            "code_ownership": 1, "dep_depth": 0,
        }}
        risk = idx.file_risk("big.py")
        # (500-200)//100 * 10 = 30
        self.assertEqual(risk, 30)

    def test_todo_density_bonus(self):
        idx = RepoIndex()
        idx.files = {"debt.py": {
            "file_size": 100, "todo_density": 5.0,
            "code_ownership": 1, "dep_depth": 0,
        }}
        risk = idx.file_risk("debt.py")
        # 5.0 * 15 = 75
        self.assertEqual(risk, 75)

    def test_ownership_bonus(self):
        idx = RepoIndex()
        idx.files = {"shared.py": {
            "file_size": 100, "todo_density": 0.0,
            "code_ownership": 4, "dep_depth": 0,
        }}
        risk = idx.file_risk("shared.py")
        # (4-1) * 5 = 15
        self.assertEqual(risk, 15)

    def test_dep_depth_bonus(self):
        idx = RepoIndex()
        idx.files = {"coupled.py": {
            "file_size": 100, "todo_density": 0.0,
            "code_ownership": 1, "dep_depth": 5,
        }}
        risk = idx.file_risk("coupled.py")
        # 5 * 8 = 40
        self.assertEqual(risk, 40)

    def test_combined_risk(self):
        idx = RepoIndex()
        idx.files = {"risky.py": {
            "file_size": 600, "todo_density": 2.0,
            "code_ownership": 3, "dep_depth": 4,
        }}
        risk = idx.file_risk("risky.py")
        # size: (600-200)//100*10=40, todo: 2.0*15=30, owners: (3-1)*5=10, deps: 4*8=32
        self.assertEqual(risk, 40 + 30 + 10 + 32)

    def test_unknown_file_returns_zero(self):
        idx = RepoIndex()
        idx.files = {}
        self.assertEqual(idx.file_risk("nonexistent.py"), 0)

    def test_small_file_no_size_bonus(self):
        idx = RepoIndex()
        idx.files = {"tiny.py": {
            "file_size": 50, "todo_density": 0.0,
            "code_ownership": 1, "dep_depth": 0,
        }}
        self.assertEqual(idx.file_risk("tiny.py"), 0)


class TestSubtaskRisk(unittest.TestCase):
    def test_matches_filepath_in_description(self):
        idx = RepoIndex()
        idx.files = {"utils/helper.py": {
            "file_size": 400, "todo_density": 1.0,
            "code_ownership": 2, "dep_depth": 3,
        }}
        risk = idx.subtask_risk("Refactor utils/helper.py to reduce coupling")
        self.assertGreater(risk, 0)

    def test_matches_basename(self):
        idx = RepoIndex()
        idx.files = {"deep/nested/module.py": {
            "file_size": 300, "todo_density": 0.0,
            "code_ownership": 1, "dep_depth": 2,
        }}
        risk = idx.subtask_risk("Fix bug in module.py")
        self.assertGreater(risk, 0)

    def test_no_match_returns_zero(self):
        idx = RepoIndex()
        idx.files = {"utils/helper.py": {
            "file_size": 400, "todo_density": 1.0,
            "code_ownership": 1, "dep_depth": 0,
        }}
        risk = idx.subtask_risk("Design the login page layout")
        self.assertEqual(risk, 0)

    def test_empty_description_returns_zero(self):
        idx = RepoIndex()
        idx.files = {"app.py": {
            "file_size": 500, "todo_density": 0.0,
            "code_ownership": 1, "dep_depth": 0,
        }}
        self.assertEqual(idx.subtask_risk(""), 0)

    def test_empty_index_returns_zero(self):
        idx = RepoIndex()
        self.assertEqual(idx.subtask_risk("Anything"), 0)


class TestPlannerIntegration(unittest.TestCase):
    """Test that the Planner correctly uses repo index for risk scoring."""

    def _make_planner(self, repo_index=None):
        # Import inline to avoid circular issues at module level
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import solo_builder_cli as m
        return m.Planner(stall_threshold=5, repo_index=repo_index)

    def test_planner_without_index(self):
        planner = self._make_planner(repo_index=None)
        st_data = {"status": "Pending", "last_update": 0, "description": "Fix app.py"}
        risk = planner._risk(st_data, step=5)
        # Should work normally without repo bonus
        self.assertIsInstance(risk, int)

    def test_planner_with_index_boosts_risk(self):
        idx = RepoIndex()
        idx.files = {"app.py": {
            "file_size": 600, "todo_density": 3.0,
            "code_ownership": 2, "dep_depth": 4,
        }}

        planner_no_idx = self._make_planner(repo_index=None)
        planner_with_idx = self._make_planner(repo_index=idx)

        st_data = {
            "status": "Pending", "last_update": 0,
            "description": "Fix critical bug in app.py",
        }

        risk_without = planner_no_idx._risk(st_data, step=5)
        risk_with = planner_with_idx._risk(st_data, step=5)

        self.assertGreater(risk_with, risk_without)

    def test_planner_adjust_weights_repo(self):
        planner = self._make_planner()
        planner.adjust_weights("repo", 0.5)
        self.assertAlmostEqual(planner.w_repo, 1.5)
        planner.adjust_weights("repo", -2.0)
        self.assertAlmostEqual(planner.w_repo, 0.1)  # clamped to 0.1

    def test_prioritize_with_index(self):
        idx = RepoIndex()
        idx.files = {"critical.py": {
            "file_size": 1000, "todo_density": 10.0,
            "code_ownership": 5, "dep_depth": 8,
        }}
        planner = self._make_planner(repo_index=idx)

        dag = {
            "Task 0": {
                "status": "Pending",
                "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status": "Pending",
                        "subtasks": {
                            "A1": {
                                "status": "Pending", "shadow": "Pending",
                                "last_update": 0,
                                "description": "Fix critical.py memory leak",
                                "output": "",
                            },
                            "A2": {
                                "status": "Pending", "shadow": "Pending",
                                "last_update": 0,
                                "description": "Update docs for README",
                                "output": "",
                            },
                        },
                    }
                },
            }
        }
        priority = planner.prioritize(dag, step=5)
        # A1 should rank higher than A2 due to repo risk
        names = [p[2] for p in priority]
        self.assertEqual(names[0], "A1")


if __name__ == "__main__":
    unittest.main()
