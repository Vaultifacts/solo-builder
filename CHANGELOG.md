# Changelog

## v5.20.0 — 2026-03-10  AnthropicMaxTokensIncrease — 256→4096 across all locations (TASK-330)

- **330 tasks** merged to master; **1329 tests**, all passing
- `config/settings.json`, `api/constants.py`, `runners/anthropic_runner.py`, `runners/executor.py`, `solo_builder_cli.py`: ANTHROPIC_MAX_TOKENS raised from 256 → 4096 — 256 tokens (~200 words) was insufficient for meaningful subtask outputs from the plain SDK execution path — TASK-330

---

## v5.19.0 — 2026-03-10  SubtaskToolsFieldFix — CLAUDE_ALLOWED_TOOLS propagated to new subtasks (TASK-329)

- **329 tasks** merged to master; **1329 tests**, all passing
- `commands/dag_cmds.py`: `_cmd_add_task` and `_cmd_add_branch` now call `st.setdefault("tools", CLAUDE_ALLOWED_TOOLS)` after subtask creation; previously the tools field was never set at creation time, making the `sdk_tool_jobs` routing branch in `executor.py` permanently unreachable — TASK-329
- `tests/test_dag_cmds_tools.py`: 6 unit tests covering tools propagation in `add_task`, `add_branch`, `setdefault` idempotency, and sdk_tool routing reachability smoke test — TASK-329

---

## v5.18.0 — 2026-03-10  DependencyAuditCheck — pip-audit script + 16 tests (TASK-328)

- **328 tasks** merged to master; **1323 tests**, all passing
- `tools/dep_audit.py`: version drift detection vs requirements-lock.txt + pip-audit CVE scan; writes dep_audit_result.json; non-zero exit on drift or vulns — TASK-328
- `claude/VERIFY.json`: added non-required `dep-audit` step (`python tools/dep_audit.py --check-only`) — TASK-328
- `tests/test_dep_audit.py`: 16 unit tests covering _parse_lock, _check_drift, _run_pip_audit (mocked), main() — TASK-328
- `.gitignore`: dep_audit_result.json excluded — TASK-328

---

## v5.17.0 — 2026-03-10  ApiInputValidation — validators.py + 20 tests (TASK-327)

- **327 tasks** merged to master; **1307 tests**, all passing
- `api/validators.py`: `require_string_fields(*required, optional=())` — validates JSON dict body, required fields non-blank strings, optional fields type-checked, MAX_FIELD_LEN=4096 — TASK-327
- `api/blueprints/triggers.py`: 6 endpoints (/heal, /add_task, /add_branch, /prioritize_branch, /depends, /undepends) now use `require_string_fields` — type confusion + oversized payload protection — TASK-327
- `tests/test_validators.py`: 11 unit tests for validator helper + 9 endpoint integration tests (missing fields, wrong types, oversized input) — TASK-327

---

## v5.16.0 — 2026-03-10  StructuredLogFormatter — JsonLogFormatter + use_json flag (TASK-326)

- **326 tasks** merged to master; **1287 tests**, all passing
- `utils/log_formatter.py`: `JsonLogFormatter(logging.Formatter)` — emits one JSON object per line with ts/level/logger/msg fields; exc key added on exception — TASK-326
- `cli_utils._setup_logging`: new `use_json=False` parameter; selects JsonLogFormatter when True, preserving text format as default — TASK-326
- `tests/test_log_formatter.py`: 12 unit tests covering JSON output, ISO-8601 ts, exc field, one-line output, formatter selection — TASK-326

---

## v5.15.0 — 2026-03-10  Windows log-lock test fix (TASK-325b)

- **1275 tests**, all passing (0 failures — Windows file-lock race fixed)
- `tests/test_cli_utils.py`: `_close_sb_log_handlers()` flushes and closes RotatingFileHandler stream before `rmtree` to release Windows OS lock on log file — TASK-325

---

## v5.14.0 — 2026-03-10  datetime deprecation fix, flaky test fix, Phase 2 design complete (TASK-325)

