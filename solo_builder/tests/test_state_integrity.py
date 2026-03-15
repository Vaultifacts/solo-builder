"""
tests/test_state_integrity.py
Tests for utils/state_integrity.py — state integrity checking and repair.

Covers:
  - Valid state passes through unchanged
  - Invalid statuses get reset to Pending
  - Missing subtask keys get defaults
  - Broken depends_on references get removed
  - Empty/None payload handled gracefully
  - Repairs list accurately describes what was fixed
"""

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_UTILS_DIR = Path(__file__).resolve().parent.parent / "utils"
sys.path.insert(0, str(_UTILS_DIR))

from state_integrity import (
    check_resume_integrity,
    VALID_SUBTASK_STATUSES,
    VALID_SHADOW_STATUSES,
    DEFAULT_SUBTASK_FIELDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(dag=None):
    """Create a minimal state dict."""
    return {"dag": dag if dag is not None else {}, "step": 1}


def _make_task(branches=None, depends_on=None):
    """Create a minimal task dict."""
    return {
        "status": "Running",
        "depends_on": depends_on if depends_on is not None else [],
        "branches": branches if branches is not None else {},
    }


def _make_branch(subtasks=None):
    """Create a minimal branch dict."""
    return {"status": "Running", "subtasks": subtasks if subtasks is not None else {}}


def _make_subtask(
    status="Pending",
    shadow="Pending",
    last_update=0,
    description="",
    output="",
    history=None,
):
    """Create a complete subtask dict with all required fields."""
    return {
        "status": status,
        "shadow": shadow,
        "last_update": last_update,
        "description": description,
        "output": output,
        "history": history if history is not None else [],
    }


# ---------------------------------------------------------------------------
# Test: Valid state passes through unchanged
# ---------------------------------------------------------------------------


class TestValidStateUnchanged(unittest.TestCase):
    """Valid state with correct statuses should produce no repairs."""

    def test_empty_dag_no_repairs(self):
        """Empty DAG should produce no repairs."""
        state = _make_state()
        repairs = check_resume_integrity(state)
        self.assertEqual(repairs, [])

    def test_valid_single_subtask(self):
        """Single valid subtask should produce no repairs."""
        subtask = _make_subtask("Pending")
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(repairs, [])

    def test_valid_multiple_statuses(self):
        """All valid statuses (Pending, Running, Review, Verified) should pass."""
        subtasks = {
            "S1": _make_subtask("Pending"),
            "S2": _make_subtask("Running"),
            "S3": _make_subtask("Review"),
            "S4": _make_subtask("Verified"),
        }
        branch = _make_branch(subtasks)
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(repairs, [])

    def test_valid_shadow_statuses(self):
        """Valid shadow statuses (Pending, Done) should pass."""
        subtasks = {
            "S1": _make_subtask(shadow="Pending"),
            "S2": _make_subtask(shadow="Done"),
        }
        branch = _make_branch(subtasks)
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(repairs, [])

    def test_valid_dependencies(self):
        """Valid task dependencies should produce no repairs."""
        state = _make_state({
            "T1": _make_task(depends_on=[]),
            "T2": _make_task(depends_on=["T1"]),
            "T3": _make_task(depends_on=["T1", "T2"]),
        })
        repairs = check_resume_integrity(state)
        self.assertEqual(repairs, [])


# ---------------------------------------------------------------------------
# Test: Invalid status gets reset to Pending
# ---------------------------------------------------------------------------


class TestInvalidStatusRepair(unittest.TestCase):
    """Invalid subtask statuses should be reset to Pending."""

    def test_bogus_status_reset_to_pending(self):
        """Bogus status like 'Bogus' should be reset to Pending."""
        subtask = _make_subtask("Bogus")
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("invalid status 'Bogus'", repairs[0])
        self.assertIn("→ Pending", repairs[0])
        self.assertEqual(state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["status"], "Pending")

    def test_none_status_reset_to_pending(self):
        """None status should be reset to Pending."""
        subtask = _make_subtask("Pending")
        subtask["status"] = None
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertEqual(state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["status"], "Pending")

    def test_multiple_invalid_statuses(self):
        """Multiple subtasks with invalid statuses should all be reset."""
        subtasks = {
            "S1": _make_subtask("Bogus1"),
            "S2": _make_subtask("Bogus2"),
            "S3": _make_subtask("Pending"),
        }
        branch = _make_branch(subtasks)
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 2)
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["S1"]["status"],
            "Pending"
        )
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["S2"]["status"],
            "Pending"
        )


