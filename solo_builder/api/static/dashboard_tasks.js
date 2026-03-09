import { state } from "./dashboard_state.js";
import { api, esc, statusClass, dotClass, toast, updateNotifBadge, checkStaleBanner, playCompletionSound } from "./dashboard_utils.js";

const _journalExpanded = new Set();

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
    document.getElementById("hdr-total").textContent    = d.total;
    document.getElementById("hdr-bar").style.width      = d.pct + "%";
    document.getElementById("hdr-pct").textContent      = d.pct + "%";
    document.getElementById("hdr-step").textContent     = `Step ${d.step} / ${d.total} — ${d.verified} verified`;
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
    const d = await api("/tasks");
    state.allTasks = d.tasks || [];
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
      card.innerHTML = `
        <div class="card-top">
          <span class="card-id">${esc(t.id)}</span>
          <span class="card-mini-badge ${statusClass(t.status)}">${esc(t.status || "Pending")}</span>
        </div>
        <div class="card-deps"></div>
        <div class="card-bar-bg"><div class="card-bar-fg" style="width:0%"></div></div>
        <div class="card-counts"></div>`;
      card.addEventListener("click", () => selectTask(t.id));
      grid.appendChild(card);
    }
    card.querySelector(".card-mini-badge").className = `card-mini-badge ${statusClass(t.status)}`;
    card.querySelector(".card-mini-badge").textContent = t.status || "Pending";
    card.classList.toggle("active",  t.id === state.selectedTask);
    card.classList.toggle("blocked", isBlocked);

    const pct = t.subtask_count > 0 ? Math.round(t.verified_subtasks / t.subtask_count * 100) : 0;
    card.querySelector(".card-bar-fg").style.width = pct + "%";
    card.querySelector(".card-counts").textContent =
      `${t.verified_subtasks}/${t.subtask_count} verified` +
      (t.running_subtasks > 0 ? ` · ${t.running_subtasks} running` : "");

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
  document.querySelectorAll(".task-card").forEach(c => c.classList.toggle("active", c.dataset.id === id));
  try {
    const t = await api("/tasks/" + encodeURIComponent(id));
    state.tasksCache[id] = t;
    renderDetail(t);
  } catch (e) {
    toast("Could not load task detail: " + e.message);
  }
}
window.selectTask = selectTask;

export function renderDetail(t) {
  const el = document.getElementById("detail-content");
  let html = `<div class="detail-task-id">${esc(t.id)}</div>`;
  html += `<div class="detail-status"><span class="card-mini-badge ${statusClass(t.status)}">${esc(t.status || "Pending")}</span>`;
  if (t.depends_on && t.depends_on.length) {
    html += ` <span style="color:#ff9800;font-size:10px">← ${esc(t.depends_on.join(", "))}</span>`;
  }
  html += `</div>`;

  const branches = t.branches || {};
  Object.entries(branches).forEach(([bname, bdata]) => {
    html += `<div class="branch-block"><div class="branch-name">${esc(bname)}</div>`;
    const subtasks = bdata.subtasks || {};
    Object.entries(subtasks).forEach(([sname, s]) => {
      const output = (s.output || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      const preview = output ? output.replace(/\n/g, " ").substring(0, 80) : esc(s.description || "");
      const previewHtml = preview
        ? `<span class="st-output" title="${output.substring(0, 400).replace(/"/g, "&quot;")}">${preview}</span>`
        : "";
      const snameJson = JSON.stringify(sname);
      const expandBtn = output
        ? `<button class="st-expand-btn" title="Expand output" onclick="toggleExpand(this,event)">&#9654;</button>`
        : "";
      const expandContent = output
        ? `<div class="st-expand-content">${output}</div>`
        : "";
      html += `
        <div class="subtask-row" onclick='showModal(${snameJson}, ${JSON.stringify(s).replace(/'/g, "&#39;")})'>
          <div class="st-dot ${dotClass(s.status)}"></div>
          <span class="st-name">${esc(sname)}</span>
          ${previewHtml}
          ${expandBtn}
          ${expandContent}
        </div>`;
    });
    html += `</div>`;
  });

  const _prevStatuses = window._prevSubtaskStatuses || {};
  const _newStatuses = {};
  let _changedSt = null;
  Object.entries(branches).forEach(([bname, bdata]) => {
    Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
      _newStatuses[sname] = s.status || "Pending";
      if (_prevStatuses[sname] && _prevStatuses[sname] !== _newStatuses[sname]) {
        _changedSt = sname;
      }
    });
  });
  window._prevSubtaskStatuses = _newStatuses;

  el.innerHTML = html;

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
  btn.innerHTML = open ? "&#9660;" : "&#9654;";
};