- **325 tasks** merged to master; **1275 tests**, all passing, zero warnings
- `runners/executor.py`: replaced deprecated `datetime.utcnow()` with `datetime.now(datetime.timezone.utc)` — fixes Python 3.13 DeprecationWarning — TASK-325
- `tests/test_cli_utils.py`: fixed flaky `test_clear_stale_triggers_*` — replaced `TemporaryDirectory()` with `mkdtemp()` + `rmtree(ignore_errors=True)`; `_close_sb_log_handlers` now explicitly flushes and closes the underlying stream before calling `handler.close()` to release Windows file locks — TASK-325
- `api/test_app.py`: added docstring to `_Base._make_state` pointing new test authors to `tests/factories.py` — TASK-325
- `docs/CLI_REFACTOR_DESIGN.md`: Phase 2 documented as ~95% complete (TASK-107); `_cmd_set` is the only remaining method, blocked by module-global mutation pattern; path forward via `self._runtime_cfg` instance dict documented — TASK-325

---

## v5.13.0 — 2026-03-10  Rate limiter 429 tests, EXEC_VERIFY_PROB fix, Phase 2 audit (TASK-324)

- **324 tasks** merged to master; **1249 tests** (excl. flaky Windows log-lock), all passing
- `solo_builder/solo_builder_cli.py`: fixed `EXEC_VERIFY_PROB` global drift — `do_set VERIFY_PROB` now writes `global EXEC_VERIFY_PROB; EXEC_VERIFY_PROB = v` so the module-level global stays in sync with `self.executor.verify_prob` — TASK-324
- `solo_builder/api/test_app.py`: +4 `TestRateLimiterIntegration` tests — assert 429 via `_rate_limiter.check` mock, error key in body, write method triggers 429, under-limit returns 200; reset rate limiter counters in `_Base.setUp` to prevent cross-test contamination — TASK-324
- `docs/CLI_REFACTOR_DESIGN.md`: Phase 2 risk downgraded to Low — audit confirmed 0 tests patch `do_*` methods; Phase 2 now blocked by implementation time only — TASK-324
- `claude/TASK_QUEUE.md`: backfilled TASK-322, TASK-323, TASK-324 entries with completion status — TASK-324

---

## v5.12.0 — 2026-03-10  CLI refactor analysis + security header integration tests (TASK-323)

- **323 tasks** merged to master; **208 tests**, all passing
- `docs/CLI_REFACTOR_DESIGN.md`: corrected Phase 1 analysis — 6 of 8 "read-only" constants are mutable via `do_set` (`STALL_THRESHOLD`, `SNAPSHOT_INTERVAL`, `VERBOSITY`, `AUTO_STEP_DELAY`, `AUTO_SAVE_INTERVAL`, `CLAUDE_ALLOWED_TOOLS`); 13 truly read-only constants identified; Phase 1 demoted to low-priority — TASK-323
- `solo_builder/api/test_app.py`: +5 Flask test-client integration tests (`TestSecurityHeadersIntegration`) asserting all security headers arrive end-to-end through the real `@after_request` hook, including HSTS — TD-TEST-003 resolved — TASK-323
- `docs/TECH_DEBT_REGISTER.md`: TD-SEC-003 (HSTS) and TD-TEST-003 (header integration tests) added and resolved — TASK-323

---

## v5.11.0 — 2026-03-10  Middleware extraction + CLI refactor design spike (TASK-322)

- **322 tasks** merged to master; **203 tests**, all passing
- `solo_builder/api/middleware.py`: `SecurityHeadersMiddleware` (7 headers: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP, HSTS, CORS) + `ApiRateLimiter` (sliding-window, per-IP, separate read/write counters, `current_count()`) extracted from `app.py` inline implementations — TD-SEC-001 partial (HSTS now present)
- `solo_builder/api/app.py`: replaced 20-line inline rate-limit + security-headers implementations with `_security.apply()` and `_rate_limiter.check()` — TASK-322
- `solo_builder/api/test_app.py`: +16 middleware tests — `TestSecurityHeadersMiddleware` (7) + `TestApiRateLimiter` (9): all 7 headers asserted, allow/deny semantics, read/write independence, window pruning, `current_count` — TASK-322
- `docs/CLI_GOD_FILE_REFACTOR.md`: design spike for splitting `solo_builder_cli.py` (TD-ARCH-001); 5 frozen globals constraint documented; Phase 1 scoped, Phases 2–3 deferred — TASK-322

