"""Tests for tools/slo_check.py — TASK-335 (OM-036, OM-037)."""
import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import slo_check as sc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(tmp: str, records: list[dict]) -> Path:
    p = Path(tmp) / "metrics.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return p


def _patch_path(p: Path):
    return patch.object(sc, "METRICS_PATH", p)


# ---------------------------------------------------------------------------
# _load_records
# ---------------------------------------------------------------------------

class TestLoadRecords(unittest.TestCase):

    def test_loads_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_jsonl(tmp, [{"a": 1}, {"b": 2}])
            records = sc._load_records(p)
        self.assertEqual(len(records), 2)

    def test_skips_malformed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.jsonl"
            p.write_text('{"ok":1}\nnot-json\n{"ok":2}\n', encoding="utf-8")
            records = sc._load_records(p)
        self.assertEqual(len(records), 2)

    def test_missing_file_returns_empty(self):
        self.assertEqual(sc._load_records(Path("/no/such/file.jsonl")), [])


# ---------------------------------------------------------------------------
# _check_slo003
# ---------------------------------------------------------------------------

class TestCheckSlo003(unittest.TestCase):

    def test_ok_when_all_succeed(self):
        records = [{"sdk_dispatched": 10, "sdk_succeeded": 10}]
        r = sc._check_slo003(records)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["value"], 1.0)

    def test_breach_below_threshold(self):
        records = [{"sdk_dispatched": 100, "sdk_succeeded": 80}]
        r = sc._check_slo003(records)
        self.assertEqual(r["status"], "breach")
        self.assertAlmostEqual(r["value"], 0.8)

    def test_no_data_when_no_sdk_records(self):
        records = [{"sdk_dispatched": 0, "elapsed_s": 0.5}]
        r = sc._check_slo003(records)
        self.assertEqual(r["status"], "no_data")

    def test_aggregates_across_records(self):
        records = [
            {"sdk_dispatched": 5, "sdk_succeeded": 5},
            {"sdk_dispatched": 5, "sdk_succeeded": 4},
        ]
        r = sc._check_slo003(records)
        self.assertAlmostEqual(r["value"], 0.9)
        self.assertEqual(r["status"], "breach")  # 0.9 < 0.95 threshold

    def test_exactly_at_threshold_is_ok(self):
        records = [{"sdk_dispatched": 20, "sdk_succeeded": 19}]
        r = sc._check_slo003(records)
        self.assertEqual(r["status"], "ok")  # 19/20 = 0.95 exactly


# ---------------------------------------------------------------------------
# _check_slo005
# ---------------------------------------------------------------------------

class TestCheckSlo005(unittest.TestCase):

    def test_ok_below_target(self):
        records = [{"elapsed_s": float(i)} for i in range(1, 6)]  # 1..5, median=3
        r = sc._check_slo005(records)
        self.assertEqual(r["status"], "ok")
        self.assertLessEqual(r["value"], sc.LATENCY_TARGET_S)

    def test_breach_above_target(self):
        records = [{"elapsed_s": 15.0}] * 5
        r = sc._check_slo005(records)
        self.assertEqual(r["status"], "breach")

    def test_no_data_when_no_elapsed_field(self):
        records = [{"sdk_dispatched": 1}]
        r = sc._check_slo005(records)
        self.assertEqual(r["status"], "no_data")

    def test_exactly_at_target_is_ok(self):
        records = [{"elapsed_s": sc.LATENCY_TARGET_S}] * 3
        r = sc._check_slo005(records)
        self.assertEqual(r["status"], "ok")


# ---------------------------------------------------------------------------
# check() / main()
# ---------------------------------------------------------------------------

class TestCheck(unittest.TestCase):

    def _records(self, n=10):
        return [{"elapsed_s": 0.5, "sdk_dispatched": 1, "sdk_succeeded": 1}
                for _ in range(n)]

    def test_returns_0_when_all_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_jsonl(tmp, self._records(10))
            with _patch_path(p):
                code = sc.check(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_1_on_breach(self):
        records = [{"elapsed_s": 50.0, "sdk_dispatched": 0}] * 10
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_jsonl(tmp, records)
            with _patch_path(p):
                code = sc.check(quiet=True)
        self.assertEqual(code, 1)

    def test_skip_when_too_few_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_jsonl(tmp, self._records(2))
            with _patch_path(p):
                code = sc.check(min_records=5, quiet=True)
        self.assertEqual(code, 0)  # skip = no breach

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_jsonl(tmp, self._records(10))
            with _patch_path(p):
                buf = StringIO()
                with patch("sys.stdout", buf):
                    sc.check(as_json=True)
        data = json.loads(buf.getvalue())
        self.assertIn("results", data)
        self.assertIn("records", data)

    def test_main_dry_run_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_jsonl(tmp, self._records(10))
            with _patch_path(p):
                code = sc.main(["--quiet"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
