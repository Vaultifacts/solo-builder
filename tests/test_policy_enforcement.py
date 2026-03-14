#!/usr/bin/env python3
"""
tests/test_policy_enforcement.py — Tests for policy enforcement integration
with Executor, RepoAnalyzer, and observability surfaces.

Covers:
    - Executor policy enforcement (blocked → Review, critical → Review)
    - RepoAnalyzer ignoring blocked paths
    - Policy stats in agent_stats()
    - Backward compatibility in persistence defaults

Run:
    python -m pytest tests/test_policy_enforcement.py -v
"""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.policy_engine import PolicyEngine
from core.persistence import apply_backward_compat_defaults
from utils.runtime_views import agent_stats


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_dag_with_output(*subtasks):
    """Build a DAG where subtasks have output referencing file paths."""
    st_dict = {}
    for name, output in subtasks:
        st_dict[name] = {
            "status": "Verified",
            "shadow": "Done",
            "last_update": 5,
            "description": f"Fix {name}",
            "output": output,
        }
    return {
        "Task 0": {
            "status": "Running",
            "depends_on": [],
            "branches": {
                "Branch A": {"status": "Running", "subtasks": st_dict},
            },
        },
    }


def _make_priority_list(*names):
    """Build priority list tuples for the given subtask names."""
    return [("Task 0", "Branch A", name, 0) for name in names]


