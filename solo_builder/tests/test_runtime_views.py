"""
tests/test_runtime_views.py
Unit tests for utils/runtime_views.py canonical view helpers.

Tests cover:
- deps_met: dependency checking
- compute_risk: risk scoring for individual subtasks
- priority_queue: prioritization with multiple weights
- stalled_subtasks: stalled task detection
- dag_summary: overall DAG statistics
- compute_rates: rate calculation from history
- forecast_summary: ETA and progress estimation
- agent_stats: aggregated agent statistics
- per_task_stats: per-task breakdown statistics
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.runtime_views import (
    deps_met,
    compute_risk,
    priority_queue,
    stalled_subtasks,
    dag_summary,
    compute_rates,
    forecast_summary,
    agent_stats,
    per_task_stats,
)


class TestDepsMet(unittest.TestCase):
    """Test dependency checking logic."""

    def test_no_dependencies(self):
        """Task with no dependencies should always have deps_met=True."""
        dag = {
            "Task A": {
                "depends_on": [],
                "branches": {},
                "status": "Pending",
            }
        }
        self.assertTrue(deps_met(dag, "Task A"))

    def test_single_verified_dependency(self):
        """Task with single Verified dependency should have deps_met=True."""
        dag = {
            "Task A": {
                "depends_on": ["Task B"],
                "status": "Pending",
                "branches": {},
            },
            "Task B": {
                "depends_on": [],
                "status": "Verified",
                "branches": {},
            },
        }
        self.assertTrue(deps_met(dag, "Task A"))

    def test_single_pending_dependency(self):
        """Task with single Pending dependency should have deps_met=False."""
        dag = {
            "Task A": {
                "depends_on": ["Task B"],
                "status": "Pending",
                "branches": {},
            },
            "Task B": {
                "depends_on": [],
                "status": "Pending",
                "branches": {},
            },
        }
        self.assertFalse(deps_met(dag, "Task A"))

    def test_multiple_dependencies_all_verified(self):
        """Task with multiple Verified dependencies should have deps_met=True."""
        dag = {
            "Task A": {
                "depends_on": ["Task B", "Task C"],
                "status": "Pending",
                "branches": {},
            },
            "Task B": {"depends_on": [], "status": "Verified", "branches": {}},
            "Task C": {"depends_on": [], "status": "Verified", "branches": {}},
        }
        self.assertTrue(deps_met(dag, "Task A"))

    def test_multiple_dependencies_one_unverified(self):
        """Task with one unverified dependency should have deps_met=False."""
        dag = {
            "Task A": {
                "depends_on": ["Task B", "Task C"],
                "status": "Pending",
                "branches": {},
            },
            "Task B": {"depends_on": [], "status": "Verified", "branches": {}},
            "Task C": {"depends_on": [], "status": "Running", "branches": {}},
        }
        self.assertFalse(deps_met(dag, "Task A"))

    def test_nonexistent_dependency(self):
        """Nonexistent dependency should have deps_met=False."""
        dag = {
            "Task A": {
                "depends_on": ["NonExistent"],
                "status": "Pending",
                "branches": {},
            }
        }
        self.assertFalse(deps_met(dag, "Task A"))

    def test_missing_depends_on_key(self):
        """Task without depends_on key should default to empty and have deps_met=True."""
        dag = {
            "Task A": {
                "branches": {},
                "status": "Pending",
            }
        }
        self.assertTrue(deps_met(dag, "Task A"))


class TestComputeRisk(unittest.TestCase):
    """Test risk score computation."""

    def test_running_no_stall_no_age(self):
        """Running task at age 0 should have base stall risk."""
        st_data = {"status": "Running", "last_update": 10}
        step = 10
        risk = compute_risk(st_data, step, stall_threshold=5)
        self.assertEqual(risk, 1000)

    def test_running_no_stall_with_age(self):
        """Running task with age < threshold should add staleness risk."""
        st_data = {"status": "Running", "last_update": 5}
        step = 8
        risk = compute_risk(st_data, step, stall_threshold=10)
        # risk = 1000 + int(3 * 10 * 1.0) = 1030
        self.assertEqual(risk, 1030)

    def test_running_with_stall(self):
        """Running task with age >= threshold should add stall bonus."""
        st_data = {"status": "Running", "last_update": 0}
        step = 15
        risk = compute_risk(st_data, step, stall_threshold=10)
        # staleness = 15
        # risk = 1000 + int(500) + 15 * 20 = 1500 + 300 = 1800
        self.assertEqual(risk, 1800)

    def test_pending_early_age(self):
        """Pending task with age < 2 should have 0 risk."""
        st_data = {"status": "Pending", "last_update": 8}
        step = 9
        risk = compute_risk(st_data, step)
        self.assertEqual(risk, 0)

    def test_pending_with_age(self):
        """Pending task with age > 2 should accumulate staleness risk."""
        st_data = {"status": "Pending", "last_update": 0}
        step = 5
        risk = compute_risk(st_data, step)
        # staleness = 5 > 2, risk = int(5 * 8 * 1.0) = 40
        self.assertEqual(risk, 40)

    def test_pending_with_shadow_bonus(self):
        """Pending task with shadow Done should add bonus."""
        st_data = {"status": "Pending", "last_update": 0, "shadow": "Done"}
        step = 5
        risk = compute_risk(st_data, step)
        # risk = 40 + 50 = 90
        self.assertEqual(risk, 90)

    def test_verified_status_no_risk(self):
        """Verified task should have 0 risk."""
        st_data = {"status": "Verified", "last_update": 0}
        step = 100
        risk = compute_risk(st_data, step)
        self.assertEqual(risk, 0)

    def test_failed_status_no_risk(self):
        """Failed task should have 0 risk."""
        st_data = {"status": "Failed", "last_update": 0}
        step = 100
        risk = compute_risk(st_data, step)
        self.assertEqual(risk, 0)

    def test_weights_affect_risk(self):
        """Weight multipliers should scale risk."""
        st_data = {"status": "Running", "last_update": 0}
        step = 15
        risk1 = compute_risk(st_data, step, stall_threshold=10, w_stall=1.0)
        risk2 = compute_risk(st_data, step, stall_threshold=10, w_stall=2.0)
        self.assertLess(risk1, risk2)


class TestPriorityQueue(unittest.TestCase):
    """Test priority queue generation."""

    def test_empty_dag(self):
        """Empty DAG should return empty priority queue."""
        dag = {}
        pq = priority_queue(dag, step=10)
        self.assertEqual(pq, [])

    def test_single_pending(self):
        """Single pending subtask should be in queue."""
        dag = {
            "Task A": {
                "depends_on": [],
                "status": "Pending",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Pending",
                                "last_update": 0,
                            }
                        }
                    }
                },
            }
        }
        pq = priority_queue(dag, step=10)
        self.assertEqual(len(pq), 1)
        self.assertEqual(pq[0]["subtask"], "A1")

    def test_verified_excluded(self):
        """Verified subtasks should be excluded from queue."""
        dag = {
            "Task A": {
                "depends_on": [],
                "status": "Verified",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified", "last_update": 0},
                            "A2": {"status": "Pending", "last_update": 0},
                        }
                    }
                },
            }
        }
        pq = priority_queue(dag, step=10)
        self.assertEqual(len(pq), 1)
        self.assertEqual(pq[0]["subtask"], "A2")

    def test_unmet_dependencies_excluded(self):
        """Subtasks of tasks with unmet dependencies should be excluded."""
        dag = {
            "Task A": {
                "depends_on": ["Task B"],
                "status": "Pending",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Pending", "last_update": 0}
                        }
                    }
                },
            },
            "Task B": {
                "depends_on": [],
                "status": "Pending",
                "branches": {"Branch 1": {"subtasks": {}}},
            },
        }
        pq = priority_queue(dag, step=10)
        self.assertEqual(len(pq), 0)

    def test_risk_sorting(self):
        """Queue should be sorted by risk descending."""
        dag = {
            "Task A": {
                "depends_on": [],
                "status": "Pending",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Running",
                                "last_update": 0,
                            },
                            "A2": {
                                "status": "Pending",
                                "last_update": 8,
                            },
                        }
                    }
                },
            }
        }
        pq = priority_queue(dag, step=10)
        self.assertEqual(len(pq), 2)
        self.assertGreater(pq[0]["risk"], pq[1]["risk"])

    def test_limit_parameter(self):
        """limit parameter should cap result count."""
        dag = {
            "Task A": {
                "depends_on": [],
                "status": "Pending",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Pending", "last_update": 0},
                            "A2": {"status": "Pending", "last_update": 0},
                            "A3": {"status": "Pending", "last_update": 0},
                        }
                    }
                },
            }
        }
        pq = priority_queue(dag, step=10, limit=2)
        self.assertEqual(len(pq), 2)

    def test_multiple_branches(self):
        """Priority queue should include subtasks from multiple branches."""
        dag = {
            "Task A": {
                "depends_on": [],
                "status": "Pending",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Pending", "last_update": 0}
                        }
                    },
                    "Branch 2": {
                        "subtasks": {
                            "A2": {"status": "Pending", "last_update": 0}
                        }
                    },
                },
            }
        }
        pq = priority_queue(dag, step=10)
        self.assertEqual(len(pq), 2)


class TestStalledSubtasks(unittest.TestCase):
    """Test stalled task detection."""

    def test_empty_dag(self):
        """Empty DAG should return empty stalled list."""
        dag = {}
        stalled = stalled_subtasks(dag, step=10)
        self.assertEqual(stalled, [])

    def test_no_stalled(self):
        """Tasks before stall threshold should not be stalled."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Running",
                                "last_update": 7,
                                "description": "Test",
                            }
                        }
                    }
                }
            }
        }
        stalled = stalled_subtasks(dag, step=10, stall_threshold=5)
        self.assertEqual(len(stalled), 0)

    def test_single_stalled(self):
        """Task at stall threshold should be stalled."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Running",
                                "last_update": 5,
                                "description": "Test",
                            }
                        }
                    }
                }
            }
        }
        stalled = stalled_subtasks(dag, step=10, stall_threshold=5)
        self.assertEqual(len(stalled), 1)
        self.assertEqual(stalled[0]["age"], 5)

    def test_beyond_stall_threshold(self):
        """Task well beyond stall threshold should be stalled."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Running",
                                "last_update": 0,
                                "description": "Test description",
                            }
                        }
                    }
                }
            }
        }
        stalled = stalled_subtasks(dag, step=50, stall_threshold=5)
        self.assertEqual(len(stalled), 1)
        self.assertEqual(stalled[0]["age"], 50)

    def test_pending_not_stalled(self):
        """Pending tasks should not be considered stalled."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Pending",
                                "last_update": 0,
                                "description": "Test",
                            }
                        }
                    }
                }
            }
        }
        stalled = stalled_subtasks(dag, step=100, stall_threshold=5)
        self.assertEqual(len(stalled), 0)

    def test_verified_not_stalled(self):
        """Verified tasks should not be considered stalled."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Verified",
                                "last_update": 0,
                                "description": "Test",
                            }
                        }
                    }
                }
            }
        }
        stalled = stalled_subtasks(dag, step=100, stall_threshold=5)
        self.assertEqual(len(stalled), 0)

    def test_sorted_by_age_descending(self):
        """Stalled list should be sorted by age descending."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Running",
                                "last_update": 20,
                                "description": "Young",
                            },
                            "A2": {
                                "status": "Running",
                                "last_update": 0,
                                "description": "Old",
                            },
                        }
                    }
                }
            }
        }
        stalled = stalled_subtasks(dag, step=50, stall_threshold=5)
        self.assertEqual(len(stalled), 2)
        self.assertGreater(stalled[0]["age"], stalled[1]["age"])

    def test_description_truncated(self):
        """Description should be truncated to 80 chars."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Running",
                                "last_update": 0,
                                "description": "x" * 100,
                            }
                        }
                    }
                }
            }
        }
        stalled = stalled_subtasks(dag, step=10, stall_threshold=5)
        self.assertEqual(len(stalled), 1)
        self.assertEqual(len(stalled[0]["description"]), 80)


