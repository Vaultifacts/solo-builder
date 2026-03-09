import { state } from "./dashboard_state.js";
import { api, esc } from "./dashboard_utils.js";

/* ── DOM helpers ─────────────────────────────────────────── */
function _div(cssText, cls) {
  const el = document.createElement("div");
  if (cssText) el.style.cssText = cssText;
  if (cls)    el.className = cls;
  return el;
}

function _span(cssText, text) {
  const el = document.createElement("span");
  if (cssText) el.style.cssText = cssText;
  el.textContent = text;
  return el;
}

function _bar(widthPx, totalPx, height, bg, fill) {
  const track = _div(`width:${totalPx}px;height:${height}px;background:${bg};border-radius:${Math.ceil(height/2)}px;flex-shrink:0`);
  const fg    = _div(`width:${widthPx}px;height:${height}px;background:${fill};border-radius:${Math.ceil(height/2)}px`);
  track.appendChild(fg);
  return track;
}

/* ── Branches pagination + filter state (all-tasks view) ─── */
let _branchesPage         = 1;
let _branchesPages        = 1;
let _branchesTotal        = 0;
let _branchesStatusFilter = "";   // "" = all; "pending"|"running"|"review"|"verified"
let _branchesTaskFilter   = "";   // "" = all; substring matched against task name
let _branchesLastData     = null;
let _branchesLastSummary  = null;
const _BRANCHES_LIMIT     = 50;

function _updateBranchesPager() {
  const pager = document.getElementById("branches-pager");
  const lbl   = document.getElementById("branches-page-label");
  const cnt   = document.getElementById("branches-count-label");
  if (!pager) return;
  if (_branchesPages > 1) {
    pager.style.display = "flex";
    if (lbl) lbl.textContent = `${_branchesPage} / ${_branchesPages}`;
    if (cnt) cnt.textContent = `${_branchesTotal} branches`;
  } else {
    pager.style.display = "none";
  }
}

window._branchesPageStep = function (delta) {
  if (state.selectedTask) return; // pager only in all-tasks view
  const next = _branchesPage + delta;
  if (next < 1 || next > _branchesPages) return;
  _branchesPage = next;
  pollBranches();
};

window._branchesFilterStatus = function (status) {
  if (state.selectedTask) return; // filter only in all-tasks view
  _branchesStatusFilter = _branchesStatusFilter === status ? "" : status;
  _branchesPage = 1;
  pollBranches();
};

window._applyBranchesTaskFilter = function () {
  if (state.selectedTask) return; // only in all-tasks view
  const v = (document.getElementById("branches-task-filter")?.value || "").trim().toLowerCase();
  if (v === _branchesTaskFilter) return;
  _branchesTaskFilter = v;
  _branchesPage = 1;
  pollBranches();
};

window._clearBranchesFilters = function () {
  const hadFilter = _branchesStatusFilter || _branchesTaskFilter;
  _branchesStatusFilter = "";
  _branchesTaskFilter   = "";
  _branchesPage = 1;
  const tf = document.getElementById("branches-task-filter");
  if (tf) tf.value = "";
  _updateBranchesExportLinks();
  if (hadFilter) pollBranches();
};

function _getBranchesFiltered() {
  const branches = (_branchesLastData && _branchesLastData.branches) || [];
  const f = _branchesStatusFilter;
  if (!f) return branches;
  return branches.filter(br => {
    if (f === "verified") return br.verified === br.total && br.total > 0;
    if (f === "running")  return br.running  > 0;
    if (f === "review")   return br.review   > 0;
    if (f === "pending")  return br.pending  > 0;
    return true;
  });
}

