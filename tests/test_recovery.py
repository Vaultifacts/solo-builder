"""
tests/test_recovery.py
Tests for crash-safe persistence, backup fallback, resume integrity,
and recovery metadata.
"""

import json
import os
import pytest

from core.persistence import (
    apply_backward_compat_defaults,
    check_resume_integrity,
    load_state_from_disk,
    save_state_to_disk,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minimal_state(step=5, subtask_statuses=None):
    """Build a minimal valid state payload."""
    if subtask_statuses is None:
        subtask_statuses = {"ST1": "Pending", "ST2": "Running"}
    sts = {
        name: {
            "status": s,
            "shadow": "Done" if s == "Verified" else "Pending",
            "last_update": step - 1,
            "description": f"Subtask {name}",
            "output": "some output" if s in ("Running", "Verified", "Review") else "",
        }
        for name, s in subtask_statuses.items()
    }
    return {
        "step": step,
        "snapshot_counter": 0,
        "healed_total": 0,
        "dag": {
            "T1": {
                "status": "Pending",
                "depends_on": [],
                "branches": {
                    "B1": {
                        "status": "Pending",
                        "subtasks": sts,
                    },
                },
            },
        },
        "memory_store": {"B1": []},
        "alerts": [],
        "meta_history": [],
        "safety_state": {},
    }


# ── Atomic save ───────────────────────────────────────────────────────────────

class TestAtomicSave:
    def test_save_creates_valid_json(self, tmp_path):
        p = str(tmp_path / "state.json")
        payload = _minimal_state()
        assert save_state_to_disk(p, payload) is True
        loaded = json.loads(open(p).read())
        assert loaded["step"] == 5

    def test_save_creates_parent_dirs(self, tmp_path):
        p = str(tmp_path / "sub" / "deep" / "state.json")
        assert save_state_to_disk(p, {"step": 1}) is True
        assert os.path.exists(p)

    def test_no_temp_file_left_on_success(self, tmp_path):
        p = str(tmp_path / "state.json")
        save_state_to_disk(p, {"step": 1})
        files = os.listdir(str(tmp_path))
        temp_files = [f for f in files if f.startswith(".state_tmp_")]
        assert temp_files == []

    def test_backup_rotation_with_atomic_save(self, tmp_path):
        p = str(tmp_path / "state.json")
        save_state_to_disk(p, {"v": 1})
        save_state_to_disk(p, {"v": 2})
        save_state_to_disk(p, {"v": 3})
        # current = v3, .1 = v2, .2 = v1
        assert json.loads(open(p).read())["v"] == 3
        assert json.loads(open(f"{p}.1").read())["v"] == 2
        assert json.loads(open(f"{p}.2").read())["v"] == 1


# ── Backup fallback ──────────────────────────────────────────────────────────

class TestBackupFallback:
    def test_loads_current_when_valid(self, tmp_path):
        p = str(tmp_path / "state.json")
        save_state_to_disk(p, {"step": 10})
        data = load_state_from_disk(p)
        assert data is not None
        assert data["step"] == 10
        assert "_recovery_source" not in data

    def test_falls_back_to_backup1(self, tmp_path):
        p = str(tmp_path / "state.json")
        # Create good backup.1 then corrupt current
        save_state_to_disk(p, {"step": 8})
        save_state_to_disk(p, {"step": 9})
        # Now current=9, backup.1=8 — corrupt current
        with open(p, "w") as f:
            f.write("{corrupt")
        data = load_state_from_disk(p)
        assert data is not None
        assert data["step"] == 8
        assert data["_recovery_source"] == "backup.1"

    def test_falls_back_to_backup2(self, tmp_path):
        p = str(tmp_path / "state.json")
        save_state_to_disk(p, {"step": 7})
        save_state_to_disk(p, {"step": 8})
        save_state_to_disk(p, {"step": 9})
        # Corrupt current and backup.1
        with open(p, "w") as f:
            f.write("{corrupt")
        with open(f"{p}.1", "w") as f:
            f.write("{also corrupt")
        data = load_state_from_disk(p)
        assert data is not None
        assert data["step"] == 7
        assert data["_recovery_source"] == "backup.2"

    def test_returns_none_when_all_corrupt(self, tmp_path):
        p = str(tmp_path / "state.json")
        save_state_to_disk(p, {"step": 1})
        with open(p, "w") as f:
            f.write("corrupt")
        # No backups exist (only one save)
        data = load_state_from_disk(p)
        assert data is None

    def test_no_fallback_when_disabled(self, tmp_path):
        p = str(tmp_path / "state.json")
        save_state_to_disk(p, {"step": 5})
        save_state_to_disk(p, {"step": 6})
        with open(p, "w") as f:
            f.write("corrupt")
        data = load_state_from_disk(p, fallback_to_backup=False)
        assert data is None

    def test_returns_none_when_missing(self, tmp_path):
        p = str(tmp_path / "nonexistent.json")
        assert load_state_from_disk(p) is None


# ── Recovery metadata backward compatibility ──────────────────────────────────

class TestRecoveryMetadataCompat:
    def test_old_state_gets_defaults(self):
        payload = {"step": 5}
        apply_backward_compat_defaults(payload)
        rs = payload["recovery_state"]
        assert rs["last_completed_step"] == 0
        assert rs["last_started_step"] == 0
        assert rs["last_save_step"] == 0
        assert rs["last_failed_phase"] is None
        assert rs["recovery_count"] == 0
        assert rs["last_recovery_source"] is None
        assert rs["malformed_trigger_count"] == 0
        assert rs["persistence_fallback_count"] == 0
        assert rs["partial_work_repair_count"] == 0
        assert rs["phase_failures"] == []

    def test_existing_recovery_state_preserved(self):
        payload = {
            "recovery_state": {
                "recovery_count": 3,
                "last_failed_phase": "Executor",
            },
        }
        apply_backward_compat_defaults(payload)
        rs = payload["recovery_state"]
        assert rs["recovery_count"] == 3
        assert rs["last_failed_phase"] == "Executor"
        # Defaults filled for missing keys
        assert rs["malformed_trigger_count"] == 0


# ── Resume integrity checks ──────────────────────────────────────────────────

class TestResumeIntegrity:
    def test_valid_state_no_issues(self):
        state = _minimal_state(step=5, subtask_statuses={"ST1": "Pending"})
        issues = check_resume_integrity(state, repair=True)
        assert issues == []

    def test_invalid_status_repaired(self):
        state = _minimal_state()
        state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]["status"] = "BOGUS"
        issues = check_resume_integrity(state, repair=True)
        assert len(issues) == 1
        assert "BOGUS" in issues[0]
        assert "Pending" in issues[0]
        assert state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]["status"] == "Pending"

    def test_broken_dep_repaired(self):
        state = _minimal_state()
        state["dag"]["T1"]["depends_on"] = ["NONEXISTENT"]
        issues = check_resume_integrity(state, repair=True)
        assert any("NONEXISTENT" in i for i in issues)
        assert state["dag"]["T1"]["depends_on"] == []

    def test_missing_field_repaired(self):
        state = _minimal_state()
        del state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]["shadow"]
        issues = check_resume_integrity(state, repair=True)
        assert any("shadow" in i for i in issues)
        assert state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]["shadow"] == "Pending"

    def test_running_no_output_repaired(self):
        state = _minimal_state(step=10, subtask_statuses={"ST1": "Running"})
        st = state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]
        st["output"] = ""
        st["last_update"] = 5
        issues = check_resume_integrity(state, repair=True)
        assert any("Running with no output" in i for i in issues)
        assert st["status"] == "Pending"

    def test_running_with_output_not_repaired(self):
        state = _minimal_state(step=10, subtask_statuses={"ST1": "Running"})
        st = state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]
        st["output"] = "some work was done"
        st["last_update"] = 5
        issues = check_resume_integrity(state, repair=True)
        running_issues = [i for i in issues if "Running with no output" in i]
        assert running_issues == []
        assert st["status"] == "Running"

    def test_branch_rollup_repaired(self):
        state = _minimal_state(subtask_statuses={"ST1": "Verified", "ST2": "Verified"})
        # Branch status is still "Pending" but all subtasks verified
        assert state["dag"]["T1"]["branches"]["B1"]["status"] == "Pending"
        issues = check_resume_integrity(state, repair=True)
        assert any("branch Verified" in i for i in issues)
        assert state["dag"]["T1"]["branches"]["B1"]["status"] == "Verified"

    def test_task_rollup_repaired(self):
        state = _minimal_state(subtask_statuses={"ST1": "Verified"})
        state["dag"]["T1"]["branches"]["B1"]["status"] = "Verified"
        # Task status still "Pending"
        issues = check_resume_integrity(state, repair=True)
        assert any("task Verified" in i for i in issues)
        assert state["dag"]["T1"]["status"] == "Verified"

    def test_fatal_corruption_detected(self):
        state = _minimal_state()
        state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"] = "not a dict"
        issues = check_resume_integrity(state, repair=True)
        assert any(i.startswith("FATAL:") for i in issues)

    def test_no_repair_mode(self):
        state = _minimal_state()
        state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]["status"] = "BOGUS"
        issues = check_resume_integrity(state, repair=False)
        assert len(issues) >= 1
        # Status should NOT be changed
        assert state["dag"]["T1"]["branches"]["B1"]["subtasks"]["ST1"]["status"] == "BOGUS"
