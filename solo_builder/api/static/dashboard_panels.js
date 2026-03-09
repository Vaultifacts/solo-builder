import { state } from "./dashboard_state.js";
import { api, esc, toast, flash } from "./dashboard_utils.js";
import { svgBar, sparklineSvg } from "./dashboard_svg.js";
export { pollBranches } from "./dashboard_branches.js";
export { pollCache, pollCacheHistory } from "./dashboard_cache.js";

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

const _STATUS_CHIP_COLORS = {Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"};

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
    chip.style.color = _STATUS_CHIP_COLORS[s] || "var(--dim)";
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

const _STATUS_COL = {Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"};

function _placeholder(text) {
  const d = document.createElement("div");
  d.className = "detail-placeholder";
  d.textContent = text;
  return d;
}


function _renderHistory(events) {
  const el = document.getElementById("history-content");
  if (!events || events.length === 0) {
    el.replaceChildren(_placeholder("No history yet."));
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
    el.replaceChildren(_placeholder("No matching events."));
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
    status.style.color = _STATUS_COL[e.status] || "var(--text)";
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
    const reviewSuffix = reviewCount > 0 ? ` · ${reviewCount}⏸` : "";
    count.textContent = serverTotal != null && serverTotal > total
      ? `${total} shown / ${serverTotal} total${reviewSuffix}`
      : `${total} event${total !== 1 ? "s" : ""}${reviewSuffix}`;
  }
  _updateHistoryExportLinks();
}

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
    _historyUnread = 0;
    _updateHistoryBadge();
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
      chip.style.color = _STATUS_CHIP_COLORS[s] || "var(--dim)";
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
    if (lbl) lbl.textContent = `≥ ${minAge} steps stalled`;
  } catch (_) {}
}

/* ── Settings panel ─────────────────────────────────────── */
let _settingsCache = {};

export async function pollSettings() {
  try {
    const d = await api("/config");
    _renderSettings(d);
  } catch (_) {}
}

function _renderSettings(d) {
  const el = document.getElementById("settings-content");
  if (!d || typeof d !== "object") {
    el.replaceChildren(_placeholder("Could not load settings."));
    return;
  }
  _settingsCache = d;
  const counter = document.createElement("div");
  counter.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:6px";
  counter.textContent = `${Object.keys(d).length} settings`;
  const rows = Object.entries(d).map(([k, v]) => {
    const vStr = typeof v === "string" ? v : JSON.stringify(v);
    const inputId = "cfg-" + k;
    const row = document.createElement("div");
    row.className = "diff-entry";
    row.style.cssText = "display:flex;align-items:center;gap:6px";
    const lbl = document.createElement("span");
    lbl.style.cssText = "color:var(--cyan);font-size:10px;min-width:120px;flex-shrink:0";
    lbl.textContent = k;
    row.appendChild(lbl);
    if (typeof v === "boolean") {
      const chk = document.createElement("input");
      chk.type = "checkbox"; chk.id = inputId; chk.checked = v;
      chk.style.accentColor = "var(--cyan)";
      chk.addEventListener("change", () => window.saveSetting(k, chk.checked));
      row.appendChild(chk);
    } else {
      const inp = document.createElement("input");
      inp.id = inputId; inp.value = vStr;
      inp.style.cssText = "flex:1;min-width:0;padding:1px 4px;font-size:10px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:3px;font-family:var(--font)";
      inp.addEventListener("change", () => window.saveSetting(k, inp.value));
      row.appendChild(inp);
    }
    return row;
  });
  const fb = document.createElement("span");
  fb.className = "feedback"; fb.id = "fb-settings";
  const exportDiv = document.createElement("div");
  exportDiv.style.marginTop = "8px";
  const exportA = document.createElement("a");
  exportA.className = "toolbar-btn"; exportA.href = "/config/export"; exportA.download = "settings.json";
  exportA.textContent = "⬇ Export settings.json";
  exportDiv.appendChild(exportA);
  const toolSection = document.createElement("div");
  toolSection.style.cssText = "margin-top:10px;border-top:1px solid var(--border);padding-top:8px";
  const toolHdr = document.createElement("div");
  toolHdr.style.cssText = "font-size:10px;color:var(--dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px";
  toolHdr.textContent = "Tool override";
  const toolRow = document.createElement("div");
  toolRow.style.cssText = "display:flex;gap:4px;align-items:center;flex-wrap:wrap";
  const stInput = document.createElement("input");
  stInput.id = "tool-override-st"; stInput.className = "cmd-input";
  stInput.placeholder = "A1"; stInput.title = "Subtask name"; stInput.style.width = "50px";
  const toolsInput = document.createElement("input");
  toolsInput.id = "tool-override-tools"; toolsInput.className = "cmd-input-wide";
  toolsInput.placeholder = "Read,Glob,Grep"; toolsInput.title = "Comma-separated tool names";
  const toolBtn = document.createElement("button");
  toolBtn.className = "cmd-btn btn-tools"; toolBtn.textContent = "⚙ Set";
  toolBtn.addEventListener("click", () => window.submitToolOverride());
  toolRow.append(stInput, toolsInput, toolBtn);
  const toolFb = document.createElement("span");
  toolFb.className = "feedback"; toolFb.id = "fb-tool-override";
  toolSection.append(toolHdr, toolRow, toolFb);
  el.replaceChildren(counter, ...rows, fb, exportDiv, toolSection);
}