class TestDagSummary(unittest.TestCase):
    """Test DAG summary statistics."""

    def test_empty_dag(self):
        """Empty DAG should have all zeros."""
        dag = {}
        summary = dag_summary(dag)
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["verified"], 0)
        self.assertEqual(summary["running"], 0)
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(summary["review"], 0)
        self.assertEqual(summary["failed"], 0)

    def test_single_verified(self):
        """Single verified subtask should be counted."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified"}
                        }
                    }
                }
            }
        }
        summary = dag_summary(dag)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["verified"], 1)
        self.assertEqual(summary["pending"], 0)

    def test_mixed_statuses(self):
        """All status types should be counted correctly."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified"},
                            "A2": {"status": "Running"},
                            "A3": {"status": "Pending"},
                            "A4": {"status": "Review"},
                            "A5": {"status": "Failed"},
                        }
                    }
                }
            }
        }
        summary = dag_summary(dag)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["verified"], 1)
        self.assertEqual(summary["running"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["review"], 1)
        self.assertEqual(summary["failed"], 1)

    def test_default_status_pending(self):
        """Missing status should default to Pending."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {}
                        }
                    }
                }
            }
        }
        summary = dag_summary(dag)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["pending"], 1)

    def test_multiple_branches(self):
        """Subtasks from multiple branches should be counted."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified"},
                            "A2": {"status": "Running"},
                        }
                    },
                    "Branch 2": {
                        "subtasks": {
                            "A3": {"status": "Pending"},
                        }
                    },
                }
            }
        }
        summary = dag_summary(dag)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["verified"], 1)
        self.assertEqual(summary["running"], 1)
        self.assertEqual(summary["pending"], 1)


