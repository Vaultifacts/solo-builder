import { state } from "./dashboard_state.js";
import { api, esc, statusClass, toast, flash, updateNotifBadge } from "./dashboard_utils.js";
import { pollStatus, pollTasks, renderGrid, selectTask, renderDetail, applyTaskSearch, pollJournal, pollDiff, pollStats, pollTaskProgress, updateTabBadges } from "./dashboard_tasks.js";
import { pollHistory, historyPageStep, pollBranches, pollSettings, pollPriority, pollStalled, pollSubtasks, pollAgents, pollForecast, pollMetrics, pollCache, pollCacheHistory, pollHealthDetailed, pollGatesDetailed, pollPolicyDetailed, pollContextWindowDetailed, pollThreatModelDetailed, pollSloDetailed, pollPromptRegressionDetailed, pollDebtScanDetailed, pollCiQualityDetailed, pollPreReleaseDetailed, pollLiveSummaryDetailed, pollRepoHealthDetailed } from "./dashboard_panels.js";

/* ── Health / uptime ─────────────────────────────────────── */
async function pollHealth() {
  try {
    const h = await api("/health");
    const el = document.getElementById("hdr-uptime");
    if (!el) return;
    const s = Math.floor(h.uptime_s || 0);
    const hh = Math.floor(s / 3600);
    const mm = Math.floor((s % 3600) / 60);
    const ss = s % 60;
    const label = hh > 0
      ? `up ${hh}h${String(mm).padStart(2,"0")}m`
      : mm > 0
        ? `up ${mm}m${String(ss).padStart(2,"0")}s`
        : `up ${ss}s`;
    el.textContent = label;
    el.title = `Server uptime: ${s}s · step ${h.step}`;
  } catch (_) {}
}

/* ── Performance profiling (?perf=1) ──────────────────────── */
const _perfMode = new URLSearchParams(location.search).has("perf");
const _perfHistory = [];
const _PERF_WINDOW = 30;

/* ── Polling loop ────────────────────────────────────────── */
let _tickCount = 0;
async function tick() {
  if (state.pollPaused) return;
  _tickCount++;
  const _t0 = _perfMode ? performance.now() : 0;
  const progressPoll = state.selectedTask ? pollTaskProgress(state.selectedTask) : Promise.resolve();
  /* Fast pollers: every tick (2s default) */
  const fast = [pollStatus(), pollTasks(), pollJournal(), pollHistory(), progressPoll];
  /* Medium pollers: every 5th tick (~10s), tab-aware */
  if (_tickCount % 5 === 0) {
    const activeTab = document.querySelector(".sidebar-tab.active");
    const tab = activeTab ? (activeTab.dataset.tab || "") : "";
    fast.push(pollSettings());
    /* Only poll data for the active tab + always-visible panels */
    if (tab === "diff") fast.push(pollDiff());
    if (tab === "stats") fast.push(pollStats());
    if (tab === "branches") fast.push(pollBranches());
    if (tab === "priority") fast.push(pollPriority());
    if (tab === "stalled") fast.push(pollStalled());
    if (tab === "subtasks") fast.push(pollSubtasks());
    if (tab === "agents") fast.push(pollAgents());
    if (tab === "forecast") fast.push(pollForecast());
    if (tab === "metrics") fast.push(pollMetrics());
    if (tab === "cache" || tab === "cache-history") fast.push(pollCache(), pollCacheHistory());
  }
  /* Slow pollers: every 15th tick (~30s) — health widgets change rarely */
  if (_tickCount % 15 === 0 || _tickCount === 1) {
    fast.push(pollHealth(), pollHealthDetailed(), pollGatesDetailed(), pollPolicyDetailed(),
              pollContextWindowDetailed(), pollThreatModelDetailed(), pollSloDetailed(),
              pollPromptRegressionDetailed(), pollDebtScanDetailed(), pollCiQualityDetailed(),
              pollPreReleaseDetailed(), pollLiveSummaryDetailed(), pollRepoHealthDetailed());
  }
  await Promise.all(fast);
  // Update tab badges from cached state
  try {
    const sd = await api("/stalled");
    updateTabBadges(sd.count || 0, null);
  } catch (_) {}
  if (state.selectedTask && state.tasksCache[state.selectedTask]) {
    try {
      const fresh = await api("/tasks/" + encodeURIComponent(state.selectedTask));
      state.tasksCache[state.selectedTask] = fresh;
      renderDetail(fresh);
    } catch (_) {}
  }
  if (state.viewMode === "graph") renderGraph();
  if (_perfMode) {
    const elapsed = performance.now() - _t0;
    const ms = elapsed.toFixed(1);
    const dom = document.querySelectorAll("*").length;
    const mem = performance.memory ? (performance.memory.usedJSHeapSize / 1048576).toFixed(1) + "MB" : "n/a";
    _perfHistory.push(elapsed);
    if (_perfHistory.length > _PERF_WINDOW) _perfHistory.shift();
    const avg = (_perfHistory.reduce((a, b) => a + b, 0) / _perfHistory.length).toFixed(1);
    const warn = elapsed > 500 ? " ⚠ SLOW" : "";
    console.log(`[perf] tick#${_tickCount} ${ms}ms (avg${avg}ms) | ${fast.length} polls | ${dom} DOM | heap ${mem}${warn}`);
  }
}
window.tick = tick;

