import { state } from "./dashboard_state.js";

const NOTIF_MAX = 20;
const STALE_MS  = 10_000;

/** Escape a value for safe insertion into HTML attribute or text content. */
export function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function statusClass(s) {
  if (!s) return "s-pending";
  const l = s.toLowerCase();
  if (l === "verified") return "s-verified";
  if (l === "running")  return "s-running";
  if (l === "blocked")  return "s-blocked";
  return "s-pending";
}

export function dotClass(s) {
  if (!s) return "dot-pending";
  const l = s.toLowerCase();
  if (l === "verified") return "dot-verified";
  if (l === "running")  return "dot-running";
  if (l === "blocked")  return "dot-blocked";
  return "dot-pending";
}

const _etagCache = new Map();

export async function api(path) {
  const opts = {};
  const cached = _etagCache.get(path);
  if (cached) {
    opts.headers = {"If-None-Match": cached.etag};
  }
  const r = await fetch(state.base + path, opts);
  if (r.status === 304 && cached) return cached.data;
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  const data = await r.json();
  const etag = r.headers.get("ETag");
  if (etag) _etagCache.set(path, {etag, data});
  return data;
}

function _renderNotifPanel() {
  const list  = document.getElementById("notif-list");
  const badge = document.getElementById("notif-count-badge");
  if (!list) return;
  list.replaceChildren();
  if (state.notifHistory.length === 0) {
    const placeholder = document.createElement("div");
    placeholder.style.cssText = "color:var(--dim);font-size:10px;padding:8px 10px";
    placeholder.textContent = "No notifications yet.";
    list.appendChild(placeholder);
  } else {
    state.notifHistory.slice().reverse().forEach(function (n) {
      const c = n.type === "error" ? "var(--red)" : n.type === "warn" ? "var(--yellow)" : "var(--text)";
      const row = document.createElement("div");
      row.style.cssText = "padding:6px 10px;border-bottom:1px solid var(--border);font-size:10px";
      const ts = document.createElement("span");
      ts.style.cssText = "color:var(--dim);margin-right:6px";
      ts.textContent = n.ts;
      const msg = document.createElement("span");
      msg.style.color = c;
      msg.textContent = n.msg;
      row.appendChild(ts);
      row.appendChild(msg);
      list.appendChild(row);
    });
  }
  if (badge) {
    badge.textContent = String(state.notifHistory.length);
    badge.style.display = state.notifHistory.length > 0 ? "block" : "none";
  }
}

export function pushNotif(msg, type) {
  const ts = new Date().toTimeString().slice(0, 8);
  state.notifHistory.push({ msg, type: type || "info", ts });
  if (state.notifHistory.length > NOTIF_MAX) state.notifHistory.shift();
  _renderNotifPanel();
}

export function toast(msg, type) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.style.display = "block";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.style.display = "none"; }, 4000);
  pushNotif(msg, type || "info");
}

export function updateNotifBadge(currentStep) {
  const badge = document.getElementById("notif-badge");
  if (!state.tabFocused && currentStep > state.lastSeenStep) {
    const unread = currentStep - state.lastSeenStep;
    badge.textContent = unread > 99 ? "99+" : String(unread);
    badge.classList.remove("hidden");
    document.title = `(${unread}) Solo Builder — Step ${currentStep}`;
  } else {
    state.lastSeenStep = currentStep;
    localStorage.setItem("sb-last-seen-step", String(currentStep));
    badge.classList.add("hidden");
  }
}

export function playCompletionSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [[523, 0], [659, 0.15], [784, 0.3]].forEach(([freq, when]) => {
      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = "sine";
      gain.gain.setValueAtTime(0.18, ctx.currentTime + when);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + when + 0.25);
      osc.start(ctx.currentTime + when);
      osc.stop(ctx.currentTime + when + 0.3);
    });
  } catch (_) {}
}

export function checkStaleBanner() {
  const stale = Date.now() - state.lastStatusOk > STALE_MS;
  const el = document.getElementById("stale-banner");
  if (el) el.style.display = stale ? "block" : "none";
}

/** Status color map — shared across history, stalled, subtasks panels. */
export const STATUS_COL = {Verified: "var(--green)", Running: "var(--cyan)", Review: "var(--yellow)", Pending: "var(--dim)"};

/** Create a dim placeholder element with the given text. */
export function placeholder(text) {
  const d = document.createElement("div");
  d.style.cssText = "color:var(--dim);font-size:11px;padding:12px 0";
  d.textContent = text;
  return d;
}

export function flash(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2500);
}

window.toggleNotifPanel = function () {
  const panel = document.getElementById("notif-panel");
  if (!panel) return;
  panel.style.display = panel.style.display === "none" ? "block" : "none";
};

window.clearNotifHistory = function () {
  state.notifHistory.length = 0;
  _renderNotifPanel();
};
