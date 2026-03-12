import { api, STATUS_COL, placeholder } from "./dashboard_utils.js";
import { svgBar, sparklineSvg } from "./dashboard_svg.js";
export { pollBranches } from "./dashboard_branches.js";
export { pollCache, pollCacheHistory } from "./dashboard_cache.js";
export { pollGatesDetailed, pollDebtScanDetailed, pollPromptRegressionDetailed, pollSloDetailed, pollThreatModelDetailed, pollContextWindowDetailed, pollPolicyDetailed, pollLiveSummaryDetailed, pollHealthDetailed, pollCiQualityDetailed, pollPreReleaseDetailed, pollRepoHealthDetailed } from "./dashboard_health.js";
export { pollSettings } from "./dashboard_settings.js";
export { pollStalled } from "./dashboard_stalled.js";
export { pollSubtasks, updateSubtasksExportLinks } from "./dashboard_subtasks.js";
export { pollHistory, historyPageStep, resetHistoryUnread } from "./dashboard_history.js";
import { updateSubtasksExportLinks as _updateSubtasksExportLinks } from "./dashboard_subtasks.js";
import { resetHistoryUnread as _resetHistoryUnread } from "./dashboard_history.js";

/* ── Sidebar tabs ────────────────────────────────────────── */
window.switchTab = function (name) {
  document.querySelectorAll(".sidebar-tab").forEach(t => {
    const tabName = t.dataset.tab || t.textContent.toLowerCase();
    t.classList.toggle("active", tabName === name);
  });
  document.querySelectorAll(".sidebar-tab-content").forEach(c => c.classList.toggle("active", c.id === "tab-" + name));
  if (name === "journal") {
    const pane = document.getElementById("tab-journal");
    if (pane) pane.scrollTop = 0;
  }
  if (name === "history") {
    _resetHistoryUnread();
  }
  if (name === "subtasks") {
    _updateSubtasksExportLinks();
  }
  if (name === "export") {
    _refreshExportHistoryByStatus();
  }
};

async function _refreshExportHistoryByStatus() {
  try {
    const d = await api("/history/count");
    const el = document.getElementById("export-history-by-status");
    if (!el) return;
    const byStatus = d.by_status || {};
    const entries = Object.entries(byStatus).filter(([, n]) => n > 0);
    if (!entries.length) { el.style.display = "none"; return; }
    el.style.display = "flex";
    el.replaceChildren();
    for (const [s, n] of entries) {
      const chip = document.createElement("span");
      chip.textContent = `${s}: ${n}`;
      chip.style.color = STATUS_COL[s] || "var(--dim)";
      el.append(chip);
    }
  } catch (_) {}
  try {
    const sd = await api("/stalled");
    const minAge = sd.threshold || 5;
    const csv  = document.getElementById("export-stalled-csv");
    const json = document.getElementById("export-stalled-json");
    if (csv)  csv.href  = `/subtasks/export?status=running&min_age=${minAge}`;
    if (json) json.href = `/subtasks/export?status=running&min_age=${minAge}&format=json`;
    const lbl = document.getElementById("export-stalled-threshold");
    if (lbl) lbl.textContent = `\u2265 ${minAge} steps stalled`;
  } catch (_) {}
}

/* ── Priority panel ─────────────────────────────────────── */
export async function pollPriority() {
  try {
    const d = await api("/priority");
    _renderPriority(d);
  } catch (_) {}
}