/* ── Toolbar actions ─────────────────────────────────────── */
window.runAuto = async function () {
  const n = Math.max(1, parseInt(document.getElementById("auto-n").value || "10", 10));
  const btn = document.getElementById("btn-auto");
  btn.disabled = true;
  let prevStep = -1;
  for (let i = 0; i < n; i++) {
    btn.textContent = `⏳ ${i+1}/${n}`;
    try {
      const r = await fetch("/run", { method: "POST" });
      const d = await r.json();
      if (!d.ok) { toast("⏩ " + (d.reason || "Pipeline complete")); break; }
      if (prevStep < 0) prevStep = d.step;
      const deadline = Date.now() + 60000;
      while (Date.now() < deadline) {
        await new Promise(res => setTimeout(res, 700));
        try {
          const hb = await api("/heartbeat");
          document.getElementById("hdr-verified").textContent = hb.verified;
          document.getElementById("hdr-running").textContent  = hb.running;
          document.getElementById("hdr-pending").textContent  = hb.pending;
          document.getElementById("hdr-total").textContent    = hb.total;
          if (hb.total > 0) {
            const pct = Math.round(hb.verified / hb.total * 100);
            document.getElementById("hdr-bar").style.width = pct + "%";
            document.getElementById("hdr-pct").textContent = pct + "%";
          }
          document.getElementById("hdr-step").textContent = "Step " + hb.step;
          btn.textContent = `⏳ ${i+1}/${n} · ${hb.verified}✓`;
          if (state.selectedTask) pollTaskProgress(state.selectedTask);
          if (hb.verified === hb.total && hb.total > 0) { await tick(); i = n; break; }
          if (hb.step > prevStep) { prevStep = hb.step; break; }
        } catch (_) {}
      }
      await tick();
    } catch (_) { break; }
  }
  btn.textContent = "⏩ Auto";
  btn.disabled = false;
};

window.exportOutputs = async function () {
  const btn = document.getElementById("btn-export");
  btn.textContent = "⏳…";
  try {
    const r = await fetch("/export", { method: "POST" });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      toast("⚠ " + (d.error || d.reason || "No outputs yet — run some steps first."));
      btn.textContent = "⬇ Export";
      return;
    }
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "solo_builder_outputs.md";
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
    btn.textContent = "✓ Downloaded";
    setTimeout(() => { btn.textContent = "⬇ Export"; }, 2000);
  } catch (_) {
    toast("⚠ Export request failed.");
    btn.textContent = "⬇ Export";
  }
};

