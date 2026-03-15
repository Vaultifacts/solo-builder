"""Tests for PolicyEngine wiring in Executor.execute_step — TASK-NNN.

Verifies that:
1. PolicyEngine is initialized with settings from executor's config
2. Policy evaluation blocks dangerous outputs (stays Running)
3. Policy evaluation sets Review on critical outputs
4. Safe outputs proceed to Verified normally
5. Oversized outputs trigger review
"""
from __future__ import annotations

import json as _json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.executor import Executor
from utils.policy_engine import PolicyEngine


def _make_dag(status="Running", description="", output="", tools="Read,Glob"):
    """Build a minimal DAG with one subtask."""
    return {
        "Task-A": {
            "branches": {
                "Branch-1": {
                    "subtasks": {
                        "ST-1": {
                            "name": "ST-1",
                            "status": status,
                            "description": description,
                            "output": output,
                            "history": [],
                            "tools": tools,
                        }
                    }
                }
            }
        }
    }


def _plist():
    """Priority list with one subtask."""
    return [("Task-A", "Branch-1", "ST-1", 0)]


def _make_executor(settings_override=None, verify_prob=1.0):
    """Build an executor with optional settings override."""
    ex = Executor(max_per_step=1, verify_prob=verify_prob)
    ex.claude.available = False
    ex.anthropic.available = False
    ex.sdk_tool.available = False
    # If settings provided, reinit policy engine with them
    if settings_override:
        ex._policy_engine = PolicyEngine(settings_override)
    return ex


# ---------------------------------------------------------------------------
# Test: PolicyEngine is wired into executor
# ---------------------------------------------------------------------------

class TestPolicyEngineInitialization(unittest.TestCase):
    """Executor initializes PolicyEngine with settings.json config."""

    def test_executor_has_policy_engine(self):
        """Executor has _policy_engine attribute initialized at construction."""
        ex = _make_executor()
        self.assertIsNotNone(ex._policy_engine)
        self.assertIsInstance(ex._policy_engine, PolicyEngine)

    def test_policy_engine_receives_config_dict(self):
        """PolicyEngine is initialized with settings dict (from _CFG)."""
        # The executor reads _CFG at module import time and passes it to PolicyEngine
        # We can't easily override _CFG at runtime, but we can verify the attribute exists
        ex = _make_executor()
        # Verify it was constructed with a dict (might be empty in tests)
        self.assertTrue(hasattr(ex._policy_engine, "blocked_paths"))
        self.assertTrue(hasattr(ex._policy_engine, "critical_patterns"))
        self.assertTrue(hasattr(ex._policy_engine, "max_patch_size"))


# ---------------------------------------------------------------------------
# Test: Blocked outputs stay Running
# ---------------------------------------------------------------------------

