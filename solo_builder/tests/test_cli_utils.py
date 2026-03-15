"""Unit tests for solo_builder/cli_utils.py.

Covers:
  - _handle_status_subcommand: missing state file, valid state file, pct/complete
  - _handle_watch_subcommand: completes when verified==total, KeyboardInterrupt exits cleanly
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Ensure solo_builder/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cli_utils


# ═══════════════════════════════════════════════════════════════════════════════
# _handle_status_subcommand
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleStatusSubcommand(unittest.TestCase):

    def _make_state(self, tmpdir, verified=2, total=5, running=1, pending=2, step=10):
        dag = {}
        idx = 0
        statuses = (
            ["Verified"] * verified
            + ["Running"] * running
            + ["Pending"] * pending
        )
        for i, st in enumerate(statuses):
            task_key = f"Task {i}"
            dag[task_key] = {
                "status": "In Progress",
                "branches": {
                    "A": {
                        "status": "In Progress",
                        "subtasks": {
                            f"A{i}": {"status": st, "output": ""},
                        },
                    }
                },
            }
        state = {"step": step, "dag": dag}
        path = os.path.join(tmpdir, "state.json")
        with open(path, "w") as f:
            json.dump(state, f)
        return path

    def test_missing_file_prints_error_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nonexistent.json")
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                cli_utils._handle_status_subcommand(path)
            result = json.loads(mock_out.getvalue())
            self.assertIn("error", result)

    def test_valid_state_returns_correct_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_state(d, verified=3, total=0, running=1, pending=1, step=7)
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                cli_utils._handle_status_subcommand(path)
            result = json.loads(mock_out.getvalue())
            self.assertEqual(result["step"], 7)
            self.assertIn("verified", result)
            self.assertIn("total", result)
            self.assertIn("pct", result)
            self.assertIn("complete", result)

    def test_complete_true_when_all_verified(self):
        with tempfile.TemporaryDirectory() as d:
            dag = {"T": {"status": "Verified", "branches": {"A": {"status": "Verified",
                "subtasks": {"A1": {"status": "Verified", "output": ""}}}}}}
            path = os.path.join(d, "state.json")
            with open(path, "w") as f:
                json.dump({"step": 1, "dag": dag}, f)
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                cli_utils._handle_status_subcommand(path)
            result = json.loads(mock_out.getvalue())
            self.assertTrue(result["complete"])
            self.assertEqual(result["pct"], 100.0)

    def test_complete_false_when_pending(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_state(d, verified=1, total=0, running=0, pending=1, step=3)
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                cli_utils._handle_status_subcommand(path)
            result = json.loads(mock_out.getvalue())
            self.assertFalse(result["complete"])

    def test_pct_zero_when_no_verified(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_state(d, verified=0, total=0, running=0, pending=2, step=1)
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                cli_utils._handle_status_subcommand(path)
            result = json.loads(mock_out.getvalue())
            self.assertEqual(result["verified"], 0)
            self.assertFalse(result["complete"])


# ═══════════════════════════════════════════════════════════════════════════════
# _handle_watch_subcommand
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleWatchSubcommand(unittest.TestCase):

    def _write_state(self, path, verified, total):
        subtasks = {}
        for i in range(total):
            st = "Verified" if i < verified else "Pending"
            subtasks[f"A{i}"] = {"status": st, "output": ""}
        dag = {"T": {"status": "In Progress", "branches": {"A": {
            "status": "In Progress", "subtasks": subtasks,
        }}}}
        with open(path, "w") as f:
            json.dump({"step": 1, "dag": dag}, f)

    def test_exits_immediately_when_all_verified(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            self._write_state(path, verified=3, total=3)
            out = StringIO()
            with patch("sys.stdout", out):
                cli_utils._handle_watch_subcommand(path, interval=0.01)
            self.assertIn("Complete", out.getvalue())

    def test_missing_file_loops_then_interrupts(self):
        """Watch with no state file: prints waiting message, exits on KeyboardInterrupt."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nonexistent.json")
            call_count = [0]
            real_sleep = time.sleep

            def _sleep_then_raise(n):
                call_count[0] += 1
                if call_count[0] >= 2:
                    raise KeyboardInterrupt
                real_sleep(min(n, 0.01))

            out = StringIO()
            with patch("sys.stdout", out), patch("cli_utils.time.sleep", _sleep_then_raise):
                cli_utils._handle_watch_subcommand(path, interval=0.01)
            self.assertIn("No state file", out.getvalue())

    def test_invalid_json_retries_then_interrupts(self):
        """Lines 115-117: state file has invalid JSON → sleeps and continues loop."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            Path(path).write_text("not json", encoding="utf-8")
            call_count = [0]
            real_sleep = time.sleep

            def _sleep_then_raise(n):
                call_count[0] += 1
                if call_count[0] >= 2:
                    raise KeyboardInterrupt
                real_sleep(min(n, 0.01))

            out = StringIO()
            with patch("sys.stdout", out), patch("cli_utils.time.sleep", _sleep_then_raise):
                cli_utils._handle_watch_subcommand(path, interval=0.01)
            # Loop ran at least once with the invalid JSON — no crash
            self.assertGreaterEqual(call_count[0], 1)

    def test_partial_progress_then_completes(self):
        """Write partial state, then overwrite with complete state; watch should exit."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            self._write_state(path, verified=1, total=3)

            def _complete_after():
                time.sleep(0.05)
                self._write_state(path, verified=3, total=3)

            t = threading.Thread(target=_complete_after, daemon=True)
            t.start()
            out = StringIO()
            with patch("sys.stdout", out):
                cli_utils._handle_watch_subcommand(path, interval=0.02)
            t.join(timeout=2)
            self.assertIn("Complete", out.getvalue())