window.submitToolOverride = async function () {
  const st    = (document.getElementById("tool-override-st")?.value    || "").trim().toUpperCase();
  const tools = (document.getElementById("tool-override-tools")?.value || "").trim();
  if (!st)    { flash("fb-tool-override", "Subtask required"); return; }
  if (!tools) { flash("fb-tool-override", "Tools required"); return; }
  try {
    const r = await fetch(state.base + "/tools", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({subtask:st, tools})});
    const d = await r.json();
    if (d.ok) {
      flash("fb-tool-override", `Tools set for ${st}`);
      document.getElementById("tool-override-st").value    = "";
      document.getElementById("tool-override-tools").value = "";
    } else { flash("fb-tool-override", d.reason || "Error"); }
  } catch (e) { flash("fb-tool-override", "Network error"); }
};

window.saveSetting = async function (key, val) {
  if (typeof val === "string") {
    const n = Number(val);
    if (!isNaN(n) && val.trim() !== "") val = n;
  }
  try {
    const r = await fetch(state.base + "/config", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({[key]: val})});
    const d = await r.json();
    if (d.ok) { flash("fb-settings", key + " saved"); _settingsCache = d; }
    else flash("fb-settings", d.reason || "Error");
  } catch (e) { flash("fb-settings", "Network error"); }
};

/* ── Priority panel ─────────────────────────────────────── */
export async function pollPriority() {
  try {
    const d = await api("/priority");
    _renderPriority(d);
  } catch (_) {}
}

function _renderPriority(d) {
  const el = document.getElementById("priority-content");
  if (!d || !d.queue) {
    el.replaceChildren(_placeholder("No priority data."));
    return;
  }
  const header = document.createElement("div");
  header.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:6px";
  header.textContent = d.count + " candidates · step " + d.step;
  const nodes = [header];
  if (d.queue.length === 0) {
    nodes.push(_placeholder("All subtasks Verified or blocked."));
  } else {
    const maxRisk = d.queue[0].risk || 1;
    d.queue.forEach((c, i) => {
      const col = c.status === "Running" ? "var(--cyan)" : "var(--dim)";
      const fill = Math.round(80 * c.risk / maxRisk);
      const row = document.createElement("div");
      row.className = "diff-entry";
      row.style.cssText = "font-size:10px;display:flex;align-items:center;gap:4px";

      const marker = document.createElement("span");
      marker.style.cssText = "color:var(--yellow);min-width:14px";
      marker.textContent = i < 6 ? "▶ " : "  ";

      const stEl = document.createElement("span");
      stEl.style.cssText = "color:var(--cyan);min-width:32px";
      stEl.textContent = c.subtask;

      const statusEl = document.createElement("span");
      statusEl.style.cssText = `color:${col};min-width:52px`;
      statusEl.textContent = c.status;

      const riskEl = document.createElement("span");
      riskEl.style.cssText = "min-width:40px;color:var(--yellow)";
      riskEl.textContent = "r=" + c.risk;

      const barBg = document.createElement("span");
      barBg.style.cssText = "flex:1;background:var(--surface);height:4px;border-radius:2px;position:relative";
      const barFg = document.createElement("span");
      barFg.style.cssText = `position:absolute;left:0;top:0;height:4px;width:${fill}%;border-radius:2px;background:${c.status === "Running" ? "var(--cyan)" : "var(--yellow)"}`;
      barBg.appendChild(barFg);

      const taskEl = document.createElement("span");
      taskEl.style.cssText = "color:var(--dim);font-size:9px;min-width:60px;text-align:right";
      taskEl.textContent = c.task;

      row.append(marker, stEl, statusEl, riskEl, barBg, taskEl);
      nodes.push(row);
    });
  }
  el.replaceChildren(...nodes);
}

