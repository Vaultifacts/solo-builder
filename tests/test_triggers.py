"""
tests/test_triggers.py
Unit tests for core/triggers.py — trigger path registry, consume/write helpers,
cleanup, malformed payloads.
"""

import json
import os
import pytest

from core.triggers import (
    TRIGGER_FILES,
    all_trigger_paths,
    cleanup_stale_triggers,
    consume_flag_trigger,
    consume_json_trigger,
    trigger_exists,
    trigger_path,
    write_flag_trigger,
)


# ── trigger_path / all_trigger_paths ──────────────────────────────────────────

class TestTriggerPath:
    def test_known_trigger(self):
        p = trigger_path("/app/state", "run")
        assert p == "/app/state/run_trigger"

    def test_json_trigger(self):
        p = trigger_path("/app/state", "add_task")
        assert p == "/app/state/add_task_trigger.json"

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            trigger_path("/app/state", "nonexistent")

    def test_all_trigger_paths(self):
        paths = all_trigger_paths("/s")
        assert len(paths) == len(TRIGGER_FILES)
        assert paths["run"] == "/s/run_trigger"
        assert paths["verify"] == "/s/verify_trigger.json"


# ── consume_json_trigger ──────────────────────────────────────────────────────

class TestConsumeJsonTrigger:
    def test_reads_and_deletes(self, tmp_path):
        p = str(tmp_path / "trig.json")
        with open(p, "w") as f:
            json.dump({"subtask": "ST1"}, f)
        result = consume_json_trigger(p)
        assert result == {"subtask": "ST1"}
        assert not os.path.exists(p)

    def test_returns_none_missing(self, tmp_path):
        assert consume_json_trigger(str(tmp_path / "nope.json")) is None

    def test_returns_none_malformed(self, tmp_path):
        p = str(tmp_path / "bad.json")
        with open(p, "w") as f:
            f.write("{broken json")
        assert consume_json_trigger(p) is None

    def test_handles_list_payload(self, tmp_path):
        p = str(tmp_path / "list.json")
        with open(p, "w") as f:
            json.dump([{"a": 1}, {"b": 2}], f)
        result = consume_json_trigger(p)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_empty_file(self, tmp_path):
        p = str(tmp_path / "empty.json")
        with open(p, "w") as f:
            pass
        assert consume_json_trigger(p) is None


# ── consume_flag_trigger ──────────────────────────────────────────────────────

class TestConsumeFlagTrigger:
    def test_consumes_existing(self, tmp_path):
        p = str(tmp_path / "flag")
        with open(p, "w") as f:
            f.write("1")
        assert consume_flag_trigger(p) is True
        assert not os.path.exists(p)

    def test_returns_false_missing(self, tmp_path):
        assert consume_flag_trigger(str(tmp_path / "nope")) is False


# ── write_flag_trigger ────────────────────────────────────────────────────────

class TestWriteFlagTrigger:
    def test_creates_file(self, tmp_path):
        p = str(tmp_path / "flag")
        write_flag_trigger(p)
        assert os.path.exists(p)

    def test_creates_parent_dirs(self, tmp_path):
        p = str(tmp_path / "sub" / "deep" / "flag")
        write_flag_trigger(p)
        assert os.path.exists(p)


# ── trigger_exists ────────────────────────────────────────────────────────────

class TestTriggerExists:
    def test_true_when_exists(self, tmp_path):
        p = str(tmp_path / "flag")
        with open(p, "w") as f:
            f.write("1")
        assert trigger_exists(p) is True

    def test_false_when_missing(self, tmp_path):
        assert trigger_exists(str(tmp_path / "nope")) is False


# ── cleanup_stale_triggers ────────────────────────────────────────────────────

class TestCleanupStaleTriggers:
    def test_removes_all(self, tmp_path):
        sd = str(tmp_path)
        # Create all trigger files
        for filename in TRIGGER_FILES.values():
            with open(os.path.join(sd, filename), "w") as f:
                f.write("1")
        removed = cleanup_stale_triggers(sd)
        assert removed == len(TRIGGER_FILES)
        for filename in TRIGGER_FILES.values():
            assert not os.path.exists(os.path.join(sd, filename))

    def test_exclude_skips(self, tmp_path):
        sd = str(tmp_path)
        with open(os.path.join(sd, "verify_trigger.json"), "w") as f:
            f.write("1")
        with open(os.path.join(sd, "run_trigger"), "w") as f:
            f.write("1")
        removed = cleanup_stale_triggers(sd, exclude=["verify"])
        assert os.path.exists(os.path.join(sd, "verify_trigger.json"))
        assert not os.path.exists(os.path.join(sd, "run_trigger"))
        assert removed == 1

    def test_noop_empty_dir(self, tmp_path):
        sd = str(tmp_path / "empty")
        removed = cleanup_stale_triggers(sd)
        assert removed == 0
        assert os.path.isdir(sd)  # creates dir

    def test_creates_state_dir(self, tmp_path):
        sd = str(tmp_path / "new_state")
        cleanup_stale_triggers(sd)
        assert os.path.isdir(sd)
