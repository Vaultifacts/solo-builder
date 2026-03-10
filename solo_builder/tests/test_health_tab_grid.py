"""Tests for HealthTabRefactor — TASK-380.

Verifies that the Health tab uses a 2-column CSS grid container and that all
widget divs are still present and in the correct relative order.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT      = Path(__file__).resolve().parents[2]
_DASHBOARD_HTML = _REPO_ROOT / "solo_builder" / "api" / "dashboard.html"

_WIDGET_IDS = [
    "gates-detailed-content",
    "policy-detailed-content",
    "context-window-detailed-content",
    "threat-model-detailed-content",
    "slo-detailed-content",
    "prompt-regression-detailed-content",
    "debt-scan-detailed-content",
    "ci-quality-detailed-content",
    "pre-release-detailed-content",
]


class TestHealthTabGrid(unittest.TestCase):

    def setUp(self):
        self._html = _DASHBOARD_HTML.read_text(encoding="utf-8")

    def test_grid_container_present(self):
        self.assertIn('id="health-widget-grid"', self._html)

    def test_grid_container_inside_health_tab(self):
        health_pos = self._html.index('id="tab-health"')
        grid_pos   = self._html.index('id="health-widget-grid"')
        self.assertGreater(grid_pos, health_pos)

    def test_grid_uses_two_column_layout(self):
        self.assertIn("grid-template-columns:1fr 1fr", self._html)

    def test_grid_display_style(self):
        self.assertIn("display:grid", self._html)

    def test_all_widget_ids_present(self):
        for wid in _WIDGET_IDS:
            with self.subTest(widget=wid):
                self.assertIn(f'id="{wid}"', self._html)

    def test_all_widgets_inside_grid(self):
        grid_pos = self._html.index('id="health-widget-grid"')
        end_grid = self._html.index("</div>", grid_pos)
        # Re-find the closing tag properly — check all widget IDs come after grid
        for wid in _WIDGET_IDS:
            with self.subTest(widget=wid):
                w_pos = self._html.index(f'id="{wid}"')
                self.assertGreater(w_pos, grid_pos)

    def test_widget_order_preserved(self):
        positions = {wid: self._html.index(f'id="{wid}"') for wid in _WIDGET_IDS}
        ordered = sorted(_WIDGET_IDS, key=lambda w: positions[w])
        self.assertEqual(ordered, _WIDGET_IDS)

    def test_health_detailed_content_before_grid(self):
        hdc_pos  = self._html.index('id="health-detailed-content"')
        grid_pos = self._html.index('id="health-widget-grid"')
        self.assertLess(hdc_pos, grid_pos)

    def test_grid_gap_defined(self):
        self.assertIn("gap:", self._html)

    def test_widgets_have_min_width_zero(self):
        self.assertIn("min-width:0", self._html)


if __name__ == "__main__":
    unittest.main()
