"""
tests/test_reliability_runtime.py
Tests for phase failure isolation, malformed trigger handling,
trigger quarantine, and reliability observability.
"""

import json
import os
import pytest

from core.triggers import consume_json_trigger
from utils.runtime_views import agent_stats


# ── Malformed trigger quarantine ──────────────────────────────────────────────

class TestTriggerQuarantine:
    def test_malformed_json_quarantined(self, tmp_path):
        p = str(tmp_path / "trigger.json")
        with open(p, "w") as f:
            f.write("{bad json!!!")
        result = consume_json_trigger(p, quarantine=True)
        assert result is None
        assert not os.path.exists(p)
        assert os.path.exists(p + ".bad")
        # Quarantined content preserved for inspection
        assert open(p + ".bad").read() == "{bad json!!!"

    def test_malformed_json_deleted_when_no_quarantine(self, tmp_path):
        p = str(tmp_path / "trigger.json")
        with open(p, "w") as f:
            f.write("{bad}")
        result = consume_json_trigger(p, quarantine=False)
        assert result is None
        assert not os.path.exists(p)
        assert not os.path.exists(p + ".bad")

    def test_valid_json_not_quarantined(self, tmp_path):
        p = str(tmp_path / "trigger.json")
        with open(p, "w") as f:
            json.dump({"task": "T1"}, f)
        result = consume_json_trigger(p, quarantine=True)
        assert result == {"task": "T1"}
        assert not os.path.exists(p)
        assert not os.path.exists(p + ".bad")

    def test_empty_file_quarantined(self, tmp_path):
        p = str(tmp_path / "trigger.json")
        with open(p, "w") as f:
            pass  # empty
        result = consume_json_trigger(p, quarantine=True)
        assert result is None
        assert os.path.exists(p + ".bad")

    def test_missing_file_returns_none(self, tmp_path):
        p = str(tmp_path / "missing.json")
        result = consume_json_trigger(p, quarantine=True)
        assert result is None

    def test_partial_json_quarantined(self, tmp_path):
        p = str(tmp_path / "trigger.json")
        with open(p, "w") as f:
            f.write('{"subtask": "ST1", "note":')
        result = consume_json_trigger(p, quarantine=True)
        assert result is None
        assert os.path.exists(p + ".bad")


# ── Phase failure alerting ────────────────────────────────────────────────────

class TestPhaseFailureAlerting:
    """Test that _run_phase handles fail-open and fail-closed correctly."""

    def test_fail_open_returns_none(self):
        """A fail-open phase that raises should return None and not re-raise."""
        from unittest.mock import MagicMock

        # Build a minimal mock CLI object with _run_phase
        cli = MagicMock()
        cli.step = 5
        cli._recovery_state = {
            "last_failed_phase": None,
            "phase_failures": [],
        }

        # Import and bind _run_phase from SoloBuilderCLI
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from solo_builder_cli import SoloBuilderCLI

        alerts = []
        result = SoloBuilderCLI._run_phase(
            cli, "TestPhase",
            lambda: (_ for _ in ()).throw(ValueError("test error")),
            alerts,
            fail_open=True,
        )
        assert result is None
        assert len(alerts) == 1
        assert "TestPhase" in alerts[0]
        assert "test error" in alerts[0]
        assert cli._recovery_state["last_failed_phase"] == "TestPhase"

    def test_fail_closed_re_raises(self):
        """A fail-closed phase should re-raise after recording the failure."""
        from unittest.mock import MagicMock
        from solo_builder_cli import SoloBuilderCLI

        cli = MagicMock()
        cli.step = 5
        cli._recovery_state = {
            "last_failed_phase": None,
            "phase_failures": [],
        }
        alerts = []
        with pytest.raises(ValueError, match="critical"):
            SoloBuilderCLI._run_phase(
                cli, "Verifier",
                lambda: (_ for _ in ()).throw(ValueError("critical")),
                alerts,
                fail_open=False,
            )
        assert cli._recovery_state["last_failed_phase"] == "Verifier"
        assert len(alerts) == 1

    def test_success_returns_value(self):
        """A successful phase should return the function's return value."""
        from unittest.mock import MagicMock
        from solo_builder_cli import SoloBuilderCLI

        cli = MagicMock()
        cli.step = 1
        cli._recovery_state = {"last_failed_phase": None, "phase_failures": []}
        alerts = []
        result = SoloBuilderCLI._run_phase(
            cli, "Planner", lambda: [1, 2, 3], alerts, fail_open=True,
        )
        assert result == [1, 2, 3]
        assert alerts == []


# ── Phase failure history ─────────────────────────────────────────────────────

class TestPhaseFailureHistory:
    def test_failures_capped_at_20(self):
        from unittest.mock import MagicMock
        from solo_builder_cli import SoloBuilderCLI

        cli = MagicMock()
        cli._recovery_state = {
            "last_failed_phase": None,
            "phase_failures": [{"step": i} for i in range(20)],
        }
        cli.step = 99
        alerts = []
        SoloBuilderCLI._run_phase(
            cli, "X", lambda: 1/0, alerts, fail_open=True,
        )
        assert len(cli._recovery_state["phase_failures"]) == 20
        assert cli._recovery_state["phase_failures"][-1]["step"] == 99


# ── Reliability observability in agent_stats ──────────────────────────────────

class TestReliabilityStats:
    def test_reliability_present_in_agent_stats(self):
        state = {
            "step": 10,
            "dag": {},
            "healed_total": 0,
            "meta_history": [],
            "safety_state": {},
            "recovery_state": {
                "recovery_count": 2,
                "last_failed_phase": "Executor",
                "last_recovery_source": "backup.1",
                "malformed_trigger_count": 3,
                "persistence_fallback_count": 1,
                "partial_work_repair_count": 4,
            },
        }
        stats = agent_stats(state)
        rel = stats["reliability"]
        assert rel["recovery_count"] == 2
        assert rel["last_failed_phase"] == "Executor"
        assert rel["last_recovery_source"] == "backup.1"
        assert rel["malformed_trigger_count"] == 3
        assert rel["persistence_fallback_count"] == 1
        assert rel["partial_work_repair_count"] == 4

    def test_reliability_defaults_for_old_state(self):
        state = {
            "step": 5,
            "dag": {},
            "healed_total": 0,
            "meta_history": [],
            "safety_state": {},
        }
        stats = agent_stats(state)
        rel = stats["reliability"]
        assert rel["recovery_count"] == 0
        assert rel["last_failed_phase"] is None
        assert rel["malformed_trigger_count"] == 0

    def test_reliability_with_missing_recovery_state(self):
        state = {"step": 1, "dag": {}, "meta_history": []}
        stats = agent_stats(state)
        assert "reliability" in stats
        assert stats["reliability"]["recovery_count"] == 0
