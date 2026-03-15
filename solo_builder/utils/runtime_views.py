"""
utils/runtime_views.py
Canonical shared runtime view helpers for priority queues, stalled detection,
DAG summaries, forecasts, and agent statistics.

All surfaces (CLI, API, Discord bot, dashboard) should derive their
outputs from these functions to guarantee consistency.

The priority logic mirrors Planner._risk() and Planner._deps_met() exactly.
The stalled logic mirrors SelfHealer.find_stalled() exactly.
The forecast/rate logic mirrors MetaOptimizer.record()/forecast() exactly.
"""

from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# PRIORITY QUEUE  (mirrors Planner.prioritize + Planner._risk)
# ═══════════════════════════════════════════════════════════════════════════════

def deps_met(dag: Dict, task_name: str) -> bool:
    """Return True if every task this task depends on is Verified."""
    for dep in dag.get(task_name, {}).get("depends_on", []):
        if dag.get(dep, {}).get("status") != "Verified":
            return False
    return True


def compute_risk(
    st_data: Dict,
    step: int,
    stall_threshold: int = 5,
    w_stall: float = 1.0,
    w_staleness: float = 1.0,
    w_shadow: float = 1.0,
) -> int:
    """
    Compute risk score for a single subtask.

    Mirrors Planner._risk() exactly (minus repo_index bonus, which requires
    the live RepoIndex object and is additive-only).

    Args:
        st_data: subtask dict with status, last_update, shadow
        step: current step number
        stall_threshold: steps in Running before considered stalled
        w_stall: weight for stall risk
        w_staleness: weight for age-based risk
        w_shadow: weight for shadow bonus

    Returns:
        Integer risk score (higher = more urgent)
    """
    staleness = step - st_data.get("last_update", 0)
    status = st_data.get("status", "Pending")

    if status == "Running":
        risk = int(1000 * w_stall)
        if staleness >= stall_threshold:
            risk += int(500 * w_stall) + staleness * 20
        else:
            risk += int(staleness * 10 * w_staleness)
    elif status == "Pending":
        risk = int(staleness * 8 * w_staleness) if staleness > 2 else 0
        if st_data.get("shadow") == "Done":
            risk += int(50 * w_shadow)
    else:
        risk = 0

    return risk


def priority_queue(
    dag: Dict,
    step: int,
    stall_threshold: int = 5,
    w_stall: float = 1.0,
    w_staleness: float = 1.0,
    w_shadow: float = 1.0,
    limit: int = 0,
) -> List[Dict[str, Any]]:
    """
    Return the priority queue as a list of dicts, sorted by risk descending.

    This is the canonical implementation that all surfaces should use.
    The Planner class itself can continue to use its own prioritize() method
    (which is the same logic); this function exists for stateless callers
    that only have the DAG dict and settings.

    Args:
        dag: full DAG dict
        step: current step number
        stall_threshold: steps in Running before considered stalled
        w_stall: weight for stall risk
        w_staleness: weight for age-based risk
        w_shadow: weight for shadow bonus
        limit: max results (0 = unlimited)

    Returns:
        List of dicts with keys: subtask, task, branch, status, risk, age
    """
    candidates: List[Dict[str, Any]] = []
    for task_name, task_data in dag.items():
        if not deps_met(dag, task_name):
            continue
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                status = st_data.get("status", "Pending")
                if status not in ("Pending", "Running"):
                    continue
                risk = compute_risk(
                    st_data, step, stall_threshold,
                    w_stall, w_staleness, w_shadow,
                )
                age = step - st_data.get("last_update", 0)
                candidates.append({
                    "subtask": st_name,
                    "task": task_name,
                    "branch": branch_name,
                    "status": status,
                    "risk": risk,
                    "age": age,
                })
    candidates.sort(key=lambda x: x["risk"], reverse=True)
    if limit > 0:
        candidates = candidates[:limit]
    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# STALLED DETECTION  (mirrors SelfHealer.find_stalled)
# ═══════════════════════════════════════════════════════════════════════════════

def stalled_subtasks(
    dag: Dict,
    step: int,
    stall_threshold: int = 5,
) -> List[Dict[str, Any]]:
    """
    Return subtasks stuck in Running longer than stall_threshold.

    Mirrors SelfHealer.find_stalled() exactly:
    - Only checks status == "Running" (NOT Review)
    - age = step - last_update
    - age >= stall_threshold → stalled

    Args:
        dag: full DAG dict
        step: current step number
        stall_threshold: steps in Running before considered stalled

    Returns:
        List of dicts with keys: subtask, task, branch, age, description
        Sorted by age descending.
    """
    stuck: List[Dict[str, Any]] = []
    for task_name, task_data in dag.items():
        for branch_name, branch_data in task_data.get("branches", {}).items():
            for st_name, st_data in branch_data.get("subtasks", {}).items():
                if st_data.get("status") == "Running":
                    age = step - st_data.get("last_update", 0)
                    if age >= stall_threshold:
                        stuck.append({
                            "subtask": st_name,
                            "task": task_name,
                            "branch": branch_name,
                            "age": age,
                            "description": (st_data.get("description") or "")[:80],
                        })
    stuck.sort(key=lambda x: x["age"], reverse=True)
    return stuck


