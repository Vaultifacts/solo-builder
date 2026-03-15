"""Tests for utils/trigger_registry.py — TriggerRegistry class and pre-registered defaults."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_UTILS_DIR = Path(__file__).resolve().parents[1] / "utils"
_spec = importlib.util.spec_from_file_location(
    "trigger_registry", _UTILS_DIR / "trigger_registry.py"
)
_mod = importlib.util.module_from_spec(_spec)
import sys as _sys
_sys.modules["trigger_registry"] = _mod
_spec.loader.exec_module(_mod)

TriggerRegistry = _mod.TriggerRegistry
TriggerDef = _mod.TriggerDef
get_default_registry = _mod.get_default_registry


# ---------------------------------------------------------------------------
# TriggerDef
# ---------------------------------------------------------------------------

class TestTriggerDef(unittest.TestCase):

    def test_frozen_dataclass(self):
        """TriggerDef is immutable (frozen)."""
        t = TriggerDef("test", "test_file", "json")
        with self.assertRaises(AttributeError):
            t.name = "changed"

    def test_handler_key_defaults_to_none(self):
        """handler_key is optional, defaults to None."""
        t = TriggerDef("test", "test_file", "json")
        self.assertIsNone(t.handler_key)

    def test_handler_key_explicit(self):
        """handler_key can be explicitly set."""
        t = TriggerDef("verify", "verify_trigger.json", "json",
                       handler_key="verify_dispatch")
        self.assertEqual(t.handler_key, "verify_dispatch")


# ---------------------------------------------------------------------------
# TriggerRegistry — registration and basic access
# ---------------------------------------------------------------------------

class TestTriggerRegistryRegistration(unittest.TestCase):

    def setUp(self):
        """Create a fresh registry for each test."""
        self.reg = TriggerRegistry()

    def test_register_json_trigger(self):
        """Register a JSON trigger."""
        self.reg.register("verify", "verify_trigger.json", "json")
        self.assertIn("verify", self.reg._triggers)
        defn = self.reg._triggers["verify"]
        self.assertEqual(defn.format, "json")

    def test_register_presence_trigger(self):
        """Register a presence (flag) trigger."""
        self.reg.register("run", "run_trigger", "presence")
        defn = self.reg._triggers["run"]
        self.assertEqual(defn.format, "presence")

    def test_register_text_trigger(self):
        """Register a text-format trigger."""
        self.reg.register("note", "note_trigger.txt", "text")
        defn = self.reg._triggers["note"]
        self.assertEqual(defn.format, "text")

    def test_register_invalid_format_raises(self):
        """Registering an unknown format raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.reg.register("bad", "bad_trigger", "unknown_format")
        self.assertIn("Unknown format_type", str(ctx.exception))

    def test_handler_key_defaults_to_name(self):
        """When handler_key not specified, register() defaults it to trigger name."""
        self.reg.register("verify", "verify_trigger.json", "json")
        defn = self.reg._triggers["verify"]
        # register() defaults handler_key to the trigger name
        self.assertEqual(defn.handler_key, "verify")

    def test_handler_key_explicit(self):
        """handler_key can be explicitly set."""
        self.reg.register("verify", "verify_trigger.json", "json",
                         handler_key="custom_key")
        defn = self.reg._triggers["verify"]
        self.assertEqual(defn.handler_key, "custom_key")

    def test_get_trigger_path(self):
        """get_trigger_path returns absolute path."""
        self.reg.register("verify", "verify_trigger.json", "json")
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.reg.get_trigger_path(tmp_dir, "verify")
            self.assertTrue(path.startswith(tmp_dir))
            self.assertTrue(path.endswith("verify_trigger.json"))

    def test_get_trigger_path_unknown_trigger_raises(self):
        """Getting path for unknown trigger raises KeyError."""
        with self.assertRaises(KeyError):
            self.reg.get_trigger_path("/tmp", "unknown")

    def test_get_all_trigger_paths(self):
        """get_all_trigger_paths returns dict of all paths."""
        self.reg.register("verify", "verify_trigger.json", "json")
        self.reg.register("run", "run_trigger", "presence")
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = self.reg.get_all_trigger_paths(tmp_dir)
            self.assertEqual(len(paths), 2)
            self.assertIn("verify", paths)
            self.assertIn("run", paths)


# ---------------------------------------------------------------------------
# TriggerRegistry — JSON trigger operations
# ---------------------------------------------------------------------------

