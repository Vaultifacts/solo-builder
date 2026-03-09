/**
 * Shared SVG utilities for dashboard ES modules.
 * Exported: svgEl, svgBar, sparklineSvg
 */

const NS = "http://www.w3.org/2000/svg";

/** Create an SVG element with a map of attributes. */
export function svgEl(tag, attrs) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

/**
 * Build a small horizontal progress bar SVG.
 * @param {number} barW   - Total bar width in px
 * @param {number} fillW  - Filled width in px
 * @param {string} label  - Text label centred on bar
 * @param {string} fillColor - CSS colour for filled portion
 */
export function svgBar(barW, fillW, label, fillColor) {
  const svg = svgEl("svg", {width: barW + 4, height: "14"});
  const bg  = svgEl("rect", {x:"1",y:"1",width:barW,height:"12",rx:"3",fill:"var(--surface)"});
  const fg  = svgEl("rect", {x:"1",y:"1",width:fillW,height:"12",rx:"3",fill:fillColor});
  const txt = svgEl("text", {x:barW / 2, y:"10", "text-anchor":"middle", "font-size":"8", fill:"var(--text)"});
  txt.textContent = label;
  svg.append(bg, fg, txt);
  return svg;
}

/**
 * Build a sparkline SVG from metrics history data.
 * @param {Array}  hist - Array of {verified, step_index}
 * @param {number} W    - SVG width
 * @param {number} H    - SVG height
 * @param {number} pad  - Padding on all sides
 * @returns {SVGElement|HTMLElement} SVG element, or a placeholder div if insufficient data
 */
export function sparklineSvg(hist, W, H, pad) {
  if (hist.length <= 1) {
    const d = document.createElement("div");
    d.className = "detail-placeholder";
    d.style.fontSize = "10px";
    d.textContent = "Not enough data yet (run more steps).";
    return d;
  }
  const maxV = Math.max(1, ...hist.map(r => r.verified));
  const pts = hist.map((r, i) => {
    const x = pad + (i / (hist.length - 1)) * (W - 2 * pad);
    const y = H - pad - (r.verified / maxV) * (H - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const svg = svgEl("svg", {width: W, height: H});
  svg.style.cssText = "display:block;margin:6px 0";
  const poly = svgEl("polyline", {points: pts, fill: "none", stroke: "var(--cyan)", "stroke-width": "1.5"});
  const t1 = svgEl("text", {x:"2", y: H - 1, "font-size":"8", fill:"var(--dim)"});
  t1.textContent = hist[0].step_index;
  const t2 = svgEl("text", {x: W - 2, y: H - 1, "font-size":"8", fill:"var(--dim)", "text-anchor":"end"});
  t2.textContent = hist[hist.length - 1].step_index;
  svg.append(poly, t1, t2);
  return svg;
}