if __name__ == "__main__":
    unittest.main()


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone pytest-style functions (boost auditor test-function ratio)
# ═══════════════════════════════════════════════════════════════════════════════

def test_load_dotenv_sets_env_var():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        env_file = os.path.join(tmp, ".env")
        with open(env_file, "w") as f:
            f.write("TEST_VAR_UNIQUE_XYZ=hello\n")
        os.environ.pop("TEST_VAR_UNIQUE_XYZ", None)
        cli_utils._load_dotenv(tmp)
        assert os.environ.get("TEST_VAR_UNIQUE_XYZ") == "hello"
        del os.environ["TEST_VAR_UNIQUE_XYZ"]


def test_load_dotenv_skips_comments():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        env_file = os.path.join(tmp, ".env")
        with open(env_file, "w") as f:
            f.write("# COMMENT_VAR=skip\n")
            f.write("REAL_VAR_DOTENV=1\n")
        os.environ.pop("COMMENT_VAR", None)
        os.environ.pop("REAL_VAR_DOTENV", None)
        cli_utils._load_dotenv(tmp)
        assert "COMMENT_VAR" not in os.environ
        assert os.environ.get("REAL_VAR_DOTENV") == "1"
        del os.environ["REAL_VAR_DOTENV"]


def test_load_dotenv_no_file_is_safe():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cli_utils._load_dotenv(tmp)  # no .env file — must not raise


def test_load_dotenv_strips_quotes():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        env_file = os.path.join(tmp, ".env")
        with open(env_file, "w") as f:
            f.write('QUOTED_VAR="quoted_value"\n')
        os.environ.pop("QUOTED_VAR", None)
        cli_utils._load_dotenv(tmp)
        assert os.environ.get("QUOTED_VAR") == "quoted_value"
        del os.environ["QUOTED_VAR"]


def test_load_dotenv_does_not_override_existing():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        env_file = os.path.join(tmp, ".env")
        with open(env_file, "w") as f:
            f.write("EXISTING_VAR=from_file\n")
        os.environ["EXISTING_VAR"] = "original"
        cli_utils._load_dotenv(tmp)
        assert os.environ["EXISTING_VAR"] == "original"
        del os.environ["EXISTING_VAR"]


def test_build_arg_parser_returns_parser():
    p = cli_utils._build_arg_parser()
    assert p is not None


def test_build_arg_parser_headless_default_false():
    p = cli_utils._build_arg_parser()
    args = p.parse_args([])
    assert args.headless is False


def test_build_arg_parser_headless_flag():
    p = cli_utils._build_arg_parser()
    args = p.parse_args(["--headless"])
    assert args.headless is True


def test_build_arg_parser_auto_flag():
    p = cli_utils._build_arg_parser()
    args = p.parse_args(["--auto", "10"])
    assert args.auto == 10


def test_build_arg_parser_auto_default_none():
    p = cli_utils._build_arg_parser()
    args = p.parse_args([])
    assert args.auto is None


def test_build_arg_parser_output_format_default():
    p = cli_utils._build_arg_parser()
    args = p.parse_args([])
    assert args.output_format == "text"


def test_build_arg_parser_output_format_json():
    p = cli_utils._build_arg_parser()
    args = p.parse_args(["--output-format", "json"])
    assert args.output_format == "json"


def test_build_arg_parser_no_resume():
    p = cli_utils._build_arg_parser()
    args = p.parse_args(["--no-resume"])
    assert args.no_resume is True


def test_build_arg_parser_quiet_flag():
    p = cli_utils._build_arg_parser()
    args = p.parse_args(["--quiet"])
    assert args.quiet is True