---

## v5.10.0 — 2026-03-10  Structured logging + prompt version control (TASK-320 through TASK-321)

- **321 tasks** merged to master; **187 tests**, all passing
- `runners/executor.py`: replace `print()` dispatch announcements with `logger.info()` — SDK tool-use, Claude, SDK direct paths all emit structured log records — TASK-320
- `docs/PROMPT_REGISTRY.md`: prompt version registry — 4 templates (PROMPT-001..004) with SHA-256 hashes, source locations, hash update process. AI-004 and AI-005 resolved — TASK-321
- `solo_builder/tests/test_prompt_registry.py`: 5 hash regression tests; prompt changes surface as assertion failures with hash diff — TASK-321

---

## v5.9.0 — 2026-03-10  Layer 3 audit: prompt standard, HITL gate, security hardening (TASK-311 through TASK-319)

- **319 tasks** merged to master; **187 tests** (182 non-API + 5 metrics), all passing
- `docs/PROMPT_STANDARD.md`: prompt engineering standard — context prefix rules, template, regression testing guidelines — TASK-311
- `test_prompt_standard.py`: 23 regression tests guarding `_PROJECT_CONTEXT`, DAG description quality, all 3 execution paths — TASK-311
- AI-002 resolved: `executor.py` subprocess path + `dag_cmds.py` decomp prompts now prepend `_PROJECT_CONTEXT` — TASK-312
- `docs/HITL_TRIGGER_DESIGN.md`: formal HITL trigger levels (0=Auto, 1=Notify, 2=Pause, 3=Block), trigger criteria, 3-phase plan — TASK-312
- `docs/AI_ACTION_SCOPE.md`: tool policy table (Read/Glob/Grep=Auto, Bash/Write/Edit=Pause, Web=Notify) — TASK-313
- `runners/hitl_gate.py`: `evaluate(tools, description)` + `HITLBlockError` + `level_name()`; 28 tests in `test_hitl_gate.py` — TASK-313
- `docs/THREAT_MODEL.md`: 6 threats (T-001..T-006); SE-001 resolved, SE-002..006 tracked — TASK-314
- `docs/SLO_DEFINITIONS.md`: 6 SLOs — API tests 100%, Discord tests 100%, SDK success ≥95%, gate checks 14/14, step latency ≤10s, Notion sync ≥99% — TASK-315
- `docs/CONTEXT_WINDOW_STRATEGY.md`: compaction triggers, 200-line MEMORY.md limit, journal archival procedure — TASK-316
- `docs/TECH_DEBT_REGISTER.md`: 9 initial open items across 5 categories — TASK-317
- `runners/executor.py`: HITL gate wired (TD-ARCH-002); validate_tools called before dispatch (TD-ARCH-005); subprocess fallback warns — TASK-318
- `runners/sdk_tool_runner.py`: `validate_tools()` function (TD-ARCH-005); `Read` path allowlist restricts to repo root (TD-SEC-001) — TASK-318
- `runners/test_runners.py`: +15 tests — TestValidateTools, TestSdkToolRunnerPathAllowlist, TestExecutorRouting — TASK-318
- `tools/requirements-lock.txt`: pinned dependencies for tools/ (TD-SEC-002) — TASK-318
- `solo_builder/requirements.txt`: explicit dependency file with `anthropic>=0.40` (TD-DEP-001) — TASK-318
- `runners/executor.py`: `_write_step_metrics()` — per-step JSONL: elapsed_s, sdk_dispatched, sdk_succeeded, sdk_success_rate (TD-OPS-001) — TASK-319
- `docs/TECH_DEBT_REGISTER.md` updated: 9 of 10 items resolved; 1 remaining (TD-ARCH-001 god file) — TASK-319
- Post-commit hook installed at `.githooks/post-commit` (Notion sync on every commit)

---

## v5.8.0 — 2026-03-09  Branch pct fields + Discord min_age + stalled clear button (TASK-301 through TASK-310)

