# HANDOFF TO ARCHITECT (from RESEARCH)

## Context
- Active task: `TASK-021`
- Goal: Fix `test_stalled_shows_stuck` so optional unittest verification is clean.
- Scope: test file only unless implementation change is required.

## 1) Failing assertion

```
FAIL: test_stalled_shows_stuck (solo_builder.discord_bot.test_bot.TestStalledCommand)
AssertionError: 'A1' not found in '✅ **Stalled Subtasks** — none (threshold: 99 steps)'
```

Test (`test_bot.py:2051–2058`):
```python
state = _make_state({"A1": "Running", "A2": "Verified"}, step=10)
# patches: _send, _load_state
await bot_module._handle_text_command(_make_msg("stalled"))
text = mock_send.call_args[0][1]
self.assertIn("A1", text)      # fails
self.assertIn("Stalled", text) # would also fail
```

`_make_dag` sets `last_update=0` on all subtasks (`test_bot.py:60`).
So age = step(10) - last_update(0) = 10.

For A1 to appear stalled: `age >= threshold` → `10 >= threshold` → threshold must be ≤ 10.

## 2) Root cause

`_format_stalled` in `bot.py:313–340` reads threshold from the real `config/settings.json`:

```python
cfg = json.loads((_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
threshold = int(cfg.get("STALL_THRESHOLD", 5))
```

Live `solo_builder/config/settings.json` has `STALL_THRESHOLD: 99` — persisted from a
previous interactive session (`set STALL_THRESHOLD=99`). The test does NOT mock this read.

Result: threshold=99, age=10, `10 < 99` → not stalled → "none".

The production behavior (reading threshold from config) is correct. The test is missing
isolation for the config read.

## 3) Why this is a test isolation failure, not an implementation bug

- `_format_stalled` correctly reads live config so the Discord bot reflects real thresholds.
- The test was written assuming threshold=5 (the code-default fallback) would apply.
- A live `set STALL_THRESHOLD=99` command broke the assumption silently.
- The test already mocks `_load_state` and `_send` — the config read is the missing mock.

## 4) Fix candidates

**Candidate A — Mock the config read in the test (preferred):**
Add a `pathlib.Path.read_text` patch returning a controlled settings JSON within the test
context. `threshold=5` (or any value ≤ 10) applied → age=10 ≥ 5 → A1 stalled → PASS.
- Follows the test's existing mock pattern.
- Fully isolates from live config state.
- Zero production code change.
- Narrow scope: only `test_stalled_shows_stuck` needs the new patch.
  (`test_stalled_empty` uses step=1, age=1, and asserts "none" — it would PASS even with
  threshold=5 since 1 < 5, so it doesn't need the same mock.)

**Candidate B — Increase step to exceed any plausible threshold:**
Change `_make_state({"A1": "Running", "A2": "Verified"}, step=10)` to `step=200`.
age=200 ≥ 99 → PASS.
- Fragile: another `set STALL_THRESHOLD=300` session would break it again.
- Does not fix the underlying isolation problem.
- Not recommended.

**Candidate C — Parameterize threshold in `_format_stalled`:**
Add an optional `threshold` parameter to `_format_stalled` for testability. Pass a
controlled value from tests.
- Changes production function signature.
- Broader scope than needed.
- Not necessary given Candidate A is sufficient.

## 5) Scope

Fix belongs entirely in the TEST (`discord_bot/test_bot.py`).
No production code change is required or recommended.

The second stalled test (`test_stalled_empty`, step=1) passes today and will continue to
pass with any of the candidates above — no change needed there.

## 6) Verification
After fix: `python -m unittest solo_builder.discord_bot.test_bot.TestStalledCommand`
should show `2 tests, 0 failures`.
Full suite: `python -m unittest discover` with 0 failures.
