"""Unit tests for tools/session_context_report.py (AI-013)."""
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import session_context_report as scr


class TestBar(unittest.TestCase):

    def test_empty_bar_at_zero(self):
        self.assertEqual(scr._bar(0, 200), " " * scr._BAR_WIDTH)

    def test_full_bar_at_limit(self):
        self.assertEqual(scr._bar(200, 200), "=" * scr._BAR_WIDTH)

    def test_half_bar(self):
        result = scr._bar(100, 200)
        self.assertEqual(result.count("="), scr._BAR_WIDTH // 2)

    def test_bar_does_not_exceed_width(self):
        result = scr._bar(9999, 200)
        self.assertEqual(len(result), scr._BAR_WIDTH)
        self.assertNotIn(" ", result)

    def test_zero_limit_returns_empty_bar(self):
        result = scr._bar(50, 0)
        self.assertEqual(result, " " * scr._BAR_WIDTH)


class TestStatusLabel(unittest.TestCase):

    def test_ok_below_warn(self):
        self.assertEqual(scr._status_label(10, 150, 200), "OK  ")

    def test_warn_at_warn_threshold(self):
        self.assertEqual(scr._status_label(150, 150, 200), "WARN")

    def test_warn_between_thresholds(self):
        self.assertEqual(scr._status_label(175, 150, 200), "WARN")

    def test_err_at_error_threshold(self):
        self.assertEqual(scr._status_label(200, 150, 200), "ERR ")

    def test_err_above_error_threshold(self):
        self.assertEqual(scr._status_label(300, 150, 200), "ERR ")


class TestReport(unittest.TestCase):

    def _fake_files(self):
        return [
            ("CLAUDE.md", Path("/fake/CLAUDE.md"), None, None),
            ("MEMORY.md", Path("/fake/MEMORY.md"), None, None),
        ]

    def test_report_ok_message(self):
        with patch.object(scr, "_CONTEXT_FILES", self._fake_files()), \
             patch.object(scr, "_count_lines", side_effect=[20, 30]), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            scr.report()
        output = mock_out.getvalue()
        self.assertIn("All files within limits", output)
        self.assertNotIn("ACTION REQUIRED", output)
        self.assertNotIn("NOTICE", output)

    def test_report_warn_message(self):
        with patch.object(scr, "_CONTEXT_FILES", self._fake_files()), \
             patch.object(scr, "_count_lines", side_effect=[155, 20]), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            scr.report()
        output = mock_out.getvalue()
        self.assertIn("NOTICE", output)
        self.assertIn("approaching", output)

    def test_report_error_message(self):
        with patch.object(scr, "_CONTEXT_FILES", self._fake_files()), \
             patch.object(scr, "_count_lines", side_effect=[205, 20]), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            scr.report()
        output = mock_out.getvalue()
        self.assertIn("ACTION REQUIRED", output)

    def test_report_missing_file(self):
        with patch.object(scr, "_CONTEXT_FILES", self._fake_files()), \
             patch.object(scr, "_count_lines", side_effect=[None, 30]), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            scr.report()
        output = mock_out.getvalue()
        self.assertIn("missing", output)

    def test_main_returns_zero(self):
        with patch.object(scr, "_CONTEXT_FILES", self._fake_files()), \
             patch.object(scr, "_count_lines", side_effect=[20, 30]), \
             patch("sys.stdout", new_callable=StringIO):
            result = scr.main([])
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
