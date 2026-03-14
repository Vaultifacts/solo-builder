import { api, STATUS_COL } from "./dashboard_utils.js";
export { pollBranches } from "./dashboard_branches.js";
export { pollCache, pollCacheHistory } from "./dashboard_cache.js";
export { pollGatesDetailed, pollDebtScanDetailed, pollPromptRegressionDetailed, pollSloDetailed, pollThreatModelDetailed, pollContextWindowDetailed, pollPolicyDetailed, pollLiveSummaryDetailed, pollHealthDetailed, pollCiQualityDetailed, pollPreReleaseDetailed, pollRepoHealthDetailed } from "./dashboard_health.js";
export { pollSettings } from "./dashboard_settings.js";
export { pollStalled } from "./dashboard_stalled.js";
export { pollSubtasks, updateSubtasksExportLinks } from "./dashboard_subtasks.js";
export { pollHistory, historyPageStep, resetHistoryUnread } from "./dashboard_history.js";
export { pollPriority, pollAgents, pollForecast, pollMetrics, pollPerf } from "./dashboard_analytics.js";
import { pollBranches as _pollBranches } from "./dashboard_branches.js";
import { pollCache as _pollCache, pollCacheHistory as _pollCacheHistory } from "./dashboard_cache.js";
import { pollStalled as _pollStalled } from "./dashboard_stalled.js";
import { pollSubtasks as _pollSubtasks, updateSubtasksExportLinks as _updateSubtasksExportLinks } from "./dashboard_subtasks.js";
import { pollHistory as _pollHistory, resetHistoryUnread as _resetHistoryUnread } from "./dashboard_history.js";
import { pollPriority as _pollPriority, pollAgents as _pollAgents, pollForecast as _pollForecast, pollMetrics as _pollMetrics } from "./dashboard_analytics.js";
import { pollDiff as _pollDiff, pollStats as _pollStats } from "./dashboard_journal.js";
import { pollSettings as _pollSettings } from "./dashboard_settings.js";

/* ── Sidebar tabs ────────────────────────────────────────── */
/* ── Keyboard nav for tablist (Arrow Left/Right, Home/End) ── */
document.addEventListener("keydown", (e) => {
  const tab = document.activeElement;
  if (!tab || !tab.classList.contains("sidebar-tab")) return;
  const tabs = [...document.querySelectorAll(".sidebar-tab")];
  const idx = tabs.indexOf(tab);
  if (idx < 0) return;
  let next = -1;
  if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (idx + 1) % tabs.length;
  else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (idx - 1 + tabs.length) % tabs.length;
  else if (e.key === "Home") next = 0;
  else if (e.key === "End") next = tabs.length - 1;
  if (next >= 0) {
    e.preventDefault();
    tabs[next].focus();
    tabs[next].click();
  }
});

window.switchTab = function (name) {
  document.querySelectorAll(".sidebar-tab").forEach(t => {
    const tabName = t.dataset.tab || t.textContent.toLowerCase();
    const isActive = tabName === name;
    t.classList.toggle("active", isActive);
    t.setAttribute("aria-selected", String(isActive));
  });
  document.querySelectorAll(".sidebar-tab-content").forEach(c => c.classList.toggle("active", c.id === "tab-" + name));
  if (name === "journal") {
    const pane = document.getElementById("tab-journal");
    if (pane) pane.scrollTop = 0;
  }
  if (name === "history") {
    _resetHistoryUnread();
  }
  if (name === "subtasks") {
    _updateSubtasksExportLinks();
  }
  if (name === "export") {
    _refreshExportHistoryByStatus();
  }
  /* Immediate poll for the newly-active tab (no waiting for next medium tick) */
  const _tabPollers = {
    diff: [_pollDiff], stats: [_pollStats], branches: [_pollBranches],
    priority: [_pollPriority], stalled: [_pollStalled], subtasks: [_pollSubtasks],
    agents: [_pollAgents], forecast: [_pollForecast], metrics: [_pollMetrics],
    cache: [_pollCache, _pollCacheHistory], "cache-history": [_pollCache, _pollCacheHistory],
    history: [_pollHistory], settings: [_pollSettings],
  };
  const fns = _tabPollers[name];
  if (fns) Promise.all(fns.map(f => f())).catch(() => {});
};

async function _refreshExportHistoryByStatus() {
  try {
    const d = await api("/history/count");
    const el = document.getElementById("export-history-by-status");
    if (!el) return;
    const byStatus = d.by_status || {};
    const entries = Object.entries(byStatus).filter(([, n]) => n > 0);
    if (!entries.length) { el.style.display = "none"; return; }
    el.style.display = "flex";
    el.replaceChildren();
    for (const [s, n] of entries) {
      const chip = document.createElement("span");
      chip.textContent = `${s}: ${n}`;
      chip.style.color = STATUS_COL[s] || "var(--dim)";
      el.append(chip);
    }
  } catch (_) {}
  try {
    const sd = await api("/stalled");
    const minAge = sd.threshold || 5;
    const csv  = document.getElementById("export-stalled-csv");
    const json = document.getElementById("export-stalled-json");
    if (csv)  csv.href  = `/subtasks/export?status=running&min_age=${minAge}`;
    if (json) json.href = `/subtasks/export?status=running&min_age=${minAge}&format=json`;
    const lbl = document.getElementById("export-stalled-threshold");
    if (lbl) lbl.textContent = `\u2265 ${minAge} steps stalled`;
  } catch (_) {}
}
