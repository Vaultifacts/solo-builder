import { state } from "./dashboard_state.js";
import { api, statusClass, dotClass, toast, updateNotifBadge, checkStaleBanner, playCompletionSound } from "./dashboard_utils.js";
import { svgEl } from "./dashboard_svg.js";
export { pollJournal, pollDiff, pollStats } from "./dashboard_journal.js";

const _TASKS_LIMIT    = 50;
let _tasksPage        = 1;
let _tasksSearchFilter = "";

/* ── Pinned tasks persistence ─────────────────────────────── */
function _getPinnedTasks() {
  try { return JSON.parse(localStorage.getItem("sb-pinned-tasks") || "[]"); } catch (_) { return []; }
}
function _setPinnedTasks(pinned) {
  localStorage.setItem("sb-pinned-tasks", JSON.stringify(pinned));
}
function _togglePin(taskId) {
  const pinned = _getPinnedTasks();
  const idx = pinned.indexOf(taskId);
  if (idx >= 0) pinned.splice(idx, 1); else pinned.push(taskId);
  _setPinnedTasks(pinned);
  applyTaskSearch();
}

/* ── Batch multi-select ──────────────────────────────────── */
const _selectedCards = new Set();
function _toggleCardSelect(taskId, ev) {
  ev.stopPropagation();
  if (_selectedCards.has(taskId)) _selectedCards.delete(taskId); else _selectedCards.add(taskId);
  _updateBatchBar();
  document.querySelectorAll(".task-card").forEach(c => c.classList.toggle("multi-selected", _selectedCards.has(c.dataset.id)));
}
function _updateBatchBar() {
  const bar = document.getElementById("batch-action-bar");
  const lbl = document.getElementById("batch-sel-count");
  if (!bar) return;
  if (_selectedCards.size > 0) {
    bar.style.display = "flex";
    lbl.textContent = `${_selectedCards.size} selected`;
  } else {
    bar.style.display = "none";
  }
}
window.batchResetSelected = async function () {
  if (_selectedCards.size === 0) return;
  for (const tid of _selectedCards) {
    try {
      await fetch(state.base + "/tasks/" + encodeURIComponent(tid) + "/bulk-reset", { method: "POST" });
    } catch (_) {}
  }
  toast(`↺ Reset ${_selectedCards.size} task(s)`);
  _selectedCards.clear();
  _updateBatchBar();
  document.querySelectorAll(".task-card.multi-selected").forEach(c => c.classList.remove("multi-selected"));
};
window.batchClearSelection = function () {
  _selectedCards.clear();
  _updateBatchBar();
  document.querySelectorAll(".task-card.multi-selected").forEach(c => c.classList.remove("multi-selected"));
};

/* ── Drag-to-reorder persistence ──────────────────────────── */
function _getTaskOrder() {
  try { return JSON.parse(localStorage.getItem("sb-task-order") || "[]"); } catch (_) { return []; }
}
function _setTaskOrder(order) {
  localStorage.setItem("sb-task-order", JSON.stringify(order));
}
function _reorderTask(fromId, toId) {
  const order = state.taskIds.slice();
  const fi = order.indexOf(fromId);
  const ti = order.indexOf(toId);
  if (fi < 0 || ti < 0) return;
  order.splice(fi, 1);
  order.splice(ti, 0, fromId);
  _setTaskOrder(order);
  state.taskIds = order;
  // Re-sort allTasks to match new order
  const taskMap = {};
  state.allTasks.forEach(t => { taskMap[t.id] = t; });
  const sorted = order.map(id => taskMap[id]).filter(Boolean);
  // Add any tasks not in order at the end
  state.allTasks.forEach(t => { if (!order.includes(t.id)) sorted.push(t); });
  state.allTasks = sorted;
  renderGrid(sorted);
}

/* ── Relative time helper ──────────────────────────────────── */
function _relativeTime(isoStr) {
  if (!isoStr) return "";
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 0 || isNaN(diff)) return "";
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/* ── Status emoji prefix ───────────────────────────────────── */
const _STATUS_EMOJI = { Verified: "✓", Running: "▶", Review: "⏸", Pending: "◯", Blocked: "⊘" };
function _statusEmoji(status) { return _STATUS_EMOJI[status] || "◯"; }

/* ── Find first running subtask name ───────────────────────── */
function _findFirstRunning(t) {
  for (const b of Object.values(t.branches || {})) {
    for (const [sn, s] of Object.entries(b.subtasks || {})) {
      if (s.status === "Running") return sn;
    }
  }
  return null;
}

/* ── Task star (favorite) persistence ──────────────────────── */
function _getStarredTasks() {
  try { return JSON.parse(localStorage.getItem("sb-starred-tasks") || "[]"); } catch (_) { return []; }
}
function _setStarredTasks(starred) {
  localStorage.setItem("sb-starred-tasks", JSON.stringify(starred));
}
function _toggleStar(taskId) {
  const starred = _getStarredTasks();
  const idx = starred.indexOf(taskId);
  if (idx >= 0) starred.splice(idx, 1); else starred.push(taskId);
  _setStarredTasks(starred);
  document.querySelectorAll(`.task-card[data-id="${CSS.escape(taskId)}"] .card-star-btn`).forEach(b => {
    b.textContent = starred.includes(taskId) ? "★" : "☆";
  });
}

