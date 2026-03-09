import { state } from "./dashboard_state.js";
import { api, statusClass, dotClass, toast, updateNotifBadge, checkStaleBanner, playCompletionSound } from "./dashboard_utils.js";
export { pollJournal, pollDiff, pollStats } from "./dashboard_journal.js";

const _TASKS_LIMIT    = 50;
let _tasksPage        = 1;
let _tasksSearchFilter = "";

function _updateTasksPager() {
  const pager = document.getElementById("tasks-pager");
  const lbl   = document.getElementById("tasks-page-label");
  if (!pager) return;
  if ((state.taskPages ?? 1) > 1) {
    pager.style.display = "flex";
    if (lbl) lbl.textContent = `${_tasksPage} / ${state.taskPages}`;
  } else {
    pager.style.display = "none";
  }
}

window._tasksPageStep = function (delta) {
  const next = _tasksPage + delta;
  if (next < 1 || next > (state.taskPages ?? 1)) return;
  _tasksPage = next;
  pollTasks();
};

window.addEventListener("focus", function () {
  state.tabFocused = true;
  updateNotifBadge(state.prevStep);
});
window.addEventListener("blur", function () { state.tabFocused = false; });

/* ── Header / status ─────────────────────────────────────── */
export async function pollStatus() {
  try {
    const t0 = performance.now();
    const d = await api("/status");
    const latencyMs = Math.round(performance.now() - t0);
    state.lastStatusOk = Date.now();
    checkStaleBanner();
    const stepEl = document.getElementById("hdr-step");
    if (stepEl) stepEl.title = `Poll latency: ${latencyMs}ms`;
    document.getElementById("hdr-verified").textContent = d.verified;
    document.getElementById("hdr-running").textContent  = d.running;
    document.getElementById("hdr-pending").textContent  = d.pending;
    const reviewEl = document.getElementById("hdr-review");
    if (reviewEl) { reviewEl.textContent = d.review > 0 ? `⏸${d.review}` : ""; reviewEl.style.display = d.review > 0 ? "" : "none"; }
    document.getElementById("hdr-total").textContent    = d.total;
    document.getElementById("hdr-bar").style.width      = d.pct + "%";
    document.getElementById("hdr-pct").textContent      = d.pct + "%";
    document.getElementById("hdr-step").textContent     = `Step ${d.step} / ${d.total} — ${d.verified} verified` + (d.review > 0 ? ` · ${d.review}⏸` : "");
    if (d.step > state.prevStep) {
      const delta = (d.verified - state.prevVerified) / (d.step - state.prevStep);
      state.rateEma = state.rateEma === null ? delta : 0.3 * delta + 0.7 * state.rateEma;
      state.prevVerified = d.verified;
      state.prevStep     = d.step;
    }
    updateNotifBadge(d.step);
    document.getElementById("hdr-rate").textContent =
      state.rateEma !== null ? state.rateEma.toFixed(1) : "—";
    document.title = d.complete
      ? "Solo Builder ✓ Complete"
      : `Solo Builder — Step ${d.step} (${d.pct}%)`;

    const badge = document.getElementById("hdr-badge");
    if (d.complete && badge.textContent !== "Complete") {
      playCompletionSound();
      fetch(state.base + "/webhook", {method: "POST"}).then(r => r.json()).then(wd => {
        if (wd.ok) toast("Pipeline complete — webhook fired");
      }).catch(() => {});
    }
    if (d.complete) {
      badge.textContent  = "Complete";
      badge.className    = "status-badge badge-complete";
    } else if (d.running > 0) {
      badge.textContent  = "Running";
      badge.className    = "status-badge badge-running";
    } else {
      badge.textContent  = "Idle";
      badge.className    = "status-badge badge-pending";
    }
    if (d.stalled > 0 && d.stalled_by_branch && d.stalled_by_branch.length > 0) {
      const w = d.stalled_by_branch[0];
      badge.title = `${d.stalled} stalled — worst: ${w.task}/${w.branch} (${w.count})`;
    } else {
      badge.title = "";
    }
    _updateFavicon(d);
  } catch (e) {
    checkStaleBanner();
  }
}

