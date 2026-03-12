"""Smoke tests for dashboard_health.js module — TASK-410.

Verifies:
  1. All 12 health poller functions are exported from dashboard_health.js
  2. dashboard_panels.js re-exports all 12 via named re-export
  3. dashboard.js imports all 12 from dashboard_panels.js
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_HEALTH_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_health.js"
_PANELS_JS      = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard_panels.js"
_MAIN_JS        = _REPO_ROOT / "solo_builder" / "api" / "static" / "dashboard.js"

_EXPECTED_POLLERS = sorted([
    "pollGatesDetailed",
    "pollDebtScanDetailed",
    "pollPromptRegressionDetailed",
    "pollSloDetailed",
    "pollThreatModelDetailed",
    "pollContextWindowDetailed",
    "pollPolicyDetailed",
    "pollLiveSummaryDetailed",
    "pollHealthDetailed",
    "pollCiQualityDetailed",
    "pollPreReleaseDetailed",
    "pollRepoHealthDetailed",
])


class TestDashboardHealthExports(unittest.TestCase):
    """All 12 health pollers must be exported from dashboard_health.js."""

    def setUp(self):
        self._src = _HEALTH_JS.read_text(encoding="utf-8")

    def test_all_pollers_exported(self):
        exported = sorted(re.findall(r"export async function (\w+)", self._src))
        self.assertEqual(exported, _EXPECTED_POLLERS)

    def test_poller_count(self):
        count = len(re.findall(r"export async function ", self._src))
        self.assertEqual(count, 12)


class TestDashboardPanelsReExport(unittest.TestCase):
    """dashboard_panels.js must re-export all 12 pollers from dashboard_health.js."""

    def setUp(self):
        self._src = _PANELS_JS.read_text(encoding="utf-8")

    def test_reexport_line_exists(self):
        self.assertIn('from "./dashboard_health.js"', self._src)

    def test_all_pollers_reexported(self):
        for name in _EXPECTED_POLLERS:
            self.assertIn(name, self._src, f"{name} missing from dashboard_panels.js re-export")


class TestDashboardJsImports(unittest.TestCase):
    """dashboard.js must import all 12 health pollers."""

    def setUp(self):
        self._src = _MAIN_JS.read_text(encoding="utf-8")

    def test_all_pollers_imported(self):
        for name in _EXPECTED_POLLERS:
            self.assertIn(name, self._src, f"{name} missing from dashboard.js imports")


if __name__ == "__main__":
    unittest.main()