/* ── Task notes persistence ───────────────────────────────── */
function _getTaskNote(taskId) {
  try { return JSON.parse(localStorage.getItem("sb-task-notes") || "{}")[taskId] || ""; } catch (_) { return ""; }
}
function _setTaskNote(taskId, note) {
  try {
    const notes = JSON.parse(localStorage.getItem("sb-task-notes") || "{}");
    if (note) notes[taskId] = note; else delete notes[taskId];
    localStorage.setItem("sb-task-notes", JSON.stringify(notes));
  } catch (_) {}
}

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
    document.getElementById("hdr-bar").title            = `Verified: ${d.verified} | Running: ${d.running} | Pending: ${d.pending}${d.review > 0 ? ` | Review: ${d.review}` : ""}`;
    document.getElementById("hdr-pct").textContent      = d.pct + "%";
    const fracEl = document.getElementById("hdr-fraction");
    if (fracEl) fracEl.textContent = `${d.verified}/${d.total}`;
    if (state._initialStep == null) state._initialStep = d.step;
    const stepDelta = d.step - state._initialStep;
    const deltaStr = stepDelta > 0 ? ` (+${stepDelta})` : "";
    document.getElementById("hdr-step").textContent     = `Step ${d.step} / ${d.total} — ${d.verified} verified${deltaStr}` + (d.review > 0 ? ` · ${d.review}⏸` : "");
    if (d.step > state.prevStep) {
      const delta = (d.verified - state.prevVerified) / (d.step - state.prevStep);
      state.rateEma = state.rateEma === null ? delta : 0.3 * delta + 0.7 * state.rateEma;
      state.prevVerified = d.verified;
      state.prevStep     = d.step;
    }
    updateNotifBadge(d.step);
    document.getElementById("hdr-rate").textContent =
      state.rateEma !== null ? state.rateEma.toFixed(1) : "—";
    // ETA estimate
    const etaEl = document.getElementById("hdr-eta");
    if (etaEl) {
      const remaining = d.total - d.verified;
      if (d.complete) { etaEl.textContent = "done"; }
      else if (state.rateEma > 0 && remaining > 0) {
        const stepsLeft = Math.ceil(remaining / state.rateEma);
        const secsLeft = stepsLeft * (state.pollMs / 1000);
        if (secsLeft < 60) etaEl.textContent = `~${Math.round(secsLeft)}s`;
        else if (secsLeft < 3600) etaEl.textContent = `~${Math.round(secsLeft / 60)}m`;
        else etaEl.textContent = `~${(secsLeft / 3600).toFixed(1)}h`;
        etaEl.title = `~${stepsLeft} steps remaining at ${state.rateEma.toFixed(2)} verified/step`;
      } else { etaEl.textContent = ""; }
    }
    document.title = d.complete
      ? "Solo Builder ✓ Complete"
      : `Solo Builder — Step ${d.step} (${d.pct}%)`;

    const badge = document.getElementById("hdr-badge");
    if (d.complete && badge.textContent !== "Complete") {
      playCompletionSound();
      fetch(state.base + "/webhook", {method: "POST"}).then(r => r.json()).then(wd => {
        if (wd.ok) toast("Pipeline complete — webhook fired", "success");
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
    // Active tasks count
    const activeEl = document.getElementById("hdr-active-tasks");
    if (activeEl) {
      const activeTasks = state.allTasks.filter(at => at.running_subtasks > 0).length;
      activeEl.textContent = activeTasks > 0 ? `${activeTasks} active` : "";
    }
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
  let filtered = q
    ? state.allTasks.filter(t => t.id.toLowerCase().includes(q) || (t.status || "").toLowerCase().includes(q))
    : state.allTasks;
  // Apply saved drag-reorder
  const savedOrder = _getTaskOrder();
  if (savedOrder.length > 0 && !q) {
    const orderMap = {};
    savedOrder.forEach((id, i) => { orderMap[id] = i; });
    filtered = filtered.slice().sort((a, b) => {
      const ai = orderMap[a.id] ?? 9999;
      const bi = orderMap[b.id] ?? 9999;
      return ai - bi;
    });
  }
  // Pin sorted tasks to top
  const pinned = _getPinnedTasks();
  if (pinned.length > 0) {
    const pinSet = new Set(pinned);
    filtered = filtered.slice().sort((a, b) => {
      const ap = pinSet.has(a.id) ? 0 : 1;
      const bp = pinSet.has(b.id) ? 0 : 1;
      return ap - bp;
    });
  }
  // Search match count
  const matchEl = document.getElementById("search-match-count");
  if (matchEl) {
    matchEl.textContent = q ? `${filtered.length} result${filtered.length !== 1 ? "s" : ""}` : "";
  }
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

      const cardPctLabel = document.createElement("span");
      cardPctLabel.className = "card-pct-label";
      barBg.style.position = "relative";
      barBg.appendChild(cardPctLabel);

      card.replaceChildren(cardTop, cardDeps, barBg, cardCounts);
      card.addEventListener("click", (ev) => { if (ev.shiftKey) { _toggleCardSelect(t.id, ev); return; } selectTask(t.id); });
      card.setAttribute("draggable", "true");
      card.addEventListener("dragstart", (ev) => { ev.dataTransfer.setData("text/plain", t.id); card.classList.add("dragging"); });
      card.addEventListener("dragend", () => { card.classList.remove("dragging"); });
      card.addEventListener("dragover", (ev) => { ev.preventDefault(); card.classList.add("drag-over"); });
      card.addEventListener("dragleave", () => { card.classList.remove("drag-over"); });
      card.addEventListener("drop", (ev) => {
        ev.preventDefault();
        card.classList.remove("drag-over");
        const fromId = ev.dataTransfer.getData("text/plain");
        if (fromId && fromId !== t.id) _reorderTask(fromId, t.id);
      });
      const pinBtn = document.createElement("button");
      pinBtn.className = "card-pin-btn";
      pinBtn.title = "Pin/unpin task";
      pinBtn.textContent = "📌";
      pinBtn.addEventListener("click", (ev) => { ev.stopPropagation(); _togglePin(t.id); });
      cardTop.appendChild(pinBtn);

      const starBtn = document.createElement("button");
      starBtn.className = "card-star-btn";
      starBtn.title = "Star/unstar task";
      starBtn.textContent = _getStarredTasks().includes(t.id) ? "★" : "☆";
      starBtn.addEventListener("click", (ev) => { ev.stopPropagation(); _toggleStar(t.id); });
      cardTop.appendChild(starBtn);

      card.addEventListener("contextmenu", (ev) => {
        ev.preventDefault();
        _showCardContextMenu(ev, t.id);
      });

      grid.appendChild(card);
    }
    card.classList.toggle("pinned", _getPinnedTasks().includes(t.id));
    card.classList.toggle("multi-selected", _selectedCards.has(t.id));
    card.querySelector(".card-mini-badge").className = `card-mini-badge ${statusClass(t.status)}`;
    card.querySelector(".card-mini-badge").textContent = `${_statusEmoji(t.status)} ${t.status || "Pending"}`;
    const reviewBadge = card.querySelector(".card-review-badge");
    if (reviewBadge) {
      if (t.review_subtasks > 0) { reviewBadge.textContent = `⏸${t.review_subtasks}`; reviewBadge.style.display = ""; }
      else { reviewBadge.style.display = "none"; }
    }
    card.classList.toggle("active",  t.id === state.selectedTask);
    card.classList.toggle("blocked", isBlocked);
    card.classList.remove("status-complete", "status-running", "status-pending");
    const _taskPct = t.subtask_count > 0 ? t.verified_subtasks / t.subtask_count : 0;
    card.classList.add(_taskPct >= 1 ? "status-complete" : t.running_subtasks > 0 ? "status-running" : "status-pending");

    const pct = t.pct != null ? Math.round(t.pct) : (t.subtask_count > 0 ? Math.round(t.verified_subtasks / t.subtask_count * 100) : 0);
    card.querySelector(".card-bar-fg").style.width = pct + "%";
    const pctLabel = card.querySelector(".card-pct-label");
    if (pctLabel) pctLabel.textContent = pct > 0 ? `${pct}%` : "";
    card.querySelector(".card-counts").textContent =
      `${t.verified_subtasks}/${t.subtask_count} verified` +
      (t.running_subtasks > 0 ? ` · ${t.running_subtasks}▶` : "") +
      (t.review_subtasks  > 0 ? ` · ${t.review_subtasks}⏸`  : "");

    // Total subtask count label
    let stCountEl = card.querySelector(".card-st-count");
    if (!stCountEl) {
      stCountEl = document.createElement("span");
      stCountEl.className = "card-st-count";
      card.querySelector(".card-counts").after(stCountEl);
    }
    stCountEl.textContent = t.subtask_count > 0 ? `${t.subtask_count} subtask${t.subtask_count !== 1 ? "s" : ""}` : "";

    // Progress ring SVG
    let ringEl = card.querySelector(".card-progress-ring");
    if (!ringEl) {
      const NS = "http://www.w3.org/2000/svg";
      ringEl = document.createElementNS(NS, "svg");
      ringEl.setAttribute("class", "card-progress-ring");
      ringEl.setAttribute("width", "20");
      ringEl.setAttribute("height", "20");
      ringEl.setAttribute("viewBox", "0 0 20 20");
      const bgCircle = document.createElementNS(NS, "circle");
      bgCircle.setAttribute("cx", "10"); bgCircle.setAttribute("cy", "10");
      bgCircle.setAttribute("r", "8"); bgCircle.setAttribute("fill", "none");
      bgCircle.setAttribute("stroke", "var(--bg3)"); bgCircle.setAttribute("stroke-width", "2");
      const fgCircle = document.createElementNS(NS, "circle");
      fgCircle.setAttribute("class", "ring-fg");
      fgCircle.setAttribute("cx", "10"); fgCircle.setAttribute("cy", "10");
      fgCircle.setAttribute("r", "8"); fgCircle.setAttribute("fill", "none");
      fgCircle.setAttribute("stroke", "var(--green)"); fgCircle.setAttribute("stroke-width", "2");
      fgCircle.setAttribute("stroke-linecap", "round");
      fgCircle.setAttribute("transform", "rotate(-90 10 10)");
      const circ = 2 * Math.PI * 8;
      fgCircle.setAttribute("stroke-dasharray", `${circ}`);
      fgCircle.setAttribute("stroke-dashoffset", `${circ}`);
      ringEl.append(bgCircle, fgCircle);
      card.querySelector(".card-bar-bg").after(ringEl);
    }
    const _ringFg = ringEl.querySelector(".ring-fg");
    if (_ringFg) {
      const circ = 2 * Math.PI * 8;
      _ringFg.setAttribute("stroke-dashoffset", `${circ - (pct / 100) * circ}`);
    }

    // Segmented status bar
    let segBar = card.querySelector(".card-seg-bar");
    if (!segBar) {
      segBar = document.createElement("div");
      segBar.className = "card-seg-bar";
      card.querySelector(".card-bar-bg").after(segBar);
    }
    if (t.subtask_count > 0) {
      const vW = Math.round(t.verified_subtasks / t.subtask_count * 100);
      const rW = Math.round(t.running_subtasks / t.subtask_count * 100);
      const rvW = Math.round((t.review_subtasks || 0) / t.subtask_count * 100);
      segBar.innerHTML = `<span class="seg seg-v" style="width:${vW}%"></span><span class="seg seg-r" style="width:${rW}%"></span><span class="seg seg-rv" style="width:${rvW}%"></span>`;
      segBar.title = `Verified: ${vW}% | Running: ${rW}% | Review: ${rvW}%`;
    }

    // Running subtask name on card
    let runNameEl = card.querySelector(".card-running-name");
    const _firstRunning = _findFirstRunning(t);
    if (_firstRunning) {
      if (!runNameEl) {
        runNameEl = document.createElement("div");
        runNameEl.className = "card-running-name";
        card.querySelector(".card-counts").after(runNameEl);
      }
      runNameEl.textContent = `▶ ${_firstRunning}`;
      runNameEl.title = `Currently running: ${_firstRunning}`;
    } else if (runNameEl) {
      runNameEl.textContent = "";
    }

    const depEl = card.querySelector(".card-deps");
    if (t.depends_on && t.depends_on.length) {
      depEl.textContent = "← " + t.depends_on.join(", ");
    } else {
      depEl.textContent = "";
    }

    // Sparkline — tiny bar chart of branch completion
    let sparkEl = card.querySelector(".card-sparkline");
    const _bEntries = Object.entries(t.branches || {});
    if (_bEntries.length > 1) {
      if (!sparkEl) {
        sparkEl = document.createElement("div");
        sparkEl.className = "card-sparkline";
        card.querySelector(".card-counts").after(sparkEl);
      }
      const bars = _bEntries.map(([, bd]) => {
        const st = Object.values(bd.subtasks || {});
        const v = st.filter(s => s.status === "Verified").length;
        return st.length > 0 ? Math.round(v / st.length * 100) : 0;
      });
      sparkEl.innerHTML = bars.map(p => `<span class="spark-bar" style="height:${Math.max(2, p * 12 / 100)}px"></span>`).join("");
    }

    // Last-active relative time
    let agoEl = card.querySelector(".card-ago");
    if (!agoEl) {
      agoEl = document.createElement("span");
      agoEl.className = "card-ago";
      card.appendChild(agoEl);
    }
    agoEl.textContent = _relativeTime(t.last_active);
    agoEl.title = t.last_active || "";

    // Tooltip with branch breakdown
    if (_bEntries.length > 0) {
      const tipLines = _bEntries.map(([bn, bd]) => {
        const st = Object.values(bd.subtasks || {});
        const v = st.filter(s => s.status === "Verified").length;
        return `${bn}: ${v}/${st.length}`;
      });
      card.title = `${t.id} — ${t.status || "Pending"}\n${tipLines.join("\n")}`;
    } else {
      card.title = `${t.id} — ${t.status || "Pending"}`;
    }
  });
}

