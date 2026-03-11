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

    def test_export_get_present(self):
        self.assertIn("/export", self.paths)
        self.assertIn("get", self.paths["/export"])

    def test_export_post_present(self):
        self.assertIn("/export", self.paths)
        self.assertIn("post", self.paths["/export"])

    def test_stats_present(self):
        self.assertIn("/stats", self.paths)

    def test_search_present(self):
        self.assertIn("/search", self.paths)

    def test_journal_present(self):
        self.assertIn("/journal", self.paths)

    def test_shortcuts_present(self):
        self.assertIn("/shortcuts", self.paths)

    def test_add_task_present(self):
        self.assertIn("/add_task", self.paths)
        self.assertIn("post", self.paths["/add_task"])

    def test_subtask_by_id_present(self):
        self.assertIn("/subtask/{subtask_id}", self.paths)

    def test_tasks_export_present(self):
        self.assertIn("/tasks/export", self.paths)

    def test_cache_get_present(self):
        self.assertIn("/cache", self.paths)
        self.assertIn("get", self.paths["/cache"])

    def test_cache_delete_present(self):
        self.assertIn("/cache", self.paths)
        self.assertIn("delete", self.paths["/cache"])

    def test_executor_gates_present(self):
        self.assertIn("/executor/gates", self.paths)

    def test_config_reset_present(self):
        self.assertIn("/config/reset", self.paths)
        self.assertIn("post", self.paths["/config/reset"])

    def test_phantom_routes_absent(self):
        """Phantom routes that have no Flask blueprint must NOT appear in spec."""
        for phantom in ("/cache/stats", "/cache/clear", "/webhook/test", "/health/executor-gates"):
            self.assertNotIn(phantom, self.paths, f"Phantom route still in spec: {phantom}")

    def test_add_task_has_request_body(self):
        op = self.paths["/add_task"]["post"]
        self.assertIn("requestBody", op)
        self.assertTrue(op["requestBody"]["required"])

    def test_verify_has_request_body(self):
        op = self.paths["/verify"]["post"]
        self.assertIn("requestBody", op)

    def test_dag_import_has_request_body(self):
        op = self.paths["/dag/import"]["post"]
        self.assertIn("requestBody", op)

    def test_add_branch_has_request_body(self):
        op = self.paths["/add_branch"]["post"]
        self.assertIn("requestBody", op)
        props = op["requestBody"]["content"]["application/json"]["schema"]["properties"]
        self.assertIn("spec", props)

    def test_each_post_with_body_has_400_response(self):
        for path, methods in self.paths.items():
            for method, op in methods.items():
                if "requestBody" in op:
                    self.assertIn("400", op.get("responses", {}),
                                  f"{method.upper()} {path} has requestBody but missing 400 response")

    def test_task_detail_has_path_param(self):
        op = self.paths["/tasks/{task_id}"]["get"]
        params = op.get("parameters", [])
        names = [p["name"] for p in params]
        self.assertIn("task_id", names)
        path_param = next(p for p in params if p["name"] == "task_id")
        self.assertEqual(path_param["in"], "path")
        self.assertTrue(path_param["required"])

    def test_subtask_detail_has_path_param(self):
        op = self.paths["/subtask/{subtask_id}"]["get"]
        params = op.get("parameters", [])
        self.assertTrue(any(p["name"] == "subtask_id" and p["in"] == "path" for p in params))

    def test_history_has_query_params(self):
        op = self.paths["/history"]["get"]
        params = op.get("parameters", [])
        query_names = {p["name"] for p in params if p["in"] == "query"}
        self.assertIn("since", query_names)
        self.assertIn("limit", query_names)
        self.assertIn("page", query_names)

    def test_search_has_query_param(self):
        op = self.paths["/search"]["get"]
        params = op.get("parameters", [])
        self.assertTrue(any(p["name"] == "q" and p["in"] == "query" for p in params))

    def test_path_params_are_required(self):
        for path, methods in self.paths.items():
            for op in methods.values():
                for param in op.get("parameters", []):
                    if param["in"] == "path":
                        self.assertTrue(param["required"],
                                        f"Path param {param['name']} in {path} must be required")

    def test_status_has_response_schema(self):
        op = self.paths["/status"]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("step", schema["properties"])
        self.assertIn("verified", schema["properties"])

    def test_health_has_response_schema(self):
        op = self.paths["/health"]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("ok", schema["properties"])
        self.assertIn("version", schema["properties"])

    def test_history_has_response_schema(self):
        op = self.paths["/history"]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("events", schema["properties"])
        self.assertIn("total", schema["properties"])

    def test_tasks_has_response_schema(self):
        op = self.paths["/tasks"]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("tasks", schema["properties"])


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

    def test_at_least_90_routes(self):
        # 90 real routes after removing phantom entries
        self.assertGreaterEqual(len(_ROUTES), 90)


# ---------------------------------------------------------------------------
# Live Flask url_map drift guard (TASK-389)
# ---------------------------------------------------------------------------

import re as _re
import sys as _sys
import tempfile as _tempfile

_SOLO_DIR = Path(__file__).resolve().parents[1]


def _flask_to_openapi(path: str) -> str:
    """Convert Flask path params (<type:name>) to OpenAPI style ({name})."""
    return _re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", path)


class TestLiveUrlMapDriftGuard(unittest.TestCase):
    """TASK-389: Live Flask url_map must match _ROUTES exactly (no drift)."""

    @classmethod
    def setUpClass(cls):
        _sys.path.insert(0, str(_SOLO_DIR))
        import api.app as _app_mod  # noqa: PLC0415
        cls._app = _app_mod.app
        cls._spec_routes: set[tuple[str, str]] = {
            (r["method"].upper(), r["path"]) for r in _ROUTES
        }
        cls._flask_routes: set[tuple[str, str]] = set()
        for rule in cls._app.url_map.iter_rules():
            if rule.rule.startswith("/static"):
                continue
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                cls._flask_routes.add((method, _flask_to_openapi(rule.rule)))

    def test_no_blueprint_route_missing_from_spec(self):
        """Every live Flask route must appear in _ROUTES."""
        missing = self._flask_routes - self._spec_routes
        self.assertEqual(
            missing, set(),
            f"Blueprint routes not in _ROUTES: {sorted(missing)}"
        )

    def test_no_phantom_routes_in_spec(self):
        """Every _ROUTES entry must correspond to a real Flask route."""
        phantoms = self._spec_routes - self._flask_routes
        self.assertEqual(
            phantoms, set(),
            f"Spec routes with no matching Flask blueprint: {sorted(phantoms)}"
        )

    def test_route_counts_match(self):
        self.assertEqual(len(self._flask_routes), len(self._spec_routes))


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
