import { state } from "./dashboard_state.js";
import { api, statusClass, dotClass, toast, updateNotifBadge, checkStaleBanner, playCompletionSound } from "./dashboard_utils.js";
import { svgEl } from "./dashboard_svg.js";
export { pollJournal, pollDiff, pollStats } from "./dashboard_journal.js";

const _TASKS_LIMIT    = 50;
let _tasksPage        = 1;
let _tasksSearchFilter = "";
let _tasksSortMode = localStorage.getItem("sb-task-sort") || "default";

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

/* ── Find last verified subtask name ──────────────────────── */
function _findLastVerified(t) {
  let last = null, lastTime = 0;
  for (const b of Object.values(t.branches || {})) {
    for (const [sn, s] of Object.entries(b.subtasks || {})) {
      if (s.status === "Verified" && s.last_update_time) {
        const ts = new Date(s.last_update_time).getTime();
        if (ts > lastTime) { lastTime = ts; last = sn; }
      }
    }
  }
  return last;
}

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
  // Sort by mode
  if (_tasksSortMode !== "default") {
    filtered = filtered.slice().sort((a, b) => {
      if (_tasksSortMode === "name") return a.id.localeCompare(b.id);
      if (_tasksSortMode === "progress") {
        const pa = a.subtask_count > 0 ? a.verified_subtasks / a.subtask_count : 0;
        const pb = b.subtask_count > 0 ? b.verified_subtasks / b.subtask_count : 0;
        return pb - pa;
      }
      if (_tasksSortMode === "active") return (b.last_active || "").localeCompare(a.last_active || "");
      if (_tasksSortMode === "status") return (a.status || "").localeCompare(b.status || "");
      return 0;
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

  // Remove old group headers
  grid.querySelectorAll(".task-grp-hdr").forEach(h => h.remove());

  // Insert group-by-status headers when sorted by status
  if (_tasksSortMode === "status" && tasks.length > 1) {
    let _lastGroup = null;
    tasks.forEach(t => {
      const group = t.status || "Pending";
      if (group !== _lastGroup) {
        _lastGroup = group;
        const hdr = document.createElement("div");
        hdr.className = "task-grp-hdr";
        hdr.textContent = group;
        hdr.dataset.group = group;
        grid.appendChild(hdr);
      }
      let card = grid.querySelector(`[data-id="${CSS.escape(t.id)}"]`);
      if (card) grid.appendChild(card);
    });
  }

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
      const dragHandle = document.createElement("span");
      dragHandle.className = "card-drag-handle";
      dragHandle.textContent = "⠿";
      dragHandle.title = "Drag to reorder";
      cardTop.append(dragHandle, cardIdSpan, cardBadge, cardReview);

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
    card.querySelector(".card-mini-badge").title = `${t.verified_subtasks} verified · ${t.running_subtasks} running · ${t.review_subtasks || 0} review · ${t.subtask_count - t.verified_subtasks - t.running_subtasks - (t.review_subtasks || 0)} pending`;
    const reviewBadge = card.querySelector(".card-review-badge");
    if (reviewBadge) {
      if (t.review_subtasks > 0) { reviewBadge.textContent = `⏸${t.review_subtasks}`; reviewBadge.style.display = ""; }
      else { reviewBadge.style.display = "none"; }
    }
    card.classList.toggle("active",  t.id === state.selectedTask);
    card.classList.toggle("blocked", isBlocked);

    // Blocked overlay
    let blockedOverlay = card.querySelector(".card-blocked-overlay");
    if (isBlocked) {
      if (!blockedOverlay) {
        blockedOverlay = document.createElement("div");
        blockedOverlay.className = "card-blocked-overlay";
        blockedOverlay.textContent = "🔒 Blocked";
        card.appendChild(blockedOverlay);
      }
    } else if (blockedOverlay) {
      blockedOverlay.remove();
    }
    card.classList.remove("status-complete", "status-running", "status-pending");
    const _taskPct = t.subtask_count > 0 ? t.verified_subtasks / t.subtask_count : 0;
    card.classList.add(_taskPct >= 1 ? "status-complete" : t.running_subtasks > 0 ? "status-running" : "status-pending");

    // Verified pulse animation (flash card when verified count increases)
    const _prevV = card._prevVerified ?? t.verified_subtasks;
    if (t.verified_subtasks > _prevV) {
      card.classList.remove("card-pulse");
      void card.offsetWidth; // reflow to restart animation
      card.classList.add("card-pulse");
    }
    // Verified delta badge
    let deltaEl = card.querySelector(".card-verified-delta");
    if (t.verified_subtasks > _prevV) {
      if (!deltaEl) { deltaEl = document.createElement("span"); deltaEl.className = "card-verified-delta"; card.querySelector(".card-top").appendChild(deltaEl); }
      deltaEl.textContent = `+${t.verified_subtasks - _prevV}`;
      setTimeout(() => { if (deltaEl) deltaEl.textContent = ""; }, 3000);
    }
    card._prevVerified = t.verified_subtasks;

    // Card completion celebration (flash when task reaches 100%)
    const _wasComplete = card._wasComplete ?? false;
    const _isComplete = t.subtask_count > 0 && t.verified_subtasks === t.subtask_count;
    if (_isComplete && !_wasComplete) {
      card.classList.remove("card-complete-flash");
      void card.offsetWidth;
      card.classList.add("card-complete-flash");
      // Confetti burst
      const confetti = document.createElement("div");
      confetti.className = "card-confetti";
      for (let i = 0; i < 8; i++) {
        const p = document.createElement("span");
        p.className = "confetti-particle";
        p.style.setProperty("--angle", `${i * 45}deg`);
        confetti.appendChild(p);
      }
      card.appendChild(confetti);
      setTimeout(() => confetti.remove(), 1500);
    }
    card._wasComplete = _isComplete;

    const pct = t.pct != null ? Math.round(t.pct) : (t.subtask_count > 0 ? Math.round(t.verified_subtasks / t.subtask_count * 100) : 0);
    const barFg = card.querySelector(".card-bar-fg");
    barFg.style.width = pct + "%";
    barFg.parentElement.title = `${t.verified_subtasks}/${t.subtask_count} verified (${pct}%)`;
    const pctLabel = card.querySelector(".card-pct-label");
    if (pctLabel) {
      pctLabel.textContent = pct > 0 ? `${pct}%` : "";
      pctLabel.className = `card-pct-label ${pct >= 80 ? "pct-high" : pct >= 50 ? "pct-mid" : "pct-low"}`;
    }
    // Card large progress text
    let bigPctEl = card.querySelector(".card-big-pct");
    if (!bigPctEl) {
      bigPctEl = document.createElement("div");
      bigPctEl.className = "card-big-pct";
      card.appendChild(bigPctEl);
    }
    bigPctEl.textContent = pct > 0 ? `${pct}%` : "";

    const _pendingSt = t.subtask_count - t.verified_subtasks - t.running_subtasks - (t.review_subtasks || 0);
    // Card status text color
    const countsEl = card.querySelector(".card-counts");
    countsEl.className = `card-counts ${pct >= 100 ? "counts-done" : t.running_subtasks > 0 ? "counts-active" : "counts-idle"}`;
    countsEl.innerHTML =
      `<span class="cnt-icon cnt-v">✓${t.verified_subtasks}</span>/${t.subtask_count}` +
      (t.running_subtasks > 0 ? ` · <span class="cnt-icon cnt-r">▶${t.running_subtasks}</span>` : "") +
      (t.review_subtasks  > 0 ? ` · <span class="cnt-icon cnt-rv">⏸${t.review_subtasks}</span>`  : "") +
      (_pendingSt > 0 ? ` · <span class="cnt-icon cnt-p">◯${_pendingSt}</span>` : "");

    // Card step counter
    let stepEl = card.querySelector(".card-step-num");
    if (!stepEl) {
      stepEl = document.createElement("span");
      stepEl.className = "card-step-num";
      card.querySelector(".card-counts").after(stepEl);
    }
    if (t.step != null) stepEl.textContent = `s${t.step}`;

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
      const ringText = document.createElementNS(NS, "text");
      ringText.setAttribute("class", "ring-pct-text");
      ringText.setAttribute("x", "10"); ringText.setAttribute("y", "10");
      ringText.setAttribute("text-anchor", "middle"); ringText.setAttribute("dominant-baseline", "central");
      ringText.setAttribute("font-size", "6"); ringText.setAttribute("fill", "var(--dim)");
      ringEl.append(bgCircle, fgCircle, ringText);
      card.querySelector(".card-bar-bg").after(ringEl);
    }
    const _ringFg = ringEl.querySelector(".ring-fg");
    if (_ringFg) {
      const circ = 2 * Math.PI * 8;
      _ringFg.setAttribute("stroke-dashoffset", `${circ - (pct / 100) * circ}`);
      // Milestone color at 25/50/75/100%
      const _milestoneColor = pct >= 100 ? "var(--green)" : pct >= 75 ? "#22d3ee" : pct >= 50 ? "#eab308" : "var(--green)";
      _ringFg.setAttribute("stroke", _milestoneColor);
    }
    const _ringPctText = ringEl.querySelector(".ring-pct-text");
    if (_ringPctText) _ringPctText.textContent = pct > 0 ? `${pct}` : "";

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

    // Stalled warning badge
    let stalledBadge = card.querySelector(".card-stalled-badge");
    if (t.stalled_subtasks > 0) {
      if (!stalledBadge) {
        stalledBadge = document.createElement("span");
        stalledBadge.className = "card-stalled-badge";
        card.querySelector(".card-top").appendChild(stalledBadge);
      }
      stalledBadge.textContent = `⚠${t.stalled_subtasks}`;
      stalledBadge.title = `${t.stalled_subtasks} stalled subtask(s)`;
    } else if (stalledBadge) {
      stalledBadge.remove();
    }

    // Last verified subtask indicator
    let lastVEl = card.querySelector(".card-last-verified");
    const _lastV = _findLastVerified(t);
    if (_lastV) {
      if (!lastVEl) {
        lastVEl = document.createElement("div");
        lastVEl.className = "card-last-verified";
        card.appendChild(lastVEl);
      }
      lastVEl.textContent = `✓ ${_lastV}`;
      lastVEl.title = `Last verified: ${_lastV}`;
    } else if (lastVEl) {
      lastVEl.textContent = "";
    }

    // Card branch count badge
    let branchBadge = card.querySelector(".card-branch-count");
    if (_bEntries.length > 0) {
      if (!branchBadge) {
        branchBadge = document.createElement("span");
        branchBadge.className = "card-branch-count";
        card.querySelector(".card-counts").after(branchBadge);
      }
      branchBadge.textContent = `${_bEntries.length} branch${_bEntries.length !== 1 ? "es" : ""}`;
    }

    // Card goal text
    let goalEl = card.querySelector(".card-goal");
    if (t.goal) {
      if (!goalEl) {
        goalEl = document.createElement("div");
        goalEl.className = "card-goal";
        card.appendChild(goalEl);
      }
      goalEl.textContent = t.goal.substring(0, 60) + (t.goal.length > 60 ? "…" : "");
      goalEl.title = t.goal;
    } else if (goalEl) {
      goalEl.textContent = "";
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
      sparkEl.title = _bEntries.map(([bn], i) => `${bn}: ${bars[i]}%`).join("\n");
    }

    // Mini heatmap — colored cells showing per-subtask status
    let heatmapEl = card.querySelector(".card-heatmap");
    if (t.subtask_count > 0 && t.subtask_count <= 40) {
      if (!heatmapEl) {
        heatmapEl = document.createElement("div");
        heatmapEl.className = "card-heatmap";
        card.appendChild(heatmapEl);
      }
      const cells = _bEntries.flatMap(([, bd]) =>
        Object.values(bd.subtasks || {}).map(s => {
          const st = s.status || "Pending";
          return st === "Verified" ? "hm-v" : st === "Running" ? "hm-r" : st === "Review" ? "hm-rv" : "hm-p";
        })
      );
      heatmapEl.innerHTML = cells.map(c => `<span class="hm-cell ${c}"></span>`).join("");
    } else if (heatmapEl) {
      heatmapEl.remove();
    }

    // Failure count badge (subtasks with error/fail in output)
    let failBadge = card.querySelector(".card-fail-count");
    const _failCount = _bEntries.reduce((acc, [, bd]) => {
      return acc + Object.values(bd.subtasks || {}).filter(s =>
        s.status === "Running" && s.output && /error|fail|exception/i.test(s.output)
      ).length;
    }, 0);
    if (_failCount > 0) {
      if (!failBadge) {
        failBadge = document.createElement("span");
        failBadge.className = "card-fail-count";
        card.querySelector(".card-top").appendChild(failBadge);
      }
      failBadge.textContent = `✗${_failCount}`;
      failBadge.title = `${_failCount} subtask(s) with errors`;
    } else if (failBadge) {
      failBadge.remove();
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

    // Card ETA countdown
    let etaEl = card.querySelector(".card-eta");
    if (!etaEl) {
      etaEl = document.createElement("span");
      etaEl.className = "card-eta";
      card.appendChild(etaEl);
    }
    if (t.verified_subtasks > 0 && t.verified_subtasks < t.subtask_count && t.verify_rate > 0) {
      const remaining = t.subtask_count - t.verified_subtasks;
      const etaSteps = Math.round(remaining / t.verify_rate);
      etaEl.textContent = `~${etaSteps} steps`;
      etaEl.title = `ETA: ~${etaSteps} steps at ${t.verify_rate.toFixed(2)}/step`;
    } else {
      etaEl.textContent = "";
    }

    // Verified streak — consecutive verified subtasks from last
    let streakEl = card.querySelector(".card-streak");
    if (!streakEl) {
      streakEl = document.createElement("span");
      streakEl.className = "card-streak";
      card.appendChild(streakEl);
    }
    const _prevStreak = card._prevVerifiedCount ?? 0;
    const _curStreak = t.verified_subtasks || 0;
    if (_curStreak > _prevStreak && _curStreak >= 3) {
      streakEl.textContent = `🔥${_curStreak - _prevStreak}`;
      streakEl.title = `${_curStreak - _prevStreak} verified this cycle`;
    } else if (_curStreak >= 3 && _prevStreak > 0) {
      streakEl.textContent = "";
    }
    card._prevVerifiedCount = _curStreak;

    // Card task age
    let taskAgeEl = card.querySelector(".card-task-age");
    if (!taskAgeEl) {
      taskAgeEl = document.createElement("span");
      taskAgeEl.className = "card-task-age";
      card.appendChild(taskAgeEl);
    }
    if (t.created_at) {
      const _ageRel = _relativeTime(t.created_at);
      if (_ageRel) taskAgeEl.textContent = `📅${_ageRel}`;
      taskAgeEl.title = `Created: ${t.created_at}`;
    }

    // Recently active highlight (active within 60s)
    const _lastActiveSec = t.last_active ? (Date.now() - new Date(t.last_active).getTime()) / 1000 : Infinity;
    card.classList.toggle("card-recently-active", _lastActiveSec < 60);

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
  const refreshDot = document.getElementById("detail-refresh-dot");
  if (refreshDot) refreshDot.classList.add("spinning");
  try {
    const t = await api("/tasks/" + encodeURIComponent(id));
    state.tasksCache[id] = t;
    renderDetail(t);
  } catch (e) {
    toast("Could not load task detail: " + e.message);
  } finally {
    if (refreshDot) refreshDot.classList.remove("spinning");
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

  // Build DOM — breadcrumb navigation
  const breadcrumb = document.createElement("div");
  breadcrumb.className = "detail-breadcrumb";
  const bcTasks = document.createElement("span");
  bcTasks.className = "detail-bc-link";
  bcTasks.textContent = "Tasks";
  bcTasks.title = "Back to task grid";
  bcTasks.addEventListener("click", () => { state.selectedTask = null; document.querySelectorAll(".task-card.selected").forEach(c => c.classList.remove("selected")); el.replaceChildren(); });
  breadcrumb.append(bcTasks, document.createTextNode(" › "));
  const bcTask = document.createElement("span");
  bcTask.className = "detail-bc-current";
  bcTask.textContent = t.id;
  breadcrumb.appendChild(bcTask);

  const taskIdDiv = document.createElement("div");
  taskIdDiv.className = "detail-task-id";
  taskIdDiv.innerHTML = `<span class="detail-id-prefix">ID</span> ${t.id}`;
  taskIdDiv.title = "Click to copy task ID";
  taskIdDiv.style.cursor = "pointer";
  taskIdDiv.addEventListener("click", () => {
    navigator.clipboard.writeText(t.id).then(() => toast(`Copied: ${t.id}`)).catch(() => {});
  });

  // Task timer — elapsed since creation
  const taskTimer = document.createElement("span");
  taskTimer.className = "detail-task-timer";
  if (t.created_at) {
    const _taskElapsed = (Date.now() - new Date(t.created_at).getTime()) / 1000;
    const _th = Math.floor(_taskElapsed / 3600);
    const _tm = Math.floor((_taskElapsed % 3600) / 60);
    taskTimer.textContent = _th > 0 ? `⏱ ${_th}h${_tm}m` : `⏱ ${_tm}m`;
    taskTimer.title = `Created: ${t.created_at}`;
  }
  taskIdDiv.appendChild(taskTimer);

  // Last modified time
  const lastModEl = document.createElement("span");
  lastModEl.className = "detail-last-mod";
  if (t.last_active) {
    const _modRel = _relativeTime(t.last_active);
    if (_modRel) lastModEl.textContent = `✎${_modRel}`;
    lastModEl.title = `Last modified: ${t.last_active}`;
  }
  taskIdDiv.appendChild(lastModEl);

  // Task description/goal
  if (t.goal) {
    const goalDiv = document.createElement("div");
    goalDiv.className = "detail-goal";
    goalDiv.textContent = t.goal;
    goalDiv.title = t.goal;
    taskIdDiv.after(goalDiv);
  }

  const statusDiv = document.createElement("div");
  statusDiv.className = "detail-status";

  const badgeSpan = document.createElement("span");
  badgeSpan.className = `card-mini-badge ${statusClass(t.status)}`;
  badgeSpan.textContent = t.status || "Pending";
  statusDiv.appendChild(badgeSpan);

  // Task status chip — colored background chip
  const statusChip = document.createElement("span");
  statusChip.className = "detail-status-chip";
  const _chipColor = t.status === "Complete" ? "var(--green)" : t.status === "Running" ? "var(--cyan)" : "var(--yellow)";
  statusChip.style.cssText = `background:${_chipColor};color:#000;font-size:8px;padding:1px 6px;border-radius:8px;margin-left:6px`;
  statusChip.textContent = t.status || "Pending";
  statusDiv.appendChild(statusChip);

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
  const mdExportBtn = document.createElement("button");
  mdExportBtn.className = "toolbar-btn";
  mdExportBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  mdExportBtn.title = "Copy detail as Markdown";
  mdExportBtn.textContent = "📋 MD";
  mdExportBtn.addEventListener("click", () => {
    let md = `# ${t.id}\n**Status:** ${t.status || "Pending"}\n**Progress:** ${_verified}/${_total} (${pct}%)\n\n`;
    Object.entries(branches).forEach(([bname, bdata]) => {
      md += `## ${bname}\n`;
      Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
        const check = s.status === "Verified" ? "x" : " ";
        md += `- [${check}] ${sname} — ${s.status}\n`;
      });
      md += "\n";
    });
    navigator.clipboard.writeText(md).then(() => toast("Copied detail as Markdown")).catch(() => {});
  });
  statusDiv.append(" ", mdExportBtn);

  const jsonExportBtn = document.createElement("button");
  jsonExportBtn.className = "toolbar-btn";
  jsonExportBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  jsonExportBtn.title = "Download task detail as JSON";
  jsonExportBtn.textContent = "{ } JSON";
  jsonExportBtn.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(t, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${t.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast("Downloaded " + t.id + ".json");
  });
  statusDiv.append(" ", jsonExportBtn);

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

  const collapseVerifiedBtn = document.createElement("button");
  collapseVerifiedBtn.className = "toolbar-btn";
  collapseVerifiedBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:2px";
  collapseVerifiedBtn.title = "Collapse only verified branches";
  collapseVerifiedBtn.textContent = "▸ ✓";
  collapseVerifiedBtn.addEventListener("click", () => {
    document.querySelectorAll("#detail-content .branch-block").forEach(bb => {
      const dots = bb.querySelectorAll(".st-dot");
      const allGreen = dots.length > 0 && [...dots].every(d => d.classList.contains("dot-green"));
      if (allGreen) {
        bb.classList.add("collapsed");
        const arrow = bb.querySelector(".branch-collapse-arrow");
        if (arrow) arrow.textContent = "▸";
      }
    });
  });
  statusDiv.append(" ", collapseVerifiedBtn);

  // Copy all outputs button
  const copyAllBtn = document.createElement("button");
  copyAllBtn.className = "toolbar-btn";
  copyAllBtn.style.cssText = "font-size:9px;padding:2px 6px;margin-left:4px";
  copyAllBtn.title = "Copy all subtask outputs to clipboard";
  copyAllBtn.textContent = "📋 All";
  copyAllBtn.addEventListener("click", () => {
    const allOutputs = [];
    Object.entries(branches).forEach(([bn, bd]) => {
      Object.entries(bd.subtasks || {}).forEach(([sn, s]) => {
        if (s.output) allOutputs.push(`## ${sn} (${bn})\n${s.output}`);
      });
    });
    if (allOutputs.length === 0) { toast("No outputs to copy"); return; }
    navigator.clipboard.writeText(allOutputs.join("\n\n")).then(() => toast(`Copied ${allOutputs.length} outputs`)).catch(() => {});
  });
  statusDiv.append(" ", copyAllBtn);

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
      // Branch mini-ring SVG
      const NS = "http://www.w3.org/2000/svg";
      const miniRing = document.createElementNS(NS, "svg");
      miniRing.setAttribute("class", "branch-mini-ring");
      miniRing.setAttribute("width", "14");
      miniRing.setAttribute("height", "14");
      miniRing.setAttribute("viewBox", "0 0 14 14");
      const bgC = document.createElementNS(NS, "circle");
      bgC.setAttribute("cx", "7"); bgC.setAttribute("cy", "7"); bgC.setAttribute("r", "5");
      bgC.setAttribute("fill", "none"); bgC.setAttribute("stroke", "var(--bg3)"); bgC.setAttribute("stroke-width", "2");
      const fgC = document.createElementNS(NS, "circle");
      fgC.setAttribute("cx", "7"); fgC.setAttribute("cy", "7"); fgC.setAttribute("r", "5");
      fgC.setAttribute("fill", "none"); fgC.setAttribute("stroke", "var(--green)"); fgC.setAttribute("stroke-width", "2");
      fgC.setAttribute("stroke-linecap", "round"); fgC.setAttribute("transform", "rotate(-90 7 7)");
      const bCirc = 2 * Math.PI * 5;
      fgC.setAttribute("stroke-dasharray", `${bCirc}`);
      fgC.setAttribute("stroke-dashoffset", `${bCirc - (bpct / 100) * bCirc}`);
      miniRing.append(bgC, fgC);

      row.append(lbl, miniRing, trk, cnt);
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

  // Status filter pills
  const filterPills = document.createElement("div");
  filterPills.className = "detail-filter-pills";
  const _pillCounts = { All: _total, Verified: _verified, Running: _running, Review: _review, Pending: _pending };
  for (const [label, count] of Object.entries(_pillCounts)) {
    if (label !== "All" && count === 0) continue;
    const pill = document.createElement("button");
    pill.className = "detail-filter-pill";
    pill.dataset.filter = label;
    pill.textContent = `${label} (${count})`;
    pill.addEventListener("click", () => {
      filterPills.querySelectorAll(".detail-filter-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      localStorage.setItem("sb-detail-filter", label);
      const dc = document.getElementById("detail-content");
      dc.querySelectorAll(".subtask-row").forEach(row => {
        if (label === "All") { row.style.display = ""; return; }
        const dot = row.querySelector(".st-dot");
        const cls = dot?.className || "";
        const match = (label === "Verified" && cls.includes("green")) ||
                      (label === "Running" && cls.includes("cyan")) ||
                      (label === "Review" && cls.includes("yellow")) ||
                      (label === "Pending" && cls.includes("gray"));
        row.style.display = match ? "" : "none";
      });
    });
    // Restore saved filter
    const _savedFilter = localStorage.getItem("sb-detail-filter");
    if (_savedFilter === label && label !== "All") {
      pill.click();
    }
    filterPills.appendChild(pill);
  }

  // Status count summary
  const statusSummary = document.createElement("div");
  statusSummary.className = "detail-status-summary";
  const _parts = [];
  if (_verified > 0) _parts.push(`${_verified} verified`);
  if (_running > 0) _parts.push(`${_running} running`);
  if (_review > 0) _parts.push(`${_review} review`);
  if (_pending > 0) _parts.push(`${_pending} pending`);
  statusSummary.textContent = _parts.join(" · ");

  const stickyHeader = document.createElement("div");
  stickyHeader.className = "detail-sticky-header";
  // Detail inline search
  const detailSearch = document.createElement("input");
  detailSearch.type = "text";
  detailSearch.className = "detail-inline-search";
  detailSearch.placeholder = "Search subtasks…";
  detailSearch.addEventListener("input", () => {
    const q = detailSearch.value.trim().toLowerCase();
    document.querySelectorAll("#detail-content .subtask-row").forEach(row => {
      const name = (row.querySelector(".st-name")?.textContent || "").toLowerCase();
      const output = (row.querySelector(".st-output")?.textContent || "").toLowerCase();
      row.style.display = (!q || name.includes(q) || output.includes(q)) ? "" : "none";
    });
  });

  // Detail zoom controls
  const zoomWrap = document.createElement("span");
  zoomWrap.className = "detail-zoom-wrap";
  const zoomOut = document.createElement("button");
  zoomOut.className = "toolbar-btn detail-zoom-btn";
  zoomOut.textContent = "A−";
  zoomOut.title = "Decrease font size";
  zoomOut.addEventListener("click", () => {
    const cur = parseFloat(localStorage.getItem("sb-detail-zoom") || "1");
    const next = Math.max(0.7, cur - 0.1);
    localStorage.setItem("sb-detail-zoom", next.toFixed(1));
    el.style.fontSize = `${next}em`;
  });
  const zoomIn = document.createElement("button");
  zoomIn.className = "toolbar-btn detail-zoom-btn";
  zoomIn.textContent = "A+";
  zoomIn.title = "Increase font size";
  zoomIn.addEventListener("click", () => {
    const cur = parseFloat(localStorage.getItem("sb-detail-zoom") || "1");
    const next = Math.min(1.5, cur + 0.1);
    localStorage.setItem("sb-detail-zoom", next.toFixed(1));
    el.style.fontSize = `${next}em`;
  });
  zoomWrap.append(zoomOut, zoomIn);
  // Restore saved zoom
  const _savedZoom = localStorage.getItem("sb-detail-zoom");
  if (_savedZoom) el.style.fontSize = `${_savedZoom}em`;

  // Total output size
  const totalSizeEl = document.createElement("span");
  totalSizeEl.className = "detail-total-size";
  const _totalBytes = Object.values(branches).reduce((acc, bd) =>
    acc + Object.values(bd.subtasks || {}).reduce((a, s) => a + (s.output || "").length, 0), 0);
  if (_totalBytes > 0) {
    totalSizeEl.textContent = _totalBytes >= 1024 ? `${(_totalBytes / 1024).toFixed(1)}KB total` : `${_totalBytes}B total`;
  }

  // Auto-refresh timer
  const refreshTimer = document.createElement("span");
  refreshTimer.className = "detail-refresh-timer";
  refreshTimer.textContent = "just now";
  window._detailLastRefresh = Date.now();

  stickyHeader.append(taskIdDiv, progressRow, branchProgressDiv, branchSummary, statusSummary, filterPills, statusDiv, detailSearch, zoomWrap, totalSizeEl, refreshTimer);

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

  // Quick actions bar
  const actionsBar = document.createElement("div");
  actionsBar.className = "detail-actions-bar";
  const _actions = [
    { label: "↺ Reset", action: () => window.resetTask(t.id) },
    { label: "📋 Copy ID", action: () => navigator.clipboard.writeText(t.id).then(() => toast(`Copied: ${t.id}`)) },
    { label: "▶ Running", action: () => { const d = document.querySelector("#detail-content .st-dot.dot-cyan"); if (d) d.closest(".subtask-row")?.scrollIntoView({ behavior: "smooth", block: "center" }); } },
    { label: "⛶ Fullscreen", action: () => { document.getElementById("detail-panel")?.classList.toggle("detail-fullscreen"); } },
  ];
  _actions.forEach(a => {
    const btn = document.createElement("button");
    btn.className = "toolbar-btn detail-action-btn";
    btn.textContent = a.label;
    btn.addEventListener("click", a.action);
    actionsBar.appendChild(btn);
  });

  const nodes = [breadcrumb, stickyHeader, actionsBar, notesWrap];

  // Sort branches by completion % descending
  const _sortedBranches = Object.entries(branches).sort(([, a], [, b]) => {
    const sa = Object.values(a.subtasks || {}), sb = Object.values(b.subtasks || {});
    const pa = sa.length ? sa.filter(s => s.status === "Verified").length / sa.length : 0;
    const pb = sb.length ? sb.filter(s => s.status === "Verified").length / sb.length : 0;
    return pb - pa;
  });
  _sortedBranches.forEach(([bname, bdata]) => {
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
      // Inline pct bar
      branchPctSpan.style.cssText += `;background:linear-gradient(90deg,rgba(34,197,94,0.2) ${bPct}%,transparent ${bPct}%);padding:0 4px;border-radius:3px`;
    }
    const branchCountSpan = document.createElement("span");
    branchCountSpan.className = "branch-st-count";
    if (_bs) branchCountSpan.textContent = ` (${_bs.total})`;
    // Branch verified counter badge
    const branchVerifiedBadge = document.createElement("span");
    branchVerifiedBadge.className = "branch-verified-cnt";
    if (_bs && _bs.verified > 0) {
      branchVerifiedBadge.textContent = `${_bs.verified}✓`;
      branchVerifiedBadge.title = `${_bs.verified} of ${_bs.total} verified`;
    }
    // Branch health dot — based on stalled/running ratio
    const branchHealthDot = document.createElement("span");
    branchHealthDot.className = "branch-health-dot";
    if (_bs && _bs.running > 0) {
      const _stalledInBranch = Object.values(bdata.subtasks || {}).filter(s =>
        s.status === "Running" && s.last_update != null && (state.step || 0) - s.last_update >= 5
      ).length;
      if (_stalledInBranch > 0) {
        branchHealthDot.classList.add("health-warn");
        branchHealthDot.title = `${_stalledInBranch} stalled subtask(s)`;
      } else {
        branchHealthDot.classList.add("health-ok");
        branchHealthDot.title = "All running subtasks healthy";
      }
    }

    // Branch last-active timestamp
    const branchLastActive = document.createElement("span");
    branchLastActive.className = "branch-last-active";
    const _branchTimes = Object.values(bdata.subtasks || {}).map(s => s.last_update_time).filter(Boolean);
    if (_branchTimes.length > 0) {
      const _maxTime = _branchTimes.reduce((a, b) => a > b ? a : b);
      const _relBranch = _relativeTime(_maxTime);
      if (_relBranch) branchLastActive.textContent = _relBranch;
    }
    // Branch diff count — how many subtasks changed status since last render
    const branchDiffSpan = document.createElement("span");
    branchDiffSpan.className = "branch-diff-count";
    const _branchChanged = Object.entries(bdata.subtasks || {}).filter(([sn, st]) => {
      return _prevStatuses[sn] && _prevStatuses[sn] !== (st.status || "Pending");
    }).length;
    if (_branchChanged > 0) {
      branchDiffSpan.textContent = `Δ${_branchChanged}`;
      branchDiffSpan.title = `${_branchChanged} subtask(s) changed status`;
    }
    // Branch elapsed time — total running time across subtasks
    const branchElapsed = document.createElement("span");
    branchElapsed.className = "branch-elapsed";
    const _runningTimes = Object.values(bdata.subtasks || {}).filter(s => s.status === "Running" && s.started_at).map(s => (Date.now() - new Date(s.started_at).getTime()) / 1000);
    if (_runningTimes.length > 0) {
      const _totalSec = Math.round(_runningTimes.reduce((a, b) => a + b, 0));
      const _em = Math.floor(_totalSec / 60);
      branchElapsed.textContent = _em > 0 ? `⏱${_em}m` : `⏱${_totalSec}s`;
      branchElapsed.title = `Total running time: ${_em}m across ${_runningTimes.length} subtask(s)`;
    }
    // Branch running indicator — animated dot when subtasks are running
    const branchRunDot = document.createElement("span");
    branchRunDot.className = "branch-run-dot";
    if (_bs && _bs.running > 0) {
      branchRunDot.classList.add("active");
      branchRunDot.title = `${_bs.running} running`;
    }
    // Branch status summary line
    const branchStatusLine = document.createElement("span");
    branchStatusLine.className = "branch-status-line";
    if (_bs) {
      const _bPending = _bs.total - _bs.verified - _bs.running - (_bs.review || 0);
      branchStatusLine.textContent = `${_bs.verified}✓ ${_bs.running}▶ ${_bPending}◯`;
    }
    branchNameEl.append(collapseArrow, " " + bname, readinessDot, branchHealthDot, branchRunDot, branchPctSpan, branchCountSpan, branchVerifiedBadge, branchStatusLine, branchLastActive, branchElapsed, branchDiffSpan);
    branchNameEl.style.cursor = "pointer";
    // Restore collapsed state from localStorage
    const _collapseKey = `sb-branch-${t.id}-${bname}`;
    if (localStorage.getItem(_collapseKey) === "1") {
      branchBlock.classList.add("collapsed");
      collapseArrow.textContent = "▸";
    }
    // Collapse count indicator
    const collapseCountEl = document.createElement("span");
    collapseCountEl.className = "branch-collapse-count";
    branchNameEl.appendChild(collapseCountEl);
    const _updateCollapseCount = () => {
      const n = Object.keys(bdata.subtasks || {}).length;
      collapseCountEl.textContent = branchBlock.classList.contains("collapsed") ? `(${n} hidden)` : "";
    };
    branchNameEl.addEventListener("click", () => {
      branchBlock.classList.toggle("collapsed");
      const _isCollapsed = branchBlock.classList.contains("collapsed");
      collapseArrow.textContent = _isCollapsed ? "▸" : "▾";
      if (_isCollapsed) localStorage.setItem(_collapseKey, "1");
      else localStorage.removeItem(_collapseKey);
      _updateCollapseCount();
    });
    _updateCollapseCount();
    // Branch compact toggle — one-line summary vs full rows
    const compactToggle = document.createElement("button");
    compactToggle.className = "branch-compact-toggle toolbar-btn";
    compactToggle.style.cssText = "font-size:8px;padding:0 4px;margin-left:4px";
    compactToggle.textContent = "≡";
    compactToggle.title = "Toggle compact branch view";
    compactToggle.addEventListener("click", (ev) => {
      ev.stopPropagation();
      branchBlock.classList.toggle("branch-compact");
    });
    branchNameEl.appendChild(compactToggle);
    // Branch merge button — shown only on fully-verified branches
    if (_bs && _bs.verified === _bs.total && _bs.total > 0) {
      const mergeBtn = document.createElement("button");
      mergeBtn.className = "branch-merge-btn toolbar-btn";
      mergeBtn.textContent = "Merge ✓";
      mergeBtn.title = `All ${_bs.total} subtasks verified — ready to merge`;
      mergeBtn.style.cssText = "font-size:8px;padding:0 4px;margin-left:4px;color:#22c55e";
      mergeBtn.addEventListener("click", (ev) => { ev.stopPropagation(); toast(`${bname}: merge-ready (${_bs.total} verified)`); });
      branchNameEl.appendChild(mergeBtn);
    }
    // Branch subtask name list tooltip
    const _stNames = Object.keys(bdata.subtasks || {});
    if (_stNames.length > 0) {
      branchNameEl.title = `${bname} subtasks:\n${_stNames.join("\n")}`;
    }
    branchBlock.appendChild(branchNameEl);

    let _rowNum = 0;
    Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
      _rowNum++;
      const rawOutput = s.output || "";

      const row = document.createElement("div");
      row.className = "subtask-row";
      // Row number
      const rowNumEl = document.createElement("span");
      rowNumEl.className = "st-row-num";
      const _totalSt = Object.keys(bdata.subtasks || {}).length;
      rowNumEl.textContent = `#${_rowNum}`;
      rowNumEl.title = `Subtask ${_rowNum} of ${_totalSt}`;
      row.appendChild(rowNumEl);
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
      dot.title = `${s.status || "Pending"}${s.last_update != null ? ` — step ${s.last_update}` : ""}`;
      // Status emoji icon
      const stEmoji = document.createElement("span");
      stEmoji.className = "st-emoji";
      const _emojiMap = { Verified: "✓", Running: "▶", Review: "⏸", Pending: "◯" };
      stEmoji.textContent = _emojiMap[s.status] || "◯";

      const statusLabel = document.createElement("span");
      statusLabel.className = "st-status-label";
      statusLabel.textContent = s.status || "Pending";

      const nameSpan = document.createElement("span");
      nameSpan.className = "st-name st-name-copy";
      nameSpan.textContent = sname;
      nameSpan.title = "Click to copy name";
      nameSpan.addEventListener("click", (ev) => {
        ev.stopPropagation();
        navigator.clipboard.writeText(sname).then(() => toast(`Copied: ${sname}`)).catch(() => {});
      });

      // Priority indicator based on action_type
      const priSpan = document.createElement("span");
      priSpan.className = "st-priority";
      const _at = (s.action_type || "").toLowerCase();
      if (_at === "full_execution") { priSpan.textContent = "●"; priSpan.classList.add("pri-high"); priSpan.title = "High priority: full execution"; }
      else if (_at === "file_edit") { priSpan.textContent = "●"; priSpan.classList.add("pri-med"); priSpan.title = "Medium priority: file edit"; }
      else if (_at === "read_only" || _at === "analysis") { priSpan.textContent = "●"; priSpan.classList.add("pri-low"); priSpan.title = "Low priority: read only"; }

      // Status transition arrow (if recently changed)
      let transSpan = null;
      const _prev = _prevStatuses[sname];
      if (_prev && _prev !== (s.status || "Pending")) {
        transSpan = document.createElement("span");
        transSpan.className = "st-transition";
        transSpan.textContent = `${_prev}→${s.status}`;
      }

      // Subtask step number
      const stStep = document.createElement("span");
      stStep.className = "st-step-num";
      if (s.last_update != null) stStep.textContent = `s${s.last_update}`;

      // Subtask elapsed time
      const stElapsed = document.createElement("span");
      stElapsed.className = "st-elapsed";
      const _stTime = _relativeTime(s.last_update_time);
      if (_stTime) stElapsed.textContent = _stTime;

      // Duration timer for running subtasks
      const stDuration = document.createElement("span");
      stDuration.className = "st-duration";
      if (s.status === "Running" && s.started_at) {
        const _elapsed = (Date.now() - new Date(s.started_at).getTime()) / 1000;
        if (_elapsed > 0) {
          const _m = Math.floor(_elapsed / 60);
          const _s = Math.floor(_elapsed % 60);
          stDuration.textContent = _m > 0 ? `${_m}m${_s}s` : `${_s}s`;
          stDuration.title = `Running for ${_m}m ${_s}s`;
        }
      }

      row.append(cb, stEmoji, dot, statusLabel, nameSpan, priSpan);
      if (transSpan) row.appendChild(transSpan);
      row.appendChild(stStep);
      row.appendChild(stElapsed);
      row.appendChild(stDuration);

      // Output timestamp — when output was last updated
      if (rawOutput && s.output_updated_at) {
        const outTime = document.createElement("span");
        outTime.className = "st-out-time";
        const _outRel = _relativeTime(s.output_updated_at);
        if (_outRel) outTime.textContent = `📝${_outRel}`;
        outTime.title = `Output updated: ${s.output_updated_at}`;
        row.appendChild(outTime);
      }

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

      // Retry button (Running subtasks only — resets to Pending via /heal)
      if (s.status === "Running") {
        const retryBtn = document.createElement("button");
        retryBtn.className = "st-retry-btn";
        retryBtn.title = `Reset ${sname} to Pending`;
        retryBtn.textContent = "↻";
        retryBtn.addEventListener("click", async (ev) => {
          ev.stopPropagation();
          try {
            const r = await fetch(state.base + "/heal", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ subtask: sname }),
            });
            const d = await r.json();
            if (d.ok) toast(`↻ Reset ${sname} to Pending`);
            else toast(`Failed: ${d.reason || "unknown"}`);
          } catch (err) { toast("Retry failed: " + err.message); }
          if (state.selectedTask) selectTask(state.selectedTask);
        });
        row.appendChild(retryBtn);
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
        // Dependency count badge
        const depCntBadge = document.createElement("span");
        depCntBadge.className = "st-dep-count";
        depCntBadge.textContent = `${s.depends_on.length}↗`;
        depCntBadge.title = `${s.depends_on.length} dependencies`;
        depWrap.appendChild(depCntBadge);
        row.appendChild(depWrap);
      }

      // Output change indicator (shows "△" when output changed since last render)
      const _prevOutputs = window._prevSubtaskOutputs || {};
      const _prevOut = _prevOutputs[sname] || "";
      if (rawOutput && _prevOut && rawOutput !== _prevOut) {
        const changeBadge = document.createElement("span");
        changeBadge.className = "st-output-changed";
        changeBadge.textContent = "△";
        changeBadge.title = "Output changed since last poll";
        row.appendChild(changeBadge);
      }
      if (!window._prevSubtaskOutputs) window._prevSubtaskOutputs = {};
      window._prevSubtaskOutputs[sname] = rawOutput;

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

        // Byte size badge
        const _bytes = new Blob([rawOutput]).size;
        const sizeBadge = document.createElement("span");
        sizeBadge.className = "st-size-badge";
        sizeBadge.textContent = _bytes >= 1024 ? `${(_bytes / 1024).toFixed(1)}KB` : `${_bytes}B`;
        sizeBadge.title = `${_bytes} bytes`;
        row.appendChild(sizeBadge);

        // Truncation indicator — show "…" when output > 1KB
        if (_bytes > 1024) {
          const truncBadge = document.createElement("span");
          truncBadge.className = "st-trunc-badge";
          truncBadge.textContent = "…";
          truncBadge.title = `Output truncated (${sizeBadge.textContent})`;
          row.appendChild(truncBadge);
        }

        // Line count badge
        const lineCount = rawOutput.split("\n").length;
        if (lineCount > 1) {
          const lcBadge = document.createElement("span");
          lcBadge.className = "st-line-count";
          lcBadge.title = `${lineCount} lines`;
          lcBadge.textContent = `${lineCount}L`;
          row.appendChild(lcBadge);
        }

        const outSpan = document.createElement("span");
        outSpan.className = "st-output";
        outSpan.title = rawOutput.substring(0, 400);
        const _flatOut = rawOutput.replace(/\n/g, " ");
        // Syntax highlight keywords in output preview
        const _highlighted = _flatOut.substring(0, 80)
          .replace(/\b(error|fail(?:ed|ure)?|exception|traceback)\b/gi, '<span class="out-err">$1</span>')
          .replace(/\b(success|passed|verified|complete(?:d)?)\b/gi, '<span class="out-ok">$1</span>')
          .replace(/\b(warning|warn|deprecated)\b/gi, '<span class="out-warn">$1</span>');
        outSpan.innerHTML = _highlighted;
        row.appendChild(outSpan);

        // Show more toggle for long output
        if (_flatOut.length > 80) {
          const moreBtn = document.createElement("button");
          moreBtn.className = "st-show-more";
          moreBtn.textContent = "more";
          moreBtn.addEventListener("click", (ev) => {
            ev.stopPropagation();
            if (outSpan._expanded) {
              outSpan.textContent = _flatOut.substring(0, 80);
              moreBtn.textContent = "more";
              outSpan._expanded = false;
            } else {
              outSpan.textContent = _flatOut.substring(0, 300);
              moreBtn.textContent = "less";
              outSpan._expanded = true;
            }
          });
          row.appendChild(moreBtn);
        }

        // Copy output button
        const copyBtn = document.createElement("button");
        copyBtn.className = "st-copy-btn";
        copyBtn.title = "Copy output to clipboard";
        copyBtn.textContent = "📋";
        copyBtn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          navigator.clipboard.writeText(rawOutput).then(() => toast("Copied output")).catch(() => {});
        });
        row.appendChild(copyBtn);

        // Output word cloud — top 5 frequent words as mini tags
        if (rawOutput.length > 50) {
          const _stopWords = new Set(["the","a","an","is","are","was","were","to","of","in","for","on","and","or","it","this","that","with","as","at","by","from","not","be","has","have","had"]);
          const _words = rawOutput.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(w => w.length > 3 && !_stopWords.has(w));
          const _freq = {};
          _words.forEach(w => { _freq[w] = (_freq[w] || 0) + 1; });
          const _top = Object.entries(_freq).sort((a, b) => b[1] - a[1]).slice(0, 5);
          if (_top.length > 0) {
            const cloudSpan = document.createElement("span");
            cloudSpan.className = "st-word-cloud";
            _top.forEach(([w]) => {
              const tag = document.createElement("span");
              tag.className = "st-word-tag";
              tag.textContent = w;
              cloudSpan.appendChild(tag);
            });
            row.appendChild(cloudSpan);
          }
        }

        const expandBtn = document.createElement("button");
        expandBtn.className = "st-expand-btn";
        expandBtn.title = "Expand output";
        expandBtn.textContent = "▶";
        expandBtn.addEventListener("click", (event) => window.toggleExpand(expandBtn, event));

        const expandContent = document.createElement("div");
        expandContent.className = "st-expand-content";
        // Highlight error lines in expanded output
        const _outLines = rawOutput.split("\n").map(line => {
          if (/error|fail|exception|traceback/i.test(line)) return `<span class="out-line-err">${line.replace(/</g,"&lt;")}</span>`;
          return line.replace(/</g,"&lt;");
        });
        expandContent.innerHTML = _outLines.join("\n");

        // Output search input
        const outSearch = document.createElement("input");
        outSearch.type = "text";
        outSearch.className = "st-out-search";
        outSearch.placeholder = "Search output…";
        outSearch.addEventListener("click", (ev) => ev.stopPropagation());
        outSearch.addEventListener("input", () => {
          const q = outSearch.value.trim().toLowerCase();
          if (!q) { expandContent.innerHTML = _outLines.join("\n"); return; }
          const highlighted = _outLines.map(line => {
            const plain = line.replace(/<[^>]*>/g, "");
            if (plain.toLowerCase().includes(q)) return `<span class="out-line-match">${line}</span>`;
            return line;
          });
          expandContent.innerHTML = highlighted.join("\n");
        });

        row.append(expandBtn, outSearch, expandContent);
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

  // Auto-scroll to changed subtask
  if (_changedSt) {
    const changedRow = el.querySelector(`.st-name`);
    const allNames = el.querySelectorAll(".st-name");
    for (const nm of allNames) {
      if (nm.textContent === _changedSt) {
        const sr = nm.closest(".subtask-row");
        if (sr) {
          sr.scrollIntoView({ behavior: "smooth", block: "center" });
          sr.style.outline = "2px solid var(--cyan)";
          setTimeout(() => { sr.style.outline = ""; }, 2000);
        }
        break;
      }
    }
  }

  // Scroll progress indicator
  if (!el._scrollListenerAdded) {
    el._scrollListenerAdded = true;
    let scrollBar = document.getElementById("detail-scroll-progress");
    if (!scrollBar) {
      scrollBar = document.createElement("div");
      scrollBar.id = "detail-scroll-progress";
      scrollBar.className = "detail-scroll-progress";
      el.parentElement.insertBefore(scrollBar, el);
    }
    // Scroll-to-top floating button
    let scrollTopBtn = document.getElementById("detail-scroll-top");
    if (!scrollTopBtn) {
      scrollTopBtn = document.createElement("button");
      scrollTopBtn.id = "detail-scroll-top";
      scrollTopBtn.className = "detail-scroll-top-btn";
      scrollTopBtn.textContent = "↑";
      scrollTopBtn.title = "Scroll to top";
      scrollTopBtn.addEventListener("click", () => el.scrollTo({ top: 0, behavior: "smooth" }));
      el.parentElement.appendChild(scrollTopBtn);
    }
    el.addEventListener("scroll", () => {
      const sb = document.getElementById("detail-scroll-progress");
      if (!sb) return;
      const pctScroll = el.scrollHeight > el.clientHeight
        ? Math.round(el.scrollTop / (el.scrollHeight - el.clientHeight) * 100) : 0;
      sb.style.width = `${pctScroll}%`;
      const stb = document.getElementById("detail-scroll-top");
      if (stb) stb.style.display = el.scrollTop > 200 ? "block" : "none";
    });
  }

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