function _triggerDownload(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

function _updateBranchesExportLinks() {
  const csv  = document.getElementById("branches-export-csv");
  const json = document.getElementById("branches-export-json");
  if (!csv || !json) return;
  let qs = _branchesStatusFilter ? `?status=${encodeURIComponent(_branchesStatusFilter)}` : "";
  if (_branchesTaskFilter) qs += (qs ? "&" : "?") + `task=${encodeURIComponent(_branchesTaskFilter)}`;
  csv.href  = `/branches/export${qs}`;
  json.href = `/branches/export${qs ? qs + "&format=json" : "?format=json"}`;
}

window._downloadBranchesCSV = function () {
  const rows = _getBranchesFiltered();
  const header = "task,branch,total,verified,running,review,pending,pct";
  const lines = rows.map(b =>
    [b.task, b.branch, b.total, b.verified, b.running, b.review ?? 0, b.pending, b.pct]
      .map(v => JSON.stringify(String(v))).join(","));
  _triggerDownload(new Blob([header + "\n" + lines.join("\n")], {type: "text/csv"}), "branches.csv");
};

window._downloadBranchesJSON = function () {
  const rows = _getBranchesFiltered();
  _triggerDownload(new Blob([JSON.stringify({branches: rows}, null, 2)], {type: "application/json"}), "branches.json");
};

/* ── Branches bulk-select state ─────────────────────────── */
const _branchesSel = new Set();

function _updateBranchesBulkBar() {
  const bar = document.getElementById("branches-bulk-bar");
  const cnt = document.getElementById("branches-sel-count");
  if (!bar) return;
  const n = _branchesSel.size;
  bar.style.display = n > 0 ? "flex" : "none";
  if (cnt) cnt.textContent = `${n} selected`;
}

window.branchesClearSel = function () {
  _branchesSel.clear();
  document.querySelectorAll("#branches-content input[type=checkbox]").forEach(c => { c.checked = false; });
  _updateBranchesBulkBar();
};

window.branchesBulkReset = async function () {
  if (!_branchesSel.size) return;
  const fb = document.getElementById("fb-branches-bulk");
  try {
    const d = await fetch(state.base + "/subtasks/bulk-reset", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({subtasks: [..._branchesSel]}),
    }).then(r => r.json());
    if (fb) { fb.textContent = `Reset ${d.reset_count ?? 0}`; setTimeout(() => { fb.textContent = ""; }, 3000); }
  } catch (_) {}
  _branchesSel.clear();
  await pollBranches();
};

window.branchesBulkVerify = async function () {
  if (!_branchesSel.size) return;
  const fb = document.getElementById("fb-branches-bulk");
  try {
    const d = await fetch(state.base + "/subtasks/bulk-verify", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({subtasks: [..._branchesSel]}),
    }).then(r => r.json());
    if (fb) { fb.textContent = `Verified ${d.verified_count ?? 0}`; setTimeout(() => { fb.textContent = ""; }, 3000); }
  } catch (_) {}
  _branchesSel.clear();
  await pollBranches();
};

export async function pollBranches() {
  try {
    if (state.selectedTask) {
      const d = await api("/branches/" + encodeURIComponent(state.selectedTask));
      _updateBranchesPager(); // hide pager in detail view
      _renderBranchesDetail(d);
    } else {
      let branchUrl = `/branches?limit=${_BRANCHES_LIMIT}&page=${_branchesPage}`;
      if (_branchesStatusFilter) branchUrl += `&status=${encodeURIComponent(_branchesStatusFilter)}`;
      if (_branchesTaskFilter)   branchUrl += `&task=${encodeURIComponent(_branchesTaskFilter)}`;
      const [d, summary] = await Promise.all([
        api(branchUrl),
        api("/dag/summary").catch(() => null),
      ]);
      _branchesTotal      = d.total  ?? (d.branches || []).length;
      _branchesPages      = d.pages  ?? 1;
      _branchesPage       = d.page   ?? 1;
      _branchesLastData    = d;
      _branchesLastSummary = summary;
      _renderBranchesAll(d, summary);
    }
  } catch (_) {}
}