window.runStep = async function () {
  state.tabFocused = true;
  updateNotifBadge(state.prevStep);
  const btn = document.getElementById("btn-run");
  btn.disabled = true;
  btn.textContent = "⏳ Sent…";
  try {
    const r = await fetch("/run", { method: "POST" });
    const d = await r.json();
    btn.textContent = d.ok ? "✓ Triggered" : "✗ " + (d.reason || "error");
    setTimeout(() => { btn.textContent = "▶ Run Step"; btn.disabled = false; }, 1500);
    if (d.ok) setTimeout(tick, 600);
  } catch (_) {
    btn.textContent = "✗ Error";
    setTimeout(() => { btn.textContent = "▶ Run Step"; btn.disabled = false; }, 1500);
  }
};

window.stopRun = async function () {
  const btn = document.getElementById("btn-stop");
  btn.disabled = true;
  btn.textContent = "⏳ Stopping…";
  try {
    const r = await fetch("/stop", { method: "POST" });
    const d = await r.json();
    btn.textContent = d.ok ? "✓ Stopped" : "⏹ Stop";
    setTimeout(() => { btn.textContent = "⏹ Stop"; btn.disabled = false; }, 2000);
  } catch (_) {
    btn.textContent = "✗ Error";
    setTimeout(() => { btn.textContent = "⏹ Stop"; btn.disabled = false; }, 2000);
  }
};

/* ── Command toolbar ─────────────────────────────────────── */
function _findTaskForSubtask(stName) {
  stName = (stName || "").toUpperCase();
  for (const [tid, t] of Object.entries(state.tasksCache)) {
    for (const b of Object.values(t.branches || {})) {
      for (const sn of Object.keys(b.subtasks || {})) {
        if (sn.toUpperCase() === stName) return tid;
      }
    }
  }
  return null;
}

async function _postCmd(url, body, fbId, subtaskHint) {
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const d = await r.json();
    flash(fbId, d.ok ? "✓" : "✗ " + (d.reason || "error"));
    if (d.ok) {
      if (subtaskHint) {
        const tid = _findTaskForSubtask(subtaskHint);
        if (tid) selectTask(tid);
      }
      setTimeout(tick, 600);
    }
  } catch (e) {
    flash(fbId, "✗ Error");
  }
}

window.cmdVerify = function () {
  const st   = document.getElementById("cmd-verify-st").value.trim();
  const note = document.getElementById("cmd-verify-note").value.trim() || "Dashboard verify";
  if (!st) { flash("fb-verify", "Enter subtask"); return; }
  _postCmd("/verify", {subtask: st, note: note}, "fb-verify", st);
  document.getElementById("cmd-verify-st").value = "";
  document.getElementById("cmd-verify-note").value = "";
};

window.cmdDescribe = function () {
  const st   = document.getElementById("cmd-desc-st").value.trim();
  const desc = document.getElementById("cmd-desc-text").value.trim();
  if (!st || !desc) { flash("fb-desc", "Enter subtask + prompt"); return; }
  _postCmd("/describe", {subtask: st, desc: desc}, "fb-desc", st);
  document.getElementById("cmd-desc-st").value = "";
  document.getElementById("cmd-desc-text").value = "";
};

window.cmdTools = function () {
  const st    = document.getElementById("cmd-tools-st").value.trim();
  const tools = document.getElementById("cmd-tools-list").value.trim();
  if (!st || !tools) { flash("fb-tools", "Enter subtask + tools"); return; }
  _postCmd("/tools", {subtask: st, tools: tools}, "fb-tools", st);
  document.getElementById("cmd-tools-st").value = "";
  document.getElementById("cmd-tools-list").value = "";
};