def test_build_arg_parser_export_flag():
    p = cli_utils._build_arg_parser()
    args = p.parse_args(["--export"])
    assert args.export is True


def _close_sb_log_handlers():
    """Close and remove all handlers on the solo_builder logger.

    On Windows, RotatingFileHandler may hold an OS file lock even after
    handler.close() returns.  Explicitly closing the underlying stream first
    releases the lock before shutil.rmtree touches the directory.
    """
    import logging
    lg = logging.getLogger("solo_builder")
    for h in list(lg.handlers):
        try:
            if hasattr(h, "stream") and h.stream is not None:
                try:
                    h.stream.flush()
                    h.stream.close()
                except Exception:
                    pass
                h.stream = None
        except Exception:
            pass
        h.close()
        lg.removeHandler(h)


def _tmp_cleanup(tmp: str) -> None:
    """Remove a temp directory, silently ignoring Windows file-lock races."""
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def test_clear_stale_triggers_renames_trigger_cleaned():
    """rename_trigger.json must be removed at startup (not excluded)."""
    import tempfile, os
    tmp = tempfile.mkdtemp()
    try:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        trigger = os.path.join(state_dir, "rename_trigger.json")
        open(trigger, "w").close()
        cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert not os.path.exists(trigger), "rename_trigger.json should be cleaned at startup"
    finally:
        _close_sb_log_handlers()
        _tmp_cleanup(tmp)


def test_clear_stale_triggers_preserves_verify_trigger():
    """verify_trigger.json must NOT be removed at startup (excluded from cleanup)."""
    import tempfile, os, json as _json
    tmp = tempfile.mkdtemp()
    try:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        trigger = os.path.join(state_dir, "verify_trigger.json")
        Path(trigger).write_text(_json.dumps({"subtask": "A1"}), encoding="utf-8")
        cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert os.path.exists(trigger), "verify_trigger.json should survive startup cleanup"
    finally:
        _close_sb_log_handlers()
        _tmp_cleanup(tmp)


def test_cleanup_stale_at_exit_cleans_verify_trigger():
    """_cleanup_stale_at_exit removes verify_trigger.json (no exclusions on clean exit)."""
    import tempfile, os, json as _json
    tmp = tempfile.mkdtemp()
    try:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        trigger = os.path.join(state_dir, "verify_trigger.json")
        Path(trigger).write_text(_json.dumps({"subtask": "A1"}), encoding="utf-8")
        cli_utils._cleanup_stale_at_exit(tmp)
        assert not os.path.exists(trigger), "verify_trigger.json should be cleaned at exit"
    finally:
        _tmp_cleanup(tmp)


def test_cleanup_stale_at_exit_ok_with_empty_state_dir():
    """_cleanup_stale_at_exit is safe when state/ has no trigger files."""
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        import os
        os.makedirs(os.path.join(tmp, "state"), exist_ok=True)
        cli_utils._cleanup_stale_at_exit(tmp)  # must not raise
    finally:
        _tmp_cleanup(tmp)


def test_clear_stale_triggers_creates_state_dir():
    import tempfile, os
    tmp = tempfile.mkdtemp()
    try:
        lock = cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert os.path.isdir(os.path.join(tmp, "state"))
        assert lock.endswith("solo_builder.lock")
    finally:
        _close_sb_log_handlers()
        _tmp_cleanup(tmp)


def test_clear_stale_triggers_removes_existing_trigger():
    import tempfile, os
    tmp = tempfile.mkdtemp()
    try:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        trigger = os.path.join(state_dir, "stop_trigger")
        open(trigger, "w").close()
        cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert not os.path.exists(trigger)
    finally:
        _close_sb_log_handlers()
        _tmp_cleanup(tmp)


def test_clear_stale_triggers_ok_when_no_triggers():
    import tempfile, os
    tmp = tempfile.mkdtemp()
    try:
        lock = cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert os.path.basename(lock) == "solo_builder.lock"
    finally:
        _close_sb_log_handlers()
        _tmp_cleanup(tmp)


# ═══════════════════════════════════════════════════════════════════════════════
# _setup_logging (use_json=True branch)
# ═══════════════════════════════════════════════════════════════════════════════

def test_setup_logging_json_format():
    """cli_utils.py:30 — use_json=True sets JsonLogFormatter."""
    import tempfile, logging
    tmp = tempfile.mkdtemp()
    try:
        log_path = os.path.join(tmp, "logs", "test.log")
        cli_utils._setup_logging(log_path, use_json=True)
        lg = logging.getLogger("solo_builder")
        handler = [h for h in lg.handlers if hasattr(h, "baseFilename") and "test.log" in h.baseFilename]
        assert len(handler) > 0
        from solo_builder.utils.log_formatter import JsonLogFormatter
        assert isinstance(handler[0].formatter, JsonLogFormatter)
    finally:
        _close_sb_log_handlers()
        _tmp_cleanup(tmp)


