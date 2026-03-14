#!/usr/bin/env python3
"""
Tests for utils/safety.py and Dynamic Task Safety Guard integration.

Covers:
    - Finding normalization and dedup
    - FindingHistory persistence
    - StepBudget behavior
    - RepoAnalyzer dedup, cooldown, caps
    - PatchReviewer rejection threshold
    - Backward compatibility with older saved state
    - AI budget deferral

Run:
    python utils/test_safety.py
    python -m pytest utils/test_safety.py -v
"""

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.safety import (
    FindingHistory,
    StepBudget,
    normalize_finding_key,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Finding normalization
# ═════════════════════════════════════════════════════════════════════════════
class TestNormalizeFindingKey(unittest.TestCase):
    def test_todo_strips_line_number(self):
        k1 = normalize_finding_key("todo", "app.py", "L10 TODO: fix this")
        k2 = normalize_finding_key("todo", "app.py", "L99 TODO: fix this")
        self.assertEqual(k1, k2)

    def test_todo_case_insensitive(self):
        k1 = normalize_finding_key("todo", "app.py", "L5 TODO: Fix Memory Leak")
        k2 = normalize_finding_key("todo", "app.py", "L5 TODO: fix memory leak")
        self.assertEqual(k1, k2)

    def test_todo_collapses_whitespace(self):
        k1 = normalize_finding_key("todo", "x.py", "L1 TODO: fix  this   now")
        k2 = normalize_finding_key("todo", "x.py", "L1 TODO: fix this now")
        self.assertEqual(k1, k2)

    def test_missing_docstring_extracts_func_name(self):
        k1 = normalize_finding_key("missing_docstring", "m.py", "foo() at line 10")
        k2 = normalize_finding_key("missing_docstring", "m.py", "foo() at line 50")
        self.assertEqual(k1, k2)

    def test_missing_test_extracts_filename(self):
        k1 = normalize_finding_key("missing_test", "a.py", "no test_{} found for a.py")
        k2 = normalize_finding_key("missing_test", "a.py", "no test_{} found for a.py")
        self.assertEqual(k1, k2)

    def test_large_file_ignores_line_count(self):
        k1 = normalize_finding_key("large_file", "big.py", "600 lines")
        k2 = normalize_finding_key("large_file", "big.py", "700 lines")
        self.assertEqual(k1, k2)

    def test_different_files_differ(self):
        k1 = normalize_finding_key("todo", "a.py", "L1 TODO: fix")
        k2 = normalize_finding_key("todo", "b.py", "L1 TODO: fix")
        self.assertNotEqual(k1, k2)

    def test_different_categories_differ(self):
        k1 = normalize_finding_key("todo", "a.py", "L1 TODO: fix")
        k2 = normalize_finding_key("missing_test", "a.py", "L1 TODO: fix")
        self.assertNotEqual(k1, k2)


# ═════════════════════════════════════════════════════════════════════════════
# 2. FindingHistory persistence
# ═════════════════════════════════════════════════════════════════════════════
class TestFindingHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "history.json")

    def test_record_and_is_known(self):
        h = FindingHistory(self.path)
        self.assertFalse(h.is_known("todo", "x.py", "L1 TODO: fix"))
        h.record("todo", "x.py", "L1 TODO: fix", step=5)
        self.assertTrue(h.is_known("todo", "x.py", "L1 TODO: fix"))

    def test_normalized_dedup(self):
        h = FindingHistory(self.path)
        h.record("todo", "x.py", "L1 TODO: fix this", step=5)
        # Different line number, same content → should be known
        self.assertTrue(h.is_known("todo", "x.py", "L99 TODO: fix this"))

    def test_save_and_load(self):
        h1 = FindingHistory(self.path)
        h1.record("todo", "a.py", "L1 TODO: save test", step=1)
        h1.save()

        h2 = FindingHistory(self.path)
        self.assertTrue(h2.is_known("todo", "a.py", "L5 TODO: save test"))

    def test_load_missing_file(self):
        h = FindingHistory(os.path.join(self.tmp, "nonexistent.json"))
        self.assertFalse(h.load())
        self.assertEqual(h.count(), 0)

    def test_count(self):
        h = FindingHistory(self.path)
        h.record("todo", "a.py", "L1 TODO: one", step=1)
        h.record("todo", "b.py", "L1 TODO: two", step=1)
        self.assertEqual(h.count(), 2)

    def test_clear(self):
        h = FindingHistory(self.path)
        h.record("todo", "a.py", "L1 TODO: one", step=1)
        h.clear()
        self.assertEqual(h.count(), 0)