# ---------------------------------------------------------------------------
# Test: Invalid shadow gets reset to Pending
# ---------------------------------------------------------------------------


class TestInvalidShadowRepair(unittest.TestCase):
    """Invalid shadow values should be reset to Pending."""

    def test_bogus_shadow_reset_to_pending(self):
        """Bogus shadow should be reset to Pending."""
        subtask = _make_subtask(shadow="Bogus")
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("invalid shadow 'Bogus'", repairs[0])
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["shadow"],
            "Pending"
        )

    def test_none_shadow_reset_to_pending(self):
        """None shadow should be reset to Pending."""
        subtask = _make_subtask()
        subtask["shadow"] = None
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["shadow"],
            "Pending"
        )


# ---------------------------------------------------------------------------
# Test: Missing subtask keys get defaults
# ---------------------------------------------------------------------------


class TestMissingKeysRepair(unittest.TestCase):
    """Missing required subtask keys should be added with defaults."""

    def test_missing_status_added(self):
        """Missing 'status' key should be added as Pending."""
        subtask = _make_subtask()
        del subtask["status"]
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        # When status is missing, it will trigger the invalid status check (None not in valid)
        # and will be reported as "invalid status 'None'" or "added missing key 'status'"
        self.assertTrue(any("status" in r for r in repairs))
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["status"],
            "Pending"
        )

    def test_missing_shadow_added(self):
        """Missing 'shadow' key should be added as Pending."""
        subtask = _make_subtask()
        del subtask["shadow"]
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        # When shadow is missing, it will trigger the invalid shadow check (None not in valid)
        # and will be reported as "invalid shadow 'None'" or "added missing key 'shadow'"
        self.assertTrue(any("shadow" in r for r in repairs))
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["shadow"],
            "Pending"
        )

    def test_missing_last_update_added(self):
        """Missing 'last_update' key should be added as 0."""
        subtask = _make_subtask()
        del subtask["last_update"]
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertTrue(any("added missing key 'last_update'" in r for r in repairs))
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["last_update"],
            0
        )

    def test_missing_description_added(self):
        """Missing 'description' key should be added as empty string."""
        subtask = _make_subtask()
        del subtask["description"]
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertTrue(any("added missing key 'description'" in r for r in repairs))
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["description"],
            ""
        )

    def test_missing_output_added(self):
        """Missing 'output' key should be added as empty string."""
        subtask = _make_subtask()
        del subtask["output"]
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertTrue(any("added missing key 'output'" in r for r in repairs))
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["output"],
            ""
        )

    def test_missing_history_added(self):
        """Missing 'history' key should be added as empty list."""
        subtask = _make_subtask()
        del subtask["history"]
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertTrue(any("added missing key 'history'" in r for r in repairs))
        self.assertEqual(
            state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]["history"],
            []
        )

    def test_all_keys_missing(self):
        """All required keys missing should all be added."""
        subtask = {}
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        # Should have 6 repairs for all missing keys
        self.assertEqual(len(repairs), 6)
        st = state["dag"]["T1"]["branches"]["Br1"]["subtasks"]["ST1"]
        self.assertEqual(st["status"], "Pending")
        self.assertEqual(st["shadow"], "Pending")
        self.assertEqual(st["last_update"], 0)
        self.assertEqual(st["description"], "")
        self.assertEqual(st["output"], "")
        self.assertEqual(st["history"], [])


# ---------------------------------------------------------------------------
# Test: Broken depends_on references get removed
# ---------------------------------------------------------------------------