function _updateFavicon(d) {
  const color = d.complete      ? "%2322c55e"
              : d.stalled > 0   ? "%23eab308"
              : d.running > 0   ? "%2306b6d4"
              : "%23555555";
  const svg = `%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='${color}'/%3E%3C/svg%3E`;
  const fav = document.getElementById("favicon");
  if (fav) fav.href = `data:image/svg+xml,${svg}`;
}

/* ── Task grid ───────────────────────────────────────────── */
export async function pollTasks() {
  try {
    let url = `/tasks?limit=${_TASKS_LIMIT}&page=${_tasksPage}`;
    if (_tasksSearchFilter) url += `&task=${encodeURIComponent(_tasksSearchFilter)}`;
    const d = await api(url);
    state.allTasks = d.tasks || [];
    state.taskTotal = d.total ?? state.allTasks.length;
    state.taskPages = d.pages ?? 1;
    _tasksPage = d.page ?? _tasksPage;
    const countEl = document.getElementById("tasks-count-lbl");
    if (countEl) {
      countEl.textContent = state.taskTotal > 0
        ? `(${state.taskTotal}${state.taskPages > 1 ? ` · p${_tasksPage}/${state.taskPages}` : ""})`
        : "";
    }
    _updateTasksPager();
    applyTaskSearch();
  } catch (e) {}
}

export function applyTaskSearch() {
  const q = (document.getElementById("task-search")?.value || "").trim().toLowerCase();
  const filtered = q
    ? state.allTasks.filter(t => t.id.toLowerCase().includes(q) || (t.status || "").toLowerCase().includes(q))
    : state.allTasks;
  renderGrid(filtered);
}

export function renderGrid(tasks) {
  state.taskIds = tasks.map(t => t.id);
  const grid = document.getElementById("task-grid");
  const existing = new Set([...grid.querySelectorAll(".task-card")].map(el => el.dataset.id));
  const incoming  = new Set(tasks.map(t => t.id));

  existing.forEach(id => { if (!incoming.has(id)) grid.querySelector(`[data-id="${CSS.escape(id)}"]`)?.remove(); });

  tasks.forEach(t => {
    let card = grid.querySelector(`[data-id="${CSS.escape(t.id)}"]`);
    const isBlocked = t.depends_on && t.depends_on.length > 0 && t.status === "Pending";
    if (!card) {
      card = document.createElement("div");
      card.className = "task-card";
      card.dataset.id = t.id;

      const cardTop = document.createElement("div");
      cardTop.className = "card-top";
      const cardIdSpan = document.createElement("span");
      cardIdSpan.className = "card-id";
      cardIdSpan.textContent = t.id;
      const cardBadge = document.createElement("span");
      cardBadge.className = `card-mini-badge ${statusClass(t.status)}`;
      cardBadge.textContent = t.status || "Pending";
      const cardReview = document.createElement("span");
      cardReview.className = "card-review-badge";
      cardReview.style.cssText = "font-size:9px;color:var(--yellow);display:none";
      cardTop.append(cardIdSpan, cardBadge, cardReview);

      const cardDeps = document.createElement("div");
      cardDeps.className = "card-deps";

      const barBg = document.createElement("div");
      barBg.className = "card-bar-bg";
      const barFg = document.createElement("div");
      barFg.className = "card-bar-fg";
      barFg.style.width = "0%";
      barBg.appendChild(barFg);

      const cardCounts = document.createElement("div");
      cardCounts.className = "card-counts";

      card.replaceChildren(cardTop, cardDeps, barBg, cardCounts);
      card.addEventListener("click", () => selectTask(t.id));
      grid.appendChild(card);
    }
    card.querySelector(".card-mini-badge").className = `card-mini-badge ${statusClass(t.status)}`;
    card.querySelector(".card-mini-badge").textContent = t.status || "Pending";
    const reviewBadge = card.querySelector(".card-review-badge");
    if (reviewBadge) {
      if (t.review_subtasks > 0) { reviewBadge.textContent = `⏸${t.review_subtasks}`; reviewBadge.style.display = ""; }
      else { reviewBadge.style.display = "none"; }
    }
    card.classList.toggle("active",  t.id === state.selectedTask);
    card.classList.toggle("blocked", isBlocked);

    const pct = t.pct != null ? Math.round(t.pct) : (t.subtask_count > 0 ? Math.round(t.verified_subtasks / t.subtask_count * 100) : 0);
    card.querySelector(".card-bar-fg").style.width = pct + "%";
    card.querySelector(".card-counts").textContent =
      `${t.verified_subtasks}/${t.subtask_count} verified` +
      (t.running_subtasks > 0 ? ` · ${t.running_subtasks}▶` : "") +
      (t.review_subtasks  > 0 ? ` · ${t.review_subtasks}⏸`  : "");

    const depEl = card.querySelector(".card-deps");
    if (t.depends_on && t.depends_on.length) {
      depEl.textContent = "← " + t.depends_on.join(", ");
    } else {
      depEl.textContent = "";
    }
  });
}

