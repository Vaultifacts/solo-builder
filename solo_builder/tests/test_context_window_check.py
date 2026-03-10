"""Tests for tools/context_window_check.py — TASK-332 (AI-008)."""
import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Make the tools directory importable
TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import context_window_check as cwc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(tmp: str, name: str, lines: int) -> Path:
    p = Path(tmp) / name
    p.write_text("\n".join(f"line {i}" for i in range(lines)), encoding="utf-8")
    return p


def _patched_files(entries):
    """Patch _CONTEXT_FILES with given list for test isolation."""
    return patch.object(cwc, "_CONTEXT_FILES", entries)


# ---------------------------------------------------------------------------
# _count_lines
# ---------------------------------------------------------------------------

class TestCountLines(unittest.TestCase):

    def test_counts_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "f.md", 42)
            self.assertEqual(cwc._count_lines(p), 42)

    def test_missing_returns_none(self):
        self.assertIsNone(cwc._count_lines(Path("/does/not/exist.md")))

    def test_empty_file_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.md"
            p.write_text("", encoding="utf-8")
            self.assertEqual(cwc._count_lines(p), 0)


# ---------------------------------------------------------------------------
# check()
# ---------------------------------------------------------------------------

class TestCheck(unittest.TestCase):

    def test_all_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 10)
            with _patched_files([("A", p, None, None)]):
                code = cwc.check(warn=50, error=100, quiet=True)
        self.assertEqual(code, 0)

    def test_warn_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 60)
            with _patched_files([("A", p, None, None)]):
                results = []
                orig = cwc.check

                def _capture(*a, **kw):
                    code = orig(*a, **kw)
                    return code

                code = cwc.check(warn=50, error=100, quiet=True)
        self.assertEqual(code, 0)  # warn does NOT set exit_code to 1

    def test_error_threshold_sets_exit_code_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 110)
            with _patched_files([("A", p, None, None)]):
                code = cwc.check(warn=50, error=100, quiet=True)
        self.assertEqual(code, 1)

    def test_missing_file_status_missing(self):
        missing = Path("/no/such/path/x.md")
        with _patched_files([("X", missing, None, None)]):
            code = cwc.check(quiet=True)
        self.assertEqual(code, 0)  # missing does not error

    def test_per_file_override_warn_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 300 lines: would error at global threshold 200 but overridden to 500
            p = _make_file(tmp, "journal.md", 300)
            with _patched_files([("J", p, 250, 500)]):
                code = cwc.check(warn=150, error=200, quiet=True)
        self.assertEqual(code, 0)  # per-file error=500 → ok

    def test_per_file_override_triggers_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 90)
            with _patched_files([("A", p, 50, 80)]):  # error override=80
                code = cwc.check(warn=150, error=200, quiet=True)
        self.assertEqual(code, 1)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 20)
            with _patched_files([("A", p, None, None)]):
                buf = StringIO()
                with patch("sys.stdout", buf):
                    cwc.check(warn=50, error=100, as_json=True)
        data = json.loads(buf.getvalue())
        self.assertIn("results", data)
        self.assertEqual(data["results"][0]["file"], "A")
        self.assertEqual(data["results"][0]["status"], "ok")

    def test_plain_text_output_contains_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "readme.md", 5)
            with _patched_files([("readme.md", p, None, None)]):
                buf = StringIO()
                with patch("sys.stdout", buf):
                    cwc.check(warn=50, error=100)
        self.assertIn("readme.md", buf.getvalue())


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_returns_0_for_ok_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 10)
            with _patched_files([("A", p, None, None)]):
                code = cwc.main(["--warn", "50", "--error", "100", "--quiet"])
        self.assertEqual(code, 0)

    def test_returns_1_for_error_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 150)
            with _patched_files([("A", p, None, None)]):
                code = cwc.main(["--warn", "50", "--error", "100", "--quiet"])
        self.assertEqual(code, 1)

    def test_returns_2_for_invalid_thresholds(self):
        code = cwc.main(["--warn", "200", "--error", "100", "--quiet"])
        self.assertEqual(code, 2)

    def test_json_flag_produces_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 5)
            with _patched_files([("A", p, None, None)]):
                buf = StringIO()
                with patch("sys.stdout", buf):
                    cwc.main(["--warn", "50", "--error", "100", "--json"])
        data = json.loads(buf.getvalue())
        self.assertIn("results", data)

    def test_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _make_file(tmp, "a.md", 5)
            with _patched_files([("A", p, None, None)]):
                buf = StringIO()
                with patch("sys.stdout", buf):
                    cwc.main(["--quiet"])
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
