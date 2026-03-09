"""
Standalone pytest-style unit tests for pure utility functions.
These run with both pytest and unittest discover (no class needed).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helper_functions import (
    dag_stats, branch_stats, shadow_stats, make_bar,
    memory_depth, add_memory_snapshot, clamp, validate_dag,
    load_settings,
)


# ── dag_stats ─────────────────────────────────────────────────────────────────

def test_dag_stats_empty_dag():
    result = dag_stats({})
    assert result == {"total": 0, "pending": 0, "running": 0, "review": 0, "verified": 0}


def test_dag_stats_single_pending():
    dag = {"T1": {"branches": {"A": {"subtasks": {"A1": {"status": "Pending"}}}}}}
    s = dag_stats(dag)
    assert s["total"] == 1
    assert s["pending"] == 1
    assert s["verified"] == 0


def test_dag_stats_all_statuses():
    dag = {"T": {"branches": {"B": {"subtasks": {
        "A1": {"status": "Pending"},
        "A2": {"status": "Running"},
        "A3": {"status": "Review"},
        "A4": {"status": "Verified"},
    }}}}}
    s = dag_stats(dag)
    assert s["total"] == 4
    assert s["pending"] == 1
    assert s["running"] == 1
    assert s["review"] == 1
    assert s["verified"] == 1


def test_dag_stats_unknown_status_not_counted():
    dag = {"T": {"branches": {"B": {"subtasks": {"A1": {"status": "Unknown"}}}}}}
    s = dag_stats(dag)
    assert s["total"] == 1
    assert s["pending"] == 0
    assert s["running"] == 0
    assert s["verified"] == 0


def test_dag_stats_missing_status_defaults_to_pending_bucket():
    dag = {"T": {"branches": {"B": {"subtasks": {"A1": {}}}}}}
    s = dag_stats(dag)
    assert s["total"] == 1
    assert s["pending"] == 1


# ── branch_stats ──────────────────────────────────────────────────────────────

def test_branch_stats_empty():
    v, r, t = branch_stats({"subtasks": {}})
    assert (v, r, t) == (0, 0, 0)


def test_branch_stats_mixed():
    bd = {"subtasks": {
        "A1": {"status": "Verified"},
        "A2": {"status": "Running"},
        "A3": {"status": "Pending"},
    }}
    v, r, t = branch_stats(bd)
    assert v == 1
    assert r == 1
    assert t == 3


# ── make_bar ──────────────────────────────────────────────────────────────────

def test_make_bar_full():
    bar = make_bar(10, 10, width=10)
    assert bar == "=" * 10


def test_make_bar_empty():
    bar = make_bar(0, 10, width=10)
    assert bar == "-" * 10


def test_make_bar_zero_total():
    bar = make_bar(0, 0, width=5)
    assert bar == "-" * 5


def test_make_bar_partial():
    bar = make_bar(5, 10, width=10)
    assert len(bar) == 10


def test_make_bar_custom_chars():
    bar = make_bar(4, 4, char="#", empty=".", width=4)
    assert bar == "####"


# ── clamp ─────────────────────────────────────────────────────────────────────

def test_clamp_within_range():
    assert clamp(5, 0, 10) == 5


def test_clamp_below_min():
    assert clamp(-1, 0, 10) == 0


def test_clamp_above_max():
    assert clamp(15, 0, 10) == 10


def test_clamp_at_boundary():
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10


# ── memory helpers ────────────────────────────────────────────────────────────

def test_memory_depth_empty():
    assert memory_depth({}, "branch_a") == 0


def test_memory_depth_after_snapshot():
    store = {}
    add_memory_snapshot(store, "branch_a", "snap1", step=1)
    assert memory_depth(store, "branch_a") == 1


def test_add_memory_snapshot_structure():
    store = {}
    add_memory_snapshot(store, "B", "label", step=42)
    assert store["B"][0]["snapshot"] == "label"
    assert store["B"][0]["timestamp"] == 42


# ── validate_dag ──────────────────────────────────────────────────────────────

def test_validate_dag_clean():
    dag = {"T": {"branches": {"A": {"subtasks": {
        "A1": {"status": "Verified", "shadow": "Done"},
    }}}}}
    warnings = validate_dag(dag)
    assert warnings == []


def test_validate_dag_missing_branches():
    dag = {"T": {}}
    warnings = validate_dag(dag)
    assert any("branches" in w for w in warnings)


def test_validate_dag_invalid_status():
    dag = {"T": {"branches": {"A": {"subtasks": {
        "A1": {"status": "Bogus", "shadow": "Pending"},
    }}}}}
    warnings = validate_dag(dag)
    assert any("invalid status" in w for w in warnings)


# ── shadow_stats ──────────────────────────────────────────────────────────────

def test_shadow_stats_empty():
    d, t = shadow_stats({"subtasks": {}})
    assert d == 0 and t == 0


def test_shadow_stats_done():
    bd = {"subtasks": {
        "A1": {"shadow": "Done"},
        "A2": {"shadow": "Pending"},
    }}
    d, t = shadow_stats(bd)
    assert d == 1
    assert t == 2


# ── load_settings ─────────────────────────────────────────────────────────────

def test_load_settings_returns_defaults_when_no_file():
    settings = load_settings("/nonexistent/path/settings.json")
    assert "STALL_THRESHOLD" in settings
    assert isinstance(settings["STALL_THRESHOLD"], int)


def test_load_settings_stall_threshold_default():
    settings = load_settings("/nonexistent/path/settings.json")
    assert settings["STALL_THRESHOLD"] == 5


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
