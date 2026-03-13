/**
 * DAG graph view for the dashboard.
 * Extracted from dashboard.js to keep the main module focused on polling.
 */
import { state } from "./dashboard_state.js";
import { svgEl } from "./dashboard_svg.js";

/* ── DAG graph view ───────────────────────────────────────── */
window.toggleView = function () {
  state.viewMode = state.viewMode === "grid" ? "graph" : "grid";
  const btn = document.getElementById("btn-view");
  btn.textContent = state.viewMode === "grid" ? "Graph" : "Grid";
  document.getElementById("task-grid").style.display = state.viewMode === "grid" ? "" : "none";
  document.getElementById("dag-svg").style.display   = state.viewMode === "grid" ? "none" : "";
  if (state.viewMode === "graph") renderGraph();
};

export function renderGraph() {
  const svg = document.getElementById("dag-svg");
  if (!state.taskIds.length) { svg.replaceChildren(); return; }

  const taskMap = {};
  state.taskIds.forEach(id => { taskMap[id] = state.tasksCache[id] || {}; });
  const levels = {};
  const visited = new Set();
  function getLevel(id) {
    if (levels[id] !== undefined) return levels[id];
    if (visited.has(id)) return 0;
    visited.add(id);
    const deps = (taskMap[id].depends_on || []).filter(d => taskMap[d]);
    if (!deps.length) { levels[id] = 0; return 0; }
    const maxDep = Math.max(...deps.map(d => getLevel(d)));
    levels[id] = maxDep + 1;
    return levels[id];
  }
  state.taskIds.forEach(id => getLevel(id));

  const byLevel = {};
  state.taskIds.forEach(id => {
    const lv = levels[id] || 0;
    if (!byLevel[lv]) byLevel[lv] = [];
    byLevel[lv].push(id);
  });
  const maxLevel = Math.max(...Object.keys(byLevel).map(Number));

  const NW = 120, NH = 44, PX = 160, PY = 70, OX = 30, OY = 30;
  const totalW = (maxLevel + 1) * PX + OX * 2;
  const maxPerLevel = Math.max(...Object.values(byLevel).map(a => a.length));
  const totalH = maxPerLevel * PY + OY * 2;
  svg.setAttribute("viewBox", `0 0 ${totalW} ${totalH}`);
  svg.style.minHeight = Math.max(200, totalH) + "px";

  const pos = {};
  Object.entries(byLevel).forEach(([lv, ids]) => {
    const n = ids.length;
    const startY = (totalH - n * PY) / 2 + PY / 2;
    ids.forEach((id, i) => {
      pos[id] = { x: OX + Number(lv) * PX, y: startY + i * PY };
    });
  });

  function nodeColor(t) {
    const s = (t.status || "").toLowerCase();
    if (s === "verified") return "var(--green)";
    if (s === "running") return "var(--cyan)";
    return "var(--yellow)";
  }
  function nodeColorBg(t) {
    const s = (t.status || "").toLowerCase();
    if (s === "verified") return "var(--node-bg-verified)";
    if (s === "running")  return "var(--node-bg-running)";
    return "var(--node-bg-pending)";
  }

  const defs = svgEl("defs", {});
  const marker = svgEl("marker", {id:"arrow",markerWidth:"8",markerHeight:"6",refX:"8",refY:"3",orient:"auto"});
  const markerPath = svgEl("path", {d:"M0,0 L8,3 L0,6",fill:"var(--dim)"});
  marker.appendChild(markerPath); defs.appendChild(marker);

  const nodes = [defs];

  state.taskIds.forEach(id => {
    const deps = (taskMap[id].depends_on || []).filter(d => pos[d]);
    deps.forEach(dep => {
      const from = pos[dep], to = pos[id];
      nodes.push(svgEl("line", {x1:from.x + NW,y1:from.y,x2:to.x,y2:to.y,stroke:"var(--dim)","stroke-width":"1.5","marker-end":"url(#arrow)",opacity:"0.5"}));
    });
  });

  state.taskIds.forEach(id => {
    const t = taskMap[id];
    const p = pos[id];
    const col = nodeColor(t);
    const bg = nodeColorBg(t);
    const branches = t.branches || {};
    const nSt = Object.values(branches).reduce((a, b) => a + Object.keys(b.subtasks || {}).length, 0);
    const nV  = Object.values(branches).reduce((a, b) => a + Object.values(b.subtasks || {}).filter(s => s.status === "Verified").length, 0);
    const pct = nSt ? Math.round(nV / nSt * 100) : 0;
    const barW = NW - 16, barH = 5, barX = p.x + 8, barY = p.y + 10;
    const rect = svgEl("rect", {x:p.x,y:p.y - NH/2,width:NW,height:NH + 8,rx:"4",fill:bg,stroke:col,"stroke-width":"1.5"});
    rect.style.cursor = "pointer";
    rect.addEventListener("click", () => window.selectTask(id));
    const txt1 = svgEl("text", {x:p.x + NW/2,y:p.y - 6,fill:col,"text-anchor":"middle","font-size":"11","font-family":"var(--font)","font-weight":"bold"});
    txt1.textContent = id;
    const txt2 = svgEl("text", {x:p.x + NW/2,y:p.y + 6,fill:"var(--dim)","text-anchor":"middle","font-size":"9","font-family":"var(--font)"});
    txt2.textContent = `${nV}/${nSt} (${pct}%)`;
    const barBg = svgEl("rect", {x:barX,y:barY,width:barW,height:barH,rx:"2",fill:"var(--surface)"});
    const barFg = svgEl("rect", {x:barX,y:barY,width:Math.round(barW * pct / 100),height:barH,rx:"2",fill:col});
    nodes.push(rect, txt1, txt2, barBg, barFg);
  });

  svg.replaceChildren(...nodes);
}