window.filterSubtasks = function filterSubtasks() {
  const q = (document.getElementById("st-search").value || "").toLowerCase();
  document.querySelectorAll("#detail-content .subtask-row").forEach(row => {
    const name = (row.querySelector(".st-name")?.textContent || "").toLowerCase();
    const output = (row.querySelector(".st-output")?.textContent || "").toLowerCase();
    row.style.display = (!q || name.includes(q) || output.includes(q)) ? "" : "none";
  });
};

/* ── Journal ─────────────────────────────────────────────── */
export async function pollJournal() {
  try {
    const d = await api("/journal");
    _renderJournal(d.entries);
  } catch (_) {}
}

function _renderJournal(entries) {
  const el = document.getElementById("journal-content");
  if (!entries || entries.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">No journal entries.</div>`;
    return;
  }
  const TRUNC = 300;
  const reversed = [...entries].reverse();
  el.innerHTML = reversed.map(e => {
    const safe = (e.output || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const long = safe.length > TRUNC;
    const key  = `${e.step}-${e.subtask}`;
    const expanded = long && _journalExpanded.has(key);
    const body = long && !expanded ? safe.substring(0, TRUNC) + "…" : safe;
    const btn  = long
      ? `<button class="journal-toggle" onclick="toggleJournal(this)" data-full="${safe.replace(/"/g, "&quot;")}" data-trunc="${TRUNC}" data-key="${key}">${expanded ? "▲ less" : "▼ more"}</button>`
      : "";
    return `<div class="journal-entry">
      <div class="journal-meta">${esc(e.subtask)} · ${esc(e.task)} / ${esc(e.branch)} · Step ${e.step}</div>
      <div class="journal-body">${body}</div>${btn}
    </div>`;
  }).join("");
  const pane = document.getElementById("tab-journal");
  if (pane && pane.classList.contains("active") && _journalExpanded.size === 0) pane.scrollTop = 0;
}

window.toggleJournal = function (btn) {
  const body = btn.previousElementSibling;
  const full = btn.dataset.full;
  const trunc = parseInt(btn.dataset.trunc, 10) || 300;
  const key  = btn.dataset.key;
  if (btn.textContent.includes("more")) {
    body.innerHTML = full;
    btn.textContent = "▲ less";
    _journalExpanded.add(key);
  } else {
    body.innerHTML = full.substring(0, trunc) + "…";
    btn.textContent = "▼ more";
    _journalExpanded.delete(key);
  }
};

/* ── Diff panel ──────────────────────────────────────────── */
export async function pollDiff() {
  try {
    const d = await api("/diff");
    _renderDiff(d);
  } catch (_) {}
}

function _renderDiff(d) {
  const el = document.getElementById("diff-content");
  if (!d || !d.diff) {
    if (el) el.innerHTML = `<div class="detail-placeholder">No diff data.</div>`;
    return;
  }
  if (el) el.innerHTML = d.diff.split("\n").map(line => {
    const cls = line.startsWith("+") ? "diff-add" : line.startsWith("-") ? "diff-del" : "";
    return `<div class="diff-line ${cls}">${line.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>`;
  }).join("");
}

/* ── Stats panel ─────────────────────────────────────────── */
export async function pollStats() {
  try {
    const d = await api("/stats");
    _renderStats(d);
  } catch (_) {}
}

function _renderStats(d) {
  const el = document.getElementById("stats-content");
  if (!d || !el) return;
  let html = "";
  Object.entries(d).forEach(([k, v]) => {
    html += `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:120px;display:inline-block">${esc(k)}</span> <span>${esc(v)}</span></div>`;
  });
  el.innerHTML = html || `<div class="detail-placeholder">No stats yet.</div>`;
}