- **310 tasks** merged to master (TASK-001 through TASK-310); **600 API tests**, **305 Discord tests**
- `GET /branches`: `review_pct` field added (% of Review subtasks per branch); 3 new tests — TASK-301
- Stalled tab: "✕ Clear" button shown when task or branch filter active; clears both filters + re-polls; parity with Branches/Subtasks tabs — TASK-302
- Discord `/branches export:True` slash command: 4 new integration tests covering file attachment and CSV content — TASK-303
- `GET /history/export ?branch=` filter: already implemented and fully tested (pre-complete) — TASK-304
- `GET /stalled ?min_age=N`: optional override for STALL_THRESHOLD; 3 new tests — TASK-305
- Dashboard Export tab stalled hrefs already use `?min_age=<threshold>` dynamically (pre-complete) — TASK-306
- Discord `/stalled min_age:int=0` param: overrides STALL_THRESHOLD for the call; shows override note in output; 3 new tests — TASK-307
- `GET /branches`: `pending_pct` field added (% pending subtasks per branch, parity with `pct`/`review_pct`); 3 new tests — TASK-308
- Dashboard Branches tab: review count now shows `review_pct` alongside (e.g. `2⏸ (40%)`) in overview table — TASK-309
- CHANGELOG v5.8.0 — TASK-310

---

## v5.7.0 — 2026-03-09  300-task milestone: branch review field + Discord subtasks text command (TASK-295 through TASK-300)

- **300 tasks** merged to master (TASK-001 through TASK-300); **591 API tests**, **298 Discord tests**
- CHANGELOG v5.6.0 documented — TASK-295
- `GET /subtasks/export` JSON wrapper shape (`subtasks` key + `total` count) and `?status=Review/Pending` filter tests; 4 new tests — TASK-296
- Stalled tab: `#stalled-filter-label` span shows active filter state (e.g. `· task: X · branch: Y`) below filter inputs; UI-only — TASK-297
- `GET /branches`: `review` field added to each row; `?status=review` + `?status=pending` filter tests; `?task=`+`?status=` compose test; 4 new tests — TASK-298
- Discord `subtasks` plain-text command: `subtasks [task=X] [status=Y]` dispatches to `_format_subtasks()`; supports multi-word task names; help text updated; 4 new tests — TASK-299
- **300-task milestone** CHANGELOG v5.7.0 — TASK-300

---

## v5.6.0 — 2026-03-09  Stalled tab UX + Discord filters + test coverage (TASK-291 through TASK-294)

- **294 tasks** merged to master (TASK-001 through TASK-294); **583 API tests**, **294 Discord tests**
- CHANGELOG v5.5.0 documented — TASK-291
- Stalled tab: `#stalled-branch-filter` input added (parity with task filter); composes `?task=` and `?branch=` in `pollStalled()` — TASK-292
- Discord `/history`: optional `task=`, `branch=`, `status=` filter params; `_format_history()` updated; 4 new tests — TASK-293
- `GET /branches/export`: `?status=review` and `?status=pending` filter tests added; JSON `total` invariant verified; 4 new tests — TASK-294

---

## v5.5.0 — 2026-03-09  Stalled filters + Stalled tab UX + Discord /stalled filters (TASK-287 through TASK-290)

- **290 tasks** merged to master (TASK-001 through TASK-290); **579 API tests**, **290 Discord tests**
- CHANGELOG v5.4.0 documented — TASK-287
- `GET /stalled` accepts `?branch=` substring filter (parity with `?task=`); 3 new tests — TASK-288
- Stalled tab: `#stalled-task-filter` input re-fetches `GET /stalled?task=X` on each keystroke — TASK-289
- Discord `/stalled`: optional `task=` and `branch=` params; `_format_stalled()` updated with filters; 4 new tests — TASK-290

---

## v5.4.0 — 2026-03-09  Export fixes + Discord CSV + stalled filters (TASK-283 through TASK-286)

- **286 tasks** merged to master (TASK-001 through TASK-286); **576 API tests**, **286 Discord tests**
- CHANGELOG v5.3.0 documented — TASK-283
- History export link bug fixed: quick-filter status values (Pending/Running/Review/Verified) now route to `?status=` instead of `?subtask=`; hint text updated — TASK-284
- Discord `/subtasks export:True` sends CSV file attachment; `_subtasks_to_csv()` formatter + 6 tests — TASK-285
- `GET /stalled` accepts `?task=` substring filter; 3 new tests — TASK-286

