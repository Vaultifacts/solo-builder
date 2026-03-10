"""Tests for tools/prompt_regression_check.py (TASK-354, AI-002 to AI-005)."""
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
    "prompt_regression_check", _TOOLS_DIR / "prompt_regression_check.py"
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["prompt_regression_check"] = _mod
_spec.loader.exec_module(_mod)

run_checks       = _mod.run_checks
_check_template  = _mod._check_template
RegressionReport = _mod.RegressionReport
TemplateResult   = _mod.TemplateResult
run              = _mod.run


# ---------------------------------------------------------------------------
# Minimal PromptTemplate stub
# ---------------------------------------------------------------------------

class _FakeTemplate:
    def __init__(self, name, template, required_vars=None, optional_vars=None):
        self.name          = name
        self.template      = template
        self.required_vars = required_vars or []
        self.optional_vars = optional_vars or []

    def render(self, **kwargs):
        values = {v: kwargs.get(v, "") for v in self.required_vars + self.optional_vars}
        return self.template.format_map(values)


def _make_registry(**templates):
    return {t.name: t for t in templates.values()}


_GOOD_TEMPLATE = _FakeTemplate(
    "good",
    "Do {task} in context {context}.",
    required_vars=["task", "context"],
)

_OPTIONAL_TEMPLATE = _FakeTemplate(
    "with_optional",
    "Do {task} with notes {notes}.",
    required_vars=["task"],
    optional_vars=["notes"],
)

_NO_REQUIRED_TEMPLATE = _FakeTemplate(
    "no_required",
    "This template has no variables.",
    required_vars=[],
)

_MISSING_VAR_TEMPLATE = _FakeTemplate(
    "missing_var",
    "Do {task} only.",
    required_vars=["task", "missing"],  # 'missing' not in template
)

_SHORT_TEMPLATE = _FakeTemplate(
    "short",
    "Hi",  # too short
    required_vars=["x"] if False else [],  # no required vars + too short
)

_SECRET_TEMPLATE = _FakeTemplate(
    "secret",
    "Use api_key= value to call {service}.",
    required_vars=["service"],
)


# ---------------------------------------------------------------------------
# _check_template
# ---------------------------------------------------------------------------

class TestCheckTemplate(unittest.TestCase):

    def test_good_template_no_errors(self):
        errors = _check_template(_GOOD_TEMPLATE, min_chars=5, max_chars=1000)
        self.assertEqual(errors, [])

    def test_no_required_vars_error(self):
        errors = _check_template(_NO_REQUIRED_TEMPLATE, min_chars=5, max_chars=1000)
        self.assertTrue(any("required_vars" in e for e in errors))

    def test_missing_required_var_in_template(self):
        errors = _check_template(_MISSING_VAR_TEMPLATE, min_chars=5, max_chars=1000)
        self.assertTrue(any("missing" in e for e in errors))

    def test_optional_var_not_in_template(self):
        t = _FakeTemplate(
            "opt_bad",
            "Do {task} only.",
            required_vars=["task"],
            optional_vars=["notes"],  # notes not in template
        )
        errors = _check_template(t, min_chars=5, max_chars=1000)
        self.assertTrue(any("notes" in e for e in errors))

    def test_render_failure_caught(self):
        class _BadTemplate(_FakeTemplate):
            def render(self, **kwargs):
                raise RuntimeError("render failed")
        t = _BadTemplate("bad_render", "Do {task}", required_vars=["task"])
        errors = _check_template(t, min_chars=5, max_chars=1000)
        self.assertTrue(any("render()" in e for e in errors))

    def test_template_too_short(self):
        t = _FakeTemplate("tiny", "X" * 3, required_vars=[])
        errors = _check_template(t, min_chars=10, max_chars=1000)
        self.assertTrue(any("too short" in e for e in errors))

    def test_template_too_long(self):
        t = _FakeTemplate("huge", "X" * 5000, required_vars=[])
        errors = _check_template(t, min_chars=5, max_chars=100)
        self.assertTrue(any("too long" in e for e in errors))

    def test_secret_pattern_detected(self):
        errors = _check_template(_SECRET_TEMPLATE, min_chars=5, max_chars=1000)
        self.assertTrue(any("secret" in e.lower() for e in errors))

    def test_no_secret_in_normal_template(self):
        errors = _check_template(_GOOD_TEMPLATE, min_chars=5, max_chars=1000)
        secret_errors = [e for e in errors if "secret" in e.lower()]
        self.assertEqual(secret_errors, [])

    def test_optional_var_valid(self):
        errors = _check_template(_OPTIONAL_TEMPLATE, min_chars=5, max_chars=1000)
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# TemplateResult / RegressionReport
# ---------------------------------------------------------------------------

