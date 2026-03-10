"""Tests for tools/lock_file_gen.py (TASK-361, SE-015)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "lock_file_gen", _TOOLS_DIR / "lock_file_gen.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["lock_file_gen"] = _mod
_spec.loader.exec_module(_mod)

generate          = _mod.generate
is_stale          = _mod.is_stale
run               = _mod.run
_parse_requirements = _mod._parse_requirements
_filter_freeze    = _mod._filter_freeze
_build_lock_content = _mod._build_lock_content


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_REQUIREMENTS_CONTENT = """\
# deps
requests>=2.32
charset-normalizer>=3.0
python-dotenv>=1.0
"""

_FREEZE_OUTPUT = [
    "certifi==2024.2.2",
    "charset-normalizer==3.4.5",
    "idna==3.7",
    "python-dotenv==1.0.1",
    "requests==2.32.3",
    "urllib3==2.2.1",
]

_LOCK_CONTENT = """\
# Exact pinned versions for tools/requirements.txt dependencies
# Generated: 2026-03-10 via pip freeze
# Install with: pip install -r tools/requirements-lock.txt

charset-normalizer==3.4.5
python-dotenv==1.0.1
requests==2.32.3
"""


def _write_req(tmp: Path) -> Path:
    p = tmp / "requirements.txt"
    p.write_text(_REQUIREMENTS_CONTENT, encoding="utf-8")
    return p


def _write_lock(tmp: Path, content: str = _LOCK_CONTENT) -> Path:
    p = tmp / "requirements-lock.txt"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _parse_requirements
# ---------------------------------------------------------------------------

class TestParseRequirements(unittest.TestCase):

    def test_extracts_package_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_req(Path(tmp))
            names = _parse_requirements(p)
        self.assertIn("requests", names)
        self.assertIn("charset_normalizer", names)
        self.assertIn("python_dotenv", names)

    def test_skips_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "req.txt"
            p.write_text("# comment\nflask==3.0\n", encoding="utf-8")
            names = _parse_requirements(p)
        self.assertNotIn("#", names)
        self.assertIn("flask", names)

    def test_missing_file_returns_empty(self):
        names = _parse_requirements(Path("/nonexistent/requirements.txt"))
        self.assertEqual(names, [])

    def test_normalises_hyphens_to_underscores(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "req.txt"
            p.write_text("python-dotenv>=1.0\n", encoding="utf-8")
            names = _parse_requirements(p)
        self.assertIn("python_dotenv", names)


# ---------------------------------------------------------------------------
# _filter_freeze
# ---------------------------------------------------------------------------

class TestFilterFreeze(unittest.TestCase):

    def test_keeps_matching_packages(self):
        names = ["requests", "charset_normalizer", "python_dotenv"]
        kept = _filter_freeze(_FREEZE_OUTPUT, names)
        self.assertIn("requests==2.32.3", kept)
        self.assertIn("charset-normalizer==3.4.5", kept)

    def test_excludes_non_declared(self):
        names = ["requests"]
        kept = _filter_freeze(_FREEZE_OUTPUT, names)
        pkg_names = [k.split("==")[0].lower() for k in kept]
        self.assertNotIn("certifi", pkg_names)
        self.assertNotIn("urllib3", pkg_names)

    def test_empty_names_returns_empty(self):
        kept = _filter_freeze(_FREEZE_OUTPUT, [])
        self.assertEqual(kept, [])

    def test_result_sorted(self):
        names = ["requests", "charset_normalizer", "python_dotenv"]
        kept = _filter_freeze(_FREEZE_OUTPUT, names)
        self.assertEqual(kept, sorted(kept, key=str.lower))


# ---------------------------------------------------------------------------
# _build_lock_content
# ---------------------------------------------------------------------------

class TestBuildLockContent(unittest.TestCase):

    def test_includes_header_comment(self):
        content = _build_lock_content(["requests==2.32.3"])
        self.assertIn("# Exact pinned versions", content)

    def test_includes_date(self):
        content = _build_lock_content(["requests==2.32.3"])
        import re
        self.assertRegex(content, r"\d{4}-\d{2}-\d{2}")

    def test_includes_packages(self):
        content = _build_lock_content(["requests==2.32.3", "flask==3.0.0"])
        self.assertIn("requests==2.32.3", content)
        self.assertIn("flask==3.0.0", content)


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------

class TestGenerate(unittest.TestCase):

    def _mock_freeze(self, lines=None):
        return patch.object(_mod, "_pip_freeze", return_value=lines or _FREEZE_OUTPUT)

    def test_writes_lock_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            req  = _write_req(tmp)
            lock = tmp / "requirements-lock.txt"
            with self._mock_freeze():
                pinned, err = generate(req_path=req, lock_path=lock)
            self.assertIsNone(err)
            self.assertTrue(lock.exists())
            self.assertGreater(len(pinned), 0)

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            req  = _write_req(tmp)
            lock = tmp / "requirements-lock.txt"
            with self._mock_freeze():
                pinned, err = generate(req_path=req, lock_path=lock, dry_run=True)
        self.assertFalse(lock.exists())
        self.assertIsNone(err)

    def test_filters_to_declared_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            req  = _write_req(tmp)
            lock = tmp / "lock.txt"
            with self._mock_freeze():
                pinned, _ = generate(req_path=req, lock_path=lock)
        names = [p.split("==")[0].lower() for p in pinned]
        self.assertIn("requests", names)
        self.assertNotIn("certifi", names)

    def test_pip_freeze_failure_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            req = _write_req(tmp)
            with patch.object(_mod, "_pip_freeze", return_value=None):
                _, err = generate(req_path=req, lock_path=tmp / "lock.txt")
        self.assertIsNotNone(err)

    def test_missing_requirements_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, err = generate(req_path=Path(tmp) / "nonexistent.txt",
                              lock_path=Path(tmp) / "lock.txt")
        self.assertIsNotNone(err)


# ---------------------------------------------------------------------------
# is_stale()
# ---------------------------------------------------------------------------

class TestIsStale(unittest.TestCase):

    def _mock_freeze(self):
        return patch.object(_mod, "_pip_freeze", return_value=_FREEZE_OUTPUT)

    def test_missing_lock_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            req = _write_req(tmp)
            with self._mock_freeze():
                stale = is_stale(req_path=req, lock_path=tmp / "nonexistent.txt")
        self.assertTrue(stale)

    def test_up_to_date_lock_not_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            req  = _write_req(tmp)
            lock = _write_lock(tmp)
            with self._mock_freeze():
                stale = is_stale(req_path=req, lock_path=lock)
        self.assertFalse(stale)

    def test_outdated_lock_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            req  = _write_req(tmp)
            lock = tmp / "lock.txt"
            lock.write_text("requests==2.0.0\n", encoding="utf-8")  # old version
            with self._mock_freeze():
                stale = is_stale(req_path=req, lock_path=lock)
        self.assertTrue(stale)

    def test_pip_freeze_failure_returns_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            lock = _write_lock(tmp)
            with patch.object(_mod, "_pip_freeze", return_value=None):
                stale = is_stale(lock_path=lock)
        self.assertTrue(stale)


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def _mock_gen(self, pinned=None, err=None):
        return patch.object(_mod, "generate",
                            return_value=(pinned or ["requests==2.32.3"], err))

    def test_returns_0_on_success(self):
        with self._mock_gen():
            code = run(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_2_on_error(self):
        with self._mock_gen(pinned=[], err="pip failed"):
            code = run(quiet=True)
        self.assertEqual(code, 2)

    def test_check_mode_returns_0_when_fresh(self):
        with patch.object(_mod, "is_stale", return_value=False):
            code = run(quiet=True, check=True)
        self.assertEqual(code, 0)

    def test_check_mode_returns_1_when_stale(self):
        with patch.object(_mod, "is_stale", return_value=True):
            code = run(quiet=True, check=True)
        self.assertEqual(code, 1)

    def test_json_output_structure(self):
        with self._mock_gen():
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(as_json=True)
                data = json.loads(mock_out.getvalue())
        for k in ("pinned", "count", "lock_path"):
            self.assertIn(k, data)

    def test_quiet_suppresses_output(self):
        with self._mock_gen():
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_check_json_has_stale_key(self):
        with patch.object(_mod, "is_stale", return_value=False):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(as_json=True, check=True)
                data = json.loads(mock_out.getvalue())
        self.assertIn("stale", data)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_dry_run(self):
        with patch.object(_mod, "generate", return_value=(["requests==2.32.3"], None)):
            rc = _mod.main(["--dry-run", "--quiet"])
        self.assertEqual(rc, 0)

    def test_main_check_flag(self):
        with patch.object(_mod, "is_stale", return_value=False):
            rc = _mod.main(["--check", "--quiet"])
        self.assertEqual(rc, 0)

    def test_main_json_flag(self):
        with patch.object(_mod, "generate", return_value=(["requests==2.32.3"], None)):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--json"])
                data = json.loads(mock_out.getvalue())
        self.assertIn("pinned", data)


# ---------------------------------------------------------------------------
# pre_release_check integration
# ---------------------------------------------------------------------------

class TestPreReleaseDepAuditGate(unittest.TestCase):

    def test_dep_audit_gate_present_in_builtins(self):
        """dep-audit gate is a REQUIRED builtin in pre_release_check.py."""
        spec = importlib.util.spec_from_file_location(
            "pre_release_check", _TOOLS_DIR / "pre_release_check.py"
        )
        prc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prc)
        gates = prc._builtin_gates()
        names = {g["name"]: g for g in gates}
        self.assertIn("dep-audit", names)
        self.assertTrue(names["dep-audit"]["required"])

    def test_lock_file_fresh_gate_present(self):
        spec = importlib.util.spec_from_file_location(
            "pre_release_check2", _TOOLS_DIR / "pre_release_check.py"
        )
        prc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prc)
        gates = prc._builtin_gates()
        names = {g["name"] for g in gates}
        self.assertIn("lock-file-fresh", names)

    def test_dep_audit_command_uses_check_only(self):
        spec = importlib.util.spec_from_file_location(
            "pre_release_check3", _TOOLS_DIR / "pre_release_check.py"
        )
        prc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prc)
        gates = {g["name"]: g for g in prc._builtin_gates()}
        cmd = gates["dep-audit"]["command"]
        self.assertIn("--check-only", cmd)
        self.assertIn("dep_severity_check", cmd)


if __name__ == "__main__":
    unittest.main()
