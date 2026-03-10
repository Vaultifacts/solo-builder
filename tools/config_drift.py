"""Config drift detector — TASK-348 (PW-010 to PW-015).

Compares the live settings.json against the canonical defaults defined in
solo_builder/api/constants.py (_CONFIG_DEFAULTS) and reports:
  - Keys that are missing from settings.json (using the default value)
  - Keys whose values differ from the defaults (intentional overrides)
  - Keys in settings.json that are not in the defaults (unknown/new keys)

Helps catch accidental config drift and surface undocumented overrides.

Exit codes:
  0 — no drift found (settings.json matches defaults exactly)
  1 — drift detected (overrides or unknown keys present)
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
SETTINGS_PATH = REPO_ROOT / "solo_builder" / "config" / "settings.json"


def _load_defaults() -> dict[str, Any]:
    """Import _CONFIG_DEFAULTS from constants.py without a running Flask app."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "constants",
        REPO_ROOT / "solo_builder" / "api" / "constants.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(getattr(mod, "_CONFIG_DEFAULTS", {}))


@dataclass
class DriftReport:
    missing_keys:   list[str] = field(default_factory=list)   # in defaults, not in settings
    overridden_keys: list[dict] = field(default_factory=list)  # present but differ from default
    unknown_keys:   list[str] = field(default_factory=list)   # in settings, not in defaults

    @property
    def has_drift(self) -> bool:
        return bool(self.overridden_keys or self.unknown_keys)

    def to_dict(self) -> dict:
        return {
            "has_drift":      self.has_drift,
            "missing_keys":   self.missing_keys,
            "overridden_keys": self.overridden_keys,
            "unknown_keys":   self.unknown_keys,
        }


def detect_drift(
    settings_path: Path | str | None = None,
    defaults: dict[str, Any] | None = None,
) -> DriftReport:
    """Compare settings.json against defaults; return a DriftReport."""
    if settings_path is None:
        settings_path = SETTINGS_PATH
    settings_path = Path(settings_path)

    if defaults is None:
        defaults = _load_defaults()

    live: dict[str, Any] = {}
    try:
        live = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    report = DriftReport()

    for key, default_val in defaults.items():
        if key not in live:
            report.missing_keys.append(key)
        elif live[key] != default_val:
            report.overridden_keys.append({
                "key":     key,
                "default": default_val,
                "live":    live[key],
            })

    for key in live:
        if key not in defaults:
            report.unknown_keys.append(key)

    return report


def run(
    quiet: bool = False,
    as_json: bool = False,
    settings_path: Path | str | None = None,
) -> int:
    """Detect drift and report; return 0 if none, 1 if drift found."""
    try:
        report = detect_drift(settings_path=settings_path)
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 0 if not report.has_drift else 1

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Config Drift Report")
            print()
            if report.missing_keys:
                print(f"  Missing keys (using default):  {len(report.missing_keys)}")
                for k in report.missing_keys:
                    print(f"    - {k}")
            if report.overridden_keys:
                print(f"  Overridden keys:               {len(report.overridden_keys)}")
                for entry in report.overridden_keys:
                    print(f"    - {entry['key']}: {entry['default']!r} → {entry['live']!r}")
            if report.unknown_keys:
                print(f"  Unknown keys (not in defaults): {len(report.unknown_keys)}")
                for k in report.unknown_keys:
                    print(f"    + {k}")
            print()
            if exit_code == 0:
                print("No drift — settings.json matches defaults.")
            else:
                print("Drift detected — see above.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect config drift in settings.json.")
    parser.add_argument("--json",     action="store_true", dest="as_json")
    parser.add_argument("--quiet",    action="store_true")
    parser.add_argument("--settings", default="", help="Override settings.json path")
    args = parser.parse_args(argv)
    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        settings_path=args.settings or None,
    )


if __name__ == "__main__":
    sys.exit(main())