/* ── Detail panel ────────────────────────────────────────── */
export async function selectTask(id) {
  state.selectedTask = id;
  window._resetSubtasksFilters?.();
  document.querySelectorAll(".task-card").forEach(c => c.classList.toggle("active", c.dataset.id === id));
  _updateTaskExportLinks(id);
  const dp = document.getElementById("detail-content");
  if (dp) dp.scrollTop = 0;
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
  taskIdDiv.title = "Click to copy task ID";
  taskIdDiv.style.cursor = "pointer";
  taskIdDiv.addEventListener("click", () => {
    navigator.clipboard.writeText(t.id).then(() => toast(`Copied: ${t.id}`)).catch(() => {});
  });

  const statusDiv = document.createElement("div");
  statusDiv.className = "detail-status";

  const badgeSpan = document.createElement("span");
  badgeSpan.className = `card-mini-badge ${statusClass(t.status)}`;
  badgeSpan.textContent = t.status || "Pending";
  statusDiv.appendChild(badgeSpan);

  if (t.depends_on && t.depends_on.length) {
    const depsWrap = document.createElement("span");
    depsWrap.className = "detail-task-deps";
    const arrow = document.createElement("span");
    arrow.style.cssText = "color:var(--dim);font-size:9px;margin-right:2px";
    arrow.textContent = "←";
    depsWrap.appendChild(arrow);
    for (const dep of t.depends_on) {
      const chip = document.createElement("span");
      chip.className = "task-dep-chip";
      chip.textContent = dep;
      chip.title = `Click to select ${dep}`;
      chip.addEventListener("click", (ev) => { ev.stopPropagation(); selectTask(dep); });
      depsWrap.appendChild(chip);
    }
    statusDiv.append(" ", depsWrap);
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

  const scrollRunBtn = document.createElement("button");
  scrollRunBtn.className = "toolbar-btn";
  scrollRunBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  scrollRunBtn.title = "Scroll to first running subtask";
  scrollRunBtn.textContent = "▶ Running";
  scrollRunBtn.addEventListener("click", () => {
    const dc = document.getElementById("detail-content");
    const dots = dc.querySelectorAll(".st-dot.dot-cyan");
    if (dots.length > 0) {
      const row = dots[0].closest(".subtask-row");
      if (row) { row.scrollIntoView({ behavior: "smooth", block: "center" }); row.style.outline = "2px solid var(--cyan)"; setTimeout(() => { row.style.outline = ""; }, 1500); }
    } else { toast("No running subtasks"); }
  });
  statusDiv.append(" ", scrollRunBtn);

  const depsBtn = document.createElement("button");
  depsBtn.className = "toolbar-btn";
  depsBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  depsBtn.title = "Toggle subtask dependency graph";
  depsBtn.textContent = "⊶ Deps";
  depsBtn.addEventListener("click", () => _toggleDepsGraph(t));
  statusDiv.append(" ", depsBtn);

  const sortBtn = document.createElement("button");
  sortBtn.className = "toolbar-btn";
  sortBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  sortBtn.title = "Sort subtasks by status (Pending → Running → Review → Verified)";
  sortBtn.textContent = "⇅ Sort";
  sortBtn.addEventListener("click", () => {
    const _ord = { Pending: 0, Running: 1, Review: 2, Verified: 3 };
    const dc = document.getElementById("detail-content");
    dc.querySelectorAll(".branch-block").forEach(bb => {
      const rows = [...bb.querySelectorAll(".subtask-row")];
      rows.sort((a, b) => {
        const sa = a.querySelector(".st-dot")?.className || "";
        const sb2 = b.querySelector(".st-dot")?.className || "";
        const oa = sa.includes("green") ? 3 : sa.includes("cyan") ? 1 : sa.includes("yellow") ? 2 : 0;
        const ob = sb2.includes("green") ? 3 : sb2.includes("cyan") ? 1 : sb2.includes("yellow") ? 2 : 0;
        return oa - ob;
      });
      rows.forEach(r => bb.appendChild(r));
    });
    toast("Sorted subtasks by status");
  });
  statusDiv.append(" ", sortBtn);

  const expandAllBtn = document.createElement("button");
  expandAllBtn.className = "toolbar-btn";
  expandAllBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  expandAllBtn.title = "Expand all branches";
  expandAllBtn.textContent = "▾ All";
  expandAllBtn.addEventListener("click", () => window.expandAllBranches());
  statusDiv.append(" ", expandAllBtn);

  const collapseAllBtn = document.createElement("button");
  collapseAllBtn.className = "toolbar-btn";
  collapseAllBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:2px";
  collapseAllBtn.title = "Collapse all branches";
  collapseAllBtn.textContent = "▸ All";
  collapseAllBtn.addEventListener("click", () => window.collapseAllBranches());
  statusDiv.append(" ", collapseAllBtn);

  const branchNames = Object.keys(branches);
  if (branchNames.length > 1) {
    const branchSelect = document.createElement("select");
    branchSelect.className = "branch-filter-select";
    branchSelect.title = "Filter to branch";
    branchSelect.style.cssText = "font-size:9px;margin-left:4px;background:var(--bg2);color:var(--dim);border:1px solid var(--border);border-radius:3px;padding:1px 4px";
    const allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = "All branches";
    branchSelect.appendChild(allOpt);
    branchNames.forEach(bn => {
      const opt = document.createElement("option");
      opt.value = bn;
      opt.textContent = bn;
      branchSelect.appendChild(opt);
    });
    branchSelect.addEventListener("change", () => window.filterBranch(branchSelect.value));
    statusDiv.append(" ", branchSelect);
  }

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

  // Branch stats summary
  const branchSummary = document.createElement("div");
  branchSummary.className = "branch-stats-summary";
  const completeBranches = _branchStats.filter(b => b.verified === b.total && b.total > 0).length;
  branchSummary.textContent = _branchStats.length > 0
    ? `${completeBranches}/${_branchStats.length} branches complete`
    : "";

  const stickyHeader = document.createElement("div");
  stickyHeader.className = "detail-sticky-header";
  stickyHeader.append(taskIdDiv, progressRow, branchProgressDiv, branchSummary, statusDiv);

  // Task notes
  const notesWrap = document.createElement("div");
  notesWrap.className = "detail-notes-wrap";
  const notesInput = document.createElement("textarea");
  notesInput.className = "detail-notes";
  notesInput.placeholder = "Add notes…";
  notesInput.rows = 2;
  notesInput.value = _getTaskNote(t.id);
  notesInput.addEventListener("input", () => _setTaskNote(t.id, notesInput.value));
  notesWrap.appendChild(notesInput);

  const nodes = [stickyHeader, notesWrap];

  Object.entries(branches).forEach(([bname, bdata]) => {
    const branchBlock = document.createElement("div");
    branchBlock.className = "branch-block";

    const branchNameEl = document.createElement("div");
    branchNameEl.className = "branch-name";
    const collapseArrow = document.createElement("span");
    collapseArrow.className = "branch-collapse-arrow";
    collapseArrow.textContent = "▾";
    const readinessDot = document.createElement("span");
    readinessDot.className = "branch-readiness";
    const _bs = _branchStats.find(b => b.name === bname);
    if (_bs) {
      if (_bs.verified === _bs.total && _bs.total > 0) {
        readinessDot.classList.add("ready");
        readinessDot.title = "All subtasks verified — merge ready";
      } else if (_bs.verified > 0) {
        readinessDot.classList.add("partial");
        readinessDot.title = `${_bs.verified}/${_bs.total} verified — in progress`;
      } else {
        readinessDot.classList.add("notready");
        readinessDot.title = `0/${_bs.total} verified — not started`;
      }
    }
    const branchPctSpan = document.createElement("span");
    branchPctSpan.className = "branch-pct";
    if (_bs && _bs.total > 0) {
      const bPct = Math.round(_bs.verified / _bs.total * 100);
      branchPctSpan.textContent = ` ${bPct}%`;
    }
    branchNameEl.append(collapseArrow, " " + bname, readinessDot, branchPctSpan);
    branchNameEl.style.cursor = "pointer";
    branchNameEl.addEventListener("click", () => {
      branchBlock.classList.toggle("collapsed");
      collapseArrow.textContent = branchBlock.classList.contains("collapsed") ? "▸" : "▾";
    });
    branchBlock.appendChild(branchNameEl);

    Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
      const rawOutput = s.output || "";

      const row = document.createElement("div");
      row.className = "subtask-row";
      row.addEventListener("click", (ev) => { if (!ev.target.closest(".st-checkbox")) window.showModal(sname, s); });
      row.addEventListener("dblclick", (ev) => {
        ev.preventDefault();
        if (s.status !== "Verified") window._quickVerify(sname);
      });

      // Bulk verify checkbox
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "st-checkbox";
      cb.title = "Select for bulk verify";
      cb.dataset.subtask = sname;
      cb.addEventListener("click", (ev) => ev.stopPropagation());
      cb.addEventListener("change", () => _updateDetailBulkBar());

      const dot = document.createElement("div");
      dot.className = `st-dot ${dotClass(s.status)}`;

      const nameSpan = document.createElement("span");
      nameSpan.className = "st-name";
      nameSpan.textContent = sname;

      // Status transition arrow (if recently changed)
      let transSpan = null;
      const _prev = _prevStatuses[sname];
      if (_prev && _prev !== (s.status || "Pending")) {
        transSpan = document.createElement("span");
        transSpan.className = "st-transition";
        transSpan.textContent = `${_prev}→${s.status}`;
      }

      // Subtask elapsed time
      const stElapsed = document.createElement("span");
      stElapsed.className = "st-elapsed";
      const _stTime = _relativeTime(s.last_update_time);
      if (_stTime) stElapsed.textContent = _stTime;

      row.append(cb, dot, nameSpan);
      if (transSpan) row.appendChild(transSpan);
      row.appendChild(stElapsed);

      // Inline verify button (non-verified only)
      if (s.status !== "Verified") {
        const inlineVerify = document.createElement("button");
        inlineVerify.className = "st-inline-verify";
        inlineVerify.title = `Verify ${sname}`;
        inlineVerify.textContent = "✓";
        inlineVerify.addEventListener("click", (ev) => {
          ev.stopPropagation();
          window._quickVerify(sname);
        });
        row.appendChild(inlineVerify);
      }

      if (s.depends_on && s.depends_on.length) {
        const depWrap = document.createElement("span");
        depWrap.style.cssText = "display:inline-flex;gap:2px;align-items:center;margin-left:4px";
        const arrow = document.createElement("span");
        arrow.style.cssText = "color:var(--dim);font-size:9px";
        arrow.textContent = "←";
        depWrap.appendChild(arrow);
        for (const dep of s.depends_on) {
          const chip = document.createElement("span");
          chip.style.cssText = "font-size:8px;padding:0 3px;border-radius:3px;background:var(--bg3);color:#ff9800;cursor:pointer";
          chip.textContent = dep;
          chip.title = `Click to scroll to ${dep}`;
          chip.addEventListener("click", (ev) => {
            ev.stopPropagation();
            const rows = document.querySelectorAll("#detail-content .st-name");
            for (const r of rows) {
              if (r.textContent === dep) {
                const sr = r.closest(".subtask-row");
                sr.scrollIntoView({ behavior: "smooth", block: "nearest" });
                sr.style.outline = "2px solid #ff9800";
                setTimeout(() => { sr.style.outline = ""; }, 1500);
                break;
              }
            }
          });
          depWrap.appendChild(chip);
        }
        row.appendChild(depWrap);
      }

      // Description preview (always show if available, truncated)
      if (s.description && !rawOutput) {
        const descPreview = document.createElement("span");
        descPreview.className = "st-desc-preview";
        descPreview.textContent = s.description.substring(0, 60) + (s.description.length > 60 ? "…" : "");
        descPreview.title = s.description;
        row.appendChild(descPreview);
      }

      if (rawOutput) {
        const wc = rawOutput.split(/\s+/).filter(Boolean).length;
        const wcBadge = document.createElement("span");
        wcBadge.className = "st-wc-badge";
        wcBadge.title = `${wc} words`;
        wcBadge.textContent = wc > 999 ? `${(wc/1000).toFixed(1)}k` : `${wc}w`;
        row.appendChild(wcBadge);

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
      }

      branchBlock.appendChild(row);
    });

    // Auto-collapse verified branches
    if (_bs && _bs.verified === _bs.total && _bs.total > 0) {
      branchBlock.classList.add("collapsed");
      collapseArrow.textContent = "▸";
    }

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
      toast(d.reason || "Reset failed", "error");
    }
  } catch (_) { toast("Network error", "error"); }
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
  } catch (_) { toast("Timeline fetch failed", "error"); return; }

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