function _renderBranchesAll(d, summary) {
  const el = document.getElementById("branches-content");
  // bulk bar only applies to detail view; hide it in all-tasks view
  _branchesSel.clear();
  _updateBranchesBulkBar();
  _updateBranchesExportLinks();

  // Show quick-filter buttons only when no task selected
  const filterBar    = document.getElementById("branches-status-filters");
  const filterLbl    = document.getElementById("branches-filter-label");
  const taskFilterRow = document.getElementById("branches-task-row");
  if (filterBar)     filterBar.style.display = "flex";
  if (taskFilterRow) taskFilterRow.style.display = "flex";

  // Server already applied status filter; just render what came back
  const f = _branchesStatusFilter;
  const branches = d.branches || [];
  const hasFilter = !!(f || _branchesTaskFilter);
  if (filterLbl) filterLbl.textContent = f ? `· ${f} filter (${branches.length})` : "";
  const clearBtn = document.getElementById("branches-clear-filters");
  if (clearBtn) clearBtn.style.display = hasFilter ? "" : "none";

  if (branches.length === 0) {
    const ph = _div(null, "detail-placeholder");
    ph.textContent = f ? `No branches with ${f} subtasks.` : "No branches yet.";
    el.replaceChildren(ph);
    _updateBranchesPager();
    return;
  }

  const children = [];

  // ── Pipeline Overview ─────────────────────────────────────
  if (summary && summary.total > 0) {
    const card = _div("margin-bottom:10px;padding:6px 8px;background:var(--bg2);border-radius:4px;border:1px solid var(--border)");

    const title = _div("font-size:10px;color:var(--cyan);font-weight:bold;margin-bottom:4px");
    title.textContent = "Pipeline Overview — Step " + summary.step;
    card.appendChild(title);

    const ovW = 120;
    const ovFill = Math.round(summary.pct * ovW / 100);
    const barRow = _div("display:flex;align-items:center;gap:8px;margin-bottom:4px");
    barRow.appendChild(_bar(ovFill, ovW, 8, "var(--bg3)", "var(--green)"));
    barRow.appendChild(_span("font-size:11px;color:var(--text)", summary.verified + "/" + summary.total + " (" + summary.pct + "%)"));
    card.appendChild(barRow);

    const counts = _div("font-size:10px;color:var(--dim)");
    counts.textContent = summary.running + " running · " + summary.pending + " pending";
    card.appendChild(counts);

    if (summary.tasks && summary.tasks.length > 0) {
      const taskList = _div("margin-top:6px");
      summary.tasks.forEach(t => {
        const tw = Math.round(t.pct * 60 / 100);
        const row = _div("display:flex;align-items:center;gap:6px;margin-top:3px");
        row.appendChild(_span("color:var(--dim);font-size:10px;min-width:48px;flex-shrink:0", t.id));
        row.appendChild(_bar(tw, 60, 4, "var(--bg3)", "var(--green)"));
        row.appendChild(_span("font-size:10px;color:var(--dim)", t.verified + "/" + t.subtasks + " (" + t.pct + "%)"));
        taskList.appendChild(row);
      });
      card.appendChild(taskList);
    }
    children.push(card);
  }

  const countHdr = _div("color:var(--dim);font-size:10px;margin-bottom:6px");
  countHdr.textContent = (_branchesTotal || d.count) + " branches across all tasks";
  children.push(countHdr);

  const barW = 60;
  branches.forEach(br => {
    const w = Math.round(br.pct * barW / 100);
    const row = _div("cursor:pointer;display:flex;align-items:center;gap:8px", "diff-entry");
    row.title = "Click to select task";
    row.addEventListener("click", () => window.selectTask(br.task));
    row.appendChild(_span("color:var(--dim);font-size:10px;min-width:60px;flex-shrink:0", br.task));
    row.appendChild(_span("color:var(--cyan);min-width:80px;flex-shrink:0", br.branch));
    row.appendChild(_bar(w, barW, 6, "var(--bg2)", "var(--green)"));
    row.appendChild(_span("color:var(--dim);font-size:10px", br.verified + "/" + br.total));
    if (br.running > 0) {
      row.appendChild(_span("font-size:10px;color:var(--cyan)", br.running + "▶"));
    }
    if (br.review > 0) {
      row.appendChild(_span("font-size:10px;color:var(--yellow)", br.review + "⏸"));
    }
    children.push(row);
  });

  el.replaceChildren(...children);
  _updateBranchesPager();
}

