# HANDOFF TO DEV (from ARCHITECT)

## Task
TASK-105

## Goal
Extract inline CSS and JavaScript from `solo_builder/api/dashboard.html` (2587 lines)
into separate static files, leaving an HTML shell of ~350 lines.

---

## Critical Constraint

All 305 API tests (`python -m unittest discover`) must pass before and after the change.
No test inspects the HTML body, so this is a low-risk refactor.

---

## Implementation Plan

Single step — can be done in one commit. Extract CSS and JS without changing any logic.

### Step 1 — Extract static assets and update dashboard.html

**Create `solo_builder/api/static/dashboard.css`:**
- Content: lines 9–580 of `dashboard.html` (the CSS inside `<style>…</style>`, excluding the tags themselves)

**Create `solo_builder/api/static/dashboard.js`:**
- Content: lines 921–2584 of `dashboard.html` (the JS inside `<script>…</script>`, excluding the tags)

**Update `solo_builder/api/dashboard.html`:**
- Remove lines 8–581 (`<style>` block); replace with:
  `<link rel="stylesheet" href="/static/dashboard.css">`
- Remove lines 920–2585 (`<script>` block); replace with:
  `<script src="/static/dashboard.js" defer></script>`
- Result: ~350-line HTML shell

**Update `claude/allowed_files.txt`:**
- Add `solo_builder/api/static/dashboard.css`
- Add `solo_builder/api/static/dashboard.js`

Flask serves `solo_builder/api/static/` at `/static/` automatically (default `static_folder`
for `Flask(__name__)` where `__name__ = solo_builder.api.app`). No Python changes required.

---

## Allowed Changes

```
solo_builder/api/dashboard.html
solo_builder/api/static/dashboard.css   (NEW)
solo_builder/api/static/dashboard.js    (NEW)
claude/allowed_files.txt
```

---

## Acceptance Criteria

1. `python -m unittest discover` — all 305 tests pass
2. `wc -l solo_builder/api/dashboard.html` — fewer than 400 lines
3. `solo_builder/api/static/dashboard.css` exists and contains valid CSS (starts with `:root {`)
4. `solo_builder/api/static/dashboard.js` exists and contains valid JS (starts with `(function`)
5. `GET /` still returns 200 with content-type `text/html`
6. `GET /static/dashboard.css` returns 200 with content-type `text/css`
7. `GET /static/dashboard.js` returns 200 with content-type `application/javascript`
8. Both new files listed in `claude/allowed_files.txt`
9. No logic changes — CSS/JS content is identical to what was inline

---

## Constraints

- Do NOT modify any Python files, test files, or blueprint files
- Do NOT change any CSS/JS logic — extract only, character-for-character
- Commit with `CLAUDE_ALLOW_NEW_FILES=1` env var to pass the new-file guard
- After commit, run tests to confirm all 305 pass