/* ── Detail panel ────────────────────────────────────────── */
export async function selectTask(id) {
  state.selectedTask = id;
  window._resetSubtasksFilters?.();
  document.querySelectorAll(".task-card").forEach(c => c.classList.toggle("active", c.dataset.id === id));
  _updateTaskExportLinks(id);
  try {
    const t = await api("/tasks/" + encodeURIComponent(id));
    state.tasksCache[id] = t;
    renderDetail(t);
  } catch (e) {
    toast("Could not load task detail: " + e.message);
  }
}

function _updateTaskExportLinks(id) {
  const section = document.getElementById("export-task-section");
  const csvLink  = document.getElementById("export-task-csv");
  const jsonLink = document.getElementById("export-task-json");
  if (!section || !csvLink || !jsonLink) return;
  const base = "/tasks/" + encodeURIComponent(id) + "/export";
  csvLink.href  = base;
  csvLink.download = "task_" + id.replace(/\s+/g, "_") + ".csv";
  jsonLink.href = base + "?format=json";
  jsonLink.download = "task_" + id.replace(/\s+/g, "_") + ".json";
  section.style.display = "";
}
window.selectTask = selectTask;

export function renderDetail(t) {
  const el = document.getElementById("detail-content");
  const branches = t.branches || {};

  // Track status changes for auto-scroll
  const _prevStatuses = window._prevSubtaskStatuses || {};
  const _newStatuses = {};
  let _changedSt = null;
  Object.entries(branches).forEach(([, bdata]) => {
    Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
      _newStatuses[sname] = s.status || "Pending";
      if (_prevStatuses[sname] && _prevStatuses[sname] !== _newStatuses[sname]) {
        _changedSt = sname;
      }
    });
  });
  window._prevSubtaskStatuses = _newStatuses;

  // Build DOM
  const taskIdDiv = document.createElement("div");
  taskIdDiv.className = "detail-task-id";
  taskIdDiv.textContent = t.id;

  const statusDiv = document.createElement("div");
  statusDiv.className = "detail-status";

  const badgeSpan = document.createElement("span");
  badgeSpan.className = `card-mini-badge ${statusClass(t.status)}`;
  badgeSpan.textContent = t.status || "Pending";
  statusDiv.appendChild(badgeSpan);

  if (t.depends_on && t.depends_on.length) {
    const depsSpan = document.createElement("span");
    depsSpan.style.cssText = "color:#ff9800;font-size:10px";
    depsSpan.textContent = "← " + t.depends_on.join(", ");
    statusDiv.append(" ", depsSpan);
  }

  const resetBtn = document.createElement("button");
  resetBtn.className = "toolbar-btn";
  resetBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:8px";
  resetBtn.title = "Reset all non-Verified subtasks to Pending";
  resetBtn.textContent = "↺ Reset task";
  resetBtn.addEventListener("click", () => window.resetTask(t.id));
  statusDiv.append(" ", resetBtn);

  const timelineBtn = document.createElement("button");
  timelineBtn.className = "toolbar-btn";
  timelineBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  timelineBtn.title = "Show task-level timeline (subtasks sorted by last activity)";
  timelineBtn.textContent = "⏱ Timeline";
  timelineBtn.addEventListener("click", () => window.toggleTaskTimeline(t.id));
  statusDiv.append(" ", timelineBtn);

  // ── Per-task progress bar + per-branch breakdown ──────────
  let _total = 0, _verified = 0, _running = 0, _review = 0, _pending = 0;
  const _branchStats = [];
  Object.entries(branches).forEach(([bname, bdata]) => {
    let bv = 0, br = 0, brv = 0, bt = 0;
    Object.values(bdata.subtasks || {}).forEach(st => {
      bt++;
      if (st.status === "Verified") bv++;
      else if (st.status === "Running") br++;
      else if (st.status === "Review")  brv++;
    });
    _branchStats.push({ name: bname, verified: bv, running: br, review: brv, total: bt });
    _total += bt; _verified += bv; _running += br; _review += brv;
    _pending += bt - bv - br - brv;
  });
  const progressRow = document.createElement("div");
  progressRow.style.cssText = "display:flex;align-items:center;gap:6px;margin:4px 0 2px";
  const barW = 100;
  const fillW = _total > 0 ? Math.round(_verified / _total * barW) : 0;
  const pct = _total > 0 ? Math.round(_verified / _total * 100) : 0;
  const trackEl = document.createElement("div");
  trackEl.id = "detail-prog-track";
  trackEl.style.cssText = `width:${barW}px;height:6px;background:var(--bg3);border-radius:3px;flex-shrink:0`;
  const fillEl = document.createElement("div");
  fillEl.id = "detail-prog-fill";
  fillEl.style.cssText = `width:${fillW}px;height:6px;background:var(--green);border-radius:3px`;
  trackEl.appendChild(fillEl);
  const pctSpan = document.createElement("span");
  pctSpan.id = "detail-prog-pct";
  pctSpan.style.cssText = "font-size:10px;color:var(--dim)";
  pctSpan.textContent = `${_verified}/${_total} (${pct}%)`;
  const runSpan = document.createElement("span");
  runSpan.id = "detail-prog-run";
  runSpan.style.cssText = "font-size:10px;color:var(--cyan)";
  let _runText = "";
  if (_running > 0) _runText += `${_running}▶`;
  if (_review  > 0) _runText += (_runText ? " " : "") + `${_review}⏸`;
  runSpan.textContent = _runText;
  progressRow.append(trackEl, pctSpan, runSpan);

  // per-branch mini rows (only when >1 branch)
  const branchProgressDiv = document.createElement("div");
  branchProgressDiv.style.cssText = "margin:2px 0 4px;display:flex;flex-direction:column;gap:2px";
  if (_branchStats.length > 1) {
    const miniW = 60;
    _branchStats.forEach(bs => {
      const bpct = bs.total > 0 ? Math.round(bs.verified / bs.total * 100) : 0;
      const bfill = Math.round(bpct * miniW / 100);
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;gap:4px";
      row.dataset.branch = bs.name;
      const lbl = document.createElement("span");
      lbl.style.cssText = "font-size:9px;color:var(--dim);min-width:80px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
      lbl.textContent = bs.name;
      lbl.title = bs.name;
      const trk = document.createElement("div");
      trk.style.cssText = `width:${miniW}px;height:4px;background:var(--bg3);border-radius:2px;flex-shrink:0`;
      const fll = document.createElement("div");
      fll.className = "branch-mini-fill";
      fll.style.cssText = `width:${bfill}px;height:4px;background:var(--green);border-radius:2px`;
      trk.appendChild(fll);
      const cnt = document.createElement("span");
      cnt.className = "branch-mini-cnt";
      cnt.style.cssText = "font-size:9px;color:var(--dim)";
      let bExtra = `${bs.verified}/${bs.total}`;
      if (bs.running > 0) bExtra += ` ${bs.running}▶`;
      if (bs.review  > 0) bExtra += ` ${bs.review}⏸`;
      cnt.textContent = bExtra;
      row.append(lbl, trk, cnt);
      branchProgressDiv.appendChild(row);
    });
  }

  const nodes = [taskIdDiv, progressRow, branchProgressDiv, statusDiv];

  Object.entries(branches).forEach(([bname, bdata]) => {
    const branchBlock = document.createElement("div");
    branchBlock.className = "branch-block";

    const branchNameEl = document.createElement("div");
    branchNameEl.className = "branch-name";
    branchNameEl.textContent = bname;
    branchBlock.appendChild(branchNameEl);

    Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
      const rawOutput = s.output || "";

      const row = document.createElement("div");
      row.className = "subtask-row";
      row.addEventListener("click", () => window.showModal(sname, s));

      const dot = document.createElement("div");
      dot.className = `st-dot ${dotClass(s.status)}`;

      const nameSpan = document.createElement("span");
      nameSpan.className = "st-name";
      nameSpan.textContent = sname;

      row.append(dot, nameSpan);

      if (rawOutput) {
        const outSpan = document.createElement("span");
        outSpan.className = "st-output";
        outSpan.title = rawOutput.substring(0, 400);
        outSpan.textContent = rawOutput.replace(/\n/g, " ").substring(0, 80);
        row.appendChild(outSpan);

        const expandBtn = document.createElement("button");
        expandBtn.className = "st-expand-btn";
        expandBtn.title = "Expand output";
        expandBtn.textContent = "▶";
        expandBtn.addEventListener("click", (event) => window.toggleExpand(expandBtn, event));

        const expandContent = document.createElement("div");
        expandContent.className = "st-expand-content";
        expandContent.textContent = rawOutput;

        row.append(expandBtn, expandContent);
      } else if (s.description) {
        const descSpan = document.createElement("span");
        descSpan.className = "st-output";
        descSpan.textContent = s.description;
        row.appendChild(descSpan);
      }

      branchBlock.appendChild(row);
    });

    nodes.push(branchBlock);
  });

  el.replaceChildren(...nodes);

  if (_changedSt) {
    const rows = el.querySelectorAll(".subtask-row .st-name");
    for (const r of rows) {
      if (r.textContent === _changedSt) {
        r.closest(".subtask-row").scrollIntoView({ behavior: "smooth", block: "nearest" });
        break;
      }
    }
  }
}