/* ── Stalled panel ──────────────────────────────────────── */
let _stalledTaskFilter   = "";
let _stalledBranchFilter = "";

export async function pollStalled() {
  try {
    let qs = _stalledTaskFilter   ? `?task=${encodeURIComponent(_stalledTaskFilter)}`   : "";
    if (_stalledBranchFilter) qs += (qs ? "&" : "?") + `branch=${encodeURIComponent(_stalledBranchFilter)}`;
    const d = await api("/stalled" + qs);
    _renderStalled(d);
  } catch (_) {}
}

window._applyStalledTaskFilter = function () {
  const el = document.getElementById("stalled-task-filter");
  _stalledTaskFilter = el ? el.value.trim() : "";
  pollStalled();
};

window._applyStalledBranchFilter = function () {
  const el = document.getElementById("stalled-branch-filter");
  _stalledBranchFilter = el ? el.value.trim() : "";
  pollStalled();
};

function _updateStalledFilterLabel() {
  const lbl = document.getElementById("stalled-filter-label");
  if (!lbl) return;
  const parts = [];
  if (_stalledTaskFilter)   parts.push(`task: ${_stalledTaskFilter}`);
  if (_stalledBranchFilter) parts.push(`branch: ${_stalledBranchFilter}`);
  lbl.textContent = parts.length ? `· ${parts.join(" · ")}` : "";
}

function _renderStalled(d) {
  _updateStalledFilterLabel();
  const el = document.getElementById("stalled-content");
  if (!d) { el.replaceChildren(_placeholder("No data.")); return; }
  const header = document.createElement("div");
  header.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:6px";
  header.textContent = "threshold: " + d.threshold + " steps · step " + d.step;
  const nodes = [header];
  if (!d.stalled || d.stalled.length === 0) {
    const p = _placeholder("No stalled subtasks.");
    p.style.color = "var(--green)";
    nodes.push(p);
  } else {
    // ── Per-branch summary ────────────────────────────────
    const byBranch = {};
    d.stalled.forEach(s => {
      const key = s.task + " / " + s.branch;
      byBranch[key] = (byBranch[key] || 0) + 1;
    });
    if (Object.keys(byBranch).length > 1) {
      const summaryDiv = document.createElement("div");
      summaryDiv.style.cssText = "margin-bottom:6px;padding:4px 6px;background:var(--bg2);border-radius:3px;border:1px solid var(--border)";
      const summaryTitle = document.createElement("div");
      summaryTitle.style.cssText = "font-size:9px;color:var(--dim);margin-bottom:3px";
      summaryTitle.textContent = "by branch";
      summaryDiv.appendChild(summaryTitle);
      Object.entries(byBranch).sort((a, b) => b[1] - a[1]).forEach(([key, cnt]) => {
        const brRow = document.createElement("div");
        brRow.style.cssText = "display:flex;justify-content:space-between;font-size:9px";
        const keyEl = document.createElement("span");
        keyEl.style.color = "var(--dim)";
        keyEl.textContent = key;
        const cntEl = document.createElement("span");
        cntEl.style.color = "var(--yellow)";
        cntEl.textContent = cnt + " stalled";
        brRow.append(keyEl, cntEl);
        summaryDiv.appendChild(brRow);
      });
      nodes.push(summaryDiv);
    }
    d.stalled.forEach(s => {
      const pct = Math.min(100, Math.round(s.age / (d.threshold * 3) * 100));
      const row = document.createElement("div");
      row.className = "diff-entry";
      row.style.cssText = "font-size:10px;display:flex;align-items:center;gap:4px";

      const stEl = document.createElement("span");
      stEl.style.cssText = "color:var(--yellow);min-width:32px";
      stEl.textContent = s.subtask;

      const ageEl = document.createElement("span");
      ageEl.style.cssText = "color:var(--red);min-width:50px";
      ageEl.textContent = s.age + " steps";

      const barBg = document.createElement("span");
      barBg.style.cssText = "flex:1;background:var(--surface);height:4px;border-radius:2px;position:relative";
      const barFg = document.createElement("span");
      barFg.style.cssText = `position:absolute;left:0;top:0;height:4px;width:${pct}%;border-radius:2px;background:var(--red)`;
      barBg.appendChild(barFg);

      const taskEl = document.createElement("span");
      taskEl.style.cssText = "color:var(--dim);font-size:9px;min-width:60px;text-align:right";
      taskEl.textContent = s.task;

      const healBtn = document.createElement("button");
      healBtn.style.cssText = "background:var(--surface);color:var(--cyan);border:1px solid var(--border);border-radius:3px;font-size:9px;padding:0 4px;cursor:pointer";
      healBtn.title = "Reset to Pending";
      healBtn.textContent = "↻";
      healBtn.addEventListener("click", () => window.healSubtask(s.subtask));

      row.append(stEl, ageEl, barBg, taskEl, healBtn);
      nodes.push(row);
    });
  }
  el.replaceChildren(...nodes);
}

