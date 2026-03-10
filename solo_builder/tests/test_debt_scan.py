"""Tests for tools/debt_scan.py — TASK-336 (ME-003)."""
import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import debt_scan as ds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp: str, name: str, content: str) -> Path:
    p = Path(tmp) / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _scan_file
# ---------------------------------------------------------------------------

class TestScanFile(unittest.TestCase):

    def test_finds_todo(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "a.py", "x = 1  # TODO: fix this\ny = 2\n")
            items = ds._scan_file(p, Path(tmp))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].marker, "TODO")
        self.assertEqual(items[0].line, 1)

    def test_finds_fixme(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "a.py", "# FIXME: broken\n")
            items = ds._scan_file(p, Path(tmp))
        self.assertEqual(items[0].marker, "FIXME")

    def test_finds_hack(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "a.py", "# HACK: workaround\n")
            items = ds._scan_file(p, Path(tmp))
        self.assertEqual(items[0].marker, "HACK")

    def test_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "a.py", "# todo: lower case\n")
            items = ds._scan_file(p, Path(tmp))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].marker, "TODO")

    def test_no_markers_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "a.py", "x = 1\ny = 2\n")
            items = ds._scan_file(p, Path(tmp))
        self.assertEqual(items, [])

    def test_multiple_markers_in_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = "# TODO: one\nx = 1\n# FIXME: two\n"
            p = _write(tmp, "a.py", content)
            items = ds._scan_file(p, Path(tmp))
        self.assertEqual(len(items), 2)

    def test_uses_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "subdir.py", "# TODO: here\n")
            items = ds._scan_file(p, Path(tmp))
        self.assertNotIn("\\", items[0].path.split("/")[0])  # forward slashes


# ---------------------------------------------------------------------------
# _format_register_section
# ---------------------------------------------------------------------------

class TestFormatRegisterSection(unittest.TestCase):

    def test_contains_table_header(self):
        section = ds._format_register_section([])
        self.assertIn("| File | Line | Marker | Note |", section)

    def test_contains_no_markers_row_when_empty(self):
        section = ds._format_register_section([])
        self.assertIn("No markers found", section)

    def test_item_appears_in_table(self):
        item = ds.DebtItem("src/a.py", 5, "TODO", "fix me")
        section = ds._format_register_section([item])
        self.assertIn("src/a.py", section)
        self.assertIn("TODO", section)
        self.assertIn("fix me", section)

    def test_long_text_truncated(self):
        item = ds.DebtItem("x.py", 1, "HACK", "a" * 100)
        section = ds._format_register_section([item])
        self.assertIn("…", section)


# ---------------------------------------------------------------------------
# _update_register
# ---------------------------------------------------------------------------

class TestUpdateRegister(unittest.TestCase):

    def test_appends_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "TECH_DEBT.md"
            reg.write_text("# Header\n\nOriginal content.\n", encoding="utf-8")
            ds._update_register("\n---\n\n## Code-Level Debt Scan (auto-generated 2026-01-01)\n\nstuff\n",
                                reg)
            content = reg.read_text(encoding="utf-8")
        self.assertIn("Original content.", content)
        self.assertIn("Code-Level Debt Scan", content)

    def test_replaces_existing_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "TECH_DEBT.md"
            reg.write_text(
                "# Header\n\n---\n\n## Code-Level Debt Scan (auto-generated 2025-01-01)\n\nOLD\n",
                encoding="utf-8",
            )
            ds._update_register("\n---\n\n## Code-Level Debt Scan (auto-generated 2026-01-01)\n\nNEW\n",
                                reg)
            content = reg.read_text(encoding="utf-8")
        self.assertIn("NEW", content)
        self.assertNotIn("OLD", content)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_dry_run_exits_0(self):
        with patch.object(ds, "scan", return_value=[]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                code = ds.main(["--dry-run"])
        self.assertEqual(code, 0)

    def test_json_output_contains_count(self):
        item = ds.DebtItem("a.py", 1, "TODO", "fix")
        with patch.object(ds, "scan", return_value=[item]):
            buf = StringIO()
            with patch("sys.stdout", buf):
                code = ds.main(["--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(data["count"], 1)
        self.assertEqual(code, 0)

    def test_writes_register_when_not_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "TECH_DEBT.md"
            reg.write_text("# Header\n", encoding="utf-8")  # must exist first
            with patch.object(ds, "scan", return_value=[]):
                with patch.object(ds, "REGISTER_PATH", reg):
                    buf = StringIO()
                    with patch("sys.stdout", buf):
                        code = ds.main(["--quiet"])
            self.assertEqual(code, 0)
            self.assertIn("Code-Level Debt Scan", reg.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
