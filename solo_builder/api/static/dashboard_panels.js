import { state } from "./dashboard_state.js";
import { api, esc, toast, flash } from "./dashboard_utils.js";

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

export async function pollHistory() {
  try {
    const url = _historyLastStep > 0
      ? `/history?since=${_historyLastStep}&limit=0`
      : `/history?limit=100`;
    const [d, countD] = await Promise.all([
      api(url),
      api("/history/count").catch(() => null),
    ]);
    if (countD) _historyServerTotal = countD.total;
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

function _updateHistoryExportLinks() {
  const q  = (document.getElementById("history-filter")?.value || "").trim();
  const bq = (document.getElementById("history-branch-filter")?.value || "").trim();
  let qs = q  ? `&subtask=${encodeURIComponent(q)}`  : "";
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
  const parts = [q ? `"${q}"` : "", bq ? `branch:"${bq}"` : ""].filter(Boolean);
  if (hint) hint.textContent = parts.length ? `(filtered: ${parts.join(", ")})` : "";
}

function _renderHistory(events) {
  const el = document.getElementById("history-content");
  if (!events || events.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">No history yet.</div>`;
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
    el.innerHTML = `<div class="detail-placeholder">No matching events.</div>`;
    const pager = document.getElementById("history-pager");
    if (pager) pager.style.display = "none";
    return;
  }
  const statusColor = s => ({Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"})[s] || "var(--text)";
  let html = "";
  page.forEach(e => {
    const safeEv = JSON.stringify(e).replace(/'/g, "&#39;");
    html += `<div class="diff-entry" style="cursor:pointer" onclick='openSubtaskModal(${safeEv})' title="Click to view subtask detail"><span style="color:var(--dim);font-size:10px">Step ${e.step}</span> <span class="diff-st">${esc(e.subtask)}</span> <span style="color:${statusColor(e.status)}">${esc(e.status)}</span> <span style="color:var(--dim);font-size:10px">(${esc(e.task)})</span></div>`;
  });
  el.innerHTML = html;
  const pager = document.getElementById("history-pager");
  const label = document.getElementById("history-page-label");
  const count = document.getElementById("history-count-label");
  if (pager) pager.style.display = pages > 1 ? "flex" : "none";
  if (label) label.textContent = `${_historyPage}/${pages}`;
  const serverTotal = _historyServerTotal;
  if (count) {
    count.textContent = serverTotal != null && serverTotal > total
      ? `${total} shown / ${serverTotal} total`
      : `${total} event${total !== 1 ? "s" : ""}`;
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
};

/* ── Branches panel ─────────────────────────────────────── */
export async function pollBranches() {
  try {
    if (state.selectedTask) {
      const d = await api("/branches/" + encodeURIComponent(state.selectedTask));
      _renderBranchesDetail(d);
    } else {
      const [d, summary] = await Promise.all([api("/branches"), api("/dag/summary").catch(() => null)]);
      _renderBranchesAll(d, summary);
    }
  } catch (_) {}
}

function _renderBranchesAll(d, summary) {
  const el = document.getElementById("branches-content");
  if (!d.branches || d.branches.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">No branches yet.</div>`;
    return;
  }
  const barW = 60;
  let html = "";

  // ── Pipeline Overview (from /dag/summary) ───────────────
  if (summary && summary.total > 0) {
    const ovW = 120;
    const ovFill = Math.round(summary.pct * ovW / 100);
    html += `<div style="margin-bottom:10px;padding:6px 8px;background:var(--bg2);border-radius:4px;border:1px solid var(--border)">`;
    html += `<div style="font-size:10px;color:var(--cyan);font-weight:bold;margin-bottom:4px">Pipeline Overview — Step ${summary.step}</div>`;
    html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">`;
    html += `<div style="width:${ovW}px;height:8px;background:var(--bg3);border-radius:4px;flex-shrink:0"><div style="width:${ovFill}px;height:8px;background:var(--green);border-radius:4px"></div></div>`;
    html += `<span style="font-size:11px;color:var(--text)">${summary.verified}/${summary.total} (${summary.pct}%)</span>`;
    html += `</div>`;
    html += `<div style="font-size:10px;color:var(--dim)">${summary.running} running · ${summary.pending} pending</div>`;
    if (summary.tasks && summary.tasks.length > 0) {
      html += `<div style="margin-top:6px">`;
      summary.tasks.forEach(t => {
        const tw = Math.round(t.pct * 60 / 100);
        html += `<div style="display:flex;align-items:center;gap:6px;margin-top:3px">`;
        html += `<span style="color:var(--dim);font-size:10px;min-width:48px;flex-shrink:0">${esc(t.id)}</span>`;
        html += `<div style="width:60px;height:4px;background:var(--bg3);border-radius:2px;flex-shrink:0"><div style="width:${tw}px;height:4px;background:var(--green);border-radius:2px"></div></div>`;
        html += `<span style="font-size:10px;color:var(--dim)">${t.verified}/${t.subtasks} (${t.pct}%)</span>`;
        html += `</div>`;
      });
      html += `</div>`;
    }
    html += `</div>`;
  }

  html += `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">${d.count} branches across all tasks</div>`;
  d.branches.forEach(br => {
    const w = Math.round(br.pct * barW / 100);
    html += `<div class="diff-entry" style="cursor:pointer;display:flex;align-items:center;gap:8px" onclick="selectTask(${JSON.stringify(br.task)})" title="Click to select task">`;
    html += `<span style="color:var(--dim);font-size:10px;min-width:60px;flex-shrink:0">${esc(br.task)}</span>`;
    html += `<span style="color:var(--cyan);min-width:80px;flex-shrink:0">${esc(br.branch)}</span>`;
    html += `<div style="width:${barW}px;height:6px;background:var(--bg2);border-radius:3px;flex-shrink:0"><div style="width:${w}px;height:6px;background:var(--green);border-radius:3px"></div></div>`;
    html += `<span style="color:var(--dim);font-size:10px">${br.verified}/${br.total}</span>`;
    if (br.running > 0) html += `<span style="font-size:10px;color:var(--cyan)">${br.running}▶</span>`;
    html += `</div>`;
  });
  el.innerHTML = html;
}

function _renderBranchesDetail(d) {
  const el = document.getElementById("branches-content");
  if (!d.branches || d.branches.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">No branches.</div>`;
    return;
  }
  const statusColor = s => ({Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"})[s] || "var(--text)";
  let html = `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">${esc(d.task)} — ${d.branch_count} branches</div>`;
  d.branches.forEach(br => {
    html += `<div style="margin-bottom:8px"><span style="color:var(--cyan);font-weight:bold">${esc(br.branch)}</span> <span style="color:var(--dim);font-size:10px">${br.subtask_count} STs</span>`;
    html += ` <span style="font-size:10px;color:var(--green)">${br.verified}✓</span> <span style="font-size:10px;color:var(--cyan)">${br.running}▶</span> <span style="font-size:10px;color:var(--yellow)">${br.pending}●</span>`;
    br.subtasks.forEach(st => {
      html += `<div class="diff-entry" style="padding-left:12px"><span class="diff-st">${esc(st.name)}</span> <span style="color:${statusColor(st.status)}">${esc(st.status)}</span></div>`;
    });
    html += `</div>`;
  });
  el.innerHTML = html;
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
    el.innerHTML = `<div class="detail-placeholder">Could not load settings.</div>`;
    return;
  }
  _settingsCache = d;
  let html = `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">${Object.keys(d).length} settings</div>`;
  Object.entries(d).forEach(([k, v]) => {
    const vStr = typeof v === "string" ? v : JSON.stringify(v);
    const inputId = "cfg-" + k;
    html += `<div class="diff-entry" style="display:flex;align-items:center;gap:6px">`;
    html += `<span style="color:var(--cyan);font-size:10px;min-width:120px;flex-shrink:0">${esc(k)}</span>`;
    if (typeof v === "boolean") {
      const chk = v ? "checked" : "";
      html += `<input type="checkbox" id="${inputId}" ${chk} onchange="saveSetting(${JSON.stringify(k)},this.checked)" style="accent-color:var(--cyan)">`;
    } else {
      html += `<input id="${inputId}" value="${vStr.replace(/"/g,'&quot;')}" style="flex:1;min-width:0;padding:1px 4px;font-size:10px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:3px;font-family:var(--font)" onchange="saveSetting(${JSON.stringify(k)},this.value)">`;
    }
    html += `</div>`;
  });
  html += `<span class="feedback" id="fb-settings"></span>`;
  html += `<div style="margin-top:8px"><a class="toolbar-btn" href="/config/export" download="settings.json">&#8659; Export settings.json</a></div>`;
  html += `<div style="margin-top:10px;border-top:1px solid var(--border);padding-top:8px">` +
    `<div style="font-size:10px;color:var(--dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px">Tool override</div>` +
    `<div style="display:flex;gap:4px;align-items:center;flex-wrap:wrap">` +
    `<input id="tool-override-st" class="cmd-input" placeholder="A1" title="Subtask name" style="width:50px">` +
    `<input id="tool-override-tools" class="cmd-input-wide" placeholder="Read,Glob,Grep" title="Comma-separated tool names">` +
    `<button class="cmd-btn btn-tools" onclick="submitToolOverride()">⚙ Set</button>` +
    `</div>` +
    `<span class="feedback" id="fb-tool-override"></span>` +
    `</div>`;
  el.innerHTML = html;
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
    el.innerHTML = `<div class="detail-placeholder">No priority data.</div>`;
    return;
  }
  let html = `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">${d.count} candidates · step ${d.step}</div>`;
  if (d.queue.length === 0) {
    html += `<div class="detail-placeholder">All subtasks Verified or blocked.</div>`;
  } else {
    d.queue.forEach((c, i) => {
      const col = c.status === "Running" ? "var(--cyan)" : "var(--dim)";
      const marker = i < 6 ? "▶ " : "  ";
      const barW = 80;
      const maxRisk = d.queue[0].risk || 1;
      const fill = Math.round(barW * c.risk / maxRisk);
      html += `<div class="diff-entry" style="font-size:10px;display:flex;align-items:center;gap:4px">`;
      html += `<span style="color:var(--yellow);min-width:14px">${marker}</span>`;
      html += `<span style="color:var(--cyan);min-width:32px">${esc(c.subtask)}</span>`;
      html += `<span style="color:${col};min-width:52px">${esc(c.status)}</span>`;
      html += `<span style="min-width:40px;color:var(--yellow)">r=${c.risk}</span>`;
      html += `<span style="flex:1;background:var(--surface);height:4px;border-radius:2px;position:relative">`;
      html += `<span style="position:absolute;left:0;top:0;height:4px;width:${fill}%;border-radius:2px;background:${c.status==="Running"?"var(--cyan)":"var(--yellow)"}"></span></span>`;
      html += `<span style="color:var(--dim);font-size:9px;min-width:60px;text-align:right">${esc(c.task)}</span>`;
      html += `</div>`;
    });
  }
  el.innerHTML = html;
}

/* ── Stalled panel ──────────────────────────────────────── */
export async function pollStalled() {
  try {
    const d = await api("/stalled");
    _renderStalled(d);
  } catch (_) {}
}

function _renderStalled(d) {
  const el = document.getElementById("stalled-content");
  if (!d) { el.innerHTML = `<div class="detail-placeholder">No data.</div>`; return; }
  let html = `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">threshold: ${d.threshold} steps · step ${d.step}</div>`;
  if (!d.stalled || d.stalled.length === 0) {
    html += `<div class="detail-placeholder" style="color:var(--green)">No stalled subtasks.</div>`;
  } else {
    d.stalled.forEach(s => {
      const pct = Math.min(100, Math.round(s.age / (d.threshold * 3) * 100));
      html += `<div class="diff-entry" style="font-size:10px;display:flex;align-items:center;gap:4px">`;
      html += `<span style="color:var(--yellow);min-width:32px">${esc(s.subtask)}</span>`;
      html += `<span style="color:var(--red);min-width:50px">${s.age} steps</span>`;
      html += `<span style="flex:1;background:var(--surface);height:4px;border-radius:2px;position:relative">`;
      html += `<span style="position:absolute;left:0;top:0;height:4px;width:${pct}%;border-radius:2px;background:var(--red)"></span></span>`;
      html += `<span style="color:var(--dim);font-size:9px;min-width:60px;text-align:right">${esc(s.task)}</span>`;
      html += `<button onclick="healSubtask(${JSON.stringify(s.subtask)})" style="background:var(--surface);color:var(--cyan);border:1px solid var(--border);border-radius:3px;font-size:9px;padding:0 4px;cursor:pointer" title="Reset to Pending">↻</button>`;
      html += `</div>`;
    });
  }
  el.innerHTML = html;
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

export async function pollSubtasks() {
  try {
    const d = await api("/subtasks");
    _subtasksAll = d.subtasks || [];
    _renderSubtasks();
  } catch (_) {}
}

window.renderSubtasks = function () { _renderSubtasks(); };

function _renderSubtasks() {
  const el = document.getElementById("subtasks-content");
  if (!el) return;
  const q = (document.getElementById("subtasks-filter")?.value || "").trim().toLowerCase();
  const rows = q
    ? _subtasksAll.filter(s =>
        s.subtask.toLowerCase().includes(q) ||
        s.status.toLowerCase().includes(q) ||
        s.branch.toLowerCase().includes(q) ||
        s.task.toLowerCase().includes(q))
    : _subtasksAll;
  if (rows.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">${q ? "No matching subtasks." : "No subtasks yet."}</div>`;
    return;
  }
  const statusColor = s => ({Verified:"var(--green)",Running:"var(--cyan)",Review:"var(--yellow)",Pending:"var(--dim)"})[s]||"var(--text)";
  let html = `<div style="color:var(--dim);font-size:10px;margin-bottom:4px">${rows.length} subtask${rows.length!==1?"s":""}</div>`;
  rows.forEach(s => {
    const ev = {subtask:s.subtask,task:s.task,branch:s.branch,status:s.status,step:"—",output:""};
    html += `<div class="diff-entry" style="cursor:pointer;display:flex;align-items:center;gap:6px" onclick='openSubtaskModal(${JSON.stringify(ev)})' title="Click for detail">`;
    html += `<span class="diff-st" style="min-width:30px">${esc(s.subtask)}</span>`;
    html += `<span style="color:${statusColor(s.status)};min-width:60px;font-size:10px">${esc(s.status)}</span>`;
    html += `<span style="color:var(--dim);font-size:9px;min-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.branch)}</span>`;
    html += `<span style="color:var(--dim);font-size:9px">${s.output_length}b</span>`;
    html += `</div>`;
  });
  el.innerHTML = html;
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
  if (!d) { el.innerHTML = `<div class="detail-placeholder">No data.</div>`; return; }
  const f = d.forecast || {};
  const pct = f.pct || 0;
  const barW = 120, fillW = Math.round(barW * pct / 100);
  let html = `<div style="color:var(--dim);font-size:10px;margin-bottom:8px">step ${d.step}</div>`;
  html += `<div style="margin-bottom:8px"><svg width="${barW+4}" height="14"><rect x="1" y="1" width="${barW}" height="12" rx="3" fill="var(--surface)"/><rect x="1" y="1" width="${fillW}" height="12" rx="3" fill="var(--cyan)"/><text x="${barW/2}" y="10" text-anchor="middle" font-size="8" fill="var(--text)">${pct}% (${f.verified}/${f.total})</text></svg></div>`;
  const cards = [
    {label:"Planner",      val:`cache interval: ${d.planner?.cache_interval || 5} steps`},
    {label:"Executor",     val:`max/step: ${d.executor?.max_per_step || 6}`},
    {label:"SelfHealer",   val:`healed: ${d.healer?.healed_total || 0}  stalled: ${d.healer?.currently_stalled || 0}  threshold: ${d.healer?.threshold || 5}`},
    {label:"MetaOptimizer",val:`history: ${d.meta?.history_len || 0}  heal: ${d.meta?.heal_rate?.toFixed(2) || "0.00"}/step  verify: ${d.meta?.verify_rate?.toFixed(2) || "0.00"}/step`},
    {label:"Forecast",     val:`${f.remaining || 0} remaining` + (f.eta_steps ? `  ETA: ~${f.eta_steps} steps` : "")},
  ];
  cards.forEach(c => {
    html += `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:80px;display:inline-block">${c.label}</span> <span style="color:var(--dim)">${c.val}</span></div>`;
  });
  el.innerHTML = html;
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
    el.innerHTML =
      `<div style="margin-bottom:8px"><svg width="${barW+4}" height="14"><rect x="1" y="1" width="${barW}" height="12" rx="3" fill="var(--surface)"/><rect x="1" y="1" width="${fillW}" height="12" rx="3" fill="var(--green)"/><text x="${barW/2}" y="10" text-anchor="middle" font-size="8" fill="var(--text)">${pct}%</text></svg></div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:80px;display:inline-block">Completion</span> <strong>${pct}%</strong></div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:80px;display:inline-block">Rate</span> ${rate} verified/step</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:80px;display:inline-block">ETA</span> ${eta}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:80px;display:inline-block">Verified</span> ${d.verified ?? "—"} / ${d.total ?? "—"}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:80px;display:inline-block">Stalled</span> ${d.stalled_count ?? 0}</div>`;
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
    let sparkline = "";
    if (hist.length > 1) {
      const maxV = Math.max(1, ...hist.map(r => r.verified));
      const pts = hist.map((r, i) => {
        const x = pad + (i / (hist.length - 1)) * (W - 2 * pad);
        const y = H - pad - (r.verified / maxV) * (H - 2 * pad);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
      sparkline = `<svg width="${W}" height="${H}" style="display:block;margin:6px 0">` +
        `<polyline points="${pts}" fill="none" stroke="var(--cyan)" stroke-width="1.5"/>` +
        `<text x="2" y="${H-1}" font-size="8" fill="var(--dim)">${hist[0].step_index}</text>` +
        `<text x="${W-2}" y="${H-1}" font-size="8" fill="var(--dim)" text-anchor="end">${hist[hist.length-1].step_index}</text>` +
        `</svg>`;
    } else {
      sparkline = `<div class="detail-placeholder" style="font-size:10px">Not enough data yet (run more steps).</div>`;
    }
    const elapsedStr = d.elapsed_s != null ? `${d.elapsed_s}s` : "—";
    const rateStr    = d.steps_per_min != null ? `${d.steps_per_min}/min` : "—";
    el.innerHTML =
      `<div style="font-size:10px;color:var(--dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Run health</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Verified</span> ${d.verified ?? "—"} / ${d.total ?? "—"} (${d.pct ?? 0}%)</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Pending</span> ${d.pending ?? "—"}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Running</span> ${d.running ?? "—"}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Review</span> ${d.review ?? 0}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:${(d.stalled??0)>0?"var(--yellow)":"var(--cyan)"};min-width:110px;display:inline-block">Stalled</span> ${d.stalled ?? 0}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Elapsed</span> ${elapsedStr}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Step rate</span> ${rateStr}</div>` +
      `<div style="font-size:10px;color:var(--dim);margin:8px 0 4px;text-transform:uppercase;letter-spacing:1px">Analytics</div>` +
      `<div style="font-size:10px;color:var(--dim);margin-bottom:2px">Verified/step over time:</div>${sparkline}` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Total steps</span> ${s.total_steps ?? "—"}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Total verifies</span> ${s.total_verifies ?? "—"}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Avg rate</span> ${s.avg_verified_per_step ?? "—"} v/step</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Peak rate</span> ${s.peak_verified_per_step ?? "—"} v/step</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Steps w/ heals</span> ${s.steps_with_heals ?? 0}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:110px;display:inline-block">Total healed</span> ${d.total_healed ?? 0}</div>` +
      `<div style="margin-top:8px;display:flex;gap:6px"><a class="toolbar-btn" href="/metrics/export" download="metrics.csv">Download CSV</a><a class="toolbar-btn" href="/metrics/export?format=json" download="metrics.json">Download JSON</a></div>`;
  } catch (_) {}
}

/* ── Cache panel ─────────────────────────────────────────── */
export async function pollCache() {
  try {
    const d = await api("/cache");
    const el = document.getElementById("cache-content");
    if (!el) return;
    const entries   = d.entries ?? 0;
    const tokens    = d.estimated_tokens_held ?? 0;
    const dir       = d.cache_dir ?? "—";
    const cumHits   = d.cumulative_hits ?? 0;
    const cumMisses = d.cumulative_misses ?? 0;
    const hitRate   = d.cumulative_hit_rate != null ? d.cumulative_hit_rate.toFixed(1) + "%" : "—";
    el.innerHTML =
      `<div style="font-size:10px;color:var(--dim);margin-bottom:4px">This session:</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Entries on disk</span> ${entries}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Est. tokens held</span> ${tokens.toLocaleString()}</div>` +
      `<div style="font-size:10px;color:var(--dim);margin:6px 0 4px">All sessions:</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Cumulative hits</span> ${cumHits.toLocaleString()}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Cumulative misses</span> ${cumMisses.toLocaleString()}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Hit rate</span> ${hitRate}</div>` +
      `<div class="diff-entry" style="font-size:10px;word-break:break-all"><span style="color:var(--cyan);min-width:130px;display:inline-block">Cache dir</span> <span style="color:var(--dim)">${esc(dir)}</span></div>` +
      `<div style="margin-top:8px"><button class="toolbar-btn" onclick="clearCache()">Clear Cache</button></div>`;
  } catch (_) {}
}

window.clearCache = async function () {
  try {
    await fetch("/cache", { method: "DELETE" });
    await pollCache();
  } catch (_) {}
};

/* ── Cache history panel (incremental) ───────────────────── */
let _cacheHistoryLastSession  = 0;
let _cacheHistoryAllSessions  = [];
let _cacheHistoryCumHits      = 0;
let _cacheHistoryCumMisses    = 0;

export async function pollCacheHistory() {
  try {
    const url = _cacheHistoryLastSession > 0
      ? `/cache/history?since=${_cacheHistoryLastSession}`
      : `/cache/history`;
    const d = await api(url);
    const el = document.getElementById("cache-history-content");
    if (!el) return;
    (d.sessions || []).forEach(s => {
      if (s.session > _cacheHistoryLastSession) {
        _cacheHistoryAllSessions.push(s);
        _cacheHistoryLastSession = s.session;
      }
    });
    _cacheHistoryCumHits   = d.cumulative_hits   ?? _cacheHistoryCumHits;
    _cacheHistoryCumMisses = d.cumulative_misses  ?? _cacheHistoryCumMisses;
    _renderCacheHistory();
  } catch (_) {}
}

function _renderCacheHistory() {
  const el = document.getElementById("cache-history-content");
  if (!el) return;
  const limitSel = document.getElementById("cache-history-limit");
  const limitN   = limitSel ? parseInt(limitSel.value, 10) : 10;
  const cumHits   = _cacheHistoryCumHits;
  const cumMisses = _cacheHistoryCumMisses;
  const cumTotal  = cumHits + cumMisses;
  const cumRate   = cumTotal > 0 ? (cumHits / cumTotal * 100).toFixed(1) + "%" : "—";
  if (_cacheHistoryAllSessions.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">No session history yet.<br>Stats accumulate after each CLI run.</div>`;
    return;
  }
  const pool = limitN > 0 ? _cacheHistoryAllSessions.slice(-limitN) : _cacheHistoryAllSessions;
  const rows = pool.slice().reverse().map(s => {
    const rate  = s.hit_rate != null ? s.hit_rate.toFixed(1) + "%" : "—";
    const ended = s.ended_at ? s.ended_at.replace("T", " ").substring(0, 19) + "Z" : "—";
    return `<div class="diff-entry" style="font-size:10px">` +
      `<span style="color:var(--cyan);min-width:24px;display:inline-block">#${s.session}</span>` +
      `<span style="min-width:48px;display:inline-block">${s.hits}H ${s.misses}M</span>` +
      `<span style="min-width:48px;display:inline-block">${rate}</span>` +
      `<span style="color:var(--dim);font-size:9px">${esc(ended)}</span>` +
      `</div>`;
  }).join("");
  el.innerHTML =
    `<div style="font-size:10px;color:var(--dim);margin-bottom:4px">Sessions (newest first):</div>` +
    rows +
    `<div style="font-size:10px;color:var(--dim);margin-top:6px">All-time: ${cumHits.toLocaleString()}H ${cumMisses.toLocaleString()}M ${cumRate}</div>`;
}
