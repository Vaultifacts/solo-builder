import { state } from "./dashboard_state.js";
import { api, toast, placeholder } from "./dashboard_utils.js";

/* ── Stalled panel ──────────────────────────────────────── */
let _stalledTaskFilter   = "";
let _stalledBranchFilter = "";

export async function pollStalled() {
  try {
    let qs = _stalledTaskFilter   ? `?task=${encodeURIComponent(_stalledTaskFilter)}`   : "";
    if (_stalledBranchFilter) qs += (qs ? "&" : "?") + `branch=${encodeURIComponent(_stalledBranchFilter)}`;
    const d = await api("/stalled" + qs);
    _renderStalled(d);
  } catch (_) {}
}

window._applyStalledTaskFilter = function () {
  const el = document.getElementById("stalled-task-filter");
  _stalledTaskFilter = el ? el.value.trim() : "";
  pollStalled();
};

window._applyStalledBranchFilter = function () {
  const el = document.getElementById("stalled-branch-filter");
  _stalledBranchFilter = el ? el.value.trim() : "";
  pollStalled();
};

function _updateStalledFilterLabel() {
  const lbl = document.getElementById("stalled-filter-label");
  if (!lbl) return;
  const parts = [];
  if (_stalledTaskFilter)   parts.push(`task: ${_stalledTaskFilter}`);
  if (_stalledBranchFilter) parts.push(`branch: ${_stalledBranchFilter}`);
  lbl.textContent = parts.length ? `· ${parts.join(" · ")}` : "";
  const clearBtn = document.getElementById("stalled-clear-filters");
  if (clearBtn) clearBtn.style.display = (_stalledTaskFilter || _stalledBranchFilter) ? "" : "none";
}

window._clearStalledFilters = function () {
  const hadFilter = _stalledTaskFilter || _stalledBranchFilter;
  _stalledTaskFilter   = "";
  _stalledBranchFilter = "";
  const tf = document.getElementById("stalled-task-filter");
  const bf = document.getElementById("stalled-branch-filter");
  if (tf) tf.value = "";
  if (bf) bf.value = "";
  _updateStalledFilterLabel();
  if (hadFilter) pollStalled();
};

function _renderStalled(d) {
  _updateStalledFilterLabel();
  const el = document.getElementById("stalled-content");
  if (!d) { el.replaceChildren(placeholder("No data.")); return; }
  const header = document.createElement("div");
  header.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:6px";
  header.textContent = "threshold: " + d.threshold + " steps · step " + d.step;
  const nodes = [header];
  if (!d.stalled || d.stalled.length === 0) {
    const p = placeholder("No stalled subtasks.");
    p.style.color = "var(--green)";
    nodes.push(p);
  } else {
    // ── Per-branch summary ────────────────────────────────
    const byBranch = {};
    d.stalled.forEach(s => {
      const key = s.task + " / " + s.branch;
      byBranch[key] = (byBranch[key] || 0) + 1;
    });
    if (Object.keys(byBranch).length > 1) {
      const summaryDiv = document.createElement("div");
      summaryDiv.style.cssText = "margin-bottom:6px;padding:4px 6px;background:var(--bg2);border-radius:3px;border:1px solid var(--border)";
      const summaryTitle = document.createElement("div");
      summaryTitle.style.cssText = "font-size:9px;color:var(--dim);margin-bottom:3px";
      summaryTitle.textContent = "by branch";
      summaryDiv.appendChild(summaryTitle);
      Object.entries(byBranch).sort((a, b) => b[1] - a[1]).forEach(([key, cnt]) => {
        const brRow = document.createElement("div");
        brRow.style.cssText = "display:flex;justify-content:space-between;font-size:9px";
        const keyEl = document.createElement("span");
        keyEl.style.color = "var(--dim)";
        keyEl.textContent = key;
        const cntEl = document.createElement("span");
        cntEl.style.color = "var(--yellow)";
        cntEl.textContent = cnt + " stalled";
        brRow.append(keyEl, cntEl);
        summaryDiv.appendChild(brRow);
      });
      nodes.push(summaryDiv);
    }
    d.stalled.forEach(s => {
      const pct = Math.min(100, Math.round(s.age / (d.threshold * 3) * 100));
      const row = document.createElement("div");
      row.className = "diff-entry";
      row.style.cssText = "font-size:10px;display:flex;align-items:center;gap:4px";

      const stEl = document.createElement("span");
      stEl.style.cssText = "color:var(--yellow);min-width:32px";
      stEl.textContent = s.subtask;

      const ageEl = document.createElement("span");
      ageEl.style.cssText = "color:var(--red);min-width:50px";
      ageEl.textContent = s.age + " steps";

      const barBg = document.createElement("span");
      barBg.style.cssText = "flex:1;background:var(--surface);height:4px;border-radius:2px;position:relative";
      const barFg = document.createElement("span");
      barFg.style.cssText = `position:absolute;left:0;top:0;height:4px;width:${pct}%;border-radius:2px;background:var(--red)`;
      barBg.appendChild(barFg);

      const taskEl = document.createElement("span");
      taskEl.style.cssText = "color:var(--dim);font-size:9px;min-width:60px;text-align:right";
      taskEl.textContent = s.task;

      const healBtn = document.createElement("button");
      healBtn.style.cssText = "background:var(--surface);color:var(--cyan);border:1px solid var(--border);border-radius:3px;font-size:9px;padding:0 4px;cursor:pointer";
      healBtn.title = "Reset to Pending";
      healBtn.textContent = "↻";
      healBtn.addEventListener("click", () => window.healSubtask(s.subtask));

      row.append(stEl, ageEl, barBg, taskEl, healBtn);
      nodes.push(row);
    });
  }
  el.replaceChildren(...nodes);
}

window.healSubtask = async function (st) {
  try {
    const r = await fetch(state.base + "/heal", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({subtask: st})});
    const d = await r.json();
    if (d.ok) toast("↻ " + st + " heal triggered");
    else toast(d.reason || "Heal failed");
  } catch (_) { toast("Network error"); }
};