window.toggleExpand = function toggleExpand(btn, event) {
  event.stopPropagation();
  const row = btn.closest(".subtask-row");
  const panel = row.querySelector(".st-expand-content");
  if (!panel) return;
  const open = panel.classList.toggle("open");
  btn.textContent = open ? "▼" : "▶";
};

window.resetTask = async function (taskId) {
  try {
    const r = await fetch(state.base + "/tasks/" + encodeURIComponent(taskId) + "/bulk-reset", { method: "POST" });
    const d = await r.json();
    if (d.ok) {
      toast("↺ " + taskId + " reset (" + d.reset_count + " subtasks)");
      selectTask(taskId);
    } else {
      toast(d.reason || "Reset failed");
    }
  } catch (_) { toast("Network error"); }
};

const _STATUS_COLOR = {
  Verified: "#22c55e", Running: "#06b6d4", Review: "#f59e0b",
  Pending: "#555", Blocked: "#ef4444",
};

window.toggleTaskTimeline = async function toggleTaskTimeline(taskId) {
  const el = document.getElementById("detail-content");
  const existing = el.querySelector(".detail-tl-panel");
  if (existing) { existing.remove(); return; }
  let data;
  try {
    const r = await fetch(state.base + "/tasks/" + encodeURIComponent(taskId) + "/timeline");
    data = await r.json();
  } catch (_) { toast("Timeline fetch failed"); return; }

  const panel = document.createElement("div");
  panel.className = "detail-tl-panel";
  panel.style.cssText = "margin-top:8px;border-top:1px solid var(--border);padding-top:6px";

  const header = document.createElement("div");
  header.style.cssText = "font-size:10px;color:var(--cyan);margin-bottom:4px";
  header.textContent = `Timeline — ${data.count} subtasks (step ${data.step})`;
  panel.appendChild(header);

  (data.subtasks || []).forEach(st => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:6px;padding:1px 0;font-size:10px";

    const dot = document.createElement("span");
    dot.style.cssText = `width:7px;height:7px;border-radius:50%;flex-shrink:0;background:${_STATUS_COLOR[st.status] || "#555"}`;
    row.appendChild(dot);

    const name = document.createElement("span");
    name.style.cssText = "font-weight:bold;min-width:28px";
    name.textContent = st.subtask;
    row.appendChild(name);

    const branch = document.createElement("span");
    branch.style.cssText = "color:var(--dim);min-width:60px";
    branch.textContent = st.branch;
    row.appendChild(branch);

    const status = document.createElement("span");
    status.style.color = _STATUS_COLOR[st.status] || "var(--text)";
    status.textContent = st.status;
    row.appendChild(status);

    const step = document.createElement("span");
    step.style.cssText = "margin-left:auto;color:var(--dim)";
    step.textContent = "s" + st.last_update;
    row.appendChild(step);

    panel.appendChild(row);
  });

  el.appendChild(panel);
};