window._setTaskSort = function (mode) {
  _tasksSortMode = mode;
  localStorage.setItem("sb-task-sort", mode);
  applyTaskSearch();
};

window._applyTaskSearch = function () {
  _tasksSearchFilter = (document.getElementById("task-search")?.value || "").trim().toLowerCase();
  _tasksPage = 1;
  pollTasks();
};

window.filterSubtasks = function filterSubtasks() {
  const q = (document.getElementById("st-search").value || "").toLowerCase();
  let matchCount = 0, totalCount = 0;
  document.querySelectorAll("#detail-content .subtask-row").forEach(row => {
    totalCount++;
    const nameEl = row.querySelector(".st-name");
    const outEl = row.querySelector(".st-output");
    const name = (nameEl?.textContent || "").toLowerCase();
    const output = (outEl?.textContent || "").toLowerCase();
    const match = !q || name.includes(q) || output.includes(q);
    if (match) matchCount++;
    row.style.display = match ? "" : "none";
    // Highlight matching text
    if (nameEl) nameEl.innerHTML = q && name.includes(q) ? _highlightText(nameEl.textContent, q) : _escHtml(nameEl.textContent);
    if (outEl) outEl.innerHTML = q && output.includes(q) ? _highlightText(outEl.textContent, q) : _escHtml(outEl.textContent);
  });
  const stSearchCount = document.getElementById("st-search-count");
  if (stSearchCount) stSearchCount.textContent = q ? `${matchCount}/${totalCount}` : "";
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
      window._lastVerifiedSubtask = stName;
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
