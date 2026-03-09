# HANDOFF: RESEARCH -> ARCHITECT
Task: TASK-105
Goal: Refactor solo_builder/api/dashboard.html: extract inline JavaScript and CSS into separate static files

---

## File Analysis

`solo_builder/api/dashboard.html` — 2587 lines (monolithic SPA):
- Lines 1-7: HTML `<head>` (meta, title, favicon)
- Lines 8-581: `<style>` block (574 lines CSS)
- Lines 582-919: HTML `<body>` (338 lines markup)
- Lines 920-2585: `<script>` block (1666 lines JavaScript)
- Lines 2586-2587: Closing tags

## How Flask Serves the Dashboard

- `GET /` handled in `solo_builder/api/blueprints/core.py` line 20:
  ```python
  return send_from_directory(Path(__file__).resolve().parent.parent, "dashboard.html")
  ```
  This serves from `solo_builder/api/`.
- `Flask(__name__)` defaults `static_folder="static"` relative to `solo_builder/api/app.py`.
  Flask auto-serves `solo_builder/api/static/**` at `/static/**` with no extra routes needed.

## Test Coverage

- `GET /` is tested in `TestGetRoot` (2 tests): status 200 and `html` content-type only.
  Neither test inspects HTML content. Extracting JS/CSS to external files will not break them.
- No JavaScript unit tests exist. Functional regression can only be caught visually.
- Existing CI (`smoke-test.yml`) runs `python -m unittest discover` — no browser tests.

## Evidence-Backed Hypotheses

1. **Extracting CSS and JS to `solo_builder/api/static/` will preserve all 305 API tests.**
   Basis: tests only check HTTP status and content-type for `GET /`; no test inspects HTML body.

2. **Flask will serve the static files at `/static/dashboard.css` and `/static/dashboard.js`
   with zero additional routes**, because `Flask(__name__)` already configures the default
   static folder at `solo_builder/api/static/` and registers the `/static/<path>` route
   automatically.

3. **`dashboard.html` can be reduced from 2587 → ~350 lines** (HTML shell only), with:
   - `<link rel="stylesheet" href="/static/dashboard.css">` replacing the 574-line `<style>` block
   - `<script src="/static/dashboard.js" defer></script>` replacing the 1666-line `<script>` block

## Explicit Unknowns

1. **No browser-level verification**: Functional correctness of the extracted JS/CSS cannot
   be confirmed by the automated test suite. Manual visual inspection is required after the change.

2. **`defer` attribute safety**: The JS block must be inspected to confirm it does not rely on
   synchronous execution relative to inline HTML elements parsed after it; if it does, `defer`
   is safe (defers to DOMContentLoaded). Must verify no `document.write` calls exist.

3. **Favicon `data:` URI in `<link>` tag**: The dashboard sets the favicon via JS at runtime
   (`document.getElementById('favicon')`). The static `<link>` tag in `<head>` with
   `id="favicon"` must remain in the HTML shell for the JS to update it correctly.

## Scope Boundary

- In scope: `solo_builder/api/dashboard.html` (reduced to HTML shell)
- In scope: `solo_builder/api/static/dashboard.css` (NEW — extracted CSS)
- In scope: `solo_builder/api/static/dashboard.js` (NEW — extracted JS)
- In scope: `claude/allowed_files.txt` (add two new static files)
- Out of scope: All Python source files, Flask blueprints, CLI, bot, test suite
- Architecture auditor score should improve (2587-line file drops off the large-file list)
