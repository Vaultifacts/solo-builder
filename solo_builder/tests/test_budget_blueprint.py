"""Tests for api/blueprints/budget.py — GET /health/budget."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_app():
    from api.app import app
    app.config["TESTING"] = True
    return app.test_client()


class TestHealthBudgetBasic(unittest.TestCase):

    def test_returns_200(self):
        client = _make_app()
        r = client.get("/health/budget")
        self.assertEqual(r.status_code, 200)

    def test_response_has_ok(self):
        client = _make_app()
        d = json.loads(client.get("/health/budget").data)
        self.assertIn("ok", d)
        self.assertTrue(d["ok"])

    def test_response_has_required_keys(self):
        client = _make_app()
        d = json.loads(client.get("/health/budget").data)
        for key in ("has_limits", "max_cost_usd", "max_total_tokens",
                    "max_api_calls_per_step", "total_api_calls",
                    "total_succeeded", "total_steps",
                    "sdk_success_rate", "recent_steps"):
            self.assertIn(key, d, f"missing key: {key}")

    def test_total_steps_is_int(self):
        client = _make_app()
        d = json.loads(client.get("/health/budget").data)
        self.assertIsInstance(d["total_steps"], int)

    def test_recent_steps_is_list(self):
        client = _make_app()
        d = json.loads(client.get("/health/budget").data)
        self.assertIsInstance(d["recent_steps"], list)

    def test_success_rate_null_when_no_calls(self):
        from api.blueprints.budget import _load_metrics
        with patch("api.blueprints.budget._load_metrics", return_value=[]):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertIsNone(d["sdk_success_rate"])

    def test_success_rate_computed(self):
        records = [
            {"sdk_dispatched": 4, "sdk_succeeded": 3, "step": 1, "elapsed_s": 1.0},
        ]
        with patch("api.blueprints.budget._load_metrics", return_value=records):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertAlmostEqual(d["sdk_success_rate"], 0.75)

    def test_total_api_calls_summed(self):
        records = [
            {"sdk_dispatched": 3, "sdk_succeeded": 2, "step": 1},
            {"sdk_dispatched": 5, "sdk_succeeded": 5, "step": 2},
        ]
        with patch("api.blueprints.budget._load_metrics", return_value=records):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertEqual(d["total_api_calls"], 8)
            self.assertEqual(d["total_succeeded"], 7)
            self.assertEqual(d["total_steps"], 2)

    def test_recent_steps_capped_at_5(self):
        records = [{"sdk_dispatched": 1, "sdk_succeeded": 1, "step": i} for i in range(10)]
        with patch("api.blueprints.budget._load_metrics", return_value=records):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertLessEqual(len(d["recent_steps"]), 5)

    def test_recent_steps_shape(self):
        records = [{"sdk_dispatched": 2, "sdk_succeeded": 1, "step": 7, "elapsed_s": 0.5}]
        with patch("api.blueprints.budget._load_metrics", return_value=records):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertEqual(len(d["recent_steps"]), 1)
            rs = d["recent_steps"][0]
            self.assertEqual(rs["step"], 7)
            self.assertEqual(rs["dispatched"], 2)
            self.assertEqual(rs["succeeded"], 1)
            self.assertAlmostEqual(rs["elapsed_s"], 0.5)

    def test_has_limits_false_when_none_configured(self):
        with patch("api.blueprints.budget._load_cfg", return_value={}):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertFalse(d["has_limits"])

    def test_has_limits_true_when_cost_set(self):
        with patch("api.blueprints.budget._load_cfg", return_value={"BUDGET_MAX_COST": 5.0}):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertTrue(d["has_limits"])
            self.assertEqual(d["max_cost_usd"], 5.0)

    def test_has_limits_true_when_tokens_set(self):
        with patch("api.blueprints.budget._load_cfg", return_value={"BUDGET_MAX_TOKENS": 10000}):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertTrue(d["has_limits"])
            self.assertEqual(d["max_total_tokens"], 10000)

    def test_missing_metrics_file(self):
        with patch("api.blueprints.budget._load_metrics", return_value=[]):
            client = _make_app()
            d = json.loads(client.get("/health/budget").data)
            self.assertEqual(d["total_steps"], 0)
            self.assertEqual(d["total_api_calls"], 0)

    def test_load_metrics_real_file(self):
        from api.blueprints.budget import _load_metrics
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"sdk_dispatched": 2, "sdk_succeeded": 2, "step": 1}) + "\n")
            f.write(json.dumps({"sdk_dispatched": 1, "sdk_succeeded": 0, "step": 2}) + "\n")
            fname = f.name
        with patch("api.blueprints.budget._METRICS_PATH", Path(fname)):
            records = _load_metrics()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["step"], 1)

    def test_load_metrics_skips_bad_json(self):
        from api.blueprints.budget import _load_metrics
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write("{good json}\n")  # invalid
            f.write(json.dumps({"step": 5}) + "\n")
            fname = f.name
        with patch("api.blueprints.budget._METRICS_PATH", Path(fname)):
            records = _load_metrics()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["step"], 5)


class TestHealthBudgetDashboardWidget(unittest.TestCase):
    """Verify the HTML element for the budget widget is present in dashboard.html."""

    def test_budget_div_in_html(self):
        html_path = (
            Path(__file__).resolve().parents[1] / "api" / "dashboard.html"
        )
        content = html_path.read_text(encoding="utf-8")
        self.assertIn("budget-detailed-content", content)

    def test_poll_budget_in_dashboard_js(self):
        js_path = (
            Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"
        )
        content = js_path.read_text(encoding="utf-8")
        self.assertIn("pollBudgetDetailed", content)

    def test_poll_budget_exported_from_panels(self):
        panels_path = (
            Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_panels.js"
        )
        content = panels_path.read_text(encoding="utf-8")
        self.assertIn("pollBudgetDetailed", content)

    def test_poll_budget_defined_in_health(self):
        health_path = (
            Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_health.js"
        )
        content = health_path.read_text(encoding="utf-8")
        self.assertIn("pollBudgetDetailed", content)
        self.assertIn("/health/budget", content)


if __name__ == "__main__":
    unittest.main()
