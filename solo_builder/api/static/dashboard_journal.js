import { api, esc } from "./dashboard_utils.js";

const _journalExpanded = new Set();

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
