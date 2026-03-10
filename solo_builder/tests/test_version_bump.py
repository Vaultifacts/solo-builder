"""Tests for tools/version_bump.py (TASK-353, RD-020 to RD-025)."""
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
    "version_bump", _TOOLS_DIR / "version_bump.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["version_bump"] = _mod
_spec.loader.exec_module(_mod)

SemVer              = _mod.SemVer
_read_current       = _mod._read_current_version
_compute_next       = _mod._compute_next
_write_version      = _mod._write_version_file
_prepend_changelog  = _mod._prepend_changelog_header
run                 = _mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHANGELOG_CONTENT = """\
# Changelog

## v5.42.0 — 2026-03-10  ReleaseNotesGen (TASK-352)

- **352 tasks** merged

---

## v5.41.0 — 2026-03-09  LintCheck (TASK-351)

- **351 tasks** merged

---
"""


def _write_version_file(tmp: Path, version: str) -> Path:
    p = tmp / "VERSION.txt"
    p.write_text(version + "\n", encoding="utf-8")
    return p


def _write_changelog(tmp: Path, content: str = _CHANGELOG_CONTENT) -> Path:
    p = tmp / "CHANGELOG.md"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# SemVer
# ---------------------------------------------------------------------------

class TestSemVer(unittest.TestCase):

    def test_parse_with_v_prefix(self):
        v = SemVer.parse("v5.42.0")
        self.assertEqual((v.major, v.minor, v.patch), (5, 42, 0))

    def test_parse_without_prefix(self):
        v = SemVer.parse("1.2.3")
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 3))

    def test_parse_invalid_raises(self):
        with self.assertRaises(ValueError):
            SemVer.parse("not_a_version")

    def test_str_representation(self):
        self.assertEqual(str(SemVer(5, 42, 0)), "v5.42.0")

    def test_bump_major(self):
        v = SemVer(5, 42, 3)
        self.assertEqual(str(v.bump("major")), "v6.0.0")

    def test_bump_minor(self):
        v = SemVer(5, 42, 3)
        self.assertEqual(str(v.bump("minor")), "v5.43.0")

    def test_bump_patch(self):
        v = SemVer(5, 42, 3)
        self.assertEqual(str(v.bump("patch")), "v5.42.4")

    def test_bump_major_resets_minor_patch(self):
        v = SemVer(3, 15, 7)
        n = v.bump("major")
        self.assertEqual(n.minor, 0)
        self.assertEqual(n.patch, 0)

    def test_bump_minor_resets_patch(self):
        v = SemVer(3, 15, 7)
        n = v.bump("minor")
        self.assertEqual(n.patch, 0)

    def test_bump_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            SemVer(1, 0, 0).bump("mega")

    def test_semver_immutable(self):
        v = SemVer(1, 2, 3)
        with self.assertRaises((AttributeError, TypeError)):
            v.major = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _read_current_version
# ---------------------------------------------------------------------------

class TestReadCurrentVersion(unittest.TestCase):

    def test_reads_from_version_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            v = _read_current(version_path=p, changelog_path=Path(tmp) / "missing.md")
        self.assertEqual(str(v), "v5.42.0")

    def test_falls_back_to_changelog(self):
        with tempfile.TemporaryDirectory() as tmp:
            cl = _write_changelog(Path(tmp))
            v = _read_current(
                version_path=Path(tmp) / "MISSING.txt",
                changelog_path=cl,
            )
        self.assertEqual(str(v), "v5.42.0")

    def test_raises_when_both_missing(self):
        with self.assertRaises(RuntimeError):
            _read_current(
                version_path=Path("/nonexistent/VERSION.txt"),
                changelog_path=Path("/nonexistent/CHANGELOG.md"),
            )

    def test_version_file_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v1.0.0")
            cl = _write_changelog(Path(tmp))
            v = _read_current(version_path=p, changelog_path=cl)
        self.assertEqual(str(v), "v1.0.0")


# ---------------------------------------------------------------------------
# _compute_next
# ---------------------------------------------------------------------------

