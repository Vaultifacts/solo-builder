"""Tests for solo_builder/api/validators.py (TASK-327 / SE-030 to SE-035)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
from solo_builder.api.validators import require_string_fields, MAX_FIELD_LEN


class _Base(unittest.TestCase):
    """Shared test base with patched paths — mirrors test_api_integration._Base."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        cfg = Path(self._tmp) / "config"
        cfg.mkdir()
        self._settings_path = cfg / "settings.json"
        try:
            src = json.loads(app_module.SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            src = {"STALL_THRESHOLD": 5}
        self._settings_path.write_text(json.dumps(src), encoding="utf-8")

        self._patches = [
            patch.object(app_module, "STATE_PATH",              new=self._state_path),
            patch.object(app_module, "TRIGGER_PATH",            new=sp / "run_trigger"),
            patch.object(app_module, "VERIFY_TRIGGER",          new=sp / "verify_trigger.json"),
            patch.object(app_module, "DESCRIBE_TRIGGER",        new=sp / "describe_trigger.json"),
            patch.object(app_module, "TOOLS_TRIGGER",           new=sp / "tools_trigger.json"),
            patch.object(app_module, "SET_TRIGGER",             new=sp / "set_trigger.json"),
            patch.object(app_module, "HEARTBEAT_PATH",          new=sp / "step.txt"),
            patch.object(app_module, "OUTPUTS_PATH",            new=Path(self._tmp) / "out.md"),
            patch.object(app_module, "JOURNAL_PATH",            new=Path(self._tmp) / "journal.md"),
            patch.object(app_module, "SETTINGS_PATH",           new=self._settings_path),
            patch.object(app_module, "ADD_TASK_TRIGGER",        new=sp / "add_task_trigger.json"),
            patch.object(app_module, "ADD_BRANCH_TRIGGER",      new=sp / "add_branch_trigger.json"),
            patch.object(app_module, "PRIORITY_BRANCH_TRIGGER", new=sp / "prioritize_branch_trigger.json"),
            patch.object(app_module, "UNDO_TRIGGER",            new=sp / "undo_trigger"),
            patch.object(app_module, "DEPENDS_TRIGGER",         new=sp / "depends_trigger.json"),
            patch.object(app_module, "UNDEPENDS_TRIGGER",       new=sp / "undepends_trigger.json"),
            patch.object(app_module, "RESET_TRIGGER",           new=sp / "reset_trigger"),
            patch.object(app_module, "SNAPSHOT_TRIGGER",        new=sp / "snapshot_trigger"),
            patch.object(app_module, "PAUSE_TRIGGER",           new=sp / "pause_trigger"),
            patch.object(app_module, "DAG_IMPORT_TRIGGER",      new=sp / "dag_import_trigger.json"),
            patch.object(app_module, "HEAL_TRIGGER",            new=sp / "heal_trigger.json"),
            patch.object(app_module, "CACHE_DIR",               new=Path(self._tmp) / "cache"),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestRequireStringFieldsUnit(unittest.TestCase):
    """Unit tests for require_string_fields() using a minimal Flask app context."""

    def setUp(self):
        from flask import Flask
        self.app = Flask(__name__)

    def _call(self, body, required, optional=()):
        with self.app.test_request_context(
            "/",
            method="POST",
            data=json.dumps(body),
            content_type="application/json",
        ):
            return require_string_fields(required, optional)

    def test_valid_body_returns_none(self):
        result = self._call({"spec": "do something"}, required=("spec",))
        self.assertIsNone(result)

    def test_missing_required_field_returns_400(self):
        resp, code = self._call({}, required=("spec",))
        self.assertEqual(code, 400)
        self.assertIn("spec", resp.get_json()["reason"])

    def test_non_dict_body_returns_400(self):
        with self.app.test_request_context(
            "/", method="POST", data="[]", content_type="application/json"
        ):
            resp, code = require_string_fields(("spec",))
        self.assertEqual(code, 400)

    def test_integer_field_returns_400(self):
        resp, code = self._call({"spec": 42}, required=("spec",))
        self.assertEqual(code, 400)
        self.assertIn("string", resp.get_json()["reason"])

    def test_blank_field_returns_400(self):
        resp, code = self._call({"spec": "   "}, required=("spec",))
        self.assertEqual(code, 400)

    def test_oversized_field_returns_400(self):
        long_val = "x" * (MAX_FIELD_LEN + 1)
        resp, code = self._call({"spec": long_val}, required=("spec",))
        self.assertEqual(code, 400)
        self.assertIn("maximum length", resp.get_json()["reason"])

    def test_exactly_max_length_is_valid(self):
        val = "x" * MAX_FIELD_LEN
        result = self._call({"spec": val}, required=("spec",))
        self.assertIsNone(result)

    def test_optional_field_wrong_type_returns_400(self):
        resp, code = self._call({"spec": "ok", "note": 123}, required=("spec",), optional=("note",))
        self.assertEqual(code, 400)

    def test_optional_field_absent_is_valid(self):
        result = self._call({"spec": "ok"}, required=("spec",), optional=("note",))
        self.assertIsNone(result)

    def test_multiple_required_fields(self):
        result = self._call({"task": "T0", "spec": "do it"}, required=("task", "spec"))
        self.assertIsNone(result)

    def test_multiple_required_fields_one_missing(self):
        resp, code = self._call({"task": "T0"}, required=("task", "spec"))
        self.assertEqual(code, 400)
        self.assertIn("spec", resp.get_json()["reason"])


class TestTriggerEndpointsValidation(_Base):
    """Integration tests verifying trigger endpoints reject invalid bodies."""

    def _post(self, url, body):
        return self.client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_heal_missing_subtask_returns_400(self):
        r = self._post("/heal", {})
        self.assertEqual(r.status_code, 400)

    def test_heal_integer_subtask_returns_400(self):
        r = self._post("/heal", {"subtask": 99})
        self.assertEqual(r.status_code, 400)

    def test_add_task_missing_spec_returns_400(self):
        r = self._post("/add_task", {})
        self.assertEqual(r.status_code, 400)

    def test_add_branch_missing_task_returns_400(self):
        r = self._post("/add_branch", {"spec": "do something"})
        self.assertEqual(r.status_code, 400)

    def test_depends_missing_dep_returns_400(self):
        r = self._post("/depends", {"target": "Task 1"})
        self.assertEqual(r.status_code, 400)

    def test_undepends_missing_target_returns_400(self):
        r = self._post("/undepends", {"dep": "Task 0"})
        self.assertEqual(r.status_code, 400)

    def test_prioritize_branch_missing_branch_returns_400(self):
        r = self._post("/prioritize_branch", {"task": "Task 0"})
        self.assertEqual(r.status_code, 400)

    def test_non_json_body_returns_400(self):
        r = self.client.post("/add_task", data="not json", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_oversized_spec_returns_400(self):
        r = self._post("/add_task", {"spec": "x" * (MAX_FIELD_LEN + 1)})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