window.healSubtask = async function (st) {
  try {
    const r = await fetch(state.base + "/heal", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({subtask: st})});
    const d = await r.json();
    if (d.ok) toast("↻ " + st + " heal triggered");
    else toast(d.reason || "Heal failed");
  } catch (_) { toast("Network error"); }
};

/* ── Subtasks tab ───────────────────────────────────────── */
let _subtasksAll = [];
const _subtasksSel = new Set();
let _subtasksPage         = 1;
let _subtasksPages        = 1;
let _subtasksTotal        = 0;
let _subtasksStatusFilter = "";   // "" = all; "Pending"|"Running"|"Review"|"Verified"
let _subtasksNameFilter   = "";   // "" = all; substring matched against subtask name
let _subtasksTaskFilter   = "";   // "" = all; substring matched against task name
let _subtasksBranchFilter = "";   // "" = all; substring matched against branch name
const _SUBTASKS_LIMIT     = 50;
const _SUBTASKS_STATUS_VALS = new Set(["pending", "running", "review", "verified"]);

function _updateBulkBar() {
  const bar = document.getElementById("subtasks-bulk-bar");
  const cnt = document.getElementById("subtasks-sel-count");
  if (!bar) return;
  const n = _subtasksSel.size;
  bar.style.display = n > 0 ? "flex" : "none";
  if (cnt) cnt.textContent = `${n} selected`;
}

function _updateSubtasksPager() {
  const pager  = document.getElementById("subtasks-pager");
  const lbl    = document.getElementById("subtasks-page-label");
  const cnt    = document.getElementById("subtasks-count-label");
  if (!pager) return;
  if (_subtasksPages > 1) {
    pager.style.display = "flex";
    if (lbl) lbl.textContent = `${_subtasksPage} / ${_subtasksPages}`;
    if (cnt) cnt.textContent = `${_subtasksTotal} subtasks`;
  } else {
    pager.style.display = "none";
  }
}

export async function pollSubtasks() {
  try {
    let url = `/subtasks?limit=${_SUBTASKS_LIMIT}&page=${_subtasksPage}`;
    if (_subtasksStatusFilter) url += `&status=${encodeURIComponent(_subtasksStatusFilter)}`;
    if (_subtasksNameFilter)   url += `&name=${encodeURIComponent(_subtasksNameFilter)}`;
    if (_subtasksTaskFilter)   url += `&task=${encodeURIComponent(_subtasksTaskFilter)}`;
    if (_subtasksBranchFilter) url += `&branch=${encodeURIComponent(_subtasksBranchFilter)}`;
    const d = await api(url);
    _subtasksAll   = d.subtasks || [];
    _subtasksTotal = d.total    ?? _subtasksAll.length;
    _subtasksPages = d.pages    ?? 1;
    _subtasksPage  = d.page     ?? 1;
    _renderSubtasks();
  } catch (_) {}
}

