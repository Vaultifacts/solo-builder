import { api } from "./dashboard_utils.js";

/* ── Health detailed (OM-001 to OM-005) ──────────────────── */
export async function pollGatesDetailed() {
  try {
    const d = await api("/executor/gates");
    const el = document.getElementById("gates-detailed-content");
    if (!el) return;

    const gates = d.gates || [];
    const blocked = d.blocked_count || 0;

    const mkBadge = (ok, label) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${ok ? "var(--green)" : "var(--red)"}`;
      b.textContent = label || (ok ? "OK" : "BLOCKED");
      return b;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = `Gates: ${d.running_count || 0} running · ${blocked} blocked`;
    hdr.append(hdrText);

    const nodes = [hdr];

    if (gates.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No Running subtasks.";
      nodes.push(empty);
    } else {
      gates.forEach(g => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:flex-start;padding:5px 0;border-bottom:1px solid var(--border);font-size:10px";
        const info = document.createElement("div");
        info.style.cssText = "flex:1;min-width:0";
        const name = document.createElement("div");
        name.style.cssText = "color:var(--text);font-weight:bold;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
        name.textContent = `${g.task} / ${g.subtask}`;
        const detail = document.createElement("div");
        detail.style.cssText = "color:var(--dim);font-size:9px;margin-top:2px";
        const parts = [`HITL:${g.hitl_name || "Auto"}`];
        if (!g.scope_ok) parts.push(`scope denied: ${(g.scope_denied || []).join(",")}`);
        if (!g.tools_valid) parts.push("invalid tools");
        if (g.action_type) parts.push(`type:${g.action_type}`);
        detail.textContent = parts.join(" · ");
        info.append(name, detail);
        row.append(mkBadge(!g.blocked, g.blocked ? "BLOCKED" : "OK"), info);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollDebtScanDetailed() {
  try {
    const d = await api("/health/debt-scan");
    const el = document.getElementById("debt-scan-detailed-content");
    if (!el) return;

    const results = d.results || [];
    const count   = d.count || 0;

    const _MARKER_COLOR = {
      FIXME: "var(--red)",
      HACK:  "var(--orange, #e07020)",
      TODO:  "var(--yellow, #e6a817)",
      XXX:   "var(--red)",
      NOQA:  "var(--dim)",
    };

    const mkBadge = (marker) => {
      const b = document.createElement("span");
      const color = _MARKER_COLOR[marker] || "var(--dim)";
      b.style.cssText = `font-size:9px;padding:1px 5px;border-radius:3px;font-weight:bold;margin-right:6px;flex-shrink:0;color:#000;background:${color}`;
      b.textContent = marker;
      return b;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--yellow, #e6a817)"}`;
    hdrText.textContent = `Debt: ${count} item${count !== 1 ? "s" : ""}${d.ok ? " — clean" : ""}`;
    hdr.append(hdrText);

    const nodes = [hdr];

    if (results.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = count > 0 ? `${count} items (showing 0 — see TECH_DEBT_REGISTER.md)` : "No debt items found.";
      nodes.push(empty);
    } else {
      results.forEach(r => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:flex-start;padding:4px 0;border-bottom:1px solid var(--border);font-size:10px";
        const info = document.createElement("div");
        info.style.cssText = "flex:1;min-width:0";
        const loc = document.createElement("div");
        loc.style.cssText = "color:var(--dim);font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
        loc.textContent = `${r.path}:${r.line}`;
        const txt = document.createElement("div");
        txt.style.cssText = "color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
        txt.textContent = r.text || "—";
        info.append(loc, txt);
        row.append(mkBadge(r.marker), info);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollPromptRegressionDetailed() {
  try {
    const d = await api("/health/prompt-regression");
    const el = document.getElementById("prompt-regression-detailed-content");
    if (!el) return;

    const results = d.results || [];
    const total   = d.total || 0;

    const mkBadge = (passed) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${passed ? "var(--green)" : "var(--red)"}`;
      b.textContent = passed ? "OK" : "FAIL";
      return b;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = `Prompts: ${total} template${total !== 1 ? "s" : ""}${d.ok ? " — OK" : ` — ${d.failed || 0} failed`}`;
    hdr.append(hdrText);

    const nodes = [hdr];

    if (results.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No templates registered.";
      nodes.push(empty);
    } else {
      results.forEach(r => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:flex-start;padding:4px 0;border-bottom:1px solid var(--border);font-size:10px";
        const info = document.createElement("div");
        info.style.cssText = "flex:1;min-width:0";
        const name = document.createElement("div");
        name.style.cssText = "color:var(--text)";
        name.textContent = r.name || "—";
        info.append(name);
        if (!r.passed && r.errors && r.errors.length > 0) {
          const errEl = document.createElement("div");
          errEl.style.cssText = "color:var(--dim);font-size:9px;margin-top:2px;word-break:break-word";
          errEl.textContent = r.errors[0];
          info.append(errEl);
        }
        row.append(mkBadge(r.passed), info);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollSloDetailed() {
  try {
    const d = await api("/health/slo");
    const el = document.getElementById("slo-detailed-content");
    if (!el) return;

    const results = d.results || [];

    const _SLO_COLOR = {
      ok:      "var(--green)",
      breach:  "var(--red)",
      no_data: "var(--dim)",
      skip:    "var(--dim)",
    };

    const mkBadge = (status) => {
      const b = document.createElement("span");
      const color = _SLO_COLOR[status] || "var(--dim)";
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${color}`;
      b.textContent = status.replace("_", " ").toUpperCase();
      return b;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = `SLO${d.ok ? " — OK" : " — breaches detected"} (${d.records || 0} records)`;
    hdr.append(hdrText);

    const nodes = [hdr];

    if (results.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "Insufficient metrics data.";
      nodes.push(empty);
    } else {
      results.forEach(r => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:flex-start;padding:4px 0;border-bottom:1px solid var(--border);font-size:10px";
        const info = document.createElement("div");
        info.style.cssText = "flex:1;min-width:0";
        const name = document.createElement("div");
        name.style.cssText = "color:var(--text);font-weight:bold";
        name.textContent = r.slo || "—";
        const detail = document.createElement("div");
        detail.style.cssText = "color:var(--dim);font-size:9px;margin-top:2px";
        const valStr = r.value != null ? `${r.value}` : "—";
        detail.textContent = `target: ${r.target || "—"} · value: ${valStr}${r.detail ? " · " + r.detail : ""}`;
        info.append(name, detail);
        row.append(mkBadge(r.status || "skip"), info);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollThreatModelDetailed() {
  try {
    const d = await api("/health/threat-model");
    const el = document.getElementById("threat-model-detailed-content");
    if (!el) return;

    const checks = d.checks || [];

    const mkBadge = (passed) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${passed ? "var(--green)" : "var(--red)"}`;
      b.textContent = passed ? "OK" : "FAIL";
      return b;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = `Threat Model${d.ok ? " — OK" : " — issues found"}`;
    hdr.append(hdrText);

    const nodes = [hdr];

    checks.forEach(c => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:flex-start;padding:4px 0;border-bottom:1px solid var(--border);font-size:10px";
      const info = document.createElement("div");
      info.style.cssText = "flex:1;min-width:0";
      const name = document.createElement("div");
      name.style.cssText = "color:var(--text)";
      name.textContent = c.name + (c.required ? "" : " (advisory)");
      if (c.detail) {
        const det = document.createElement("div");
        det.style.cssText = "color:var(--dim);font-size:9px;margin-top:2px;word-break:break-word";
        det.textContent = c.detail;
        info.append(name, det);
      } else {
        info.append(name);
      }
      row.append(mkBadge(c.passed), info);
      nodes.push(row);
    });

    if (checks.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No threat model checks available.";
      nodes.push(empty);
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollContextWindowDetailed() {
  try {
    const d = await api("/health/context-window");
    const el = document.getElementById("context-window-detailed-content");
    if (!el) return;

    const results = d.results || [];

    const _STATUS_COLOR = {
      ok:          "var(--green)",
      warn:        "var(--yellow, #e6a817)",
      critical:    "var(--orange, #e07020)",
      over_budget: "var(--red)",
      missing:     "var(--dim)",
    };

    const mkBadge = (status) => {
      const b = document.createElement("span");
      const color = _STATUS_COLOR[status] || "var(--dim)";
      b.style.cssText = `font-size:9px;padding:1px 5px;border-radius:3px;font-weight:bold;margin-right:6px;flex-shrink:0;color:#000;background:${color}`;
      b.textContent = status.replace("_", " ").toUpperCase();
      return b;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = `Context Window${d.has_issues ? " — pressure detected" : " — OK"}`;
    hdr.append(hdrText);

    const nodes = [hdr];

    results.forEach(r => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;padding:4px 0;border-bottom:1px solid var(--border);font-size:10px";
      const info = document.createElement("div");
      info.style.cssText = "flex:1;min-width:0";
      const name = document.createElement("div");
      name.style.cssText = "color:var(--text);font-weight:bold";
      name.textContent = r.label;
      const detail = document.createElement("div");
      detail.style.cssText = "color:var(--dim);font-size:9px;margin-top:2px";
      const linesStr = r.lines != null ? `${r.lines} / ${r.budget} lines (${r.utilization}%)` : "missing";
      detail.textContent = linesStr;
      info.append(name, detail);
      row.append(mkBadge(r.status), info);
      nodes.push(row);
    });

    if (results.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No tracked files.";
      nodes.push(empty);
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollPolicyDetailed() {
  try {
    const [dh, ds] = await Promise.all([api("/policy/hitl"), api("/policy/scope")]);
    const el = document.getElementById("policy-detailed-content");
    if (!el) return;

    const mkBadge = (ok) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${ok ? "var(--green)" : "var(--red)"}`;
      b.textContent = ok ? "OK" : "WARN";
      return b;
    };

    const mkRow = (label, value) => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:flex-start;padding:4px 0;border-bottom:1px solid var(--border);font-size:10px;gap:6px";
      const lbl = document.createElement("span");
      lbl.style.cssText = "color:var(--dim);min-width:90px;flex-shrink:0";
      lbl.textContent = label;
      const val = document.createElement("span");
      val.style.cssText = "color:var(--text);word-break:break-all";
      val.textContent = value;
      row.append(lbl, val);
      return row;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = "font-size:12px;font-weight:bold;color:var(--text)";
    hdrText.textContent = "Policy";
    hdr.append(hdrText);

    const nodes = [hdr];

    // HITL section
    const hitlHdr = document.createElement("div");
    hitlHdr.style.cssText = "display:flex;align-items:center;gap:6px;padding:4px 0;font-size:11px;font-weight:bold;color:var(--text)";
    hitlHdr.append(mkBadge(dh.ok), Object.assign(document.createElement("span"), {textContent: "HITL"}));
    nodes.push(hitlHdr);

    const hp = dh.policy || {};
    const pauseTools = (hp.pause_tools || []).join(", ") || "—";
    const blockKw    = (hp.block_keywords || []).join(", ") || "—";
    nodes.push(mkRow("pause tools:", pauseTools));
    nodes.push(mkRow("block kw:", blockKw));
    if (dh.warnings && dh.warnings.length > 0) {
      nodes.push(mkRow("warnings:", dh.warnings.join("; ")));
    }

    // Scope section
    const scopeHdr = document.createElement("div");
    scopeHdr.style.cssText = "display:flex;align-items:center;gap:6px;padding:6px 0 4px 0;font-size:11px;font-weight:bold;color:var(--text)";
    scopeHdr.append(mkBadge(ds.ok), Object.assign(document.createElement("span"), {textContent: "Scope"}));
    nodes.push(scopeHdr);

    const sp = ds.policy || {};
    const defaultType = sp.default_action_type || "—";
    const actionTypes = Object.keys(sp.allowlists || {}).join(", ") || "—";
    nodes.push(mkRow("default type:", defaultType));
    nodes.push(mkRow("action types:", actionTypes));
    if (ds.warnings && ds.warnings.length > 0) {
      nodes.push(mkRow("warnings:", ds.warnings.join("; ")));
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollLiveSummaryDetailed() {
  try {
    const d = await api("/health/live-summary");
    const el = document.getElementById("live-summary-detailed-content");
    if (!el) return;

    const checks  = d.checks || [];
    const passed  = d.passed ?? 0;
    const total   = d.total  ?? 0;

    const allOk = d.ok !== false;
    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:6px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${allOk ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = `Live: ${passed}/${total} checks passing`;
    hdr.append(hdrText);

    const nodes = [hdr];

    if (checks.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No live checks configured.";
      nodes.push(empty);
    } else {
      checks.forEach(c => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;gap:6px;padding:2px 0;font-size:10px";
        const badge = document.createElement("span");
        badge.style.cssText = `font-size:9px;padding:1px 5px;border-radius:3px;font-weight:bold;flex-shrink:0;color:#fff;background:${c.ok ? "var(--green)" : "var(--red)"}`;
        badge.textContent = c.ok ? "OK" : "FAIL";
        const name = document.createElement("span");
        name.style.cssText = "color:var(--text)";
        name.textContent = c.name;
        row.append(badge, name);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollHealthDetailed() {
  try {
    const d = await api("/health/detailed");
    const el = document.getElementById("health-detailed-content");
    if (!el) return;

    const checks = d.checks || {};
    const sv  = checks.state_valid    || {};
    const cd  = checks.config_drift   || {};
    const ma  = checks.metrics_alerts || {};
    const slo = checks.slo_status     || {};

    const mkBadge = (ok) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${ok ? "var(--green)" : "var(--red)"}`;
      b.textContent = ok ? "OK" : "FAIL";
      return b;
    };
    const mkRow = (label, ok, detail) => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;padding:5px 0;border-bottom:1px solid var(--border);font-size:10px";
      const lbl = document.createElement("span");
      lbl.style.cssText = "color:var(--dim);width:120px;flex-shrink:0";
      lbl.textContent = label;
      const det = document.createElement("span");
      det.style.color = ok ? "var(--text)" : "var(--yellow)";
      det.textContent = detail;
      row.append(mkBadge(ok), lbl, det);
      return row;
    };

    const svDetail = sv.ok
      ? "state valid"
      : `${(sv.errors || []).length} error(s), ${(sv.warnings || []).length} warn(s)`;
    const cdDetail = cd.ok
      ? "no drift"
      : `${(cd.unknown_keys || []).length} unknown · ${cd.overridden_count || 0} overridden`;
    const maDetail = ma.ok
      ? "no alerts"
      : `${ma.alert_count || 0} alert(s) active`;
    const sloResults = slo.results || [];
    const sloDetail = sloResults.length
      ? sloResults.map(r => `${r.slo} ${r.status}`).join(" · ")
      : `${slo.records || 0} records (insufficient data)`;

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = `System Health: ${d.ok ? "OK" : "FAIL"}`;
    hdr.append(hdrText);

    // Fetch ws_clients from /health endpoint
    let wsClients = 0;
    try {
      const hd = await api("/health");
      wsClients = hd.ws_clients ?? 0;
    } catch (_) {}

    const wsRow = mkRow("WS Clients", true, `${wsClients} connected dashboard${wsClients !== 1 ? "s" : ""}`);
    wsRow.querySelector("span:last-child").style.color = wsClients > 0 ? "var(--green)" : "var(--dim)";
    wsRow.querySelector("span[style*='background']").style.background = "var(--surface)";
    wsRow.querySelector("span[style*='background']").style.color = "var(--dim)";
    wsRow.querySelector("span[style*='background']").textContent = wsClients > 0 ? `${wsClients}` : "0";

    const nodes = [hdr, mkRow("State Valid", sv.ok, svDetail),
                        mkRow("Config Drift", cd.ok, cdDetail),
                        mkRow("Metrics Alerts", ma.ok, maDetail),
                        mkRow("SLO Status", slo.ok !== false, sloDetail),
                        wsRow];

    if (sloResults.length) {
      sloResults.forEach(r => {
        const sub = document.createElement("div");
        sub.style.cssText = "display:flex;align-items:center;padding:3px 0 3px 16px;font-size:9px;color:var(--dim)";
        const badge = mkBadge(r.status === "ok");
        const txt = document.createElement("span");
        txt.textContent = `${r.slo}  target: ${r.target}  value: ${r.value ?? "—"}  (${r.detail || ""})`;
        sub.append(badge, txt);
        nodes.push(sub);
      });
    }
    if (!sv.ok && (sv.errors || []).length) {
      const errDiv = document.createElement("div");
      errDiv.style.cssText = "margin-top:5px;font-size:9px;color:var(--red)";
      errDiv.textContent = sv.errors.slice(0, 3).join(" · ");
      nodes.push(errDiv);
    }
    if (!ma.ok && (ma.alerts || []).length) {
      const aDiv = document.createElement("div");
      aDiv.style.cssText = "margin-top:5px;font-size:9px;color:var(--yellow)";
      aDiv.textContent = ma.alerts.map(a => a.name || a.message || "alert").slice(0, 3).join(" · ");
      nodes.push(aDiv);
    }

    el.replaceChildren(...nodes);

    const favicon = document.getElementById("favicon");
    if (favicon) {
      const color = d.ok ? "%2322c55e" : "%23ef4444";
      favicon.href = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='${color}'/%3E%3C/svg%3E`;
    }
  } catch (_) {}
}

export async function pollCiQualityDetailed() {
  try {
    const d = await api("/health/ci-quality");
    const el = document.getElementById("ci-quality-detailed-content");
    if (!el) return;

    const tools = d.tools || [];
    const count = d.count || 0;

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = "font-size:12px;font-weight:bold;color:var(--green)";
    hdrText.textContent = `CI Gate: ${count} tool${count !== 1 ? "s" : ""} configured`;
    hdr.append(hdrText);

    const nodes = [hdr];

    if (tools.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No CI tools configured.";
      nodes.push(empty);
    } else {
      tools.forEach(t => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;padding:3px 0;font-size:10px;border-bottom:1px solid var(--border)";
        const name = document.createElement("span");
        name.style.cssText = "color:var(--text)";
        name.textContent = t.name;
        row.append(name);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollPreReleaseDetailed() {
  try {
    const d = await api("/health/pre-release");
    const el = document.getElementById("pre-release-detailed-content");
    if (!el) return;

    const gates    = d.gates || [];
    const total    = d.total || 0;
    const required = d.required || 0;

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = "font-size:12px;font-weight:bold;color:var(--green)";
    hdrText.textContent = `Release Gates: ${total} (${required} required)`;
    hdr.append(hdrText);

    const nodes = [hdr];

    if (gates.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No release gates configured.";
      nodes.push(empty);
    } else {
      gates.forEach(g => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;gap:6px;padding:3px 0;font-size:10px;border-bottom:1px solid var(--border)";
        const badge = document.createElement("span");
        badge.style.cssText = `font-size:9px;padding:1px 5px;border-radius:3px;font-weight:bold;flex-shrink:0;color:#000;background:${g.required ? "var(--yellow, #e6a817)" : "var(--dim)"}`;
        badge.textContent = g.required ? "REQ" : "OPT";
        const name = document.createElement("span");
        name.style.cssText = "color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
        name.textContent = g.name;
        row.append(badge, name);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollRepoHealthDetailed() {
  try {
    const d = await api("/health/detailed");
    const el = document.getElementById("repo-health-detailed-content");
    if (!el) return;
    const rh = (d.checks || {}).repo_health || {};
    const mkBadge = (ok) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${ok ? "var(--green)" : "var(--red)"}`;
      b.textContent = ok ? "OK" : "WARN";
      return b;
    };
    const mkRow = (label, ok, detail) => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;padding:5px 0;border-bottom:1px solid var(--border);font-size:10px";
      const lbl = document.createElement("span");
      lbl.style.cssText = "color:var(--dim);width:110px;flex-shrink:0";
      lbl.textContent = label;
      const det = document.createElement("span");
      det.style.color = ok ? "var(--text)" : "var(--yellow)";
      det.textContent = detail;
      row.append(mkBadge(ok), lbl, det);
      return row;
    };
    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = "font-size:12px;font-weight:bold;color:var(--text)";
    hdrText.textContent = rh.available ? `AAWO · ${rh.complexity || "?"}` : "AAWO Repo Health";
    hdr.append(hdrText);
    const nodes = [hdr];
    if (rh.available) {
      const sigs = rh.signals || {};
      const active = Object.entries(sigs).filter(([, v]) => v).map(([k]) => k.replace(/^has_/, ""));
      nodes.push(mkRow("Signals", true, active.length ? active.join(", ") : "none"));
      nodes.push(mkRow("Complexity", true, `${rh.complexity || "?"} · ${rh.file_count || 0} files`));
      if ((rh.risk_factors || []).length) {
        nodes.push(mkRow("Risk Factors", false, rh.risk_factors.join(", ")));
      }
      if ((rh.active_agents || []).length) {
        const names = rh.active_agents.map(a => a.replace(/_agent$/, "")).join(", ");
        nodes.push(mkRow("Active Agents", true, names));
      }
      const os = rh.outcome_stats || {};
      const osEntries = Object.entries(os);
      if (osEntries.length) {
        const total = osEntries.reduce((s, [, c]) => s + (c.total || 0), 0);
        const ok    = osEntries.reduce((s, [, c]) => s + (c.success || 0), 0);
        const rate  = total ? Math.round(ok / total * 100) : 0;
        nodes.push(mkRow("Outcomes", rate >= 70, `${ok}/${total} success (${rate}%) across ${osEntries.length} agent(s)`));
      }
    } else {
      const msg = document.createElement("div");
      msg.style.cssText = "font-size:10px;color:var(--dim);padding:8px 0";
      msg.textContent = rh.error ? `unavailable: ${rh.error}` : "not configured — set AAWO_PATH in settings.json";
      nodes.push(msg);
    }
    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollBudgetDetailed() {
  try {
    const d = await api("/health/budget");
    const el = document.getElementById("budget-detailed-content");
    if (!el) return;

    const mkRow = (label, value, dim) => {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;padding:3px 0;border-bottom:1px solid var(--border);font-size:10px;gap:6px";
      const lbl = document.createElement("span");
      lbl.style.cssText = "color:var(--dim);min-width:110px;flex-shrink:0";
      lbl.textContent = label;
      const val = document.createElement("span");
      val.style.color = dim ? "var(--dim)" : "var(--text)";
      val.textContent = value;
      row.append(lbl, val);
      return row;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = "font-size:12px;font-weight:bold;color:var(--text)";
    hdrText.textContent = `Budget${d.has_limits ? "" : " — unlimited"}`;
    hdr.append(hdrText);

    const nodes = [hdr];

    const rateStr = d.sdk_success_rate != null
      ? `${Math.round(d.sdk_success_rate * 100)}%`
      : "—";
    nodes.push(mkRow("Steps run:",     `${d.total_steps || 0}`));
    nodes.push(mkRow("API calls:",     `${d.total_api_calls || 0} (${d.total_succeeded || 0} succeeded · ${rateStr})`));

    if (d.has_limits) {
      const costStr   = d.max_cost_usd           > 0 ? `$${d.max_cost_usd}` : "—";
      const tokStr    = d.max_total_tokens        > 0 ? `${d.max_total_tokens}` : "—";
      const callsStr  = d.max_api_calls_per_step  > 0 ? `${d.max_api_calls_per_step}/step` : "—";
      nodes.push(mkRow("Max cost:",    costStr,  costStr  === "—"));
      nodes.push(mkRow("Max tokens:",  tokStr,   tokStr   === "—"));
      nodes.push(mkRow("Max calls:",   callsStr, callsStr === "—"));
    } else {
      nodes.push(mkRow("Limits:", "none configured", true));
    }

    if ((d.recent_steps || []).length > 0) {
      const recHdr = document.createElement("div");
      recHdr.style.cssText = "font-size:10px;font-weight:bold;color:var(--dim);padding:5px 0 2px 0";
      recHdr.textContent = "Recent steps";
      nodes.push(recHdr);
      d.recent_steps.forEach(s => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;gap:10px;font-size:9px;color:var(--dim);padding:1px 0";
        const stepEl = document.createElement("span");
        stepEl.style.minWidth = "50px";
        stepEl.textContent = `step ${s.step}`;
        const calls = document.createElement("span");
        calls.textContent = `${s.dispatched}→${s.succeeded}`;
        const elapsed = document.createElement("span");
        elapsed.textContent = s.elapsed_s != null ? `${s.elapsed_s}s` : "";
        row.append(stepEl, calls, elapsed);
        nodes.push(row);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollPatchReviewDetailed() {
  try {
    const d = await api("/health/patch-review");
    const el = document.getElementById("patch-review-detailed-content");
    if (!el) return;

    const rejected = d.rejected_subtasks || [];

    const mkBadge = (val, color) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${color}`;
      b.textContent = val;
      return b;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    const noRejections = d.total_rejections === 0;
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${noRejections ? "var(--green)" : "var(--yellow, #e6a817)"}`;
    hdrText.textContent = `PatchReview: ${d.threshold_hits || 0} escalated · ${d.total_rejections || 0} rejected`;
    if (!d.enabled) hdrText.textContent += " [disabled]";
    hdr.append(hdrText);

    const nodes = [hdr];

    // SDK availability chip
    const sdkChip = document.createElement("div");
    sdkChip.style.cssText = "font-size:9px;margin-bottom:6px;display:flex;gap:6px;align-items:center";
    const sdkLabel = document.createElement("span");
    sdkLabel.style.cssText = `padding:1px 5px;border-radius:3px;font-weight:bold;color:#000;background:${d.available ? "var(--green)" : "var(--dim)"}`;
    sdkLabel.textContent = d.available ? "SDK" : "Heuristic";
    sdkChip.append(sdkLabel);
    const limitNote = document.createElement("span");
    limitNote.style.cssText = "color:var(--dim)";
    limitNote.textContent = `limit ${d.max_rejections} rejections/subtask`;
    sdkChip.append(limitNote);
    nodes.push(sdkChip);

    if (rejected.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:10px;color:var(--dim);padding:4px 0";
      empty.textContent = "No rejections recorded.";
      nodes.push(empty);
    } else {
      rejected.forEach(r => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:flex-start;padding:5px 0;border-bottom:1px solid var(--border);font-size:10px";
        const info = document.createElement("div");
        info.style.cssText = "flex:1;min-width:0";
        const name = document.createElement("div");
        name.style.cssText = "color:var(--text);font-weight:bold;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
        name.textContent = r.name || "—";
        const reason = document.createElement("div");
        reason.style.cssText = "color:var(--dim);font-size:9px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
        reason.textContent = r.last_reason || "";
        info.append(name, reason);
        const badgeColor = r.count >= (d.max_rejections || 3) ? "var(--red)" : "var(--yellow, #e6a817)";
        row.append(mkBadge(`×${r.count}`, badgeColor), info);
        nodes.push(row);
      });
    }

    // Recent reviews table (last 10 steps)
    const recent = d.recent_reviews || [];
    if (recent.length > 0) {
      const tblHdr = document.createElement("div");
      tblHdr.style.cssText = "font-size:9px;font-weight:bold;color:var(--dim);margin-top:8px;margin-bottom:4px";
      tblHdr.textContent = "Recent steps";
      nodes.push(tblHdr);
      recent.slice().reverse().forEach(rv => {
        const rrow = document.createElement("div");
        rrow.style.cssText = "display:flex;gap:8px;font-size:9px;padding:2px 0;border-bottom:1px solid var(--border)";
        const stepEl = document.createElement("span");
        stepEl.style.cssText = "color:var(--dim);min-width:42px";
        stepEl.textContent = `step ${rv.step}`;
        const appr = document.createElement("span");
        appr.style.cssText = "color:var(--green)";
        appr.textContent = `✓${rv.approved || 0}`;
        const rej = document.createElement("span");
        rej.style.cssText = `color:${rv.rejected > 0 ? "var(--red)" : "var(--dim)"}`;
        rej.textContent = `✗${rv.rejected || 0}`;
        const esc = document.createElement("span");
        esc.style.cssText = `color:${rv.escalated > 0 ? "var(--yellow, #e6a817)" : "var(--dim)"}`;
        esc.textContent = `⚠${rv.escalated || 0}`;
        rrow.append(stepEl, appr, rej, esc);
        nodes.push(rrow);
      });
    }

    el.replaceChildren(...nodes);
  } catch (_) {}
}

export async function pollPolicyEngineDetailed() {
  try {
    const d = await api("/policy/engine");
    const el = document.getElementById("policy-engine-detailed-content");
    if (!el) return;

    const mkBadge = (ok) => {
      const b = document.createElement("span");
      b.style.cssText = `font-size:9px;padding:1px 6px;border-radius:3px;font-weight:bold;margin-right:8px;flex-shrink:0;color:#000;background:${ok ? "var(--green)" : "var(--red)"}`;
      b.textContent = ok ? "OK" : "WARN";
      return b;
    };

    const mkCollapsible = (title, items) => {
      const container = document.createElement("div");
      const header = document.createElement("div");
      header.style.cssText = "display:flex;align-items:center;gap:6px;padding:4px 0;font-size:10px;font-weight:bold;color:var(--text);cursor:pointer";
      header.onclick = () => {
        const content = container.querySelector("[data-content]");
        const isHidden = content.style.display === "none";
        content.style.display = isHidden ? "block" : "none";
        arrow.textContent = isHidden ? "▼" : "▶";
      };
      const arrow = document.createElement("span");
      arrow.style.cssText = "font-size:8px;color:var(--dim);flex-shrink:0";
      arrow.textContent = items.length > 0 ? "▶" : "•";
      header.append(arrow);
      const titleSpan = document.createElement("span");
      titleSpan.textContent = title;
      header.append(titleSpan);
      container.append(header);

      if (items.length === 0) {
        const empty = document.createElement("div");
        empty.style.cssText = "font-size:9px;color:var(--dim);padding:2px 0;margin-left:14px";
        empty.textContent = "none";
        container.append(empty);
      } else {
        const content = document.createElement("div");
        content.setAttribute("data-content", "");
        content.style.cssText = "display:none;margin-left:14px";
        items.forEach(item => {
          const row = document.createElement("div");
          row.style.cssText = "font-size:9px;color:var(--dim);padding:2px 0;word-break:break-all";
          row.textContent = item;
          content.append(row);
        });
        container.append(content);
      }
      return container;
    };

    const hdr = document.createElement("div");
    hdr.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid var(--border)";
    const hdrText = document.createElement("span");
    hdrText.style.cssText = `font-size:12px;font-weight:bold;color:${d.ok ? "var(--green)" : "var(--red)"}`;
    hdrText.textContent = "Policy Engine";
    hdr.append(mkBadge(d.ok), hdrText);

    const nodes = [hdr];

    // Stats summary
    const stats = d.stats || {};
    const statsRow = document.createElement("div");
    statsRow.style.cssText = "display:flex;gap:12px;padding:4px 0;border-bottom:1px solid var(--border);font-size:10px;color:var(--dim)";
    const bcCount = document.createElement("span");
    bcCount.textContent = `Blocks: ${stats.policy_block_count || 0}`;
    const crCount = document.createElement("span");
    crCount.textContent = `Critical: ${stats.critical_path_review_count || 0}`;
    const opCount = document.createElement("span");
    opCount.textContent = `Oversized: ${stats.oversized_patch_count || 0}`;
    statsRow.append(bcCount, crCount, opCount);
    nodes.push(statsRow);

    // Limits
    const cfg = d.config || {};
    const limitsRow = document.createElement("div");
    limitsRow.style.cssText = "padding:4px 0;border-bottom:1px solid var(--border);font-size:9px;color:var(--dim)";
    const limitsText = document.createElement("span");
    limitsText.textContent = `Limits: ${cfg.max_files || 0} files · ${cfg.max_lines || 0} lines · ${cfg.max_patch_size || 0} bytes${cfg.require_review_for_critical ? " · review critical paths" : ""}`;
    limitsRow.append(limitsText);
    nodes.push(limitsRow);

    // Blocked paths
    nodes.push(mkCollapsible("Blocked Paths", d.blocked_paths || []));

    // Critical patterns
    nodes.push(mkCollapsible("Critical Patterns", d.critical_patterns || []));

    el.replaceChildren(...nodes);
  } catch (_) {}
}
