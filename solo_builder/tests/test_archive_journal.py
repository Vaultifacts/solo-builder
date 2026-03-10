"""Unit tests for tools/archive_journal.py (AI-009)."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import archive_journal as aj


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


def _entry(dt: datetime, msg: str = "task done") -> str:
    return f"- [{_iso(dt)}] {msg}\n"


def _write_journal(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


class TestParseTs(unittest.TestCase):

    def test_parses_full_iso_with_fraction(self):
        ts = aj._parse_ts("2026-03-05T23:42:24.8337338Z")
        self.assertIsNotNone(ts)
        self.assertEqual(ts.year, 2026)
        self.assertEqual(ts.month, 3)
        self.assertEqual(ts.day, 5)

    def test_returns_none_for_garbage(self):
        self.assertIsNone(aj._parse_ts("not-a-date"))

    def test_result_is_utc_aware(self):
        ts = aj._parse_ts("2026-01-15T12:00:00.000Z")
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.tzinfo)


class TestRun(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._journal = self._tmp / "JOURNAL.md"
        self._archive_dir = self._tmp / "journal_archive"
        # Patch module-level paths
        self._orig_journal  = aj.JOURNAL_PATH
        self._orig_archive  = aj.ARCHIVE_DIR
        aj.JOURNAL_PATH = self._journal
        aj.ARCHIVE_DIR  = self._archive_dir

    def tearDown(self):
        aj.JOURNAL_PATH = self._orig_journal
        aj.ARCHIVE_DIR  = self._orig_archive
        self._tmpdir.cleanup()

    def _recent(self, days_ago=1) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days_ago)

    def _old(self, days_ago=60) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days_ago)

    # ── basic behaviour ─────────────────────────────────────────────────────

    def test_missing_journal_returns_0(self):
        rc = aj.run(quiet=True)
        self.assertEqual(rc, 0)

    def test_nothing_to_archive_returns_0(self):
        _write_journal(self._journal, [
            "# Journal\n",
            _entry(self._recent(1)),
        ])
        rc = aj.run(older_than=30, quiet=True)
        self.assertEqual(rc, 0)
        self.assertFalse(self._archive_dir.exists())

    def test_old_entries_moved_to_archive(self):
        old_dt  = self._old(60)
        new_dt  = self._recent(1)
        _write_journal(self._journal, [
            "# Journal\n",
            _entry(old_dt, "old task"),
            _entry(new_dt, "new task"),
        ])
        rc = aj.run(older_than=30, quiet=True)
        self.assertEqual(rc, 0)
        # journal retains header + new entry
        remaining = self._journal.read_text(encoding="utf-8")
        self.assertIn("new task", remaining)
        self.assertNotIn("old task", remaining)

    def test_archive_file_created_in_correct_month_dir(self):
        old_dt = self._old(60)
        month_key = old_dt.strftime("%Y-%m")
        _write_journal(self._journal, [_entry(old_dt, "old")])
        aj.run(older_than=30, quiet=True)
        expected = self._archive_dir / f"{month_key}.md"
        self.assertTrue(expected.exists())
        self.assertIn("old", expected.read_text(encoding="utf-8"))

    def test_archive_file_has_header_on_first_creation(self):
        old_dt = self._old(60)
        month_key = old_dt.strftime("%Y-%m")
        _write_journal(self._journal, [_entry(old_dt)])
        aj.run(older_than=30, quiet=True)
        content = (self._archive_dir / f"{month_key}.md").read_text(encoding="utf-8")
        self.assertIn("Journal Archive", content)
        self.assertIn(month_key, content)

    def test_archive_appends_on_subsequent_run(self):
        old_dt = self._old(60)
        month_key = old_dt.strftime("%Y-%m")
        # First run
        _write_journal(self._journal, [_entry(old_dt, "first")])
        aj.run(older_than=30, quiet=True)
        # Second run with another old entry in the same month
        _write_journal(self._journal, [_entry(old_dt, "second")])
        aj.run(older_than=30, quiet=True)
        content = (self._archive_dir / f"{month_key}.md").read_text(encoding="utf-8")
        self.assertIn("first", content)
        self.assertIn("second", content)

    def test_non_entry_lines_always_kept(self):
        old_dt = self._old(60)
        _write_journal(self._journal, [
            "# Journal\n",
            "\n",
            _entry(old_dt, "old"),
        ])
        aj.run(older_than=30, quiet=True)
        remaining = self._journal.read_text(encoding="utf-8")
        self.assertIn("# Journal", remaining)

    # ── dry-run ─────────────────────────────────────────────────────────────

    def test_dry_run_does_not_write_archive(self):
        old_dt = self._old(60)
        _write_journal(self._journal, [_entry(old_dt)])
        aj.run(older_than=30, dry_run=True, quiet=True)
        self.assertFalse(self._archive_dir.exists())

    def test_dry_run_does_not_modify_journal(self):
        old_dt = self._old(60)
        original = _entry(old_dt, "old")
        _write_journal(self._journal, [original])
        aj.run(older_than=30, dry_run=True, quiet=True)
        self.assertEqual(self._journal.read_text(encoding="utf-8"), original)

    # ── multi-month grouping ─────────────────────────────────────────────────

    def test_entries_grouped_into_separate_month_files(self):
        jan = datetime(2025, 1, 15, tzinfo=timezone.utc)
        feb = datetime(2025, 2, 20, tzinfo=timezone.utc)
        _write_journal(self._journal, [
            _entry(jan, "january"),
            _entry(feb, "february"),
        ])
        aj.run(older_than=1, quiet=True)
        self.assertTrue((self._archive_dir / "2025-01.md").exists())
        self.assertTrue((self._archive_dir / "2025-02.md").exists())


class TestMain(unittest.TestCase):

    def test_returns_0_with_dry_run(self):
        rc = aj.main(["--dry-run", "--quiet", "--older-than", "30"])
        self.assertEqual(rc, 0)

    def test_older_than_parsed(self):
        rc = aj.main(["--dry-run", "--quiet", "--older-than", "90"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