window.cmdSet = function () {
  const raw = document.getElementById("cmd-set-key").value.trim();
  if (!raw || !raw.includes("=")) { flash("fb-set", "Format: KEY=VALUE"); return; }
  const [key, ...rest] = raw.split("=");
  const value = rest.join("=").trim();
  if (!key.trim() || !value) { flash("fb-set", "Format: KEY=VALUE"); return; }
  _postCmd("/set", {key: key.trim(), value: value}, "fb-set");
  document.getElementById("cmd-set-key").value = "";
};

/* ── Subtask modal ─────────────────────────────────────── */
let _modalSt = null;

function _renderModal(stName, d) {
  const status = d.status || "Pending";
  document.getElementById("modal-title").textContent = stName;
  const statusWrap = document.getElementById("modal-status-wrap");
  const statusSpan = document.createElement("span");
  statusSpan.className = `modal-status ${statusClass(status)}`;
  statusSpan.textContent = status;
  statusWrap.replaceChildren(statusSpan);
  document.getElementById("modal-desc").textContent = d.description || "(no description)";
  document.getElementById("modal-output").textContent = d.output || "(no output yet)";
  const tlWrap = document.getElementById("modal-timeline-wrap");
  const history = d.history || [];
  if (history.length > 0) {
    const colorMap = {Running: "var(--cyan)", Verified: "var(--green)", Review: "var(--yellow)", Pending: "var(--dim)"};
    const _mkTlEntry = (status, step) => {
      const entry = document.createElement("span"); entry.className = "timeline-entry";
      const dot = document.createElement("span"); dot.className = "timeline-dot";
      dot.style.background = colorMap[status] || "var(--dim)";
      entry.appendChild(dot);
      entry.appendChild(document.createTextNode(" " + status));
      if (step !== undefined) {
        const stepSpan = document.createElement("span");
        stepSpan.style.color = "var(--dim)"; stepSpan.textContent = ` (step ${step})`;
        entry.appendChild(stepSpan);
      }
      return entry;
    };
    const tlNodes = [_mkTlEntry("Pending", undefined)];
    for (const h of history) {
      const arrow = document.createElement("span"); arrow.className = "timeline-arrow"; arrow.textContent = "→";
      tlNodes.push(arrow, _mkTlEntry(h.status, h.step));
    }
    document.getElementById("modal-timeline").replaceChildren(...tlNodes);
    tlWrap.style.display = "";
  } else {
    tlWrap.style.display = "none";
  }
  const toolsWrap = document.getElementById("modal-tools-wrap");
  if (d.tools) {
    toolsWrap.style.display = "";
    document.getElementById("modal-tools").textContent = d.tools;
  } else {
    toolsWrap.style.display = "none";
  }
}

window.showModal = function (stName, stData) {
  _modalSt = stName;
  _renderModal(stName, stData);
  document.getElementById("modal-overlay").classList.add("show");
  api("/timeline/" + encodeURIComponent(stName))
    .then(d => { if (_modalSt === stName) _renderModal(stName, d); })
    .catch(() => {});
};

window.closeModal = function () {
  document.getElementById("modal-overlay").classList.remove("show");
  _modalSt = null;
};

window.openKeysModal = function () {
  document.getElementById("keys-overlay").style.display = "flex";
  api("/shortcuts").then(function (d) {
    const tbl = document.getElementById("shortcuts-table");
    if (!tbl) return;
    const tblRows = (d.shortcuts || []).map(function (s) {
      const tr = document.createElement("tr");
      const td1 = document.createElement("td"); td1.style.cssText = "color:var(--cyan);width:120px";
      const kbd = document.createElement("kbd"); kbd.textContent = s.key; td1.appendChild(kbd);
      const td2 = document.createElement("td"); td2.style.color = "var(--dim)"; td2.textContent = s.description;
      tr.append(td1, td2); return tr;
    });
    tbl.replaceChildren(...tblRows);
  }).catch(function () {});
};

window.closeKeysModal = function () {
  document.getElementById("keys-overlay").style.display = "none";
};

