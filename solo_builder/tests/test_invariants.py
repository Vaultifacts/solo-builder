"""Tests for utils/invariants.py"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.invariants import check_post_phase


class TestCheckPostPhase(unittest.TestCase):
    """Test check_post_phase invariant checker."""

    def test_clean_dag_returns_no_violations(self):
        """A valid DAG with no structural issues should return empty list."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"},
                            "subtask_2": {"status": "Verified", "shadow": "Done"},
                        }
                    }
                }
            }
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(violations, [])

    def test_invalid_status_detected(self):
        """Invalid status in subtask should be detected and phase included."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "InvalidStatus", "shadow": "Pending"}
                        }
                    }
                }
            }
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(len(violations), 1)
        self.assertIn("[TestPhase]", violations[0])
        self.assertIn("invalid status", violations[0])

    def test_invalid_shadow_detected(self):
        """Invalid shadow value should be detected and phase included."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "InvalidShadow"}
                        }
                    }
                }
            }
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(len(violations), 1)
        self.assertIn("[TestPhase]", violations[0])
        self.assertIn("invalid shadow", violations[0])

    def test_missing_depends_on_target_detected(self):
        """depends_on reference to non-existent task should be detected."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"}
                        }
                    }
                },
                "depends_on": ["NonExistentTask"],
            }
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(len(violations), 1)
        self.assertIn("[TestPhase]", violations[0])
        self.assertIn("TaskA", violations[0])
        self.assertIn("depends_on", violations[0])
        self.assertIn("NonExistentTask", violations[0])
        self.assertIn("missing from DAG", violations[0])

    def test_phase_name_included_in_violations(self):
        """All violation strings should include the phase name in brackets."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "BadStatus", "shadow": "Pending"}
                        }
                    }
                },
                "depends_on": ["MissingTask"],
            }
        }
        violations = check_post_phase(dag, "MyPhase")
        self.assertTrue(all("[MyPhase]" in v for v in violations))

    def test_empty_dag_handled(self):
        """An empty DAG should return no violations."""
        dag = {}
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(violations, [])

    def test_multiple_violations_collected(self):
        """All violations should be collected and returned."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "BadStatus", "shadow": "Pending"},
                            "subtask_2": {"status": "Pending", "shadow": "BadShadow"},
                        }
                    }
                },
                "depends_on": ["MissingTask1"],
            },
            "TaskB": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"}
                        }
                    }
                },
                "depends_on": ["MissingTask2"],
            },
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertGreater(len(violations), 0)
        # Should have structural violations (2) + dependency violations (2)
        self.assertGreaterEqual(len(violations), 4)

    def test_valid_depends_on_references_ignored(self):
        """Valid depends_on references should not generate violations."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"}
                        }
                    }
                }
            },
            "TaskB": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"}
                        }
                    }
                },
                "depends_on": ["TaskA"],
            },
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(violations, [])

    def test_missing_branches_key_detected(self):
        """Task missing 'branches' key should generate violation."""
        dag = {
            "TaskA": {}
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(len(violations), 1)
        self.assertIn("[TestPhase]", violations[0])
        self.assertIn("missing 'branches'", violations[0])

    def test_missing_subtasks_key_detected(self):
        """Branch missing 'subtasks' key should generate violation."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {}
                }
            }
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(len(violations), 1)
        self.assertIn("[TestPhase]", violations[0])
        self.assertIn("missing 'subtasks'", violations[0])

    def test_multiple_depends_on_targets_all_checked(self):
        """All depends_on targets should be validated."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"}
                        }
                    }
                }
            },
            "TaskB": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"}
                        }
                    }
                },
                "depends_on": ["TaskA", "MissingTask1", "MissingTask2"],
            },
        }
        violations = check_post_phase(dag, "TestPhase")
        # Should have 2 dependency violations
        dep_violations = [v for v in violations if "depends_on" in v]
        self.assertEqual(len(dep_violations), 2)

    def test_no_depends_on_field_handled(self):
        """Tasks without depends_on field should not cause errors."""
        dag = {
            "TaskA": {
                "branches": {
                    "main": {
                        "subtasks": {
                            "subtask_1": {"status": "Pending", "shadow": "Pending"}
                        }
                    }
                }
            }
        }
        violations = check_post_phase(dag, "TestPhase")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
