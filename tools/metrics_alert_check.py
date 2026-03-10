"""Metrics alert threshold checker — TASK-350 (OM-020 to OM-025).

Reads metrics.jsonl and evaluates configurable alert thresholds:
  - failure_rate   : fraction of SDK dispatches that failed  (0.0–1.0)
  - avg_latency_s  : mean elapsed_s across all rows
  - p99_latency_s  : 99th-percentile elapsed_s
  - stall_rate     : fraction of steps with elapsed_s == 0
  - min_rows       : minimum row count required (alert if fewer rows recorded)

Thresholds are read from settings.json (ALERT_* keys) and can be overridden
via CLI flags.  Any threshold set to None / not configured is skipped.

Defaults (matching SLO thresholds where applicable):
  ALERT_MAX_FAILURE_RATE    = 0.10   (SLO-003 proxy)
  ALERT_MAX_AVG_LATENCY_S   = 30.0
  ALERT_MAX_P99_LATENCY_S   = 60.0
  ALERT_MAX_STALL_RATE      = 0.50
  ALERT_MIN_ROWS            = 0      (disabled by default)

Exit codes:
  0 — all thresholds satisfied (or no data)
  1 — one or more thresholds exceeded
  2 — usage / file error
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT    = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "solo_builder" / "metrics.jsonl"
SETTINGS_PATH = REPO_ROOT / "solo_builder" / "config" / "settings.json"

_ALERT_DEFAULTS: dict[str, Any] = {
    "ALERT_MAX_FAILURE_RATE":  0.10,
    "ALERT_MAX_AVG_LATENCY_S": 30.0,
    "ALERT_MAX_P99_LATENCY_S": 60.0,
    "ALERT_MAX_STALL_RATE":    0.50,
    "ALERT_MIN_ROWS":          0,
}


# ---------------------------------------------------------------------------
# Thresholds config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AlertThresholds:
    max_failure_rate:  float | None = 0.10
    max_avg_latency_s: float | None = 30.0
    max_p99_latency_s: float | None = 60.0
    max_stall_rate:    float | None = 0.50
    min_rows:          int   | None = 0


def load_thresholds(settings_path: Path | None = None) -> AlertThresholds:
    """Load thresholds from settings.json, falling back to _ALERT_DEFAULTS."""
    if settings_path is None:
        settings_path = SETTINGS_PATH
    settings: dict = {}
    try:
        settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    def _get(key: str) -> Any:
        return settings.get(key, _ALERT_DEFAULTS.get(key))

    return AlertThresholds(
        max_failure_rate=_get("ALERT_MAX_FAILURE_RATE"),
        max_avg_latency_s=_get("ALERT_MAX_AVG_LATENCY_S"),
        max_p99_latency_s=_get("ALERT_MAX_P99_LATENCY_S"),
        max_stall_rate=_get("ALERT_MAX_STALL_RATE"),
        min_rows=_get("ALERT_MIN_ROWS"),
    )


# ---------------------------------------------------------------------------
# Metrics loading
# ---------------------------------------------------------------------------

def _load_metrics(metrics_path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        for line in metrics_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except (OSError, FileNotFoundError):
        pass
    return rows


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = int(len(sorted_values) * pct / 100)
    return sorted_values[min(idx, len(sorted_values) - 1)]


# ---------------------------------------------------------------------------
# Alert report
# ---------------------------------------------------------------------------

@dataclass
class AlertReport:
    alerts:  list[dict] = field(default_factory=list)
    metrics: dict       = field(default_factory=dict)

    @property
    def has_alerts(self) -> bool:
        return bool(self.alerts)

    def to_dict(self) -> dict:
        return {
            "has_alerts": self.has_alerts,
            "alerts":     self.alerts,
            "metrics":    self.metrics,
        }


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def check_alerts(
    metrics_path: Path | str | None = None,
    thresholds: AlertThresholds | None = None,
    settings_path: Path | str | None = None,
) -> AlertReport:
    if metrics_path is None:
        metrics_path = METRICS_PATH
    metrics_path = Path(metrics_path)

    if thresholds is None:
        thresholds = load_thresholds(
            settings_path=Path(settings_path) if settings_path else None
        )

    rows = _load_metrics(metrics_path)
    report = AlertReport()

    n = len(rows)
    report.metrics["row_count"] = n

    # min_rows check (before computing other metrics)
    if thresholds.min_rows and n < thresholds.min_rows:
        report.alerts.append({
            "name":      "min_rows",
            "threshold": thresholds.min_rows,
            "actual":    n,
            "message":   f"Only {n} metric rows; expected >= {thresholds.min_rows}.",
        })

    if n == 0:
        return report

    # Latency metrics
    latencies = sorted(
        r["elapsed_s"] for r in rows
        if isinstance(r.get("elapsed_s"), (int, float))
    )
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        p99_lat = _percentile(latencies, 99)
        stall_count = sum(1 for v in latencies if v == 0.0)
        stall_rate = stall_count / len(latencies)
        report.metrics.update({
            "avg_latency_s": round(avg_lat, 4),
            "p99_latency_s": round(p99_lat, 4),
            "stall_rate":    round(stall_rate, 4),
        })

        if thresholds.max_avg_latency_s is not None and avg_lat > thresholds.max_avg_latency_s:
            report.alerts.append({
                "name":      "avg_latency_s",
                "threshold": thresholds.max_avg_latency_s,
                "actual":    round(avg_lat, 4),
                "message":   f"avg_latency {avg_lat:.3f}s > threshold {thresholds.max_avg_latency_s}s",
            })
        if thresholds.max_p99_latency_s is not None and p99_lat > thresholds.max_p99_latency_s:
            report.alerts.append({
                "name":      "p99_latency_s",
                "threshold": thresholds.max_p99_latency_s,
                "actual":    round(p99_lat, 4),
                "message":   f"p99_latency {p99_lat:.3f}s > threshold {thresholds.max_p99_latency_s}s",
            })
        if thresholds.max_stall_rate is not None and stall_rate > thresholds.max_stall_rate:
            report.alerts.append({
                "name":      "stall_rate",
                "threshold": thresholds.max_stall_rate,
                "actual":    round(stall_rate, 4),
                "message":   f"stall_rate {stall_rate:.3f} > threshold {thresholds.max_stall_rate}",
            })

    # Failure rate (sdk_dispatched / sdk_succeeded)
    dispatched_total = sum(
        r.get("sdk_dispatched", 0) or 0 for r in rows
        if isinstance(r.get("sdk_dispatched"), int)
    )
    succeeded_total = sum(
        r.get("sdk_succeeded", 0) or 0 for r in rows
        if isinstance(r.get("sdk_succeeded"), int)
    )
    if dispatched_total > 0:
        failure_rate = 1.0 - (succeeded_total / dispatched_total)
        report.metrics["failure_rate"] = round(failure_rate, 4)
        if (thresholds.max_failure_rate is not None
                and failure_rate > thresholds.max_failure_rate):
            report.alerts.append({
                "name":      "failure_rate",
                "threshold": thresholds.max_failure_rate,
                "actual":    round(failure_rate, 4),
                "message":   (
                    f"failure_rate {failure_rate:.3f} > threshold "
                    f"{thresholds.max_failure_rate}"
                ),
            })

    return report


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    metrics_path: Path | str | None = None,
    thresholds: AlertThresholds | None = None,
    settings_path: Path | str | None = None,
) -> int:
    try:
        report = check_alerts(
            metrics_path=metrics_path,
            thresholds=thresholds,
            settings_path=settings_path,
        )
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 1 if report.has_alerts else 0

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Metrics Alert Check")
            print()
            m = report.metrics
            if m:
                print(f"  Rows analysed : {m.get('row_count', 0)}")
                if "avg_latency_s" in m:
                    print(f"  Avg latency   : {m['avg_latency_s']}s")
                if "p99_latency_s" in m:
                    print(f"  P99 latency   : {m['p99_latency_s']}s")
                if "stall_rate" in m:
                    print(f"  Stall rate    : {m['stall_rate']}")
                if "failure_rate" in m:
                    print(f"  Failure rate  : {m['failure_rate']}")
            if report.alerts:
                print(f"\n  Alerts ({len(report.alerts)}):")
                for a in report.alerts:
                    print(f"    [ALERT] {a['message']}")
            print()
            if exit_code == 0:
                print("All thresholds satisfied.")
            else:
                print("Alert(s) triggered — see above.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check metrics.jsonl against alert thresholds."
    )
    parser.add_argument("--json",     action="store_true", dest="as_json")
    parser.add_argument("--quiet",    action="store_true")
    parser.add_argument("--metrics",  default="", help="Override metrics.jsonl path")
    parser.add_argument("--settings", default="", help="Override settings.json path")
    parser.add_argument(
        "--max-failure-rate", type=float, default=None,
        help="Override max failure rate threshold (0.0–1.0)"
    )
    parser.add_argument(
        "--max-avg-latency",  type=float, default=None,
        help="Override max average latency (seconds)"
    )
    parser.add_argument(
        "--max-p99-latency",  type=float, default=None,
        help="Override max p99 latency (seconds)"
    )
    args = parser.parse_args(argv)

    thresholds = None
    if any(v is not None for v in (
        args.max_failure_rate, args.max_avg_latency, args.max_p99_latency
    )):
        base = load_thresholds(
            settings_path=args.settings or None
        )
        thresholds = AlertThresholds(
            max_failure_rate=args.max_failure_rate
                if args.max_failure_rate is not None else base.max_failure_rate,
            max_avg_latency_s=args.max_avg_latency
                if args.max_avg_latency is not None else base.max_avg_latency_s,
            max_p99_latency_s=args.max_p99_latency
                if args.max_p99_latency is not None else base.max_p99_latency_s,
            max_stall_rate=base.max_stall_rate,
            min_rows=base.min_rows,
        )

    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        metrics_path=args.metrics or None,
        thresholds=thresholds,
        settings_path=args.settings or None,
    )


if __name__ == "__main__":
    sys.exit(main())
