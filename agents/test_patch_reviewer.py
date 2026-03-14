#!/usr/bin/env python3
"""
Tests for agents/patch_reviewer.py — PatchReviewer agent.

Run:
    python agents/test_patch_reviewer.py
    python -m pytest agents/test_patch_reviewer.py -v
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.patch_reviewer import PatchReviewer


def _make_dag(st_status="Review", output="def foo(): return 42"):
    """Minimal DAG with one subtask at the given status."""
    return {
        "Task 0": {
            "status": "Running",
            "depends_on": [],
            "branches": {
                "Branch A": {
                    "status": "Running",
                    "subtasks": {
                        "A1": {
                            "status": st_status,
                            "shadow": "Done",
                            "last_update": 5,
                            "description": "Implement foo function",
                            "output": output,
                        }
                    },
                }
            },
        }
    }


class TestParseVerdict(unittest.TestCase):
    def test_approved(self):
        ok, reason = PatchReviewer._parse_verdict("APPROVED")
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_approved_with_dash(self):
        ok, reason = PatchReviewer._parse_verdict("APPROVED — looks good")
        self.assertTrue(ok)

    def test_rejected_with_reason(self):
        ok, reason = PatchReviewer._parse_verdict("REJECTED: breaks style conventions")
        self.assertFalse(ok)
        self.assertIn("breaks style", reason)

    def test_rejected_no_reason(self):
        ok, reason = PatchReviewer._parse_verdict("REJECTED")
        self.assertFalse(ok)
        self.assertEqual(reason, "no reason given")

    def test_ambiguous_auto_approves(self):
        ok, reason = PatchReviewer._parse_verdict("The code looks fine to me.")
        self.assertTrue(ok)
        self.assertIn("ambiguous", reason)

    def test_empty_auto_approves(self):
        ok, reason = PatchReviewer._parse_verdict("")
        self.assertTrue(ok)

    def test_multiline_uses_first_line(self):
        ok, reason = PatchReviewer._parse_verdict("REJECTED: bad style\nBut otherwise fine")
        self.assertFalse(ok)
        self.assertIn("bad style", reason)


class TestReviewStepDisabled(unittest.TestCase):
    def test_returns_empty_when_disabled(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": False})
        dag = _make_dag()
        results = pr.review_step(dag, {"A1": "verified"}, 6, {"Branch A": []}, [])
        self.assertEqual(results, {})

    def test_returns_empty_when_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        self.assertFalse(pr.available)


class TestReviewStepApproved(unittest.TestCase):
    def test_approved_leaves_status(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        # Mock Claude returning APPROVED
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="APPROVED")]
        pr._client.messages.create.return_value = mock_msg

        dag = _make_dag(st_status="Review")
        alerts: list = []
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, alerts)

        self.assertEqual(results["A1"], "approved")
        self.assertEqual(dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["status"], "Review")
        self.assertTrue(any("approved" in a for a in alerts))


class TestReviewStepRejected(unittest.TestCase):
    def test_rejected_resets_to_pending(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        # Mock Claude returning REJECTED
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="REJECTED: removes important error handling")]
        pr._client.messages.create.return_value = mock_msg

        dag = _make_dag(st_status="Verified")
        memory = {"Branch A": []}
        alerts: list = []
        results = pr.review_step(dag, {"A1": "verified"}, 6, memory, alerts)

        st = dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]
        self.assertEqual(results["A1"], "rejected")
        self.assertEqual(st["status"], "Pending")
        self.assertEqual(st["shadow"], "Pending")
        self.assertEqual(st["last_update"], 6)
        # History should have rejection note
        self.assertTrue(any("rejected" in str(h.get("note", "")) for h in st.get("history", [])))
        # Memory should be updated
        self.assertGreater(len(memory["Branch A"]), 0)
        # Alert should mention rejection
        self.assertTrue(any("rejected" in a for a in alerts))

    def test_rejected_alert_contains_reason(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="REJECTED: violates task description")]
        pr._client.messages.create.return_value = mock_msg

        dag = _make_dag()
        alerts: list = []
        pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, alerts)

        self.assertTrue(any("violates task description" in a for a in alerts))


class TestReviewStepSkips(unittest.TestCase):
    def test_skips_non_executor_subtasks(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        dag = _make_dag()
        # executor_actions doesn't contain A1
        results = pr.review_step(dag, {"B1": "verified"}, 6, {"Branch A": []}, [])
        self.assertNotIn("A1", results)
        pr._client.messages.create.assert_not_called()

    def test_skips_started_actions(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        dag = _make_dag(st_status="Running")
        results = pr.review_step(dag, {"A1": "started"}, 6, {"Branch A": []}, [])
        self.assertNotIn("A1", results)
        pr._client.messages.create.assert_not_called()

    def test_approves_empty_output(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        dag = _make_dag(output="")
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, [])
        self.assertEqual(results["A1"], "approved")
        pr._client.messages.create.assert_not_called()


class TestSdkError(unittest.TestCase):
    def test_sdk_error_auto_approves(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()
        pr._client.messages.create.side_effect = Exception("API timeout")

        dag = _make_dag()
        alerts: list = []
        results = pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, alerts)

        # Should auto-approve on error to avoid blocking
        self.assertEqual(results["A1"], "approved")
        self.assertEqual(dag["Task 0"]["branches"]["Branch A"]["subtasks"]["A1"]["status"], "Review")


class TestPromptContent(unittest.TestCase):
    def test_prompt_includes_description_and_output(self):
        pr = PatchReviewer({"PATCH_REVIEWER_ENABLED": True})
        pr.available = True
        pr._client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="APPROVED")]
        pr._client.messages.create.return_value = mock_msg

        dag = _make_dag(output="def bar(): return 99")
        pr.review_step(dag, {"A1": "review"}, 6, {"Branch A": []}, [])

        call_args = pr._client.messages.create.call_args
        prompt_text = call_args.kwargs["messages"][0]["content"]
        self.assertIn("Implement foo function", prompt_text)
        self.assertIn("def bar(): return 99", prompt_text)


if __name__ == "__main__":
    unittest.main()
