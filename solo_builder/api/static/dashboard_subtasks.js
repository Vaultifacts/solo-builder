import { state } from "./dashboard_state.js";
import { api, STATUS_COL, placeholder } from "./dashboard_utils.js";

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

export function updateSubtasksExportLinks() {
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
  updateSubtasksExportLinks();
  pollSubtasks();
};

window._applySubtasksBranchFilter = function () {
  const v = (document.getElementById("subtasks-branch-filter")?.value || "").trim().toLowerCase();
  if (v === _subtasksBranchFilter) return;
  _subtasksBranchFilter = v;
  _subtasksPage = 1;
  updateSubtasksExportLinks();
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
  updateSubtasksExportLinks();
};

window._clearSubtasksFilters = function () {
  const hadFilter = _subtasksStatusFilter || _subtasksNameFilter || _subtasksTaskFilter || _subtasksBranchFilter;
  window._resetSubtasksFilters();
  if (hadFilter) pollSubtasks();
};

window.renderSubtasks = function () {
  const q  = (document.getElementById("subtasks-filter")?.value || "").trim();
  const ql = q.toLowerCase();
  const params = new URLSearchParams(location.hash.slice(1));
  if (q) { params.set("st-filter", q); } else { params.delete("st-filter"); }
  const next = params.toString();
  history.replaceState(null, "", next ? "#" + next : location.pathname + location.search);

  if (_SUBTASKS_STATUS_VALS.has(ql)) {
    _subtasksStatusFilter = ql;
    _subtasksNameFilter   = "";
    _subtasksPage = 1;
    updateSubtasksExportLinks();
    pollSubtasks();
  } else if (q) {
    _subtasksNameFilter   = ql;
    _subtasksStatusFilter = "";
    _subtasksPage = 1;
    updateSubtasksExportLinks();
    pollSubtasks();
  } else {
    const hadFilter = _subtasksStatusFilter || _subtasksNameFilter;
    _subtasksStatusFilter = "";
    _subtasksNameFilter   = "";
    _subtasksPage = 1;
    updateSubtasksExportLinks();
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
    _fbSet(fb, d.ok ? `\u21ba ${d.reset_count} reset` : (d.reason || "Error"));
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
    _fbSet(fb, d.ok ? `\u2714 ${d.verified_count} verified` : (d.reason || "Error"));
    _subtasksSel.clear();
    await pollSubtasks();
  } catch (_) { _fbSet(fb, "Network error"); }
};

function _renderSubtasks() {
  const el = document.getElementById("subtasks-content");
  if (!el) return;
  const rows = _subtasksAll;
  const hasFilter = _subtasksStatusFilter || _subtasksNameFilter || _subtasksTaskFilter || _subtasksBranchFilter;
  const filterLbl = document.getElementById("subtasks-filter-label");
  if (filterLbl) {
    const parts = [];
    if (_subtasksStatusFilter) parts.push(_subtasksStatusFilter);
    if (_subtasksNameFilter)   parts.push(`"${_subtasksNameFilter}"`);
    if (_subtasksTaskFilter)   parts.push(`task:${_subtasksTaskFilter}`);
    if (_subtasksBranchFilter) parts.push(`branch:${_subtasksBranchFilter}`);
    filterLbl.textContent = parts.length ? `\u00b7 ${parts.join(" ")} (${rows.length})` : "";
  }
  const clearBtn = document.getElementById("subtasks-clear-filters");
  if (clearBtn) clearBtn.style.display = hasFilter ? "" : "none";
  if (rows.length === 0) {
    el.replaceChildren(placeholder(hasFilter ? "No matching subtasks." : "No subtasks yet."));
    return;
  }
  const counter = document.createElement("div");
  counter.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:4px";
  counter.textContent = `${rows.length} subtask${rows.length !== 1 ? "s" : ""}`;
  const nodes = [counter];
  rows.forEach(s => {
    const ev = {subtask: s.subtask, task: s.task, branch: s.branch, status: s.status, step: "\u2014", output: ""};
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
    statusEl.style.cssText = `color:${STATUS_COL[s.status] || "var(--text)"};min-width:60px;font-size:10px`;
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