class TestPolicyEngineBlokedOutputsStayRunning(unittest.TestCase):
    """Subtask output mentioning .env or blocked path stays Running."""

    def test_env_file_mention_blocks_and_stays_running(self):
        """Output mentioning .env → blocked → status stays Running."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        # Use default config which has .env in blocked_paths
        dag = _make_dag(status="Running", description="setup secrets", tools="Read")
        # Simulate SDK tool success with .env output
        async def _ok_with_env(*a, **kw):
            return (True, "I updated .env with the keys")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_with_env

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Running",
                         "Subtask with .env mention should stay Running")
        self.assertNotIn("ST-1", actions,
                         "Blocked subtask should not be in actions")

    def test_requirements_txt_stays_running(self):
        """Output mentioning requirements.txt → critical pattern → Review (not Verified)."""
        ex = _make_executor()
        dag = _make_dag(status="Running", description="update deps")
        # Note: requirements.txt is in critical_patterns, not blocked_paths
        # So it goes to Review, not stays Running. Let's test both cases.
        async def _ok_with_reqs(*a, **kw):
            return (True, "Updated requirements.txt with new versions")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_with_reqs

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        # requirements.txt is critical, so requires_review
        self.assertEqual(st["status"], "Review",
                         "Subtask with requirements.txt mention should go to Review")
        self.assertIn("ST-1", actions)
        self.assertEqual(actions["ST-1"], "review")

    def test_custom_blocked_config_respected(self):
        """PolicyEngine uses custom BLOCKED_AUTONOMOUS_PATHS from settings."""
        custom_config = {
            "BLOCKED_AUTONOMOUS_PATHS": ["secrets/*"],
        }
        ex = _make_executor(settings_override=custom_config, verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="handle secrets", tools="Read")
        # Output mentions a secrets/* file (in custom blocked list)
        async def _ok_with_secret(*a, **kw):
            return (True, "Wrote API key to secrets/api_key.json")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_with_secret

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Running",
                         "Custom blocked config should be respected")
        self.assertNotIn("ST-1", actions)


# ---------------------------------------------------------------------------
# Test: Critical outputs go to Review (not Verified)
# ---------------------------------------------------------------------------

class TestPolicyCriticalOutputsGoToReview(unittest.TestCase):
    """Subtask with critical file mentions → Review status."""

    def test_package_json_mention_requires_review(self):
        """Output mentioning package.json → critical → Review."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        # package.json is in default critical_patterns
        dag = _make_dag(status="Running", description="add dependencies", tools="Read")
        async def _ok_with_pkg(*a, **kw):
            return (True, "I updated package.json with the new packages")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_with_pkg

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Review",
                         "Critical file mentions should go to Review")
        self.assertEqual(actions.get("ST-1"), "review")

    def test_migrations_mention_requires_review(self):
        """Output mentioning migrations/* → critical → Review."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="migrate database", tools="Read")
        async def _ok_with_migration(*a, **kw):
            return (True, "Created migrations/0002_add_user_table.py")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_with_migration

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Review")
        self.assertEqual(actions.get("ST-1"), "review")

    def test_pyproject_toml_mention_requires_review(self):
        """Output mentioning pyproject.toml → critical → Review."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="update python config", tools="Read")
        async def _ok_with_pyproject(*a, **kw):
            return (True, "Modified pyproject.toml to add new test dependencies")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_with_pyproject

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Review")

    def test_custom_critical_pattern_respected(self):
        """Custom CRITICAL_PATH_PATTERNS config is respected."""
        custom_config = {
            "CRITICAL_PATH_PATTERNS": ["secret_config/*"],
            "REQUIRE_HUMAN_REVIEW_FOR_CRITICAL_PATHS": True,
        }
        ex = _make_executor(settings_override=custom_config, verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="set secrets", tools="Read")
        async def _ok_with_secret(*a, **kw):
            return (True, "Wrote to secret_config/api_keys.json")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_with_secret

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Review",
                         "Custom critical pattern should trigger Review")


# ---------------------------------------------------------------------------
# Test: Safe outputs proceed to Verified
# ---------------------------------------------------------------------------