class TestComputeRates(unittest.TestCase):
    """Test rate computation from history."""

    def test_empty_history(self):
        """Empty history should return 0 rates."""
        history = []
        rates = compute_rates(history)
        self.assertEqual(rates["verify_rate"], 0.0)
        self.assertEqual(rates["heal_rate"], 0.0)

    def test_single_entry(self):
        """Single history entry should compute rates."""
        history = [{"verified": 5, "healed": 2}]
        rates = compute_rates(history)
        self.assertEqual(rates["verify_rate"], 5.0)
        self.assertEqual(rates["heal_rate"], 2.0)

    def test_multiple_entries_under_window(self):
        """Multiple entries under 10-step window should average."""
        history = [
            {"verified": 10, "healed": 2},
            {"verified": 10, "healed": 2},
        ]
        rates = compute_rates(history)
        self.assertEqual(rates["verify_rate"], 10.0)
        self.assertEqual(rates["heal_rate"], 2.0)

    def test_window_limit(self):
        """History over 10 steps should use 10-step window."""
        history = [{"verified": i, "healed": 1} for i in range(20)]
        rates = compute_rates(history)
        expected_avg = sum(i for i in range(10, 20)) / 10
        self.assertAlmostEqual(rates["verify_rate"], expected_avg, places=1)

    def test_missing_fields_default_zero(self):
        """Missing fields should default to 0."""
        history = [{"verified": 5}, {"healed": 3}]
        rates = compute_rates(history)
        # avg = (5 + 0) / 2 = 2.5
        self.assertAlmostEqual(rates["verify_rate"], 2.5, places=1)