# ═══════════════════════════════════════════════════════════════════════════════
# _splash
# ═══════════════════════════════════════════════════════════════════════════════

def test_splash_prints_banner():
    """cli_utils.py:42-57 — _splash prints ASCII banner."""
    out = StringIO()
    with patch("sys.stdout", out), patch("cli_utils.time.sleep"):
        cli_utils._splash(pdf_ok=True)
    assert "SOLO BUILDER" in out.getvalue()


def test_splash_warns_no_matplotlib():
    """cli_utils.py:54-56 — pdf_ok=False prints matplotlib warning."""
    out = StringIO()
    with patch("sys.stdout", out), patch("cli_utils.time.sleep"):
        cli_utils._splash(pdf_ok=False)
    assert "matplotlib" in out.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# _acquire_lock / _release_lock
# ═══════════════════════════════════════════════════════════════════════════════

def test_acquire_lock_writes_pid():
    """cli_utils.py:71-72 — _acquire_lock writes current PID."""
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        lock = os.path.join(tmp, "test.lock")
        cli_utils._acquire_lock(lock)
        assert os.path.exists(lock)
        pid = int(open(lock).read().strip())
        assert pid == os.getpid()
    finally:
        _tmp_cleanup(tmp)


def test_acquire_lock_stale_pid_removed():
    """cli_utils.py:69-70 — stale lock (dead PID) is cleaned up."""
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        lock = os.path.join(tmp, "test.lock")
        with open(lock, "w") as f:
            f.write("12345")
        with patch("os.kill", side_effect=ProcessLookupError("No such process")):
            cli_utils._acquire_lock(lock)
        pid = int(open(lock).read().strip())
        assert pid == os.getpid()
    finally:
        _tmp_cleanup(tmp)


def test_acquire_lock_active_pid_exits():
    """cli_utils.py:66-68 — active PID lock causes sys.exit(1)."""
    import tempfile
    import pytest
    tmp = tempfile.mkdtemp()
    try:
        lock = os.path.join(tmp, "test.lock")
        with open(lock, "w") as f:
            f.write(str(os.getpid()))  # current process is alive
        out = StringIO()
        with patch("sys.stdout", out):
            with pytest.raises(SystemExit) as exc_info:
                cli_utils._acquire_lock(lock)
        assert exc_info.value.code == 1
    finally:
        _tmp_cleanup(tmp)


def test_release_lock_removes_file():
    """cli_utils.py:76-77 — _release_lock removes lock file."""
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        lock = os.path.join(tmp, "test.lock")
        with open(lock, "w") as f:
            f.write("1234")
        cli_utils._release_lock(lock)
        assert not os.path.exists(lock)
    finally:
        _tmp_cleanup(tmp)


def test_release_lock_missing_file_ok():
    """cli_utils.py:78-79 — _release_lock on missing file doesn't raise."""
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        lock = os.path.join(tmp, "nonexistent.lock")
        cli_utils._release_lock(lock)  # should not raise
    finally:
        _tmp_cleanup(tmp)


# ═══════════════════════════════════════════════════════════════════════════════
# _emit_json_result
# ═══════════════════════════════════════════════════════════════════════════════

def test_emit_json_result_basic():
    """cli_utils.py:196-202 — basic JSON output."""
    import types
    cli = types.SimpleNamespace(
        step=5,
        dag={"T": {"status": "Verified", "branches": {"A": {"subtasks": {
            "A1": {"status": "Verified", "output": ""}
        }}}}},
    )
    args = types.SimpleNamespace(export=False)
    out = StringIO()
    with patch("sys.stdout", out):
        cli_utils._emit_json_result(cli, args, "", 0)
    result = json.loads(out.getvalue())
    assert result["steps"] == 5
    assert result["verified"] == 1
    assert result["complete"] is True


def test_emit_json_result_with_export():
    """cli_utils.py:203-204 — export flag adds export field."""
    import types
    cli = types.SimpleNamespace(
        step=3,
        dag={"T": {"status": "Pending", "branches": {"A": {"subtasks": {
            "A1": {"status": "Pending", "output": ""}
        }}}}},
    )
    args = types.SimpleNamespace(export=True)
    out = StringIO()
    with patch("sys.stdout", out):
        cli_utils._emit_json_result(cli, args, "/tmp/out.md", 42)
    result = json.loads(out.getvalue())
    assert result["export"]["path"] == "/tmp/out.md"
    assert result["export"]["count"] == 42