window._applyTaskSearch = function () {
  _tasksSearchFilter = (document.getElementById("task-search")?.value || "").trim().toLowerCase();
  _tasksPage = 1;
  pollTasks();
};

window.filterSubtasks = function filterSubtasks() {
  const q = (document.getElementById("st-search").value || "").toLowerCase();
  document.querySelectorAll("#detail-content .subtask-row").forEach(row => {
    const name = (row.querySelector(".st-name")?.textContent || "").toLowerCase();
    const output = (row.querySelector(".st-output")?.textContent || "").toLowerCase();
    row.style.display = (!q || name.includes(q) || output.includes(q)) ? "" : "none";
  });
};

/* ── Lightweight progress bar update (no full re-render) ──── */
export async function pollTaskProgress(taskId) {
  if (!taskId) return;
  try {
    const d = await api("/tasks/" + encodeURIComponent(taskId) + "/progress");
    const fill = document.getElementById("detail-prog-fill");
    const pct  = document.getElementById("detail-prog-pct");
    const run  = document.getElementById("detail-prog-run");
    if (!fill || !pct) return;
    const barW = 100;
    const fillW = d.total > 0 ? Math.round(d.verified / d.total * barW) : 0;
    const pctVal = d.total > 0 ? Math.round(d.verified / d.total * 100) : 0;
    fill.style.width = fillW + "px";
    pct.textContent = `${d.verified}/${d.total} (${pctVal}%)`;
    if (run) {
      let runText = "";
      if (d.running > 0) runText += `${d.running}▶`;
      if (d.review  > 0) runText += (runText ? " " : "") + `${d.review}⏸`;
      run.textContent = runText;
    }
    const miniW = 60;
    (d.branches || []).forEach(b => {
      const row = document.querySelector(`[data-branch="${CSS.escape(b.branch)}"]`);
      if (!row) return;
      const fll = row.querySelector(".branch-mini-fill");
      const cnt = row.querySelector(".branch-mini-cnt");
      if (fll) fll.style.width = Math.round((b.pct || 0) * miniW / 100) + "px";
      if (cnt) {
        let t = `${b.verified}/${b.total}`;
        if (b.running > 0) t += ` ${b.running}▶`;
        if (b.review  > 0) t += ` ${b.review}⏸`;
        cnt.textContent = t;
      }
    });
  } catch (_) {}
}