---

## v5.3.0 — 2026-03-09  Clear buttons + stalled UX + export rows + Discord /subtasks (TASK-278 through TASK-282)

- **282 tasks** merged to master (TASK-001 through TASK-282); **573 API tests**, **280 Discord tests**
- Branches tab: "✕ Clear" button shown when status/task filters active; calls `_clearBranchesFilters()` — TASK-278
- Export tab: "Stalled Subtasks" row links to `/subtasks/export?status=running&min_age=<threshold>`; threshold fetched from `GET /stalled` on tab open — TASK-279
- Dashboard `hdr-badge` tooltip shows worst-offending branch on hover when stalled > 0: `"N stalled — worst: task/branch (count)"` — TASK-280
- `GET /history/export` `?task=` filter: 5 new tests (match, no-match, case-insensitive, compose, CSV) — TASK-281
- Discord `/subtasks` slash command: `task=` + `status=` optional filters; `_format_subtasks()` formatter; 6 new tests — TASK-282

---

## v5.2.0 — 2026-03-09  Cross-endpoint tests + filter UX + min_age + server-side exports (TASK-273 through TASK-277)

- **277 tasks** merged to master (TASK-001 through TASK-277); **568 API tests**, **274 Discord tests**
- Cross-endpoint stall invariant tests: `/status.stalled_by_branch` == `/stalled.by_branch` (count, sum, entries, zero-stall) — TASK-273
- Subtasks tab: "✕ Clear" button shown when any filter active; calls `_clearSubtasksFilters()` — TASK-274
- `GET /subtasks` + `GET /subtasks/export` accept `?min_age=N` to return only Running subtasks stalled ≥ N steps; 5 new tests — TASK-275
- Branches tab: CSV/JSON downloads switched to server-side `/branches/export` with active ?status= and ?task= filter params — TASK-276
- CHANGELOG v5.1.0 documented — TASK-277 (this entry)

---

## v5.1.0 — 2026-03-09  Stall breakdown + filter UX + sort parity (TASK-267 through TASK-272)

- **272 tasks** merged to master (TASK-001 through TASK-272); **559 API tests**, **274 Discord tests**
- Stalled tab: per-branch summary card when multiple branches stalling, sorted by count desc — TASK-267
- `GET /stalled` includes `by_branch: [{task, branch, count}]` sorted desc; 5 new tests — TASK-268
- Discord `/stalled`: per-branch grouping summary block when multiple branches stalling; 5 new tests — TASK-269
- Subtasks tab: `#subtasks-filter-label` shows active filters + result count beside quick-filter buttons — TASK-270
- `GET /status` `stalled_by_branch` sorted by count desc (parity with GET /stalled); 1 new test — TASK-271
- CHANGELOG v5.0.0 documented — TASK-272 (this entry)

---

## v5.0.0 — 2026-03-09  Filter resets + Export tab completeness + Discord CSV + stall breakdown (TASK-262 through TASK-266)

- **266 tasks** merged to master (TASK-001 through TASK-266); **553 API tests**, **269 Discord tests**
- `selectTask()` clears all subtask filters (status/name/task/branch) + input values on task switch — TASK-262
- Export tab: Branches (CSV+JSON via /branches/export) and Subtasks (CSV+JSON via /subtasks/export) rows added — TASK-263
- Discord `/branches export:True` sends full CSV file attachment; `_branches_to_csv()` formatter + 6 tests — TASK-264
- `GET /status` now includes `stalled_by_branch: [{task, branch, count}]` for per-branch stall breakdown; 5 new tests — TASK-265
- CHANGELOG v4.9.0 documented — TASK-266 (this entry)

---

## v4.9.0 — 2026-03-09  Branches export + subtasks branch filter + export link re-sync (TASK-258 through TASK-261)

- **261 tasks** merged to master (TASK-001 through TASK-261); **548 API tests**, **454 Discord tests**
- `GET /branches/export` endpoint added; CSV/JSON download with ?task=, ?status=, ?format=json — TASK-258
- Subtasks tab: `#subtasks-branch-filter` input wired to server `?branch=` filter + export links — TASK-259
- Subtasks tab export links re-synced on tab switch via `switchTab("subtasks")` → `_updateSubtasksExportLinks()` — TASK-260
- CHANGELOG v4.8.0 documented — TASK-261 (this entry)