window.fireWebhook = async function () {
  const btn = document.getElementById("btn-fire-webhook");
  const fb  = document.getElementById("fb-webhook");
  if (btn) btn.disabled = true;
  try {
    const d = await fetch(state.base + "/webhook", {method: "POST"}).then(r => r.json());
    if (fb) { fb.textContent = d.ok ? "Sent" : (d.reason || d.error || "Failed"); fb.style.color = d.ok ? "var(--green)" : "var(--red)"; }
    if (d.ok) toast("Webhook fired");
  } catch (e) {
    if (fb) { fb.textContent = "Network error"; fb.style.color = "var(--red)"; }
  } finally {
    if (btn) btn.disabled = false;
  }
};

window.togglePollPause = function () {
  state.pollPaused = !state.pollPaused;
  const btn = document.getElementById("btn-poll-pause");
  if (state.pollPaused) {
    btn.textContent = "▶ Resume";
    btn.style.background = "#2a1a1a";
    btn.style.color = "#f77";
    btn.style.borderColor = "#733";
  } else {
    btn.textContent = "⏸ Pause";
    btn.style.background = "#1a2a1a";
    btn.style.color = "#6f6";
    btn.style.borderColor = "#373";
    tick();
  }
};

/* ── Subtask detail modal ─────────────────────────────────── */
window.openSubtaskModal = function (ev) {
  const statusColor = s => ({Verified:"var(--green)",Running:"var(--cyan)",Review:"var(--yellow)",Pending:"var(--dim)"})[s] || "var(--text)";
  document.getElementById("sd-title").textContent  = ev.subtask;
  document.getElementById("sd-task").textContent   = ev.task;
  document.getElementById("sd-branch").textContent = ev.branch;
  document.getElementById("sd-step").textContent   = ev.step;
  const sdStatus = document.getElementById("sd-status");
  sdStatus.textContent = ev.status === "Review" ? "Review ⏸" : ev.status;
  sdStatus.style.color = statusColor(ev.status);
  document.getElementById("sd-output").textContent = ev.output || "(no output)";
  document.getElementById("sd-sparkline").replaceChildren();
  const _modal = document.getElementById("st-modal-overlay");
  _modal.style.display = "flex";
  trapFocus(_modal);
  api("/timeline/" + encodeURIComponent(ev.subtask)).then(function (td) {
    const hist = td.history || [];
    const sparkEl = document.getElementById("sd-sparkline");
    if (!sparkEl) return;
    if (hist.length === 0) { sparkEl.replaceChildren(); return; }
    const W = 300, H = 36, pad = 4;
    const NS = "http://www.w3.org/2000/svg";
    const statusVal = {Pending:1, Running:2, Review:3, Verified:4};
    const statusClr = {Pending:"var(--dim)", Running:"var(--cyan)", Review:"var(--yellow)", Verified:"var(--green)"};
    const header = document.createElement("div");
    header.style.cssText = "font-size:10px;color:var(--dim);margin-bottom:3px";
    header.textContent = `Timeline (${hist.length} transition${hist.length !== 1 ? "s" : ""})`;
    const tlSvg = document.createElementNS(NS, "svg");
    tlSvg.setAttribute("width", W); tlSvg.setAttribute("height", H);
    tlSvg.style.cssText = "display:block;overflow:visible";
    const pts = hist.map((h, i) => {
      const v = statusVal[h.status] || 1;
      const x = pad + (hist.length < 2 ? (W - 2*pad)/2 : i / (hist.length - 1) * (W - 2*pad));
      const y = H - pad - ((v - 1) / 3) * (H - 2*pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    const poly = document.createElementNS(NS, "polyline");
    poly.setAttribute("points", pts); poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", "var(--border)"); poly.setAttribute("stroke-width", "1");
    tlSvg.appendChild(poly);
    hist.forEach((h, i) => {
      const v = statusVal[h.status] || 1;
      const x = pad + (hist.length < 2 ? (W - 2*pad)/2 : i / (hist.length - 1) * (W - 2*pad));
      const y = H - pad - ((v - 1) / 3) * (H - 2*pad);
      const circle = document.createElementNS(NS, "circle");
      circle.setAttribute("cx", x.toFixed(1)); circle.setAttribute("cy", y.toFixed(1));
      circle.setAttribute("r", "3"); circle.setAttribute("fill", statusClr[h.status] || "var(--dim)");
      const titleEl = document.createElementNS(NS, "title"); titleEl.textContent = `${h.status} @ step ${h.step}`;
      circle.appendChild(titleEl);
      tlSvg.appendChild(circle);
    });
    const legend = document.createElement("div");
    legend.style.cssText = "display:flex;gap:10px;font-size:9px;margin-top:2px;color:var(--dim)";
    [["var(--dim)","▪ Pending"],["var(--cyan)","▪ Running"],["var(--yellow)","▪ Review"],["var(--green)","▪ Verified"]].forEach(([c, t]) => {
      const s = document.createElement("span"); s.style.color = c; s.textContent = t; legend.appendChild(s);
    });
    sparkEl.replaceChildren(header, tlSvg, legend);
  }).catch(function () {});
};

window.closeSubtaskModal = function () {
  document.getElementById("st-modal-overlay").style.display = "none";
};

/* ── Modal action buttons ─────────────────────────────────── */
window.modalVerify = function () {
  if (!_modalSt) return;
  _postCmd("/verify", {subtask: _modalSt, note: "Dashboard modal verify"}, "fb-verify", _modalSt);
  window.closeModal();
};

window.modalDescribe = function () {
  if (!_modalSt) return;
  const desc = prompt("Enter new prompt for " + _modalSt + ":");
  if (!desc) return;
  _postCmd("/describe", {subtask: _modalSt, desc: desc}, "fb-desc", _modalSt);
  window.closeModal();
};

window.modalTools = function () {
  if (!_modalSt) return;
  const tools = prompt("Enter tools for " + _modalSt + " (e.g. Read,Glob,Grep or none):");
  if (!tools) return;
  _postCmd("/tools", {subtask: _modalSt, tools: tools}, "fb-tools", _modalSt);
  window.closeModal();
};

window.modalRenameShow = function () {
  const wrap  = document.getElementById("modal-rename-wrap");
  const input = document.getElementById("modal-rename-input");
  input.value = document.getElementById("modal-desc").textContent || "";
  wrap.style.display = "";
  input.focus();
};

window.modalRenameSubmit = function () {
  if (!_modalSt) return;
  const desc = document.getElementById("modal-rename-input").value.trim();
  if (!desc) { flash("fb-rename", "Enter a description"); return; }
  _postCmd("/rename", {subtask: _modalSt, desc: desc}, "fb-rename", _modalSt);
  document.getElementById("modal-rename-wrap").style.display = "none";
  setTimeout(() => {
    api("/timeline/" + encodeURIComponent(_modalSt))
      .then(d => { if (_modalSt) _renderModal(_modalSt, d); })
      .catch(() => {});
  }, 800);
};

/* ── Keyboard shortcuts ───────────────────────────────────── */
document.addEventListener("keydown", function (e) {
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return;

  if (e.key === "Escape") {
    window.closeModal(); window.closeKeysModal(); window.closeSubtaskModal();
    const np = document.getElementById("notif-panel");
    if (np) np.style.display = "none";
    const ts = document.getElementById("task-search");
    if (ts && ts.value) { ts.value = ""; applyTaskSearch(); }
    const ss = document.getElementById("st-search");
    if (ss && ss.value) { ss.value = ""; window.filterSubtasks(); }
    return;
  }
  if (e.key === "?") { window.openKeysModal(); return; }
  if (e.key === "p") { window.togglePollPause(); return; }

  if (e.key === "j" || e.key === "k") {
    if (state.taskIds.length === 0) return;
    const cur = state.taskIds.indexOf(state.selectedTask);
    let next;
    if (e.key === "j") next = cur < 0 ? 0 : Math.min(cur + 1, state.taskIds.length - 1);
    else               next = cur <= 0 ? state.taskIds.length - 1 : cur - 1;
    selectTask(state.taskIds[next]);
    return;
  }

  if (e.key === "v" && state.selectedTask && state.tasksCache[state.selectedTask]) {
    const t = state.tasksCache[state.selectedTask];
    for (const b of Object.values(t.branches || {})) {
      for (const [sn, s] of Object.entries(b.subtasks || {})) {
        if (s.status !== "Verified") {
          _postCmd("/verify", {subtask: sn, note: "Keyboard verify"}, "fb-verify", sn);
          return;
        }
      }
    }
    return;
  }

  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const historyPane = document.getElementById("tab-history");
    if (historyPane && historyPane.classList.contains("active")) {
      historyPageStep(e.key === "ArrowRight" ? 1 : -1);
      e.preventDefault();
      return;
    }
  }

  if (e.key === "n") {
    // Jump to next task with unverified subtasks
    for (const tid of state.taskIds) {
      const t = state.tasksCache[tid];
      if (!t) continue;
      if (t.verified_subtasks < t.subtask_count) {
        selectTask(tid);
        toast(`Jumped to ${tid}`);
        return;
      }
    }
    toast("All tasks fully verified");
    return;
  }
  if (e.key === "c" && state.selectedTask) {
    navigator.clipboard.writeText(state.selectedTask).then(() => toast(`Copied: ${state.selectedTask}`)).catch(() => {});
    return;
  }
  if (e.key === "x" && state.selectedTask) {
    const collapsed = document.querySelectorAll("#detail-content .branch-block.collapsed");
    if (collapsed.length > 0) window.expandAllBranches();
    else window.collapseAllBranches();
    return;
  }
  if (e.key === "d") {
    const dp = document.querySelector(".detail-panel");
    if (dp) dp.style.display = dp.style.display === "none" ? "" : "none";
    return;
  }
  if (e.key === "f") {
    const ts = document.getElementById("task-search");
    if (ts) { ts.focus(); ts.select(); e.preventDefault(); }
    return;
  }
  if (e.key === "m") {
    const isMuted = localStorage.getItem("sb-mute") === "1" ? "0" : "1";
    localStorage.setItem("sb-mute", isMuted);
    const mb = document.getElementById("btn-mute");
    if (mb) mb.textContent = isMuted === "1" ? "🔇" : "🔔";
    toast(isMuted === "1" ? "Sound muted" : "Sound unmuted");
    return;
  }
  if (e.key === "i" && state.selectedTask && state.tasksCache[state.selectedTask]) {
    const t = state.tasksCache[state.selectedTask];
    const branches = Object.keys(t.branches || {}).length;
    toast(`${t.id}: ${t.verified_subtasks}/${t.subtask_count} verified, ${t.running_subtasks} running, ${branches} branches`);
    return;
  }
  if (e.key === "w") {
    window.toggleCompactMode();
    return;
  }
  if (e.key === "v" && state.selectedTask && state.tasksCache[state.selectedTask]) {
    const t = state.tasksCache[state.selectedTask];
    for (const b of Object.values(t.branches || {})) {
      for (const [sn, s] of Object.entries(b.subtasks || {})) {
        if (s.status !== "Verified") {
          window._quickVerify(sn);
          return;
        }
      }
    }
    toast("All subtasks already verified");
    return;
  }
  if (e.key === "a") {
    const cards = document.querySelectorAll(".task-card:not([style*='display: none'])");
    if (cards.length === 0) return;
    cards.forEach(c => {
      const tid = c.dataset.id;
      if (tid) { c.classList.add("multi-selected"); c.click && c.dispatchEvent(new MouseEvent("click", { shiftKey: true })); }
    });
    toast(`Selected ${cards.length} task(s)`);
    return;
  }
  if (e.key === "r") { window.runStep(); return; }
  if (e.key === "g") { window.toggleView(); return; }
  if (e.key === "b") { window.switchTab("branches"); return; }
  if (e.key === "s") { window.switchTab("subtasks"); return; }
  if (e.key === "h") { window.switchTab("history"); return; }

  if (e.key === "Enter" && state.selectedTask && state.tasksCache[state.selectedTask] && !_modalSt) {
    const t = state.tasksCache[state.selectedTask];
    for (const b of Object.values(t.branches || {})) {
      for (const [sn, s] of Object.entries(b.subtasks || {})) {
        if (s.status !== "Verified") { window.showModal(sn, s); return; }
      }
    }
    return;
  }
});

/* ── Search / filter ──────────────────────────────────────── */
let _filterText = "";

window.applyFilter = function () {
  _filterText = (document.getElementById("search-input").value || "").toLowerCase();
  document.querySelectorAll(".task-card").forEach(card => {
    const id    = (card.dataset.id || "").toLowerCase();
    const badge = (card.querySelector(".card-mini-badge")?.textContent || "").toLowerCase();
    const match = !_filterText || id.includes(_filterText) || badge.includes(_filterText);
    card.style.display = match ? "" : "none";
  });
  document.querySelectorAll(".subtask-row").forEach(row => {
    const name   = (row.querySelector(".st-name")?.textContent || "").toLowerCase();
    const output = (row.querySelector(".st-output")?.textContent || "").toLowerCase();
    const match  = !_filterText || name.includes(_filterText) || output.includes(_filterText);
    row.style.display = match ? "" : "none";
  });
};

/* ── DAG graph view (extracted to dashboard_graph.js) ─────── */
import { renderGraph } from "./dashboard_graph.js";

/* ── Theme toggle ─────────────────────────────────────────── */
function _applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("btn-theme").textContent = theme === "dark" ? "🌙" : "☀️";
}
{ const saved = localStorage.getItem("sb-theme");
  const osTheme = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  _applyTheme(saved || osTheme);
}
{ const mb = document.getElementById("btn-mute"); if (mb) mb.textContent = localStorage.getItem("sb-mute") === "1" ? "🔇" : "🔔"; }

window.toggleTheme = function () {
  const next = (localStorage.getItem("sb-theme") || "dark") === "dark" ? "light" : "dark";
  localStorage.setItem("sb-theme", next);
  _applyTheme(next);
};

window.setPollInterval = function (ms) {
  state.pollMs = ms;
  localStorage.setItem("sb-poll-ms", ms);
  if (state.pollIntervalId !== null) clearInterval(state.pollIntervalId);
  state.pollIntervalId = setInterval(() => { tick(); _startCountdown(); }, state.pollMs);
  _startCountdown();
};

// Restore poll interval dropdown
const pollSel = document.getElementById("poll-interval-select");
if (pollSel) pollSel.value = String(state.pollMs);

/* ── Header clock ──────────────────────────────────────────── */
function _updateClock() {
  const el = document.getElementById("hdr-clock");
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
_updateClock();
setInterval(_updateClock, 1000);

/* ── Poll countdown timer ──────────────────────────────────── */
let _countdownId = null;
let _countdownLeft = 0;
function _startCountdown() {
  _countdownLeft = Math.round(state.pollMs / 1000);
  const el = document.getElementById("poll-countdown");
  if (el) el.textContent = `${_countdownLeft}s`;
  if (_countdownId) clearInterval(_countdownId);
  _countdownId = setInterval(() => {
    if (state.pollPaused) return;
    _countdownLeft = Math.max(0, _countdownLeft - 1);
    const el = document.getElementById("poll-countdown");
    if (el) el.textContent = `${_countdownLeft}s`;
  }, 1000);
}

tick();
_startCountdown();
state.pollIntervalId = setInterval(() => { tick(); _startCountdown(); }, state.pollMs);

/* ── Keyboard shortcuts (extracted to dashboard_keyboard.js) ── */
import { trapFocus } from "./dashboard_keyboard.js";