function _updateSubtasksExportLinks() {
  const csv  = document.getElementById("subtasks-export-csv");
  const json = document.getElementById("subtasks-export-json");
  if (!csv || !json) return;
  let qs = _subtasksStatusFilter ? `?status=${encodeURIComponent(_subtasksStatusFilter)}` : "";
  if (_subtasksNameFilter) qs += (qs ? "&" : "?") + `name=${encodeURIComponent(_subtasksNameFilter)}`;
  if (_subtasksTaskFilter)   qs += (qs ? "&" : "?") + `task=${encodeURIComponent(_subtasksTaskFilter)}`;
  if (_subtasksBranchFilter) qs += (qs ? "&" : "?") + `branch=${encodeURIComponent(_subtasksBranchFilter)}`;
  csv.href  = `/subtasks/export${qs}`;
  json.href = `/subtasks/export${qs ? qs + "&format=json" : "?format=json"}`;
}

window._subtasksPageStep = function (delta) {
  const next = _subtasksPage + delta;
  if (next < 1 || next > _subtasksPages) return;
  _subtasksPage = next;
  pollSubtasks();
};

window._applySubtasksTaskFilter = function () {
  const v = (document.getElementById("subtasks-task-filter")?.value || "").trim().toLowerCase();
  if (v === _subtasksTaskFilter) return;
  _subtasksTaskFilter = v;
  _subtasksPage = 1;
  _updateSubtasksExportLinks();
  pollSubtasks();
};

window._applySubtasksBranchFilter = function () {
  const v = (document.getElementById("subtasks-branch-filter")?.value || "").trim().toLowerCase();
  if (v === _subtasksBranchFilter) return;
  _subtasksBranchFilter = v;
  _subtasksPage = 1;
  _updateSubtasksExportLinks();
  pollSubtasks();
};

window._resetSubtasksFilters = function () {
  _subtasksStatusFilter = "";
  _subtasksNameFilter   = "";
  _subtasksTaskFilter   = "";
  _subtasksBranchFilter = "";
  _subtasksPage = 1;
  const f = document.getElementById("subtasks-filter");
  const tf = document.getElementById("subtasks-task-filter");
  const bf = document.getElementById("subtasks-branch-filter");
  if (f)  f.value  = "";
  if (tf) tf.value = "";
  if (bf) bf.value = "";
  _updateSubtasksExportLinks();
};

window._clearSubtasksFilters = function () {
  const hadFilter = _subtasksStatusFilter || _subtasksNameFilter || _subtasksTaskFilter || _subtasksBranchFilter;
  window._resetSubtasksFilters();
  if (hadFilter) pollSubtasks();
};

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

window.renderSubtasks = function () {
  const q  = (document.getElementById("subtasks-filter")?.value || "").trim();
  const ql = q.toLowerCase();
  const params = new URLSearchParams(location.hash.slice(1));
  if (q) { params.set("st-filter", q); } else { params.delete("st-filter"); }
  const next = params.toString();
  history.replaceState(null, "", next ? "#" + next : location.pathname + location.search);

  if (_SUBTASKS_STATUS_VALS.has(ql)) {
    // Known status value → server-side status filter
    _subtasksStatusFilter = ql;
    _subtasksNameFilter   = "";
    _subtasksPage = 1;
    _updateSubtasksExportLinks();
    pollSubtasks();
  } else if (q) {
    // Non-empty non-status text → server-side name filter
    _subtasksNameFilter   = ql;
    _subtasksStatusFilter = "";
    _subtasksPage = 1;
    _updateSubtasksExportLinks();
    pollSubtasks();
  } else {
    // Empty input → clear all server filters and re-fetch
    const hadFilter = _subtasksStatusFilter || _subtasksNameFilter;
    _subtasksStatusFilter = "";
    _subtasksNameFilter   = "";
    _subtasksPage = 1;
    _updateSubtasksExportLinks();
    if (hadFilter) { pollSubtasks(); } else { _renderSubtasks(); }
  }
};

