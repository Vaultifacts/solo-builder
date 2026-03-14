/**
 * Keyboard shortcuts and focus management for the dashboard.
 * Extracted from dashboard.js to keep the main module focused on polling.
 */
import { state } from "./dashboard_state.js";
import { toast } from "./dashboard_utils.js";

/* ── Keyboard shortcuts ──────────────────────────────────── */
const _SHORTCUTS = [
  ["?", "Show/hide this shortcuts panel"],
  ["j / \u2193", "Select next task"],
  ["k / \u2191", "Select previous task"],
  ["Escape", "Close modal / shortcuts / panels"],
  ["p", "Pause/resume polling"],
  ["t", "Toggle dark/light theme"],
  ["/", "Focus task search"],
  ["1-9", "Switch to sidebar tab by position"],
  ["Ctrl+K", "Command palette"],
  ["Ctrl+Shift+E", "Copy task summary to clipboard"],
  ["g h", "Go to Health tab"],
  ["g s", "Go to Settings tab"],
  ["g b", "Go to Branches tab"],
  ["g m", "Go to Metrics tab"],
  ["c", "Copy selected task ID"],
  ["n", "Jump to next unverified task"],
  ["x", "Expand/collapse all branches"],
  ["d", "Toggle detail panel"],
  ["f", "Focus task search"],
  ["m", "Toggle mute"],
  ["w", "Toggle compact mode"],
  ["v", "Verify first unverified subtask"],
  ["a", "Select all task cards"],
  ["r", "Force refresh (immediate poll)"],
  ["b", "Branches tab"],
  ["s", "Subtasks tab"],
  ["h", "History tab"],
  ["l", "Journal tab"],
  ["o", "Open output modal for first subtask"],
  ["e", "Export selected task as markdown"],
  ["z", "Undo last verify (reset to Pending)"],
  ["q", "Cycle detail status filter"],
  ["u", "Scroll to first unverified subtask"],
  ["y", "Yank (copy) first subtask output"],
  ["Shift+R", "Reset selected task"],
  ["Shift+V", "Verify all unverified subtasks"],
  ["Shift+C", "Copy all subtask outputs"],
  ["Shift+D", "Download DAG as JSON"],
  ["Shift+S", "Trigger snapshot"],
  ["Shift+P", "Toggle pause auto-run"],
  ["Shift+X", "Expand all branches"],
  ["Shift+F", "Focus detail search"],
  ["Shift+G", "Go to first running subtask"],
  ["Shift+H", "Toggle history tab"],
];

function _showShortcuts() {
  let overlay = document.getElementById("shortcuts-overlay");
  if (overlay) { overlay.remove(); return; }
  overlay = document.createElement("div");
  overlay.id = "shortcuts-overlay";
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center";
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
  const card = document.createElement("div");
  card.style.cssText = "background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px 24px;max-width:360px;width:90%";
  const title = document.createElement("div");
  title.style.cssText = "font-size:14px;font-weight:bold;margin-bottom:10px;color:var(--cyan)";
  title.textContent = "Keyboard Shortcuts";
  card.appendChild(title);
  for (const [key, desc] of _SHORTCUTS) {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;padding:3px 0;font-size:11px";
    const k = document.createElement("span");
    k.style.cssText = "font-weight:bold;color:var(--text);min-width:80px";
    k.textContent = key;
    const d = document.createElement("span");
    d.style.color = "var(--dim)";
    d.textContent = desc;
    row.append(k, d);
    card.appendChild(row);
  }
  overlay.appendChild(card);
  document.body.appendChild(overlay);
  trapFocus(overlay);
}