class TestBrokenDependsOnRepair(unittest.TestCase):
    """Broken task dependencies should be removed."""

    def test_single_broken_dependency(self):
        """Task depending on non-existent task should remove the broken dep."""
        state = _make_state({
            "T1": _make_task(depends_on=["T_NONEXISTENT"]),
        })

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("removed broken depends_on refs", repairs[0])
        self.assertEqual(state["dag"]["T1"]["depends_on"], [])

    def test_mixed_valid_and_broken_dependencies(self):
        """Mix of valid and broken deps should keep valid, remove broken."""
        state = _make_state({
            "T1": _make_task(depends_on=[]),
            "T2": _make_task(depends_on=["T1", "T_BROKEN", "T3"]),
            "T3": _make_task(depends_on=[]),
        })

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("removed broken depends_on refs", repairs[0])
        # Should keep T1 and T3, remove T_BROKEN
        self.assertEqual(set(state["dag"]["T2"]["depends_on"]), {"T1", "T3"})

    def test_multiple_broken_dependencies(self):
        """Multiple broken deps should all be removed."""
        state = _make_state({
            "T1": _make_task(depends_on=["T_A", "T_B", "T_C"]),
        })

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertEqual(state["dag"]["T1"]["depends_on"], [])

    def test_dependency_list_is_not_list(self):
        """Non-list depends_on should be reset to empty list."""
        state = _make_state({
            "T1": _make_task(depends_on="T2"),
        })

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("depends_on was not a list", repairs[0])
        self.assertEqual(state["dag"]["T1"]["depends_on"], [])


# ---------------------------------------------------------------------------
# Test: Empty/None payload handled gracefully
# ---------------------------------------------------------------------------


class TestEmptyPayloadHandling(unittest.TestCase):
    """Empty, None, and invalid payloads should be handled gracefully."""

    def test_none_payload(self):
        """None payload should be handled gracefully."""
        repairs = check_resume_integrity(None)
        self.assertEqual(len(repairs), 1)
        self.assertIn("Empty or invalid payload", repairs[0])

    def test_empty_dict_payload(self):
        """Empty dict payload should be handled gracefully."""
        repairs = check_resume_integrity({})
        self.assertEqual(len(repairs), 1)
        self.assertIn("Empty or invalid payload", repairs[0])

    def test_payload_without_dag_key(self):
        """Payload missing 'dag' key should initialize it."""
        repairs = check_resume_integrity({"step": 1})
        self.assertEqual(len(repairs), 1)
        self.assertIn("Missing 'dag' key", repairs[0])

    def test_dag_not_dict(self):
        """DAG that is not a dict should be reported and skipped."""
        repairs = check_resume_integrity({"dag": [1, 2, 3]})
        self.assertEqual(len(repairs), 1)
        self.assertIn("dag is not a dict", repairs[0])

    def test_task_not_dict(self):
        """Task that is not a dict should be skipped with message."""
        state = _make_state({"T1": "not_a_dict"})
        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("is not a dict", repairs[0])

    def test_branches_not_dict(self):
        """Branches that is not a dict should be reset."""
        state = _make_state({"T1": _make_task()})
        state["dag"]["T1"]["branches"] = "not_a_dict"
        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("branches is not a dict", repairs[0])
        self.assertEqual(state["dag"]["T1"]["branches"], {})

    def test_subtasks_not_dict(self):
        """Subtasks that is not a dict should be reset."""
        branch = _make_branch()
        branch["subtasks"] = "not_a_dict"
        state = _make_state({"T1": _make_task({"Br1": branch})})

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("subtasks is not a dict", repairs[0])
        self.assertEqual(state["dag"]["T1"]["branches"]["Br1"]["subtasks"], {})

    def test_subtask_not_dict(self):
        """Subtask that is not a dict should be skipped."""
        branch = _make_branch({"ST1": "not_a_dict"})
        state = _make_state({"T1": _make_task({"Br1": branch})})

        repairs = check_resume_integrity(state)
        self.assertEqual(len(repairs), 1)
        self.assertIn("not a dict", repairs[0])


# ---------------------------------------------------------------------------
# Test: Repairs list accurately describes what was fixed
# ---------------------------------------------------------------------------


class TestRepairsDescriptions(unittest.TestCase):
    """Repair messages should accurately describe what was fixed."""

    def test_repair_message_includes_path(self):
        """Repair message should include task/branch/subtask path."""
        subtask = _make_subtask("Invalid")
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        self.assertTrue(any("T1/Br1/ST1" in r for r in repairs))

    def test_repair_message_shows_old_and_new_value(self):
        """Repair message should show old status and new (Pending)."""
        subtask = _make_subtask("OldStatus")
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch})
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        msg = repairs[0]
        self.assertIn("OldStatus", msg)
        self.assertIn("Pending", msg)

    def test_repair_includes_broken_dep_names(self):
        """Repair message for broken deps should list the broken refs."""
        state = _make_state({
            "T1": _make_task(depends_on=["T_A", "T_B"]),
        })

        repairs = check_resume_integrity(state)
        msg = repairs[0]
        # Should mention the broken deps
        self.assertIn("T_A", msg)
        self.assertIn("T_B", msg)

    def test_multiple_repairs_all_reported(self):
        """All repairs should be reported in the list."""
        subtask_invalid_status = _make_subtask("BadStatus")
        subtask_missing_output = _make_subtask()
        del subtask_missing_output["output"]
        branch = _make_branch({
            "ST1": subtask_invalid_status,
            "ST2": subtask_missing_output,
        })
        task = _make_task({"Br1": branch}, depends_on=["T_BROKEN"])
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)
        # Should have: 1 invalid status, 1 missing output, 1 broken dep
        self.assertGreaterEqual(len(repairs), 3)


