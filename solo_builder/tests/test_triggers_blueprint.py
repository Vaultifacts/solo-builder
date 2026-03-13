"""Tests for triggers blueprint — POST /verify, /describe, /tools, /rename, /heal,
/add_task, /add_branch, /prioritize_branch, /depends, /undepends."""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        sp = Path(self._tmp) / "state"
        sp.mkdir()
        self._state_path = sp / "solo_builder_state.json"
        self._state_path.write_text("{}", encoding="utf-8")
        self._settings_path = Path(self._tmp) / "settings.json"
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "STATE_PATH", new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
            patch.object(app_module, "VERIFY_TRIGGER", new=sp / "verify_trigger.json"),
            patch.object(app_module, "DESCRIBE_TRIGGER", new=sp / "describe_trigger.json"),
            patch.object(app_module, "TOOLS_TRIGGER", new=sp / "tools_trigger.json"),
            patch.object(app_module, "RENAME_TRIGGER", new=sp / "rename_trigger.json"),
            patch.object(app_module, "HEAL_TRIGGER", new=sp / "heal_trigger.json"),
            patch.object(app_module, "ADD_TASK_TRIGGER", new=sp / "add_task_trigger.json"),
            patch.object(app_module, "ADD_BRANCH_TRIGGER", new=sp / "add_branch_trigger.json"),
            patch.object(app_module, "PRIORITY_BRANCH_TRIGGER", new=sp / "priority_branch_trigger.json"),
            patch.object(app_module, "DEPENDS_TRIGGER", new=sp / "depends_trigger.json"),
            patch.object(app_module, "UNDEPENDS_TRIGGER", new=sp / "undepends_trigger.json"),
            patch.object(app_module, "CACHE_DIR", new=Path(self._tmp) / "cache"),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestVerifyTrigger(_Base):
    def test_verify_with_subtask(self):
        r = self.client.post("/verify", json={"subtask": "st-1"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["subtask"], "ST-1")

    def test_verify_missing_subtask(self):
        r = self.client.post("/verify", json={})
        self.assertEqual(r.status_code, 400)


class TestDescribeTrigger(_Base):
    def test_describe_with_subtask(self):
        r = self.client.post("/describe", json={"subtask": "st-1", "desc": "new desc"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["subtask"], "ST-1")

    def test_describe_missing_subtask(self):
        r = self.client.post("/describe", json={})
        self.assertEqual(r.status_code, 400)


class TestToolsTrigger(_Base):
    def test_tools_with_subtask(self):
        r = self.client.post("/tools", json={"subtask": "st-2", "tools": "Read,Grep"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])

    def test_tools_missing_subtask(self):
        r = self.client.post("/tools", json={})
        self.assertEqual(r.status_code, 400)


class TestRenameTrigger(_Base):
    def test_rename_with_subtask(self):
        r = self.client.post("/rename", json={"subtask": "st-3", "desc": "new name"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])

    def test_rename_missing_subtask(self):
        r = self.client.post("/rename", json={})
        self.assertEqual(r.status_code, 400)


class TestHealTrigger(_Base):
    def test_heal_success(self):
        r = self.client.post("/heal", json={"subtask": "st-4"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["subtask"], "ST-4")
        trigger = json.loads((Path(self._tmp) / "state" / "heal_trigger.json").read_text())
        self.assertEqual(trigger["subtask"], "ST-4")

    def test_heal_missing_subtask(self):
        r = self.client.post("/heal", json={})
        self.assertEqual(r.status_code, 400)

    def test_heal_non_string_subtask(self):
        r = self.client.post("/heal", json={"subtask": 123})
        self.assertEqual(r.status_code, 400)


class TestAddTaskTrigger(_Base):
    def test_add_task_success(self):
        r = self.client.post("/add_task", json={"spec": "Do something"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["spec"], "Do something")
        trigger = json.loads((Path(self._tmp) / "state" / "add_task_trigger.json").read_text())
        self.assertEqual(trigger["spec"], "Do something")

    def test_add_task_missing_spec(self):
        r = self.client.post("/add_task", json={})
        self.assertEqual(r.status_code, 400)

    def test_add_task_blank_spec(self):
        r = self.client.post("/add_task", json={"spec": "   "})
        self.assertEqual(r.status_code, 400)


class TestAddBranchTrigger(_Base):
    def test_add_branch_success(self):
        r = self.client.post("/add_branch", json={"task": "TASK-1", "spec": "new branch"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["task"], "TASK-1")
        self.assertEqual(d["spec"], "new branch")

    def test_add_branch_missing_task(self):
        r = self.client.post("/add_branch", json={"spec": "x"})
        self.assertEqual(r.status_code, 400)

    def test_add_branch_missing_spec(self):
        r = self.client.post("/add_branch", json={"task": "TASK-1"})
        self.assertEqual(r.status_code, 400)


class TestPrioritizeBranchTrigger(_Base):
    def test_prioritize_branch_success(self):
        r = self.client.post("/prioritize_branch", json={"task": "TASK-1", "branch": "main"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["task"], "TASK-1")
        self.assertEqual(d["branch"], "main")

    def test_prioritize_branch_missing_branch(self):
        r = self.client.post("/prioritize_branch", json={"task": "TASK-1"})
        self.assertEqual(r.status_code, 400)


class TestDependsTrigger(_Base):
    def test_depends_success(self):
        r = self.client.post("/depends", json={"target": "TASK-2", "dep": "TASK-1"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["target"], "TASK-2")
        self.assertEqual(d["dep"], "TASK-1")
        trigger = json.loads((Path(self._tmp) / "state" / "depends_trigger.json").read_text())
        self.assertEqual(trigger["target"], "TASK-2")

    def test_depends_missing_target(self):
        r = self.client.post("/depends", json={"dep": "TASK-1"})
        self.assertEqual(r.status_code, 400)

    def test_depends_missing_dep(self):
        r = self.client.post("/depends", json={"target": "TASK-2"})
        self.assertEqual(r.status_code, 400)


class TestUndependsTrigger(_Base):
    def test_undepends_success(self):
        r = self.client.post("/undepends", json={"target": "TASK-2", "dep": "TASK-1"})
        self.assertEqual(r.status_code, 202)
        d = r.get_json()
        self.assertTrue(d["ok"])
        trigger = json.loads((Path(self._tmp) / "state" / "undepends_trigger.json").read_text())
        self.assertEqual(trigger["dep"], "TASK-1")

    def test_undepends_missing_fields(self):
        r = self.client.post("/undepends", json={})
        self.assertEqual(r.status_code, 400)

    def test_undepends_non_json_body(self):
        r = self.client.post("/undepends", data="not json",
                             content_type="text/plain")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
