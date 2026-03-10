"""Tests for tools/context_window_compact.py (TASK-359, AI-014 to AI-016)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "context_window_compact", _TOOLS_DIR / "context_window_compact.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["context_window_compact"] = _mod
_spec.loader.exec_module(_mod)

compact         = _mod.compact
CompactionAction = _mod.CompactionAction
CompactionReport = _mod.CompactionReport
run             = _mod.run
_truncate_file  = _mod._truncate_file
_compact_journal = _mod._compact_journal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_result(label, path, lines, budget, status):
    r = MagicMock()
    r.label  = label
    r.path   = str(path)
    r.lines  = lines
    r.budget = budget
    r.status = status
    return r


def _budget_report(*results):
    r = MagicMock()
    r.results = list(results)
    return r


def _lines(n: int) -> str:
    return "\n".join(f"line {i}" for i in range(n)) + "\n"


# ---------------------------------------------------------------------------
# CompactionAction
# ---------------------------------------------------------------------------

class TestCompactionAction(unittest.TestCase):

    def test_to_dict_keys(self):
        a = CompactionAction("X", "/x", "truncated", 100, 80, "msg")
        d = a.to_dict()
        for k in ("label", "path", "action", "lines_before", "lines_after", "message"):
            self.assertIn(k, d)

    def test_values_stored(self):
        a = CompactionAction("MEMORY.md", "/m", "truncated", 250, 200, "ok")
        self.assertEqual(a.action, "truncated")
        self.assertEqual(a.lines_before, 250)
        self.assertEqual(a.lines_after, 200)


# ---------------------------------------------------------------------------
# CompactionReport
# ---------------------------------------------------------------------------

class TestCompactionReport(unittest.TestCase):

    def test_no_actions_has_actions_false(self):
        r = CompactionReport(actions=[
            CompactionAction("X", "/x", "skipped", 10, 10, ""),
        ])
        self.assertFalse(r.has_actions)

    def test_truncated_has_actions_true(self):
        r = CompactionReport(actions=[
            CompactionAction("X", "/x", "truncated", 200, 180, ""),
        ])
        self.assertTrue(r.has_actions)

    def test_warning_only_has_actions_true(self):
        r = CompactionReport(actions=[
            CompactionAction("X", "/x", "warning_only", 210, 210, ""),
        ])
        self.assertTrue(r.has_actions)

    def test_to_dict_structure(self):
        r = CompactionReport(actions=[], dry_run=True)
        d = r.to_dict()
        self.assertIn("has_actions", d)
        self.assertIn("dry_run", d)
        self.assertIn("actions", d)
        self.assertTrue(d["dry_run"])


# ---------------------------------------------------------------------------
# _truncate_file
# ---------------------------------------------------------------------------

class TestTruncateFile(unittest.TestCase):

    def test_truncates_over_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(250), encoding="utf-8")
            a = _truncate_file("MEMORY.md", p, budget=200)
        self.assertEqual(a.action, "truncated")
        self.assertEqual(a.lines_after, 200)

    def test_file_within_budget_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(100), encoding="utf-8")
            a = _truncate_file("MEMORY.md", p, budget=200)
        self.assertEqual(a.action, "skipped")

    def test_dry_run_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(250), encoding="utf-8")
            a = _truncate_file("MEMORY.md", p, budget=200, dry_run=True)
            # File should not be changed
            self.assertEqual(len(p.read_text(encoding="utf-8").splitlines()), 250)
        self.assertEqual(a.action, "truncated")
        self.assertEqual(a.lines_after, 200)  # dry-run shows anticipated budget value

    def test_missing_file_returns_error(self):
        a = _truncate_file("X", Path("/nonexistent/X.md"), budget=100)
        self.assertEqual(a.action, "error")

    def test_actual_file_size_reduced(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(250), encoding="utf-8")
            _truncate_file("MEMORY.md", p, budget=200)
            actual = len(p.read_text(encoding="utf-8").splitlines())
        self.assertEqual(actual, 200)


# ---------------------------------------------------------------------------
# _compact_journal
# ---------------------------------------------------------------------------

class TestCompactJournal(unittest.TestCase):

    def test_dry_run_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "JOURNAL.md"
            p.write_text("- [2020-01-01T00:00:00Z] old entry\n", encoding="utf-8")
            a = _compact_journal(p, Path(tmp) / "archive", dry_run=True)
        self.assertEqual(a.action, "archived")
        self.assertIn("dry-run", a.message.lower())

    def test_missing_journal_still_returns_action(self):
        a = _compact_journal(Path("/nonexistent/JOURNAL.md"),
                             Path("/tmp/archive"), dry_run=True)
        self.assertIn(a.action, ("archived", "error"))

    def test_lines_before_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "JOURNAL.md"
            p.write_text("line1\nline2\nline3\n", encoding="utf-8")
            a = _compact_journal(p, Path(tmp) / "archive", dry_run=True)
        self.assertEqual(a.lines_before, 3)

    def test_calls_archive_journal_run(self):
        aj_mock = MagicMock()
        aj_mock.run = MagicMock(return_value=0)
        with patch.dict(_sys.modules, {"archive_journal": aj_mock}):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "JOURNAL.md"
                p.write_text("line\n", encoding="utf-8")
                _compact_journal(p, Path(tmp) / "archive", older_than=14, dry_run=False)
        aj_mock.run.assert_called_once()


# ---------------------------------------------------------------------------
# compact()
# ---------------------------------------------------------------------------

class TestCompact(unittest.TestCase):

    def _make_cwb_mock(self, results):
        m = MagicMock()
        m.check_budget = MagicMock(return_value=_budget_report(*results))
        return m

    def test_all_ok_no_compaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "CLAUDE.md"
            p.write_text(_lines(50), encoding="utf-8")
            report = compact(budget_report=_budget_report(
                _file_result("CLAUDE.md", p, 50, 200, "ok")
            ))
        actions = [a for a in report.actions if a.action != "skipped"]
        self.assertEqual(len(actions), 0)

    def test_critical_claude_md_warning_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "CLAUDE.md"
            p.write_text(_lines(190), encoding="utf-8")
            report = compact(budget_report=_budget_report(
                _file_result("CLAUDE.md", p, 190, 200, "critical")
            ))
        actions = [a for a in report.actions if a.action != "skipped"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action, "warning_only")

    def test_critical_memory_md_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(210), encoding="utf-8")
            report = compact(budget_report=_budget_report(
                _file_result("MEMORY.md", p, 210, 200, "over_budget")
            ))
        actions = [a for a in report.actions if a.action != "skipped"]
        self.assertEqual(actions[0].action, "truncated")

    def test_warn_threshold_skipped_when_using_critical(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(150), encoding="utf-8")
            report = compact(
                budget_report=_budget_report(
                    _file_result("MEMORY.md", p, 150, 200, "warn")
                ),
                threshold="critical",
            )
        actions = [a for a in report.actions if a.action != "skipped"]
        self.assertEqual(len(actions), 0)

    def test_warn_threshold_triggers_at_warn(self):
        # Use a CLAUDE.md (warning_only strategy) to confirm warn threshold fires
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "CLAUDE.md"
            p.write_text(_lines(150), encoding="utf-8")
            report = compact(
                budget_report=_budget_report(
                    _file_result("CLAUDE.md", p, 150, 200, "warn")
                ),
                threshold="warn",
            )
        actions = [a for a in report.actions if a.action != "skipped"]
        self.assertGreater(len(actions), 0)
        self.assertEqual(actions[0].action, "warning_only")

    def test_dry_run_flag_propagated(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(250), encoding="utf-8")
            report = compact(
                budget_report=_budget_report(
                    _file_result("MEMORY.md", p, 250, 200, "over_budget")
                ),
                dry_run=True,
            )
            self.assertTrue(report.dry_run)
            # File should not have been changed
            actual = len(p.read_text(encoding="utf-8").splitlines())
            self.assertEqual(actual, 250)

    def test_report_has_actions_true_when_compacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "MEMORY.md"
            p.write_text(_lines(250), encoding="utf-8")
            report = compact(
                budget_report=_budget_report(
                    _file_result("MEMORY.md", p, 250, 200, "over_budget")
                ),
            )
        self.assertTrue(report.has_actions)


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def _mock_compact(self, report):
        return patch.object(_mod, "compact", return_value=report)

    def test_returns_0_no_actions(self):
        r = CompactionReport(actions=[
            CompactionAction("X", "/x", "skipped", 10, 10, ""),
        ])
        with self._mock_compact(r):
            code = run(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_1_with_actions(self):
        r = CompactionReport(actions=[
            CompactionAction("MEMORY.md", "/m", "truncated", 250, 200, ""),
        ])
        with self._mock_compact(r):
            code = run(quiet=True)
        self.assertEqual(code, 1)

    def test_json_output_structure(self):
        r = CompactionReport(actions=[], dry_run=False)
        with self._mock_compact(r):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(as_json=True)
                data = json.loads(mock_out.getvalue())
        for k in ("has_actions", "dry_run", "actions"):
            self.assertIn(k, data)

    def test_quiet_suppresses_output(self):
        r = CompactionReport(actions=[])
        with self._mock_compact(r):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_text_output_shows_action(self):
        r = CompactionReport(actions=[
            CompactionAction("MEMORY.md", "/m", "truncated", 250, 200, "ok"),
        ])
        with self._mock_compact(r):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run()
                output = mock_out.getvalue()
        self.assertIn("MEMORY.md", output)

    def test_dry_run_text_mentions_dry_run(self):
        r = CompactionReport(actions=[
            CompactionAction("MEMORY.md", "/m", "truncated", 250, 200, "ok"),
        ], dry_run=True)
        with self._mock_compact(r):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(dry_run=True)
                output = mock_out.getvalue()
        self.assertIn("dry", output.lower())

    def test_exception_returns_2(self):
        with patch.object(_mod, "compact", side_effect=RuntimeError("boom")):
            code = run(quiet=True)
        self.assertEqual(code, 2)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_dry_run_flag(self):
        r = CompactionReport(actions=[], dry_run=True)
        with patch.object(_mod, "compact", return_value=r):
            rc = _mod.main(["--dry-run", "--quiet"])
        self.assertEqual(rc, 0)

    def test_main_json_flag(self):
        r = CompactionReport(actions=[], dry_run=False)
        with patch.object(_mod, "compact", return_value=r):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--dry-run", "--json"])
                data = json.loads(mock_out.getvalue())
        self.assertIn("has_actions", data)

    def test_main_threshold_flag(self):
        r = CompactionReport(actions=[], dry_run=False)
        with patch.object(_mod, "compact", return_value=r) as mc:
            _mod.main(["--quiet", "--threshold", "warn"])
        _, kwargs = mc.call_args
        self.assertEqual(kwargs.get("threshold"), "warn")

    def test_main_older_than_flag(self):
        r = CompactionReport(actions=[], dry_run=False)
        with patch.object(_mod, "compact", return_value=r) as mc:
            _mod.main(["--quiet", "--older-than", "7"])
        _, kwargs = mc.call_args
        self.assertEqual(kwargs.get("older_than"), 7)


if __name__ == "__main__":
    unittest.main()
