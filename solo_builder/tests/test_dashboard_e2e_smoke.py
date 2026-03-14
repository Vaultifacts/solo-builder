"""Dashboard E2E smoke tests — TASK-382.

Uses the Flask test client to verify:
  1. GET / returns valid dashboard HTML with key structural elements
  2. Key API endpoints return 200 with JSON content-type
  3. Health tab grid structure is present in the served HTML
  4. All JS module imports are referenced from the dashboard HTML
  5. Critical widget div IDs are present in the served HTML
"""
from __future__ import annotations

import collections
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.app as app_module

# ---------------------------------------------------------------------------
# Shared fixture base
# ---------------------------------------------------------------------------

class _Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._state_path    = Path(self._tmp) / "state.json"
        self._settings_path = Path(self._tmp) / "settings.json"
        self._state_path.write_text(
            json.dumps({"step": 0, "dag": {}}), encoding="utf-8"
        )
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


# ---------------------------------------------------------------------------
# 1. Dashboard HTML response
# ---------------------------------------------------------------------------

class TestDashboardHtmlResponse(_Base):

    def setUp(self):
        super().setUp()
        self._resp = self.client.get("/")
        self._html = self._resp.data.decode("utf-8", errors="replace")

    def test_status_200(self):
        self.assertEqual(self._resp.status_code, 200)

    def test_content_type_html(self):
        self.assertIn("text/html", self._resp.content_type)

    def test_doctype_present(self):
        self.assertIn("<!DOCTYPE html>", self._html)

    def test_title_present(self):
        self.assertIn("<title>", self._html)

    def test_health_tab_present(self):
        self.assertIn('id="tab-health"', self._html)

    def test_health_widget_grid_present(self):
        self.assertIn('id="health-widget-grid"', self._html)

    def test_live_summary_widget_present(self):
        self.assertIn('id="live-summary-detailed-content"', self._html)


# ---------------------------------------------------------------------------
# 2. Key API endpoints return 200 + JSON
# ---------------------------------------------------------------------------

_HEALTH_ENDPOINTS = [
    "/health",
    "/status",
    "/heartbeat",
]

_JSON_ENDPOINTS = [
    "/tasks",
    "/history/count",
    "/config",
]


class TestApiEndpointSmoke(_Base):

    def _check_endpoint(self, path: str):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, msg=f"GET {path} returned {resp.status_code}")
        self.assertIn("application/json", resp.content_type, msg=f"GET {path} not JSON")

    def test_health_returns_200(self):
        self._check_endpoint("/health")

    def test_status_returns_200(self):
        self._check_endpoint("/status")

    def test_heartbeat_returns_200(self):
        self._check_endpoint("/heartbeat")

    def test_tasks_returns_200(self):
        self._check_endpoint("/tasks")

    def test_history_count_returns_200(self):
        self._check_endpoint("/history/count")

    def test_config_returns_200(self):
        self._check_endpoint("/config")

    def test_health_version_matches_pyproject(self):
        resp = self.client.get("/health")
        data = resp.get_json()
        toml = Path(__file__).resolve().parents[1] / ".." / "pyproject.toml"
        version = None
        for line in toml.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version"):
                version = line.split("=")[1].strip().strip('"\'')
                break
        self.assertIsNotNone(version)
        self.assertEqual(data["version"], version)

    def test_404_returns_json(self):
        resp = self.client.get("/no-such-route-xyz")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("application/json", resp.content_type)

    def test_405_returns_json(self):
        resp = self.client.post("/health")
        self.assertEqual(resp.status_code, 405)
        self.assertIn("application/json", resp.content_type)


# ---------------------------------------------------------------------------
# 3. Health tab widget IDs in served HTML
# ---------------------------------------------------------------------------

_WIDGET_IDS = [
    "live-summary-detailed-content",
    "health-detailed-content",
    "health-widget-grid",
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


class TestDashboardWidgetIds(_Base):

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_all_widget_ids_present(self):
        for wid in _WIDGET_IDS:
            with self.subTest(widget=wid):
                self.assertIn(f'id="{wid}"', self._html)


# ---------------------------------------------------------------------------
# 4. JS modules referenced from HTML
# ---------------------------------------------------------------------------

_JS_MODULES = [
    "dashboard_panels.js",
    "dashboard.js",
    "dashboard_state.js",
    "dashboard_utils.js",
    "dashboard_tasks.js",
]

# Sub-modules that dashboard_panels.js re-exports from
_PANEL_SUBMODULES = [
    "dashboard_branches.js",
    "dashboard_cache.js",
    "dashboard_health.js",
    "dashboard_settings.js",
    "dashboard_stalled.js",
    "dashboard_subtasks.js",
    "dashboard_history.js",
    "dashboard_analytics.js",
    "dashboard_svg.js",
    "dashboard_keyboard.js",
    "dashboard_graph.js",
]


class TestDashboardJsModules(_Base):

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_main_js_referenced(self):
        self.assertIn("dashboard.js", self._html)

    def test_script_type_module(self):
        self.assertIn('type="module"', self._html)


# ---------------------------------------------------------------------------
# 5. Grid layout in served HTML
# ---------------------------------------------------------------------------

class TestDashboardGridLayout(_Base):

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_grid_template_columns_present(self):
        self.assertIn("grid-template-columns", self._html)

    def test_display_grid_present(self):
        self.assertIn("display:grid", self._html)

    def test_grid_before_all_widget_ids(self):
        grid_pos = self._html.index('id="health-widget-grid"')
        for wid in _WIDGET_IDS[3:]:  # skip live-summary and health-detailed (above grid)
            with self.subTest(widget=wid):
                w_pos = self._html.index(f'id="{wid}"')
                self.assertGreater(w_pos, grid_pos)


# ---------------------------------------------------------------------------
# 6. Panel sub-module JS files exist on disk
# ---------------------------------------------------------------------------

class TestPanelSubmodulesExist(unittest.TestCase):
    """Verify all JS sub-modules that dashboard_panels.js re-exports actually exist."""

    _STATIC_DIR = Path(__file__).resolve().parents[1] / "api" / "static"

    def test_all_submodules_exist(self):
        for mod in _PANEL_SUBMODULES:
            with self.subTest(module=mod):
                path = self._STATIC_DIR / mod
                self.assertTrue(path.exists(), f"{mod} missing from api/static/")

    def test_panels_hub_is_small(self):
        """dashboard_panels.js should be a small re-export hub (<100 lines)."""
        panels = self._STATIC_DIR / "dashboard_panels.js"
        lines = panels.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 100, f"dashboard_panels.js is {len(lines)} lines — should be a small hub")


# ---------------------------------------------------------------------------
# 7. dashboard_panels.js re-exports key functions
# ---------------------------------------------------------------------------

class TestPanelsHubReexports(unittest.TestCase):
    """Verify dashboard_panels.js re-exports essential functions."""

    _PANELS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_panels.js"

    def setUp(self):
        self._src = self._PANELS_PATH.read_text(encoding="utf-8")

    def test_reexports_pollBranches(self):
        self.assertIn("pollBranches", self._src)

    def test_reexports_pollCache(self):
        self.assertIn("pollCache", self._src)

    def test_reexports_pollSubtasks(self):
        self.assertIn("pollSubtasks", self._src)

    def test_reexports_pollHistory(self):
        self.assertIn("pollHistory", self._src)

    def test_reexports_pollPriority(self):
        self.assertIn("pollPriority", self._src)

    def test_reexports_pollAgents(self):
        self.assertIn("pollAgents", self._src)

    def test_reexports_pollForecast(self):
        self.assertIn("pollForecast", self._src)

    def test_reexports_pollMetrics(self):
        self.assertIn("pollMetrics", self._src)

    def test_reexports_pollSettings(self):
        self.assertIn("pollSettings", self._src)

    def test_reexports_pollStalled(self):
        self.assertIn("pollStalled", self._src)

    def test_reexports_pollHealthDetailed(self):
        self.assertIn("pollHealthDetailed", self._src)

    def test_contains_switchTab(self):
        self.assertIn("switchTab", self._src)

    def test_reexports_resetHistoryUnread(self):
        self.assertIn("resetHistoryUnread", self._src)

    def test_reexports_historyPageStep(self):
        self.assertIn("historyPageStep", self._src)


# ---------------------------------------------------------------------------
# 8. Analytics sub-module content validation
# ---------------------------------------------------------------------------

class TestAnalyticsModuleContent(unittest.TestCase):
    """Verify dashboard_analytics.js exports required functions."""

    _PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_analytics.js"

    def setUp(self):
        self._src = self._PATH.read_text(encoding="utf-8")

    def test_exports_pollPriority(self):
        self.assertIn("export async function pollPriority", self._src)

    def test_exports_pollAgents(self):
        self.assertIn("export async function pollAgents", self._src)

    def test_exports_pollForecast(self):
        self.assertIn("export async function pollForecast", self._src)

    def test_exports_pollMetrics(self):
        self.assertIn("export async function pollMetrics", self._src)

    def test_imports_svg_helpers(self):
        self.assertIn("svgBar", self._src)
        self.assertIn("sparklineSvg", self._src)


# ---------------------------------------------------------------------------
# 9. Accessibility — ARIA attributes
# ---------------------------------------------------------------------------

