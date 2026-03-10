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


# ---------------------------------------------------------------------------
# TASK-360: Extended checks (SE-007 to SE-015)
# ---------------------------------------------------------------------------

# Re-import new symbols added by TASK-360
EXTENDED_GAP_IDS  = _mod.EXTENDED_GAP_IDS
EXTENDED_CONTROLS = _mod.EXTENDED_CONTROLS


def _full_doc() -> str:
    """Document passing baseline + extended checks."""
    lines = ["Last updated: 2026-03-10"]
    for gid in REQUIRED_GAP_IDS + EXTENDED_GAP_IDS:
        lines.append(f"| {gid} | desc | Resolved |")
    for ctrl in REQUIRED_CONTROLS + EXTENDED_CONTROLS:
        lines.append(f"Mentions {ctrl} control.")
    for n in range(1, 7):
        lines.append(f"### T-{n:03d} — threat")
    return "\n".join(lines)


class TestExtendedGapIds(unittest.TestCase):

    def test_extended_gap_ids_list_length(self):
        self.assertEqual(len(EXTENDED_GAP_IDS), 9)   # SE-007 … SE-015

    def test_first_and_last_extended_id(self):
        self.assertEqual(EXTENDED_GAP_IDS[0], "SE-007")
        self.assertEqual(EXTENDED_GAP_IDS[-1], "SE-015")

    def test_extended_check_passes_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_full_doc(), encoding="utf-8")
            code = run_checks(quiet=True, extended=True, path=p)
        self.assertEqual(code, 0)

    def test_extended_check_fails_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            # Only baseline gap IDs, no SE-007 to SE-015
            p.write_text(_minimal_doc(), encoding="utf-8")
            code = run_checks(quiet=True, extended=True, path=p)
        self.assertEqual(code, 1)

    def test_baseline_still_passes_without_extended_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            code = run_checks(quiet=True, extended=False, path=p)
        self.assertEqual(code, 0)

    def test_extended_check_includes_check_in_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_full_doc(), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(as_json=True, extended=True, path=p)
                data = json.loads(mock_out.getvalue())
        check_names = [c["name"] for c in data["checks"]]
        self.assertIn("extended-gap-ids", check_names)


class TestExtendedControls(unittest.TestCase):

    def test_extended_controls_list(self):
        self.assertIn("dep_severity_check", EXTENDED_CONTROLS)
        self.assertIn("context_window_compact", EXTENDED_CONTROLS)

    def test_ext_controls_pass_when_mentioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_full_doc(), encoding="utf-8")
            code = run_checks(quiet=True, extended=True, path=p)
        self.assertEqual(code, 0)

    def test_ext_controls_fail_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            # Include extended gap IDs but NOT extended controls
            lines = ["Last updated: 2026-03-10"]
            for gid in REQUIRED_GAP_IDS + EXTENDED_GAP_IDS:
                lines.append(f"| {gid} | desc |")
            for ctrl in REQUIRED_CONTROLS:
                lines.append(f"Mentions {ctrl}.")
            # No dep_severity_check or context_window_compact
            for n in range(1, 7):
                lines.append(f"### T-{n:03d} — threat")
            p.write_text("\n".join(lines), encoding="utf-8")
            code = run_checks(quiet=True, extended=True, path=p)
        self.assertEqual(code, 1)

    def test_ext_control_names_in_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_full_doc(), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(as_json=True, extended=True, path=p)
                data = json.loads(mock_out.getvalue())
        names = [c["name"] for c in data["checks"]]
        self.assertIn("ext-control-dep_severity_check", names)
        self.assertIn("ext-control-context_window_compact", names)


class TestPathOverride(unittest.TestCase):

    def test_custom_path_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "custom_threat_model.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            code = run_checks(quiet=True, path=p)
        self.assertEqual(code, 0)

    def test_nonexistent_custom_path_fails(self):
        code = run_checks(quiet=True, path="/nonexistent/TM.md")
        self.assertEqual(code, 1)


class TestGapMax(unittest.TestCase):

    def test_gap_max_10_checks_se001_to_se010(self):
        content = "2026-03-10\n" + "\n".join(
            f"SE-{n:03d}" for n in range(1, 11)
        ) + "\n" + "\n".join(REQUIRED_CONTROLS) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(content, encoding="utf-8")
            code = run_checks(quiet=True, path=p, gap_max=10)
        self.assertEqual(code, 0)

    def test_gap_max_10_fails_when_missing_se008(self):
        content = "2026-03-10\n" + "\n".join(
            f"SE-{n:03d}" for n in range(1, 8)  # only SE-001 to SE-007
        ) + "\n" + "\n".join(REQUIRED_CONTROLS) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(content, encoding="utf-8")
            code = run_checks(quiet=True, path=p, gap_max=10)
        self.assertEqual(code, 1)


class TestExtendedJsonOutput(unittest.TestCase):

    def test_json_includes_extended_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_full_doc(), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(as_json=True, extended=True, path=p)
                data = json.loads(mock_out.getvalue())
        self.assertIn("extended", data)
        self.assertTrue(data["extended"])

    def test_json_extended_false_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run_checks(as_json=True, path=p)
                data = json.loads(mock_out.getvalue())
        self.assertFalse(data.get("extended", False))


class TestMainExtended(unittest.TestCase):

    def test_main_extended_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_full_doc(), encoding="utf-8")
            rc = _mod.main(["--extended", "--quiet", "--path", str(p)])
        self.assertEqual(rc, 0)

    def test_main_path_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TM.md"
            p.write_text(_minimal_doc(), encoding="utf-8")
            rc = _mod.main(["--quiet", "--path", str(p)])
        self.assertEqual(rc, 0)

    def test_actual_threat_model_extended_passes(self):
        """The real docs/THREAT_MODEL.md should pass extended checks after TASK-360."""
        code = run_checks(quiet=True, extended=True)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
