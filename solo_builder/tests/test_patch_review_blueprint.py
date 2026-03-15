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

    def test_get_includes_alert_threshold(self):
        """GET /health/patch-review always returns alert_threshold field."""
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertIn("alert_threshold", d)

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

    def test_reads_available_and_use_sdk(self):
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "enabled": True, "available": True, "use_sdk": True,
                "threshold_hits": 0, "total_rejections": 0,
                "max_rejections": 3, "rejected_subtasks": [],
                "recent_reviews": [],
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertTrue(d["available"])
        self.assertTrue(d["use_sdk"])

    def test_reads_recent_reviews(self):
        import api.blueprints.patch_review as pr_mod
        reviews = [{"step": 1, "approved": 3, "rejected": 1, "escalated": 0, "deferred": 0}]
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "enabled": True, "available": False, "use_sdk": True,
                "threshold_hits": 0, "total_rejections": 1,
                "max_rejections": 3, "rejected_subtasks": [],
                "recent_reviews": reviews,
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertEqual(len(d["recent_reviews"]), 1)
        self.assertEqual(d["recent_reviews"][0]["approved"], 3)

    def test_missing_stats_available_defaults_false(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertFalse(d["available"])

    def test_missing_stats_recent_reviews_defaults_empty(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertEqual(d["recent_reviews"], [])

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

    # ── /history endpoint ────────────────────────────────────────────────

    def test_history_route_registered(self):
        rules = [r.rule for r in app.url_map.iter_rules()]
        self.assertIn("/health/patch-review/history", rules)

    def test_history_empty_when_no_stats(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review/history")
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.data)
        self.assertTrue(d["ok"])
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["items"], [])
        self.assertEqual(d["page"], 1)
        self.assertEqual(d["pages"], 1)

    def test_history_returns_all_items(self):
        import api.blueprints.patch_review as pr_mod
        reviews = [{"step": i, "approved": 1} for i in range(5)]
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {"recent_reviews": reviews})
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review/history")
        d = json.loads(resp.data)
        self.assertEqual(d["total"], 5)
        self.assertEqual(len(d["items"]), 5)

    def test_history_pagination(self):
        import api.blueprints.patch_review as pr_mod
        reviews = [{"step": i} for i in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {"recent_reviews": reviews})
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review/history?limit=3&page=2")
        d = json.loads(resp.data)
        self.assertEqual(d["limit"], 3)
        self.assertEqual(d["page"], 2)
        self.assertEqual(len(d["items"]), 3)
        self.assertEqual(d["items"][0]["step"], 3)

    def test_history_limit_capped_at_100(self):
        import api.blueprints.patch_review as pr_mod
        reviews = [{"step": i} for i in range(20)]
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {"recent_reviews": reviews})
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review/history?limit=9999")
        d = json.loads(resp.data)
        self.assertEqual(d["limit"], 100)

    def test_history_invalid_params_use_defaults(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review/history?limit=bad&page=nope")
        d = json.loads(resp.data)
        self.assertEqual(d["limit"], 10)
        self.assertEqual(d["page"], 1)

    def test_history_pages_count(self):
        import api.blueprints.patch_review as pr_mod
        reviews = [{"step": i} for i in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {"recent_reviews": reviews})
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review/history?limit=3")
        d = json.loads(resp.data)
        self.assertEqual(d["pages"], 4)  # ceil(10/3)

    # ── Reset endpoint ───────────────────────────────────────────────────

    def test_reset_returns_ok(self):
        resp = self.client.post("/health/patch-review/reset")
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.data)
        self.assertTrue(d["ok"])

    def test_reset_deletes_stats_file(self):
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {"threshold_hits": 5, "total_rejections": 2,
                                        "enabled": True, "available": True, "use_sdk": True,
                                        "max_rejections": 3, "rejected_subtasks": [],
                                        "recent_reviews": []})
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.post("/health/patch-review/reset")
        d = json.loads(resp.data)
        self.assertTrue(d["reset"])
        self.assertFalse(p.exists())

    def test_reset_missing_file_still_returns_ok(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.post("/health/patch-review/reset")
        d = json.loads(resp.data)
        self.assertTrue(d["ok"])

    def test_reset_route_in_app(self):
        rules = [r.rule for r in app.url_map.iter_rules()]
        self.assertIn("/health/patch-review/reset", rules)

    # ── /health/detailed includes patch_review ───────────────────────────

    def test_health_detailed_includes_patch_review(self):
        resp = self.client.get("/health/detailed")
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.data)
        self.assertIn("patch_review", d["checks"])
        pr = d["checks"]["patch_review"]
        self.assertIn("ok", pr)
        self.assertIn("threshold_hits", pr)
        self.assertIn("total_rejections", pr)
        self.assertIn("alert_threshold", pr)

    def test_health_detailed_patch_review_ok_when_threshold_zero(self):
        """When PATCH_REVIEW_ALERT_THRESHOLD=0 (default), patch_review is always ok."""
        import api.blueprints.health_detailed as hd_mod
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "threshold_hits": 99, "total_rejections": 50,
                "enabled": True, "available": False, "use_sdk": True,
                "max_rejections": 3, "rejected_subtasks": [], "recent_reviews": [],
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/detailed")
        d = json.loads(resp.data)
        # threshold=0 → patch_review ok=True even with many hits
        self.assertTrue(d["checks"]["patch_review"]["ok"])

    def test_reads_max_reviews_per_step(self):
        import api.blueprints.patch_review as pr_mod
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_stats(tmp, {
                "enabled": True, "available": True, "use_sdk": True,
                "threshold_hits": 0, "total_rejections": 0,
                "max_rejections": 3, "max_reviews_per_step": 4,
                "rejected_subtasks": [], "recent_reviews": [],
            })
            with patch.object(pr_mod, "_STATS_PATH", p):
                resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertEqual(d["max_reviews_per_step"], 4)

    def test_missing_stats_max_reviews_per_step_defaults_zero(self):
        import api.blueprints.patch_review as pr_mod
        with patch.object(pr_mod, "_STATS_PATH", Path("/nonexistent/x.json")):
            resp = self.client.get("/health/patch-review")
        d = json.loads(resp.data)
        self.assertEqual(d["max_reviews_per_step"], 0)

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
        reviewer.available = True
        reviewer.use_sdk = True
        reviewer.threshold_hits = 2
        reviewer.max_rejections = 3
        reviewer.max_reviews_per_step = 0
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
        reviewer.available = False
        reviewer.use_sdk = True
        reviewer.threshold_hits = 0
        reviewer.max_rejections = 3
        reviewer.max_reviews_per_step = 0
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

    def test_write_patch_stats_appends_recent_reviews(self):
        from runners.executor import _write_patch_stats
        from agents.patch_reviewer import PatchReviewer

        reviewer = PatchReviewer.__new__(PatchReviewer)
        reviewer.enabled = True
        reviewer.available = True
        reviewer.use_sdk = True
        reviewer.threshold_hits = 0
        reviewer.max_rejections = 3
        reviewer.max_reviews_per_step = 0
        reviewer._rejections = {}

        import runners.executor as ex_mod
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = os.path.join(tmp, "patch_review_stats.json")
            with patch.object(ex_mod, "_PATCH_STATS_PATH", stats_path):
                _write_patch_stats(reviewer, step=5, pr_results={"A1": "approved", "B2": "rejected"})
                with open(stats_path, encoding="utf-8") as f:
                    data = json.loads(f.read())

        self.assertEqual(len(data["recent_reviews"]), 1)
        rv = data["recent_reviews"][0]
        self.assertEqual(rv["step"], 5)
        self.assertEqual(rv["approved"], 1)
        self.assertEqual(rv["rejected"], 1)

    def test_write_patch_stats_keeps_max_10_recent(self):
        from runners.executor import _write_patch_stats
        from agents.patch_reviewer import PatchReviewer

        reviewer = PatchReviewer.__new__(PatchReviewer)
        reviewer.enabled = True
        reviewer.available = False
        reviewer.use_sdk = True
        reviewer.threshold_hits = 0
        reviewer.max_rejections = 3
        reviewer.max_reviews_per_step = 0
        reviewer._rejections = {}

        import runners.executor as ex_mod
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = os.path.join(tmp, "patch_review_stats.json")
            with patch.object(ex_mod, "_PATCH_STATS_PATH", stats_path):
                for i in range(12):
                    _write_patch_stats(reviewer, step=i, pr_results={"X": "approved"})
                with open(stats_path, encoding="utf-8") as f:
                    data = json.loads(f.read())

        self.assertLessEqual(len(data["recent_reviews"]), 10)

    def test_write_patch_stats_ioerror_is_silent(self):
        """OSError on write must not propagate."""
        from runners.executor import _write_patch_stats
        from agents.patch_reviewer import PatchReviewer

        reviewer = PatchReviewer.__new__(PatchReviewer)
        reviewer.enabled = True
        reviewer.available = False
        reviewer.use_sdk = False
        reviewer.threshold_hits = 0
        reviewer.max_rejections = 3
        reviewer.max_reviews_per_step = 0
        reviewer._rejections = {}

        import runners.executor as ex_mod
        # Point to a directory path — writing to a dir raises OSError
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ex_mod, "_PATCH_STATS_PATH", tmp):
                _write_patch_stats(reviewer)  # must not raise


