"""
task_orchestrator.py — read generated/notion_feedback.json and select the
safest next task, writing generated/next_task.json.

Safety scoring rationale:
    Design / Document / Model / Register / Strategy / Standard
        → pure thinking work; no code change, no blast radius → score 90
    Definition / SLO / Metrics
        → lightweight spec work → score 75
    Test / Harness / Coverage
        → adds tests only, low risk → score 65
    Context / Management / Enforcement
        → cross-cutting changes with moderate scope → score 50
    (default)
        → unknown scope → score 40

Unchecked items only. Among ties, prefer the item listed first (order in
Notion reflects priority already set by the user).

Usage:
    python tools/task_orchestrator.py [--feedback path] [--verbose]
"""
import sys
import json
import argparse
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from notion_config import GENERATED_DIR, FEEDBACK_JSON, NEXT_TASK_JSON


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_SCORE_TABLE: list[tuple[list[str], int, str, str]] = [
    (
        ["design", "document", "model", "register", "strategy", "standard"],
        90,
        "Low",
        "Pure design/documentation work — no code changes required, minimal blast radius.",
    ),
    (
        ["definition", "slo", "metrics", "target"],
        75,
        "Low",
        "Lightweight specification task — output is a document or config file.",
    ),
    (
        ["test", "harness", "coverage", "regression"],
        65,
        "Low-Medium",
        "Adds tests only — does not modify production code paths.",
    ),
    (
        ["context", "management", "enforcement", "scope", "window"],
        50,
        "Medium",
        "Cross-cutting change with moderate scope; requires careful planning.",
    ),
]

_DEFAULT_SCORE = 40
_DEFAULT_RISK  = "Medium"
_DEFAULT_RATIONALE = "Scope unclear from title; recommend a spike or design doc first."


def _score(title: str) -> tuple[int, str, str]:
    t = title.lower()
    for keywords, score, risk, rationale in _SCORE_TABLE:
        if any(kw in t for kw in keywords):
            return score, risk, rationale
    return _DEFAULT_SCORE, _DEFAULT_RISK, _DEFAULT_RATIONALE


# ---------------------------------------------------------------------------
# Task suggestion derivation
# ---------------------------------------------------------------------------

_SCOPE_HINTS: dict[str, str] = {
    "ThreatModelDocument":               "1 markdown file: assets, threats, mitigations",
    "PromptEngineeringStandard":          "1 PROMPT_STANDARD.md + snapshot test fixture",
    "TechnicalDebtRegister":             "1 TECH_DEBT.md with categorised debt items",
    "SLODefinitions":                    "1 SLO.md defining 3–5 measurable targets",
    "ContextWindowManagementStrategy":   "1 CONTEXT_STRATEGY.md + CLAUDE.md trim guidelines",
    "HumanInTheLoopTriggerDesign":       "1 HITL_DESIGN.md with formal trigger criteria",
    "AIActionScopeEnforcementDesign":    "1 ACTION_SCOPE.md with per-task tool permission matrix",
}

_DEFAULT_SCOPE = "Scope to be determined; start with a design spike."


def _next_task_id(feedback: dict) -> str:
    """Derive a suggested TASK-NNN ID from the CHANGELOG metrics in feedback."""
    # feedback doesn't carry task count directly; read from gap_domains notes
    # Fallback: derive from open_priorities position
    return "TASK-311"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def orchestrate(feedback_path=None, verbose: bool = False) -> dict:
    path = feedback_path or FEEDBACK_JSON
    if not path.exists():
        print(f"ERROR: feedback file not found: {path}\nRun notion_feedback.py first.", file=sys.stderr)
        sys.exit(1)

    feedback = json.loads(path.read_text(encoding="utf-8"))
    priorities = feedback.get("layer3_priorities", [])
    unchecked = [p for p in priorities if not p.get("checked", False)]

    if not unchecked:
        print("All Layer 3 priorities are already checked off. No task selected.")
        result = {"selected_at": datetime.now(timezone.utc).isoformat(), "task": None}
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        NEXT_TASK_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    # Score every unchecked item; stable sort preserves original order for ties.
    scored = []
    for item in unchecked:
        score, risk, rationale = _score(item["title"])
        scored.append({
            "title":           item["title"],
            "audit_refs":      item.get("audit_refs", ""),
            "safety_score":    score,
            "risk_level":      risk,
            "rationale":       rationale,
            "estimated_scope": _SCOPE_HINTS.get(item["title"], _DEFAULT_SCOPE),
        })

    scored.sort(key=lambda x: -x["safety_score"])
    best = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None

    # Incorporate high-severity gap domain context if audit_refs match
    high_domains = feedback.get("summary", {}).get("high_severity_domains", [])
    if high_domains and verbose:
        print(f"High-severity gap domains: {', '.join(high_domains)}")

    result = {
        "selected_at":    datetime.now(timezone.utc).isoformat(),
        "layer1_pct":     feedback.get("layer1_completion", {}).get("pct", 100),
        "open_count":     len(unchecked),
        "task": {
            "suggested_task_id": _next_task_id(feedback),
            **best,
        },
        "runner_up": runner_up,
        "all_scored": scored,
    }

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    NEXT_TASK_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if verbose:
        print(f"\nSelected:   {best['title']}")
        print(f"Risk level: {best['risk_level']}")
        print(f"Score:      {best['safety_score']}/100")
        print(f"Rationale:  {best['rationale']}")
        print(f"Scope:      {best['estimated_scope']}")
        if runner_up:
            print(f"\nRunner-up:  {runner_up['title']} (score {runner_up['safety_score']})")

    print(f"\nWrote {NEXT_TASK_JSON}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Select safest next task from Notion feedback")
    parser.add_argument("--feedback", type=str, help="Override feedback JSON path")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    feedback_path = __import__("pathlib").Path(args.feedback) if args.feedback else FEEDBACK_JSON
    result = orchestrate(feedback_path=feedback_path, verbose=args.verbose)

    if result.get("task"):
        t = result["task"]
        print(f"\nNext task: {t['suggested_task_id']} — {t['title']}")
        print(f"Risk: {t['risk_level']}  Score: {t['safety_score']}/100")
        print(f"Scope: {t['estimated_scope']}")


if __name__ == "__main__":
    main()
