import { state } from "./dashboard_state.js";
import { api, esc } from "./dashboard_utils.js";

/* ── DOM helpers ─────────────────────────────────────────── */
function _div(cssText, cls) {
  const el = document.createElement("div");
  if (cssText) el.style.cssText = cssText;
  if (cls)    el.className = cls;
  return el;
}

function _span(cssText, text) {
  const el = document.createElement("span");
  if (cssText) el.style.cssText = cssText;
  el.textContent = text;
  return el;
}

function _bar(widthPx, totalPx, height, bg, fill) {
  const track = _div(`width:${totalPx}px;height:${height}px;background:${bg};border-radius:${Math.ceil(height/2)}px;flex-shrink:0`);
  const fg    = _div(`width:${widthPx}px;height:${height}px;background:${fill};border-radius:${Math.ceil(height/2)}px`);
  track.appendChild(fg);
  return track;
}

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
    const ph = _div(null, "detail-placeholder");
    ph.textContent = "No branches yet.";
    el.replaceChildren(ph);
    return;
  }

  const children = [];

  // ── Pipeline Overview ─────────────────────────────────────
  if (summary && summary.total > 0) {
    const card = _div("margin-bottom:10px;padding:6px 8px;background:var(--bg2);border-radius:4px;border:1px solid var(--border)");

    const title = _div("font-size:10px;color:var(--cyan);font-weight:bold;margin-bottom:4px");
    title.textContent = "Pipeline Overview — Step " + summary.step;
    card.appendChild(title);

    const ovW = 120;
    const ovFill = Math.round(summary.pct * ovW / 100);
    const barRow = _div("display:flex;align-items:center;gap:8px;margin-bottom:4px");
    barRow.appendChild(_bar(ovFill, ovW, 8, "var(--bg3)", "var(--green)"));
    barRow.appendChild(_span("font-size:11px;color:var(--text)", summary.verified + "/" + summary.total + " (" + summary.pct + "%)"));
    card.appendChild(barRow);

    const counts = _div("font-size:10px;color:var(--dim)");
    counts.textContent = summary.running + " running · " + summary.pending + " pending";
    card.appendChild(counts);

    if (summary.tasks && summary.tasks.length > 0) {
      const taskList = _div("margin-top:6px");
      summary.tasks.forEach(t => {
        const tw = Math.round(t.pct * 60 / 100);
        const row = _div("display:flex;align-items:center;gap:6px;margin-top:3px");
        row.appendChild(_span("color:var(--dim);font-size:10px;min-width:48px;flex-shrink:0", t.id));
        row.appendChild(_bar(tw, 60, 4, "var(--bg3)", "var(--green)"));
        row.appendChild(_span("font-size:10px;color:var(--dim)", t.verified + "/" + t.subtasks + " (" + t.pct + "%)"));
        taskList.appendChild(row);
      });
      card.appendChild(taskList);
    }
    children.push(card);
  }

  const countHdr = _div("color:var(--dim);font-size:10px;margin-bottom:6px");
  countHdr.textContent = d.count + " branches across all tasks";
  children.push(countHdr);

  const barW = 60;
  d.branches.forEach(br => {
    const w = Math.round(br.pct * barW / 100);
    const row = _div("cursor:pointer;display:flex;align-items:center;gap:8px", "diff-entry");
    row.title = "Click to select task";
    row.addEventListener("click", () => window.selectTask(br.task));
    row.appendChild(_span("color:var(--dim);font-size:10px;min-width:60px;flex-shrink:0", br.task));
    row.appendChild(_span("color:var(--cyan);min-width:80px;flex-shrink:0", br.branch));
    row.appendChild(_bar(w, barW, 6, "var(--bg2)", "var(--green)"));
    row.appendChild(_span("color:var(--dim);font-size:10px", br.verified + "/" + br.total));
    if (br.running > 0) {
      row.appendChild(_span("font-size:10px;color:var(--cyan)", br.running + "▶"));
    }
    children.push(row);
  });

  el.replaceChildren(...children);
}

function _renderBranchesDetail(d) {
  const el = document.getElementById("branches-content");
  if (!d.branches || d.branches.length === 0) {
    const ph = _div(null, "detail-placeholder");
    ph.textContent = "No branches.";
    el.replaceChildren(ph);
    return;
  }
  const statusColor = s => ({Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"})[s] || "var(--text)";

  const hdr = _div("color:var(--dim);font-size:10px;margin-bottom:6px");
  hdr.textContent = d.task + " — " + d.branch_count + " branches";

  const children = [hdr];
  d.branches.forEach(br => {
    const block = _div("margin-bottom:8px");

    const nameSpan = _span("color:var(--cyan);font-weight:bold", br.branch);
    const stCount  = _span("color:var(--dim);font-size:10px", " " + br.subtask_count + " STs");
    const vSpan    = _span("font-size:10px;color:var(--green)", " " + br.verified + "✓");
    const rSpan    = _span("font-size:10px;color:var(--cyan)", " " + br.running + "▶");
    const pSpan    = _span("font-size:10px;color:var(--yellow)", " " + br.pending + "●");
    block.appendChild(nameSpan);
    block.appendChild(stCount);
    block.appendChild(vSpan);
    block.appendChild(rSpan);
    block.appendChild(pSpan);

    br.subtasks.forEach(st => {
      const stRow = _div("padding-left:12px", "diff-entry");
      const stName = _span(null);
      stName.className = "diff-st";
      stName.textContent = st.name;
      const stStatus = _span("color:" + statusColor(st.status), st.status);
      stRow.appendChild(stName);
      stRow.appendChild(document.createTextNode(" "));
      stRow.appendChild(stStatus);
      block.appendChild(stRow);
    });
    children.push(block);
  });

  el.replaceChildren(...children);
}
