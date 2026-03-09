import { api, esc } from "./dashboard_utils.js";

const _journalExpanded = new Set();

/* ── Journal ─────────────────────────────────────────────── */
export async function pollJournal() {
  try {
    const d = await api("/journal");
    _renderJournal(d.entries);
  } catch (_) {}
}

function _placeholder(text) {
  const d = document.createElement("div");
  d.className = "detail-placeholder";
  d.textContent = text;
  return d;
}

function _renderJournal(entries) {
  const el = document.getElementById("journal-content");
  if (!entries || entries.length === 0) {
    el.replaceChildren(_placeholder("No journal entries."));
    return;
  }
  const TRUNC = 300;
  const reversed = [...entries].reverse();
  const nodes = reversed.map(e => {
    const raw = e.output || "";
    const long = raw.length > TRUNC;
    const key  = `${e.step}-${e.subtask}`;
    const expanded = long && _journalExpanded.has(key);

    const entry = document.createElement("div");
    entry.className = "journal-entry";

    const meta = document.createElement("div");
    meta.className = "journal-meta";
    meta.textContent = `${e.subtask} · ${e.task} / ${e.branch} · Step ${e.step}`;

    const body = document.createElement("div");
    body.className = "journal-body";
    body.textContent = long && !expanded ? raw.substring(0, TRUNC) + "…" : raw;

    entry.append(meta, body);

    if (long) {
      const btn = document.createElement("button");
      btn.className = "journal-toggle";
      btn.dataset.full = raw;
      btn.dataset.trunc = TRUNC;
      btn.dataset.key = key;
      btn.textContent = expanded ? "▲ less" : "▼ more";
      btn.addEventListener("click", () => window.toggleJournal(btn));
      entry.appendChild(btn);
    }
    return entry;
  });
  el.replaceChildren(...nodes);
  const pane = document.getElementById("tab-journal");
  if (pane && pane.classList.contains("active") && _journalExpanded.size === 0) pane.scrollTop = 0;
}

window.toggleJournal = function (btn) {
  const body = btn.previousElementSibling;
  const full  = btn.dataset.full;
  const trunc = parseInt(btn.dataset.trunc, 10) || 300;
  const key   = btn.dataset.key;
  if (btn.textContent.includes("more")) {
    body.textContent = full;
    btn.textContent = "▲ less";
    _journalExpanded.add(key);
  } else {
    body.textContent = full.substring(0, trunc) + "…";
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
    if (el) el.replaceChildren(_placeholder("No diff data."));
    return;
  }
  const nodes = d.diff.split("\n").map(line => {
    const div = document.createElement("div");
    const cls = line.startsWith("+") ? "diff-add" : line.startsWith("-") ? "diff-del" : "";
    div.className = `diff-line ${cls}`.trim();
    div.textContent = line;
    return div;
  });
  if (el) el.replaceChildren(...nodes);
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
  const entries = Object.entries(d);
  if (entries.length === 0) {
    el.replaceChildren(_placeholder("No stats yet."));
    return;
  }
  const nodes = entries.map(([k, v]) => {
    const row = document.createElement("div");
    row.className = "diff-entry";
    row.style.fontSize = "10px";
    const lbl = document.createElement("span");
    lbl.style.cssText = "color:var(--cyan);min-width:120px;display:inline-block";
    lbl.textContent = k;
    const val = document.createElement("span");
    val.textContent = String(v);
    row.append(lbl, val);
    return row;
  });
  el.replaceChildren(...nodes);
}
