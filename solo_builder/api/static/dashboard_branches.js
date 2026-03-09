import { state } from "./dashboard_state.js";
import { api, esc } from "./dashboard_utils.js";

export async function pollBranches() {
  try {
    if (state.selectedTask) {
      const d = await api("/branches/" + encodeURIComponent(state.selectedTask));
      _renderBranchesDetail(d);
    } else {
      const [d, summary] = await Promise.all([api("/branches"), api("/dag/summary").catch(() => null)]);
      _renderBranchesAll(d, summary);
    }
  } catch (_) {}
}

function _renderBranchesAll(d, summary) {
  const el = document.getElementById("branches-content");
  if (!d.branches || d.branches.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">No branches yet.</div>`;
    return;
  }
  const barW = 60;
  let html = "";

  // ── Pipeline Overview (from /dag/summary) ───────────────
  if (summary && summary.total > 0) {
    const ovW = 120;
    const ovFill = Math.round(summary.pct * ovW / 100);
    html += `<div style="margin-bottom:10px;padding:6px 8px;background:var(--bg2);border-radius:4px;border:1px solid var(--border)">`;
    html += `<div style="font-size:10px;color:var(--cyan);font-weight:bold;margin-bottom:4px">Pipeline Overview — Step ${summary.step}</div>`;
    html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">`;
    html += `<div style="width:${ovW}px;height:8px;background:var(--bg3);border-radius:4px;flex-shrink:0"><div style="width:${ovFill}px;height:8px;background:var(--green);border-radius:4px"></div></div>`;
    html += `<span style="font-size:11px;color:var(--text)">${summary.verified}/${summary.total} (${summary.pct}%)</span>`;
    html += `</div>`;
    html += `<div style="font-size:10px;color:var(--dim)">${summary.running} running · ${summary.pending} pending</div>`;
    if (summary.tasks && summary.tasks.length > 0) {
      html += `<div style="margin-top:6px">`;
      summary.tasks.forEach(t => {
        const tw = Math.round(t.pct * 60 / 100);
        html += `<div style="display:flex;align-items:center;gap:6px;margin-top:3px">`;
        html += `<span style="color:var(--dim);font-size:10px;min-width:48px;flex-shrink:0">${esc(t.id)}</span>`;
        html += `<div style="width:60px;height:4px;background:var(--bg3);border-radius:2px;flex-shrink:0"><div style="width:${tw}px;height:4px;background:var(--green);border-radius:2px"></div></div>`;
        html += `<span style="font-size:10px;color:var(--dim)">${t.verified}/${t.subtasks} (${t.pct}%)</span>`;
        html += `</div>`;
      });
      html += `</div>`;
    }
    html += `</div>`;
  }

  html += `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">${d.count} branches across all tasks</div>`;
  d.branches.forEach(br => {
    const w = Math.round(br.pct * barW / 100);
    html += `<div class="diff-entry" style="cursor:pointer;display:flex;align-items:center;gap:8px" onclick="selectTask(${JSON.stringify(br.task)})" title="Click to select task">`;
    html += `<span style="color:var(--dim);font-size:10px;min-width:60px;flex-shrink:0">${esc(br.task)}</span>`;
    html += `<span style="color:var(--cyan);min-width:80px;flex-shrink:0">${esc(br.branch)}</span>`;
    html += `<div style="width:${barW}px;height:6px;background:var(--bg2);border-radius:3px;flex-shrink:0"><div style="width:${w}px;height:6px;background:var(--green);border-radius:3px"></div></div>`;
    html += `<span style="color:var(--dim);font-size:10px">${br.verified}/${br.total}</span>`;
    if (br.running > 0) html += `<span style="font-size:10px;color:var(--cyan)">${br.running}▶</span>`;
    html += `</div>`;
  });
  el.innerHTML = html;
}

function _renderBranchesDetail(d) {
  const el = document.getElementById("branches-content");
  if (!d.branches || d.branches.length === 0) {
    el.innerHTML = `<div class="detail-placeholder">No branches.</div>`;
    return;
  }
  const statusColor = s => ({Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"})[s] || "var(--text)";
  let html = `<div style="color:var(--dim);font-size:10px;margin-bottom:6px">${esc(d.task)} — ${d.branch_count} branches</div>`;
  d.branches.forEach(br => {
    html += `<div style="margin-bottom:8px"><span style="color:var(--cyan);font-weight:bold">${esc(br.branch)}</span> <span style="color:var(--dim);font-size:10px">${br.subtask_count} STs</span>`;
    html += ` <span style="font-size:10px;color:var(--green)">${br.verified}✓</span> <span style="font-size:10px;color:var(--cyan)">${br.running}▶</span> <span style="font-size:10px;color:var(--yellow)">${br.pending}●</span>`;
    br.subtasks.forEach(st => {
      html += `<div class="diff-entry" style="padding-left:12px"><span class="diff-st">${esc(st.name)}</span> <span style="color:${statusColor(st.status)}">${esc(st.status)}</span></div>`;
    });
    html += `</div>`;
  });
  el.innerHTML = html;
}
