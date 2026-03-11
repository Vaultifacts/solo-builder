"""Tests for OpenAPIHealthRoutes — TASK-383.

Verifies that all new health + policy endpoints are present in the
generate_openapi.py _ROUTES catalogue and appear in the built spec.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"

# ---------------------------------------------------------------------------
# Load generate_openapi module
# ---------------------------------------------------------------------------

def _load_openapi_mod():
    spec = importlib.util.spec_from_file_location(
        "generate_openapi", _TOOLS_DIR / "generate_openapi.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod    = _load_openapi_mod()
_ROUTES = _mod._ROUTES

_HEALTH_ROUTES = [
    "/health/detailed",
    "/health/context-window",
    "/health/threat-model",
    "/health/slo",
    "/health/prompt-regression",
    "/health/debt-scan",
    "/health/ci-quality",
    "/health/pre-release",
    "/health/live-summary",
]

_POLICY_ROUTES = [
    "/policy/hitl",
    "/policy/scope",
]


# ---------------------------------------------------------------------------
# Route catalogue tests
# ---------------------------------------------------------------------------

class TestHealthRoutesInCatalogue(unittest.TestCase):

    def _route_paths(self):
        return {r["path"] for r in _ROUTES}

    def test_health_detailed_present(self):
        self.assertIn("/health/detailed", self._route_paths())

    def test_executor_gates_present(self):
        self.assertIn("/executor/gates", self._route_paths())

    def test_health_context_window_present(self):
        self.assertIn("/health/context-window", self._route_paths())

    def test_health_threat_model_present(self):
        self.assertIn("/health/threat-model", self._route_paths())

    def test_health_slo_present(self):
        self.assertIn("/health/slo", self._route_paths())

    def test_health_prompt_regression_present(self):
        self.assertIn("/health/prompt-regression", self._route_paths())

    def test_health_debt_scan_present(self):
        self.assertIn("/health/debt-scan", self._route_paths())

    def test_health_ci_quality_present(self):
        self.assertIn("/health/ci-quality", self._route_paths())

    def test_health_pre_release_present(self):
        self.assertIn("/health/pre-release", self._route_paths())

    def test_health_live_summary_present(self):
        self.assertIn("/health/live-summary", self._route_paths())

    def test_policy_hitl_present(self):
        self.assertIn("/policy/hitl", self._route_paths())

    def test_policy_scope_present(self):
        self.assertIn("/policy/scope", self._route_paths())

    def test_all_health_routes_are_get(self):
        health_routes = [r for r in _ROUTES if r["path"] in _HEALTH_ROUTES]
        for r in health_routes:
            with self.subTest(path=r["path"]):
                self.assertEqual(r["method"], "GET")

    def test_all_health_routes_tagged_health(self):
        for path in _HEALTH_ROUTES:
            route = next((r for r in _ROUTES if r["path"] == path), None)
            with self.subTest(path=path):
                self.assertIsNotNone(route, f"{path} not in _ROUTES")
                self.assertEqual(route["tag"], "Health")

    def test_policy_routes_tagged_policy(self):
        for path in _POLICY_ROUTES:
            route = next((r for r in _ROUTES if r["path"] == path), None)
            with self.subTest(path=path):
                self.assertIsNotNone(route, f"{path} not in _ROUTES")
                self.assertEqual(route["tag"], "Policy")

    def test_total_routes_at_least_50(self):
        self.assertGreaterEqual(len(_ROUTES), 50)


# ---------------------------------------------------------------------------
# Built spec tests
# ---------------------------------------------------------------------------

class TestHealthRoutesInSpec(unittest.TestCase):

    def setUp(self):
        self._spec  = _mod.build_spec()
        self._paths = self._spec.get("paths", {})

    def test_health_detailed_in_spec(self):
        self.assertIn("/health/detailed", self._paths)

    def test_health_slo_in_spec(self):
        self.assertIn("/health/slo", self._paths)

    def test_health_debt_scan_in_spec(self):
        self.assertIn("/health/debt-scan", self._paths)

    def test_health_ci_quality_in_spec(self):
        self.assertIn("/health/ci-quality", self._paths)

    def test_health_pre_release_in_spec(self):
        self.assertIn("/health/pre-release", self._paths)

    def test_health_live_summary_in_spec(self):
        self.assertIn("/health/live-summary", self._paths)

    def test_policy_hitl_in_spec(self):
        self.assertIn("/policy/hitl", self._paths)

    def test_policy_scope_in_spec(self):
        self.assertIn("/policy/scope", self._paths)

    def test_health_tag_in_spec_tags(self):
        tags = [t["name"] for t in self._spec.get("tags", [])]
        self.assertIn("Health", tags)

    def test_policy_tag_in_spec_tags(self):
        tags = [t["name"] for t in self._spec.get("tags", [])]
        self.assertIn("Policy", tags)


if __name__ == "__main__":
    unittest.main()