# ═════════════════════════════════════════════════════════════════════════════
# Executor policy enforcement
# ═════════════════════════════════════════════════════════════════════════════
class TestExecutorPolicyBlocked(unittest.TestCase):
    """Executor moves subtask to Review when output references blocked path."""

    def test_blocked_path_moves_to_review(self):
        policy = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": ["config/*"],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
        })
        dag = _make_dag_with_output(
            ("A1", "Modified config/database.yaml"),
        )
        actions = {"A1": "verified"}
        priority = _make_priority_list("A1")

        # Simulate the policy enforcement pass from Executor.execute_step
        for task_name, branch_name, st_name, _ in priority:
            if st_name not in actions:
                continue
            action = actions[st_name]
            if action not in ("verified", "review"):
                continue
            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            output = st_data.get("output", "")
            if not output:
                continue
            decision = policy.evaluate_patch(output, st_data.get("description", ""))
            if decision.action == "blocked":
                st_data["status"] = "Review"
                st_data["shadow"] = "Pending"
                actions[st_name] = "review"
            elif decision.action == "requires_review":
                st_data["status"] = "Review"
                actions[st_name] = "review"

        self.assertEqual(actions["A1"], "review")
        self.assertEqual(
            dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["status"],
            "Review"
        )

    def test_clean_output_stays_verified(self):
        policy = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": ["config/*"],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
        })
        dag = _make_dag_with_output(
            ("A1", "Modified src/app.py"),
        )
        actions = {"A1": "verified"}
        priority = _make_priority_list("A1")

        for task_name, branch_name, st_name, _ in priority:
            if st_name not in actions:
                continue
            action = actions[st_name]
            if action not in ("verified", "review"):
                continue
            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            output = st_data.get("output", "")
            if not output:
                continue
            decision = policy.evaluate_patch(output, st_data.get("description", ""))
            if decision.action == "blocked":
                st_data["status"] = "Review"
                actions[st_name] = "review"

        self.assertEqual(actions["A1"], "verified")
        self.assertEqual(
            dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["status"],
            "Verified"
        )


class TestExecutorPolicyCritical(unittest.TestCase):
    """Executor moves subtask to Review for critical path references."""

    def test_critical_path_moves_to_review(self):
        policy = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": ["requirements*.txt"],
            "REQUIRE_HUMAN_REVIEW_FOR_CRITICAL_PATHS": True,
        })
        dag = _make_dag_with_output(
            ("A1", "Updated requirements.txt"),
        )
        actions = {"A1": "verified"}
        priority = _make_priority_list("A1")

        for task_name, branch_name, st_name, _ in priority:
            if st_name not in actions:
                continue
            action = actions[st_name]
            if action not in ("verified", "review"):
                continue
            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            output = st_data.get("output", "")
            if not output:
                continue
            decision = policy.evaluate_patch(output, st_data.get("description", ""))
            if decision.action == "requires_review":
                st_data["status"] = "Review"
                actions[st_name] = "review"

        self.assertEqual(actions["A1"], "review")


class TestExecutorPolicyOversized(unittest.TestCase):
    """Oversized patches move to Review."""

    def test_oversized_patch_moves_to_review(self):
        policy = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
            "MAX_PATCH_SIZE": 20,
        })
        big_output = "x" * 100  # exceeds MAX_PATCH_SIZE
        dag = _make_dag_with_output(("A1", big_output))
        actions = {"A1": "verified"}
        priority = _make_priority_list("A1")

        for task_name, branch_name, st_name, _ in priority:
            if st_name not in actions:
                continue
            action = actions[st_name]
            if action not in ("verified", "review"):
                continue
            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            output = st_data.get("output", "")
            if not output:
                continue
            decision = policy.evaluate_patch(output, st_data.get("description", ""))
            if decision.action in ("blocked", "requires_review"):
                st_data["status"] = "Review"
                actions[st_name] = "review"

        self.assertEqual(actions["A1"], "review")


# ═════════════════════════════════════════════════════════════════════════════
# RepoAnalyzer policy filtering
# ═════════════════════════════════════════════════════════════════════════════
class TestRepoAnalyzerPolicyFilter(unittest.TestCase):
    """RepoAnalyzer skips blocked files during scan."""

    def _write(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(textwrap.dedent(content))

    def test_blocked_files_skipped(self):
        from agents.repo_analyzer import RepoAnalyzer

        tmp = tempfile.mkdtemp()
        # Create a blocked file and an allowed file
        self._write(os.path.join(tmp, "config", "settings.py"),
                     "# TODO: fix config\ndef configure(): pass\n")
        self._write(os.path.join(tmp, "src", "app.py"),
                     "# TODO: fix app\ndef main(): pass\n")

        hist_path = os.path.join(tmp, "history.json")
        cfg = {
            "REPO_ANALYZER_ROOT": tmp,
            "REPO_ANALYZER_SCAN_DIRS": ["."],
            "REPO_ANALYZER_INTERVAL": 1,
            "REPO_ANALYZER_COOLDOWN_STEPS": 1,
            "REPO_ANALYZER_HISTORY_PATH": hist_path,
            "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 50,
            "MAX_DYNAMIC_TASKS_TOTAL": 100,
        }
        ra = RepoAnalyzer(cfg)

        policy = PolicyEngine({
            "BLOCKED_AUTONOMOUS_PATHS": ["config/*"],
            "ALLOWED_AUTONOMOUS_PATHS": [],
            "CRITICAL_PATH_PATTERNS": [],
        })

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

        alerts = []
        added = ra.analyze(dag, {"Branch A": []}, step=20, alerts=alerts,
                            policy=policy)

        # Should only find TODOs in src/app.py, NOT config/settings.py
        # Check that no subtask descriptions reference config/
        for task_data in dag.values():
            for branch_data in task_data.get("branches", {}).values():
                for st_data in branch_data.get("subtasks", {}).values():
                    desc = st_data.get("description", "")
                    self.assertNotIn("config/", desc,
                                      "Policy-blocked file should not generate tasks")

    def test_no_policy_scans_all(self):
        from agents.repo_analyzer import RepoAnalyzer

        tmp = tempfile.mkdtemp()
        self._write(os.path.join(tmp, "config", "settings.py"),
                     "# TODO: fix config\n")
        self._write(os.path.join(tmp, "src", "app.py"),
                     "# TODO: fix app\n")

        hist_path = os.path.join(tmp, "history.json")
        cfg = {
            "REPO_ANALYZER_ROOT": tmp,
            "REPO_ANALYZER_SCAN_DIRS": ["."],
            "REPO_ANALYZER_INTERVAL": 1,
            "REPO_ANALYZER_COOLDOWN_STEPS": 1,
            "REPO_ANALYZER_HISTORY_PATH": hist_path,
            "MAX_DYNAMIC_TASKS_PER_ANALYSIS": 50,
            "MAX_DYNAMIC_TASKS_TOTAL": 100,
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

        alerts = []
        added = ra.analyze(dag, {"Branch A": []}, step=20, alerts=alerts)
        # Without policy, both files should be scanned
        self.assertGreaterEqual(added, 2)


# ═════════════════════════════════════════════════════════════════════════════
# Policy stats in observability
# ═════════════════════════════════════════════════════════════════════════════
class TestPolicyStatsInAgentStats(unittest.TestCase):
    """agent_stats() includes policy section."""

    def test_policy_section_present(self):
        state = {
            "dag": {},
            "step": 10,
            "healed_total": 0,
            "meta_history": [],
            "safety_state": {},
        }
        stats = agent_stats(state)
        self.assertIn("policy", stats)
        self.assertEqual(stats["policy"]["policy_block_count"], 0)
        self.assertEqual(stats["policy"]["critical_path_review_count"], 0)
        self.assertEqual(stats["policy"]["oversized_patch_count"], 0)

    def test_policy_section_with_data(self):
        state = {
            "dag": {},
            "step": 10,
            "healed_total": 0,
            "meta_history": [],
            "safety_state": {},
            "policy_state": {
                "policy_block_count": 5,
                "critical_path_review_count": 3,
                "oversized_patch_count": 2,
            },
        }
        stats = agent_stats(state)
        self.assertEqual(stats["policy"]["policy_block_count"], 5)
        self.assertEqual(stats["policy"]["critical_path_review_count"], 3)
        self.assertEqual(stats["policy"]["oversized_patch_count"], 2)


# ═════════════════════════════════════════════════════════════════════════════
# Backward compatibility
# ═════════════════════════════════════════════════════════════════════════════
class TestBackwardCompatPolicyState(unittest.TestCase):
    """Older state files without policy_state get valid defaults."""

    def test_missing_policy_state(self):
        payload = {"meta_history": [], "safety_state": {}, "recovery_state": {}}
        apply_backward_compat_defaults(payload)
        ps = payload["policy_state"]
        self.assertEqual(ps["policy_block_count"], 0)
        self.assertEqual(ps["critical_path_review_count"], 0)
        self.assertEqual(ps["oversized_patch_count"], 0)

    def test_existing_policy_state_preserved(self):
        payload = {
            "meta_history": [], "safety_state": {}, "recovery_state": {},
            "policy_state": {
                "policy_block_count": 42,
                "critical_path_review_count": 10,
                "oversized_patch_count": 5,
            },
        }
        apply_backward_compat_defaults(payload)
        self.assertEqual(payload["policy_state"]["policy_block_count"], 42)


if __name__ == "__main__":
    unittest.main()