class TestForecastSummary(unittest.TestCase):
    """Test forecast summary generation."""

    def test_empty_dag(self):
        """Empty DAG should have zero progress."""
        dag = {}
        forecast = forecast_summary(dag, [])
        self.assertEqual(forecast["total"], 0)
        self.assertEqual(forecast["verified"], 0)
        self.assertEqual(forecast["pct"], 0.0)
        self.assertIsNone(forecast["eta_steps"])

    def test_partial_progress(self):
        """Partial completion should show correct pct."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified"},
                            "A2": {"status": "Pending"},
                        }
                    }
                }
            }
        }
        forecast = forecast_summary(dag, [], step=10)
        self.assertEqual(forecast["total"], 2)
        self.assertEqual(forecast["verified"], 1)
        self.assertEqual(forecast["pct"], 50.0)

    def test_eta_with_verify_rate(self):
        """ETA should be computed from verify rate."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified"},
                            "A2": {"status": "Pending"},
                        }
                    }
                }
            }
        }
        history = [{"verified": 1, "healed": 0} for _ in range(10)]
        forecast = forecast_summary(dag, history, step=10)
        # remaining = 1, verify_rate = 1.0, eta = 1
        self.assertEqual(forecast["eta_steps"], 1)

    def test_zero_verify_rate_eta_none(self):
        """Zero verify rate should result in None ETA."""
        dag = {
            "Task A": {
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Pending"},
                        }
                    }
                }
            }
        }
        history = [{"verified": 0, "healed": 0} for _ in range(10)]
        forecast = forecast_summary(dag, history)
        self.assertIsNone(forecast["eta_steps"])