---

## v4.8.0 — 2026-03-09  Server-side filters + UI filter inputs + stall cross-task tests (TASK-251 through TASK-257)

- **257 tasks** merged to master (TASK-001 through TASK-257); **534 API tests**, **454 Discord tests**
- `GET /subtasks` + `GET /subtasks/export` accept `?name=` substring filter on subtask name — TASK-251
- `renderSubtasks()` routes non-status text to server-side `?name=` re-fetch; export links include `&name=X` — TASK-252
- `GET /branches` accepts `?status=pending|running|review|verified`; applied before pagination; dashboard re-fetches on filter change — TASK-253
- Stall detection cross-task tests: count across 2 tasks × 2 branches, task/branch metadata fields, `/status.stalled == /stalled.count` — TASK-254
- Subtasks tab: `#branches-task-filter` input wired to server `?task=` filter + export links — TASK-255
- Branches tab: task filter input wired to server `?task=` filter; shown only in all-tasks view — TASK-256
- CHANGELOG v4.7.0 documented — TASK-250 (prior batch entry)

---

## v4.7.0 — 2026-03-09  Branches export + task filter + stall tests + history branch filter (TASK-246 through TASK-250)

- **250 tasks** merged to master (TASK-001 through TASK-250); **512 API tests**, **454 Discord tests**
- Branches tab CSV/JSON client-side download (filtered data via `Blob` + `URL.createObjectURL`) — TASK-246
- `GET /tasks` accepts `?task=` substring filter; dashboard `_applyTaskSearch` re-fetches server-side — TASK-247
- Stall detection boundary + regression tests: at-threshold, below-threshold, custom `STALL_THRESHOLD`, `/status.stalled` == `/stalled.count` (+7 tests) — TASK-248
- `GET /history/export` was silently ignoring `?branch=` parameter; now correctly filters (+5 tests) — TASK-249
- CHANGELOG v4.6.0 documented — TASK-245 (prior batch entry)

---

## v4.6.0 — 2026-03-09  Status filters + CI lint + review regressions (TASK-236 through TASK-245)

- **245 tasks** merged to master (TASK-001 through TASK-245); **498 API tests**, **454 Discord tests**
- Subtasks quick-filter (Pending/Running/Review/Verified) re-fetches with `?status=X` server-side; composes with pagination — TASK-236
- Branches all-tasks view: `review` count badge rendered per row (field added TASK-229, previously not displayed) — TASK-237
- Search inputs reset page to 1 on change (`_applyTaskSearch`, `renderSubtasks` non-status branch) — TASK-238
- `tools/lint_dashboard_handlers.js` — Node.js CI script cross-checks HTML inline handlers vs `window.*`; exits 1 on gaps — TASK-239
- Lint script wired into `.githooks/pre-commit`; runs automatically on every commit — TASK-241
- Subtasks CSV/JSON export links updated with `?status=X` when status filter active — TASK-242
- Branches all-tasks view: Pending/Running/Review/Verified quick-filter buttons (client-side, cached data) — TASK-243
- Subtask detail modal shows `Review ⏸` (yellow) when status is Review — TASK-240
- `review_subtasks` regression tests: multi-branch sum, not-in-pct, separate-from-running (+3) — TASK-244
- CHANGELOG v4.5.0 documented — TASK-235 (prior batch entry)

---

## v4.5.0 — 2026-03-09  Pager UIs + window-exposure audit + CI invariant (TASK-226 through TASK-235)

- **235 tasks** merged to master (TASK-001 through TASK-235); **495 API tests**, **454 Discord tests**
- `GET /branches` supports `?limit=N&page=P`; response adds `total`, `page`, `pages`; `review` field added per row; `pending` formula fixed (was omitting review) — TASK-229
- Dashboard **Subtasks tab** pager `◀/▶` added; `pollSubtasks()` fetches `?limit=50&page=N` — TASK-231
- Dashboard **Branches tab** all-tasks pager `◀/▶` added; hidden in per-task detail view — TASK-232
- Dashboard **Tasks panel** pager `◀/▶` added below task grid — TASK-233
- ES module `window.*` gap audit: `_applyTaskSearch` and `_renderCacheHistory` exposed — TASK-230
- Final inline handler audit: zero gaps remain across all 50 handler calls in dashboard.html — TASK-234
- CI invariant check (`tools/ci_invariant_check.ps1`) implemented; enforces test-count floor — TASK-019 (backfill)
- CHANGELOG v4.4.5 documented — TASK-226 (prior batch entry)

