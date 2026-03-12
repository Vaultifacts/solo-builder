import { state } from "./dashboard_state.js";
import { api, STATUS_COL, placeholder } from "./dashboard_utils.js";

/* ── History panel (incremental + paged) ─────────────────── */
let _historyLastStep   = 0;
let _historyPage       = 1;
const _PAGE_SIZE       = 20;
const _historyRows     = [];
let _historyRowsFiltered = [];
let _historyServerTotal  = null;
let _historyUnread       = 0;

function _updateHistoryBadge() {
  const badge = document.getElementById("history-unread-badge");
  if (!badge) return;
  if (_historyUnread > 0) {
    badge.textContent = _historyUnread > 99 ? "99+" : String(_historyUnread);
    badge.style.display = "inline-block";
  } else {
    badge.style.display = "none";
  }
}

export function resetHistoryUnread() {
  _historyUnread = 0;
  _updateHistoryBadge();
}

function _updateHistoryStatusChips(byStatus) {
  const el = document.getElementById("history-status-chips");
  if (!el) return;
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
}

export async function pollHistory() {
  try {
    const url = _historyLastStep > 0
      ? `/history?since=${_historyLastStep}&limit=0`
      : `/history?limit=100`;
    const [d, countD] = await Promise.all([
      api(url),
      api("/history/count").catch(() => null),
    ]);
    if (countD) {
      _historyServerTotal = countD.total;
      _updateHistoryStatusChips(countD.by_status || {});
    }
    if (!d.events || d.events.length === 0) {
      if (_historyRows.length === 0) _renderHistory([]);
      return;
    }
    const historyActive = document.getElementById("tab-history")?.classList.contains("active");
    d.events.forEach(e => {
      if (e.step > _historyLastStep) _historyLastStep = e.step;
      _historyRows.unshift(e);
    });
    if (!historyActive) {
      _historyUnread += d.events.length;
      _updateHistoryBadge();
    }
    if (_historyRows.length > 500) _historyRows.splice(500);
    _renderHistory(_historyRows);
  } catch (_) {}
}

window._historyPageStep = function (delta) { historyPageStep(delta); };

export function historyPageStep(delta) {
  const filterEl = document.getElementById("history-filter");
  const q = filterEl ? filterEl.value.trim().toLowerCase() : "";
  const filtered = q
    ? _historyRows.filter(e => e.subtask.toLowerCase().includes(q) || e.status.toLowerCase().includes(q) || e.task.toLowerCase().includes(q))
    : _historyRows;
  const pages = Math.max(1, Math.ceil(filtered.length / _PAGE_SIZE));
  _historyPage = Math.max(1, Math.min(pages, _historyPage + delta));
  _renderHistory(_historyRows);
}

const _KNOWN_STATUSES = new Set(["pending", "running", "review", "verified"]);

function _updateHistoryExportLinks() {
  const q  = (document.getElementById("history-filter")?.value || "").trim();
  const bq = (document.getElementById("history-branch-filter")?.value || "").trim();
  const isStatus = _KNOWN_STATUSES.has(q.toLowerCase());
  let qs = "";
  if (q)  qs += isStatus ? `&status=${encodeURIComponent(q)}` : `&subtask=${encodeURIComponent(q)}`;
  if (bq) qs += `&branch=${encodeURIComponent(bq)}`;
  const csvHref  = `/history/export${qs ? "?" + qs.slice(1) : ""}`;
  const jsonHref = `/history/export?format=json${qs}`;
  const csv  = document.getElementById("history-export-csv");
  const json = document.getElementById("history-export-json");
  if (csv)  csv.href  = csvHref;
  if (json) json.href = jsonHref;
  const tabCsv  = document.getElementById("export-tab-history-csv");
  const tabJson = document.getElementById("export-tab-history-json");
  if (tabCsv)  tabCsv.href  = csvHref;
  if (tabJson) tabJson.href = jsonHref;
  const hint = document.getElementById("export-tab-filter-hint");
  const hintQ = q ? (isStatus ? `status:"${q}"` : `"${q}"`) : "";
  const parts = [hintQ, bq ? `branch:"${bq}"` : ""].filter(Boolean);
  if (hint) hint.textContent = parts.length ? `(filtered: ${parts.join(", ")})` : "";
}

