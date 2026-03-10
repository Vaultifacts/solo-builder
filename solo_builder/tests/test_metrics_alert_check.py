"""Tests for tools/metrics_alert_check.py (TASK-350, OM-020 to OM-025)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys as _sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Load module
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "metrics_alert_check", _TOOLS_DIR / "metrics_alert_check.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["metrics_alert_check"] = _mod
_spec.loader.exec_module(_mod)

check_alerts    = _mod.check_alerts
AlertReport     = _mod.AlertReport
AlertThresholds = _mod.AlertThresholds
load_thresholds = _mod.load_thresholds
run             = _mod.run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_metrics(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "metrics.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


_ROW_OK = {
    "ts": "2026-01-01T00:00:00Z",
    "step": 1,
    "elapsed_s": 1.0,
    "sdk_dispatched": 1,
    "sdk_succeeded": 1,
    "sdk_success_rate": 1.0,
    "started": 1,
    "verified": 1,
}

_ROW_SLOW = {**_ROW_OK, "elapsed_s": 120.0}
_ROW_FAILED = {**_ROW_OK, "sdk_dispatched": 1, "sdk_succeeded": 0, "sdk_success_rate": 0.0}
_ROW_STALL = {**_ROW_OK, "elapsed_s": 0.0}


# ---------------------------------------------------------------------------
# AlertThresholds
# ---------------------------------------------------------------------------

class TestAlertThresholds(unittest.TestCase):

    def test_defaults_are_set(self):
        t = AlertThresholds()
        self.assertIsNotNone(t.max_failure_rate)
        self.assertIsNotNone(t.max_avg_latency_s)
        self.assertIsNotNone(t.max_p99_latency_s)
        self.assertIsNotNone(t.max_stall_rate)

    def test_thresholds_are_immutable(self):
        t = AlertThresholds()
        with self.assertRaises((AttributeError, TypeError)):
            t.max_failure_rate = 0.99  # type: ignore[misc]

    def test_none_thresholds_skip_check(self):
        t = AlertThresholds(
            max_failure_rate=None,
            max_avg_latency_s=None,
            max_p99_latency_s=None,
            max_stall_rate=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_FAILED, _ROW_SLOW])
            report = check_alerts(metrics_path=p, thresholds=t)
        self.assertFalse(report.has_alerts)


# ---------------------------------------------------------------------------
# AlertReport
# ---------------------------------------------------------------------------

class TestAlertReport(unittest.TestCase):

    def test_empty_no_alerts(self):
        r = AlertReport()
        self.assertFalse(r.has_alerts)

    def test_with_alert(self):
        r = AlertReport(alerts=[{"name": "failure_rate", "threshold": 0.1, "actual": 0.5, "message": "x"}])
        self.assertTrue(r.has_alerts)

    def test_to_dict_structure(self):
        r = AlertReport()
        d = r.to_dict()
        for k in ("has_alerts", "alerts", "metrics"):
            self.assertIn(k, d)


# ---------------------------------------------------------------------------
# load_thresholds
# ---------------------------------------------------------------------------

class TestLoadThresholds(unittest.TestCase):

    def test_missing_settings_uses_defaults(self):
        t = load_thresholds(settings_path=Path("/nonexistent/settings.json"))
        self.assertAlmostEqual(t.max_failure_rate, 0.10)

    def test_settings_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"ALERT_MAX_FAILURE_RATE": 0.05}), encoding="utf-8")
            t = load_thresholds(settings_path=p)
        self.assertAlmostEqual(t.max_failure_rate, 0.05)

    def test_partial_override_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            p.write_text(json.dumps({"ALERT_MAX_FAILURE_RATE": 0.20}), encoding="utf-8")
            t = load_thresholds(settings_path=p)
        self.assertAlmostEqual(t.max_avg_latency_s, 30.0)


# ---------------------------------------------------------------------------
# check_alerts — no data
# ---------------------------------------------------------------------------

class TestCheckAlertsNoData(unittest.TestCase):

    def test_empty_file_no_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "metrics.jsonl"
            p.write_text("", encoding="utf-8")
            report = check_alerts(metrics_path=p)
        self.assertFalse(report.has_alerts)
        self.assertEqual(report.metrics["row_count"], 0)

    def test_missing_file_no_alerts(self):
        report = check_alerts(
            metrics_path="/nonexistent/metrics.jsonl",
            thresholds=AlertThresholds(),
        )
        self.assertFalse(report.has_alerts)

    def test_row_count_in_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK, _ROW_OK])
            report = check_alerts(metrics_path=p, thresholds=AlertThresholds())
        self.assertEqual(report.metrics["row_count"], 2)


# ---------------------------------------------------------------------------
# check_alerts — latency
# ---------------------------------------------------------------------------

class TestCheckAlertsLatency(unittest.TestCase):

    def test_avg_latency_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK] * 5)
            t = AlertThresholds(max_avg_latency_s=10.0)
            report = check_alerts(metrics_path=p, thresholds=t)
        self.assertFalse(report.has_alerts)

    def test_avg_latency_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [_ROW_SLOW] * 5
            p = _write_metrics(Path(tmp), rows)
            t = AlertThresholds(max_avg_latency_s=30.0)
            report = check_alerts(metrics_path=p, thresholds=t)
        self.assertTrue(report.has_alerts)
        self.assertTrue(any(a["name"] == "avg_latency_s" for a in report.alerts))

    def test_p99_latency_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 99 normal + 1 very slow
            rows = [_ROW_OK] * 99 + [{**_ROW_OK, "elapsed_s": 200.0}]
            p = _write_metrics(Path(tmp), rows)
            t = AlertThresholds(max_p99_latency_s=60.0)
            report = check_alerts(metrics_path=p, thresholds=t)
        self.assertTrue(any(a["name"] == "p99_latency_s" for a in report.alerts))

    def test_avg_latency_in_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK])
            report = check_alerts(
                metrics_path=p,
                thresholds=AlertThresholds(max_avg_latency_s=None),
            )
        self.assertIn("avg_latency_s", report.metrics)


# ---------------------------------------------------------------------------
# check_alerts — stall rate
# ---------------------------------------------------------------------------

class TestCheckAlertsStallRate(unittest.TestCase):

    def test_no_stalls_no_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK] * 10)
            t = AlertThresholds(max_stall_rate=0.5)
            report = check_alerts(metrics_path=p, thresholds=t)
        names = [a["name"] for a in report.alerts]
        self.assertNotIn("stall_rate", names)

    def test_high_stall_rate_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [_ROW_STALL] * 8 + [_ROW_OK] * 2
            p = _write_metrics(Path(tmp), rows)
            t = AlertThresholds(max_stall_rate=0.5)
            report = check_alerts(metrics_path=p, thresholds=t)
        self.assertTrue(any(a["name"] == "stall_rate" for a in report.alerts))


# ---------------------------------------------------------------------------
# check_alerts — failure rate
# ---------------------------------------------------------------------------

class TestCheckAlertsFailureRate(unittest.TestCase):

    def test_zero_dispatched_no_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [{**_ROW_OK, "sdk_dispatched": 0, "sdk_succeeded": 0}]
            p = _write_metrics(Path(tmp), rows)
            t = AlertThresholds(max_failure_rate=0.10)
            report = check_alerts(metrics_path=p, thresholds=t)
        names = [a["name"] for a in report.alerts]
        self.assertNotIn("failure_rate", names)

    def test_high_failure_rate_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 5 dispatched, 0 succeeded → 100% failure
            rows = [{**_ROW_FAILED}] * 5
            p = _write_metrics(Path(tmp), rows)
            t = AlertThresholds(max_failure_rate=0.10)
            report = check_alerts(metrics_path=p, thresholds=t)
        self.assertTrue(any(a["name"] == "failure_rate" for a in report.alerts))

    def test_low_failure_rate_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [_ROW_OK] * 10  # 0 failures
            p = _write_metrics(Path(tmp), rows)
            t = AlertThresholds(max_failure_rate=0.10)
            report = check_alerts(metrics_path=p, thresholds=t)
        names = [a["name"] for a in report.alerts]
        self.assertNotIn("failure_rate", names)

    def test_failure_rate_in_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK])
            report = check_alerts(
                metrics_path=p,
                thresholds=AlertThresholds(max_failure_rate=None),
            )
        self.assertIn("failure_rate", report.metrics)


# ---------------------------------------------------------------------------
# check_alerts — min_rows
# ---------------------------------------------------------------------------

class TestCheckAlertsMinRows(unittest.TestCase):

    def test_min_rows_not_met(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK])
            t = AlertThresholds(min_rows=10)
            report = check_alerts(metrics_path=p, thresholds=t)
        self.assertTrue(any(a["name"] == "min_rows" for a in report.alerts))

    def test_min_rows_met(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK] * 10)
            t = AlertThresholds(min_rows=5)
            report = check_alerts(metrics_path=p, thresholds=t)
        names = [a["name"] for a in report.alerts]
        self.assertNotIn("min_rows", names)

    def test_min_rows_zero_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [])
            t = AlertThresholds(min_rows=0)
            report = check_alerts(metrics_path=p, thresholds=t)
        names = [a["name"] for a in report.alerts]
        self.assertNotIn("min_rows", names)


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_when_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK] * 3)
            t = AlertThresholds(max_failure_rate=0.5, max_avg_latency_s=100.0)
            code = run(quiet=True, metrics_path=p, thresholds=t)
        self.assertEqual(code, 0)

    def test_returns_1_on_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_FAILED] * 5)
            t = AlertThresholds(max_failure_rate=0.10)
            code = run(quiet=True, metrics_path=p, thresholds=t)
        self.assertEqual(code, 1)

    def test_json_output_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK])
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=True, metrics_path=p)
                data = json.loads(mock_out.getvalue())
        for k in ("has_alerts", "alerts", "metrics"):
            self.assertIn(k, data)

    def test_quiet_suppresses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK])
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True, metrics_path=p)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_text_output_mentions_thresholds_satisfied(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK] * 2)
            t = AlertThresholds(max_failure_rate=0.5)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=False, metrics_path=p, thresholds=t)
                output = mock_out.getvalue()
        self.assertIn("satisfied", output.lower())

    def test_text_output_shows_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_FAILED] * 5)
            t = AlertThresholds(max_failure_rate=0.10)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=False, as_json=False, metrics_path=p, thresholds=t)
                output = mock_out.getvalue()
        self.assertIn("ALERT", output)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_ok_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK] * 3)
            rc = _mod.main(["--quiet", "--metrics", str(p),
                            "--max-failure-rate", "0.5"])
        self.assertEqual(rc, 0)

    def test_main_alert_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_FAILED] * 5)
            rc = _mod.main(["--quiet", "--metrics", str(p),
                            "--max-failure-rate", "0.05"])
        self.assertEqual(rc, 1)

    def test_main_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_OK])
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                _mod.main(["--json", "--quiet", "--metrics", str(p)])
        # No error means success — we just need it not to crash
        self.assertTrue(True)

    def test_main_override_avg_latency(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write_metrics(Path(tmp), [_ROW_SLOW] * 5)
            # very low threshold → should alert
            rc = _mod.main(["--quiet", "--metrics", str(p),
                            "--max-avg-latency", "1.0"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
