import { api, STATUS_COL } from "./dashboard_utils.js";
export { pollBranches } from "./dashboard_branches.js";
export { pollCache, pollCacheHistory } from "./dashboard_cache.js";
export { pollGatesDetailed, pollDebtScanDetailed, pollPromptRegressionDetailed, pollSloDetailed, pollThreatModelDetailed, pollContextWindowDetailed, pollPolicyDetailed, pollLiveSummaryDetailed, pollHealthDetailed, pollCiQualityDetailed, pollPreReleaseDetailed, pollRepoHealthDetailed } from "./dashboard_health.js";
export { pollSettings } from "./dashboard_settings.js";
export { pollStalled } from "./dashboard_stalled.js";
export { pollSubtasks, updateSubtasksExportLinks } from "./dashboard_subtasks.js";
export { pollHistory, historyPageStep, resetHistoryUnread } from "./dashboard_history.js";
export { pollPriority, pollAgents, pollForecast, pollMetrics } from "./dashboard_analytics.js";
import { updateSubtasksExportLinks as _updateSubtasksExportLinks } from "./dashboard_subtasks.js";
import { resetHistoryUnread as _resetHistoryUnread } from "./dashboard_history.js";

/* ── Sidebar tabs ────────────────────────────────────────── */
window.switchTab = function (name) {
  document.querySelectorAll(".sidebar-tab").forEach(t => {
    const tabName = t.dataset.tab || t.textContent.toLowerCase();
    t.classList.toggle("active", tabName === name);
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