// Restore subtasks filter from URL hash on load
(function _restoreStFilter() {
  const params = new URLSearchParams(location.hash.slice(1));
  const saved = params.get("st-filter");
  if (!saved) return;
  const restoreWhenReady = () => {
    const f = document.getElementById("subtasks-filter");
    if (f) { f.value = saved; } else { setTimeout(restoreWhenReady, 100); }
  };
  restoreWhenReady();
}());

window.subtasksClearSel = function () {
  _subtasksSel.clear();
  _renderSubtasks();
};

function _fbSet(fb, msg) {
  if (!fb) return;
  fb.textContent = msg;
  setTimeout(() => { if (fb) fb.textContent = ""; }, 3000);
}

window.subtasksBulkReset = async function () {
  if (!_subtasksSel.size) return;
  const fb = document.getElementById("fb-subtasks-bulk");
  try {
    const d = await fetch(state.base + "/subtasks/bulk-reset", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({subtasks: [..._subtasksSel]}),
    }).then(r => r.json());
    _fbSet(fb, d.ok ? `↺ ${d.reset_count} reset` : (d.reason || "Error"));
    _subtasksSel.clear();
    await pollSubtasks();
  } catch (_) { _fbSet(fb, "Network error"); }
};

window.subtasksBulkVerify = async function () {
  if (!_subtasksSel.size) return;
  const fb = document.getElementById("fb-subtasks-bulk");
  try {
    const d = await fetch(state.base + "/subtasks/bulk-verify", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({subtasks: [..._subtasksSel]}),
    }).then(r => r.json());
    _fbSet(fb, d.ok ? `✔ ${d.verified_count} verified` : (d.reason || "Error"));
    _subtasksSel.clear();
    await pollSubtasks();
  } catch (_) { _fbSet(fb, "Network error"); }
};

function _renderSubtasks() {
  const el = document.getElementById("subtasks-content");
  if (!el) return;
  const rows = _subtasksAll;  // server-side filters (status, name) already applied
  const hasFilter = _subtasksStatusFilter || _subtasksNameFilter || _subtasksTaskFilter || _subtasksBranchFilter;
  // Update filter summary label
  const filterLbl = document.getElementById("subtasks-filter-label");
  if (filterLbl) {
    const parts = [];
    if (_subtasksStatusFilter) parts.push(_subtasksStatusFilter);
    if (_subtasksNameFilter)   parts.push(`"${_subtasksNameFilter}"`);
    if (_subtasksTaskFilter)   parts.push(`task:${_subtasksTaskFilter}`);
    if (_subtasksBranchFilter) parts.push(`branch:${_subtasksBranchFilter}`);
    filterLbl.textContent = parts.length ? `· ${parts.join(" ")} (${rows.length})` : "";
  }
  const clearBtn = document.getElementById("subtasks-clear-filters");
  if (clearBtn) clearBtn.style.display = hasFilter ? "" : "none";
  if (rows.length === 0) {
    el.replaceChildren(_placeholder(hasFilter ? "No matching subtasks." : "No subtasks yet."));
    return;
  }
  const counter = document.createElement("div");
  counter.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:4px";
  counter.textContent = `${rows.length} subtask${rows.length !== 1 ? "s" : ""}`;
  const nodes = [counter];
  rows.forEach(s => {
    const ev = {subtask: s.subtask, task: s.task, branch: s.branch, status: s.status, step: "—", output: ""};
    const row = document.createElement("div");
    row.className = "diff-entry";
    row.style.cssText = "display:flex;align-items:center;gap:6px";

    const chk = document.createElement("input");
    chk.type = "checkbox"; chk.style.accentColor = "var(--cyan)";
    chk.checked = _subtasksSel.has(s.subtask);
    chk.addEventListener("change", () => {
      if (chk.checked) _subtasksSel.add(s.subtask);
      else _subtasksSel.delete(s.subtask);
      _updateBulkBar();
    });

    const stEl = document.createElement("span");
    stEl.className = "diff-st"; stEl.style.cssText = "min-width:30px;cursor:pointer";
    stEl.textContent = s.subtask;
    stEl.addEventListener("click", () => window.openSubtaskModal(ev));

    const statusEl = document.createElement("span");
    statusEl.style.cssText = `color:${_STATUS_COL[s.status] || "var(--text)"};min-width:60px;font-size:10px`;
    statusEl.textContent = s.status;
    const branchEl = document.createElement("span");
    branchEl.style.cssText = "color:var(--dim);font-size:9px;min-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
    branchEl.textContent = s.branch;
    const lenEl = document.createElement("span");
    lenEl.style.cssText = "color:var(--dim);font-size:9px";
    lenEl.textContent = `${s.output_length}b`;
    row.append(chk, stEl, statusEl, branchEl, lenEl);
    nodes.push(row);
  });
  el.replaceChildren(...nodes);
  _updateBulkBar();
  _updateSubtasksPager();
}