function _toggleDepsGraph(task) {
  const el = document.getElementById("detail-content");
  const existing = el.querySelector(".detail-deps-panel");
  if (existing) { existing.remove(); return; }

  const allSt = {};
  Object.entries(task.branches || {}).forEach(([, bdata]) => {
    Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
      allSt[sname] = s;
    });
  });
  const names = Object.keys(allSt);
  if (!names.length) return;

  const hasDeps = names.some(n => (allSt[n].depends_on || []).length > 0);
  if (!hasDeps) {
    toast("No dependencies in this task");
    return;
  }

  const NW = 60, NH = 22, PX = 90, PY = 34, OX = 10, OY = 20;
  const levels = {};
  const placed = new Set();
  function assignLevel(n, lv) {
    if (placed.has(n)) return;
    placed.add(n);
    levels[n] = Math.max(levels[n] || 0, lv);
    names.forEach(other => {
      if ((allSt[other].depends_on || []).includes(n)) assignLevel(other, lv + 1);
    });
  }
  names.forEach(n => {
    if (!(allSt[n].depends_on || []).length) assignLevel(n, 0);
  });
  names.forEach(n => { if (!placed.has(n)) levels[n] = 0; });

  const byLevel = {};
  names.forEach(n => {
    const lv = levels[n] || 0;
    (byLevel[lv] = byLevel[lv] || []).push(n);
  });
  const maxLevel = Math.max(...Object.values(levels));
  const maxPerLevel = Math.max(...Object.values(byLevel).map(a => a.length));
  const totalW = (maxLevel + 1) * PX + OX * 2;
  const totalH = maxPerLevel * PY + OY * 2;

  const pos = {};
  Object.entries(byLevel).forEach(([lv, ids]) => {
    const startY = (totalH - ids.length * PY) / 2 + PY / 2;
    ids.forEach((id, i) => { pos[id] = { x: OX + Number(lv) * PX, y: startY + i * PY }; });
  });

  const panel = document.createElement("div");
  panel.className = "detail-deps-panel";
  panel.style.cssText = "margin-top:8px;border-top:1px solid var(--border);padding-top:6px;overflow-x:auto";

  const header = document.createElement("div");
  header.style.cssText = "font-size:10px;color:var(--cyan);margin-bottom:4px";
  header.textContent = `Dependency graph — ${names.length} subtasks`;
  panel.appendChild(header);

  const svg = svgEl("svg", { width: totalW, height: totalH, viewBox: `0 0 ${totalW} ${totalH}` });
  svg.style.cssText = "display:block;min-height:80px";

  const defs = svgEl("defs", {});
  const marker = svgEl("marker", { id: "dep-arrow", markerWidth: "6", markerHeight: "4", refX: "6", refY: "2", orient: "auto" });
  marker.appendChild(svgEl("path", { d: "M0,0 L6,2 L0,4", fill: "var(--dim)" }));
  defs.appendChild(marker);
  svg.appendChild(defs);

  names.forEach(n => {
    (allSt[n].depends_on || []).filter(d => pos[d]).forEach(dep => {
      const from = pos[dep], to = pos[n];
      svg.appendChild(svgEl("line", {
        x1: from.x + NW, y1: from.y, x2: to.x, y2: to.y,
        stroke: "var(--dim)", "stroke-width": "1", "marker-end": "url(#dep-arrow)", opacity: "0.6"
      }));
    });
  });

  const stColor = s => {
    if (s === "Verified") return "var(--green)";
    if (s === "Running") return "var(--cyan)";
    if (s === "Blocked") return "#ef4444";
    return "var(--yellow)";
  };

  names.forEach(n => {
    const p = pos[n];
    const col = stColor(allSt[n].status);
    const rect = svgEl("rect", { x: p.x, y: p.y - NH / 2, width: NW, height: NH, rx: "3", fill: "var(--surface)", stroke: col, "stroke-width": "1" });
    rect.style.cursor = "pointer";
    rect.addEventListener("click", () => {
      const rows = document.querySelectorAll("#detail-content .st-name");
      for (const r of rows) {
        if (r.textContent === n) {
          const sr = r.closest(".subtask-row");
          sr.scrollIntoView({ behavior: "smooth", block: "nearest" });
          sr.style.outline = "2px solid var(--cyan)";
          setTimeout(() => { sr.style.outline = ""; }, 1500);
          break;
        }
      }
    });
    const txt = svgEl("text", { x: p.x + NW / 2, y: p.y + 4, "text-anchor": "middle", "font-size": "9", fill: col, "font-family": "var(--font)", style: "pointer-events:none" });
    txt.textContent = n;
    svg.append(rect, txt);
  });

  panel.appendChild(svg);
  el.appendChild(panel);
}

