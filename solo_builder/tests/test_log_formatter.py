"""Tests for solo_builder/utils/log_formatter.py (TASK-326 / OM-011)."""
import json
import logging
import os
import sys
import unittest
from pathlib import Path

# Ensure solo_builder/ is on sys.path (needed by cli_utils -> utils.helper_functions)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solo_builder.utils.log_formatter import JsonLogFormatter


class TestJsonLogFormatter(unittest.TestCase):

    def _make_record(self, msg="hello", level=logging.INFO, name="solo_builder", exc_info=None):
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )
        return record

    def _format(self, record):
        fmt = JsonLogFormatter()
        return json.loads(fmt.format(record))

    def test_output_is_valid_json(self):
        record = self._make_record()
        fmt = JsonLogFormatter()
        raw = fmt.format(record)
        parsed = json.loads(raw)
        self.assertIsInstance(parsed, dict)

    def test_has_required_keys(self):
        entry = self._format(self._make_record())
        for key in ("ts", "level", "logger", "msg"):
            self.assertIn(key, entry)

    def test_level_name(self):
        entry = self._format(self._make_record(level=logging.WARNING))
        self.assertEqual(entry["level"], "WARNING")

    def test_logger_name(self):
        entry = self._format(self._make_record(name="my_logger"))
        self.assertEqual(entry["logger"], "my_logger")

    def test_message_content(self):
        entry = self._format(self._make_record(msg="sdk_dispatch step=5"))
        self.assertEqual(entry["msg"], "sdk_dispatch step=5")

    def test_no_exc_key_when_no_exception(self):
        entry = self._format(self._make_record())
        self.assertNotIn("exc", entry)

    def test_exc_key_present_on_exception(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = self._make_record(exc_info=exc_info)
        entry = self._format(record)
        self.assertIn("exc", entry)
        self.assertIn("ValueError", entry["exc"])

    def test_ts_format_matches_iso8601(self):
        import re
        entry = self._format(self._make_record())
        self.assertRegex(entry["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    def test_one_line_per_record(self):
        fmt = JsonLogFormatter()
        raw = fmt.format(self._make_record())
        self.assertNotIn("\n", raw)


class TestSetupLoggingJsonFlag(unittest.TestCase):
    """Verify _setup_logging creates a JsonLogFormatter when use_json=True."""

    def _close_handlers(self):
        lg = logging.getLogger("solo_builder")
        for h in list(lg.handlers):
            h.close()
            lg.removeHandler(h)

    def test_text_formatter_by_default(self):
        import tempfile, os
        tmp = tempfile.mkdtemp()
        try:
            from solo_builder import cli_utils
            cli_utils._setup_logging(os.path.join(tmp, "logs", "sb.log"), use_json=False)
            lg = logging.getLogger("solo_builder")
            handler = lg.handlers[-1]
            self.assertNotIsInstance(handler.formatter, JsonLogFormatter)
        finally:
            self._close_handlers()
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_json_formatter_when_flag_set(self):
        import tempfile, os
        tmp = tempfile.mkdtemp()
        try:
            from solo_builder import cli_utils
            cli_utils._setup_logging(os.path.join(tmp, "logs", "sb.log"), use_json=True)
            lg = logging.getLogger("solo_builder")
            handler = lg.handlers[-1]
            self.assertIsInstance(handler.formatter, JsonLogFormatter)
        finally:
            self._close_handlers()
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_json_output_is_parseable(self):
        import tempfile, os
        tmp = tempfile.mkdtemp()
        log_path = os.path.join(tmp, "logs", "sb.log")
        try:
            from solo_builder import cli_utils
            cli_utils._setup_logging(log_path, use_json=True)
            lg = logging.getLogger("solo_builder")
            lg.info("test_event key=val")
            # flush handler
            for h in lg.handlers:
                h.flush()
            with open(log_path, encoding="utf-8") as f:
                line = f.readline().strip()
            entry = json.loads(line)
            self.assertEqual(entry["msg"], "test_event key=val")
            self.assertEqual(entry["level"], "INFO")
        finally:
            self._close_handlers()
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