/* ── Agents panel ───────────────────────────────────────── */
export async function pollAgents() {
  try {
    const d = await api("/agents");
    _renderAgents(d);
  } catch (_) {}
}

function _renderAgents(d) {
  const el = document.getElementById("agents-content");
  if (!d) { el.replaceChildren(_placeholder("No data.")); return; }
  const f = d.forecast || {};
  const pct = f.pct || 0;
  const barW = 120, fillW = Math.round(barW * pct / 100);
  const stepEl = document.createElement("div");
  stepEl.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:8px";
  stepEl.textContent = `step ${d.step}`;
  const barDiv = document.createElement("div");
  barDiv.style.marginBottom = "8px";
  barDiv.appendChild(svgBar(barW, fillW, `${pct}% (${f.verified}/${f.total})`, "var(--cyan)"));
  const cards = [
    {label: "Planner",       val: `cache interval: ${d.planner?.cache_interval || 5} steps`},
    {label: "Executor",      val: `max/step: ${d.executor?.max_per_step || 6}`},
    {label: "SelfHealer",    val: `healed: ${d.healer?.healed_total || 0}  stalled: ${d.healer?.currently_stalled || 0}  threshold: ${d.healer?.threshold || 5}`},
    {label: "MetaOptimizer", val: `history: ${d.meta?.history_len || 0}  heal: ${d.meta?.heal_rate?.toFixed(2) || "0.00"}/step  verify: ${d.meta?.verify_rate?.toFixed(2) || "0.00"}/step`},
    {label: "Forecast",      val: `${f.remaining || 0} remaining` + (f.eta_steps ? `  ETA: ~${f.eta_steps} steps` : "")},
  ];
  const cardEls = cards.map(c => {
    const row = document.createElement("div");
    row.className = "diff-entry"; row.style.fontSize = "10px";
    const lbl = document.createElement("span");
    lbl.style.cssText = "color:var(--cyan);min-width:80px;display:inline-block";
    lbl.textContent = c.label;
    const val = document.createElement("span");
    val.style.color = "var(--dim)"; val.textContent = " " + c.val;
    row.append(lbl, val);
    return row;
  });
  el.replaceChildren(stepEl, barDiv, ...cardEls);
}

/* ── Forecast panel ─────────────────────────────────────── */
export async function pollForecast() {
  try {
    const d = await api("/forecast");
    const el = document.getElementById("forecast-content");
    if (!el) return;
    const eta  = d.eta_steps != null ? `~${d.eta_steps} steps` : "N/A";
    const rate = d.verified_per_step != null ? d.verified_per_step.toFixed(2) : "—";
    const pct  = d.percent_complete != null ? d.percent_complete.toFixed(1) : "—";
    const barW = 120, fillW = Math.round(barW * (d.percent_complete || 0) / 100);
    const barWrap = document.createElement("div");
    barWrap.style.marginBottom = "8px";
    barWrap.appendChild(svgBar(barW, fillW, `${pct}%`, "var(--green)"));
    const mkRow = (label, content) => {
      const row = document.createElement("div");
      row.className = "diff-entry"; row.style.fontSize = "10px";
      const lbl = document.createElement("span");
      lbl.style.cssText = "color:var(--cyan);min-width:80px;display:inline-block";
      lbl.textContent = label;
      row.appendChild(lbl);
      if (typeof content === "string") {
        row.appendChild(document.createTextNode(content));
      } else {
        row.appendChild(content);
      }
      return row;
    };
    const pctStrong = document.createElement("strong");
    pctStrong.textContent = `${pct}%`;
    el.replaceChildren(
      barWrap,
      mkRow("Completion", pctStrong),
      mkRow("Rate", `${rate} verified/step`),
      mkRow("ETA", eta),
      mkRow("Verified", `${d.verified ?? "—"} / ${d.total ?? "—"}`),
      mkRow("Stalled", `${d.stalled_count ?? 0}`),
    );
  } catch (_) {}
}