class TestTemplateResult(unittest.TestCase):

    def test_no_errors_passes(self):
        r = TemplateResult(name="t")
        self.assertTrue(r.passed)

    def test_with_errors_fails(self):
        r = TemplateResult(name="t", errors=["oops"])
        self.assertFalse(r.passed)


class TestRegressionReport(unittest.TestCase):

    def test_empty_report_passes(self):
        r = RegressionReport()
        self.assertTrue(r.passed)

    def test_all_pass(self):
        r = RegressionReport(results=[
            TemplateResult("a"), TemplateResult("b")
        ])
        self.assertTrue(r.passed)
        self.assertEqual(r.failed_count, 0)

    def test_one_fail(self):
        r = RegressionReport(results=[
            TemplateResult("a"),
            TemplateResult("b", errors=["err"]),
        ])
        self.assertFalse(r.passed)
        self.assertEqual(r.failed_count, 1)

    def test_to_dict_structure(self):
        r = RegressionReport(results=[TemplateResult("a")])
        d = r.to_dict()
        for k in ("passed", "total", "failed", "results"):
            self.assertIn(k, d)

    def test_to_dict_results_list(self):
        r = RegressionReport(results=[TemplateResult("a", errors=["e"])])
        d = r.to_dict()
        self.assertEqual(len(d["results"]), 1)
        self.assertIn("name", d["results"][0])
        self.assertIn("passed", d["results"][0])
        self.assertIn("errors", d["results"][0])


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------

class TestRunChecks(unittest.TestCase):

    def test_all_good_templates_pass(self):
        registry = {"good": _GOOD_TEMPLATE, "opt": _OPTIONAL_TEMPLATE}
        report = run_checks(registry=registry)
        self.assertTrue(report.passed)

    def test_bad_template_detected(self):
        registry = {"missing_var": _MISSING_VAR_TEMPLATE}
        report = run_checks(registry=registry)
        self.assertFalse(report.passed)

    def test_total_count_matches_registry(self):
        registry = {"a": _GOOD_TEMPLATE, "b": _OPTIONAL_TEMPLATE}
        report = run_checks(registry=registry)
        self.assertEqual(len(report.results), 2)

    def test_settings_override_max_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            # Set max_chars very low to force failure
            p.write_text(json.dumps({"PROMPT_MAX_CHARS": 5}), encoding="utf-8")
            registry = {"good": _GOOD_TEMPLATE}
            report = run_checks(registry=registry, settings_path=p)
        self.assertFalse(report.passed)  # too long with max 5 chars

    def test_empty_registry_passes(self):
        report = run_checks(registry={})
        self.assertTrue(report.passed)
        self.assertEqual(len(report.results), 0)

    def test_live_registry_passes(self):
        """Check the actual prompt_builder.py REGISTRY passes all regression checks."""
        report = run_checks()
        # All built-in templates should pass
        self.assertTrue(
            report.passed,
            f"Live prompt templates failed: {[r.errors for r in report.results if not r.passed]}"
        )


# ---------------------------------------------------------------------------
# run() — exit codes and output
# ---------------------------------------------------------------------------

class TestRun(unittest.TestCase):

    def test_returns_0_on_pass(self):
        with patch.object(_mod, "run_checks",
                          return_value=RegressionReport()):
            code = run(quiet=True)
        self.assertEqual(code, 0)

    def test_returns_1_on_fail(self):
        with patch.object(_mod, "run_checks",
                          return_value=RegressionReport(
                              results=[TemplateResult("bad", errors=["err"])]
                          )):
            code = run(quiet=True)
        self.assertEqual(code, 1)

    def test_returns_2_on_error(self):
        with patch.object(_mod, "run_checks", side_effect=RuntimeError("fail")):
            code = run(quiet=True)
        self.assertEqual(code, 2)

    def test_json_output_structure(self):
        with patch.object(_mod, "run_checks", return_value=RegressionReport()):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(as_json=True)
                data = json.loads(mock_out.getvalue())
        for k in ("passed", "total", "failed", "results"):
            self.assertIn(k, data)

    def test_quiet_suppresses_output(self):
        with patch.object(_mod, "run_checks", return_value=RegressionReport()):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run(quiet=True)
                output = mock_out.getvalue()
        self.assertEqual(output, "")

    def test_text_output_shows_pass(self):
        with patch.object(_mod, "run_checks", return_value=RegressionReport()):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                run()
                output = mock_out.getvalue()
        self.assertIn("pass", output.lower())


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    def test_main_returns_0_on_live_registry(self):
        rc = _mod.main(["--quiet"])
        self.assertEqual(rc, 0)

    def test_main_json_flag(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            _mod.main(["--json"])
            data = json.loads(mock_out.getvalue())
        self.assertIn("passed", data)

    def test_main_missing_prompt_builder_returns_2(self):
        rc = _mod.main(["--quiet", "--prompt-builder", "/nonexistent/prompt_builder.py"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
