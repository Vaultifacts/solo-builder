import { api, esc, toast } from "./dashboard_utils.js";

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
    el.innerHTML =
      `<div style="font-size:10px;color:var(--dim);margin-bottom:4px">This session:</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Entries on disk</span> ${entries}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Est. tokens held</span> ${tokens.toLocaleString()}</div>` +
      `<div style="font-size:10px;color:var(--dim);margin:6px 0 4px">All sessions:</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Cumulative hits</span> ${cumHits.toLocaleString()}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Cumulative misses</span> ${cumMisses.toLocaleString()}</div>` +
      `<div class="diff-entry" style="font-size:10px"><span style="color:var(--cyan);min-width:130px;display:inline-block">Hit rate</span> ${hitRate}</div>` +
      `<div class="diff-entry" style="font-size:10px;word-break:break-all"><span style="color:var(--cyan);min-width:130px;display:inline-block">Cache dir</span> <span style="color:var(--dim)">${esc(dir)}</span></div>` +
      `<div style="margin-top:8px"><button class="toolbar-btn" onclick="clearCache()">Clear Cache</button></div>`;
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
    el.innerHTML = `<div class="detail-placeholder">No session history yet.<br>Stats accumulate after each CLI run.</div>`;
    return;
  }
  const pool = limitN > 0 ? _cacheHistoryAllSessions.slice(-limitN) : _cacheHistoryAllSessions;
  const rows = pool.slice().reverse().map(s => {
    const rate  = s.hit_rate != null ? s.hit_rate.toFixed(1) + "%" : "—";
    const ended = s.ended_at ? s.ended_at.replace("T", " ").substring(0, 19) + "Z" : "—";
    return `<div class="diff-entry" style="font-size:10px">` +
      `<span style="color:var(--cyan);min-width:24px;display:inline-block">#${s.session}</span>` +
      `<span style="min-width:48px;display:inline-block">${s.hits}H ${s.misses}M</span>` +
      `<span style="min-width:48px;display:inline-block">${rate}</span>` +
      `<span style="color:var(--dim);font-size:9px">${esc(ended)}</span>` +
      `</div>`;
  }).join("");
  el.innerHTML =
    `<div style="font-size:10px;color:var(--dim);margin-bottom:4px">Sessions (newest first):</div>` +
    rows +
    `<div style="font-size:10px;color:var(--dim);margin-top:6px">All-time: ${cumHits.toLocaleString()}H ${cumMisses.toLocaleString()}M ${cumRate}</div>`;
}
