"""Tests for _load_tool() in health check blueprints (TASK-392).

Each health blueprint has its own copy of _load_tool() which uses importlib to
load tools from tools/.  Tests here exercise the real importlib path (no mock)
and the sys.modules cache-hit path, covering lines 42-48 in each blueprint.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.blueprints.context_window as cw_mod
import api.blueprints.debt_scan      as ds_mod
import api.blueprints.ci_quality     as ci_mod
import api.blueprints.pre_release    as pr_mod
import api.blueprints.slo            as slo_mod
import api.blueprints.prompt_regression as preg_mod

# (tool_name, blueprint_module, sys_modules_key)
_CASES = [
    ("context_window_budget", cw_mod,   "context_window_budget"),
    ("debt_scan",             ds_mod,   "debt_scan"),
    ("ci_quality_gate",       ci_mod,   "ci_quality_gate"),
    ("pre_release_check",     pr_mod,   "pre_release_check"),
    ("slo_check",             slo_mod,  "slo_check"),
    ("prompt_regression_check", preg_mod, "prompt_regression_check"),
]


class TestLoadToolRealImport(unittest.TestCase):
    """_load_tool() loads the real module via importlib (covers lines 42-46)."""

    def setUp(self):
        # Remove cached modules so the real import path is exercised
        for _, _, key in _CASES:
            sys.modules.pop(key, None)

    def tearDown(self):
        for _, _, key in _CASES:
            sys.modules.pop(key, None)

    def test_context_window_budget_loads(self):
        mod = cw_mod._load_tool("context_window_budget")
        self.assertTrue(hasattr(mod, "check_budget"))

    def test_debt_scan_loads(self):
        mod = ds_mod._load_tool("debt_scan")
        self.assertTrue(hasattr(mod, "scan"))

    def test_ci_quality_gate_loads(self):
        mod = ci_mod._load_tool("ci_quality_gate")
        self.assertIsNotNone(mod)

    def test_pre_release_check_loads(self):
        mod = pr_mod._load_tool("pre_release_check")
        self.assertIsNotNone(mod)

    def test_slo_check_loads(self):
        mod = slo_mod._load_tool("slo_check")
        self.assertIsNotNone(mod)

    def test_prompt_regression_check_loads(self):
        mod = preg_mod._load_tool("prompt_regression_check")
        self.assertIsNotNone(mod)


class TestLoadToolCacheHit(unittest.TestCase):
    """_load_tool() returns cached module from sys.modules on second call (covers lines 42-43)."""

    def tearDown(self):
        for _, _, key in _CASES:
            sys.modules.pop(key, None)

    def test_context_window_cache_hit(self):
        sys.modules.pop("context_window_budget", None)
        first  = cw_mod._load_tool("context_window_budget")
        second = cw_mod._load_tool("context_window_budget")
        self.assertIs(first, second)

    def test_debt_scan_cache_hit(self):
        sys.modules.pop("debt_scan", None)
        first  = ds_mod._load_tool("debt_scan")
        second = ds_mod._load_tool("debt_scan")
        self.assertIs(first, second)

    def test_slo_check_cache_hit(self):
        sys.modules.pop("slo_check", None)
        first  = slo_mod._load_tool("slo_check")
        second = slo_mod._load_tool("slo_check")
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
