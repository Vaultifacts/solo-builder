"""Regression guard: architecture audit score must stay >= 95.0."""
import json
import unittest
from pathlib import Path

_ARCH_LAST = Path(__file__).resolve().parents[2] / "claude" / "arch_last.json"


class TestArchScoreRegression(unittest.TestCase):

    def test_arch_last_exists(self):
        self.assertTrue(_ARCH_LAST.exists(), "claude/arch_last.json missing — run audit_check.ps1")

    def test_health_score_above_threshold(self):
        data = json.loads(_ARCH_LAST.read_text(encoding="utf-8"))
        score = data.get("health_score", 0)
        self.assertGreaterEqual(score, 95.0, f"Arch score {score} below 95.0 threshold")

    def test_zero_critical_findings(self):
        data = json.loads(_ARCH_LAST.read_text(encoding="utf-8"))
        criticals = data.get("counts", {}).get("critical", -1)
        self.assertEqual(criticals, 0, f"Expected 0 critical findings, got {criticals}")


if __name__ == "__main__":
    unittest.main()
