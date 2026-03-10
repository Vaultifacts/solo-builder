"""Tests for tools/threat_model_check.py (TASK-342, SE-001 to SE-006)."""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module from tools/
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "threat_model_check", _TOOLS_DIR / "threat_model_check.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_checks       = _mod.run_checks
CheckResult      = _mod.CheckResult
REQUIRED_GAP_IDS = _mod.REQUIRED_GAP_IDS
REQUIRED_CONTROLS = _mod.REQUIRED_CONTROLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_doc(
    gap_ids=None, date="2026-03-10", controls=None, threats=True
) -> str:
    """Build a minimal document that passes all required checks."""
    lines = []
    if date:
        lines.append(f"Last updated: {date}")
    # Gap IDs
    for gid in (gap_ids if gap_ids is not None else REQUIRED_GAP_IDS):
        lines.append(f"| {gid} | desc | Resolved |")
    # Controls
    for ctrl in (controls if controls is not None else REQUIRED_CONTROLS):
        lines.append(f"Mentions {ctrl} control.")
    # Threat sections
    if threats:
        for n in range(1, 7):
            lines.append(f"### T-{n:03d} — example threat")
    return "\n".join(lines)


def _patch_path(tmp_path: Path, content: str | None):
    """Patch THREAT_MODEL_PATH to a temp file (or nonexistent if content is None)."""
    if content is None:
        return patch.object(_mod, "THREAT_MODEL_PATH", tmp_path / "nonexistent.md")
    p = tmp_path / "THREAT_MODEL.md"
    p.write_text(content, encoding="utf-8")
    return patch.object(_mod, "THREAT_MODEL_PATH", p)


# ---------------------------------------------------------------------------
# File existence check
# ---------------------------------------------------------------------------

class TestFileExists(unittest.TestCase):

    def test_passes_with_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 0)

    def test_fails_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no_such_file.md"
            with patch.object(_mod, "THREAT_MODEL_PATH", missing):
                code = run_checks(quiet=True)
        self.assertEqual(code, 1)

    def test_fails_when_file_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text("", encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# Gap IDs check
# ---------------------------------------------------------------------------

class TestGapIds(unittest.TestCase):

    def test_all_gap_ids_present_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 0)

    def test_missing_gap_id_fails(self):
        partial = [g for g in REQUIRED_GAP_IDS if g != "SE-003"]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(gap_ids=partial), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 1)

    def test_required_gap_ids_list(self):
        self.assertEqual(REQUIRED_GAP_IDS, ["SE-001", "SE-002", "SE-003",
                                             "SE-004", "SE-005", "SE-006"])


# ---------------------------------------------------------------------------
# Date check
# ---------------------------------------------------------------------------

class TestDate(unittest.TestCase):

    def test_date_present_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(date="2026-03-10"), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 0)

    def test_no_date_fails(self):
        content = _minimal_doc(date=None)
        # Ensure no date pattern sneaks in
        content = content.replace("2026", "XXXX")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(content, encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# Controls check
# ---------------------------------------------------------------------------

class TestControls(unittest.TestCase):

    def test_all_controls_present_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 0)

    def test_missing_control_fails(self):
        partial = [c for c in REQUIRED_CONTROLS if c != "ToolScopePolicy"]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(controls=partial), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                code = run_checks(quiet=True)
        self.assertEqual(code, 1)

    def test_hitl_policy_required(self):
        self.assertIn("HitlPolicy", REQUIRED_CONTROLS)

    def test_tool_scope_policy_required(self):
        self.assertIn("ToolScopePolicy", REQUIRED_CONTROLS)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

class TestJsonOutput(unittest.TestCase):

    def test_json_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=True)
                data = json.loads(mock_out.getvalue())
        self.assertIn("threat_model_ok", data)
        self.assertIn("checks", data)
        self.assertIn("path", data)

    def test_json_ok_true_on_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=True)
                data = json.loads(mock_out.getvalue())
        self.assertTrue(data["threat_model_ok"])

    def test_json_ok_false_on_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no_file.md"
            with patch.object(_mod, "THREAT_MODEL_PATH", missing), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=True)
                data = json.loads(mock_out.getvalue())
        self.assertFalse(data["threat_model_ok"])


# ---------------------------------------------------------------------------
# Text output
# ---------------------------------------------------------------------------

class TestTextOutput(unittest.TestCase):

    def test_pass_message_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=False)
                output = mock_out.getvalue()
        self.assertIn("PASS", output)

    def test_fail_message_shown_on_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no_file.md"
            with patch.object(_mod, "THREAT_MODEL_PATH", missing), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=False, as_json=False)
                output = mock_out.getvalue()
        self.assertIn("FAIL", output)

    def test_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(quiet=True)
                output = mock_out.getvalue()
        self.assertEqual(output, "")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_int(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p):
                rc = _mod.main(["--quiet"])
        self.assertIsInstance(rc, int)

    def test_main_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "THREAT_MODEL.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch.object(_mod, "THREAT_MODEL_PATH", p), \
                 patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--json"])
                data = json.loads(mock_out.getvalue())
        self.assertIn("threat_model_ok", data)


# ---------------------------------------------------------------------------
# Live document passes all checks
# ---------------------------------------------------------------------------

class TestLiveDocument(unittest.TestCase):

    def test_actual_threat_model_passes(self):
        """The real docs/THREAT_MODEL.md should pass all required checks."""
        code = run_checks(quiet=True)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
