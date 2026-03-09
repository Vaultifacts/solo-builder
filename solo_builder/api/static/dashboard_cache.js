import { api, esc, toast } from "./dashboard_utils.js";

/* ── DOM helpers ─────────────────────────────────────────── */
function _div(cssText) {
  const el = document.createElement("div");
  if (cssText) el.style.cssText = cssText;
  return el;
}

function _span(cssText, text) {
  const el = document.createElement("span");
  if (cssText) el.style.cssText = cssText;
  el.textContent = text;
  return el;
}

function _statRow(label, value) {
  const row = _div("font-size:10px");
  row.className = "diff-entry";
  const lbl = _span("color:var(--cyan);min-width:130px;display:inline-block", label);
  row.appendChild(lbl);
  row.appendChild(document.createTextNode(" " + value));
  return row;
}

/* ── Cache panel ─────────────────────────────────────────── */
export async function pollCache() {
  try {
    const d = await api("/cache");
    const el = document.getElementById("cache-content");
    if (!el) return;
    const entries   = d.entries ?? 0;
    const tokens    = d.estimated_tokens_held ?? 0;
    const dir       = d.cache_dir ?? "—";
    const cumHits   = d.cumulative_hits ?? 0;
    const cumMisses = d.cumulative_misses ?? 0;
    const hitRate   = d.cumulative_hit_rate != null ? d.cumulative_hit_rate.toFixed(1) + "%" : "—";

    const hdr1 = _div("font-size:10px;color:var(--dim);margin-bottom:4px");
    hdr1.textContent = "This session:";

    const dirRow = _div("font-size:10px;word-break:break-all");
    dirRow.className = "diff-entry";
    const dirLbl = _span("color:var(--cyan);min-width:130px;display:inline-block", "Cache dir");
    const dirVal = _span("color:var(--dim)", esc(dir));
    dirRow.appendChild(dirLbl);
    dirRow.appendChild(document.createTextNode(" "));
    dirRow.appendChild(dirVal);

    const hdr2 = _div("font-size:10px;color:var(--dim);margin:6px 0 4px");
    hdr2.textContent = "All sessions:";

    const btn = document.createElement("button");
    btn.className = "toolbar-btn";
    btn.textContent = "Clear Cache";
    btn.onclick = window.clearCache;
    const btnWrap = _div("margin-top:8px");
    btnWrap.appendChild(btn);

    el.replaceChildren(
      hdr1,
      _statRow("Entries on disk", entries),
      _statRow("Est. tokens held", tokens.toLocaleString()),
      hdr2,
      _statRow("Cumulative hits", cumHits.toLocaleString()),
      _statRow("Cumulative misses", cumMisses.toLocaleString()),
      _statRow("Hit rate", hitRate),
      dirRow,
      btnWrap,
    );
  } catch (_) {}
}

window.clearCache = async function () {
  try {
    await fetch("/cache", { method: "DELETE" });
    await pollCache();
  } catch (_) {}
};

/* ── Cache history panel (incremental) ───────────────────── */
let _cacheHistoryLastSession  = 0;
let _cacheHistoryAllSessions  = [];
let _cacheHistoryCumHits      = 0;
let _cacheHistoryCumMisses    = 0;

export async function pollCacheHistory() {
  try {
    const url = _cacheHistoryLastSession > 0
      ? `/cache/history?since=${_cacheHistoryLastSession}`
      : `/cache/history`;
    const d = await api(url);
    const el = document.getElementById("cache-history-content");
    if (!el) return;
    (d.sessions || []).forEach(s => {
      if (s.session > _cacheHistoryLastSession) {
        _cacheHistoryAllSessions.push(s);
        _cacheHistoryLastSession = s.session;
      }
    });
    _cacheHistoryCumHits   = d.cumulative_hits   ?? _cacheHistoryCumHits;
    _cacheHistoryCumMisses = d.cumulative_misses  ?? _cacheHistoryCumMisses;
    _renderCacheHistory();
  } catch (_) {}
}

function _renderCacheHistory() {
  const el = document.getElementById("cache-history-content");
  if (!el) return;
  const limitSel = document.getElementById("cache-history-limit");
  const limitN   = limitSel ? parseInt(limitSel.value, 10) : 10;
  const cumHits   = _cacheHistoryCumHits;
  const cumMisses = _cacheHistoryCumMisses;
  const cumTotal  = cumHits + cumMisses;
  const cumRate   = cumTotal > 0 ? (cumHits / cumTotal * 100).toFixed(1) + "%" : "—";

  if (_cacheHistoryAllSessions.length === 0) {
    const ph = _div("font-size:10px");
    ph.className = "detail-placeholder";
    ph.textContent = "No session history yet.";
    const ph2 = document.createElement("br");
    ph.appendChild(ph2);
    ph.appendChild(document.createTextNode("Stats accumulate after each CLI run."));
    el.replaceChildren(ph);
    return;
  }

  const pool = limitN > 0 ? _cacheHistoryAllSessions.slice(-limitN) : _cacheHistoryAllSessions;
  const hdr = _div("font-size:10px;color:var(--dim);margin-bottom:4px");
  hdr.textContent = "Sessions (newest first):";

  const rows = pool.slice().reverse().map(s => {
    const rate  = s.hit_rate != null ? s.hit_rate.toFixed(1) + "%" : "—";
    const ended = s.ended_at ? s.ended_at.replace("T", " ").substring(0, 19) + "Z" : "—";
    const row = _div("font-size:10px");
    row.className = "diff-entry";
    row.appendChild(_span("color:var(--cyan);min-width:24px;display:inline-block", "#" + s.session));
    row.appendChild(_span("min-width:48px;display:inline-block", s.hits + "H " + s.misses + "M"));
    row.appendChild(_span("min-width:48px;display:inline-block", rate));
    row.appendChild(_span("color:var(--dim);font-size:9px", ended));
    return row;
  });

  const footer = _div("font-size:10px;color:var(--dim);margin-top:6px");
  footer.textContent = "All-time: " + cumHits.toLocaleString() + "H " + cumMisses.toLocaleString() + "M " + cumRate;

  el.replaceChildren(hdr, ...rows, footer);
}