class TestComputeNext(unittest.TestCase):

    def test_minor_bump_from_version_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            current, nxt = _compute_next("minor", version_path=p)
        self.assertEqual(str(current), "v5.42.0")
        self.assertEqual(str(nxt), "v5.43.0")

    def test_patch_bump(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v2.3.4")
            _, nxt = _compute_next("patch", version_path=p)
        self.assertEqual(str(nxt), "v2.3.5")

    def test_major_bump(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v4.99.99")
            _, nxt = _compute_next("major", version_path=p)
        self.assertEqual(str(nxt), "v5.0.0")


# ---------------------------------------------------------------------------
# _write_version_file / _prepend_changelog_header
# ---------------------------------------------------------------------------

class TestWriteVersionFile(unittest.TestCase):

    def test_writes_version_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "VERSION.txt"
            _write_version(SemVer(5, 43, 0), p)
            content = p.read_text(encoding="utf-8").strip()
        self.assertEqual(content, "v5.43.0")


class TestPrependChangelogHeader(unittest.TestCase):

    def test_header_added_at_top(self):
        with tempfile.TemporaryDirectory() as tmp:
            cl = _write_changelog(Path(tmp))
            _prepend_changelog(SemVer(5, 43, 0), "New Release", cl)
            content = cl.read_text(encoding="utf-8")
        lines = content.splitlines()
        # Find first ## header
        header_line = next(l for l in lines if l.startswith("## "))
        self.assertIn("v5.43.0", header_line)

    def test_existing_content_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            cl = _write_changelog(Path(tmp))
            _prepend_changelog(SemVer(5, 43, 0), "New Release", cl)
            content = cl.read_text(encoding="utf-8")
        self.assertIn("v5.42.0", content)


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_on_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            code = run(bump_type="minor", dry_run=True, quiet=True, version_path=p)
        self.assertEqual(code, 0)

    def test_returns_2_on_missing_bump_type(self):
        code = run(bump_type=None, quiet=True)
        self.assertEqual(code, 2)

    def test_returns_2_on_invalid_bump_type(self):
        code = run(bump_type="mega", quiet=True)
        self.assertEqual(code, 2)

    def test_show_current_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            code = run(show_current=True, quiet=True, version_path=p)
        self.assertEqual(code, 0)

    def test_show_current_prints_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(show_current=True, version_path=p)
                output = mock_out.getvalue()
        self.assertIn("v5.42.0", output)

    def test_json_output_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(bump_type="minor", dry_run=True, as_json=True, version_path=p)
                data = json.loads(mock_out.getvalue())
        for k in ("bump_type", "current", "next", "dry_run"):
            self.assertIn(k, data)

    def test_json_current_and_next_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(bump_type="minor", dry_run=True, as_json=True, version_path=p)
                data = json.loads(mock_out.getvalue())
        self.assertEqual(data["current"], "v5.42.0")
        self.assertEqual(data["next"], "v5.43.0")

    def test_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(bump_type="minor", dry_run=True, quiet=True, version_path=p)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_write_updates_version_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            cl = _write_changelog(Path(tmp))
            run(bump_type="minor", write=True, dry_run=False, quiet=True,
                version_path=p, changelog_path=cl)
            content = p.read_text(encoding="utf-8").strip()
        self.assertEqual(content, "v5.43.0")

    def test_write_updates_changelog(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            cl = _write_changelog(Path(tmp))
            run(bump_type="minor", write=True, dry_run=False, quiet=True,
                version_path=p, changelog_path=cl)
            content = cl.read_text(encoding="utf-8")
        self.assertIn("v5.43.0", content)

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            run(bump_type="minor", dry_run=True, write=False, quiet=True, version_path=p)
            content = p.read_text(encoding="utf-8").strip()
        self.assertEqual(content, "v5.42.0")  # unchanged


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_dry_run_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            rc = _mod.main(["minor", "--quiet", "--version-file", str(p)])
        self.assertEqual(rc, 0)

    def test_main_current_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            rc = _mod.main(["--current", "--quiet", "--version-file", str(p)])
        self.assertEqual(rc, 0)

    def test_main_no_args_returns_2(self):
        rc = _mod.main([])
        self.assertEqual(rc, 2)

    def test_main_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["patch", "--json", "--version-file", str(p)])
                data = json.loads(mock_out.getvalue())
        self.assertEqual(data["next"], "v5.42.1")

    def test_main_write_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_version_file(Path(tmp), "v5.42.0")
            cl = _write_changelog(Path(tmp))
            rc = _mod.main([
                "patch", "--write", "--quiet",
                "--version-file", str(p),
                "--changelog", str(cl),
            ])
            content = p.read_text(encoding="utf-8").strip()
        self.assertEqual(rc, 0)
        self.assertEqual(content, "v5.42.1")


if __name__ == "__main__":
    unittest.main()