class TestTriggerRegistryJsonOperations(unittest.TestCase):

    def setUp(self):
        self.reg = TriggerRegistry()
        self.reg.register("verify", "verify_trigger.json", "json")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = self.tmpdir.name

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_write_json_trigger(self):
        """write() creates JSON trigger file."""
        data = {"subtask": "ST-001", "note": "test"}
        self.reg.write(self.state_dir, "verify", data)
        path = os.path.join(self.state_dir, "verify_trigger.json")
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            written = json.load(f)
        self.assertEqual(written, data)

    def test_consume_json_trigger(self):
        """consume() reads, parses, and deletes JSON trigger."""
        data = {"subtask": "ST-001", "note": "test"}
        path = os.path.join(self.state_dir, "verify_trigger.json")
        with open(path, "w") as f:
            json.dump(data, f)

        result = self.reg.consume(self.state_dir, "verify")
        self.assertEqual(result, data)
        self.assertFalse(os.path.exists(path))

    def test_consume_json_missing_returns_none(self):
        """consume() returns None for missing JSON trigger."""
        result = self.reg.consume(self.state_dir, "verify")
        self.assertIsNone(result)

    def test_consume_json_malformed_no_quarantine_deletes(self):
        """consume() with quarantine=False deletes malformed JSON."""
        path = os.path.join(self.state_dir, "verify_trigger.json")
        with open(path, "w") as f:
            f.write("{bad json")

        result = self.reg.consume(self.state_dir, "verify", quarantine=False)
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(path))

    def test_consume_json_malformed_with_quarantine_moves_to_bad(self):
        """consume() with quarantine=True moves malformed JSON to .bad."""
        path = os.path.join(self.state_dir, "verify_trigger.json")
        with open(path, "w") as f:
            f.write("{bad json")

        result = self.reg.consume(self.state_dir, "verify", quarantine=True)
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(path + ".bad"))

    def test_consume_unknown_trigger_raises(self):
        """consume() raises KeyError for unknown trigger."""
        with self.assertRaises(KeyError):
            self.reg.consume(self.state_dir, "unknown")

    def test_write_without_data_uses_empty_dict(self):
        """write() with data=None writes empty dict for JSON triggers."""
        self.reg.write(self.state_dir, "verify", None)
        path = os.path.join(self.state_dir, "verify_trigger.json")
        with open(path) as f:
            written = json.load(f)
        self.assertEqual(written, {})


# ---------------------------------------------------------------------------
# TriggerRegistry — presence (flag) trigger operations
# ---------------------------------------------------------------------------

class TestTriggerRegistryPresenceOperations(unittest.TestCase):

    def setUp(self):
        self.reg = TriggerRegistry()
        self.reg.register("run", "run_trigger", "presence")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = self.tmpdir.name

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_write_presence_trigger(self):
        """write() creates presence trigger file."""
        self.reg.write(self.state_dir, "run")
        path = os.path.join(self.state_dir, "run_trigger")
        self.assertTrue(os.path.exists(path))

    def test_consume_presence_trigger_returns_true_and_deletes(self):
        """consume() for presence trigger returns True and deletes file."""
        path = os.path.join(self.state_dir, "run_trigger")
        with open(path, "w") as f:
            f.write("1")

        result = self.reg.consume(self.state_dir, "run")
        self.assertTrue(result)
        self.assertFalse(os.path.exists(path))

    def test_consume_presence_missing_returns_false(self):
        """consume() returns False for missing presence trigger."""
        result = self.reg.consume(self.state_dir, "run")
        self.assertFalse(result)

    def test_exists_presence_trigger(self):
        """exists() returns True for presence trigger that exists."""
        path = os.path.join(self.state_dir, "run_trigger")
        with open(path, "w") as f:
            f.write("1")
        self.assertTrue(self.reg.exists(self.state_dir, "run"))

    def test_exists_presence_trigger_missing(self):
        """exists() returns False for missing presence trigger."""
        self.assertFalse(self.reg.exists(self.state_dir, "run"))


# ---------------------------------------------------------------------------
# TriggerRegistry — check_all
# ---------------------------------------------------------------------------