function _renderPriority(d) {
  const el = document.getElementById("priority-content");
  if (!d || !d.queue) {
    el.replaceChildren(placeholder("No priority data."));
    return;
  }
  const header = document.createElement("div");
  header.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:6px";
  header.textContent = d.count + " candidates · step " + d.step;
  const nodes = [header];
  if (d.queue.length === 0) {
    nodes.push(placeholder("All subtasks Verified or blocked."));
  } else {
    const maxRisk = d.queue[0].risk || 1;
    d.queue.forEach((c, i) => {
      const col = c.status === "Running" ? "var(--cyan)" : "var(--dim)";
      const fill = Math.round(80 * c.risk / maxRisk);
      const row = document.createElement("div");
      row.className = "diff-entry";
      row.style.cssText = "font-size:10px;display:flex;align-items:center;gap:4px";

      const marker = document.createElement("span");
      marker.style.cssText = "color:var(--yellow);min-width:14px";
      marker.textContent = i < 6 ? "▶ " : "  ";

      const stEl = document.createElement("span");
      stEl.style.cssText = "color:var(--cyan);min-width:32px";
      stEl.textContent = c.subtask;

      const statusEl = document.createElement("span");
      statusEl.style.cssText = `color:${col};min-width:52px`;
      statusEl.textContent = c.status;

      const riskEl = document.createElement("span");
      riskEl.style.cssText = "min-width:40px;color:var(--yellow)";
      riskEl.textContent = "r=" + c.risk;

      const barBg = document.createElement("span");
      barBg.style.cssText = "flex:1;background:var(--surface);height:4px;border-radius:2px;position:relative";
      const barFg = document.createElement("span");
      barFg.style.cssText = `position:absolute;left:0;top:0;height:4px;width:${fill}%;border-radius:2px;background:${c.status === "Running" ? "var(--cyan)" : "var(--yellow)"}`;
      barBg.appendChild(barFg);

      const taskEl = document.createElement("span");
      taskEl.style.cssText = "color:var(--dim);font-size:9px;min-width:60px;text-align:right";
      taskEl.textContent = c.task;

      row.append(marker, stEl, statusEl, riskEl, barBg, taskEl);
      nodes.push(row);
    });
  }
  el.replaceChildren(...nodes);
}

/* ── Agents panel ───────────────────────────────────────── */
export async function pollAgents() {
  try {
    const d = await api("/agents");
    _renderAgents(d);
  } catch (_) {}
}

function _renderAgents(d) {
  const el = document.getElementById("agents-content");
  if (!d) { el.replaceChildren(placeholder("No data.")); return; }
  const f = d.forecast || {};
  const pct = f.pct || 0;
  const barW = 120, fillW = Math.round(barW * pct / 100);
  const stepEl = document.createElement("div");
  stepEl.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:8px";
  stepEl.textContent = `step ${d.step}`;
  const barDiv = document.createElement("div");
  barDiv.style.marginBottom = "8px";
  barDiv.appendChild(svgBar(barW, fillW, `${pct}% (${f.verified}/${f.total})`, "var(--cyan)"));
  const cards = [
    {label: "Planner",       val: `cache interval: ${d.planner?.cache_interval || 5} steps`},
    {label: "Executor",      val: `max/step: ${d.executor?.max_per_step || 6}`},
    {label: "SelfHealer",    val: `healed: ${d.healer?.healed_total || 0}  stalled: ${d.healer?.currently_stalled || 0}  threshold: ${d.healer?.threshold || 5}`},
    {label: "MetaOptimizer", val: `history: ${d.meta?.history_len || 0}  heal: ${d.meta?.heal_rate?.toFixed(2) || "0.00"}/step  verify: ${d.meta?.verify_rate?.toFixed(2) || "0.00"}/step`},
    {label: "Forecast",      val: `${f.remaining || 0} remaining` + (f.eta_steps ? `  ETA: ~${f.eta_steps} steps` : "")},
  ];
  const cardEls = cards.map(c => {
    const row = document.createElement("div");
    row.className = "diff-entry"; row.style.fontSize = "10px";
    const lbl = document.createElement("span");
    lbl.style.cssText = "color:var(--cyan);min-width:80px;display:inline-block";
    lbl.textContent = c.label;
    const val = document.createElement("span");
    val.style.color = "var(--dim)"; val.textContent = " " + c.val;
    row.append(lbl, val);
    return row;
  });
  el.replaceChildren(stepEl, barDiv, ...cardEls);
}

