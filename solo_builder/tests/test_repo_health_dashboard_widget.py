"""Tests for RepoHealthDashboardWidget — AAWO integration.

Covers:
  1. dashboard.html — repo-health-detailed-content div present in Health tab
  2. dashboard_panels.js — pollRepoHealthDetailed exported and well-formed
  3. dashboard.js — pollRepoHealthDetailed imported and called in tick()
"""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_health.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"


# ---------------------------------------------------------------------------
# 1. Dashboard HTML
# ---------------------------------------------------------------------------

class TestRepoHealthDashboardHtml(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_div_present(self):
        self.assertIn('id="repo-health-detailed-content"', self._html)

    def test_div_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        rh_pos     = self._html.index('id="repo-health-detailed-content"')
        self.assertGreater(rh_pos, health_pos)

    def test_loading_placeholder(self):
        self.assertIn("Loading AAWO repo health", self._html)

    def test_div_after_pre_release_div(self):
        pr_pos = self._html.index('id="pre-release-detailed-content"')
        rh_pos = self._html.index('id="repo-health-detailed-content"')
        self.assertGreater(rh_pos, pr_pos)


# ---------------------------------------------------------------------------
# 2. dashboard_panels.js
# ---------------------------------------------------------------------------

class TestRepoHealthPanelsJs(unittest.TestCase):

    def setUp(self):
        self._js = _PANELS_JS.read_text(encoding="utf-8")

    def test_pollRepoHealthDetailed_exported(self):
        self.assertIn("export async function pollRepoHealthDetailed", self._js)

    def test_endpoint_called(self):
        self.assertIn("/health/detailed", self._js)

    def test_content_el_queried(self):
        self.assertIn("repo-health-detailed-content", self._js)

    def test_repo_health_key_accessed(self):
        self.assertIn("repo_health", self._js)

    def test_available_flag_checked(self):
        self.assertIn("rh.available", self._js)

    def test_signals_rendered(self):
        self.assertIn("rh.signals", self._js)

    def test_complexity_rendered(self):
        self.assertIn("rh.complexity", self._js)

    def test_risk_factors_rendered(self):
        self.assertIn("risk_factors", self._js)

    def test_active_agents_rendered(self):
        self.assertIn("active_agents", self._js)

    def test_unavailable_message(self):
        self.assertIn("not configured", self._js)

    def test_aawo_path_hint(self):
        self.assertIn("AAWO_PATH", self._js)

    def test_replaceChildren_called(self):
        self.assertIn("replaceChildren", self._js)

    def test_header_shows_complexity(self):
        self.assertIn("AAWO ·", self._js)


# ---------------------------------------------------------------------------
# 3. dashboard.js
# ---------------------------------------------------------------------------

class TestRepoHealthMainJs(unittest.TestCase):

    def setUp(self):
        self._js = _MAIN_JS.read_text(encoding="utf-8")

    def test_pollRepoHealthDetailed_imported(self):
        self.assertIn("pollRepoHealthDetailed", self._js)

    def test_pollRepoHealthDetailed_called_in_tick(self):
        self.assertIn("pollRepoHealthDetailed()", self._js)

    def test_import_from_panels(self):
        self.assertRegex(
            self._js,
            r'import\s*\{[^}]*pollRepoHealthDetailed[^}]*\}\s*from\s*["\']\./dashboard_panels\.js["\']'
        )


if __name__ == "__main__":
    unittest.main()