window._applyTaskSearch = function () {
  _tasksSearchFilter = (document.getElementById("task-search")?.value || "").trim().toLowerCase();
  _tasksPage = 1;
  pollTasks();
};

window.filterSubtasks = function filterSubtasks() {
  const q = (document.getElementById("st-search").value || "").toLowerCase();
  document.querySelectorAll("#detail-content .subtask-row").forEach(row => {
    const nameEl = row.querySelector(".st-name");
    const outEl = row.querySelector(".st-output");
    const name = (nameEl?.textContent || "").toLowerCase();
    const output = (outEl?.textContent || "").toLowerCase();
    const match = !q || name.includes(q) || output.includes(q);
    row.style.display = match ? "" : "none";
    // Highlight matching text
    if (nameEl) nameEl.innerHTML = q && name.includes(q) ? _highlightText(nameEl.textContent, q) : _escHtml(nameEl.textContent);
    if (outEl) outEl.innerHTML = q && output.includes(q) ? _highlightText(outEl.textContent, q) : _escHtml(outEl.textContent);
  });
};

function _escHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function _highlightText(text, query) {
  const esc = _escHtml(text);
  const qEsc = _escHtml(query);
  const re = new RegExp(`(${qEsc.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  return esc.replace(re, "<mark>$1</mark>");
}

/* ── Quick-verify (double-click) ──────────────────────────── */
window._quickVerify = async function (stName) {
  try {
    const r = await fetch(state.base + "/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subtask: stName, note: "Quick verify (dblclick)" }),
    });
    const d = await r.json();
    if (d.ok) {
      toast(`✓ ${stName} verified`);
      if (state.selectedTask) selectTask(state.selectedTask);
    } else {
      toast(d.reason || "Verify failed", "error");
    }
  } catch (_) { toast("Network error", "error"); }
};

/* ── Bulk verify in detail panel ──────────────────────────── */
function _updateDetailBulkBar() {
  const bar = document.getElementById("detail-bulk-bar");
  if (!bar) return;
  const checked = document.querySelectorAll("#detail-content .st-checkbox:checked");
  const lbl = document.getElementById("detail-bulk-count");
  if (checked.length > 0) {
    bar.style.display = "flex";
    if (lbl) lbl.textContent = `${checked.length} selected`;
  } else {
    bar.style.display = "none";
  }
}
window.detailBulkVerify = async function () {
  const checked = document.querySelectorAll("#detail-content .st-checkbox:checked");
  if (checked.length === 0) return;
  let ok = 0;
  for (const cb of checked) {
    try {
      const r = await fetch(state.base + "/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subtask: cb.dataset.subtask, note: "Bulk verify" }),
      });
      const d = await r.json();
      if (d.ok) ok++;
    } catch (_) {}
  }
  toast(`✓ Verified ${ok}/${checked.length} subtasks`);
  if (state.selectedTask) selectTask(state.selectedTask);
};
window.detailBulkClear = function () {
  document.querySelectorAll("#detail-content .st-checkbox:checked").forEach(cb => { cb.checked = false; });
  _updateDetailBulkBar();
};

/* ── Tab count badges ─────────────────────────────────────── */
export function updateTabBadges(stalledCount, historyCount) {
  const _setBadge = (tab, count) => {
    const btn = document.querySelector(`.sidebar-tab[data-tab="${tab}"]`);
    if (!btn) return;
    let badge = btn.querySelector(".tab-count-badge");
    if (count > 0) {
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "tab-count-badge";
        btn.appendChild(badge);
      }
      badge.textContent = count;
    } else if (badge) {
      badge.remove();
    }
  };
  if (stalledCount != null) _setBadge("stalled", stalledCount);
  if (historyCount != null) _setBadge("history", historyCount);
}

/* ── Compact mode toggle ──────────────────────────────────── */
window.toggleCompactMode = function () {
  const isCompact = document.body.classList.toggle("compact-mode");
  localStorage.setItem("sb-compact", isCompact ? "1" : "0");
  const btn = document.getElementById("btn-compact");
  if (btn) btn.textContent = isCompact ? "▤ Expand" : "▥ Compact";
};
// Restore on load
if (localStorage.getItem("sb-compact") === "1") {
  document.body.classList.add("compact-mode");
  const btn = document.getElementById("btn-compact");
  if (btn) btn.textContent = "▤ Expand";
}

/* ── Card context menu ─────────────────────────────────────── */
function _showCardContextMenu(ev, taskId) {
  let menu = document.getElementById("card-ctx-menu");
  if (!menu) {
    menu = document.createElement("div");
    menu.id = "card-ctx-menu";
    menu.className = "card-ctx-menu";
    document.body.appendChild(menu);
  }
  const pinned = _getPinnedTasks().includes(taskId);
  menu.innerHTML = "";
  const items = [
    { label: pinned ? "Unpin" : "Pin", action: () => _togglePin(taskId) },
    { label: "Reset", action: () => window.resetTask(taskId) },
    { label: "Copy ID", action: () => { navigator.clipboard.writeText(taskId).then(() => toast(`Copied: ${taskId}`)); } },
    { label: "Select", action: () => selectTask(taskId) },
  ];
  items.forEach(it => {
    const btn = document.createElement("div");
    btn.className = "ctx-menu-item";
    btn.textContent = it.label;
    btn.addEventListener("click", () => { menu.style.display = "none"; it.action(); });
    menu.appendChild(btn);
  });
  menu.style.display = "block";
  menu.style.left = ev.pageX + "px";
  menu.style.top = ev.pageY + "px";
  const _hideMenu = () => { menu.style.display = "none"; document.removeEventListener("click", _hideMenu); };
  setTimeout(() => document.addEventListener("click", _hideMenu), 0);
}

/* ── Expand / collapse all branches ───────────────────────── */
window.expandAllBranches = function () {
  document.querySelectorAll("#detail-content .branch-block.collapsed").forEach(bb => {
    bb.classList.remove("collapsed");
    const arrow = bb.querySelector(".branch-collapse-arrow");
    if (arrow) arrow.textContent = "▾";
  });
};
window.collapseAllBranches = function () {
  document.querySelectorAll("#detail-content .branch-block:not(.collapsed)").forEach(bb => {
    bb.classList.add("collapsed");
    const arrow = bb.querySelector(".branch-collapse-arrow");
    if (arrow) arrow.textContent = "▸";
  });
};

/* ── Branch filter dropdown ───────────────────────────────── */
window.filterBranch = function (branchName) {
  document.querySelectorAll("#detail-content .branch-block").forEach(bb => {
    const name = bb.querySelector(".branch-name")?.textContent?.trim() || "";
    bb.style.display = (!branchName || name.includes(branchName)) ? "" : "none";
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