class TestTriggerRegistryCheckAll(unittest.TestCase):

    def setUp(self):
        self.reg = TriggerRegistry()
        self.reg.register("verify", "verify_trigger.json", "json")
        self.reg.register("run", "run_trigger", "presence")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = self.tmpdir.name

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_check_all_empty_registry(self):
        """check_all on empty state_dir returns empty dict."""
        fired = self.reg.check_all(self.state_dir)
        self.assertEqual(fired, {})

    def test_check_all_finds_json_trigger(self):
        """check_all finds and returns JSON trigger content."""
        data = {"subtask": "ST-001"}
        path = os.path.join(self.state_dir, "verify_trigger.json")
        with open(path, "w") as f:
            json.dump(data, f)

        fired = self.reg.check_all(self.state_dir)
        self.assertIn("verify", fired)
        self.assertEqual(fired["verify"], data)

    def test_check_all_finds_presence_trigger(self):
        """check_all finds presence trigger and returns True."""
        path = os.path.join(self.state_dir, "run_trigger")
        with open(path, "w") as f:
            f.write("1")

        fired = self.reg.check_all(self.state_dir)
        self.assertIn("run", fired)
        self.assertTrue(fired["run"])

    def test_check_all_finds_multiple_triggers(self):
        """check_all finds all fired triggers."""
        data = {"subtask": "ST-001"}
        with open(os.path.join(self.state_dir, "verify_trigger.json"), "w") as f:
            json.dump(data, f)
        with open(os.path.join(self.state_dir, "run_trigger"), "w") as f:
            f.write("1")

        fired = self.reg.check_all(self.state_dir)
        self.assertEqual(len(fired), 2)
        self.assertIn("verify", fired)
        self.assertIn("run", fired)

    def test_check_all_does_not_consume(self):
        """check_all does not delete trigger files."""
        data = {"subtask": "ST-001"}
        path = os.path.join(self.state_dir, "verify_trigger.json")
        with open(path, "w") as f:
            json.dump(data, f)

        self.reg.check_all(self.state_dir)
        self.assertTrue(os.path.exists(path))

    def test_check_all_malformed_json_returns_none(self):
        """check_all returns None for malformed JSON trigger."""
        path = os.path.join(self.state_dir, "verify_trigger.json")
        with open(path, "w") as f:
            f.write("{bad")

        fired = self.reg.check_all(self.state_dir)
        self.assertIn("verify", fired)
        self.assertIsNone(fired["verify"])


# ---------------------------------------------------------------------------
# TriggerRegistry — cleanup_stale
# ---------------------------------------------------------------------------

class TestTriggerRegistryCleanupStale(unittest.TestCase):

    def setUp(self):
        self.reg = TriggerRegistry()
        self.reg.register("verify", "verify_trigger.json", "json")
        self.reg.register("run", "run_trigger", "presence")
        self.reg.register("stop", "stop_trigger", "presence")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_dir = self.tmpdir.name

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_cleanup_stale_removes_all_triggers(self):
        """cleanup_stale removes all registered triggers."""
        # Create all triggers
        with open(os.path.join(self.state_dir, "verify_trigger.json"), "w") as f:
            json.dump({"x": 1}, f)
        with open(os.path.join(self.state_dir, "run_trigger"), "w") as f:
            f.write("1")
        with open(os.path.join(self.state_dir, "stop_trigger"), "w") as f:
            f.write("1")

        count = self.reg.cleanup_stale(self.state_dir)
        self.assertEqual(count, 3)
        self.assertFalse(os.path.exists(os.path.join(self.state_dir, "verify_trigger.json")))
        self.assertFalse(os.path.exists(os.path.join(self.state_dir, "run_trigger")))
        self.assertFalse(os.path.exists(os.path.join(self.state_dir, "stop_trigger")))

    def test_cleanup_stale_respects_exclude(self):
        """cleanup_stale excludes specified triggers."""
        # Create all triggers
        with open(os.path.join(self.state_dir, "run_trigger"), "w") as f:
            f.write("1")
        with open(os.path.join(self.state_dir, "stop_trigger"), "w") as f:
            f.write("1")

        count = self.reg.cleanup_stale(self.state_dir, exclude=["run"])
        self.assertEqual(count, 1)
        self.assertTrue(os.path.exists(os.path.join(self.state_dir, "run_trigger")))
        self.assertFalse(os.path.exists(os.path.join(self.state_dir, "stop_trigger")))

    def test_cleanup_stale_missing_files_ignored(self):
        """cleanup_stale ignores missing trigger files."""
        # Create no triggers
        count = self.reg.cleanup_stale(self.state_dir)
        self.assertEqual(count, 0)  # nothing removed


# ---------------------------------------------------------------------------
# Default registry
# ---------------------------------------------------------------------------