---

## v4.4.5 — 2026-03-09  Pagination + pager fixes + Export chips + metrics tests (TASK-221 through TASK-225)

- **225 tasks** merged to master (TASK-001 through TASK-225); **489 API tests**, **454 Discord tests**
- `GET /tasks` supports `?limit=N&page=P`; response adds `total`, `page`, `pages` (backward-compatible) — TASK-225
- History pager `◀/▶` buttons fixed (exposed `window._historyPageStep`); count label shows `· N⏸` — TASK-224
- `GET /metrics` review regression tests (exact count + pending exclusion) — TASK-223
- Export tab shows `/history/count` by_status chips on open — TASK-222
- CHANGELOG v4.4.0 documented — TASK-221

---

## v4.4.0 — 2026-03-09  History review metadata + by_status chips + stalled regression (TASK-216 through TASK-220)

- **220 tasks** merged to master (TASK-001 through TASK-220); **481 API tests**, **454 Discord tests**
- `GET /history` response includes `review` count at top level (pre-pagination, like `total`) — TASK-217
- `GET /history/count` `by_status` dict consumed by dashboard: History tab status chips — TASK-218
- `GET /stalled` Review-exclusion regression tests (3 new assertions) — TASK-219
- MEMORY.md pruned 384→75 lines; archived to 4 topic files (architecture, test_patterns, discord_bot, design_decisions) — TASK-220
- CHANGELOG v4.3.5 documented — TASK-216

---

## v4.3.5 — 2026-03-09  History hash persistence + review stat box + /history/count distribution (TASK-213 through TASK-215)

- **215 tasks** merged to master (TASK-001 through TASK-215); **475 API tests**, **454 Discord tests**
- History filter persisted to `location.hash` as `ht-filter=<value>`; broken inline handlers fixed — TASK-213
- `hdr-pending` stat box shows `⏸N` review count alongside pending when review > 0 — TASK-214
- `GET /history/count` now returns `by_status` dict with per-status event counts (Review included) — TASK-215

---

## v4.2.9 — 2026-03-09  Review status in all endpoints + URL hash filter (TASK-203 through TASK-209)

- **210 tasks** merged to master (TASK-001 through TASK-210); **471 API tests**, **451 Discord tests**
- `GET /status` now returns `review` count; `pending` excludes review — TASK-206
- `GET /dag/summary` per-task rows and top-level include `review`; summary text updated — TASK-208
- Header step counter (`hdr-step`) appends `· N⏸` when review > 0 — TASK-207
- Subtasks filter persisted to `location.hash` as `st-filter=<value>` (deep-linkable) — TASK-209
- CHANGELOG v4.2.2 200-task milestone documented — TASK-203

---

## v4.1.4 – v4.2.2 — 2026-03-09  Review Status Propagation (TASK-181 through TASK-202)

- **202 tasks** total; **464 API + 447 Discord tests**
- Review visible everywhere: card badge (⏸N yellow), card counts, detail bar, per-branch rows, header counter, Discord formatter, History/Subtasks quick-filters (TASK-186–202)
- `GET /tasks` includes `pct` and `review_subtasks`; `/tasks/<id>/progress` branches[] includes `review` (TASK-188, 196)
- `pollTaskProgress()` updates per-branch mini rows in-place; uses branches[] from /progress (TASK-192)
- Subtasks + History tabs: 4 toggle quick-filter buttons (Pending/Running/Review/Verified) (TASK-199, 201)
- `GET /stalled` and Discord `stalled` confirmed to exclude Review/Pending; tests added (TASK-194, 200)
- CHANGELOG v4.0.0 milestone entry created (TASK-181)

---

## v4.0.0 — 2026-03-09  Milestone: 180 Tasks Complete