function _renderBranchesDetail(d) {
  const el = document.getElementById("branches-content");
  if (!d.branches || d.branches.length === 0) {
    _branchesSel.clear();
    _updateBranchesBulkBar();
    const ph = _div(null, "detail-placeholder");
    ph.textContent = "No branches.";
    el.replaceChildren(ph);
    return;
  }
  const statusColor = s => ({Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"})[s] || "var(--text)";

  const hdr = _div("color:var(--dim);font-size:10px;margin-bottom:6px");
  hdr.textContent = d.task + " — " + d.branch_count + " branches";

  const children = [hdr];
  d.branches.forEach(br => {
    const block = _div("margin-bottom:8px");

    const brHdr = _div("display:flex;align-items:center;gap:4px;flex-wrap:wrap");
    const nameSpan = _span("color:var(--cyan);font-weight:bold", br.branch);
    const stCount  = _span("color:var(--dim);font-size:10px", " " + br.subtask_count + " STs");
    const vSpan    = _span("font-size:10px;color:var(--green)", " " + br.verified + "✓");
    const rSpan    = _span("font-size:10px;color:var(--cyan)", " " + br.running + "▶");
    const pSpan    = _span("font-size:10px;color:var(--yellow)", " " + br.pending + "●");

    // Inline pct mini-bar (data already available from /branches/<task>)
    const pct = br.subtask_count > 0 ? Math.round(br.verified / br.subtask_count * 100) : 0;
    const miniTrack = _div("width:40px;height:4px;background:var(--bg3);border-radius:2px;flex-shrink:0");
    const miniFill  = _div(`width:${Math.round(pct * 40 / 100)}px;height:4px;background:var(--green);border-radius:2px`);
    miniTrack.appendChild(miniFill);
    const pctSpan = _span("font-size:9px;color:var(--dim)", pct + "%");

    const resetBtn = document.createElement("button");
    resetBtn.className = "toolbar-btn";
    resetBtn.style.cssText = "font-size:8px;padding:1px 4px;margin-left:4px";
    resetBtn.textContent = "↺ Reset";
    resetBtn.title = "Reset all non-Verified subtasks in this branch to Pending";
    resetBtn.addEventListener("click", async () => {
      const names = (br.subtasks || []).filter(s => s.status !== "Verified").map(s => s.name);
      if (!names.length) return;
      try {
        await fetch(state.base + "/subtasks/bulk-reset", {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({subtasks: names}),
        });
      } catch (_) {}
      await pollBranches();
    });
    brHdr.append(nameSpan, stCount, vSpan, rSpan, pSpan, miniTrack, pctSpan, resetBtn);
    block.appendChild(brHdr);

    br.subtasks.forEach(st => {
      const stRow = _div("padding-left:12px;display:flex;align-items:center;gap:4px", "diff-entry");
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.style.cssText = "width:10px;height:10px;cursor:pointer;flex-shrink:0";
      chk.checked = _branchesSel.has(st.name);
      chk.addEventListener("change", () => {
        if (chk.checked) _branchesSel.add(st.name);
        else _branchesSel.delete(st.name);
        _updateBranchesBulkBar();
      });
      const stName = _span(null);
      stName.className = "diff-st";
      stName.textContent = st.name;
      const stStatus = _span("color:" + statusColor(st.status), st.status);
      stRow.appendChild(chk);
      stRow.appendChild(stName);
      stRow.appendChild(document.createTextNode(" "));
      stRow.appendChild(stStatus);
      block.appendChild(stRow);
    });
    children.push(block);
  });

  el.replaceChildren(...children);
  _updateBranchesBulkBar();
  // pager, status filter bar, and task filter row only shown in all-tasks view
  const pager = document.getElementById("branches-pager");
  if (pager) pager.style.display = "none";
  const filterBar = document.getElementById("branches-status-filters");
  if (filterBar) filterBar.style.display = "none";
  const taskFilterRow = document.getElementById("branches-task-row");
  if (taskFilterRow) taskFilterRow.style.display = "none";
}