/* ── Metrics panel ──────────────────────────────────────── */
export async function pollMetrics() {
  try {
    const d = await api("/metrics");
    const el = document.getElementById("metrics-content");
    if (!el) return;
    const s = d.summary || {};
    const hist = d.history || [];
    const W = 200, H = 48, pad = 4;
    const sparkline = sparklineSvg(hist, W, H, pad);
    const elapsedStr = d.elapsed_s != null ? `${d.elapsed_s}s` : "—";
    const rateStr    = d.steps_per_min != null ? `${d.steps_per_min}/min` : "—";
    const mkSect = (label, marginTop) => {
      const h = document.createElement("div");
      h.style.cssText = `font-size:10px;color:var(--dim);${marginTop ? "margin:8px 0 4px;" : "margin-bottom:4px;"}text-transform:uppercase;letter-spacing:1px`;
      h.textContent = label;
      return h;
    };
    const mkRow = (label, text, labelColor) => {
      const row = document.createElement("div");
      row.className = "diff-entry"; row.style.fontSize = "10px";
      const lbl = document.createElement("span");
      lbl.style.cssText = `color:${labelColor || "var(--cyan)"};min-width:110px;display:inline-block`;
      lbl.textContent = label;
      row.append(lbl, document.createTextNode(text));
      return row;
    };
    const chartLabel = document.createElement("div");
    chartLabel.style.cssText = "font-size:10px;color:var(--dim);margin-bottom:2px";
    chartLabel.textContent = "Verified/step over time:";
    const dlBar = document.createElement("div");
    dlBar.style.cssText = "margin-top:8px;display:flex;gap:6px";
    const csvA = document.createElement("a");
    csvA.className = "toolbar-btn"; csvA.href = "/metrics/export"; csvA.download = "metrics.csv";
    csvA.textContent = "Download CSV";
    const jsonA = document.createElement("a");
    jsonA.className = "toolbar-btn"; jsonA.href = "/metrics/export?format=json"; jsonA.download = "metrics.json";
    jsonA.textContent = "Download JSON";
    dlBar.append(csvA, jsonA);
    el.replaceChildren(
      mkSect("Run health", false),
      mkRow("Verified", `${d.verified ?? "—"} / ${d.total ?? "—"} (${d.pct ?? 0}%)`),
      mkRow("Pending",  `${d.pending ?? "—"}`),
      mkRow("Running",  `${d.running ?? "—"}`),
      mkRow("Review",   `${d.review ?? 0}`),
      mkRow("Stalled",  `${d.stalled ?? 0}`, (d.stalled ?? 0) > 0 ? "var(--yellow)" : "var(--cyan)"),
      mkRow("Elapsed",  elapsedStr),
      mkRow("Step rate", rateStr),
      mkSect("Analytics", true),
      chartLabel,
      sparkline,
      mkRow("Total steps",   `${s.total_steps ?? "—"}`),
      mkRow("Total verifies",`${s.total_verifies ?? "—"}`),
      mkRow("Avg rate",      `${s.avg_verified_per_step ?? "—"} v/step`),
      mkRow("Peak rate",     `${s.peak_verified_per_step ?? "—"} v/step`),
      mkRow("Steps w/ heals",`${s.steps_with_heals ?? 0}`),
      mkRow("Total healed",  `${d.total_healed ?? 0}`),
      dlBar,
    );
  } catch (_) {}
}