# ═══════════════════════════════════════════════════════════════════════════════
# DAG SUMMARY STATS
# ═══════════════════════════════════════════════════════════════════════════════

def dag_summary(dag: Dict) -> Dict[str, int]:
    """
    Compute canonical DAG summary counts.

    Counts all subtasks by status across all tasks and branches.

    Args:
        dag: full DAG dict

    Returns:
        Dict with keys: total, verified, running, pending, review, failed
    """
    total = verified = running = pending = review = failed = 0
    for task_data in dag.values():
        for branch_data in task_data.get("branches", {}).values():
            for st_data in branch_data.get("subtasks", {}).values():
                total += 1
                s = st_data.get("status", "Pending")
                if s == "Verified":
                    verified += 1
                elif s == "Running":
                    running += 1
                elif s == "Pending":
                    pending += 1
                elif s == "Review":
                    review += 1
                elif s == "Failed":
                    failed += 1
    return {
        "total": total,
        "verified": verified,
        "running": running,
        "pending": pending,
        "review": review,
        "failed": failed,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RATES & FORECAST  (mirrors MetaOptimizer rate computation)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_rates(meta_history: List[Dict]) -> Dict[str, float]:
    """
    Compute verify_rate and heal_rate from meta_history using a 10-step
    rolling window — identical to MetaOptimizer.record() logic.

    Args:
        meta_history: list of historical metric dicts with 'verified', 'healed'

    Returns:
        Dict with keys: verify_rate, heal_rate (both float)
    """
    if not meta_history:
        return {"verify_rate": 0.0, "heal_rate": 0.0}
    window = min(10, len(meta_history))
    recent = meta_history[-window:]
    verify_rate = sum(r.get("verified", 0) for r in recent) / window
    heal_rate = sum(r.get("healed", 0) for r in recent) / window
    return {"verify_rate": verify_rate, "heal_rate": heal_rate}


def forecast_summary(
    dag: Dict,
    meta_history: List[Dict],
    step: int = 0,
) -> Dict[str, Any]:
    """
    Canonical forecast summary combining DAG stats and rate-based ETA.

    Computes progress percentage and estimates steps-to-completion based
    on verify_rate from recent history.

    Args:
        dag: full DAG dict
        meta_history: list of historical metric dicts
        step: current step number (optional, for response metadata)

    Returns:
        Dict with keys: step, total, verified, running, pending, review,
        remaining, pct, verify_rate, heal_rate, eta_steps
    """
    stats = dag_summary(dag)
    rates = compute_rates(meta_history)
    total = stats["total"]
    verified = stats["verified"]
    remaining = total - verified
    pct = round(verified / total * 100, 1) if total else 0.0
    vr = rates["verify_rate"]
    eta = round(remaining / (vr + 1e-6)) if vr > 0 else None
    return {
        "step": step,
        "total": total,
        "verified": verified,
        "running": stats["running"],
        "pending": stats["pending"],
        "review": stats["review"],
        "remaining": remaining,
        "pct": pct,
        "verify_rate": round(vr, 3),
        "heal_rate": round(rates["heal_rate"], 3),
        "eta_steps": eta,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT STATS  (stateless, from persisted state)
# ═══════════════════════════════════════════════════════════════════════════════

def agent_stats(
    state: Dict,
    stall_threshold: int = 5,
    executor_max_per_step: int = 2,
) -> Dict[str, Any]:
    """
    Canonical agent statistics derived from the persisted state dict.

    Suitable for API/bot surfaces that read state from disk.
    Gracefully handles missing optional keys (backward compatibility).

    Args:
        state: full persisted state dict
        stall_threshold: steps in Running before considered stalled
        executor_max_per_step: max subtasks executor processes per step

    Returns:
        Dict with keys: step, planner, executor, healer, meta, forecast,
        safety_guard, reliability, usage, policy
    """
    dag = state.get("dag", {})
    step = state.get("step", 0)
    healed_total = state.get("healed_total", 0)
    meta_history = state.get("meta_history", [])
    safety = state.get("safety_state", {})

    stats = dag_summary(dag)
    stalled = stalled_subtasks(dag, step, stall_threshold)
    rates = compute_rates(meta_history)
    remaining = stats["total"] - stats["verified"]
    vr = rates["verify_rate"]
    eta = round(remaining / (vr + 1e-6)) if vr > 0 else None

    return {
        "step": step,
        "planner": {"cache_interval": 5},
        "executor": {"max_per_step": executor_max_per_step},
        "healer": {
            "healed_total": healed_total,
            "threshold": stall_threshold,
            "currently_stalled": len(stalled),
        },
        "meta": {
            "history_len": len(meta_history),
            "heal_rate": round(rates["heal_rate"], 3),
            "verify_rate": round(vr, 3),
        },
        "forecast": {
            "total": stats["total"],
            "verified": stats["verified"],
            "remaining": remaining,
            "pct": round(stats["verified"] / stats["total"] * 100) if stats["total"] else 0,
            "eta_steps": eta,
        },
        "safety_guard": {
            "dynamic_tasks_created": safety.get("dynamic_tasks_created", 0),
            "ra_last_run_step": safety.get("ra_last_run_step", -1),
            "patch_rejections_total": sum(
                v.get("count", 0)
                for v in safety.get("patch_rejections", {}).values()
            ),
            "patch_threshold_hits": safety.get("patch_threshold_hits", 0),
        },
        "reliability": _reliability_stats(state),
        "usage": _usage_stats(state),
        "policy": _policy_stats(state),
    }


def _policy_stats(state: Dict) -> Dict[str, Any]:
    """
    Extract policy enforcement statistics from persisted state.

    Returns a dict suitable for API/bot consumption.
    Always returns a valid dict even when policy_state is absent
    (backward compatibility with older state files).

    Args:
        state: full persisted state dict

    Returns:
        Dict with keys: policy_block_count, critical_path_review_count,
        oversized_patch_count
    """
    ps = state.get("policy_state", {})
    return {
        "policy_block_count": ps.get("policy_block_count", 0),
        "critical_path_review_count": ps.get("critical_path_review_count", 0),
        "oversized_patch_count": ps.get("oversized_patch_count", 0),
    }


def _usage_stats(state: Dict) -> Dict[str, Any]:
    """
    Extract cumulative AI usage statistics from persisted state.

    Returns a dict suitable for API/bot consumption.
    Always returns a valid dict even when usage_state is absent
    (backward compatibility with older state files).

    Args:
        state: full persisted state dict

    Returns:
        Dict with keys: total_calls, total_tokens, total_cost_usd,
        total_deferred, by_agent
    """
    us = state.get("usage_state", {})
    return {
        "total_calls": us.get("total_calls", 0),
        "total_tokens": us.get("total_tokens", 0),
        "total_cost_usd": us.get("total_cost_usd", 0.0),
        "total_deferred": us.get("total_deferred", 0),
        "by_agent": us.get("by_agent", {}),
    }


def _reliability_stats(state: Dict) -> Dict[str, Any]:
    """
    Extract reliability/recovery statistics from persisted state.

    Returns a dict suitable for API/bot consumption.
    Always returns a valid dict even when recovery_state is absent
    (backward compatibility with older state files).

    Args:
        state: full persisted state dict

    Returns:
        Dict with keys: recovery_count, last_failed_phase,
        last_recovery_source, malformed_trigger_count,
        persistence_fallback_count, partial_work_repair_count
    """
    rs = state.get("recovery_state", {})
    return {
        "recovery_count": rs.get("recovery_count", 0),
        "last_failed_phase": rs.get("last_failed_phase"),
        "last_recovery_source": rs.get("last_recovery_source"),
        "malformed_trigger_count": rs.get("malformed_trigger_count", 0),
        "persistence_fallback_count": rs.get("persistence_fallback_count", 0),
        "partial_work_repair_count": rs.get("partial_work_repair_count", 0),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PER-TASK STATS  (mirrors /stats in API and _format_stats in bot)
# ═══════════════════════════════════════════════════════════════════════════════

def per_task_stats(dag: Dict) -> Dict[str, Any]:
    """
    Per-task breakdown: verified, total, pct, avg steps.

    Computes statistics for each task and grand totals.

    Args:
        dag: full DAG dict

    Returns:
        Dict with keys: tasks, grand_verified, grand_total, grand_pct,
        grand_avg_steps. tasks is a list of dicts with keys: id, verified,
        total, pct, avg_steps, status
    """
    tasks = []
    grand_v = grand_t = 0
    all_dur: list = []
    for task_id, task_data in dag.items():
        tv = tt = 0
        durs: list = []
        for b in task_data.get("branches", {}).values():
            for st in b.get("subtasks", {}).values():
                tt += 1
                if st.get("status") == "Verified":
                    tv += 1
                    h = st.get("history", [])
                    if len(h) >= 2:
                        durs.append(h[-1].get("step", 0) - h[0].get("step", 0))
        pct = round(tv / tt * 100, 1) if tt else 0
        avg = round(sum(durs) / len(durs), 1) if durs else None
        tasks.append({
            "id": task_id,
            "verified": tv,
            "total": tt,
            "pct": pct,
            "avg_steps": avg,
            "status": task_data.get("status"),
        })
        grand_v += tv
        grand_t += tt
        all_dur.extend(durs)
    return {
        "tasks": tasks,
        "grand_verified": grand_v,
        "grand_total": grand_t,
        "grand_pct": round(grand_v / grand_t * 100, 1) if grand_t else 0,
        "grand_avg_steps": round(sum(all_dur) / len(all_dur), 1) if all_dur else None,
    }