# ═════════════════════════════════════════════════════════════════════════════
# 3. StepBudget
# ═════════════════════════════════════════════════════════════════════════════
class TestStepBudget(unittest.TestCase):
    def test_unlimited(self):
        b = StepBudget(max_calls=0)
        self.assertFalse(b.exhausted)
        self.assertTrue(b.consume(100))
        self.assertFalse(b.exhausted)
        self.assertEqual(b.remaining, -1)

    def test_limited_budget(self):
        b = StepBudget(max_calls=3)
        self.assertFalse(b.exhausted)
        self.assertTrue(b.consume(1))
        self.assertTrue(b.consume(1))
        self.assertTrue(b.consume(1))
        self.assertTrue(b.exhausted)
        self.assertEqual(b.remaining, 0)

    def test_over_budget_defers(self):
        b = StepBudget(max_calls=2)
        b.consume(2)
        self.assertFalse(b.consume(1))
        self.assertEqual(b.deferred, 1)

    def test_consume_multiple(self):
        b = StepBudget(max_calls=5)
        self.assertTrue(b.consume(3))
        self.assertEqual(b.used, 3)
        self.assertEqual(b.remaining, 2)
        self.assertFalse(b.consume(3))  # would exceed
        self.assertEqual(b.deferred, 3)


# ═════════════════════════════════════════════════════════════════════════════
# 4. RepoAnalyzer dedup, cooldown, caps
# ═════════════════════════════════════════════════════════════════════════════
def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(textwrap.dedent(content))


def _make_dag():
    return {
        "Task 0": {
            "status": "Pending",
            "depends_on": [],
            "branches": {
                "Branch A": {
                    "status": "Pending",
                    "subtasks": {
                        "A1": {
                            "status": "Pending", "shadow": "Pending",
                            "last_update": 0, "description": "Seed", "output": "",
                        }
                    },
                }
            },
        }
    }


class TestRepoAnalyzerDedup(unittest.TestCase):
    def test_persistent_dedup_across_instances(self):
        tmp = tempfile.mkdtemp()
        _write(os.path.join(tmp, "x.py"), "# TODO: fix this\n")
        hist_path = os.path.join(tmp, "history.json")
        cfg = {
            "REPO_ANALYZER_ROOT": tmp, "REPO_ANALYZER_SCAN_DIRS": ["."],
            "REPO_ANALYZER_INTERVAL": 1, "REPO_ANALYZER_COOLDOWN_STEPS": 1,
            "REPO_ANALYZER_HISTORY_PATH": hist_path,
            "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 20,
            "MAX_DYNAMIC_TASKS_TOTAL": 50,
        }
        from agents.repo_analyzer import RepoAnalyzer

        ra1 = RepoAnalyzer(cfg)
        dag1 = _make_dag()
        added1 = ra1.analyze(dag1, {"Branch A": []}, step=1, alerts=[])
        self.assertGreater(added1, 0)

        # Second instance loads history — same findings should be deduped
        ra2 = RepoAnalyzer(cfg)
        dag2 = _make_dag()
        added2 = ra2.analyze(dag2, {"Branch A": []}, step=2, alerts=[])
        self.assertEqual(added2, 0, "Persistent dedup should prevent re-injection")


