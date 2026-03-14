"""
tests/test_persistence.py
Unit tests for core/persistence.py — state I/O, backup rotation, heartbeat,
backward-compatible defaults.
"""

import json
import os
import pytest

from core.persistence import (
    apply_backward_compat_defaults,
    load_state_from_disk,
    rotate_backups,
    save_state_to_disk,
    write_heartbeat,
)


# ── rotate_backups ────────────────────────────────────────────────────────────

class TestRotateBackups:
    def test_creates_dot1_from_current(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("current")
        rotate_backups(str(p))
        assert (tmp_path / "state.json.1").read_text() == "current"

    def test_shifts_existing_backups(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("v3")
        (tmp_path / "state.json.1").write_text("v2")
        (tmp_path / "state.json.2").write_text("v1")
        rotate_backups(str(p))
        assert (tmp_path / "state.json.1").read_text() == "v3"
        assert (tmp_path / "state.json.2").read_text() == "v2"
        assert (tmp_path / "state.json.3").read_text() == "v1"

    def test_drops_dot3_on_overflow(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("v4")
        (tmp_path / "state.json.1").write_text("v3")
        (tmp_path / "state.json.2").write_text("v2")
        (tmp_path / "state.json.3").write_text("v1-old")
        rotate_backups(str(p))
        assert (tmp_path / "state.json.3").read_text() == "v2"

    def test_noop_when_no_file(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        rotate_backups(str(p))  # should not raise


# ── save_state_to_disk ────────────────────────────────────────────────────────

class TestSaveState:
    def test_writes_json(self, tmp_path):
        p = str(tmp_path / "state.json")
        payload = {"step": 5, "dag": {"T1": {}}}
        assert save_state_to_disk(p, payload) is True
        loaded = json.loads(open(p).read())
        assert loaded["step"] == 5

    def test_creates_parent_dirs(self, tmp_path):
        p = str(tmp_path / "sub" / "deep" / "state.json")
        assert save_state_to_disk(p, {"x": 1}) is True
        assert os.path.exists(p)

    def test_rotates_before_write(self, tmp_path):
        p = str(tmp_path / "state.json")
        save_state_to_disk(p, {"v": 1})
        save_state_to_disk(p, {"v": 2})
        backup = json.loads(open(f"{p}.1").read())
        assert backup["v"] == 1


# ── load_state_from_disk ──────────────────────────────────────────────────────

class TestLoadState:
    def test_loads_valid_json(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps({"step": 10}))
        result = load_state_from_disk(str(p))
        assert result["step"] == 10

    def test_returns_none_missing(self, tmp_path):
        assert load_state_from_disk(str(tmp_path / "nope.json")) is None

    def test_returns_none_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{broken")
        assert load_state_from_disk(str(p)) is None


# ── apply_backward_compat_defaults ────────────────────────────────────────────

class TestBackwardCompatDefaults:
    def test_adds_missing_keys(self):
        payload = {}
        result = apply_backward_compat_defaults(payload)
        assert result["meta_history"] == []
        assert "safety_state" in result
        ss = result["safety_state"]
        assert ss["dynamic_tasks_created"] == 0
        assert ss["ra_last_run_step"] == -1
        assert ss["patch_rejections"] == {}
        assert ss["patch_threshold_hits"] == 0

    def test_preserves_existing(self):
        payload = {
            "meta_history": [{"x": 1}],
            "safety_state": {"dynamic_tasks_created": 5, "custom": True},
        }
        result = apply_backward_compat_defaults(payload)
        assert len(result["meta_history"]) == 1
        assert result["safety_state"]["dynamic_tasks_created"] == 5
        assert result["safety_state"]["custom"] is True
        # sub-defaults still filled
        assert result["safety_state"]["ra_last_run_step"] == -1

    def test_mutates_in_place(self):
        payload = {}
        result = apply_backward_compat_defaults(payload)
        assert result is payload


# ── write_heartbeat ───────────────────────────────────────────────────────────

class TestWriteHeartbeat:
    def _make_dag(self, statuses):
        """Build a minimal DAG with given subtask statuses."""
        sts = {f"ST{i}": {"status": s} for i, s in enumerate(statuses)}
        return {"T1": {"branches": {"B1": {"subtasks": sts}}}}

    def test_basic_counts(self, tmp_path):
        hb = str(tmp_path / "step.txt")
        dag = self._make_dag(["Verified", "Pending", "Running", "Review", "Verified"])
        write_heartbeat(hb, 42, dag)
        parts = open(hb).read().split(",")
        assert parts == ["42", "2", "5", "1", "1", "1"]

    def test_empty_dag(self, tmp_path):
        hb = str(tmp_path / "step.txt")
        write_heartbeat(hb, 0, {})
        assert open(hb).read() == "0,0,0,0,0,0"

    def test_all_verified(self, tmp_path):
        hb = str(tmp_path / "step.txt")
        dag = self._make_dag(["Verified", "Verified", "Verified"])
        write_heartbeat(hb, 10, dag)
        parts = open(hb).read().split(",")
        assert parts[1] == "3"  # verified
        assert parts[2] == "3"  # total
