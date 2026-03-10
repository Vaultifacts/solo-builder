"""Tests for tools/release_notes_gen.py (TASK-352, RD-010 to RD-015)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "release_notes_gen", _TOOLS_DIR / "release_notes_gen.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["release_notes_gen"] = _mod
_spec.loader.exec_module(_mod)

parse_changelog = _mod.parse_changelog
get_entry       = _mod.get_entry
ReleaseEntry    = _mod.ReleaseEntry
run             = _mod.run


# ---------------------------------------------------------------------------
# Sample CHANGELOG content
# ---------------------------------------------------------------------------

_SAMPLE_CHANGELOG = """\
# Changelog

## v5.41.0 — 2026-03-10  LintCheck — flake8 runner + 33 tests (TASK-351)

- **351 tasks** merged to master; **1445 tests**, all passing
- `tools/lint_check.py`: run_lint() runs flake8 and parses E/W/F/C counts

---

## v5.40.0 — 2026-03-10  MetricsAlertCheck — alert threshold checker (TASK-350)

- **350 tasks** merged to master; **1412 tests**, all passing
- `tools/metrics_alert_check.py`: check_alerts() evaluates failure_rate and latency

---

## v5.39.0 — 2026-03-09  StateIntegrityValidator (TASK-349)

- **349 tasks** merged to master
- Validates DAG schema, cycles, and orphans

---
"""

_SINGLE_ENTRY_CHANGELOG = """\
# Changelog

## v1.0.0 — 2026-01-01  Initial Release

- First release
- Includes core system
"""

_NO_BULLETS_CHANGELOG = """\
# Changelog

## v2.0.0 — 2026-02-01  Silent Release

No bullet points here.
"""


def _write_changelog(tmp: Path, content: str) -> Path:
    p = tmp / "CHANGELOG.md"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# ReleaseEntry
# ---------------------------------------------------------------------------

class TestReleaseEntry(unittest.TestCase):

    def test_to_dict_keys(self):
        e = ReleaseEntry(version="v1.0.0", date="2026-01-01", title="Test", bullets=["bullet"])
        d = e.to_dict()
        for k in ("version", "date", "title", "bullets"):
            self.assertIn(k, d)

    def test_to_dict_values(self):
        e = ReleaseEntry(version="v1.0.0", date="2026-01-01", title="My Release", bullets=["a", "b"])
        d = e.to_dict()
        self.assertEqual(d["version"], "v1.0.0")
        self.assertEqual(d["date"], "2026-01-01")
        self.assertEqual(len(d["bullets"]), 2)

    def test_to_markdown_contains_version(self):
        e = ReleaseEntry(version="v1.0.0", date="2026-01-01", title="Test")
        md = e.to_markdown()
        self.assertIn("v1.0.0", md)

    def test_to_markdown_contains_bullets(self):
        e = ReleaseEntry(version="v1.0.0", date="2026-01-01", title="", bullets=["hello world"])
        md = e.to_markdown()
        self.assertIn("hello world", md)

    def test_to_markdown_no_bullets(self):
        e = ReleaseEntry(version="v1.0.0", date="2026-01-01", title="")
        md = e.to_markdown()
        self.assertIn("v1.0.0", md)


# ---------------------------------------------------------------------------
# parse_changelog
# ---------------------------------------------------------------------------

class TestParseChangelog(unittest.TestCase):

    def test_parses_multiple_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        self.assertEqual(len(entries), 3)

    def test_versions_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        versions = [e.version for e in entries]
        self.assertIn("v5.41.0", versions)
        self.assertIn("v5.40.0", versions)
        self.assertIn("v5.39.0", versions)

    def test_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        self.assertEqual(entries[0].version, "v5.41.0")

    def test_bullets_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        first = entries[0]
        self.assertGreater(len(first.bullets), 0)

    def test_no_bullets_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _NO_BULLETS_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].bullets, [])

    def test_single_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SINGLE_ENTRY_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].version, "v1.0.0")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            parse_changelog(changelog_path=Path("/nonexistent/CHANGELOG.md"))

    def test_dates_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        self.assertEqual(entries[0].date, "2026-03-10")

    def test_title_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entries = parse_changelog(changelog_path=p)
        self.assertIn("LintCheck", entries[0].title)

    def test_empty_changelog_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), "# Changelog\n")
            entries = parse_changelog(changelog_path=p)
        self.assertEqual(entries, [])


# ---------------------------------------------------------------------------
# get_entry
# ---------------------------------------------------------------------------

class TestGetEntry(unittest.TestCase):

    def test_get_latest_returns_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entry = get_entry(changelog_path=p)
        self.assertEqual(entry.version, "v5.41.0")

    def test_get_specific_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entry = get_entry(version="v5.40.0", changelog_path=p)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.version, "v5.40.0")

    def test_get_missing_version_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            entry = get_entry(version="v99.99.99", changelog_path=p)
        self.assertIsNone(entry)

    def test_get_entry_empty_changelog(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), "# Changelog\n")
            entry = get_entry(changelog_path=p)
        self.assertIsNone(entry)


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            code = run(quiet=True, changelog_path=p)
        self.assertEqual(code, 0)

    def test_returns_1_version_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            code = run(version="v0.0.0", quiet=True, changelog_path=p)
        self.assertEqual(code, 1)

    def test_returns_2_missing_file(self):
        code = run(changelog_path="/nonexistent/CHANGELOG.md", quiet=True)
        self.assertEqual(code, 2)

    def test_json_output_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(as_json=True, changelog_path=p)
                data = json.loads(mock_out.getvalue())
        for k in ("version", "date", "title", "bullets"):
            self.assertIn(k, data)

    def test_markdown_output_contains_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(changelog_path=p)
                output = mock_out.getvalue()
        self.assertIn("v5.41.0", output)

    def test_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True, changelog_path=p)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_output_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            out = Path(tmp) / "notes.md"
            run(quiet=True, output_path=out, changelog_path=p)
            content = out.read_text(encoding="utf-8")
        self.assertIn("v5.41.0", content)

    def test_specific_version_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(version="v5.39.0", changelog_path=p)
                output = mock_out.getvalue()
        self.assertIn("v5.39.0", output)
        self.assertNotIn("v5.41.0", output)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            rc = _mod.main(["--quiet", "--changelog", str(p)])
        self.assertEqual(rc, 0)

    def test_main_version_arg(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            rc = _mod.main(["v5.40.0", "--quiet", "--changelog", str(p)])
        self.assertEqual(rc, 0)

    def test_main_missing_version_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            rc = _mod.main(["v0.0.0", "--quiet", "--changelog", str(p)])
        self.assertEqual(rc, 1)

    def test_main_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--json", "--changelog", str(p)])
                data = json.loads(mock_out.getvalue())
        self.assertIn("version", data)

    def test_main_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_changelog(Path(tmp), _SAMPLE_CHANGELOG)
            out = str(Path(tmp) / "out.md")
            rc = _mod.main(["--quiet", "--changelog", str(p), "--output", out])
            content = Path(out).read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn("v5.41.0", content)


if __name__ == "__main__":
    unittest.main()