class TestRepoAnalyzerCooldown(unittest.TestCase):
    def test_cooldown_prevents_early_rerun(self):
        tmp = tempfile.mkdtemp()
        _write(os.path.join(tmp, "a.py"), "# TODO: first\n")
        _write(os.path.join(tmp, "b.py"), "# TODO: second\n")
        cfg = {
            "REPO_ANALYZER_ROOT": tmp, "REPO_ANALYZER_SCAN_DIRS": ["."],
            "REPO_ANALYZER_INTERVAL": 1, "REPO_ANALYZER_COOLDOWN_STEPS": 10,
            "REPO_ANALYZER_HISTORY_PATH": os.path.join(tmp, "h.json"),
            "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 20,
            "MAX_DYNAMIC_TASKS_TOTAL": 50,
        }
        from agents.repo_analyzer import RepoAnalyzer
        ra = RepoAnalyzer(cfg)

        self.assertTrue(ra.should_run(step=10))
        ra._last_run_step = 10
        # Cooldown is 10 — should not run at step 15
        self.assertFalse(ra.should_run(step=15))
        # Should run at step 20
        self.assertTrue(ra.should_run(step=20))

    def test_cooldown_remaining_at(self):
        from agents.repo_analyzer import RepoAnalyzer
        ra = RepoAnalyzer({"REPO_ANALYZER_COOLDOWN_STEPS": 10, "REPO_ANALYZER_INTERVAL": 1})
        ra._last_run_step = 5
        self.assertEqual(ra.cooldown_remaining_at(10), 5)
        self.assertEqual(ra.cooldown_remaining_at(15), 0)

    def test_force_bypasses_cooldown(self):
        from agents.repo_analyzer import RepoAnalyzer
        ra = RepoAnalyzer({"REPO_ANALYZER_COOLDOWN_STEPS": 100, "REPO_ANALYZER_INTERVAL": 100})
        ra._last_run_step = 0
        self.assertFalse(ra.should_run(step=5))
        self.assertTrue(ra.should_run(step=5, force=True))


class TestRepoAnalyzerCaps(unittest.TestCase):
    def test_per_analysis_cap(self):
        tmp = tempfile.mkdtemp()
        # Create many TODOs
        lines = "\n".join(f"# TODO: item {i}" for i in range(20))
        _write(os.path.join(tmp, "many.py"), lines)
        cfg = {
            "REPO_ANALYZER_ROOT": tmp, "REPO_ANALYZER_SCAN_DIRS": ["."],
            "REPO_ANALYZER_INTERVAL": 1, "REPO_ANALYZER_COOLDOWN_STEPS": 1,
            "REPO_ANALYZER_HISTORY_PATH": os.path.join(tmp, "h.json"),
            "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 3,
            "MAX_DYNAMIC_TASKS_TOTAL": 50,
        }
        from agents.repo_analyzer import RepoAnalyzer
        ra = RepoAnalyzer(cfg)
        dag = _make_dag()
        added = ra.analyze(dag, {"Branch A": []}, step=1, alerts=[])
        self.assertLessEqual(added, 3)

    def test_global_cap(self):
        tmp = tempfile.mkdtemp()
        lines = "\n".join(f"# TODO: item {i}" for i in range(10))
        _write(os.path.join(tmp, "many.py"), lines)
        cfg = {
            "REPO_ANALYZER_ROOT": tmp, "REPO_ANALYZER_SCAN_DIRS": ["."],
            "REPO_ANALYZER_INTERVAL": 1, "REPO_ANALYZER_COOLDOWN_STEPS": 1,
            "REPO_ANALYZER_HISTORY_PATH": os.path.join(tmp, "h.json"),
            "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 20,
            "MAX_DYNAMIC_TASKS_TOTAL": 2,
        }
        from agents.repo_analyzer import RepoAnalyzer
        ra = RepoAnalyzer(cfg)
        dag = _make_dag()
        added = ra.analyze(dag, {"Branch A": []}, step=1, alerts=[])
        self.assertLessEqual(added, 2)
        self.assertLessEqual(ra.dynamic_tasks_created, 2)

    def test_global_cap_blocks_further_analysis(self):
        from agents.repo_analyzer import RepoAnalyzer
        ra = RepoAnalyzer({
            "MAX_DYNAMIC_TASKS_TOTAL": 5,
            "REPO_ANALYZER_INTERVAL": 1, "REPO_ANALYZER_COOLDOWN_STEPS": 1,
        })
        ra._dynamic_tasks_created = 5
        alerts: list = []
        added = ra.analyze(_make_dag(), {"Branch A": []}, step=100, alerts=alerts)
        self.assertEqual(added, 0)
        self.assertTrue(any("global cap" in a for a in alerts))


