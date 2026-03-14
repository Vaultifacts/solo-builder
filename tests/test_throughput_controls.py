#!/usr/bin/env python3
"""
tests/test_throughput_controls.py — Tests for per-phase throughput caps.

Covers:
    - PatchReviewer throughput cap (MAX_PATCH_REVIEWS_PER_STEP)
    - TestGenerator throughput cap (MAX_TEST_GENERATIONS_PER_STEP)
    - RepoAnalyzer findings cap (MAX_REPO_ANALYZER_FINDINGS_PER_STEP)
    - PatchReviewer fail-safe deferral (budget exhausted → deferred, NOT approved)
    - TestGenerator fail-safe deferral (budget exhausted → deferred)
    - Deferred alerts surfaced correctly

Run:
    python -m pytest tests/test_throughput_controls.py -v
"""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.safety import StepBudget


def _make_dag_with_subtasks(*names, output="some code", description="Test"):
    """Build a minimal DAG with the given subtask names."""
    subtasks = {}
    for n in names:
        subtasks[n] = {
            "status": "Review", "shadow": "Done",
            "last_update": 5, "description": description,
            "output": output,
        }
    return {
        "Task 0": {
            "status": "Running", "depends_on": [],
            "branches": {
                "Branch A": {"status": "Running", "subtasks": subtasks},
            },
        }
    }


# ═════════════════════════════════════════════════════════════════════════════
# PatchReviewer throughput cap
# ═════════════════════════════════════════════════════════════════════════════
class TestPatchReviewerThroughputCap(unittest.TestCase):
    def setUp(self):
        from agents.patch_reviewer import PatchReviewer
        self.pr = PatchReviewer({
            "PATCH_REVIEWER_ENABLED": True,
            "MAX_PATCH_REVIEWS_PER_STEP": 2,
        })
        self.pr.available = True
        self.pr._client = MagicMock()
        # Mock _ask_claude to return approved
        self.pr._ask_claude = MagicMock(return_value=(True, "", 100))

    def test_defers_excess_reviews(self):
        dag = _make_dag_with_subtasks("A1", "A2", "A3")
        actions = {"A1": "review", "A2": "review", "A3": "review"}
        alerts = []
        results = self.pr.review_step(dag, actions, 6, {"Branch A": []}, alerts)

        approved = [k for k, v in results.items() if v == "approved"]
        deferred = [k for k, v in results.items() if v == "deferred"]
        self.assertEqual(len(approved), 2)
        self.assertEqual(len(deferred), 1)
        # Verify deferred alert exists
        self.assertTrue(any("deferred (throughput cap)" in a for a in alerts))

    def test_no_cap_when_zero(self):
        self.pr.max_reviews_per_step = 0  # unlimited
        dag = _make_dag_with_subtasks("A1", "A2", "A3")
        actions = {"A1": "review", "A2": "review", "A3": "review"}
        results = self.pr.review_step(dag, actions, 6, {"Branch A": []}, [])
        approved = [k for k, v in results.items() if v == "approved"]
        self.assertEqual(len(approved), 3)


# ═════════════════════════════════════════════════════════════════════════════
# PatchReviewer fail-safe deferral
# ═════════════════════════════════════════════════════════════════════════════
class TestPatchReviewerFailSafeDeferral(unittest.TestCase):
    def test_budget_exhausted_defers_not_approves(self):
        from agents.patch_reviewer import PatchReviewer
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        budget = StepBudget(max_calls=1)
        budget.used = 1  # exhausted

        dag = _make_dag_with_subtasks("A1")
        alerts = []
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []},
                                  alerts, budget=budget)
        self.assertEqual(results["A1"], "deferred")
        self.assertTrue(any("budget exhausted" in a for a in alerts))
        pr._client.messages.create.assert_not_called()

    def test_token_budget_exhausted_defers(self):
        from agents.patch_reviewer import PatchReviewer
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        budget = StepBudget(max_tokens=100)
        budget.record_usage(tokens=100)

        dag = _make_dag_with_subtasks("A1")
        alerts = []
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []},
                                  alerts, budget=budget)
        self.assertEqual(results["A1"], "deferred")


