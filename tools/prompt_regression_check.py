"""Prompt regression checker — TASK-354 (AI-002 to AI-005).

Validates all registered PromptTemplate entries in utils/prompt_builder.py
against a quality regression checklist.  Catches template regressions early
before they reach the Claude API.

Checks performed per template:
  1. Has at least one required variable
  2. All declared required_vars appear in the template string as {var}
  3. All declared optional_vars appear in the template string as {var}
  4. Template renders without error using dummy values
  5. No empty {} placeholders in the template
  6. Template length is within bounds (MIN_PROMPT_CHARS to MAX_PROMPT_CHARS)
  7. No secret-like patterns (sk-, api_key=, password=) in the template text

Configurable via settings.json:
  PROMPT_MIN_CHARS  (default 20)
  PROMPT_MAX_CHARS  (default 4000)

Exit codes:
  0 — all templates pass
  1 — one or more templates fail a check
  2 — usage / import error
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT     = Path(__file__).resolve().parent.parent
SETTINGS_PATH = REPO_ROOT / "solo_builder" / "config" / "settings.json"

_SECRET_RE = re.compile(r"(?i)(sk-[A-Za-z0-9]{5,}|api_key\s*=|password\s*=)")

_DEFAULTS: dict[str, Any] = {
    "PROMPT_MIN_CHARS": 20,
    "PROMPT_MAX_CHARS": 4000,
}


# ---------------------------------------------------------------------------
# Load prompt_builder without Flask context
# ---------------------------------------------------------------------------

def _load_registry(prompt_builder_path: Path | None = None) -> dict:
    """Import prompt_builder.py and return its REGISTRY dict."""
    if prompt_builder_path is None:
        prompt_builder_path = REPO_ROOT / "solo_builder" / "utils" / "prompt_builder.py"
    spec = importlib.util.spec_from_file_location("prompt_builder", prompt_builder_path)
    mod = importlib.util.module_from_spec(spec)
    # Register so dataclasses resolve __module__ correctly
    sys.modules.setdefault("prompt_builder", mod)
    spec.loader.exec_module(mod)
    return dict(getattr(mod, "REGISTRY", {}))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_settings(settings_path: Path | None = None) -> dict:
    if settings_path is None:
        settings_path = SETTINGS_PATH
    try:
        return json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# Per-template result
# ---------------------------------------------------------------------------

@dataclass
class TemplateResult:
    name:   str
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


@dataclass
class RegressionReport:
    results:  list[TemplateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def to_dict(self) -> dict:
        return {
            "passed":       self.passed,
            "total":        len(self.results),
            "failed":       self.failed_count,
            "results": [
                {"name": r.name, "passed": r.passed, "errors": r.errors}
                for r in self.results
            ],
        }


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------

def _check_template(template: Any, min_chars: int, max_chars: int) -> list[str]:
    """Run all regression checks on a single PromptTemplate; return list of errors."""
    errors: list[str] = []
    name = getattr(template, "name", "?")
    tmpl_str = getattr(template, "template", "")
    required_vars: list[str] = getattr(template, "required_vars", [])
    optional_vars: list[str] = getattr(template, "optional_vars", [])

    # 1. At least one required variable
    if not required_vars:
        errors.append(f"[{name}] has no required_vars — consider adding at least one.")

    # 2. All required_vars appear in template string
    for var in required_vars:
        if f"{{{var}}}" not in tmpl_str:
            errors.append(f"[{name}] required_var '{var}' not found as '{{{var}}}' in template.")

    # 3. All optional_vars appear in template string
    for var in optional_vars:
        if f"{{{var}}}" not in tmpl_str:
            errors.append(f"[{name}] optional_var '{var}' not found as '{{{var}}}' in template.")

    # 4. Template renders without error using dummy values
    render_fn = getattr(template, "render", None)
    if render_fn is not None:
        try:
            dummy = {v: "test_value" for v in required_vars + optional_vars}
            render_fn(**dummy)
        except Exception as exc:
            errors.append(f"[{name}] render() failed with dummy values: {exc}")

    # 5. No empty {} placeholders (already enforced by __post_init__, but verify here too)
    if re.search(r"\{\s*\}", tmpl_str):
        errors.append(f"[{name}] contains empty '{{}}' placeholder.")

    # 6. Length within bounds
    length = len(tmpl_str)
    if length < min_chars:
        errors.append(
            f"[{name}] template is too short ({length} chars < min {min_chars})."
        )
    if length > max_chars:
        errors.append(
            f"[{name}] template is too long ({length} chars > max {max_chars})."
        )

    # 7. No secret-like patterns
    if _SECRET_RE.search(tmpl_str):
        errors.append(f"[{name}] template contains secret-like pattern (api key / password).")

    return errors


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def run_checks(
    registry: dict | None = None,
    settings_path: Path | str | None = None,
    prompt_builder_path: Path | str | None = None,
) -> RegressionReport:
    if registry is None:
        registry = _load_registry(
            prompt_builder_path=Path(prompt_builder_path) if prompt_builder_path else None
        )

    settings = _load_settings(
        settings_path=Path(settings_path) if settings_path else None
    )
    min_chars = int(settings.get("PROMPT_MIN_CHARS", _DEFAULTS["PROMPT_MIN_CHARS"]))
    max_chars = int(settings.get("PROMPT_MAX_CHARS", _DEFAULTS["PROMPT_MAX_CHARS"]))

    report = RegressionReport()
    for name, template in registry.items():
        errs = _check_template(template, min_chars, max_chars)
        report.results.append(TemplateResult(name=name, errors=errs))

    return report


# ---------------------------------------------------------------------------
# run() / main()
# ---------------------------------------------------------------------------

def run(
    quiet: bool = False,
    as_json: bool = False,
    settings_path: Path | str | None = None,
    prompt_builder_path: Path | str | None = None,
) -> int:
    try:
        report = run_checks(
            settings_path=settings_path,
            prompt_builder_path=prompt_builder_path,
        )
    except Exception as exc:
        if not quiet:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    exit_code = 0 if report.passed else 1

    if not quiet:
        if as_json:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Prompt Regression Check")
            print()
            print(f"  Templates checked: {len(report.results)}")
            print(f"  Passed:            {len(report.results) - report.failed_count}")
            print(f"  Failed:            {report.failed_count}")
            for r in report.results:
                if not r.passed:
                    print(f"\n  [FAIL] {r.name}:")
                    for e in r.errors:
                        print(f"    - {e}")
            print()
            if exit_code == 0:
                print("All prompt templates pass regression checks.")
            else:
                print("Prompt regression failed — see above.")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate PromptTemplate registry against regression checklist."
    )
    parser.add_argument("--json",    action="store_true", dest="as_json")
    parser.add_argument("--quiet",   action="store_true")
    parser.add_argument("--settings", default="", help="Override settings.json path")
    parser.add_argument(
        "--prompt-builder", default="",
        help="Override utils/prompt_builder.py path"
    )
    args = parser.parse_args(argv)
    return run(
        quiet=args.quiet,
        as_json=args.as_json,
        settings_path=args.settings or None,
        prompt_builder_path=args.prompt_builder or None,
    )


if __name__ == "__main__":
    sys.exit(main())