# ═════════════════════════════════════════════════════════════════════════════
# 5. PatchReviewer rejection threshold
# ═════════════════════════════════════════════════════════════════════════════
class TestPatchReviewerRejectionThreshold(unittest.TestCase):
    def _make_reviewer(self, max_rejections=3):
        from agents.patch_reviewer import PatchReviewer
        pr = PatchReviewer({
            "PATCH_REVIEWER_ENABLED": True,
            "MAX_PATCH_REJECTIONS": max_rejections,
        })
        pr.available = True
        pr._client = MagicMock()
        return pr

    def _make_dag(self, status="Review"):
        return {
            "Task 0": {
                "status": "Running", "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status": "Running",
                        "subtasks": {
                            "A1": {
                                "status": status, "shadow": "Done",
                                "last_update": 5,
                                "description": "Implement foo",
                                "output": "def foo(): pass",
                            }
                        },
                    }
                },
            }
        }

    def test_first_rejection_resets_to_pending(self):
        pr = self._make_reviewer(max_rejections=3)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="REJECTED: bad style")]
        pr._client.messages.create.return_value = mock_msg

        dag = self._make_dag()
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, [])

        self.assertEqual(results["A1"], "rejected")
        self.assertEqual(dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["status"], "Pending")
        self.assertEqual(pr.rejection_count("A1"), 1)

    def test_threshold_escalates_to_review(self):
        pr = self._make_reviewer(max_rejections=2)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="REJECTED: still bad")]
        pr._client.messages.create.return_value = mock_msg

        # Pre-seed rejection count to threshold-1
        pr._rejections["A1"] = {"count": 1, "reasons": ["first"]}

        dag = self._make_dag()
        alerts: list = []
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, alerts)

        self.assertEqual(results["A1"], "escalated")
        st = dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(st["status"], "Review")
        self.assertEqual(pr.rejection_count("A1"), 2)
        self.assertEqual(pr.threshold_hits, 1)
        self.assertTrue(any("REJECTION LIMIT" in a for a in alerts))

    def test_rejection_reasons_tracked(self):
        pr = self._make_reviewer(max_rejections=5)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="REJECTED: reason one")]
        pr._client.messages.create.return_value = mock_msg

        pr.review_step(self._make_dag(), {"A1": "review"}, 6, {"Branch A": []}, [])
        reasons = pr.rejection_reasons("A1")
        self.assertEqual(len(reasons), 1)
        self.assertIn("reason one", reasons[0])

    def test_rejection_count_for_unknown_subtask(self):
        from agents.patch_reviewer import PatchReviewer
        pr = PatchReviewer({})
        self.assertEqual(pr.rejection_count("UNKNOWN"), 0)
        self.assertEqual(pr.rejection_reasons("UNKNOWN"), [])


