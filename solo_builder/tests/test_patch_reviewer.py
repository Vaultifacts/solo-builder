"""Tests for agents/patch_reviewer.py - PatchReviewer agent."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.patch_reviewer import PatchReviewer


class TestPatchReviewerInit(unittest.TestCase):
    """Tests for PatchReviewer initialization."""

    def test_init_default_settings(self):
        """Test initialization with default settings."""
        reviewer = PatchReviewer()
        self.assertTrue(reviewer.enabled)
        self.assertEqual(reviewer._model, "claude-sonnet-4-6")
        self.assertEqual(reviewer._max_tokens, 256)
        self.assertEqual(reviewer.max_rejections, 3)

    def test_init_custom_settings(self):
        """Test initialization with custom settings."""
        settings = {
            "PATCH_REVIEWER_ENABLED": False,
            "PATCH_REVIEWER_MODEL": "claude-haiku",
            "PATCH_REVIEWER_MAX_TOKENS": 512,
            "MAX_PATCH_REJECTIONS": 5,
        }
        reviewer = PatchReviewer(settings)
        self.assertFalse(reviewer.enabled)
        self.assertEqual(reviewer._max_tokens, 512)

    def test_init_client_disabled(self):
        """Test that client is not initialized when disabled."""
        settings = {"PATCH_REVIEWER_USE_SDK": False}
        reviewer = PatchReviewer(settings)
        self.assertFalse(reviewer.available)


class TestPatchReviewerHeuristics(unittest.TestCase):
    """Tests for heuristic-based review."""

    def setUp(self):
        self.reviewer = PatchReviewer({"PATCH_REVIEWER_USE_SDK": False})

    def test_heuristics_detects_file_deletion(self):
        """Test dangerous file deletion patterns."""
        approved, reason, risk_score = self.reviewer._check_heuristics(
            description="Cleanup", output="shutil.rmtree('/tmp')"
        )
        self.assertFalse(approved)
        self.assertIn("Dangerous pattern", reason)

    def test_heuristics_detects_os_remove(self):
        """Test os.remove detection."""
        approved, reason, risk_score = self.reviewer._check_heuristics(
            description="Delete file", output="os.remove('/etc/passwd')"
        )
        self.assertFalse(approved)

    def test_heuristics_detects_sql_drop(self):
        """Test DROP TABLE detection."""
        approved, reason, risk_score = self.reviewer._check_heuristics(
            description="Schema", output="DROP TABLE users;"
        )
        self.assertFalse(approved)
        self.assertIn("Dangerous keyword", reason)

    def test_heuristics_rejects_empty(self):
        """Test empty output rejection."""
        approved, reason, risk_score = self.reviewer._check_heuristics(
            description="Task", output=""
        )
        self.assertFalse(approved)
        self.assertIn("empty", reason.lower())

    def test_heuristics_approves_clean(self):
        """Test clean code approval."""
        approved, reason, risk_score = self.reviewer._check_heuristics(
            description="Feature", output="def good_func():\n    return True"
        )
        self.assertTrue(approved)
        self.assertEqual(risk_score, 0)

    def test_heuristics_flags_error_messages(self):
        """Test that ERROR messages increase risk."""
        approved, reason, risk_score = self.reviewer._check_heuristics(
            description="Fix", output="ERROR: something failed"
        )
        self.assertTrue(approved)
        self.assertGreater(risk_score, 0)


class TestPatchReviewerSDK(unittest.TestCase):
    """Tests for SDK verdict parsing."""

    def test_parse_approved(self):
        """Test APPROVED parsing."""
        approved, reason = PatchReviewer._parse_verdict("APPROVED")
        self.assertTrue(approved)
        self.assertEqual(reason, "")

    def test_parse_rejected(self):
        """Test REJECTED parsing."""
        approved, reason = PatchReviewer._parse_verdict("REJECTED: bad code")
        self.assertFalse(approved)
        self.assertIn("bad code", reason)

    def test_parse_ambiguous_rejects(self):
        """Test ambiguous defaults to reject."""
        approved, reason = PatchReviewer._parse_verdict("Maybe?")
        self.assertFalse(approved)
        self.assertIn("ambiguous", reason)

    def test_sdk_failure_rejects(self):
        """CRITICAL: SDK failure must reject, not approve."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        reviewer = PatchReviewer({"PATCH_REVIEWER_USE_SDK": True})
        reviewer._client = mock_client

        approved, reason, tokens = reviewer._ask_claude("task", "output")

        self.assertFalse(approved)
        self.assertIn("manual review required", reason)
        self.assertEqual(tokens, 0)

    def test_sdk_success(self):
        """Test successful Claude review."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="APPROVED")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=10)
        mock_client.messages.create.return_value = mock_response

        reviewer = PatchReviewer({"PATCH_REVIEWER_USE_SDK": True})
        reviewer._client = mock_client

        approved, reason, tokens = reviewer._ask_claude("task", "output")

        self.assertTrue(approved)
        self.assertEqual(tokens, 110)


class TestPatchReviewerTracking(unittest.TestCase):
    """Tests for rejection tracking."""

    def setUp(self):
        self.reviewer = PatchReviewer({"PATCH_REVIEWER_USE_SDK": False})

    def test_rejection_count_starts_zero(self):
        """Initial rejection count is zero."""
        count = self.reviewer.rejection_count("st1")
        self.assertEqual(count, 0)

    def test_rejection_tracking(self):
        """Rejection tracking increments."""
        st = "st1"
        self.reviewer._rejections[st] = {"count": 2, "reasons": ["r1", "r2"]}
        self.assertEqual(self.reviewer.rejection_count(st), 2)
        self.assertEqual(self.reviewer.rejection_reasons(st), ["r1", "r2"])

    def test_threshold_hits(self):
        """Threshold hits counter works."""
        self.assertEqual(self.reviewer.threshold_hits, 0)
        self.reviewer.threshold_hits += 1
        self.assertEqual(self.reviewer.threshold_hits, 1)


class TestPatchReviewerIntegration(unittest.TestCase):
    """Tests for review_step integration."""

    def setUp(self):
        self.reviewer = PatchReviewer({"PATCH_REVIEWER_USE_SDK": False})

    def test_disabled_returns_empty(self):
        """Disabled reviewer returns empty."""
        reviewer = PatchReviewer({"PATCH_REVIEWER_ENABLED": False})
        results = reviewer.review_step({}, {}, 1, {}, [])
        self.assertEqual(results, {})

    def test_no_actions_returns_empty(self):
        """No actions returns empty."""
        results = self.reviewer.review_step({}, {}, 1, {}, [])
        self.assertEqual(results, {})

    def test_approves_empty_output(self):
        """Empty output is approved."""
        dag = {
            "t1": {"branches": {"b1": {"subtasks": {
                "st1": {"status": "Verified", "output": "", "description": "task"}
            }}}}
        }
        results = self.reviewer.review_step(dag, {"st1": "verified"}, 1, {}, [])
        self.assertEqual(results["st1"], "approved")

    def test_approves_clean_output(self):
        """Clean output is approved."""
        dag = {
            "t1": {"branches": {"b1": {"subtasks": {
                "st1": {"status": "Verified", "output": "def func(): pass", "description": "task"}
            }}}}
        }
        results = self.reviewer.review_step(dag, {"st1": "verified"}, 1, {}, [])
        self.assertEqual(results["st1"], "approved")

    def test_rejects_dangerous_output(self):
        """Dangerous output is rejected."""
        dag = {
            "t1": {"branches": {"b1": {"subtasks": {
                "st1": {
                    "status": "Verified",
                    "output": "DROP TABLE",
                    "description": "task",
                    "history": []
                }
            }}}}
        }
        results = self.reviewer.review_step(dag, {"st1": "verified"}, 1, {}, [])
        self.assertEqual(results["st1"], "rejected")
        self.assertEqual(self.reviewer.rejection_count("st1"), 1)

    def test_escalates_after_threshold(self):
        """Escalates to Review after max rejections."""
        reviewer = PatchReviewer({
            "PATCH_REVIEWER_USE_SDK": False,
            "MAX_PATCH_REJECTIONS": 1
        })
        dag = {
            "t1": {"branches": {"b1": {"subtasks": {
                "st1": {
                    "status": "Verified",
                    "output": "DROP TABLE",
                    "description": "task",
                    "history": []
                }
            }}}}
        }
        results = reviewer.review_step(dag, {"st1": "verified"}, 1, {}, [])
        self.assertEqual(results["st1"], "escalated")
        self.assertEqual(dag["t1"]["branches"]["b1"]["subtasks"]["st1"]["status"], "Review")
        self.assertEqual(reviewer.threshold_hits, 1)

    def test_defers_with_throughput_limit(self):
        """Defers when throughput cap hit."""
        reviewer = PatchReviewer({
            "PATCH_REVIEWER_USE_SDK": False,
            "MAX_PATCH_REVIEWS_PER_STEP": 1
        })
        dag = {
            "t1": {"branches": {"b1": {"subtasks": {
                "st1": {"status": "Verified", "output": "ok", "description": "t1"},
                "st2": {"status": "Verified", "output": "ok", "description": "t2"}
            }}}}
        }
        results = reviewer.review_step(dag, {"st1": "verified", "st2": "verified"}, 1, {}, [])
        approved = sum(1 for v in results.values() if v == "approved")
        deferred = sum(1 for v in results.values() if v == "deferred")
        self.assertEqual(approved, 1)
        self.assertEqual(deferred, 1)

    def test_defers_with_exhausted_budget(self):
        """Defers when budget exhausted."""
        dag = {
            "t1": {"branches": {"b1": {"subtasks": {
                "st1": {"status": "Verified", "output": "ok", "description": "task"}
            }}}}
        }

        mock_budget = MagicMock()
        mock_budget.exhausted = True

        results = self.reviewer.review_step(dag, {"st1": "verified"}, 1, {}, [], budget=mock_budget)
        self.assertEqual(results["st1"], "deferred")


if __name__ == "__main__":
    unittest.main()
