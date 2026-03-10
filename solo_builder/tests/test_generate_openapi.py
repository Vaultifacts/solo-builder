"""Tests for tools/generate_openapi.py (TASK-345, DK-005, DK-006)."""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "generate_openapi", _TOOLS_DIR / "generate_openapi.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_spec    = _mod.build_spec
_operation_id = _mod._operation_id
_ROUTES       = _mod._ROUTES


# ---------------------------------------------------------------------------
# _operation_id
# ---------------------------------------------------------------------------

class TestOperationId(unittest.TestCase):

    def test_simple_get(self):
        result = _operation_id("get", "/status")
        self.assertEqual(result, "getStatus")

    def test_nested_path(self):
        result = _operation_id("get", "/tasks/{task_id}/progress")
        self.assertEqual(result, "getTasksTaskIdProgress")

    def test_post_method(self):
        result = _operation_id("post", "/trigger")
        self.assertEqual(result, "postTrigger")

    def test_empty_path(self):
        result = _operation_id("get", "/")
        self.assertEqual(result, "get")

    def test_hyphen_converted(self):
        result = _operation_id("get", "/bulk-reset")
        self.assertEqual(result, "getBulkReset")


# ---------------------------------------------------------------------------
# build_spec — structure
# ---------------------------------------------------------------------------

class TestBuildSpec(unittest.TestCase):

    def setUp(self):
        self.spec = build_spec()

    def test_openapi_version(self):
        self.assertEqual(self.spec["openapi"], "3.0.3")

    def test_info_present(self):
        self.assertIn("info", self.spec)
        self.assertIn("title", self.spec["info"])
        self.assertIn("version", self.spec["info"])

    def test_servers_present(self):
        self.assertIn("servers", self.spec)
        self.assertIsInstance(self.spec["servers"], list)
        self.assertGreater(len(self.spec["servers"]), 0)

    def test_local_server_url(self):
        urls = [s["url"] for s in self.spec["servers"]]
        self.assertTrue(any("127.0.0.1" in u for u in urls))

    def test_paths_present(self):
        self.assertIn("paths", self.spec)
        self.assertIsInstance(self.spec["paths"], dict)
        self.assertGreater(len(self.spec["paths"]), 0)

    def test_tags_present(self):
        self.assertIn("tags", self.spec)
        self.assertIsInstance(self.spec["tags"], list)

    def test_required_tags_exist(self):
        tag_names = {t["name"] for t in self.spec["tags"]}
        for expected in ("Core", "Metrics", "Tasks", "Branches", "History",
                         "Subtasks", "Triggers", "Control", "Config", "DAG"):
            self.assertIn(expected, tag_names)


# ---------------------------------------------------------------------------
# build_spec — paths
# ---------------------------------------------------------------------------

class TestBuildSpecPaths(unittest.TestCase):

    def setUp(self):
        self.spec = build_spec()
        self.paths = self.spec["paths"]

    def test_health_endpoint_present(self):
        self.assertIn("/health", self.paths)

    def test_status_endpoint_present(self):
        self.assertIn("/status", self.paths)

    def test_metrics_summary_present(self):
        self.assertIn("/metrics/summary", self.paths)

    def test_dag_summary_present(self):
        self.assertIn("/dag/summary", self.paths)

    def test_each_operation_has_summary(self):
        for path, methods in self.paths.items():
            for method, op in methods.items():
                self.assertIn("summary", op, f"{method.upper()} {path} missing summary")

    def test_each_operation_has_tags(self):
        for path, methods in self.paths.items():
            for method, op in methods.items():
                self.assertIn("tags", op)
                self.assertIsInstance(op["tags"], list)
                self.assertGreater(len(op["tags"]), 0)

    def test_each_operation_has_200_response(self):
        for path, methods in self.paths.items():
            for method, op in methods.items():
                self.assertIn("200", op.get("responses", {}),
                              f"{method.upper()} {path} missing 200 response")

    def test_task_progress_path_present(self):
        self.assertIn("/tasks/{task_id}/progress", self.paths)

    def test_subtasks_bulk_reset_present(self):
        self.assertIn("/subtasks/bulk-reset", self.paths)

    def test_metrics_export_present(self):
        self.assertIn("/metrics/export", self.paths)


# ---------------------------------------------------------------------------
# _ROUTES catalogue completeness
# ---------------------------------------------------------------------------

class TestRoutesCatalogue(unittest.TestCase):

    def test_all_routes_have_required_keys(self):
        for route in _ROUTES:
            for key in ("path", "method", "tag", "summary"):
                self.assertIn(key, route, f"Route {route} missing '{key}'")

    def test_methods_are_valid_http_verbs(self):
        valid = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        for route in _ROUTES:
            self.assertIn(route["method"].upper(), valid)

    def test_no_duplicate_path_method_combinations(self):
        seen: set[tuple[str, str]] = set()
        for route in _ROUTES:
            key = (route["path"], route["method"].upper())
            self.assertNotIn(key, seen, f"Duplicate route: {key}")
            seen.add(key)

    def test_at_least_30_routes(self):
        self.assertGreaterEqual(len(_ROUTES), 30)


# ---------------------------------------------------------------------------
# main() — output modes
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_0(self):
        with patch("sys.stdout", new_callable=io.StringIO):
            rc = _mod.main(["--quiet"])
        self.assertEqual(rc, 0)

    def test_main_json_to_stdout(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            _mod.main([])
            output = mock_out.getvalue()
        data = json.loads(output)
        self.assertEqual(data["openapi"], "3.0.3")

    def test_main_write_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "spec.json")
            with patch("sys.stdout", new_callable=io.StringIO):
                rc = _mod.main(["--output", out, "--quiet"])
            self.assertEqual(rc, 0)
            data = json.loads(Path(out).read_text(encoding="utf-8"))
        self.assertIn("openapi", data)

    def test_main_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "spec.json")
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--output", out, "--quiet"])
                output = mock_out.getvalue()
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