# ═════════════════════════════════════════════════════════════════════════════
# 6. Backward compatibility with older saved state
# ═════════════════════════════════════════════════════════════════════════════
class TestBackwardCompatibility(unittest.TestCase):
    def test_load_old_state_without_safety(self):
        """State files without safety_state key should load cleanly."""
        tmp = tempfile.mkdtemp()
        state_path = os.path.join(tmp, "state", "solo_builder_state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)

        old_state = {
            "step": 10,
            "snapshot_counter": 2,
            "healed_total": 1,
            "dag": _make_dag(),
            "memory_store": {"Branch A": []},
            "alerts": [],
            "meta_history": [],
        }
        with open(state_path, "w") as f:
            json.dump(old_state, f)

        import solo_builder_cli as m
        old_state_path = m.STATE_PATH
        try:
            m.STATE_PATH = state_path
            cli = m.SoloBuilderCLI()
            result = cli.load_state()
            self.assertTrue(result)
            self.assertEqual(cli.step, 10)
            # Safety state should use defaults
            self.assertEqual(cli.repo_analyzer._dynamic_tasks_created, 0)
            self.assertEqual(cli.patch_reviewer._rejections, {})
            self.assertEqual(cli.patch_reviewer.threshold_hits, 0)
        finally:
            m.STATE_PATH = old_state_path

    def test_subtask_without_history_field(self):
        """Subtasks lacking 'history' should not crash PatchReviewer."""
        from agents.patch_reviewer import PatchReviewer
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True, "MAX_PATCH_REJECTIONS": 3})
        pr.available = True
        pr._client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="REJECTED: missing")]
        pr._client.messages.create.return_value = mock_msg

        dag = {
            "Task 0": {
                "status": "Running", "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status": "Running",
                        "subtasks": {
                            "A1": {
                                "status": "Review", "shadow": "Done",
                                "last_update": 5,
                                "description": "Test",
                                "output": "code here",
                                # No "history" key — old state format
                            }
                        },
                    }
                },
            }
        }
        # Should not raise
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, [])
        self.assertIn("A1", results)


# ═════════════════════════════════════════════════════════════════════════════
# 7. AI budget deferral
# ═════════════════════════════════════════════════════════════════════════════
class TestBudgetDeferral(unittest.TestCase):
    def test_patch_reviewer_respects_budget(self):
        from agents.patch_reviewer import PatchReviewer
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        budget = StepBudget(max_calls=0)  # exhausted immediately
        budget.used = 1
        budget.max_calls = 1  # already at limit

        dag = {
            "Task 0": {
                "status": "Running", "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status": "Running",
                        "subtasks": {
                            "A1": {
                                "status": "Review", "shadow": "Done",
                                "last_update": 5,
                                "description": "Test",
                                "output": "some code",
                            }
                        },
                    }
                },
            }
        }
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, [],
                                  budget=budget)
        # Should defer (fail-safe) when budget exhausted — NOT auto-approve
        self.assertEqual(results["A1"], "deferred")
        pr._client.messages.create.assert_not_called()

    def test_test_generator_respects_budget(self):
        from agents.test_generator import TestGenerator
        tmp = tempfile.mkdtemp()
        tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": True,
            "TEST_GENERATOR_ROOT": tmp,
            "TEST_GENERATOR_OUTPUT_DIR": "tests/generated",
        })
        tg.available = True
        tg._client = MagicMock()

        budget = StepBudget(max_calls=1)
        budget.used = 1  # already at limit

        dag = {
            "Task 0": {
                "status": "Running", "depends_on": [],
                "branches": {
                    "Branch A": {
                        "status": "Running",
                        "subtasks": {
                            "A1": {
                                "status": "Review", "shadow": "Done",
                                "last_update": 5,
                                "description": "Test",
                                "output": "def foo(): return 42",
                            }
                        },
                    }
                },
            }
        }
        written = tg.generate_tests(dag, {"A1": "review"}, 6, {"Branch A": []}, [],
                                      budget=budget)
        self.assertEqual(written, 0)
        tg._client.messages.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