class TestDashboardAccessibility(_Base):
    """Verify ARIA attributes and accessibility markup in served HTML."""

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_tablist_role_present(self):
        self.assertIn('role="tablist"', self._html)

    def test_tab_roles_present(self):
        self.assertIn('role="tab"', self._html)

    def test_tabpanel_roles_present(self):
        self.assertIn('role="tabpanel"', self._html)

    def test_aria_selected_on_active_tab(self):
        self.assertIn('aria-selected="true"', self._html)

    def test_aria_controls_on_tabs(self):
        self.assertIn('aria-controls="tab-journal"', self._html)

    def test_dialog_role_on_modals(self):
        # At least one modal should have role="dialog"
        self.assertIn('role="dialog"', self._html)

    def test_aria_modal_on_modals(self):
        self.assertIn('aria-modal="true"', self._html)

    def test_alert_role_on_toast(self):
        self.assertIn('id="toast"', self._html)
        # Toast should have aria-live for screen reader announcements
        toast_pos = self._html.index('id="toast"')
        # Check within 200 chars before the id (in the same element)
        snippet = self._html[max(0, toast_pos - 200):toast_pos + 50]
        self.assertIn('aria-live', snippet)

    def test_stale_banner_has_alert_role(self):
        self.assertIn('id="stale-banner"', self._html)
        banner_pos = self._html.index('id="stale-banner"')
        snippet = self._html[max(0, banner_pos - 200):banner_pos + 50]
        self.assertIn('role="alert"', snippet)

    def test_theme_button_has_aria_label(self):
        self.assertIn('aria-label="Toggle dark/light theme"', self._html)

    def test_notif_button_has_aria_label(self):
        self.assertIn('aria-label="Notification history"', self._html)

    def test_mute_button_present(self):
        self.assertIn('id="btn-mute"', self._html)

    def test_mute_button_has_aria_label(self):
        self.assertIn('aria-label="Mute notification sounds"', self._html)

    def test_all_tabs_have_data_tab(self):
        """All sidebar tab buttons should have data-tab for reliable switchTab matching."""
        import re
        tabs = re.findall(r'<button\s+class="sidebar-tab[^"]*"[^>]*>', self._html)
        self.assertGreater(len(tabs), 0, "No sidebar-tab buttons found")
        for tab in tabs:
            with self.subTest(tab=tab[:60]):
                self.assertIn('data-tab=', tab)


# ---------------------------------------------------------------------------
# 10. Accessibility — aria-label on command toolbar inputs
# ---------------------------------------------------------------------------

class TestCommandToolbarLabels(_Base):
    """Verify all command toolbar inputs and buttons have aria-label."""

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    _INPUT_IDS = [
        "cmd-verify-st", "cmd-verify-note",
        "cmd-desc-st", "cmd-desc-text",
        "cmd-tools-st", "cmd-tools-list",
        "cmd-set-key",
    ]

    def test_all_cmd_inputs_have_aria_label(self):
        for iid in self._INPUT_IDS:
            with self.subTest(input_id=iid):
                pos = self._html.index(f'id="{iid}"')
                # Check the element tag (up to 300 chars around the id)
                snippet = self._html[max(0, pos - 200):pos + 100]
                self.assertIn("aria-label=", snippet)


# ---------------------------------------------------------------------------
# 11. Tiered polling — dashboard.js tick structure
# ---------------------------------------------------------------------------

class TestTieredPollingStructure(unittest.TestCase):
    """Verify dashboard.js uses tiered polling with _tickCount."""

    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def setUp(self):
        self._src = self._JS_PATH.read_text(encoding="utf-8")

    def test_tick_count_variable_exists(self):
        self.assertIn("_tickCount", self._src)

    def test_fast_pollers_comment(self):
        self.assertIn("Fast poller", self._src)

    def test_medium_pollers_modulo_5(self):
        self.assertIn("_tickCount % 5", self._src)

    def test_slow_pollers_modulo_15(self):
        self.assertIn("_tickCount % 15", self._src)

    def test_slow_pollers_include_health(self):
        # Health widgets should be in the slow tier
        self.assertIn("pollHealthDetailed", self._src)

    def test_perf_mode_flag(self):
        self.assertIn("_perfMode", self._src)

    def test_mute_state_init(self):
        self.assertIn("sb-mute", self._src)

    def test_perf_rolling_average(self):
        self.assertIn("_perfHistory", self._src)
        self.assertIn("_PERF_WINDOW", self._src)

    def test_perf_slow_warning(self):
        self.assertIn("SLOW", self._src)

    def test_imports_keyboard_module(self):
        self.assertIn("dashboard_keyboard.js", self._src)


# ---------------------------------------------------------------------------
# 11b. Keyboard shortcuts module
# ---------------------------------------------------------------------------

class TestKeyboardModule(unittest.TestCase):
    """Verify dashboard_keyboard.js contains all keyboard features."""

    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def setUp(self):
        self._src = self._JS_PATH.read_text(encoding="utf-8")

    def test_shortcuts_panel(self):
        self.assertIn("_SHORTCUTS", self._src)
        self.assertIn("shortcuts-overlay", self._src)

    def test_focus_trap_function(self):
        self.assertIn("trapFocus", self._src)

    def test_slash_search_shortcut(self):
        self.assertIn('"/"', self._src)
        self.assertIn("task-search", self._src)

    def test_go_key_combos(self):
        self.assertIn("_pendingG", self._src)
        self.assertIn("_GO_MAP", self._src)

    def test_escape_closes_deps_panel(self):
        self.assertIn("detail-deps-panel", self._src)
        self.assertIn("detail-tl-panel", self._src)

    def test_copy_task_summary(self):
        self.assertIn("_copyTaskSummary", self._src)
        self.assertIn("clipboard", self._src)


# ---------------------------------------------------------------------------
# 12. Subtask dependency graph toggle
# ---------------------------------------------------------------------------

class TestDepsGraphFunction(unittest.TestCase):
    """Verify dashboard_tasks.js contains the deps graph toggle."""

    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def setUp(self):
        self._src = self._JS_PATH.read_text(encoding="utf-8")

    def test_toggle_deps_graph_exists(self):
        self.assertIn("_toggleDepsGraph", self._src)

    def test_deps_panel_class(self):
        self.assertIn("detail-deps-panel", self._src)

    def test_imports_svg_el(self):
        self.assertIn('import { svgEl }', self._src)

    def test_dep_graph_node_click(self):
        self.assertIn("scrollIntoView", self._src)
        self.assertIn("pointer", self._src)


# ---------------------------------------------------------------------------
# 13. Responsive CSS — tablet breakpoint
# ---------------------------------------------------------------------------

class TestResponsiveBreakpoints(unittest.TestCase):
    """Verify dashboard.css has both tablet and mobile breakpoints."""

    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def setUp(self):
        self._src = self._CSS_PATH.read_text(encoding="utf-8")

    def test_mobile_breakpoint(self):
        self.assertIn("max-width: 768px", self._src)

    def test_tablet_breakpoint(self):
        self.assertIn("max-width: 1024px", self._src)

    def test_skeleton_pulse_animation(self):
        self.assertIn("skeleton-pulse", self._src)

    def test_skeleton_card_class(self):
        self.assertIn(".skeleton-card", self._src)


# ---------------------------------------------------------------------------
# 14. Skeleton in served HTML
# ---------------------------------------------------------------------------

class TestDashboardSkeleton(_Base):

    def setUp(self):
        super().setUp()
        self._html = self.client.get("/").data.decode("utf-8", errors="replace")

    def test_skeleton_cards_in_html(self):
        self.assertIn('class="skeleton-card"', self._html)


# ---------------------------------------------------------------------------
# 15. Scroll-to-top on task select
# ---------------------------------------------------------------------------