export function trapFocus(container) {
  const focusable = () => container.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  const handler = (e) => {
    if (e.key !== "Tab") return;
    const els = [...focusable()];
    if (!els.length) return;
    const first = els[0], last = els[els.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  container.addEventListener("keydown", handler);
  const first = [...focusable()][0];
  if (first) first.focus();
}

async function _copyTaskSummary() {
  const t = state.selectedTask && state.tasksCache[state.selectedTask];
  if (!t) { toast("No task selected"); return; }
  const branches = t.branches || {};
  let total = 0, verified = 0, running = 0;
  const lines = [`## ${t.id}`, `Status: ${t.status || "Pending"}`, ""];
  Object.entries(branches).forEach(([bname, bdata]) => {
    lines.push(`### ${bname}`);
    Object.entries(bdata.subtasks || {}).forEach(([sname, s]) => {
      total++;
      if (s.status === "Verified") verified++;
      else if (s.status === "Running") running++;
      const mark = s.status === "Verified" ? "x" : " ";
      lines.push(`- [${mark}] ${sname} \u2014 ${s.status || "Pending"}`);
    });
    lines.push("");
  });
  lines.push(`Progress: ${verified}/${total} verified` + (running > 0 ? `, ${running} running` : ""));
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    toast("Task summary copied to clipboard", "success");
  } catch (_) { toast("Clipboard write failed", "error"); }
}

let _pendingG = false;
const _GO_MAP = { h: "health", s: "settings", b: "branches", m: "metrics", d: "diff", p: "priority", a: "agents", f: "forecast" };

/* ── Command palette (Ctrl+K) ──────────────────────────────── */
const _PALETTE_CMDS = [];

function _buildPaletteCmds() {
  _PALETTE_CMDS.length = 0;
  // Tabs
  [...document.querySelectorAll(".sidebar-tab")].forEach(t => {
    const name = t.dataset.tab || t.textContent.trim().toLowerCase();
    _PALETTE_CMDS.push({ label: `Tab: ${name}`, action: () => window.switchTab(name) });
  });
  // Tasks
  (state.allTasks || []).forEach(t => {
    _PALETTE_CMDS.push({ label: `Task: ${t.id}`, action: () => window.selectTask(t.id) });
  });
  // Actions
  _PALETTE_CMDS.push({ label: "Toggle theme", action: () => window.toggleTheme() });
  _PALETTE_CMDS.push({ label: "Pause/resume polling", action: () => { state.pollPaused = !state.pollPaused; toast(state.pollPaused ? "Polling paused" : "Polling resumed"); } });
  _PALETTE_CMDS.push({ label: "Copy task summary", action: () => _copyTaskSummary() });
  _PALETTE_CMDS.push({ label: "Toggle mute", action: () => window.toggleMute?.() });
  _PALETTE_CMDS.push({ label: "Keyboard shortcuts", action: () => _showShortcuts() });
}

function _showPalette() {
  let existing = document.getElementById("cmd-palette");
  if (existing) { existing.remove(); return; }
  _buildPaletteCmds();
  const overlay = document.createElement("div");
  overlay.id = "cmd-palette";
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:flex-start;justify-content:center;padding-top:20vh";
  overlay.addEventListener("click", (ev) => { if (ev.target === overlay) overlay.remove(); });
  const box = document.createElement("div");
  box.style.cssText = "background:var(--surface);border:1px solid var(--border);border-radius:8px;width:90%;max-width:400px;max-height:60vh;display:flex;flex-direction:column;overflow:hidden";
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Type to search commands...";
  input.style.cssText = "padding:10px 14px;font-size:13px;border:none;border-bottom:1px solid var(--border);background:transparent;color:var(--text);font-family:var(--font);outline:none";
  const list = document.createElement("div");
  list.style.cssText = "overflow-y:auto;max-height:50vh";
  let _sel = 0;

  function render(q) {
    const filtered = q ? _PALETTE_CMDS.filter(c => c.label.toLowerCase().includes(q.toLowerCase())) : _PALETTE_CMDS;
    _sel = Math.min(_sel, Math.max(0, filtered.length - 1));
    list.replaceChildren();
    filtered.forEach((cmd, i) => {
      const row = document.createElement("div");
      row.style.cssText = `padding:6px 14px;font-size:11px;cursor:pointer;${i === _sel ? "background:var(--cyan);color:#000" : "color:var(--text)"}`;
      row.textContent = cmd.label;
      row.addEventListener("click", () => { overlay.remove(); cmd.action(); });
      row.addEventListener("mouseenter", () => { _sel = i; render(input.value); });
      list.appendChild(row);
    });
  }

  input.addEventListener("input", () => { _sel = 0; render(input.value); });
  input.addEventListener("keydown", (ev) => {
    const q = input.value;
    const filtered = q ? _PALETTE_CMDS.filter(c => c.label.toLowerCase().includes(q.toLowerCase())) : _PALETTE_CMDS;
    if (ev.key === "ArrowDown") { ev.preventDefault(); _sel = Math.min(_sel + 1, filtered.length - 1); render(q); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); _sel = Math.max(_sel - 1, 0); render(q); }
    else if (ev.key === "Enter" && filtered[_sel]) { overlay.remove(); filtered[_sel].action(); }
    else if (ev.key === "Escape") { overlay.remove(); }
  });

  box.append(input, list);
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  render("");
  input.focus();
}

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "k") {
    e.preventDefault();
    _showPalette();
    return;
  }
  if (e.ctrlKey && e.shiftKey && e.key === "E") {
    e.preventDefault();
    _copyTaskSummary();
    return;
  }
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
  if (e.target.classList.contains("sidebar-tab")) return;
  const key = e.key;
  if (_pendingG) {
    _pendingG = false;
    const tab = _GO_MAP[key];
    if (tab) { window.switchTab(tab); return; }
  }
  if (key === "g") { _pendingG = true; setTimeout(() => { _pendingG = false; }, 500); return; }
  if (key === "?") { _showShortcuts(); return; }
  if (key === "Escape") {
    const sc = document.getElementById("shortcuts-overlay");
    if (sc) { sc.remove(); return; }
    const modal = document.querySelector(".modal-overlay[style*='flex']");
    if (modal) { modal.style.display = "none"; return; }
    const deps = document.querySelector(".detail-deps-panel");
    if (deps) { deps.remove(); return; }
    const tl = document.querySelector(".detail-tl-panel");
    if (tl) { tl.remove(); return; }
    return;
  }
  if (key === "j" || key === "ArrowDown") {
    e.preventDefault();
    const cards = [...document.querySelectorAll(".task-card")];
    if (!cards.length) return;
    const cur = cards.findIndex(c => c.classList.contains("selected"));
    const next = cur < cards.length - 1 ? cur + 1 : 0;
    cards[next].click();
    cards[next].scrollIntoView({ block: "nearest" });
    return;
  }
  if (key === "k" || key === "ArrowUp") {
    e.preventDefault();
    const cards = [...document.querySelectorAll(".task-card")];
    if (!cards.length) return;
    const cur = cards.findIndex(c => c.classList.contains("selected"));
    const prev = cur > 0 ? cur - 1 : cards.length - 1;
    cards[prev].click();
    cards[prev].scrollIntoView({ block: "nearest" });
    return;
  }
  if (key === "/") { e.preventDefault(); const si = document.getElementById("task-search"); if (si) si.focus(); return; }
  if (key === "p") { state.pollPaused = !state.pollPaused; toast(state.pollPaused ? "Polling paused" : "Polling resumed"); return; }
  if (key === "t") { window.toggleTheme(); return; }
  if (key === "u") {
    const dots = document.querySelectorAll("#detail-content .st-dot:not(.dot-green)");
    if (dots.length > 0) {
      const row = dots[0].closest(".subtask-row");
      if (row) { row.scrollIntoView({ behavior: "smooth", block: "center" }); row.style.outline = "2px solid var(--yellow)"; setTimeout(() => { row.style.outline = ""; }, 1500); }
    } else { toast("All subtasks verified"); }
    return;
  }
  if (key === "e") { _copyTaskSummary(); return; }
  if (key === "z") {
    const lastV = window._lastVerifiedSubtask;
    if (lastV) {
      fetch(state.base + "/heal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subtask: lastV }),
      }).then(r => r.json()).then(d => {
        if (d.ok) toast(`↺ Undid verify: ${lastV} → Pending`);
        else toast("Undo failed");
      }).catch(() => toast("Undo failed"));
    } else { toast("No recent verify to undo"); }
    return;
  }
  if (key === "H" && e.shiftKey) {
    window.switchTab?.("history");
    return;
  }
  if (key === "G" && e.shiftKey) {
    const dot = document.querySelector("#detail-content .st-dot.dot-cyan");
    if (dot) { const row = dot.closest(".subtask-row"); if (row) { row.scrollIntoView({ behavior: "smooth", block: "center" }); row.style.outline = "2px solid var(--cyan)"; setTimeout(() => { row.style.outline = ""; }, 1500); } }
    else { toast("No running subtasks"); }
    return;
  }
  if (key === "F" && e.shiftKey) {
    const ds = document.querySelector(".detail-inline-search");
    if (ds) { ds.focus(); e.preventDefault(); } else { toast("No detail panel open"); }
    return;
  }
  if (key === "X" && e.shiftKey) {
    window.expandAllBranches?.();
    toast("Expanded all branches");
    return;
  }
  if (key === "P" && e.shiftKey) {
    fetch(state.base + (state.pollPaused ? "/resume" : "/pause"), { method: "POST" })
      .then(() => { state.pollPaused = !state.pollPaused; toast(state.pollPaused ? "Auto paused" : "Auto resumed"); })
      .catch(() => toast("Failed"));
    return;
  }
  if (key === "S" && e.shiftKey) {
    fetch(state.base + "/snapshot", { method: "POST" }).then(() => toast("Snapshot triggered")).catch(() => toast("Snapshot failed"));
    return;
  }
  if (key === "D" && e.shiftKey) {
    fetch(state.base + "/dag/export").then(r => r.blob()).then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "dag_export.json"; a.click();
      URL.revokeObjectURL(url);
      toast("DAG downloaded");
    }).catch(() => toast("Download failed"));
    return;
  }
  if (key === "C" && e.shiftKey && !e.ctrlKey) {
    const outputs = [...document.querySelectorAll("#detail-content .st-expand-content")].map(el => el.textContent).filter(Boolean);
    if (outputs.length > 0) {
      navigator.clipboard.writeText(outputs.join("\n---\n")).then(() => toast(`Copied ${outputs.length} outputs`)).catch(() => toast("Copy failed"));
    } else { toast("No outputs to copy"); }
    return;
  }
  if (key === "V" && e.shiftKey) {
    const cbs = document.querySelectorAll("#detail-content .st-checkbox");
    if (cbs.length > 0) {
      cbs.forEach(cb => { cb.checked = true; });
      window.detailBulkVerify?.();
    } else { toast("No subtasks to verify"); }
    return;
  }
  if (key === "R" && e.shiftKey) {
    if (state.selectedTask) { window.resetTask?.(state.selectedTask); toast(`Reset: ${state.selectedTask}`); }
    else { toast("No task selected"); }
    return;
  }
  if (key === "r") { toast("Refreshing…"); window.tick?.(); return; }
  if (key === "q") {
    const pills = [...document.querySelectorAll(".detail-filter-pill")];
    if (pills.length > 0) {
      const activeIdx = pills.findIndex(p => p.classList.contains("active"));
      const nextIdx = (activeIdx + 1) % pills.length;
      pills[nextIdx].click();
      toast(`Filter: ${pills[nextIdx].dataset.filter || pills[nextIdx].textContent}`);
    }
    return;
  }
  if (key === "l") { window.switchTab?.("journal"); return; }
  if (key === "y") {
    const outEl = document.querySelector("#detail-content .st-expand-content");
    if (outEl && outEl.textContent) {
      navigator.clipboard.writeText(outEl.textContent).then(() => toast("Output copied")).catch(() => toast("Copy failed"));
    } else { toast("No output to copy"); }
    return;
  }
  if (key === "o") {
    const row = document.querySelector("#detail-content .subtask-row");
    if (row) { row.click(); } else { toast("No subtask rows visible"); }
    return;
  }
  if (key >= "1" && key <= "9") {
    const tabs = [...document.querySelectorAll(".sidebar-tab")];
    const idx = parseInt(key) - 1;
    if (tabs[idx]) { tabs[idx].click(); }
    return;
  }
});
