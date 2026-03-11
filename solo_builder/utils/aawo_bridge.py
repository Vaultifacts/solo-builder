"""
aawo_bridge.py — thin subprocess interface to the Autonomous Agent Workflow Orchestrator.

All public functions return None on any failure (AAWO unavailable, timeout, JSON parse
error). Callers must handle None gracefully — the bridge is purely advisory.
"""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("solo_builder")

# AAWO integration is opt-in — requires explicit configuration via:
#   1. AAWO_RUNTIME_PATH environment variable, or
#   2. settings.json key "AAWO_PATH"
# Without explicit config the bridge is a no-op.

_BUILTIN_MAPPING = {
    "testing_agent":       {"action_type": "read_only",      "tools": "Read,Grep,Glob"},
    "security_agent":      {"action_type": "analysis",       "tools": "Read,Grep,Glob"},
    "devops_agent":        {"action_type": "file_edit",      "tools": "Read,Grep,Glob"},
    "architect_agent":     {"action_type": "full_execution", "tools": "Read,Grep,Glob"},
    "orchestration_agent": {"action_type": "analysis",       "tools": "Read,Grep,Glob"},
    "repo_analyzer_agent": {"action_type": "read_only",      "tools": "Read,Grep,Glob"},
    "registry_agent":      {"action_type": "read_only",      "tools": "Read,Grep,Glob"},
    "routing_agent":       {"action_type": "analysis",       "tools": "Read,Grep,Glob"},
}


def _aawo_path() -> Optional[Path]:
    # 1. Env var override
    override = os.environ.get("AAWO_RUNTIME_PATH")
    if override:
        p = Path(override)
        return p if p.exists() else None
    # 2. settings.json AAWO_PATH key
    cfg = _load_settings()
    configured = cfg.get("AAWO_PATH")
    if configured:
        p = Path(configured)
        return p if p.exists() else None
    # Not configured — no-op
    return None


def _load_settings() -> dict:
    try:
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "settings.json"
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _run(args: list) -> Optional[dict]:
    path = _aawo_path()
    if path is None:
        logger.debug("aawo_bridge: AAWO runtime not found — skipping")
        return None
    cfg = _load_settings()
    timeout = cfg.get("AAWO_TIMEOUT", 10)
    try:
        result = subprocess.run(
            ["python", str(path)] + args + ["--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        if result.returncode != 0:
            logger.warning("aawo_bridge: non-zero exit %d stderr=%s",
                           result.returncode, result.stderr[:200])
            return None
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning("aawo_bridge: timeout after %ds", timeout)
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("aawo_bridge: error %s", exc)
        return None


def route_task(description: str, repo_path: str = ".") -> Optional[dict]:
    """Route a task description via AAWO. Returns routing decision dict or None."""
    return _run(["route", "--task", description])


def get_snapshot(repo_path: str = ".") -> Optional[dict]:
    """Build (or load cached) AAWO snapshot of repo_path. Returns snapshot dict or None."""
    return _run(["snapshot", "--repo", repo_path])


def _load_mapping() -> dict:
    cfg = _load_settings()
    override = cfg.get("AAWO_AGENT_MAPPING")
    if isinstance(override, dict):
        merged = dict(_BUILTIN_MAPPING)
        merged.update(override)
        return merged
    return _BUILTIN_MAPPING


def resolve_executor_config(agent_id: str) -> Optional[dict]:
    """Return {"action_type": str, "tools": str} for an AAWO agent_id, or None."""
    return _load_mapping().get(agent_id)


def enrich_subtask(st_data: dict, description: str, repo_path: str = ".") -> dict:
    """
    Consult AAWO routing and inject action_type/tools into st_data if not already set.

    Returns st_data unchanged on any failure or if both fields are already present.
    Safe to call even if AAWO is unavailable.
    """
    if st_data.get("tools"):
        return st_data

    decision = route_task(description, repo_path)
    if decision is None or decision.get("policy_blocked"):
        return st_data

    agent_id = decision.get("selected_agent_id")
    if not agent_id:
        return st_data

    config = resolve_executor_config(agent_id)
    if config is None:
        logger.debug("aawo_bridge: no mapping for agent_id=%s", agent_id)
        return st_data

    st_data["action_type"] = config["action_type"]
    st_data["tools"] = config["tools"]
    st_data["_aawo_routing"] = {
        "agent_id": agent_id,
        "score":    decision.get("score", 0.0),
        "fallback": decision.get("fallback", False),
    }
    logger.info("aawo_bridge: enriched subtask action_type=%s tools=%s agent_id=%s",
                config["action_type"], config["tools"], agent_id)
    return st_data