class TestAgentStats(unittest.TestCase):
    """Test aggregated agent statistics."""

    def test_empty_state(self):
        """Empty state should have sensible defaults."""
        state = {}
        stats = agent_stats(state)
        self.assertEqual(stats["step"], 0)
        self.assertEqual(stats["healer"]["healed_total"], 0)
        self.assertEqual(stats["meta"]["history_len"], 0)

    def test_with_data(self):
        """State with data should populate stats."""
        state = {
            "step": 50,
            "healed_total": 3,
            "dag": {
                "Task A": {
                    "branches": {
                        "Branch 1": {
                            "subtasks": {
                                "A1": {"status": "Verified"},
                                "A2": {"status": "Running", "last_update": 10},
                            }
                        }
                    }
                }
            },
            "meta_history": [{"verified": 1, "healed": 0}] * 10,
        }
        stats = agent_stats(state, stall_threshold=5)
        self.assertEqual(stats["step"], 50)
        self.assertEqual(stats["healer"]["healed_total"], 3)
        self.assertEqual(stats["meta"]["history_len"], 10)
        self.assertEqual(stats["forecast"]["total"], 2)
        self.assertEqual(stats["forecast"]["verified"], 1)

    def test_stalled_count(self):
        """Agent stats should include currently stalled count."""
        state = {
            "step": 50,
            "dag": {
                "Task A": {
                    "branches": {
                        "Branch 1": {
                            "subtasks": {
                                "A1": {
                                    "status": "Running",
                                    "last_update": 10,
                                },
                            }
                        }
                    }
                }
            },
        }
        stats = agent_stats(state, stall_threshold=5)
        self.assertEqual(stats["healer"]["currently_stalled"], 1)

    def test_backward_compatibility(self):
        """Missing optional state keys should not cause errors."""
        state = {
            "step": 10,
            "dag": {},
        }
        stats = agent_stats(state)
        self.assertEqual(stats["reliability"]["recovery_count"], 0)
        self.assertEqual(stats["usage"]["total_calls"], 0)
        self.assertEqual(stats["policy"]["policy_block_count"], 0)


class TestPerTaskStats(unittest.TestCase):
    """Test per-task statistics."""

    def test_empty_dag(self):
        """Empty DAG should have zero grand totals."""
        dag = {}
        stats = per_task_stats(dag)
        self.assertEqual(stats["grand_total"], 0)
        self.assertEqual(stats["grand_verified"], 0)
        self.assertIsNone(stats["grand_avg_steps"])

    def test_single_task_partial(self):
        """Single task with mixed status should show pct."""
        dag = {
            "Task A": {
                "status": "Running",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified"},
                            "A2": {"status": "Pending"},
                        }
                    }
                },
            }
        }
        stats = per_task_stats(dag)
        self.assertEqual(len(stats["tasks"]), 1)
        self.assertEqual(stats["tasks"][0]["verified"], 1)
        self.assertEqual(stats["tasks"][0]["total"], 2)
        self.assertEqual(stats["tasks"][0]["pct"], 50.0)

    def test_multiple_tasks(self):
        """Multiple tasks should be aggregated correctly."""
        dag = {
            "Task A": {
                "status": "Running",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {"status": "Verified"},
                            "A2": {"status": "Verified"},
                        }
                    }
                },
            },
            "Task B": {
                "status": "Pending",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "B1": {"status": "Pending"},
                        }
                    }
                },
            },
        }
        stats = per_task_stats(dag)
        self.assertEqual(len(stats["tasks"]), 2)
        self.assertEqual(stats["grand_total"], 3)
        self.assertEqual(stats["grand_verified"], 2)

    def test_avg_steps_calculation(self):
        """Average steps should be computed from history."""
        dag = {
            "Task A": {
                "status": "Running",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Verified",
                                "history": [
                                    {"step": 0},
                                    {"step": 10},
                                ],
                            },
                        }
                    }
                },
            }
        }
        stats = per_task_stats(dag)
        self.assertEqual(stats["tasks"][0]["avg_steps"], 10.0)

    def test_avg_steps_multiple_runs(self):
        """Average steps should average over multiple subtasks."""
        dag = {
            "Task A": {
                "status": "Running",
                "branches": {
                    "Branch 1": {
                        "subtasks": {
                            "A1": {
                                "status": "Verified",
                                "history": [{"step": 0}, {"step": 10}],
                            },
                            "A2": {
                                "status": "Verified",
                                "history": [{"step": 0}, {"step": 20}],
                            },
                        }
                    }
                },
            }
        }
        stats = per_task_stats(dag)
        self.assertEqual(stats["tasks"][0]["avg_steps"], 15.0)


if __name__ == "__main__":
    unittest.main()