class TestDefaultRegistry(unittest.TestCase):

    def test_get_default_registry_returns_singleton(self):
        """get_default_registry returns same instance on multiple calls."""
        reg1 = get_default_registry()
        reg2 = get_default_registry()
        self.assertIs(reg1, reg2)

    def test_default_registry_has_all_standard_triggers(self):
        """Default registry has all 18 standard triggers."""
        reg = get_default_registry()
        expected_triggers = {
            # Presence
            "run", "stop", "pause", "reset", "snapshot", "undo",
            # JSON
            "verify", "describe", "tools", "set", "rename", "heal",
            "add_task", "add_branch", "prioritize_branch",
            "depends", "undepends", "dag_import",
        }
        for name in expected_triggers:
            self.assertIn(name, reg._triggers,
                         f"Missing trigger: {name}")
        self.assertEqual(len(reg._triggers), len(expected_triggers))

    def test_default_registry_presence_triggers(self):
        """Default registry has correct presence triggers."""
        reg = get_default_registry()
        for name in ["run", "stop", "pause", "reset", "snapshot", "undo"]:
            defn = reg._triggers[name]
            self.assertEqual(defn.format, "presence",
                           f"{name} should be presence format")

    def test_default_registry_json_triggers(self):
        """Default registry has correct JSON triggers."""
        reg = get_default_registry()
        for name in ["verify", "describe", "tools", "set", "rename", "heal",
                     "add_task", "add_branch", "prioritize_branch",
                     "depends", "undepends"]:
            defn = reg._triggers[name]
            self.assertEqual(defn.format, "json",
                           f"{name} should be JSON format")

    def test_default_registry_verify_trigger(self):
        """Verify trigger is properly registered."""
        reg = get_default_registry()
        verify_defn = reg._triggers["verify"]
        self.assertEqual(verify_defn.filename, "verify_trigger.json")
        self.assertEqual(verify_defn.format, "json")

    def test_default_registry_run_trigger(self):
        """Run trigger is properly registered."""
        reg = get_default_registry()
        run_defn = reg._triggers["run"]
        self.assertEqual(run_defn.filename, "run_trigger")
        self.assertEqual(run_defn.format, "presence")

    def test_default_registry_add_task_trigger(self):
        """add_task trigger is properly registered."""
        reg = get_default_registry()
        add_task_defn = reg._triggers["add_task"]
        self.assertEqual(add_task_defn.filename, "add_task_trigger.json")
        self.assertEqual(add_task_defn.format, "json")

    def test_default_registry_operations(self):
        """Default registry supports all standard operations."""
        reg = get_default_registry()
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Write and consume JSON
            reg.write(tmp_dir, "verify", {"subtask": "ST-001"})
            result = reg.consume(tmp_dir, "verify")
            self.assertEqual(result["subtask"], "ST-001")

            # Write and consume presence
            reg.write(tmp_dir, "run")
            result = reg.consume(tmp_dir, "run")
            self.assertTrue(result)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestTriggerRegistryIntegration(unittest.TestCase):

    def test_full_workflow_json_trigger(self):
        """Complete workflow: register, write, check, consume."""
        reg = TriggerRegistry()
        reg.register("describe", "describe_trigger.json", "json")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Write
            data = {"subtask": "ST-123", "desc": "new description"}
            reg.write(tmp_dir, "describe", data)

            # Check (without consuming)
            fired = reg.check_all(tmp_dir)
            self.assertEqual(fired["describe"], data)

            # Consume
            result = reg.consume(tmp_dir, "describe")
            self.assertEqual(result, data)

            # File is gone
            self.assertFalse(os.path.exists(os.path.join(tmp_dir, "describe_trigger.json")))

    def test_full_workflow_presence_trigger(self):
        """Complete workflow for presence trigger."""
        reg = TriggerRegistry()
        reg.register("stop", "stop_trigger", "presence")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Check before write
            self.assertFalse(reg.exists(tmp_dir, "stop"))

            # Write
            reg.write(tmp_dir, "stop")
            self.assertTrue(reg.exists(tmp_dir, "stop"))

            # Check all
            fired = reg.check_all(tmp_dir)
            self.assertTrue(fired.get("stop"))

            # Consume
            result = reg.consume(tmp_dir, "stop")
            self.assertTrue(result)
            self.assertFalse(os.path.exists(os.path.join(tmp_dir, "stop_trigger")))

    def test_multiple_triggers_in_workflow(self):
        """Workflow with multiple different trigger types."""
        reg = TriggerRegistry()
        reg.register("add_task", "add_task_trigger.json", "json")
        reg.register("run", "run_trigger", "presence")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Write both
            reg.write(tmp_dir, "add_task", {"spec": "new task"})
            reg.write(tmp_dir, "run")

            # Check all
            fired = reg.check_all(tmp_dir)
            self.assertEqual(len(fired), 2)
            self.assertEqual(fired["add_task"]["spec"], "new task")
            self.assertTrue(fired["run"])

            # Consume one
            result = reg.consume(tmp_dir, "add_task")
            self.assertEqual(result["spec"], "new task")

            # Other still exists
            fired = reg.check_all(tmp_dir)
            self.assertEqual(len(fired), 1)
            self.assertNotIn("add_task", fired)
            self.assertIn("run", fired)


if __name__ == "__main__":
    unittest.main()
