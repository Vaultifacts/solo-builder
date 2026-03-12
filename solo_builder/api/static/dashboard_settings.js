import { state } from "./dashboard_state.js";
import { api, flash, placeholder } from "./dashboard_utils.js";

/* ── Settings panel ─────────────────────────────────────── */
let _settingsCache = {};

export async function pollSettings() {
  try {
    const d = await api("/config");
    _renderSettings(d);
  } catch (_) {}
}

function _renderSettings(d) {
  const el = document.getElementById("settings-content");
  if (!d || typeof d !== "object") {
    el.replaceChildren(placeholder("Could not load settings."));
    return;
  }
  _settingsCache = d;
  const counter = document.createElement("div");
  counter.style.cssText = "color:var(--dim);font-size:10px;margin-bottom:6px";
  counter.textContent = `${Object.keys(d).length} settings`;
  const rows = Object.entries(d).map(([k, v]) => {
    const vStr = typeof v === "string" ? v : JSON.stringify(v);
    const inputId = "cfg-" + k;
    const row = document.createElement("div");
    row.className = "diff-entry";
    row.style.cssText = "display:flex;align-items:center;gap:6px";
    const lbl = document.createElement("span");
    lbl.style.cssText = "color:var(--cyan);font-size:10px;min-width:120px;flex-shrink:0";
    lbl.textContent = k;
    row.appendChild(lbl);
    if (typeof v === "boolean") {
      const chk = document.createElement("input");
      chk.type = "checkbox"; chk.id = inputId; chk.checked = v;
      chk.style.accentColor = "var(--cyan)";
      chk.addEventListener("change", () => window.saveSetting(k, chk.checked));
      row.appendChild(chk);
    } else {
      const inp = document.createElement("input");
      inp.id = inputId; inp.value = vStr;
      inp.style.cssText = "flex:1;min-width:0;padding:1px 4px;font-size:10px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:3px;font-family:var(--font)";
      inp.addEventListener("change", () => window.saveSetting(k, inp.value));
      row.appendChild(inp);
    }
    return row;
  });
  const fb = document.createElement("span");
  fb.className = "feedback"; fb.id = "fb-settings";
  const exportDiv = document.createElement("div");
  exportDiv.style.marginTop = "8px";
  const exportA = document.createElement("a");
  exportA.className = "toolbar-btn"; exportA.href = "/config/export"; exportA.download = "settings.json";
  exportA.textContent = "⬇ Export settings.json";
  exportDiv.appendChild(exportA);
  const toolSection = document.createElement("div");
  toolSection.style.cssText = "margin-top:10px;border-top:1px solid var(--border);padding-top:8px";
  const toolHdr = document.createElement("div");
  toolHdr.style.cssText = "font-size:10px;color:var(--dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:1px";
  toolHdr.textContent = "Tool override";
  const toolRow = document.createElement("div");
  toolRow.style.cssText = "display:flex;gap:4px;align-items:center;flex-wrap:wrap";
  const stInput = document.createElement("input");
  stInput.id = "tool-override-st"; stInput.className = "cmd-input";
  stInput.placeholder = "A1"; stInput.title = "Subtask name"; stInput.style.width = "50px";
  const toolsInput = document.createElement("input");
  toolsInput.id = "tool-override-tools"; toolsInput.className = "cmd-input-wide";
  toolsInput.placeholder = "Read,Glob,Grep"; toolsInput.title = "Comma-separated tool names";
  const toolBtn = document.createElement("button");
  toolBtn.className = "cmd-btn btn-tools"; toolBtn.textContent = "⚙ Set";
  toolBtn.addEventListener("click", () => window.submitToolOverride());
  toolRow.append(stInput, toolsInput, toolBtn);
  const toolFb = document.createElement("span");
  toolFb.className = "feedback"; toolFb.id = "fb-tool-override";
  toolSection.append(toolHdr, toolRow, toolFb);
  el.replaceChildren(counter, ...rows, fb, exportDiv, toolSection);
}

window.submitToolOverride = async function () {
  const st    = (document.getElementById("tool-override-st")?.value    || "").trim().toUpperCase();
  const tools = (document.getElementById("tool-override-tools")?.value || "").trim();
  if (!st)    { flash("fb-tool-override", "Subtask required"); return; }
  if (!tools) { flash("fb-tool-override", "Tools required"); return; }
  try {
    const r = await fetch(state.base + "/tools", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({subtask:st, tools})});
    const d = await r.json();
    if (d.ok) {
      flash("fb-tool-override", `Tools set for ${st}`);
      document.getElementById("tool-override-st").value    = "";
      document.getElementById("tool-override-tools").value = "";
    } else { flash("fb-tool-override", d.reason || "Error"); }
  } catch (e) { flash("fb-tool-override", "Network error"); }
};

window.saveSetting = async function (key, val) {
  if (typeof val === "string") {
    const n = Number(val);
    if (!isNaN(n) && val.trim() !== "") val = n;
  }
  try {
    const r = await fetch(state.base + "/config", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({[key]: val})});
    const d = await r.json();
    if (d.ok) { flash("fb-settings", key + " saved"); _settingsCache = d; }
    else flash("fb-settings", d.reason || "Error");
  } catch (e) { flash("fb-settings", "Network error"); }
};