class TestScrollToTop(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_scroll_top_in_select_task(self):
        src = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("scrollTop = 0", src)


# ---------------------------------------------------------------------------
# 16. Command palette (Ctrl+K)
# ---------------------------------------------------------------------------

class TestCommandPalette(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def setUp(self):
        self._src = self._JS_PATH.read_text(encoding="utf-8")

    def test_palette_function_exists(self):
        self.assertIn("_showPalette", self._src)

    def test_palette_builds_cmds(self):
        self.assertIn("_buildPaletteCmds", self._src)

    def test_palette_fuzzy_filter(self):
        self.assertIn(".includes(", self._src)

    def test_palette_ctrl_k_binding(self):
        self.assertIn('key === "k"', self._src)


# ---------------------------------------------------------------------------
# 17. Sticky detail header
# ---------------------------------------------------------------------------

class TestStickyHeader(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_css_sticky_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-sticky-header", css)
        self.assertIn("position: sticky", css)

    def test_js_creates_sticky_header(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-sticky-header", js)


# ---------------------------------------------------------------------------
# 18. Collapsible branch blocks
# ---------------------------------------------------------------------------

class TestCollapsibleBranches(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_css_collapsed_hides_subtasks(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".collapsed", css)

    def test_js_toggle_collapsed(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("collapsed", js)

    def test_js_collapse_arrow(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("\u25be", js)  # ▾


# ---------------------------------------------------------------------------
# 19. Graph module extraction
# ---------------------------------------------------------------------------

class TestGraphModule(unittest.TestCase):
    _GRAPH_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_graph.js"
    _MAIN_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_graph_module_exists(self):
        self.assertTrue(self._GRAPH_PATH.exists())

    def test_exports_render_graph(self):
        src = self._GRAPH_PATH.read_text(encoding="utf-8")
        self.assertIn("export function renderGraph", src)

    def test_graph_imports_state(self):
        src = self._GRAPH_PATH.read_text(encoding="utf-8")
        self.assertIn('import { state }', src)

    def test_main_imports_graph(self):
        src = self._MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("dashboard_graph.js", src)


# ---------------------------------------------------------------------------
# 20. Diff syntax highlighting
# ---------------------------------------------------------------------------

class TestDiffSyntaxHighlighting(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_journal.js"

    def test_css_diff_add_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".diff-add", css)

    def test_css_diff_del_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".diff-del", css)

    def test_js_assigns_diff_classes(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("diff-add", js)
        self.assertIn("diff-del", js)


# ---------------------------------------------------------------------------
# 21. Branch merge-readiness badge
# ---------------------------------------------------------------------------

class TestBranchMergeReadiness(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_css_readiness_classes(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-readiness", css)
        self.assertIn(".ready", css)
        self.assertIn(".notready", css)

    def test_js_creates_readiness_dot(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-readiness", js)
        self.assertIn("merge ready", js)


# ---------------------------------------------------------------------------
# 22. Export DAG as PNG
# ---------------------------------------------------------------------------

class TestExportDagPng(unittest.TestCase):
    _GRAPH_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_graph.js"

    def test_download_function_exists(self):
        src = self._GRAPH_PATH.read_text(encoding="utf-8")
        self.assertIn("downloadDagPng", src)

    def test_canvas_conversion(self):
        src = self._GRAPH_PATH.read_text(encoding="utf-8")
        self.assertIn("canvas", src)
        self.assertIn("toBlob", src)

    def test_png_download_button_in_html(self):
        html = Path(self._GRAPH_PATH).resolve().parents[1] / "dashboard.html"
        src = html.read_text(encoding="utf-8")
        self.assertIn("btn-dag-download", src)


# ---------------------------------------------------------------------------
# 23. Task card hover tooltip
# ---------------------------------------------------------------------------

class TestTaskCardTooltip(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_card_title_set(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card.title", js)


# ---------------------------------------------------------------------------
# 24. Drag-to-reorder task cards
# ---------------------------------------------------------------------------

class TestDragToReorder(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_css_dragging_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".dragging", css)
        self.assertIn(".drag-over", css)

    def test_js_draggable_attr(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('draggable', js)

    def test_js_reorder_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_reorderTask", js)

    def test_js_localstorage_persist(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-task-order", js)


# ---------------------------------------------------------------------------
# 25. Batch task actions (multi-select)
# ---------------------------------------------------------------------------

class TestBatchTaskActions(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_toggle_card_select(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_toggleCardSelect", js)

    def test_js_batch_reset(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("batchResetSelected", js)

    def test_js_batch_clear(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("batchClearSelection", js)

    def test_js_shift_click(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("shiftKey", js)

    def test_css_multi_selected_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".multi-selected", css)

    def test_batch_bar_in_html(self):
        html = Path(self._JS_PATH).resolve().parents[1] / "dashboard.html"
        src = html.read_text(encoding="utf-8")
        self.assertIn("batch-action-bar", src)


# ---------------------------------------------------------------------------
# 26. Auto theme from OS (prefers-color-scheme)
# ---------------------------------------------------------------------------

class TestAutoThemeFromOS(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_prefers_color_scheme_check(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("prefers-color-scheme", js)

    def test_match_media_call(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("matchMedia", js)

    def test_fallback_to_os_theme(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("osTheme", js)


# ---------------------------------------------------------------------------
# 27. Subtask search highlight
# ---------------------------------------------------------------------------

class TestSubtaskSearchHighlight(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_highlight_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_highlightText", js)

    def test_js_mark_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("<mark>", js)

    def test_css_mark_styling(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("mark", css)


# ---------------------------------------------------------------------------
# 28. Pinned tasks
# ---------------------------------------------------------------------------

class TestPinnedTasks(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_get_pinned(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_getPinnedTasks", js)

    def test_js_set_pinned(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_setPinnedTasks", js)

    def test_js_toggle_pin(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_togglePin", js)

    def test_js_localstorage_key(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-pinned-tasks", js)

    def test_css_pinned_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".pinned", css)

    def test_js_pin_button(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-pin-btn", js)


# ---------------------------------------------------------------------------
# 29. Card percentage label
# ---------------------------------------------------------------------------

class TestCardPercentageLabel(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_pct_label_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-pct-label", js)

    def test_css_pct_label_style(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-pct-label", css)

    def test_js_sets_pct_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("pctLabel.textContent", js)


# ---------------------------------------------------------------------------
# 30. Double-click subtask to quick-verify
# ---------------------------------------------------------------------------

class TestQuickVerifyDblclick(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_quick_verify_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_quickVerify", js)

    def test_js_dblclick_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("dblclick", js)

    def test_js_verify_post(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Quick verify (dblclick)", js)

    def test_js_checkbox_guard(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-checkbox", js)


# ---------------------------------------------------------------------------
# 31. Tab count badges (stalled/history)
# ---------------------------------------------------------------------------

class TestTabCountBadges(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    _MAIN_JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_update_tab_badges_export(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("export function updateTabBadges", js)

    def test_js_set_badge_helper(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_setBadge", js)

    def test_css_badge_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".tab-count-badge", css)

    def test_main_js_imports_badges(self):
        js = self._MAIN_JS.read_text(encoding="utf-8")
        self.assertIn("updateTabBadges", js)


# ---------------------------------------------------------------------------
# 32. Compact mode toggle
# ---------------------------------------------------------------------------

class TestCompactModeToggle(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_toggle_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("toggleCompactMode", js)

    def test_js_localstorage_key(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-compact", js)

    def test_css_compact_mode_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".compact-mode", css)

    def test_html_compact_button(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("btn-compact", html)

    def test_js_body_class_toggle(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("compact-mode", js)


# ---------------------------------------------------------------------------
# 33. Task card sparkline
# ---------------------------------------------------------------------------

class TestTaskCardSparkline(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_sparkline_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-sparkline", js)

    def test_js_spark_bar_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("spark-bar", js)

    def test_css_sparkline_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-sparkline", css)

    def test_css_spark_bar_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".spark-bar", css)


# ---------------------------------------------------------------------------
# 34. Bulk verify in detail panel
# ---------------------------------------------------------------------------

class TestBulkVerifyDetailPanel(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_detail_bulk_verify(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detailBulkVerify", js)

    def test_js_detail_bulk_clear(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detailBulkClear", js)

    def test_js_update_detail_bulk_bar(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_updateDetailBulkBar", js)

    def test_html_detail_bulk_bar(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-bulk-bar", html)

    def test_js_bulk_verify_post(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Bulk verify", js)


# ---------------------------------------------------------------------------
# 35. Poll countdown timer
# ---------------------------------------------------------------------------

class TestPollCountdownTimer(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_countdown_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_startCountdown", js)

    def test_js_countdown_interval(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_countdownLeft", js)

    def test_html_countdown_element(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("poll-countdown", html)

    def test_css_countdown_style(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("#poll-countdown", css)


# ---------------------------------------------------------------------------
# 36. Task card last-active relative time
# ---------------------------------------------------------------------------

class TestCardRelativeTime(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_relative_time_helper(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_relativeTime", js)

    def test_js_card_ago_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-ago", js)

    def test_css_card_ago_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-ago", css)

    def test_js_time_units(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("s ago", js)
        self.assertIn("m ago", js)
        self.assertIn("h ago", js)


# ---------------------------------------------------------------------------
# 37. Subtask output word count badge
# ---------------------------------------------------------------------------

class TestSubtaskWordCountBadge(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_wc_badge_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-wc-badge", js)

    def test_js_word_count_calc(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("split(/\\s+/)", js)

    def test_css_wc_badge_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-wc-badge", css)


# ---------------------------------------------------------------------------
# 38. Sticky batch action bar
# ---------------------------------------------------------------------------

class TestStickyBatchBar(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_css_sticky_batch_bar(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("#batch-action-bar", css)
        self.assertIn("sticky", css)


# ---------------------------------------------------------------------------
# 39. Detail panel copy-task-id
# ---------------------------------------------------------------------------

class TestCopyTaskId(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_clipboard_write(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard.writeText", js)

    def test_js_copy_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Copied:", js)

    def test_css_hover_underline(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-task-id:hover", css)

    def test_js_cursor_pointer(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Click to copy task ID", js)


# ---------------------------------------------------------------------------
# 40. Task card status emoji
# ---------------------------------------------------------------------------

class TestTaskCardStatusEmoji(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_status_emoji_map(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_STATUS_EMOJI", js)

    def test_js_status_emoji_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_statusEmoji", js)

    def test_js_verified_symbol(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"Verified"', js)


# ---------------------------------------------------------------------------
# 41. Search match count
# ---------------------------------------------------------------------------

class TestSearchMatchCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_match_count_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("search-match-count", js)

    def test_html_match_count_span(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("search-match-count", html)

    def test_js_result_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("result", js)

    def test_css_match_count_style(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("#search-match-count", css)


# ---------------------------------------------------------------------------
# 42. Auto-collapse verified branches
# ---------------------------------------------------------------------------

class TestAutoCollapseVerifiedBranches(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_auto_collapse_logic(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Auto-collapse verified branches", js)

    def test_js_collapsed_class_added(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        # Verify the collapsed class is added programmatically
        self.assertIn('branchBlock.classList.add("collapsed")', js)

    def test_js_arrow_set_to_collapsed(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        # Collapsed arrow symbol
        self.assertIn('"▸"', js)


# ---------------------------------------------------------------------------
# 43. Subtask status sort toggle
# ---------------------------------------------------------------------------

class TestSubtaskStatusSort(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_sort_button(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Sort", js)

    def test_js_sort_by_status(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Sorted subtasks by status", js)

    def test_js_sort_order(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Pending", js)


# ---------------------------------------------------------------------------
# 44. Header progress bar tooltip
# ---------------------------------------------------------------------------

class TestHeaderProgressTooltip(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_bar_title_set(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('hdr-bar").title', js)

    def test_js_tooltip_breakdown(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Verified:", js)
        self.assertIn("Running:", js)
        self.assertIn("Pending:", js)


# ---------------------------------------------------------------------------
# 45. Task card running subtask name
# ---------------------------------------------------------------------------

class TestCardRunningSubtaskName(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_find_first_running(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_findFirstRunning", js)

    def test_js_card_running_name_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-running-name", js)

    def test_css_running_name_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-running-name", css)


# ---------------------------------------------------------------------------
# 46. Keyboard shortcut `c` to copy task ID
# ---------------------------------------------------------------------------

class TestKeyboardCopyTaskId(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_c_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"c"', js)

    def test_js_clipboard_write(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard.writeText", js)


# ---------------------------------------------------------------------------
# 47. Subtask row hover highlight
# ---------------------------------------------------------------------------

class TestSubtaskRowHover(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_css_hover_rule(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".subtask-row:hover", css)

    def test_css_hover_background(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        # Verify hover sets a background
        idx = css.index(".subtask-row:hover")
        snippet = css[idx:idx+80]
        self.assertIn("background", snippet)


# ---------------------------------------------------------------------------
# 48. Branch completion percentage
# ---------------------------------------------------------------------------

class TestBranchCompletionPercentage(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_branch_pct_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-pct", js)

    def test_js_branch_pct_calc(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branchPctSpan", js)

    def test_css_branch_pct_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-pct", css)


# ---------------------------------------------------------------------------
# 49. Detail panel verified counter (green text summary)
# ---------------------------------------------------------------------------

class TestDetailVerifiedCounter(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_detail_prog_pct(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-prog-pct", js)

    def test_js_verified_total_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        # Format: verified/total (pct%)
        self.assertIn("_verified}/${_total}", js)


# ---------------------------------------------------------------------------
# 50. Task card context menu
# ---------------------------------------------------------------------------

class TestCardContextMenu(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_context_menu_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_showCardContextMenu", js)

    def test_js_contextmenu_event(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("contextmenu", js)

    def test_css_ctx_menu_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-ctx-menu", css)

    def test_css_ctx_menu_item(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".ctx-menu-item", css)


# ---------------------------------------------------------------------------
# 51. Header clock
# ---------------------------------------------------------------------------

class TestHeaderClock(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_update_clock_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_updateClock", js)

    def test_html_clock_element(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("hdr-clock", html)

    def test_js_locale_time_string(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("toLocaleTimeString", js)


# ---------------------------------------------------------------------------
# 52. Expand / collapse all branches
# ---------------------------------------------------------------------------

class TestExpandCollapseAllBranches(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_expand_all(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("expandAllBranches", js)

    def test_js_collapse_all(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("collapseAllBranches", js)

    def test_js_expand_button_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("All", js)


# ---------------------------------------------------------------------------
# 53. Branch filter dropdown
# ---------------------------------------------------------------------------

class TestBranchFilterDropdown(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_filter_branch_function(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("filterBranch", js)

    def test_js_branch_filter_select(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-filter-select", js)

    def test_js_all_branches_option(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("All branches", js)


# ---------------------------------------------------------------------------
# 54. Subtask output preview tooltip
# ---------------------------------------------------------------------------

class TestSubtaskOutputPreview(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_output_title_attr(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("outSpan.title", js)

    def test_js_output_truncated(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("substring(0, 400)", js)


# ---------------------------------------------------------------------------
# 55. Task card star (favorite)
# ---------------------------------------------------------------------------

class TestTaskCardStar(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_starred_persistence(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-starred-tasks", js)

    def test_js_toggle_star(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_toggleStar", js)

    def test_js_star_button(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-star-btn", js)

    def test_css_star_btn_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-star-btn", css)


# ---------------------------------------------------------------------------
# 56. Subtask row elapsed time
# ---------------------------------------------------------------------------

class TestSubtaskRowElapsedTime(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_elapsed_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-elapsed", js)

    def test_js_uses_relative_time(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_relativeTime(s.last_update_time)", js)

    def test_css_elapsed_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-elapsed", css)


# ---------------------------------------------------------------------------
# 57. Detail panel task notes
# ---------------------------------------------------------------------------

class TestDetailPanelTaskNotes(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_get_task_note(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_getTaskNote", js)

    def test_js_set_task_note(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_setTaskNote", js)

    def test_js_notes_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-notes", js)

    def test_css_notes_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-notes", css)

    def test_js_localstorage_key(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-task-notes", js)


# ---------------------------------------------------------------------------
# 58. Header verified/total fraction
# ---------------------------------------------------------------------------

class TestHeaderFraction(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_fraction_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("hdr-fraction", js)

    def test_html_fraction_span(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("hdr-fraction", html)


# ---------------------------------------------------------------------------
# 59. Keyboard `n` jump to next unverified
# ---------------------------------------------------------------------------

class TestKeyboardNextUnverified(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_n_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"n"', js)

    def test_js_jump_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Jumped to", js)

    def test_js_all_verified_message(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("All tasks fully verified", js)


# ---------------------------------------------------------------------------
# 60. Subtask row status transition arrow
# ---------------------------------------------------------------------------

class TestSubtaskStatusTransition(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_transition_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-transition", js)

    def test_js_prev_status_check(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_prevStatuses", js)

    def test_css_transition_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-transition", css)


# ---------------------------------------------------------------------------
# 61. Task card total subtask count
# ---------------------------------------------------------------------------

class TestCardSubtaskCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_st_count_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-st-count", js)

    def test_js_subtask_label(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("subtask", js)

    def test_css_st_count_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-st-count", css)


# ---------------------------------------------------------------------------
# 62. Detail panel scroll-to-running
# ---------------------------------------------------------------------------

class TestScrollToRunning(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_scroll_run_button(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Running", js)

    def test_js_scroll_to_running(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Scroll to first running subtask", js)

    def test_js_dot_cyan_selector(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("dot-cyan", js)


# ---------------------------------------------------------------------------
# 63. Header ETA estimate
# ---------------------------------------------------------------------------

class TestHeaderETA(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_eta_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("hdr-eta", js)

    def test_html_eta_span(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("hdr-eta", html)

    def test_js_eta_calculation(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("stepsLeft", js)


# ---------------------------------------------------------------------------
# 64. Keyboard `x` expand/collapse branches
# ---------------------------------------------------------------------------

class TestKeyboardExpandCollapse(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_x_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"x"', js)

    def test_js_calls_expand_all(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("expandAllBranches", js)

    def test_js_calls_collapse_all(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("collapseAllBranches", js)


# ---------------------------------------------------------------------------
# 65. Task card progress ring
# ---------------------------------------------------------------------------

class TestCardProgressRing(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_progress_ring_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-progress-ring", js)

    def test_js_ring_fg_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("ring-fg", js)

    def test_js_stroke_dashoffset(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("stroke-dashoffset", js)

    def test_css_ring_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-progress-ring", css)


# ---------------------------------------------------------------------------
# 66. Subtask row inline verify button
# ---------------------------------------------------------------------------

class TestInlineVerifyButton(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_inline_verify_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-inline-verify", js)

    def test_js_calls_quick_verify(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_quickVerify", js)

    def test_css_inline_verify_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-inline-verify", css)

    def test_css_hover_style(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-inline-verify:hover", css)


# ---------------------------------------------------------------------------
# 67. Detail panel branch stats summary
# ---------------------------------------------------------------------------

class TestBranchStatsSummary(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_branch_summary_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-stats-summary", js)

    def test_js_complete_branches_count(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branches complete", js)

    def test_css_summary_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-stats-summary", css)


# ---------------------------------------------------------------------------
# 68. Header step delta
# ---------------------------------------------------------------------------

class TestHeaderStepDelta(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_initial_step_tracking(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_initialStep", js)

    def test_js_delta_display(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("deltaStr", js)


# ---------------------------------------------------------------------------
# 69. Keyboard `f` focus search
# ---------------------------------------------------------------------------

class TestKeyboardFocusSearch(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_f_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"f"', js)

    def test_js_focus_and_select(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("ts.focus()", js)
        self.assertIn("ts.select()", js)


# ---------------------------------------------------------------------------
# 70. Task card segmented status bar
# ---------------------------------------------------------------------------

class TestCardSegmentedStatusBar(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_seg_bar_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-seg-bar", js)

    def test_js_seg_segments(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("seg-v", js)
        self.assertIn("seg-r", js)

    def test_css_seg_bar_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-seg-bar", css)

    def test_css_seg_colors(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".seg-v", css)
        self.assertIn(".seg-r", css)
        self.assertIn(".seg-rv", css)


# ---------------------------------------------------------------------------
# 71. Subtask description preview
# ---------------------------------------------------------------------------

class TestSubtaskDescriptionPreview(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_desc_preview_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-desc-preview", js)

    def test_js_desc_truncation(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("substring(0, 60)", js)

    def test_css_desc_preview_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-desc-preview", css)


# ---------------------------------------------------------------------------
# 72. Detail panel task deps chips
# ---------------------------------------------------------------------------

class TestDetailTaskDepsChips(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_task_dep_chip(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("task-dep-chip", js)

    def test_js_chip_click_selects(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("selectTask(dep)", js)

    def test_css_chip_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".task-dep-chip", css)

    def test_css_chip_hover(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".task-dep-chip:hover", css)


# ---------------------------------------------------------------------------
# 73. Header active tasks count
# ---------------------------------------------------------------------------

class TestHeaderActiveTasksCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_active_tasks_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("hdr-active-tasks", js)

    def test_html_active_tasks_span(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("hdr-active-tasks", html)

    def test_js_active_filter(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("active", js)


# ---------------------------------------------------------------------------
# 74. Keyboard `d` toggle detail panel
# ---------------------------------------------------------------------------

class TestKeyboardToggleDetail(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_d_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"d"', js)

    def test_js_detail_panel_toggle(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-panel", js)


# ---------------------------------------------------------------------------
# 75. Card verified pulse animation
# ---------------------------------------------------------------------------

class TestCardVerifiedPulse(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_pulse_class_added(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-pulse", js)

    def test_js_prev_verified_tracking(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_prevVerified", js)

    def test_js_reflow_trick(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("offsetWidth", js)

    def test_css_pulse_animation(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-pulse", css)

    def test_css_keyframes(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-pulse-anim", css)


# ---------------------------------------------------------------------------
# 76. Output show more/less toggle
# ---------------------------------------------------------------------------

class TestOutputShowMoreToggle(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_show_more_button(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-show-more", js)

    def test_js_expanded_flag(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_expanded", js)

    def test_js_more_less_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"more"', js)
        self.assertIn('"less"', js)

    def test_css_show_more_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-show-more", css)


# ---------------------------------------------------------------------------
# 77. Card last verified subtask indicator
# ---------------------------------------------------------------------------

class TestCardLastVerified(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_find_last_verified(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_findLastVerified", js)

    def test_js_last_verified_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-last-verified", js)

    def test_js_last_verified_title(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Last verified:", js)

    def test_css_last_verified_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-last-verified", css)


# ---------------------------------------------------------------------------
# 78. Branch subtask count in detail header
# ---------------------------------------------------------------------------

class TestBranchSubtaskCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_branch_count_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-st-count", js)

    def test_js_branch_count_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branchCountSpan", js)

    def test_css_branch_count_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-st-count", css)


# ---------------------------------------------------------------------------
# 79. Keyboard `m` mute toggle
# ---------------------------------------------------------------------------

class TestKeyboardMuteToggle(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_m_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"m"', js)

    def test_js_mute_localStorage(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-mute", js)

    def test_js_mute_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Sound muted", js)

    def test_js_unmute_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Sound unmuted", js)


# ---------------------------------------------------------------------------
# 80. Subtask output copy button
# ---------------------------------------------------------------------------

class TestSubtaskOutputCopyButton(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_copy_btn_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-copy-btn", js)

    def test_js_copy_output_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Copied output", js)

    def test_js_clipboard_write(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard.writeText(rawOutput)", js)

    def test_css_copy_btn_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-copy-btn", css)


# ---------------------------------------------------------------------------
# 81. Detail panel status filter pills
# ---------------------------------------------------------------------------

class TestDetailStatusFilterPills(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_filter_pills_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-filter-pills", js)

    def test_js_filter_pill_click(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-filter-pill", js)

    def test_js_pill_active_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"active"', js)

    def test_css_filter_pills_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-filter-pills", css)

    def test_css_pill_active_style(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-filter-pill.active", css)


# ---------------------------------------------------------------------------
# 82. Card goal text
# ---------------------------------------------------------------------------

class TestCardGoalText(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_card_goal_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-goal", js)

    def test_js_goal_truncation(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("t.goal.substring(0, 60)", js)

    def test_css_card_goal_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-goal", css)


# ---------------------------------------------------------------------------
# 83. Keyboard `a` select all
# ---------------------------------------------------------------------------

class TestKeyboardSelectAll(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_a_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"a"', js)

    def test_js_select_all_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Selected", js)

    def test_js_multi_selected_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("multi-selected", js)


# ---------------------------------------------------------------------------
# 84. Card completion celebration flash
# ---------------------------------------------------------------------------

class TestCardCompletionFlash(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_complete_flash_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-complete-flash", js)

    def test_js_was_complete_tracking(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_wasComplete", js)

    def test_css_flash_animation(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-complete-flash", css)

    def test_css_flash_keyframes(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-complete-flash-anim", css)


# ---------------------------------------------------------------------------
# 85. Subtask row step number
# ---------------------------------------------------------------------------

class TestSubtaskStepNumber(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_step_num_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-step-num", js)

    def test_js_step_prefix(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("`s${s.last_update}`", js)

    def test_css_step_num_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-step-num", css)


# ---------------------------------------------------------------------------
# 86. Card branch count badge
# ---------------------------------------------------------------------------

class TestCardBranchCountBadge(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_branch_count_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-branch-count", js)

    def test_js_branch_label(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch", js)

    def test_css_branch_count_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-branch-count", css)


# ---------------------------------------------------------------------------
# 87. Detail panel markdown export
# ---------------------------------------------------------------------------

class TestDetailMarkdownExport(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_md_export_button(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("MD", js)

    def test_js_markdown_format(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Copied detail as Markdown", js)

    def test_js_checklist_format(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("- [", js)


# ---------------------------------------------------------------------------
# 88. Keyboard `v` verify first unverified
# ---------------------------------------------------------------------------

class TestKeyboardVerifyFirst(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_v_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"v"', js)

    def test_js_quick_verify_call(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_quickVerify", js)

    def test_js_all_verified_message(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("All subtasks already verified", js)


# ---------------------------------------------------------------------------
# 89. Running dot pulse animation
# ---------------------------------------------------------------------------

class TestRunningDotPulse(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_css_dot_pulse_keyframes(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("dot-pulse-anim", css)

    def test_css_dot_cyan_animation(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-dot.dot-cyan", css)

    def test_css_pulse_opacity(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        idx = css.index("dot-pulse-anim")
        snippet = css[idx:idx+120]
        self.assertIn("opacity", snippet)


# ---------------------------------------------------------------------------
# 90. Card blocked overlay
# ---------------------------------------------------------------------------

class TestCardBlockedOverlay(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_blocked_overlay_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-blocked-overlay", js)

    def test_js_blocked_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Blocked", js)

    def test_css_overlay_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-blocked-overlay", css)


# ---------------------------------------------------------------------------
# 91. Subtask search count
# ---------------------------------------------------------------------------

class TestSubtaskSearchCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_search_count_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-search-count", js)

    def test_js_match_total_format(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("matchCount", js)

    def test_html_search_count_span(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("st-search-count", html)


# ---------------------------------------------------------------------------
# 92. Keyboard `w` compact toggle
# ---------------------------------------------------------------------------

class TestKeyboardCompactToggle(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_w_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"w"', js)

    def test_js_calls_toggle_compact(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("toggleCompactMode", js)


# ---------------------------------------------------------------------------
# 93. Card percentage color
# ---------------------------------------------------------------------------

class TestCardPercentageColor(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_pct_classes(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("pct-high", js)
        self.assertIn("pct-mid", js)
        self.assertIn("pct-low", js)

    def test_css_pct_high(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".pct-high", css)

    def test_css_pct_mid(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".pct-mid", css)

    def test_css_pct_low(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".pct-low", css)


# ---------------------------------------------------------------------------
# 94. Subtask dot status tooltip
# ---------------------------------------------------------------------------

class TestSubtaskDotTooltip(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_dot_title_set(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("dot.title", js)

    def test_js_step_info_in_tooltip(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("step ${s.last_update}", js)

    def test_css_dot_cursor(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-dot[title]", css)


# ---------------------------------------------------------------------------
# 95. Card sort dropdown
# ---------------------------------------------------------------------------

class TestCardSortDropdown(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"

    def test_js_set_task_sort(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_setTaskSort", js)

    def test_js_sort_modes(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_tasksSortMode", js)

    def test_js_sort_localstorage(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-task-sort", js)

    def test_html_sort_select(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("task-sort-sel", html)


# ---------------------------------------------------------------------------
# 96. Detail panel status count summary
# ---------------------------------------------------------------------------

class TestDetailStatusSummary(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_summary_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-status-summary", js)

    def test_js_summary_parts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("verified", js)
        self.assertIn("running", js)
        self.assertIn("pending", js)

    def test_css_summary_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-status-summary", css)


# ---------------------------------------------------------------------------
# 97. Shortcuts overlay updated keys
# ---------------------------------------------------------------------------

class TestShortcutsOverlayKeys(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_new_shortcut_entries(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Toggle mute", js)
        self.assertIn("Toggle compact mode", js)
        self.assertIn("Verify first unverified", js)
        self.assertIn("Select all task cards", js)


# ---------------------------------------------------------------------------
# 98. Card hover scale
# ---------------------------------------------------------------------------

class TestCardHoverScale(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_css_hover_scale(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("scale(1.02)", css)

    def test_css_hover_transition(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".task-card:hover", css)


# ---------------------------------------------------------------------------
# 99. Subtask row alternate striping
# ---------------------------------------------------------------------------

class TestSubtaskRowStriping(unittest.TestCase):
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_css_even_row(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".subtask-row:nth-child(even)", css)

    def test_css_odd_row(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".subtask-row:nth-child(odd)", css)


# ---------------------------------------------------------------------------
# 100. Card pending subtask count
# ---------------------------------------------------------------------------

class TestCardPendingCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_pending_count_calc(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_pendingSt", js)

    def test_js_pending_symbol(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("◯", js)


# ---------------------------------------------------------------------------
# 101. Detail panel scroll progress
# ---------------------------------------------------------------------------

class TestDetailScrollProgress(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_scroll_progress_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-scroll-progress", js)

    def test_js_scroll_listener(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_scrollListenerAdded", js)

    def test_css_scroll_bar_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-scroll-progress", css)


# ---------------------------------------------------------------------------
# 102. Escape clears subtask search
# ---------------------------------------------------------------------------

class TestEscapeClearsSubtaskSearch(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_st_search_clear(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-search", js)

    def test_js_filter_subtasks_called(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("filterSubtasks", js)


# ---------------------------------------------------------------------------
# 103. Subtask output line count
# ---------------------------------------------------------------------------

class TestSubtaskOutputLineCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_line_count_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-line-count", js)

    def test_js_line_split(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('split("\\n")', js)

    def test_css_line_count_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-line-count", css)


# ---------------------------------------------------------------------------
# 104. Card recently active highlight
# ---------------------------------------------------------------------------

class TestCardRecentlyActive(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_recently_active_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-recently-active", js)

    def test_js_60s_threshold(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("< 60", js)

    def test_css_recently_active_border(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-recently-active", css)


# ---------------------------------------------------------------------------
# 105. Card progress bar tooltip
# ---------------------------------------------------------------------------

class TestCardProgressBarTooltip(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_bar_parent_title(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("barFg.parentElement.title", js)

    def test_js_ratio_in_tooltip(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("verified (${pct}%)", js)


# ---------------------------------------------------------------------------
# 106. Card stalled warning badge
# ---------------------------------------------------------------------------

class TestCardStalledBadge(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_stalled_badge_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-stalled-badge", js)

    def test_js_stalled_subtasks_check(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("stalled_subtasks", js)

    def test_css_stalled_badge_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-stalled-badge", css)


# ---------------------------------------------------------------------------
# 107. Subtask row status label
# ---------------------------------------------------------------------------

class TestSubtaskStatusLabel(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_status_label_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-status-label", js)

    def test_js_status_text(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("statusLabel.textContent", js)

    def test_css_status_label_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-status-label", css)

    def test_css_compact_hides_label(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".compact-mode .st-status-label", css)


# ---------------------------------------------------------------------------
# 108. Detail auto-refresh indicator
# ---------------------------------------------------------------------------

class TestDetailRefreshIndicator(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _HTML_PATH = Path(__file__).resolve().parents[1] / "api" / "dashboard.html"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_refresh_dot_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-refresh-dot", js)

    def test_js_spinning_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("spinning", js)

    def test_html_refresh_dot(self):
        html = self._HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-refresh-dot", html)

    def test_css_refresh_dot_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-refresh-dot", css)

    def test_css_spinning_animation(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-refresh-dot.spinning", css)


# ---------------------------------------------------------------------------
# 109. Keyboard `i` task info toast
# ---------------------------------------------------------------------------

class TestKeyboardTaskInfo(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.js"

    def test_js_i_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"i"', js)

    def test_js_info_toast_content(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("verified,", js)
        self.assertIn("running,", js)
        self.assertIn("branches", js)


# ---------------------------------------------------------------------------
# 110. Subtask retry button
# ---------------------------------------------------------------------------

class TestSubtaskRetryButton(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_retry_btn_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-retry-btn", js)

    def test_js_retry_heal_endpoint(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"/heal"', js)

    def test_js_retry_only_running(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('s.status === "Running"', js)

    def test_css_retry_btn_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-retry-btn", css)


# ---------------------------------------------------------------------------
# 111. Card drag handle icon
# ---------------------------------------------------------------------------

class TestCardDragHandle(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_drag_handle_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-drag-handle", js)

    def test_js_drag_handle_icon(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("⠿", js)

    def test_css_drag_handle_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-drag-handle", css)

    def test_css_drag_handle_hover(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".task-card:hover .card-drag-handle", css)


# ---------------------------------------------------------------------------
# 112. Branch last-active timestamp
# ---------------------------------------------------------------------------

class TestBranchLastActive(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_branch_last_active_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-last-active", js)

    def test_js_branch_times_computed(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_branchTimes", js)

    def test_css_branch_last_active_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-last-active", css)


# ---------------------------------------------------------------------------
# 113. Detail panel breadcrumb
# ---------------------------------------------------------------------------

class TestDetailBreadcrumb(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_breadcrumb_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-breadcrumb", js)

    def test_js_breadcrumb_tasks_link(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-bc-link", js)

    def test_js_breadcrumb_separator(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("›", js)

    def test_css_breadcrumb_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-breadcrumb", css)

    def test_css_bc_link_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-bc-link", css)


# ---------------------------------------------------------------------------
# 114. Keyboard `r` force refresh
# ---------------------------------------------------------------------------

class TestKeyboardForceRefresh(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_r_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"r"', js)

    def test_js_tick_call(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("window.tick", js)

    def test_js_refresh_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Refreshing", js)


# ---------------------------------------------------------------------------
# 115. Card failure count badge
# ---------------------------------------------------------------------------

class TestCardFailCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_fail_count_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-fail-count", js)

    def test_js_fail_regex(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("error|fail|exception", js)

    def test_css_fail_count_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-fail-count", css)


# ---------------------------------------------------------------------------
# 116. Subtask output change indicator
# ---------------------------------------------------------------------------

class TestSubtaskOutputChange(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_output_changed_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-output-changed", js)

    def test_js_prev_outputs_tracking(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_prevSubtaskOutputs", js)

    def test_js_change_badge_symbol(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("△", js)

    def test_css_output_changed_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-output-changed", css)


# ---------------------------------------------------------------------------
# 117. Branch progress mini-ring
# ---------------------------------------------------------------------------

class TestBranchMiniRing(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_mini_ring_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-mini-ring", js)

    def test_js_mini_ring_svg(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("createElementNS", js)

    def test_css_mini_ring_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-mini-ring", css)


# ---------------------------------------------------------------------------
# 118. Detail panel JSON export
# ---------------------------------------------------------------------------

class TestDetailJsonExport(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_json_export_btn(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("jsonExportBtn", js)

    def test_js_json_stringify(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("JSON.stringify(t, null, 2)", js)

    def test_js_json_download(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn(".json", js)

    def test_js_blob_creation(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("application/json", js)


# ---------------------------------------------------------------------------
# 119. Keyboard `l` journal tab
# ---------------------------------------------------------------------------

class TestKeyboardJournalTab(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_l_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"l"', js)

    def test_js_journal_switch(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("journal", js)

    def test_js_l_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Journal tab", js)


# ---------------------------------------------------------------------------
# 120. Subtask duration timer
# ---------------------------------------------------------------------------

class TestSubtaskDurationTimer(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_duration_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-duration", js)

    def test_js_started_at(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("started_at", js)

    def test_js_elapsed_calc(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_elapsed", js)

    def test_css_duration_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-duration", css)


# ---------------------------------------------------------------------------
# 121. Card group-by-status headers
# ---------------------------------------------------------------------------

class TestCardGroupHeaders(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_group_header_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("task-grp-hdr", js)

    def test_js_group_status_sort(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_lastGroup", js)

    def test_css_group_header_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".task-grp-hdr", css)


# ---------------------------------------------------------------------------
# 122. Branch diff count
# ---------------------------------------------------------------------------

class TestBranchDiffCount(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_diff_count_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-diff-count", js)

    def test_js_branch_changed(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_branchChanged", js)

    def test_css_diff_count_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-diff-count", css)


# ---------------------------------------------------------------------------
# 123. Detail panel inline search
# ---------------------------------------------------------------------------

class TestDetailInlineSearch(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_inline_search_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-inline-search", js)

    def test_js_search_placeholder(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Search subtasks", js)

    def test_js_search_filters_rows(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detailSearch.value", js)

    def test_css_inline_search_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-inline-search", css)

    def test_css_search_focus(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-inline-search:focus", css)


# ---------------------------------------------------------------------------
# 124. Keyboard `o` open output modal
# ---------------------------------------------------------------------------

class TestKeyboardOpenOutput(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_o_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"o"', js)

    def test_js_row_click(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("row.click", js)

    def test_js_o_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Open output modal", js)


# ---------------------------------------------------------------------------
# 125. Subtask priority indicator
# ---------------------------------------------------------------------------

class TestSubtaskPriority(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_priority_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-priority", js)

    def test_js_action_type_check(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("full_execution", js)

    def test_js_pri_high_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("pri-high", js)

    def test_css_priority_classes(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-priority", css)
        self.assertIn(".st-priority.pri-high", css)
        self.assertIn(".st-priority.pri-med", css)
        self.assertIn(".st-priority.pri-low", css)


# ---------------------------------------------------------------------------
# 126. Card ETA countdown
# ---------------------------------------------------------------------------

class TestCardETA(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_eta_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-eta", js)

    def test_js_verify_rate(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("verify_rate", js)

    def test_js_eta_steps(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("etaSteps", js)

    def test_css_eta_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-eta", css)


# ---------------------------------------------------------------------------
# 127. Branch collapse memory
# ---------------------------------------------------------------------------

class TestBranchCollapseMemory(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_collapse_key(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_collapseKey", js)

    def test_js_localStorage_set(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("localStorage.setItem(_collapseKey", js)

    def test_js_localStorage_get(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("localStorage.getItem(_collapseKey)", js)


# ---------------------------------------------------------------------------
# 128. Detail panel auto-scroll to changed
# ---------------------------------------------------------------------------

class TestAutoScrollToChanged(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_changed_st_variable(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_changedSt", js)

    def test_js_scroll_into_view(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("scrollIntoView", js)

    def test_js_cyan_outline(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("var(--cyan)", js)


# ---------------------------------------------------------------------------
# 129. Keyboard `e` export clipboard
# ---------------------------------------------------------------------------

class TestKeyboardExport(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_e_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"e"', js)

    def test_js_copy_task_summary(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_copyTaskSummary", js)

    def test_js_e_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Export selected task", js)


# ---------------------------------------------------------------------------
# 130. Subtask output word cloud
# ---------------------------------------------------------------------------

class TestSubtaskWordCloud(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_word_cloud_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-word-cloud", js)

    def test_js_word_tag_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-word-tag", js)

    def test_js_freq_computation(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_freq", js)

    def test_css_word_cloud_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-word-cloud", css)


# ---------------------------------------------------------------------------
# 131. Card verified streak
# ---------------------------------------------------------------------------

class TestCardVerifiedStreak(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_streak_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-streak", js)

    def test_js_streak_icon(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("🔥", js)

    def test_css_streak_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-streak", css)


# ---------------------------------------------------------------------------
# 132. Branch health dot
# ---------------------------------------------------------------------------

class TestBranchHealthDot(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_health_dot_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-health-dot", js)

    def test_js_health_ok(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("health-ok", js)

    def test_js_health_warn(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("health-warn", js)

    def test_css_health_dot_ok(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-health-dot.health-ok", css)

    def test_css_health_dot_warn(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-health-dot.health-warn", css)


# ---------------------------------------------------------------------------
# 133. Detail panel tab memory
# ---------------------------------------------------------------------------

class TestDetailFilterMemory(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_detail_filter_key(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-detail-filter", js)

    def test_js_saved_filter_restore(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_savedFilter", js)


# ---------------------------------------------------------------------------
# 134. Keyboard `z` undo verify
# ---------------------------------------------------------------------------

class TestKeyboardUndoVerify(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    _TASKS_JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_z_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"z"', js)

    def test_js_undo_toast(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Undid verify", js)

    def test_js_last_verified_stored(self):
        js = self._TASKS_JS.read_text(encoding="utf-8")
        self.assertIn("_lastVerifiedSubtask", js)

    def test_js_z_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Undo last verify", js)


# ---------------------------------------------------------------------------
# 135. Subtask output syntax highlight
# ---------------------------------------------------------------------------

class TestOutputSyntaxHighlight(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_out_err_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("out-err", js)

    def test_js_out_ok_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("out-ok", js)

    def test_js_out_warn_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("out-warn", js)

    def test_css_highlight_classes(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".out-err", css)
        self.assertIn(".out-ok", css)
        self.assertIn(".out-warn", css)


# ---------------------------------------------------------------------------
# 136. Card mini heatmap
# ---------------------------------------------------------------------------

class TestCardMiniHeatmap(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_heatmap_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-heatmap", js)

    def test_js_hm_cell_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("hm-cell", js)

    def test_css_heatmap_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-heatmap", css)
        self.assertIn(".hm-v", css)


# ---------------------------------------------------------------------------
# 137. Branch elapsed time
# ---------------------------------------------------------------------------

class TestBranchElapsedTime(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_elapsed_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-elapsed", js)

    def test_js_running_times(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_runningTimes", js)

    def test_css_elapsed_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-elapsed", css)


# ---------------------------------------------------------------------------
# 138. Detail panel zoom level
# ---------------------------------------------------------------------------

class TestDetailZoom(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_zoom_wrap_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-zoom-wrap", js)

    def test_js_zoom_localStorage(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("sb-detail-zoom", js)

    def test_js_zoom_btn(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-zoom-btn", js)

    def test_css_zoom_wrap(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-zoom-wrap", css)


# ---------------------------------------------------------------------------
# 139. Keyboard `q` quick filter
# ---------------------------------------------------------------------------

class TestKeyboardQuickFilter(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_q_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"q"', js)

    def test_js_cycle_pills(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-filter-pill", js)

    def test_js_q_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Cycle detail status filter", js)


# ---------------------------------------------------------------------------
# 140. Subtask output timestamp
# ---------------------------------------------------------------------------

class TestSubtaskOutputTimestamp(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_out_time_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-out-time", js)

    def test_js_output_updated_at(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("output_updated_at", js)

    def test_css_out_time_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-out-time", css)


# ---------------------------------------------------------------------------
# 141. Card completion milestone arc
# ---------------------------------------------------------------------------

class TestCardMilestoneArc(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_milestone_color(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_milestoneColor", js)

    def test_js_milestone_thresholds(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("pct >= 75", js)
        self.assertIn("pct >= 50", js)


# ---------------------------------------------------------------------------
# 142. Branch compact toggle
# ---------------------------------------------------------------------------

class TestBranchCompactToggle(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_compact_toggle_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-compact-toggle", js)

    def test_js_branch_compact_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-compact", js)

    def test_css_branch_compact_hides_rows(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-compact .subtask-row", css)


# ---------------------------------------------------------------------------
# 143. Detail panel scroll-to-top button
# ---------------------------------------------------------------------------

class TestDetailScrollToTop(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_scroll_top_id(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-scroll-top", js)

    def test_js_scroll_to_top(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("scrollTo", js)

    def test_css_scroll_top_btn(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-scroll-top-btn", css)


# ---------------------------------------------------------------------------
# 144. Keyboard `u` scroll to unverified
# ---------------------------------------------------------------------------

class TestKeyboardScrollUnverified(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_u_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"u"', js)

    def test_js_not_dot_green(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("dot-green", js)

    def test_js_u_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Scroll to first unverified", js)


# ---------------------------------------------------------------------------
# 145. Subtask output line highlight
# ---------------------------------------------------------------------------

class TestOutputLineHighlight(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_out_line_err_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("out-line-err", js)

    def test_js_line_split(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_outLines", js)

    def test_css_line_err_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".out-line-err", css)


# ---------------------------------------------------------------------------
# 146. Card progress ring percentage text
# ---------------------------------------------------------------------------

class TestRingPercentageText(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_ring_pct_text_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("ring-pct-text", js)

    def test_js_ring_text_element(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_ringPctText", js)


# ---------------------------------------------------------------------------
# 147. Branch subtask name list tooltip
# ---------------------------------------------------------------------------

class TestBranchSubtaskTooltip(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_st_names_variable(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_stNames", js)

    def test_js_tooltip_join(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_stNames.join", js)


# ---------------------------------------------------------------------------
# 148. Detail collapse verified branches button
# ---------------------------------------------------------------------------

class TestCollapseVerifiedButton(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_collapse_verified_btn(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("collapseVerifiedBtn", js)

    def test_js_all_green_check(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("allGreen", js)

    def test_js_collapse_verified_title(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Collapse only verified", js)


# ---------------------------------------------------------------------------
# 149. Keyboard `y` yank output
# ---------------------------------------------------------------------------

class TestKeyboardYankOutput(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_y_key_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"y"', js)

    def test_js_clipboard_write(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard.writeText", js)

    def test_js_y_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Yank", js)


# ---------------------------------------------------------------------------
# 150. Subtask output search
# ---------------------------------------------------------------------------

class TestSubtaskOutputSearch(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_out_search_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-out-search", js)

    def test_js_out_line_match(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("out-line-match", js)

    def test_css_out_search_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-out-search", css)

    def test_css_match_highlight(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".out-line-match", css)


# ---------------------------------------------------------------------------
# 151. Card status emoji tooltip
# ---------------------------------------------------------------------------

class TestCardStatusEmojiTooltip(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_badge_title(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('.querySelector(".card-mini-badge").title', js)

    def test_js_tooltip_breakdown(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("verified", js)
        self.assertIn("running", js)
        self.assertIn("pending", js)


# ---------------------------------------------------------------------------
# 152. Branch verified counter badge
# ---------------------------------------------------------------------------

class TestBranchVerifiedCounter(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_verified_cnt_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-verified-cnt", js)

    def test_js_verified_badge(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branchVerifiedBadge", js)

    def test_css_verified_cnt_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-verified-cnt", css)


# ---------------------------------------------------------------------------
# 153. Detail panel task timer
# ---------------------------------------------------------------------------

class TestDetailTaskTimer(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_task_timer_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-task-timer", js)

    def test_js_created_at(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("created_at", js)

    def test_css_task_timer_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".detail-task-timer", css)


# ---------------------------------------------------------------------------
# 154. Keyboard Shift+R reset task
# ---------------------------------------------------------------------------

class TestKeyboardShiftReset(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_shift_r_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"R"', js)
        self.assertIn("e.shiftKey", js)

    def test_js_reset_task_call(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("window.resetTask", js)

    def test_js_shift_r_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Shift+R", js)


# ---------------------------------------------------------------------------
# 155. Subtask output byte size
# ---------------------------------------------------------------------------

class TestSubtaskByteSize(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_size_badge_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("st-size-badge", js)

    def test_js_blob_size(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("new Blob", js)

    def test_css_size_badge_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".st-size-badge", css)


# ---------------------------------------------------------------------------
# 156. Card step counter
# ---------------------------------------------------------------------------

class TestCardStepCounter(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_step_num_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("card-step-num", js)

    def test_js_step_display(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("t.step", js)

    def test_css_step_num_class(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".card-step-num", css)


# ---------------------------------------------------------------------------
# 157. Branch running indicator
# ---------------------------------------------------------------------------

class TestBranchRunningIndicator(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"

    def test_js_run_dot_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-run-dot", js)

    def test_js_run_dot_active(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("branchRunDot", js)

    def test_css_run_dot_active(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".branch-run-dot.active", css)

    def test_css_run_pulse_animation(self):
        css = self._CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("branch-run-pulse", css)


# ---------------------------------------------------------------------------
# 158. Detail panel task status chip
# ---------------------------------------------------------------------------

class TestDetailStatusChip(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"

    def test_js_status_chip_class(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detail-status-chip", js)

    def test_js_chip_color(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("_chipColor", js)


# ---------------------------------------------------------------------------
# 159. Keyboard Shift+V verify all
# ---------------------------------------------------------------------------

class TestKeyboardShiftVerifyAll(unittest.TestCase):
    _JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"

    def test_js_shift_v_handler(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn('"V"', js)

    def test_js_bulk_verify_call(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("detailBulkVerify", js)

    def test_js_shift_v_in_shortcuts(self):
        js = self._JS_PATH.read_text(encoding="utf-8")
        self.assertIn("Verify all unverified", js)


# ---------------------------------------------------------------------------
# 160. Subtask output truncation indicator
# ---------------------------------------------------------------------------
class TestTruncationIndicator(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self):
        self.assertIn("st-trunc-badge", self._JS.read_text(encoding="utf-8"))
    def test_css(self):
        self.assertIn(".st-trunc-badge", self._CSS.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# 161. Card task age
# ---------------------------------------------------------------------------
class TestCardTaskAge(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self):
        self.assertIn("card-task-age", self._JS.read_text(encoding="utf-8"))
    def test_css(self):
        self.assertIn(".card-task-age", self._CSS.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# 162. Branch merge button
# ---------------------------------------------------------------------------
class TestBranchMergeButton(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    def test_js(self):
        self.assertIn("branch-merge-btn", self._JS.read_text(encoding="utf-8"))
    def test_js_merge_text(self):
        self.assertIn("Merge", self._JS.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# 163. Detail panel copy all outputs
# ---------------------------------------------------------------------------
class TestCopyAllOutputs(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    def test_js(self):
        self.assertIn("copyAllBtn", self._JS.read_text(encoding="utf-8"))
    def test_js_all_outputs(self):
        self.assertIn("allOutputs", self._JS.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# 164. Keyboard Shift+C copy all
# ---------------------------------------------------------------------------
class TestKeyboardShiftC(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"C"', js)
        self.assertIn("Shift+C", js)

# 165-169: Round 37
class TestCardStatusTextColor(unittest.TestCase):
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_css(self):
        css = self._CSS.read_text(encoding="utf-8")
        self.assertIn(".counts-done", css)
        self.assertIn(".counts-active", css)

class TestSubtaskDepCount(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self):
        self.assertIn("st-dep-count", self._JS.read_text(encoding="utf-8"))
    def test_css(self):
        self.assertIn(".st-dep-count", self._CSS.read_text(encoding="utf-8"))

class TestBranchStatusSummary(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self):
        self.assertIn("branch-status-line", self._JS.read_text(encoding="utf-8"))
    def test_css(self):
        self.assertIn(".branch-status-line", self._CSS.read_text(encoding="utf-8"))

class TestDetailRefreshTimer(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self):
        self.assertIn("detail-refresh-timer", self._JS.read_text(encoding="utf-8"))
    def test_css(self):
        self.assertIn(".detail-refresh-timer", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftD(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"D"', js)
        self.assertIn("dag/export", js)

# 170-174: Round 38
class TestCardVerifiedDelta(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("card-verified-delta", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".card-verified-delta", self._CSS.read_text(encoding="utf-8"))

class TestSubtaskRowNumber(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("st-row-num", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".st-row-num", self._CSS.read_text(encoding="utf-8"))

class TestBranchCollapseCount(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("branch-collapse-count", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".branch-collapse-count", self._CSS.read_text(encoding="utf-8"))

class TestDetailTotalSize(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("detail-total-size", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".detail-total-size", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftS(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"S"', js)
        self.assertIn("snapshot", js)

# 175-179: Round 39
class TestCardBigPct(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("card-big-pct", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".card-big-pct", self._CSS.read_text(encoding="utf-8"))

class TestSubtaskRowHover(unittest.TestCase):
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_css(self): self.assertIn(".subtask-row:hover", self._CSS.read_text(encoding="utf-8"))

class TestBranchPctBar(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    def test_js(self): self.assertIn("linear-gradient", self._JS.read_text(encoding="utf-8"))

class TestDetailLastMod(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("detail-last-mod", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".detail-last-mod", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftP(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"P"', js)
        self.assertIn("Shift+P", js)

# 180-184: Round 40
class TestCardMiniIcons(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("cnt-icon", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".cnt-v", self._CSS.read_text(encoding="utf-8"))

class TestSubtaskNameCopy(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("st-name-copy", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".st-name-copy", self._CSS.read_text(encoding="utf-8"))

class TestDetailIdPrefix(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("detail-id-prefix", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".detail-id-prefix", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftX(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"X"', js)
        self.assertIn("expandAllBranches", js)

# 185-189: Round 41
class TestCardStatusBorder(unittest.TestCase):
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_css(self):
        css = self._CSS.read_text(encoding="utf-8")
        self.assertIn(".task-card.status-complete", css)
        self.assertIn(".task-card.status-running", css)

class TestSubtaskRowTooltip(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    def test_js(self): self.assertIn("_totalSt", self._JS.read_text(encoding="utf-8"))

class TestBranchAnimation(unittest.TestCase):
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_css(self): self.assertIn(".branch-block", self._CSS.read_text(encoding="utf-8"))

class TestDetailGoal(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("detail-goal", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".detail-goal", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftF(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"F"', js)
        self.assertIn("detail-inline-search", js)

# 190-194: Round 42
class TestSubtaskEmoji(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("st-emoji", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".st-emoji", self._CSS.read_text(encoding="utf-8"))

class TestDetailActionsBar(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("detail-actions-bar", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".detail-actions-bar", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftG(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"G"', js)
        self.assertIn("Shift+G", js)

# 195-199: Round 43
class TestCardConfetti(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("card-confetti", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn("confetti-fly", self._CSS.read_text(encoding="utf-8"))

class TestDetailFullscreen(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("detail-fullscreen", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".detail-fullscreen", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftH(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"H"', js)
        self.assertIn("history", js)

# 200-204: Round 44
class TestSparklineTooltip(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    def test_js(self): self.assertIn("sparkEl.title", self._JS.read_text(encoding="utf-8"))

class TestRowFadeIn(unittest.TestCase):
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_css(self): self.assertIn("st-fade-in", self._CSS.read_text(encoding="utf-8"))

class TestBranchAutoSort(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    def test_js(self): self.assertIn("_sortedBranches", self._JS.read_text(encoding="utf-8"))

class TestKeyboardShiftT(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"T"', js)
        self.assertIn("toggleTheme", js)

# 205-209: Round 45
class TestCardTransArrow(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("card-trans-arrow", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".card-trans-arrow", self._CSS.read_text(encoding="utf-8"))

class TestRowOutputPreview(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    def test_js(self): self.assertIn("data-preview", self._JS.read_text(encoding="utf-8"))

class TestDetailDepMini(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_tasks.js"
    _CSS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard.css"
    def test_js(self): self.assertIn("detail-dep-mini", self._JS.read_text(encoding="utf-8"))
    def test_css(self): self.assertIn(".detail-dep-mini", self._CSS.read_text(encoding="utf-8"))

class TestKeyboardShiftL(unittest.TestCase):
    _JS = Path(__file__).resolve().parents[1] / "api" / "static" / "dashboard_keyboard.js"
    def test_js(self):
        js = self._JS.read_text(encoding="utf-8")
        self.assertIn('"L"', js)
        self.assertIn("Shift+L", js)

if __name__ == "__main__":
    unittest.main()