/* ── Forecast panel ─────────────────────────────────────── */
export async function pollForecast() {
  try {
    const d = await api("/forecast");
    const el = document.getElementById("forecast-content");
    if (!el) return;
    const eta  = d.eta_steps != null ? `~${d.eta_steps} steps` : "N/A";
    const rate = d.verified_per_step != null ? d.verified_per_step.toFixed(2) : "—";
    const pct  = d.percent_complete != null ? d.percent_complete.toFixed(1) : "—";
    const barW = 120, fillW = Math.round(barW * (d.percent_complete || 0) / 100);
    const barWrap = document.createElement("div");
    barWrap.style.marginBottom = "8px";
    barWrap.appendChild(svgBar(barW, fillW, `${pct}%`, "var(--green)"));
    const mkRow = (label, content) => {
      const row = document.createElement("div");
      row.className = "diff-entry"; row.style.fontSize = "10px";
      const lbl = document.createElement("span");
      lbl.style.cssText = "color:var(--cyan);min-width:80px;display:inline-block";
      lbl.textContent = label;
      row.appendChild(lbl);
      if (typeof content === "string") {
        row.appendChild(document.createTextNode(content));
      } else {
        row.appendChild(content);
      }
      return row;
    };
    const pctStrong = document.createElement("strong");
    pctStrong.textContent = `${pct}%`;
    el.replaceChildren(
      barWrap,
      mkRow("Completion", pctStrong),
      mkRow("Rate", `${rate} verified/step`),
      mkRow("ETA", eta),
      mkRow("Verified", `${d.verified ?? "—"} / ${d.total ?? "—"}`),
      mkRow("Stalled", `${d.stalled_count ?? 0}`),
    );
  } catch (_) {}
}

/* ── Metrics panel ──────────────────────────────────────── */
export async function pollMetrics() {
  try {
    const d = await api("/metrics");
    const el = document.getElementById("metrics-content");
    if (!el) return;
    const s = d.summary || {};
    const hist = d.history || [];
    const W = 200, H = 48, pad = 4;
    const sparkline = sparklineSvg(hist, W, H, pad);
    const elapsedStr = d.elapsed_s != null ? `${d.elapsed_s}s` : "—";
    const rateStr    = d.steps_per_min != null ? `${d.steps_per_min}/min` : "—";
    const mkSect = (label, marginTop) => {
      const h = document.createElement("div");
      h.style.cssText = `font-size:10px;color:var(--dim);${marginTop ? "margin:8px 0 4px;" : "margin-bottom:4px;"}text-transform:uppercase;letter-spacing:1px`;
      h.textContent = label;
      return h;
    };
    const mkRow = (label, text, labelColor) => {
      const row = document.createElement("div");
      row.className = "diff-entry"; row.style.fontSize = "10px";
      const lbl = document.createElement("span");
      lbl.style.cssText = `color:${labelColor || "var(--cyan)"};min-width:110px;display:inline-block`;
      lbl.textContent = label;
      row.append(lbl, document.createTextNode(text));
      return row;
    };
    const chartLabel = document.createElement("div");
    chartLabel.style.cssText = "font-size:10px;color:var(--dim);margin-bottom:2px";
    chartLabel.textContent = "Verified/step over time:";
    const dlBar = document.createElement("div");
    dlBar.style.cssText = "margin-top:8px;display:flex;gap:6px";
    const csvA = document.createElement("a");
    csvA.className = "toolbar-btn"; csvA.href = "/metrics/export"; csvA.download = "metrics.csv";
    csvA.textContent = "Download CSV";
    const jsonA = document.createElement("a");
    jsonA.className = "toolbar-btn"; jsonA.href = "/metrics/export?format=json"; jsonA.download = "metrics.json";
    jsonA.textContent = "Download JSON";
    dlBar.append(csvA, jsonA);
    el.replaceChildren(
      mkSect("Run health", false),
      mkRow("Verified", `${d.verified ?? "—"} / ${d.total ?? "—"} (${d.pct ?? 0}%)`),
      mkRow("Pending",  `${d.pending ?? "—"}`),
      mkRow("Running",  `${d.running ?? "—"}`),
      mkRow("Review",   `${d.review ?? 0}`),
      mkRow("Stalled",  `${d.stalled ?? 0}`, (d.stalled ?? 0) > 0 ? "var(--yellow)" : "var(--cyan)"),
      mkRow("Elapsed",  elapsedStr),
      mkRow("Step rate", rateStr),
      mkSect("Analytics", true),
      chartLabel,
      sparkline,
      mkRow("Total steps",   `${s.total_steps ?? "—"}`),
      mkRow("Total verifies",`${s.total_verifies ?? "—"}`),
      mkRow("Avg rate",      `${s.avg_verified_per_step ?? "—"} v/step`),
      mkRow("Peak rate",     `${s.peak_verified_per_step ?? "—"} v/step`),
      mkRow("Steps w/ heals",`${s.steps_with_heals ?? 0}`),
      mkRow("Total healed",  `${d.total_healed ?? 0}`),
      dlBar,
    );
  } catch (_) {}
}