# ═════════════════════════════════════════════════════════════════════════════
# TestGenerator throughput cap
# ═════════════════════════════════════════════════════════════════════════════
class TestTestGeneratorThroughputCap(unittest.TestCase):
    def setUp(self):
        from agents.test_generator import TestGenerator
        self.tmp = tempfile.mkdtemp()
        self.tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": True,
            "TEST_GENERATOR_ROOT": self.tmp,
            "TEST_GENERATOR_OUTPUT_DIR": "tests/generated",
            "MAX_TEST_GENERATIONS_PER_STEP": 1,
        })
        self.tg.available = True
        self.tg._client = MagicMock()
        # Mock _ask_claude to return test code
        self.tg._ask_claude = MagicMock(
            return_value=("# auto-generated\ndef test_foo(): assert True\n", 150)
        )

    def test_defers_excess_generations(self):
        dag = _make_dag_with_subtasks("A1", "A2", output="def foo(): return 42")
        actions = {"A1": "review", "A2": "review"}
        alerts = []
        written = self.tg.generate_tests(dag, actions, 6, {"Branch A": []}, alerts)
        self.assertEqual(written, 1)
        self.assertTrue(any("deferred (throughput cap)" in a for a in alerts))

    def test_no_cap_when_zero(self):
        self.tg.max_test_gens_per_step = 0
        dag = _make_dag_with_subtasks("A1", "A2", output="def foo(): return 42")
        actions = {"A1": "review", "A2": "review"}
        written = self.tg.generate_tests(dag, actions, 6, {"Branch A": []}, [])
        self.assertEqual(written, 2)


# ═════════════════════════════════════════════════════════════════════════════
# TestGenerator fail-safe deferral
# ═════════════════════════════════════════════════════════════════════════════
class TestTestGeneratorFailSafeDeferral(unittest.TestCase):
    def test_budget_exhausted_defers_with_alert(self):
        from agents.test_generator import TestGenerator
        tmp = tempfile.mkdtemp()
        tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": True,
            "TEST_GENERATOR_ROOT": tmp,
        })
        tg.available = True
        tg._client = MagicMock()

        budget = StepBudget(max_calls=1)
        budget.used = 1

        dag = _make_dag_with_subtasks("A1", output="def foo(): return 42")
        alerts = []
        written = tg.generate_tests(dag, {"A1": "review"}, 6,
                                      {"Branch A": []}, alerts, budget=budget)
        self.assertEqual(written, 0)
        self.assertTrue(any("budget exhausted" in a for a in alerts))
        tg._client.messages.create.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# RepoAnalyzer findings cap
# ═════════════════════════════════════════════════════════════════════════════
class TestRepoAnalyzerFindingsCap(unittest.TestCase):
    def _write(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(textwrap.dedent(content))

    def test_findings_per_step_cap(self):
        from agents.repo_analyzer import RepoAnalyzer

        tmp = tempfile.mkdtemp()
        # Create files with many TODOs
        for i in range(10):
            self._write(os.path.join(tmp, f"mod{i}.py"),
                        f"# TODO: fix thing {i}\ndef fn{i}(): pass\n")

        hist_path = os.path.join(tmp, "history.json")
        cfg = {
            "REPO_ANALYZER_ROOT": tmp,
            "REPO_ANALYZER_SCAN_DIRS": ["."],
            "REPO_ANALYZER_INTERVAL": 1,
            "REPO_ANALYZER_COOLDOWN_STEPS": 1,
            "REPO_ANALYZER_HISTORY_PATH": hist_path,
            "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 50,
            "MAX_DYNAMIC_TASKS_TOTAL": 100,
            "REPO_ANALYZER_MAX_FINDINGS": 50,
            "MAX_REPO_ANALYZER_FINDINGS_PER_STEP": 3,
        }
        ra = RepoAnalyzer(cfg)

        dag = {
            "Task 0": {
                "status": "Pending", "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status": "Pending",
                        "subtasks": {
                            "A1": {
                                "status": "Pending", "shadow": "Pending",
                                "last_update": 0, "description": "Seed",
                                "output": "",
                            }
                        },
                    }
                },
            }
        }
        added = ra.analyze(dag, {"Branch A": []}, step=20, alerts=[])
        self.assertLessEqual(added, 3)

    def test_findings_cap_zero_means_unlimited(self):
        from agents.repo_analyzer import RepoAnalyzer
        ra = RepoAnalyzer({"MAX_REPO_ANALYZER_FINDINGS_PER_STEP": 0})
        self.assertEqual(ra.max_findings_per_step, 0)


if __name__ == "__main__":
    unittest.main()