class TestRestorePatchStats(unittest.TestCase):

    def test_restore_loads_threshold_hits(self):
        from runners.executor import _restore_patch_stats, _write_patch_stats
        from agents.patch_reviewer import PatchReviewer

        # Write a stats file with known values
        import runners.executor as ex_mod
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = os.path.join(tmp, "patch_review_stats.json")
            Path(stats_path).write_text(json.dumps({
                "enabled": True, "available": False, "use_sdk": True,
                "threshold_hits": 7, "total_rejections": 4,
                "max_rejections": 3,
                "rejected_subtasks": [
                    {"name": "Z1", "count": 2, "last_reason": "bad"},
                ],
                "recent_reviews": [],
            }), encoding="utf-8")
            with patch.object(ex_mod, "_PATCH_STATS_PATH", stats_path):
                reviewer = PatchReviewer.__new__(PatchReviewer)
                reviewer.threshold_hits = 0
                reviewer._rejections = {}
                _restore_patch_stats(reviewer)

        self.assertEqual(reviewer.threshold_hits, 7)
        self.assertIn("Z1", reviewer._rejections)
        self.assertEqual(reviewer._rejections["Z1"]["count"], 2)

    def test_restore_missing_file_is_safe(self):
        from runners.executor import _restore_patch_stats
        from agents.patch_reviewer import PatchReviewer
        import runners.executor as ex_mod

        reviewer = PatchReviewer.__new__(PatchReviewer)
        reviewer.threshold_hits = 0
        reviewer._rejections = {}
        with patch.object(ex_mod, "_PATCH_STATS_PATH", "/nonexistent/x.json"):
            _restore_patch_stats(reviewer)  # must not raise

        self.assertEqual(reviewer.threshold_hits, 0)

    def test_restore_does_not_decrease_existing_count(self):
        """Restore uses max() so in-memory counts are never reduced."""
        from runners.executor import _restore_patch_stats
        from agents.patch_reviewer import PatchReviewer
        import runners.executor as ex_mod

        with tempfile.TemporaryDirectory() as tmp:
            stats_path = os.path.join(tmp, "x.json")
            Path(stats_path).write_text(json.dumps({
                "threshold_hits": 0, "rejected_subtasks": [
                    {"name": "A1", "count": 1, "last_reason": "old"},
                ],
            }), encoding="utf-8")
            reviewer = PatchReviewer.__new__(PatchReviewer)
            reviewer.threshold_hits = 0
            reviewer._rejections = {"A1": {"count": 3, "reasons": ["x"]}}
            with patch.object(ex_mod, "_PATCH_STATS_PATH", stats_path):
                _restore_patch_stats(reviewer)

        # File had count=1, in-memory had count=3 — should keep 3
        self.assertEqual(reviewer._rejections["A1"]["count"], 3)


if __name__ == "__main__":
    unittest.main()
