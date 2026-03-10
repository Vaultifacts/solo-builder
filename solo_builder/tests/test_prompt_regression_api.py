"""Tests for PromptRegressionAPI widget — TASK-376 (AI-002, AI-003).

Covers:
  1. dashboard.html — prompt-regression-detailed-content div present in Health tab
  2. dashboard_panels.js — pollPromptRegressionDetailed exported and well-formed
  3. dashboard.js — pollPromptRegressionDetailed imported and called in tick()
  4. GET /health/prompt-regression endpoint (shape, ok flag, results)
"""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
import api.blueprints.prompt_regression as pr_mod

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestPromptRegressionDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_div_present(self):
        self.assertIn('id="prompt-regression-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        pr_pos     = self._html.index('id="prompt-regression-detailed-content"')
        self.assertGreater(pr_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading prompt regression", self._html)

    def test_div_after_slo_div(self):
        slo_pos = self._html.index('id="slo-detailed-content"')
        pr_pos  = self._html.index('id="prompt-regression-detailed-content"')
        self.assertGreater(pr_pos, slo_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestPromptRegressionPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollPromptRegressionDetailed_exported(self):
        self.assertIn("export async function pollPromptRegressionDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/prompt-regression", self._js)

    def test_content_el_queried(self):
        self.assertIn("prompt-regression-detailed-content", self._js)

    def test_ok_flag_used(self):
        self.assertIn("d.ok", self._js)

    def test_total_rendered(self):
        self.assertIn("d.total", self._js)

    def test_failed_rendered(self):
        self.assertIn("d.failed", self._js)

    def test_template_name_rendered(self):
        self.assertIn("r.name", self._js)

    def test_errors_rendered(self):
        self.assertIn("r.errors", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_empty_state_message(self):
        self.assertIn("No templates registered", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestPromptRegressionMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollPromptRegressionDetailed_imported(self):
        self.assertIn("pollPromptRegressionDetailed", self._js)

    def test_pollPromptRegressionDetailed_called_in_tick(self):
        self.assertIn("pollPromptRegressionDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollPromptRegressionDetailed[^}]*\}\s*from\s*["\']./dashboard_panels\.js["\']'
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tr(name="tmpl", passed=True, errors=None):
    m = MagicMock()
    m.name = name
    m.passed = passed
    m.errors = errors or []
    return m


def _mock_prc(passed=True, total=3, failed=0, results=None):
    report = MagicMock()
    report.to_dict.return_value = {
        "passed": passed,
        "total":  total,
        "failed": failed,
        "results": results or [
            {"name": f"tmpl{i}", "passed": True, "errors": []}
            for i in range(total)
        ],
    }
    mod = MagicMock()
    mod.run_checks.return_value = report
    return mod


# ---------------------------------------------------------------------------
# 4. Endpoint tests
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path    = Path(self._tmp) / "state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._state_path.write_text(json.dumps({"step": 0, "dag": {}}), encoding="utf-8")
        self._settings_path.write_text("{}", encoding="utf-8")

        self._patches = [
            patch.object(app_module, "STATE_PATH",    new=self._state_path),
            patch.object(app_module, "SETTINGS_PATH", new=self._settings_path),
        ]
        for p in self._patches:
            p.start()
        app_module.app.config["TESTING"] = True
        app_module._rate_limiter._read  = collections.defaultdict(collections.deque)
        app_module._rate_limiter._write = collections.defaultdict(collections.deque)
        self.client = app_module.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _get(self, mod=None):
        if mod is None:
            mod = _mock_prc()
        with patch.object(pr_mod, "_load_tool", return_value=mod):
            return self.client.get("/health/prompt-regression")

    def _data(self, mod=None):
        return json.loads(self._get(mod=mod).data)


class TestPromptRegressionEndpointStatus(_Base):

    def test_status_200(self):
        self.assertEqual(self._get().status_code, 200)

    def test_content_type_json(self):
        self.assertIn("application/json", self._get().content_type)


class TestPromptRegressionEndpointShape(_Base):

    def test_ok_key_present(self):
        self.assertIn("ok", self._data())

    def test_passed_key_present(self):
        self.assertIn("passed", self._data())

    def test_total_key_present(self):
        self.assertIn("total", self._data())

    def test_failed_key_present(self):
        self.assertIn("failed", self._data())

    def test_results_key_present(self):
        self.assertIn("results", self._data())

    def test_results_is_list(self):
        self.assertIsInstance(self._data()["results"], list)


class TestPromptRegressionEndpointBehavior(_Base):

    def test_ok_true_when_all_pass(self):
        mod = _mock_prc(passed=True, failed=0)
        self.assertTrue(self._data(mod)["ok"])

    def test_ok_false_when_failures(self):
        mod = _mock_prc(passed=False, failed=1, results=[
            {"name": "tmpl1", "passed": False, "errors": ["too short"]},
        ])
        self.assertFalse(self._data(mod)["ok"])

    def test_total_count_returned(self):
        mod = _mock_prc(total=5)
        self.assertEqual(self._data(mod)["total"], 5)

    def test_failed_count_returned(self):
        mod = _mock_prc(passed=False, total=2, failed=1, results=[
            {"name": "t1", "passed": False, "errors": ["err"]},
            {"name": "t2", "passed": True,  "errors": []},
        ])
        self.assertEqual(self._data(mod)["failed"], 1)


if __name__ == "__main__":
    unittest.main()
