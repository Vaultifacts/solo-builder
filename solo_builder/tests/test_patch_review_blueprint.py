"""Tests for api/blueprints/patch_review.py — GET /health/patch-review."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module
from api.app import app


class TestPatchReviewEndpoint(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    # ── Missing stats file ───────────────────────────────────────────────

    def test_missing_stats_returns_defaults(self):
        """When stats file is absent the endpoint returns zero counts."""
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.data)
        self.assertTrue(d["ok"])
        self.assertEqual(d["threshold_hits"], 0)
        self.assertEqual(d["total_rejections"], 0)
        self.assertEqual(d["rejected_subtasks"], [])

    def test_missing_stats_enabled_defaults_true(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertTrue(d["enabled"])

    def test_missing_stats_max_rejections_defaults_3(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertEqual(d["max_rejections"], 3)

    # ── Real stats file ──────────────────────────────────────────────────

    def _write_stats(self, tmp: str, data: dict) -> Path:
        p = Path(tmp) / "patch_review_stats.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_reads_threshold_hits(self):
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "enabled": True, "threshold_hits": 5,
                "total_rejections": 8, "max_rejections": 3,
                "rejected_subtasks": [],
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertEqual(d["threshold_hits"], 5)
        self.assertEqual(d["total_rejections"], 8)

    def test_reads_rejected_subtasks(self):
        import api.blueprints.patch_review as pr_mod
        subtasks = [{"name": "A1", "count": 2, "last_reason": "bad output"}]
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "enabled": True, "threshold_hits": 1,
                "total_rejections": 2, "max_rejections": 3,
                "rejected_subtasks": subtasks,
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertEqual(len(d["rejected_subtasks"]), 1)
        self.assertEqual(d["rejected_subtasks"][0]["name"], "A1")
        self.assertEqual(d["rejected_subtasks"][0]["count"], 2)

    def test_reads_enabled_false(self):
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "enabled": False, "threshold_hits": 0,
                "total_rejections": 0, "max_rejections": 3,
                "rejected_subtasks": [],
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertFalse(d["enabled"])

    def test_always_returns_ok_true(self):
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "enabled": True, "threshold_hits": 99,
                "total_rejections": 100, "max_rejections": 3,
                "rejected_subtasks": [],
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertTrue(d["ok"])

    def test_corrupt_stats_file_returns_defaults(self):
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "patch_review_stats.json"
            p.write_text("not json!!", encoding="utf-8")
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.data)
        self.assertTrue(d["ok"])
        self.assertEqual(d["threshold_hits"], 0)

    def test_content_type_is_json(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        self.assertIn("application/json", resp.content_type)

    def test_method_not_allowed(self):
        resp = self.client.post("/health/patch-review")
        self.assertEqual(resp.status_code, 405)

    # ── Wiring ───────────────────────────────────────────────────────────

    def test_blueprint_registered_in_app(self):
        rules = [r.rule for r in app.url_map.iter_rules()]
        self.assertIn("/health/patch-review", rules)

    def test_patch_review_in_dashboard_panels_js(self):
        panels = (
            Path(__file__).resolve().parents[1]
            / "api" / "static" / "dashboard_panels.js"
        )
        src = panels.read_text(encoding="utf-8")
        self.assertIn("pollPatchReviewDetailed", src)

    def test_patch_review_in_dashboard_js(self):
        dash = (
            Path(__file__).resolve().parents[1]
            / "api" / "static" / "dashboard.js"
        )
        src = dash.read_text(encoding="utf-8")
        self.assertIn("pollPatchReviewDetailed", src)

    def test_patch_review_div_in_dashboard_html(self):
        html = (
            Path(__file__).resolve().parents[1]
            / "api" / "dashboard.html"
        )
        src = html.read_text(encoding="utf-8")
        self.assertIn("patch-review-detailed-content", src)


# ── _write_patch_stats in executor ──────────────────────────────────────────

class TestWritePatchStats(unittest.TestCase):

    def test_write_patch_stats_creates_file(self):
        from runners.executor import _write_patch_stats
        from agents.patch_reviewer import PatchReviewer
        import types

        reviewer = PatchReviewer.__new__(PatchReviewer)
        reviewer.enabled = True
        reviewer.threshold_hits = 2
        reviewer.max_rejections = 3
        reviewer._rejections = {
            "A1": {"count": 1, "reasons": ["bad output"]},
            "B2": {"count": 3, "reasons": ["danger", "still bad", "too short"]},
        }

        import runners.executor as ex_mod
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = os.path.join(tmp, "patch_review_stats.json")
            with patch.object(ex_mod, "_PATCH_STATS_PATH", stats_path):
                _write_patch_stats(reviewer)
            with open(stats_path, encoding="utf-8") as f:
                data = json.loads(f.read())

        self.assertEqual(data["threshold_hits"], 2)
        self.assertEqual(data["total_rejections"], 4)
        self.assertEqual(data["enabled"], True)
        names = {r["name"] for r in data["rejected_subtasks"]}
        self.assertIn("A1", names)
        self.assertIn("B2", names)

    def test_write_patch_stats_last_reason(self):
        from runners.executor import _write_patch_stats
        from agents.patch_reviewer import PatchReviewer

        reviewer = PatchReviewer.__new__(PatchReviewer)
        reviewer.enabled = True
        reviewer.threshold_hits = 0
        reviewer.max_rejections = 3
        reviewer._rejections = {
            "C1": {"count": 2, "reasons": ["first", "second"]},
        }

        import runners.executor as ex_mod
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = os.path.join(tmp, "patch_review_stats.json")
            with patch.object(ex_mod, "_PATCH_STATS_PATH", stats_path):
                _write_patch_stats(reviewer)
            with open(stats_path, encoding="utf-8") as f:
                data = json.loads(f.read())

        entry = data["rejected_subtasks"][0]
        self.assertEqual(entry["last_reason"], "second")

    def test_write_patch_stats_ioerror_is_silent(self):
        """OSError on write must not propagate."""
        from runners.executor import _write_patch_stats
        from agents.patch_reviewer import PatchReviewer

        reviewer = PatchReviewer.__new__(PatchReviewer)
        reviewer.enabled = True
        reviewer.threshold_hits = 0
        reviewer.max_rejections = 3
        reviewer._rejections = {}

        import runners.executor as ex_mod
        # Point to a directory path — writing to a dir raises OSError
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ex_mod, "_PATCH_STATS_PATH", tmp):
                _write_patch_stats(reviewer)  # must not raise


if __name__ == "__main__":
    unittest.main()