function _renderHistory(events) {
  const el = document.getElementById("history-content");
  if (!events || events.length === 0) {
    el.replaceChildren(placeholder("No history yet."));
    const pager = document.getElementById("history-pager");
    if (pager) pager.style.display = "none";
    return;
  }
  const filterEl = document.getElementById("history-filter");
  const q  = filterEl ? filterEl.value.trim().toLowerCase() : "";
  const bq = (document.getElementById("history-branch-filter")?.value || "").trim().toLowerCase();
  let filtered = q
    ? events.filter(e => e.subtask.toLowerCase().includes(q) || e.status.toLowerCase().includes(q) || e.task.toLowerCase().includes(q))
    : events;
  if (bq) filtered = filtered.filter(e => e.branch.toLowerCase().includes(bq));
  _historyRowsFiltered = filtered;
  const total = filtered.length;
  const pages = Math.max(1, Math.ceil(total / _PAGE_SIZE));
  if (_historyPage > pages) _historyPage = pages;
  const start = (_historyPage - 1) * _PAGE_SIZE;
  const page  = filtered.slice(start, start + _PAGE_SIZE);
  if (page.length === 0) {
    el.replaceChildren(placeholder("No matching events."));
    const pager = document.getElementById("history-pager");
    if (pager) pager.style.display = "none";
    return;
  }
  const rows = page.map(e => {
    const row = document.createElement("div");
    row.className = "diff-entry";
    row.style.cursor = "pointer";
    row.title = "Click to view subtask detail";
    row.addEventListener("click", () => window.openSubtaskModal(e));

    const step = document.createElement("span");
    step.style.cssText = "color:var(--dim);font-size:10px";
    step.textContent = "Step " + e.step;

    const st = document.createElement("span");
    st.className = "diff-st";
    st.textContent = e.subtask;

    const status = document.createElement("span");
    status.style.color = STATUS_COL[e.status] || "var(--text)";
    status.textContent = e.status;

    const task = document.createElement("span");
    task.style.cssText = "color:var(--dim);font-size:10px";
    task.textContent = "(" + e.task + ")";

    row.append(step, " ", st, " ", status, " ", task);
    return row;
  });
  el.replaceChildren(...rows);
  const pager = document.getElementById("history-pager");
  const label = document.getElementById("history-page-label");
  const count = document.getElementById("history-count-label");
  if (pager) pager.style.display = pages > 1 ? "flex" : "none";
  if (label) label.textContent = `${_historyPage}/${pages}`;
  const serverTotal = _historyServerTotal;
  if (count) {
    const reviewCount = filtered.filter(e => e.status === "Review").length;
    const reviewSuffix = reviewCount > 0 ? ` \u00b7 ${reviewCount}\u23f8` : "";
    count.textContent = serverTotal != null && serverTotal > total
      ? `${total} shown / ${serverTotal} total${reviewSuffix}`
      : `${total} event${total !== 1 ? "s" : ""}${reviewSuffix}`;
  }
  _updateHistoryExportLinks();
}

window.renderHistory = function () {
  _historyPage = 1;
  _renderHistory(_historyRows);
  _updateHistoryExportLinks();
  const q = (document.getElementById("history-filter")?.value || "").trim();
  const params = new URLSearchParams(location.hash.slice(1));
  if (q) { params.set("ht-filter", q); } else { params.delete("ht-filter"); }
  const next = params.toString();
  history.replaceState(null, "", next ? "#" + next : location.pathname + location.search);
};

// Restore history filter from URL hash on load
(function _restoreHtFilter() {
  const params = new URLSearchParams(location.hash.slice(1));
  const saved = params.get("ht-filter");
  if (!saved) return;
  const restoreWhenReady = () => {
    const f = document.getElementById("history-filter");
    if (f) { f.value = saved; } else { setTimeout(restoreWhenReady, 100); }
  };
  restoreWhenReady();
}());
