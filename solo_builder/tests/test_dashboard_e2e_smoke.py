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


if __name__ == "__main__":
    unittest.main()
