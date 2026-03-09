#!/usr/bin/env node
/**
 * lint_dashboard_handlers.js
 *
 * Parses dashboard.html for inline event handler function calls, then
 * cross-checks them against window.* assignments across all dashboard JS files.
 * Exits 1 and prints gaps if any handler function is not window-exposed.
 *
 * Usage: node tools/lint_dashboard_handlers.js
 */

"use strict";

const fs   = require("fs");
const path = require("path");

const ROOT   = path.resolve(__dirname, "..");
const HTML   = path.join(ROOT, "solo_builder", "api", "dashboard.html");
const JS_DIR = path.join(ROOT, "solo_builder", "api", "static");

// ── 1. Extract function names from inline handlers ─────────────────────────
const htmlSrc = fs.readFileSync(HTML, "utf8");

// Match on(click|input|change|focus|blur|keydown|keyup)="..." attributes
const HANDLER_ATTR_RE = /on(?:click|input|change|focus|blur|keydown|keyup)="([^"]*)"/g;

// Known built-ins that appear in IIFE bodies — not top-level calls we need to check
const SKIP = new Set([
  "function", "var", "if", "document", "event", "this", "return",
]);

const calledFns = new Set();
let m;
while ((m = HANDLER_ATTR_RE.exec(htmlSrc)) !== null) {
  const expr = m[1];
  // Extract identifiers that look like function calls: word(
  const callRE = /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g;
  let c;
  while ((c = callRE.exec(expr)) !== null) {
    const name = c[1];
    if (!SKIP.has(name)) calledFns.add(name);
  }
}

// ── 2. Extract window.* assignments from JS files ──────────────────────────
const WINDOW_ASSIGN_RE = /window\.([a-zA-Z_][a-zA-Z0-9_]*)\s*=/g;

const windowExposed = new Set();
const jsFiles = fs.readdirSync(JS_DIR).filter(f => f.startsWith("dashboard") && f.endsWith(".js"));

for (const file of jsFiles) {
  const src = fs.readFileSync(path.join(JS_DIR, file), "utf8");
  let w;
  while ((w = WINDOW_ASSIGN_RE.exec(src)) !== null) {
    windowExposed.add(w[1]);
  }
}

// ── 3. Find gaps ───────────────────────────────────────────────────────────
// Also exclude pure built-in global functions that are always available
const GLOBALS = new Set([
  "parseInt", "parseFloat", "encodeURIComponent", "decodeURIComponent",
  "setTimeout", "clearTimeout", "setInterval", "clearInterval",
  "alert", "confirm", "prompt", "fetch", "console", "Math",
  // DOM built-ins that appear inside IIFE bodies in inline handlers
  "getElementById", "querySelector", "querySelectorAll",
  "addEventListener", "removeEventListener", "dispatchEvent",
]);

const gaps = [...calledFns].filter(fn => !windowExposed.has(fn) && !GLOBALS.has(fn));

// ── 4. Report ─────────────────────────────────────────────────────────────
console.log(`dashboard handler audit:`);
console.log(`  handler calls found : ${calledFns.size}`);
console.log(`  window.* exposed    : ${windowExposed.size}`);
console.log(`  js files scanned    : ${jsFiles.length}`);

if (gaps.length === 0) {
  console.log("  result              : PASS — 0 gaps");
  process.exit(0);
} else {
  console.error(`  result              : FAIL — ${gaps.length} gap(s)`);
  for (const fn of gaps) {
    console.error(`    MISSING: ${fn}()`);
  }
  process.exit(1);
}