### Summary
- **180 tasks** merged to master (TASK-001 through TASK-180)
- **451 API tests** (test_app.py), **439 total tests** across all test files — 0 failures
- **Architecture score**: 97.7 / 100 (effective ceiling — remaining majors are intentional autonomy patterns)
- **Zero innerHTML** across all 7 ES module dashboard files (all DOM API)

### Major Features Added (selected highlights)

#### API
- Flask app refactored from 1729-line monolith → 13 blueprints in `api/blueprints/`
- Endpoints added: `/dag/summary`, `/branches`, `/branches/<task>`, `/subtasks`, `/subtasks/export`,
  `/tasks/<id>/subtasks`, `/tasks/<id>/branches`, `/tasks/<id>/progress` (with per-branch `branches[]`),
  `/tasks/<id>/timeline`, `/tasks/<id>/bulk-reset`, `/tasks/<id>/bulk-verify`, `/tasks/<id>/reset`,
  `/config/export`, `/config/reset`, `/health`, `/shortcuts`, `/dag/export`, `/tasks/export`
- `GET /tasks/<id>/progress` now returns `branches[]` breakdown per branch

#### Dashboard (ES modules)
- `dashboard.js` (1664 lines) split into 7 ES modules: `dashboard_state.js`, `dashboard_utils.js`,
  `dashboard_tasks.js`, `dashboard_panels.js`, `dashboard_branches.js`, `dashboard_cache.js`,
  `dashboard_svg.js`
- Keyboard shortcuts: `j/k` nav, `←/→` history paging, `r` run, `g` graph, `v` verify,
  `p` pause, `b` branches, `s` subtasks, `h` history, `?` help, `Esc` close
- Task detail panel: per-branch mini progress rows (TASK-176)
- `pollTaskProgress()` — in-place progress bar update via stable element IDs (TASK-180)
- Bulk-select UI in Branches and Subtasks tabs; 3-second auto-clear feedback (TASK-157/166)
- Pipeline Overview in Branches all-tasks view with per-task mini bars (TASK-121)
- SVG sparkline in subtask modal from `/timeline/<id>` (TASK-094)
- Toast notification history (max 20, 🔔 button) (TASK-098)
- Dark/light theme toggle persisted to `localStorage` (TASK-093)

#### Discord Bot
- 40+ slash commands extracted to `bot_slash.py`; formatters to `bot_formatters.py`
- New commands: `/task_progress`, `/bulk_reset`, `/bulk_verify`, `/branches`, `/forecast`,
  `/tasks`, `/filter`, `/agents`, `/heartbeat`, `/cache`
- `_format_task_progress()` — per-branch block-bar progress table

#### CLI / Runners
- `solo_builder_cli.py` refactored 2965 → 665 lines via mixin classes + 4 extracted modules
- `api/app.py` refactored 1729 → 84 lines
- `discord_bot/bot.py` refactored 2086 → 925 lines
- Response cache with SHA-256 keying, hit/miss stats, session stats in JOURNAL
- Async SDK runner (`AnthropicRunner` + `SdkToolRunner`) with rate-limit retry

### Test Coverage Additions (selected)
- `test_api_integration.py` (52 tests) — TASK-114
- `tests/test_utils_standalone.py` (30 tests) — TASK-117
- `test_cli_utils.py` (+20 tests) — TASK-122
- `TestBulkResetCommand`, `TestBulkVerifyCommand`, slash command variants — TASK-156/171
- `TestFormatTaskProgress` (7 direct unit tests) — TASK-178

### Architecture Notes
- **`/branches/<task>`** kept alongside `/tasks/<id>/branches` — former includes `subtasks[]` array
  needed by dashboard detail view; latter is the paginated branch-counts endpoint
- **`POST /tasks/<id>/reset`** (destructive, clears output) kept alongside `/bulk-reset`
  (preserves output, has `include_verified` flag) — different semantics, both valid
- **Test-patch gotcha** for CLI mixins: patch `solo_builder_cli.X` not mixin module globals;
  five globals (`_PDF_OK`, `_CFG_PATH`, `STATE_PATH`, `JOURNAL_PATH`, `WEBHOOK_URL`) must
  remain in `solo_builder_cli.py` or test patches won't take effect

---

## v3.x.x — 2025–2026  (TASK-001 through TASK-139)

See git log for individual task entries.