class TestSafeOutputsVerified(unittest.TestCase):
    """Subtask with safe output proceeds to Verified (when not in review_mode)."""

    def test_generic_safe_output_verified(self):
        """Output with no risky paths → Verified."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="write documentation", tools="Read")
        async def _ok_safe(*a, **kw):
            return (True, "Updated README.md with installation instructions")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_safe

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Verified",
                         "Safe output should be Verified")
        self.assertEqual(actions.get("ST-1"), "verified")

    def test_output_with_safe_paths_only(self):
        """Output mentioning only safe file paths (src/, test/) → Verified."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="refactor code", tools="Read")
        async def _ok_refactor(*a, **kw):
            return (True, "Refactored src/main.py and test/test_main.py")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_refactor

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Verified")
        # Output is truncated to 400 chars in executor.py line 298
        self.assertEqual(st.get("output", "")[:45], "Refactored src/main.py and test/test_main.py")

    def test_empty_output_verified(self):
        """Empty output (no paths) → Verified."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="run tests", tools="Read")
        async def _ok_empty(*a, **kw):
            return (True, "")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_empty

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Verified")


# ---------------------------------------------------------------------------
# Test: Oversized outputs trigger Review
# ---------------------------------------------------------------------------

class TestOversizedOutputsReview(unittest.TestCase):
    """Subtask with oversized output → Review (triggered by patch size policy)."""

    def test_oversized_lines_triggers_review(self):
        """Output exceeding max_lines_modified → Review."""
        custom_config = {
            "MAX_LINES_MODIFIED_PER_SUBTASK": 100,  # limit to 100 lines
        }
        ex = _make_executor(settings_override=custom_config, verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="add feature", tools="Read")
        # Create output with >100 lines (200 newlines = 200+ lines)
        big_output = "Added line " + "\nAdded line ".join(str(i) for i in range(150))
        async def _ok_big(*a, **kw):
            return (True, big_output)
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_big

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Review",
                         "Oversized output (lines) should go to Review")
        self.assertEqual(actions.get("ST-1"), "review")

    def test_oversized_files_triggers_review(self):
        """Output mentioning >max_files paths → Review."""
        custom_config = {
            "MAX_FILES_MODIFIED_PER_SUBTASK": 3,
        }
        ex = _make_executor(settings_override=custom_config, verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="refactor", tools="Read")
        # Mention 5 files (more than limit of 3)
        async def _ok_many_files(*a, **kw):
            return (True, "Modified file1.py file2.py file3.py file4.py file5.py")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_many_files

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Review",
                         "Output touching too many files should go to Review")

    def test_oversized_patch_size_triggers_review(self):
        """Output size exceeding max_patch_size → Review."""
        custom_config = {
            "MAX_PATCH_SIZE": 1000,  # 1000 bytes max
        }
        ex = _make_executor(settings_override=custom_config, verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", description="big change", tools="Read")
        # Create output > 1000 bytes
        big_output = "x" * 1500
        async def _ok_big_patch(*a, **kw):
            return (True, big_output)
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_big_patch

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        self.assertEqual(st["status"], "Review",
                         "Oversized patch should go to Review")


# ---------------------------------------------------------------------------
# Test: Policy evaluation on all execution paths
# ---------------------------------------------------------------------------

class TestPolicyEvaluationOnAllPaths(unittest.TestCase):
    """PolicyEngine.evaluate_patch is called on all successful execution paths."""

    def test_policy_evaluated_on_claude_subprocess_success(self):
        """Claude subprocess path → policy evaluated."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        ex.anthropic.available = False
        ex.sdk_tool.available = False
        ex.claude.available = True
        dag = _make_dag(status="Running", description="test", tools="Read")
        ex.claude.run = MagicMock(return_value=(True, "I updated .env"))

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        # Claude output mentions .env → should stay Running
        self.assertEqual(st["status"], "Running",
                         "Claude path should respect policy")
        self.assertNotIn("ST-1", actions)

    def test_policy_evaluated_on_anthropic_direct_success(self):
        """SDK direct (anthropic) path → policy evaluated."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        ex.sdk_tool.available = False
        ex.claude.available = False
        ex.anthropic.available = True
        # No tools → uses anthropic direct (SDK jobs path, not sdk_tool)
        dag = _make_dag(status="Running", description="describe", tools="")
        async def _ok_direct(*a, **kw):
            return (True, "Migrated database with migrations/0001_init.py")
        ex.anthropic.arun = _ok_direct

        plist = _plist()
        with patch("runners.executor._write_step_metrics"):
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        # Output mentions migrations/ → critical → Review
        self.assertEqual(st["status"], "Review",
                         "Anthropic direct path should respect policy")
        self.assertEqual(actions.get("ST-1"), "review")


# ---------------------------------------------------------------------------
# Test: Policy decision logging
# ---------------------------------------------------------------------------

class TestPolicyDecisionLogging(unittest.TestCase):
    """Policy decisions are logged at appropriate levels."""

    def test_blocked_decision_logged_at_warning(self):
        """policy_blocked log at WARNING level."""
        import logging
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = False
        ex.sdk_tool.available = True
        dag = _make_dag(status="Running", tools="Read")
        async def _ok_blocked(*a, **kw):
            return (True, "Modified .env with secrets")
        ex.sdk_tool.arun = _ok_blocked

        log_records: list[logging.LogRecord] = []

        class _Cap(logging.Handler):
            def emit(self, record):
                log_records.append(record)

        cap = _Cap()
        logger = logging.getLogger("solo_builder")
        logger.addHandler(cap)
        old_level = logger.level
        logger.setLevel(logging.WARNING)
        try:
            plist = _plist()
            with patch("runners.executor._write_step_metrics"), \
                 patch("runners.executor._hitl_evaluate", return_value=0), \
                 patch("runners.executor._hitl_policy_evaluate", return_value=0), \
                 patch("runners.executor._scope_evaluate") as mock_scope:
                mock_scope.return_value = MagicMock(allowed=True)
                ex.execute_step(dag, plist, step=1, memory_store={})
        finally:
            logger.removeHandler(cap)
            logger.setLevel(old_level)

        msgs = [r.getMessage() for r in log_records if "policy_blocked" in r.getMessage()]
        self.assertTrue(msgs, "policy_blocked should be logged")
        blocked_records = [r for r in log_records if "policy_blocked" in r.getMessage()]
        self.assertTrue(blocked_records)
        self.assertEqual(blocked_records[0].levelno, logging.WARNING)


# ---------------------------------------------------------------------------
# Test: Policy config integration from settings.json
# ---------------------------------------------------------------------------

class TestPolicyConfigFromSettings(unittest.TestCase):
    """PolicyEngine loads configuration correctly from settings."""

    def test_default_blocked_paths_when_not_configured(self):
        """Default blocked paths include .env, .pem, etc. when not overridden."""
        ex = Executor(max_per_step=1, verify_prob=1.0)
        # .env should be in default blocked paths
        self.assertIn(".env", ex._policy_engine.blocked_paths)

    def test_default_critical_patterns_when_not_configured(self):
        """Default critical patterns include requirements*.txt, package.json, etc."""
        ex = Executor(max_per_step=1, verify_prob=1.0)
        # requirements*.txt should be in default critical patterns
        has_requirements = any(
            "requirements" in p for p in ex._policy_engine.critical_patterns
        )
        self.assertTrue(has_requirements)

    def test_config_override_via_settings(self):
        """Settings override affects policy decisions."""
        # Simulate a very restrictive policy
        restrictive = {
            "BLOCKED_AUTONOMOUS_PATHS": ["*.py", "*.json"],  # block python and json files
        }
        ex = _make_executor(settings_override=restrictive, verify_prob=1.0)
        ex.review_mode = False
        dag = _make_dag(status="Running", tools="Read")
        async def _ok_anything(*a, **kw):
            return (True, "Modified script.py and config.json")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_anything

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        # With blocked patterns, matching files are blocked
        self.assertEqual(st["status"], "Running",
                         "Restrictive policy should block matching output")


# ---------------------------------------------------------------------------
# Test: Review mode interaction with policy
# ---------------------------------------------------------------------------

class TestPolicyWithReviewMode(unittest.TestCase):
    """When review_mode=True, even safe outputs go to Review."""

    def test_safe_output_goes_to_review_in_review_mode(self):
        """review_mode=True → all successful outputs go to Review (policy allows)."""
        ex = _make_executor(verify_prob=1.0)
        ex.review_mode = True
        dag = _make_dag(status="Running", tools="Read")
        async def _ok_safe(*a, **kw):
            return (True, "Safe output, no risky paths")
        ex.sdk_tool.available = True
        ex.sdk_tool.arun = _ok_safe

        plist = _plist()
        with patch("runners.executor._write_step_metrics"), \
             patch("runners.executor._hitl_evaluate", return_value=0), \
             patch("runners.executor._hitl_policy_evaluate", return_value=0), \
             patch("runners.executor._scope_evaluate") as mock_scope:
            mock_scope.return_value = MagicMock(allowed=True)
            actions = ex.execute_step(dag, plist, step=1, memory_store={})

        st = dag["Task-A"]["branches"]["Branch-1"]["subtasks"]["ST-1"]
        # review_mode overrides Verified → Review
        self.assertEqual(st["status"], "Review")
        self.assertEqual(actions.get("ST-1"), "review")


if __name__ == "__main__":
    unittest.main()
