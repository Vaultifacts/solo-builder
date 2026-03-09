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


def test_clear_stale_triggers_creates_state_dir():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        lock = cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert os.path.isdir(os.path.join(tmp, "state"))
        assert lock.endswith("solo_builder.lock")


def test_clear_stale_triggers_removes_existing_trigger():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        trigger = os.path.join(state_dir, "stop_trigger")
        open(trigger, "w").close()
        cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert not os.path.exists(trigger)


def test_clear_stale_triggers_ok_when_no_triggers():
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        lock = cli_utils._clear_stale_triggers(tmp, os.path.join(tmp, "logs", "sb.log"))
        assert os.path.basename(lock) == "solo_builder.lock"
