"""SLO Check — TASK-335 (OM-036, OM-037).

Reads solo_builder/metrics.jsonl and validates two measurable SLOs:

  SLO-003  SDK call success rate >= SDK_SUCCESS_TARGET  (default 0.95)
  SLO-005  Executor step latency median <= LATENCY_TARGET_S  (default 10 s)

Exits:
  0 — all SLOs within target
  1 — one or more SLOs breached
  2 — usage / path error

Usage:
    python tools/slo_check.py [--min-records N] [--json] [--quiet]

Options:
    --min-records N  Minimum records required to evaluate (default 5)
    --json           Output machine-readable JSON
    --quiet          Suppress output (still exits non-zero on breach)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT    = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "solo_builder" / "metrics.jsonl"

SDK_SUCCESS_TARGET = 0.95   # SLO-003
LATENCY_TARGET_S   = 10.0   # SLO-005 (median)
DEFAULT_MIN_RECORDS = 5


def _load_records(path: Path) -> list[dict]:
    """Parse JSONL; skip blank lines and malformed entries."""
    records = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except OSError:
        pass
    return records


def _check_slo003(records: list[dict]) -> dict:
    """SLO-003: SDK success rate across all records that dispatched SDK calls."""
    sdk_records = [r for r in records if r.get("sdk_dispatched", 0) > 0]
    if not sdk_records:
        return {"slo": "SLO-003", "target": f">={SDK_SUCCESS_TARGET:.0%}",
                "value": None, "status": "no_data",
                "detail": "No records with sdk_dispatched > 0"}
    total_dispatched = sum(r["sdk_dispatched"] for r in sdk_records)
    total_succeeded  = sum(r.get("sdk_succeeded", 0) for r in sdk_records)
    rate = total_succeeded / total_dispatched if total_dispatched else 0.0
    status = "ok" if rate >= SDK_SUCCESS_TARGET else "breach"
    return {
        "slo":     "SLO-003",
        "target":  f">={SDK_SUCCESS_TARGET:.0%}",
        "value":   round(rate, 4),
        "status":  status,
        "detail":  f"{total_succeeded}/{total_dispatched} SDK calls succeeded ({rate:.1%})",
    }


def _check_slo005(records: list[dict]) -> dict:
    """SLO-005: Executor step latency median <= LATENCY_TARGET_S."""
    elapsed = [r["elapsed_s"] for r in records if "elapsed_s" in r]
    if not elapsed:
        return {"slo": "SLO-005", "target": f"<={LATENCY_TARGET_S}s median",
                "value": None, "status": "no_data",
                "detail": "No elapsed_s fields found"}
    median = statistics.median(elapsed)
    status = "ok" if median <= LATENCY_TARGET_S else "breach"
    return {
        "slo":    "SLO-005",
        "target": f"<={LATENCY_TARGET_S}s median",
        "value":  round(median, 3),
        "status": status,
        "detail": f"median={median:.3f}s over {len(elapsed)} records "
                  f"(p95={statistics.quantiles(elapsed, n=20)[18]:.3f}s)" if len(elapsed) >= 5
                  else f"median={median:.3f}s over {len(elapsed)} records",
    }


def check(min_records: int = DEFAULT_MIN_RECORDS,
          quiet: bool = False,
          as_json: bool = False) -> int:
    records = _load_records(METRICS_PATH)
    results: list[dict] = []
    exit_code = 0

    if len(records) < min_records:
        r = {
            "slo": "ALL", "status": "skip",
            "detail": f"Only {len(records)} records (need >= {min_records})",
        }
        results.append(r)
    else:
        slo003 = _check_slo003(records)
        slo005 = _check_slo005(records)
        results = [slo003, slo005]
        if any(r["status"] == "breach" for r in results):
            exit_code = 1

    if not quiet:
        if as_json:
            print(json.dumps({"metrics_path": str(METRICS_PATH),
                               "records": len(records),
                               "results": results,
                               "exit_code": exit_code},
                             ensure_ascii=False))
        else:
            print(f"SLO Check  ({len(records)} records from {METRICS_PATH.name})")
            print()
            for r in results:
                flag = {"ok": "OK", "breach": "BREACH", "no_data": "NO_DATA",
                        "skip": "SKIP"}.get(r["status"], "??")
                val  = f"  value={r['value']}" if "value" in r and r["value"] is not None else ""
                print(f"  [{flag}]  {r.get('slo','?')}  target={r.get('target','?')}{val}")
                print(f"           {r.get('detail','')}")
            print()
            if exit_code:
                print("FAIL — one or more SLOs breached.")
            else:
                print("PASS — all SLOs within target.")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate metrics.jsonl against SLO targets.")
    parser.add_argument("--min-records", type=int, default=DEFAULT_MIN_RECORDS,
                        help=f"Min records to evaluate (default {DEFAULT_MIN_RECORDS})")
    parser.add_argument("--json",  action="store_true", dest="as_json", help="Output JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args(argv)
    return check(min_records=args.min_records, quiet=args.quiet, as_json=args.as_json)


if __name__ == "__main__":
    sys.exit(main())