# ---------------------------------------------------------------------------
# Test: Integration scenarios
# ---------------------------------------------------------------------------


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for realistic scenarios."""

    def test_heavily_corrupted_state(self):
        """Heavily corrupted state should be repaired without crashing."""
        state = {
            "dag": {
                "T1": {
                    "branches": {
                        "Br1": {
                            "subtasks": {
                                "ST1": {
                                    "status": "Bogus",
                                    # Missing: shadow, last_update, description, output, history
                                }
                            }
                        }
                    },
                    "depends_on": ["T_NONEXISTENT"],
                },
                "T2": "not_a_dict",
            },
            "step": 1,
        }

        repairs = check_resume_integrity(state)
        # Should have multiple repairs
        self.assertGreater(len(repairs), 0)
        # State should still be traversable
        self.assertIn("T1", state["dag"])

    def test_multiple_tasks_multiple_branches_multiple_subtasks(self):
        """Complex DAG with multiple tasks/branches/subtasks should all be repaired."""
        state = _make_state({
            "T1": _make_task(
                {
                    "Br1": _make_branch({
                        "ST1": _make_subtask("Invalid1"),
                        "ST2": _make_subtask("Invalid2"),
                    }),
                    "Br2": _make_branch({
                        "ST3": _make_subtask(),
                    }),
                },
                depends_on=["T_FAKE"],
            ),
            "T2": _make_task(
                {
                    "Br3": _make_branch({
                        "ST4": _make_subtask("Invalid3"),
                    }),
                },
                depends_on=["T1"],
            ),
        })

        repairs = check_resume_integrity(state)
        # Should have at least 3 status repairs + 1 depends_on repair
        self.assertGreaterEqual(len(repairs), 4)

    def test_state_consistency_after_repairs(self):
        """After repairs, state should have consistent structure."""
        subtask = _make_subtask("BadStatus")
        del subtask["output"]
        del subtask["history"]
        branch = _make_branch({"ST1": subtask})
        task = _make_task({"Br1": branch}, depends_on=["T_BROKEN"])
        state = _make_state({"T1": task})

        repairs = check_resume_integrity(state)

        # Verify state is consistent
        t1 = state["dag"]["T1"]
        self.assertIsInstance(t1["depends_on"], list)
        self.assertNotIn("T_BROKEN", t1["depends_on"])

        st1 = t1["branches"]["Br1"]["subtasks"]["ST1"]
        self.assertIn(st1["status"], VALID_SUBTASK_STATUSES)
        self.assertIn(st1["shadow"], VALID_SHADOW_STATUSES)
        self.assertEqual(st1["last_update"], 0)
        self.assertEqual(st1["description"], "")
        self.assertEqual(st1["output"], "")
        self.assertEqual(st1["history"], [])


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------


class TestConstants(unittest.TestCase):
    """Verify module constants are correct."""

    def test_valid_subtask_statuses_includes_all_expected(self):
        """Should include Pending, Running, Review, Verified."""
        expected = {"Pending", "Running", "Review", "Verified"}
        self.assertEqual(VALID_SUBTASK_STATUSES, expected)

    def test_valid_shadow_statuses_includes_all_expected(self):
        """Should include Pending and Done."""
        expected = {"Pending", "Done"}
        self.assertEqual(VALID_SHADOW_STATUSES, expected)

    def test_default_subtask_fields_includes_all_required(self):
        """Should include all required fields."""
        required = {"status", "shadow", "last_update", "description", "output", "history"}
        self.assertEqual(set(DEFAULT_SUBTASK_FIELDS.keys()), required)


if __name__ == "__main__":
    unittest.main()
