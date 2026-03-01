"""
solo_builder_cli.py
Solo Builder AI Agent CLI — main entry point.

Agents:
  Planner        → prioritizes subtasks by risk
  Executor       → advances subtask lifecycle (Pending → Running → Verified)
  ShadowAgent    → tracks expected states, detects & resolves conflicts
  Verifier       → enforces DAG consistency (branch/task status roll-up)
  SelfHealer     → detects stalled subtasks and resets them
  MetaOptimizer  → adapts heuristics, generates forecasts

CLI commands: run | snapshot | status | add_task | set KEY=VALUE | help | exit
"""

import os
import sys
import copy
import json
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple

# ── Path setup (allow running from project root or solo_builder/) ─────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from utils.helper_functions import (
    load_settings,
    make_bar,
    dag_stats,
    branch_stats,
    shadow_stats,
    memory_depth,
    add_memory_snapshot,
    format_status,
    format_shadow,
    validate_dag,
    # ANSI
    RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA,
    WHITE, BOLD, DIM, BLINK, RESET,
    STATUS_COLORS,
    # Alerts
    ALERT_STALLED, ALERT_PREDICTIVE, ALERT_CONFLICT, ALERT_HEALED,
)

try:
    from solo_builder_live_multi_snapshot import generate_live_multi_pdf
    _PDF_OK = True
except ImportError:
    _PDF_OK = False


# ── Load config ───────────────────────────────────────────────────────────────
_CFG_PATH = os.path.join(_HERE, "config", "settings.json")
_CFG = load_settings(_CFG_PATH)

STALL_THRESHOLD    : int   = _CFG["STALL_THRESHOLD"]
SNAPSHOT_INTERVAL  : int   = _CFG["SNAPSHOT_INTERVAL"]
DAG_UPDATE_INTERVAL: int   = _CFG["DAG_UPDATE_INTERVAL"]
PDF_OUTPUT_PATH    : str   = _CFG["PDF_OUTPUT_PATH"]
STATE_PATH         : str   = _CFG.get("STATE_PATH", "./state/solo_builder_state.json")
AUTO_SAVE_INTERVAL : int   = _CFG.get("AUTO_SAVE_INTERVAL", 5)
AUTO_STEP_DELAY    : float = _CFG.get("AUTO_STEP_DELAY", 0.4)
VERBOSITY          : str   = _CFG["VERBOSITY"]
BAR_WIDTH          : int   = _CFG["BAR_WIDTH"]
MAX_ALERTS         : int   = _CFG["MAX_ALERTS"]
EXEC_MAX_PER_STEP  : int   = _CFG["EXECUTOR_MAX_PER_STEP"]
EXEC_VERIFY_PROB   : float = _CFG["EXECUTOR_VERIFY_PROBABILITY"]
CLAUDE_TIMEOUT        : int = _CFG.get("CLAUDE_TIMEOUT", 60)
CLAUDE_ALLOWED_TOOLS  : str = _CFG.get("CLAUDE_ALLOWED_TOOLS", "")
ANTHROPIC_MODEL       : str = _CFG.get("ANTHROPIC_MODEL",      "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS  : int = _CFG.get("ANTHROPIC_MAX_TOKENS", 300)

# Resolve relative paths to script location
if not os.path.isabs(PDF_OUTPUT_PATH):
    PDF_OUTPUT_PATH = os.path.join(_HERE, PDF_OUTPUT_PATH)
if not os.path.isabs(STATE_PATH):
    STATE_PATH = os.path.join(_HERE, STATE_PATH)
JOURNAL_PATH = os.path.join(_HERE, "journal.md")


# ── Initial DAG Definition ────────────────────────────────────────────────────
INITIAL_DAG: Dict[str, Any] = {
    "Task 0": {
        "status": "Running",
        "depends_on": [],
        "branches": {
            "Branch A": {
                "status": "Running",
                "subtasks": {
                    "A1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 5 key features a solo developer AI project management tool needs. Bullet points.", "output": ""},
                    "A2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.", "output": ""},
                    "A3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.", "output": ""},
                    "A4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 risks of building a self-healing agent system, and one mitigation for each?", "output": ""},
                    "A5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a tagline for Solo Builder in under 10 words.", "output": ""},
                },
            },
            "Branch B": {
                "status": "Pending",
                "subtasks": {
                    "B1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.", "output": ""},
                    "B2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 real-world use cases for a DAG-based AI project tracker.", "output": ""},
                    "B3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "In one sentence, explain what a MetaOptimizer does in an AI pipeline.", "output": ""},
                },
            },
        },
    },
    "Task 1": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch C": {
                "status": "Pending",
                "subtasks": {
                    "C1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What does a DAG (Directed Acyclic Graph) represent in software project management? Answer in one paragraph.", "output": ""},
                    "C2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 advantages of using a priority queue to schedule software tasks.", "output": ""},
                    "C3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Explain the concept of task staleness in a project management system in 2 sentences.", "output": ""},
                    "C4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a shadow state in an agent-based system? Give one concrete example.", "output": ""},
                },
            },
            "Branch D": {
                "status": "Pending",
                "subtasks": {
                    "D1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe 2 strategies for preventing task starvation in a priority-based scheduler.", "output": ""},
                    "D2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between optimistic and pessimistic task verification? One paragraph.", "output": ""},
                },
            },
        },
    },
    "Task 2": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch E": {
                "status": "Pending",
                "subtasks": {
                    "E1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 benefits of self-healing automation in a software pipeline?", "output": ""},
                    "E2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.", "output": ""},
                    "E3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 metrics that indicate an AI agent system is performing well.", "output": ""},
                    "E4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between reactive and proactive error handling in agent systems? One sentence each.", "output": ""},
                    "E5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Give one example of a heuristic weight that a MetaOptimizer might adjust in a task planner.", "output": ""},
                },
            },
            "Branch F": {
                "status": "Pending",
                "subtasks": {
                    "F1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the role of a Verifier agent in a multi-agent pipeline? 2 sentences.", "output": ""},
                    "F2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe how memory snapshots help with debugging in an agent system. One paragraph.", "output": ""},
                    "F3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 2 ways a ShadowAgent could detect state inconsistencies in a DAG pipeline.", "output": ""},
                    "F4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between a branch and a task in a DAG-based project tracker? One sentence.", "output": ""},
                },
            },
        },
    },
    "Task 3": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch G": {
                "status": "Pending",
                "subtasks": {
                    "G1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is continuous integration and how does it relate to automated project management? One paragraph.", "output": ""},
                    "G2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 common causes of technical debt in solo developer projects.", "output": ""},
                    "G3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the MVP (Minimum Viable Product) concept in 2 sentences.", "output": ""},
                    "G4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a sprint in agile methodology? One sentence.", "output": ""},
                    "G5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 developer tools a solo builder could use alongside an AI task manager.", "output": ""},
                    "G6": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between async and sync task execution in pipelines? One paragraph.", "output": ""},
                },
            },
            "Branch H": {
                "status": "Pending",
                "subtasks": {
                    "H1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of a 'Definition of Done' in software projects. 2 sentences.", "output": ""},
                    "H2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 ways to reduce context-switching costs for a solo developer.", "output": ""},
                    "H3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the Pomodoro technique and how might it help a solo developer? One paragraph.", "output": ""},
                    "H4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Give 2 examples of how AI can assist with project estimation for a solo developer.", "output": ""},
                },
            },
            "Branch I": {
                "status": "Pending",
                "subtasks": {
                    "I1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is scope creep and how can a solo developer prevent it? One paragraph.", "output": ""},
                    "I2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 warning signs that a solo software project is at risk of failure.", "output": ""},
                    "I3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of 'bikeshedding' and why it's a risk for solo developers. 2 sentences.", "output": ""},
                },
            },
        },
    },
    "Task 4": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch J": {
                "status": "Pending",
                "subtasks": {
                    "J1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 principles of clean code that every solo developer should follow?", "output": ""},
                    "J2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the DRY (Don't Repeat Yourself) principle in one sentence with a concrete example.", "output": ""},
                    "J3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a code smell? Give 3 examples.", "output": ""},
                    "J4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Pick 3 of the SOLID principles and explain each in one bullet point.", "output": ""},
                    "J5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is test-driven development (TDD)? Describe it in 2 sentences.", "output": ""},
                    "J6": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 benefits of writing unit tests for a solo developer project.", "output": ""},
                    "J7": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a linter and why should solo developers use one? One paragraph.", "output": ""},
                    "J8": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the difference between unit tests and integration tests in one sentence each.", "output": ""},
                },
            },
            "Branch K": {
                "status": "Pending",
                "subtasks": {
                    "K1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is semantic versioning (semver)? Give one example of a version bump and why.", "output": ""},
                    "K2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 best practices for writing clear git commit messages.", "output": ""},
                    "K3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a pull request and how does it help with code quality? One paragraph.", "output": ""},
                    "K4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of self-code-review for a solo developer. 2 sentences.", "output": ""},
                    "K5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is continuous deployment and how does it benefit a solo developer project? 2 sentences.", "output": ""},
                },
            },
        },
    },
    "Task 5": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch L": {
                "status": "Pending",
                "subtasks": {
                    "L1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 key metrics a solo developer should track for a CLI tool project?", "output": ""},
                    "L2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of a project roadmap in 2 sentences.", "output": ""},
                    "L3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 ways to gather user feedback on a solo developer CLI tool.", "output": ""},
                    "L4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is feature prioritization and why is it important for solo developers? One paragraph.", "output": ""},
                    "L5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe 2 ways AI can help a solo developer with project documentation.", "output": ""},
                    "L6": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a changelog and why should every project have one? One sentence.", "output": ""},
                },
            },
            "Branch M": {
                "status": "Pending",
                "subtasks": {
                    "M1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 strategies for getting early users for a solo developer tool.", "output": ""},
                    "M2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is developer experience (DX) and why does it matter? One paragraph.", "output": ""},
                    "M3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe 2 ways to measure whether a solo developer project is succeeding.", "output": ""},
                    "M4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is open source and what are 2 benefits of open-sourcing a solo developer project?", "output": ""},
                },
            },
            "Branch N": {
                "status": "Pending",
                "subtasks": {
                    "N1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 signs that a software project is ready for its first public release?", "output": ""},
                    "N2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of a 'soft launch' for a developer tool. 2 sentences.", "output": ""},
                    "N3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 things a developer should document before releasing an open-source project.", "output": ""},
                    "N4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a README file and what are its 3 most important sections? One sentence each.", "output": ""},
                    "N5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a one-sentence mission statement for Solo Builder — an AI-powered CLI that manages DAG-based tasks for solo developers.", "output": ""},
                },
            },
        },
    },
    "Task 6": {
        "status": "Pending",
        "depends_on": ["Task 1", "Task 2", "Task 3", "Task 4", "Task 5"],
        "branches": {
            "Branch O": {
                "status": "Pending",
                "subtasks": {
                    "O1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Read the file state/solo_builder_state.json. Summarize in 3 bullet points: how many tasks completed, which task had the most subtasks, and one notable Claude output found in the data.", "output": "", "tools": "Read,Glob,Grep"},
                    "O2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe how self-healing agents reduce manual intervention in a software project pipeline. One paragraph.", "output": ""},
                    "O3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a 3-sentence executive summary of Solo Builder for a developer audience.", "output": ""},
                },
            },
            "Branch P": {
                "status": "Pending",
                "subtasks": {
                    "P1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What would a 'v2.0' of Solo Builder look like? List 3 major new features with one sentence each.", "output": ""},
                    "P2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "How would you adapt Solo Builder for a team of 3-5 developers instead of a solo developer? Give 3 key changes.", "output": ""},
                    "P3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a haiku about software agents managing project tasks autonomously.", "output": ""},
                },
            },
        },
    },
}


# ── Journal ───────────────────────────────────────────────────────────────────
def _append_journal(
    st_name: str, task_name: str, branch_name: str,
    description: str, output: str, step: int,
) -> None:
    """Append one verified Claude result to journal.md."""
    exists = os.path.exists(JOURNAL_PATH)
    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        if not exists:
            f.write("# Solo Builder — Live Journal\n\n")
        f.write(f"## {st_name} · {task_name} / {branch_name} · Step {step}\n\n")
        if description:
            f.write(f"**Prompt:** {description}\n\n")
        f.write(f"{output}\n\n---\n\n")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT: Planner
# ═══════════════════════════════════════════════════════════════════════════════
class Planner:
    """Prioritizes subtasks by computed risk score. Higher = more urgent."""

    def __init__(self, stall_threshold: int) -> None:
        self.stall_threshold = stall_threshold
        # Meta-optimizer adjustable weights
        self.w_stall    = 1.0
        self.w_staleness = 1.0
        self.w_shadow   = 1.0

    # ── Public ──────────────────────────────────────────────────────────────
    def prioritize(
        self, dag: Dict, step: int
    ) -> List[Tuple[str, str, str, int]]:
        """
        Return a sorted list of (task, branch, subtask, risk_score) for all
        non-Verified subtasks, highest risk first.
        """
        candidates: List[Tuple[str, str, str, int]] = []
        for task_name, task_data in dag.items():
            if not self._deps_met(dag, task_name):
                continue
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    if st_data.get("status") not in ("Pending", "Running"):
                        continue
                    risk = self._risk(st_data, step)
                    candidates.append((task_name, branch_name, st_name, risk))
        candidates.sort(key=lambda x: x[3], reverse=True)
        return candidates

    def _deps_met(self, dag: Dict, task_name: str) -> bool:
        """Return True if every task this task depends on is Verified."""
        for dep in dag.get(task_name, {}).get("depends_on", []):
            if dag.get(dep, {}).get("status") != "Verified":
                return False
        return True

    def adjust_weights(self, key: str, delta: float) -> None:
        """Hook for MetaOptimizer to tune heuristic weights."""
        if key == "stall_risk":
            self.w_stall    = max(0.1, self.w_stall    + delta)
        elif key == "staleness":
            self.w_staleness = max(0.1, self.w_staleness + delta)
        elif key == "shadow":
            self.w_shadow   = max(0.1, self.w_shadow   + delta)

    # ── Private ─────────────────────────────────────────────────────────────
    def _risk(self, st_data: Dict, step: int) -> int:
        staleness = step - st_data.get("last_update", 0)
        status    = st_data.get("status", "Pending")

        if status == "Running":
            # Base of 1000 guarantees Running always outranks Pending regardless
            # of how long Pending subtasks have been waiting.
            risk = int(1000 * self.w_stall)
            if staleness >= self.stall_threshold:
                # Extra urgency for stalled — bump above normal Running
                risk += int(500 * self.w_stall) + staleness * 20
            else:
                risk += int(staleness * 10 * self.w_staleness)
        elif status == "Pending":
            risk = int(staleness * 8 * self.w_staleness) if staleness > 2 else 0
            if st_data.get("shadow") == "Done":
                # Shadow claims Done but status is Pending → extra urgency
                risk += int(50 * self.w_shadow)
        else:
            risk = 0

        return risk


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════
class ClaudeRunner:
    """Calls `claude -p` headlessly and returns (success, output_text).

    Tools:
      allowed_tools  — comma-separated default tool list (e.g. "Read,Glob,Grep")
                        "" means no tools (pure headless, fastest)
      Per-call tools override via run(..., tools="Bash,Write")
    """

    def __init__(self, timeout: int = 60, allowed_tools: str = "") -> None:
        self.timeout       = timeout
        self.allowed_tools = allowed_tools
        self.available     = self._check()

    def _check(self) -> bool:
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def run(self, description: str, st_name: str, tools: str = "") -> tuple:
        """Returns (success: bool, output: str).

        tools — comma-separated list overriding self.allowed_tools for this call.
                Falls back to self.allowed_tools if empty.
        """
        if not self.available:
            return False, "claude CLI not found"
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        effective_tools = (tools or self.allowed_tools).strip()
        cmd = ["claude", "-p", description, "--output-format", "json"]
        if effective_tools:
            cmd += ["--allowedTools"] + [t.strip() for t in effective_tools.split(",") if t.strip()]

        try:
            r = subprocess.run(
                cmd,
                capture_output=True, text=True,
                encoding="utf-8", timeout=self.timeout,
                env=env,
            )
            if r.returncode != 0:
                return False, (r.stderr or "non-zero exit").strip()[:200]
            data = json.loads(r.stdout)
            output = data.get("result", r.stdout).strip()
            return True, output
        except subprocess.TimeoutExpired:
            return False, f"Timed out after {self.timeout}s"
        except json.JSONDecodeError:
            out = r.stdout.strip()
            return (True, out) if out else (False, "empty response")
        except Exception as exc:
            return False, str(exc)[:200]


class AnthropicRunner:
    """Calls the Anthropic SDK directly — no subprocess, no CLI required.

    Activated when ANTHROPIC_API_KEY is set in the environment.
    Used for Running subtasks that have no tools requirement.
    Falls back gracefully if the SDK is not installed or key is absent.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 300) -> None:
        self.model      = model
        self.max_tokens = max_tokens
        self.client     = None
        self.available  = self._init()

    def _init(self) -> bool:
        try:
            import anthropic                        # noqa: PLC0415
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                return False
            self.client = anthropic.Anthropic(api_key=key)
            return True
        except ImportError:
            return False

    def run(self, prompt: str) -> tuple:
        """Returns (success: bool, output: str)."""
        if not self.available:
            return False, "Anthropic SDK unavailable"
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return True, msg.content[0].text.strip()
        except Exception as exc:
            return False, str(exc)[:200]


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT: Executor
# ═══════════════════════════════════════════════════════════════════════════════
class Executor:
    """Advances subtasks through Pending → Running → Verified."""

    def __init__(self, max_per_step: int, verify_prob: float) -> None:
        self.max_per_step = max_per_step
        self.verify_prob  = verify_prob
        self.claude       = ClaudeRunner(timeout=CLAUDE_TIMEOUT, allowed_tools=CLAUDE_ALLOWED_TOOLS)
        self.anthropic    = AnthropicRunner(model=ANTHROPIC_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS)

    def execute_step(
        self,
        dag: Dict,
        priority_list: List[Tuple[str, str, str, int]],
        step: int,
        memory_store: Dict,
    ) -> Dict[str, str]:
        """
        Advance up to max_per_step subtasks.
        Returns {subtask_name: action} where action ∈ {"started", "verified"}.
        """
        actions: Dict[str, str] = {}
        advanced = 0
        claude_jobs: list = []
        sdk_jobs:    list = []

        for task_name, branch_name, st_name, _ in priority_list:
            if advanced >= self.max_per_step:
                break

            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            status  = st_data.get("status", "Pending")

            if status == "Pending":
                st_data["status"]      = "Running"
                st_data["last_update"] = step
                dag[task_name]["status"]                              = "Running"
                dag[task_name]["branches"][branch_name]["status"]     = "Running"
                add_memory_snapshot(memory_store, branch_name, f"{st_name}_started", step)
                actions[st_name] = "started"
                advanced += 1

            elif status == "Running":
                st_tools    = st_data.get("tools", "").strip()
                description = st_data.get("description", "").strip()
                if st_tools and self.claude.available:
                    # Has tools — must use subprocess Claude (needs --allowedTools)
                    claude_jobs.append((task_name, branch_name, st_name, st_data, st_tools))
                    advanced += 1
                elif self.anthropic.available:
                    # No tools — use SDK directly (faster, no subprocess)
                    auto_prompt = (
                        description
                        or f"You completed subtask '{st_name}' in task '{task_name}'. "
                           f"Write one concrete sentence describing what was accomplished."
                    )
                    sdk_jobs.append((task_name, branch_name, st_name, st_data, auto_prompt))
                    advanced += 1
                elif random.random() < self.verify_prob:
                        st_data["status"]      = "Verified"
                        st_data["shadow"]      = "Done"
                        st_data["last_update"] = step
                        add_memory_snapshot(memory_store, branch_name, f"{st_name}_verified", step)
                        actions[st_name] = "verified"
                        advanced += 1
                        self._roll_up(dag, task_name, branch_name)

        # ── Run Claude jobs in parallel ───────────────────────────────────────
        if claude_jobs:
            names = ", ".join(j[2] for j in claude_jobs)
            print(f"  {CYAN}Claude executing {names}…{RESET}", flush=True)
            with ThreadPoolExecutor(max_workers=len(claude_jobs)) as pool:
                futures = {
                    pool.submit(self.claude.run, st_data.get("description", ""), st_name,
                                st_tools): (task_name, branch_name, st_name, st_data)
                    for task_name, branch_name, st_name, st_data, st_tools in claude_jobs
                }
                for future in as_completed(futures):
                    task_name, branch_name, st_name, st_data = futures[future]
                    success, output = future.result()
                    if success:
                        st_data["status"]      = "Verified"
                        st_data["shadow"]      = "Done"
                        st_data["output"]      = output
                        st_data["last_update"] = step
                        add_memory_snapshot(memory_store, branch_name, f"{st_name}_claude_verified", step)
                        actions[st_name] = "verified"
                        self._roll_up(dag, task_name, branch_name)
                        _append_journal(
                            st_name, task_name, branch_name,
                            st_data.get("description", ""), output, step,
                        )
                    # On failure: stay Running → will retry next step or self-heal

        # ── SDK jobs (Anthropic API, no subprocess) ───────────────────────────
        if sdk_jobs:
            names = ", ".join(j[2] for j in sdk_jobs)
            print(f"  {BLUE}SDK executing {names}…{RESET}", flush=True)
            with ThreadPoolExecutor(max_workers=len(sdk_jobs)) as pool:
                futures = {
                    pool.submit(self.anthropic.run, prompt):
                        (task_name, branch_name, st_name, st_data)
                    for task_name, branch_name, st_name, st_data, prompt in sdk_jobs
                }
                for future in as_completed(futures):
                    task_name, branch_name, st_name, st_data = futures[future]
                    success, output = future.result()
                    if success:
                        st_data["status"]      = "Verified"
                        st_data["shadow"]      = "Done"
                        st_data["output"]      = output[:400]
                        st_data["last_update"] = step
                        add_memory_snapshot(memory_store, branch_name,
                                            f"{st_name}_sdk_verified", step)
                        actions[st_name] = "verified"
                        self._roll_up(dag, task_name, branch_name)
                    else:
                        # SDK failed — dice-roll so pipeline isn't blocked
                        if random.random() < self.verify_prob:
                            st_data["status"]      = "Verified"
                            st_data["shadow"]      = "Done"
                            st_data["last_update"] = step
                            add_memory_snapshot(memory_store, branch_name,
                                                f"{st_name}_verified", step)
                            actions[st_name] = "verified"
                            self._roll_up(dag, task_name, branch_name)

        return actions

    # ── Roll-up helpers ──────────────────────────────────────────────────────
    def _roll_up(self, dag: Dict, task_name: str, branch_name: str) -> None:
        self._update_branch(dag, task_name, branch_name)
        self._update_task(dag, task_name)

    def _update_branch(self, dag: Dict, task_name: str, branch_name: str) -> None:
        sts = dag[task_name]["branches"][branch_name]["subtasks"]
        if all(s.get("status") == "Verified" for s in sts.values()):
            dag[task_name]["branches"][branch_name]["status"] = "Verified"

    def _update_task(self, dag: Dict, task_name: str) -> None:
        branches = dag[task_name]["branches"]
        if all(b.get("status") == "Verified" for b in branches.values()):
            dag[task_name]["status"] = "Verified"
        elif any(b.get("status") == "Running" for b in branches.values()):
            dag[task_name]["status"] = "Running"


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT: ShadowAgent
# ═══════════════════════════════════════════════════════════════════════════════
class ShadowAgent:
    """
    Maintains an expected-state map and detects shadow/status conflicts.
    Conflict: shadow == "Done" but status != "Verified"  (or vice versa).
    """

    def __init__(self) -> None:
        self.expected: Dict[str, str] = {}   # st_name → expected status

    def update_expected(self, dag: Dict) -> None:
        """Rebuild expected state from current DAG."""
        for task_data in dag.values():
            for branch_data in task_data.get("branches", {}).values():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    self.expected[st_name] = st_data.get("status", "Pending")

    def detect_conflicts(self, dag: Dict) -> List[Tuple[str, str, str]]:
        """
        Return list of (task, branch, subtask) where shadow/status are inconsistent.
        """
        conflicts: List[Tuple[str, str, str]] = []
        for task_name, task_data in dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    shadow = st_data.get("shadow", "Pending")
                    status = st_data.get("status", "Pending")
                    # shadow Done but not Verified → stale shadow
                    if shadow == "Done" and status != "Verified":
                        conflicts.append((task_name, branch_name, st_name))
                    # Verified but shadow still Pending → shadow lag (non-critical but fixable)
                    elif status == "Verified" and shadow == "Pending":
                        conflicts.append((task_name, branch_name, st_name))
        return conflicts

    def resolve_conflict(
        self,
        dag: Dict,
        task_name: str,
        branch_name: str,
        st_name: str,
        step: int,
        memory_store: Dict,
    ) -> None:
        """Auto-resolve by aligning shadow with actual status."""
        st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
        status  = st_data.get("status", "Pending")
        if status == "Verified":
            st_data["shadow"] = "Done"
        else:
            st_data["shadow"] = "Pending"
        add_memory_snapshot(memory_store, branch_name, f"{st_name}_conflict_resolved", step)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT: Verifier
# ═══════════════════════════════════════════════════════════════════════════════
class Verifier:
    """Enforces DAG invariants: branch/task statuses must reflect subtask states."""

    def verify(self, dag: Dict) -> List[str]:
        """
        Scan all branch and task statuses; correct any inconsistencies.
        Returns list of correction messages.
        """
        fixes: List[str] = []
        for task_name, task_data in dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                sts              = branch_data.get("subtasks", {})
                all_v            = all(s.get("status") == "Verified" for s in sts.values())
                any_r            = any(s.get("status") == "Running"  for s in sts.values())
                cur_branch_status = branch_data.get("status", "Pending")

                if all_v and cur_branch_status != "Verified":
                    branch_data["status"] = "Verified"
                    fixes.append(f"Branch {branch_name}: Pending/Running → Verified")
                elif any_r and cur_branch_status == "Pending":
                    branch_data["status"] = "Running"
                    fixes.append(f"Branch {branch_name}: Pending → Running")

            branches = task_data.get("branches", {})
            all_bv   = all(b.get("status") == "Verified" for b in branches.values())
            any_br   = any(b.get("status") == "Running"  for b in branches.values())
            cur_t    = task_data.get("status", "Pending")

            if all_bv and cur_t != "Verified":
                task_data["status"] = "Verified"
                fixes.append(f"Task {task_name}: → Verified")
            elif any_br and cur_t == "Pending":
                task_data["status"] = "Running"
                fixes.append(f"Task {task_name}: → Running")

        return fixes


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT: SelfHealer
# ═══════════════════════════════════════════════════════════════════════════════
class SelfHealer:
    """Detects subtasks stalled in Running state and resets them to Pending."""

    def __init__(self, stall_threshold: int) -> None:
        self.stall_threshold = stall_threshold
        self.healed_total    = 0

    def find_stalled(
        self, dag: Dict, step: int
    ) -> List[Tuple[str, str, str, int]]:
        """Return list of (task, branch, subtask, staleness) for stalled subtasks."""
        stalled: List[Tuple[str, str, str, int]] = []
        for task_name, task_data in dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    if st_data.get("status") == "Running":
                        age = step - st_data.get("last_update", 0)
                        if age >= self.stall_threshold:
                            stalled.append((task_name, branch_name, st_name, age))
        return stalled

    def heal(
        self,
        dag: Dict,
        stalled: List[Tuple[str, str, str, int]],
        step: int,
        memory_store: Dict,
        alerts: List[str],
    ) -> int:
        """Reset stalled subtasks. Returns count healed."""
        count = 0
        for task_name, branch_name, st_name, age in stalled:
            st_data = dag[task_name]["branches"][branch_name]["subtasks"][st_name]
            st_data["status"]      = "Pending"
            st_data["shadow"]      = "Pending"
            st_data["last_update"] = step
            add_memory_snapshot(memory_store, branch_name, f"{st_name}_healed", step)
            alerts.append(
                f"  {ALERT_PREDICTIVE} {CYAN}{st_name}{RESET} "
                f"reset after {age} steps stalled"
            )
            count          += 1
            self.healed_total += 1
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT: MetaOptimizer
# ═══════════════════════════════════════════════════════════════════════════════
class MetaOptimizer:
    """
    Records per-step metrics and adapts Planner weights.
    Also generates completion forecasts.
    """

    def __init__(self) -> None:
        self._history: List[Dict[str, int]] = []
        self.heal_rate   = 0.0
        self.verify_rate = 0.0

    def record(self, healed: int, verified: int) -> None:
        self._history.append({"healed": healed, "verified": verified})
        window = min(10, len(self._history))
        recent = self._history[-window:]
        self.heal_rate   = sum(r["healed"]   for r in recent) / window
        self.verify_rate = sum(r["verified"] for r in recent) / window

    def optimize(self, planner: Planner) -> Optional[str]:
        """Return an optimisation note if any weight was adjusted."""
        if len(self._history) < 5:
            return None
        if self.heal_rate > 0.5:
            planner.adjust_weights("stall_risk", 0.1)
            return (f"Meta-Opt: ↑ stall_risk weight "
                    f"(heal_rate={self.heal_rate:.2f})")
        if self.verify_rate < 0.2:
            planner.adjust_weights("staleness", 0.1)
            return (f"Meta-Opt: ↑ staleness weight "
                    f"(verify_rate={self.verify_rate:.2f})")
        return None

    def forecast(self, dag: Dict) -> str:
        """Simple linear-extrapolation forecast for completion."""
        total = verified = 0
        for task_data in dag.values():
            for branch_data in task_data.get("branches", {}).values():
                for st_data in branch_data.get("subtasks", {}).values():
                    total    += 1
                    if st_data.get("status") == "Verified":
                        verified += 1
        if total == 0:
            return "N/A"
        if verified == total:
            return f"{GREEN}COMPLETE{RESET}"
        pct = verified / total * 100
        if self.verify_rate > 0:
            remaining     = total - verified
            eta           = remaining / (self.verify_rate + 1e-6)
            return f"~{eta:.0f} steps  ({pct:.0f}% done)"
        return f"{pct:.0f}% done  (ETA unavailable)"


# ═══════════════════════════════════════════════════════════════════════════════
# TERMINAL DISPLAY
# ═══════════════════════════════════════════════════════════════════════════════
class TerminalDisplay:
    """Renders the full-screen terminal mini-graph."""

    _WIDTH = 72

    def __init__(self, bar_width: int = BAR_WIDTH, stall_threshold: int = STALL_THRESHOLD) -> None:
        self.bar_width       = bar_width
        self.stall_threshold = stall_threshold

    # ── Main render ─────────────────────────────────────────────────────────
    def render(
        self,
        dag: Dict,
        memory_store: Dict,
        step: int,
        alerts: List[str],
        forecast: str,
    ) -> None:
        print("\033[2J\033[H", end="")   # clear screen + home cursor
        self._header(step, forecast)
        self._dag_section(dag, memory_store, step)
        self._alerts_section(alerts)
        self._footer(dag)

    # ── Sections ────────────────────────────────────────────────────────────
    def _header(self, step: int, forecast: str) -> None:
        W = self._WIDTH
        print(f"{BOLD}{CYAN}{'═' * W}{RESET}")
        print(
            f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI"
            f"  │  Step: {YELLOW}{step}{CYAN}"
            f"  │  ETA: {forecast}{RESET}"
        )
        print(f"{CYAN}{'═' * W}{RESET}")

    def _dag_section(self, dag: Dict, memory_store: Dict, step: int) -> None:
        for task_name, task_data in dag.items():
            t_status = task_data.get("status", "Pending")
            t_color  = STATUS_COLORS.get(t_status, WHITE)
            blocked_by = [
                dep for dep in task_data.get("depends_on", [])
                if dag.get(dep, {}).get("status") != "Verified"
            ]
            block_tag = (
                f"  {DIM}[blocked → {', '.join(blocked_by)}]{RESET}"
                if blocked_by else ""
            )
            print(
                f"\n  {BOLD}{t_color}▶ {task_name}{RESET}"
                f"  [{format_status(t_status)}]{block_tag}"
            )
            for branch_name, branch_data in task_data.get("branches", {}).items():
                self._branch_row(branch_name, branch_data, memory_store, step)
            print()

    def _branch_row(
        self,
        branch_name: str,
        branch_data: Dict,
        memory_store: Dict,
        step: int,
    ) -> None:
        subtasks = branch_data.get("subtasks", {})
        total    = len(subtasks)
        verified, running, _ = branch_stats(branch_data)
        shadow_done, _       = shadow_stats(branch_data)
        mem_cnt              = memory_depth(memory_store, branch_name)

        prog_bar   = self._bar(verified,    total,     "=", "-")
        shadow_bar = self._bar(shadow_done, total,     "!", " ")
        mem_bar    = self._bar(min(mem_cnt, total * 3), total * 3, "#", " ")

        b_status = branch_data.get("status", "Pending")
        b_color  = STATUS_COLORS.get(b_status, WHITE)

        print(f"    {b_color}├─ {branch_name}{RESET} [{format_status(b_status)}]")
        print(f"    │  Progress [{GREEN}{prog_bar}{RESET}] {verified}/{total}")
        print(f"    │  Shadow   [{MAGENTA}{shadow_bar}{RESET}] {shadow_done}/{total}")
        print(f"    │  Memory   [{BLUE}{mem_bar}{RESET}] {mem_cnt} snapshots")

        for st_name, st_data in subtasks.items():
            self._subtask_row(st_name, st_data, step)

        print(f"    │")

    def _subtask_row(self, st_name: str, st_data: Dict, step: int) -> None:
        status    = st_data.get("status", "Pending")
        shadow    = st_data.get("shadow", "Pending")
        age       = step - st_data.get("last_update", 0)
        st_color  = STATUS_COLORS.get(status, WHITE)

        stall_tag = ""
        if status == "Running" and age >= self.stall_threshold:
            stall_tag = f" {ALERT_STALLED}"

        print(
            f"    │    {st_color}◦ {st_name:<4}{RESET}"
            f"  {format_status(status):<20}"
            f"  shadow={format_shadow(shadow):<15}"
            f"  age={age}"
            f"{stall_tag}"
        )
        output = st_data.get("output", "")
        if output and status == "Verified":
            preview = output[:65].replace("\n", " ")
            print(f"    │      {DIM}↳ {preview}…{RESET}")

    def _alerts_section(self, alerts: List[str]) -> None:
        if not alerts:
            return
        print(f"  {BOLD}{YELLOW}{'─' * 10} ALERTS {'─' * 10}{RESET}")
        for alert in alerts[-5:]:
            print(alert)

    def _footer(self, dag: Dict) -> None:
        stats    = dag_stats(dag)
        total    = stats["total"]
        verified = stats["verified"]
        running  = stats["running"]
        pending  = stats["pending"]
        pct      = verified / total * 100 if total else 0

        overall = self._bar(verified, total, "=", "-", width=32)
        print(f"\n  {CYAN}{'─' * self._WIDTH}{RESET}")
        print(
            f"  Overall [{GREEN}{overall}{RESET}] "
            f"{GREEN}{verified}✓{RESET} "
            f"{CYAN}{running}▶{RESET} "
            f"{YELLOW}{pending}●{RESET} "
            f"/ {total}  ({pct:.1f}%)"
        )
        print(f"\n  {DIM}Commands: run │ auto [N] │ add_task │ add_branch │ depends │ describe │ verify │ tools │ output │ export │ snapshot │ save │ load │ reset │ help │ exit{RESET}")
        print(f"  {CYAN}{'═' * self._WIDTH}{RESET}")

    # ── Bar helper ──────────────────────────────────────────────────────────
    def _bar(self, filled: int, total: int, ch: str, emp: str,
             width: int = None) -> str:
        return make_bar(filled, total, ch, emp, width or self.bar_width)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLI ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════
class SoloBuilderCLI:
    """
    Orchestrates all agents and handles the interactive CLI loop.

    Step lifecycle:
        Planner → ShadowAgent (conflicts) → SelfHealer → Executor
        → Verifier → ShadowAgent (update expected) → MetaOptimizer → display
    """

    def __init__(self) -> None:
        self.dag          = copy.deepcopy(INITIAL_DAG)
        self.memory_store = {
            branch: []
            for task_data in self.dag.values()
            for branch in task_data.get("branches", {})
        }
        self.step             = 0
        self.snapshot_counter = 0
        self.alerts: List[str] = []

        # Agents
        self.planner  = Planner(stall_threshold=STALL_THRESHOLD)
        self.executor = Executor(max_per_step=EXEC_MAX_PER_STEP,
                                 verify_prob=EXEC_VERIFY_PROB)
        self.shadow   = ShadowAgent()
        self.verifier = Verifier()
        self.healer   = SelfHealer(stall_threshold=STALL_THRESHOLD)
        self.meta     = MetaOptimizer()
        self.display  = TerminalDisplay(bar_width=BAR_WIDTH,
                                        stall_threshold=STALL_THRESHOLD)
        self.running  = True

        os.makedirs(PDF_OUTPUT_PATH, exist_ok=True)

        # Validate initial DAG
        warnings = validate_dag(self.dag)
        for w in warnings:
            print(f"{YELLOW}[DAG Warning] {w}{RESET}")

    # ── Step ────────────────────────────────────────────────────────────────
    def run_step(self) -> None:
        """Execute one full agent pipeline step."""
        self.step += 1
        step_alerts: List[str] = []

        # 1. Planner: prioritize
        priority = self.planner.prioritize(self.dag, self.step)

        # 2. ShadowAgent: detect and resolve conflicts
        conflicts = self.shadow.detect_conflicts(self.dag)
        for task_name, branch_name, st_name in conflicts:
            step_alerts.append(
                f"  {ALERT_CONFLICT} {CYAN}{st_name}{RESET}: "
                f"shadow/status mismatch → resolving"
            )
            self.shadow.resolve_conflict(
                self.dag, task_name, branch_name, st_name,
                self.step, self.memory_store,
            )

        # 3. SelfHealer: detect stalls (alert before healing)
        stalled = self.healer.find_stalled(self.dag, self.step)
        for _, _, st_name, age in stalled:
            step_alerts.append(
                f"  {ALERT_STALLED} {CYAN}{st_name}{RESET} stalled {age} steps"
            )
        healed = self.healer.heal(
            self.dag, stalled, self.step, self.memory_store, step_alerts
        )

        # 4. Executor: advance subtasks
        actions = self.executor.execute_step(
            self.dag, priority, self.step, self.memory_store
        )

        # 5. Verifier: fix any status inconsistencies
        fixes = self.verifier.verify(self.dag)
        if VERBOSITY == "DEBUG":
            for fix in fixes:
                step_alerts.append(f"  {DIM}Verifier: {fix}{RESET}")

        # 6. ShadowAgent: update expected state map
        self.shadow.update_expected(self.dag)

        # 7. MetaOptimizer: record + maybe adjust weights
        verified_count = sum(1 for a in actions.values() if a == "verified")
        self.meta.record(healed, verified_count)
        opt_note = self.meta.optimize(self.planner)
        if opt_note and VERBOSITY == "DEBUG":
            step_alerts.append(f"  {DIM}{opt_note}{RESET}")

        # 8. Auto-snapshot
        if self.step % SNAPSHOT_INTERVAL == 0:
            self._take_snapshot(auto=True)

        # 9. Auto-save state
        if self.step % AUTO_SAVE_INTERVAL == 0:
            self.save_state(silent=True)

        # Accumulate alerts
        self.alerts = (self.alerts + step_alerts)[-MAX_ALERTS:]

        # Render
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    # ── Snapshot ────────────────────────────────────────────────────────────
    def _take_snapshot(self, auto: bool = False) -> None:
        if not _PDF_OK:
            print(f"{YELLOW}PDF unavailable — install matplotlib.{RESET}")
            return
        self.snapshot_counter += 1
        fname = os.path.join(
            PDF_OUTPUT_PATH,
            f"Solo_Builder_Timeline_{self.snapshot_counter:04d}.pdf",
        )
        try:
            generate_live_multi_pdf(self.dag, self.memory_store, fname)
            tag = "AUTO" if auto else "MANUAL"
            print(f"  {GREEN}[{tag}] Snapshot → {fname}{RESET}")
        except Exception as exc:
            print(f"  {RED}Snapshot failed: {exc}{RESET}")

    # ── Persistence ──────────────────────────────────────────────────────────
    def save_state(self, silent: bool = False) -> None:
        """Serialize full runtime state to JSON on disk."""
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        payload = {
            "step":             self.step,
            "snapshot_counter": self.snapshot_counter,
            "healed_total":     self.healer.healed_total,
            "dag":              self.dag,
            "memory_store":     self.memory_store,
            "alerts":           self.alerts,
            "meta_history":     self.meta._history,
        }
        try:
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            if not silent:
                print(f"  {GREEN}State saved → {STATE_PATH}{RESET}")
        except Exception as exc:
            print(f"  {RED}Save failed: {exc}{RESET}")

    def load_state(self) -> bool:
        """
        Load state from disk into this instance.
        Returns True if loaded successfully, False otherwise.
        """
        if not os.path.exists(STATE_PATH):
            return False
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.step             = payload["step"]
            self.snapshot_counter = payload["snapshot_counter"]
            self.healer.healed_total = payload["healed_total"]
            self.dag              = payload["dag"]
            self.memory_store     = payload["memory_store"]
            self.alerts           = payload["alerts"]
            self.meta._history    = payload.get("meta_history", [])
            # Rebuild MetaOptimizer rolling rates
            if self.meta._history:
                window = min(10, len(self.meta._history))
                recent = self.meta._history[-window:]
                self.meta.heal_rate   = sum(r["healed"]   for r in recent) / window
                self.meta.verify_rate = sum(r["verified"] for r in recent) / window
            # Rebuild ShadowAgent expected state map
            self.shadow.update_expected(self.dag)
            return True
        except Exception as exc:
            print(f"  {RED}Load failed: {exc}{RESET}")
            return False

    # ── Auto-run ─────────────────────────────────────────────────────────────
    def _cmd_auto(self, args: str) -> None:
        """
        auto [N] — run N steps automatically (default: until COMPLETE).
        Speed controlled by AUTO_STEP_DELAY seconds between steps.
        Press Ctrl+C to pause.
        """
        global AUTO_STEP_DELAY
        try:
            limit = int(args.strip()) if args.strip() else None
        except ValueError:
            print(f"  {YELLOW}Usage: auto [N]  (N = number of steps){RESET}")
            return

        stats = dag_stats(self.dag)
        if stats["verified"] == stats["total"]:
            print(f"  {GREEN}DAG already complete. Reset with 'reset' or add tasks.{RESET}")
            time.sleep(1)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )
            return

        ran    = 0
        label  = f"{limit} steps" if limit else "until complete"
        print(f"  {CYAN}Auto-run: {label}  │  delay={AUTO_STEP_DELAY}s  │  Ctrl+C to pause{RESET}")
        time.sleep(0.6)

        _trigger = os.path.join(_HERE, "state", "run_trigger")
        try:
            while True:
                self.run_step()
                ran += 1

                stats = dag_stats(self.dag)
                if stats["verified"] == stats["total"]:
                    # Brief pause so the 100% screen is visible
                    time.sleep(1.2)
                    break

                if limit is not None and ran >= limit:
                    break

                # Honour external trigger (from dashboard Run Step button)
                _waited = 0.0
                while _waited < AUTO_STEP_DELAY:
                    if os.path.exists(_trigger):
                        try:
                            os.remove(_trigger)
                        except OSError:
                            pass
                        break
                    time.sleep(0.05)
                    _waited += 0.05

        except KeyboardInterrupt:
            print(f"\n  {YELLOW}Auto-run paused at step {self.step}.{RESET}")
            time.sleep(0.5)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

    # ── Command dispatcher ───────────────────────────────────────────────────
    def handle_command(self, raw: str) -> None:
        raw = raw.strip()
        cmd = raw.lower()

        if cmd == "run":
            self.run_step()

        elif cmd.startswith("auto"):
            self._cmd_auto(cmd[4:])

        elif cmd == "snapshot":
            self._take_snapshot(auto=False)
            input(f"  {DIM}Press Enter to continue…{RESET}")
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

        elif cmd == "save":
            self.save_state()
            time.sleep(0.6)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

        elif cmd == "load":
            ok = self.load_state()
            if ok:
                print(f"  {GREEN}State loaded — step {self.step}, "
                      f"{dag_stats(self.dag)['verified']} verified.{RESET}")
                time.sleep(0.8)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

        elif cmd == "reset":
            self._cmd_reset()

        elif cmd == "status":
            self._cmd_status()

        elif cmd == "add_task":
            self._cmd_add_task()

        elif cmd.startswith("add_branch"):
            self._cmd_add_branch(raw[10:])

        elif cmd == "prioritize_branch":
            self._cmd_prioritize_branch()

        elif cmd == "export":
            self._cmd_export()

        elif cmd == "depends":
            self._cmd_depends("")

        elif cmd.startswith("depends "):
            self._cmd_depends(raw[8:])

        elif cmd.startswith("undepends "):
            self._cmd_undepends(raw[10:])

        elif cmd.startswith("describe "):
            self._cmd_describe(raw[9:])

        elif cmd.startswith("verify "):
            self._cmd_verify(raw[7:])

        elif cmd.startswith("tools "):
            self._cmd_tools(raw[6:])

        elif cmd.startswith("output "):
            self._cmd_output(raw[7:])

        elif cmd.startswith("set "):
            self._cmd_set(raw[4:])

        elif cmd == "help":
            self._cmd_help()

        elif cmd == "exit":
            self.save_state(silent=True)
            print(f"\n{CYAN}Solo Builder shutting down. "
                  f"Steps: {self.step}  │  Healed: {self.healer.healed_total}  "
                  f"│  State saved.{RESET}\n")
            self.running = False

        elif cmd == "":
            pass   # empty enter → redraw

        else:
            print(f"  {YELLOW}Unknown command '{cmd}'. "
                  f"Type 'help' for options.{RESET}")
            time.sleep(0.8)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )

    # ── Sub-commands ─────────────────────────────────────────────────────────
    def _cmd_status(self) -> None:
        stats    = dag_stats(self.dag)
        forecast = self.meta.forecast(self.dag)
        total_snaps = sum(len(v) for v in self.memory_store.values())
        print(f"\n  {BOLD}DAG Statistics{RESET}")
        print(f"    Total subtasks : {stats['total']}")
        print(f"    Verified       : {GREEN}{stats['verified']}{RESET}")
        print(f"    Running        : {CYAN}{stats['running']}{RESET}")
        print(f"    Pending        : {YELLOW}{stats['pending']}{RESET}")
        print(f"    Healed (total) : {self.healer.healed_total}")
        print(f"    Memory snaps   : {total_snaps}")
        print(f"    Forecast       : {forecast}")
        print(f"    Verify rate    : {self.meta.verify_rate:.2f}/step")
        print(f"    Heal rate      : {self.meta.heal_rate:.2f}/step")
        input(f"\n  {DIM}Press Enter…{RESET}")
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, forecast,
        )

    def _cmd_reset(self) -> None:
        """Reset the DAG back to the initial state and delete the save file."""
        self.dag          = copy.deepcopy(INITIAL_DAG)
        self.memory_store = {
            branch: []
            for task_data in self.dag.values()
            for branch in task_data.get("branches", {})
        }
        self.step             = 0
        self.snapshot_counter = 0
        self.alerts           = []
        self.healer.healed_total = 0
        self.meta._history    = []
        self.meta.heal_rate   = 0.0
        self.meta.verify_rate = 0.0
        self.shadow.expected  = {}
        if os.path.exists(STATE_PATH):
            os.remove(STATE_PATH)
        print(f"  {YELLOW}DAG reset to initial state. Save file cleared.{RESET}")
        time.sleep(0.6)
        self.display.render(
            self.dag, self.memory_store, self.step, self.alerts, "N/A"
        )

    def _cmd_add_task(self) -> None:
        task_idx  = len(self.dag)
        task_name = f"Task {task_idx}"
        if task_name in self.dag:
            print(f"  {YELLOW}{task_name} already exists.{RESET}")
            return

        letter      = chr(ord("A") + task_idx % 26)
        branch_name = f"Branch {letter}"

        spec = input(f"  {BOLD}What should {task_name} accomplish?{RESET} ").strip()
        if not spec:
            print(f"  {YELLOW}Cancelled — description cannot be empty.{RESET}")
            return

        # Try Claude decomposition into subtasks
        subtasks: dict = {}
        if self.executor.claude.available:
            print(f"  {CYAN}Claude decomposing into subtasks…{RESET}", flush=True)
            decomp_prompt = (
                f"Break this task into 2-5 concrete subtasks for a solo developer AI project.\n\n"
                f"Task: {spec}\n\n"
                f"Reply with a JSON array only — no explanation, no markdown fences:\n"
                f'[{{"name": "{letter}1", "description": "actionable prompt"}}, ...]\n\n'
                f"Rules:\n"
                f"- name: uppercase letter '{letter}' + digit, e.g. {letter}1 {letter}2 {letter}3\n"
                f"- description: a self-contained question or instruction Claude can answer headlessly\n"
                f"- 2 to 5 items"
            )
            success, output = self.executor.claude.run(decomp_prompt, task_name)
            if success:
                import re as _re
                m = _re.search(r'\[.*?\]', output, _re.DOTALL)
                if m:
                    try:
                        items = json.loads(m.group())
                        for item in items[:5]:
                            raw_name = str(item.get("name", "")).upper().strip()
                            # Enforce correct letter prefix
                            if not raw_name.startswith(letter) or not raw_name[1:].isdigit():
                                raw_name = f"{letter}{len(subtasks) + 1}"
                            subtasks[raw_name] = {
                                "status":      "Pending",
                                "shadow":      "Pending",
                                "last_update": self.step,
                                "description": item.get("description", "").strip(),
                                "output":      "",
                            }
                    except (json.JSONDecodeError, Exception):
                        pass

        # Fallback: single subtask with the spec itself
        if not subtasks:
            subtasks[f"{letter}1"] = {
                "status":      "Pending",
                "shadow":      "Pending",
                "last_update": self.step,
                "description": spec,
                "output":      "",
            }

        # Auto-wire: new task depends on the last existing task
        last_task = list(self.dag.keys())[-1] if self.dag else None

        self.dag[task_name] = {
            "status": "Pending",
            "depends_on": [last_task] if last_task else [],
            "branches": {
                branch_name: {
                    "status": "Pending",
                    "subtasks": subtasks,
                }
            },
        }
        if branch_name not in self.memory_store:
            self.memory_store[branch_name] = []

        st_list = list(subtasks.keys())
        print(f"  {GREEN}Added {task_name} → {branch_name} → {', '.join(st_list)}{RESET}")
        time.sleep(0.6)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_add_branch(self, args: str) -> None:
        """add_branch <Task N> — Claude-decompose a spec into a new branch on an existing task."""
        # Normalise task name
        arg = args.strip().strip("'\"")
        if arg.isdigit():
            arg = f"Task {arg}"
        elif arg and arg[0].islower():
            arg = arg.title()
        task_name = arg or ""

        if not task_name or task_name not in self.dag:
            tasks = list(self.dag.keys())
            print(f"  {YELLOW}Usage: add_branch <task>   Available: {tasks}{RESET}")
            return

        # Find next unused branch letter across the whole DAG
        used = set()
        for t in self.dag.values():
            for bname in t.get("branches", {}):
                parts = bname.split()
                if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isupper():
                    used.add(parts[1])
        branch_letter = next(
            (c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in used), "Z"
        )
        branch_name = f"Branch {branch_letter}"

        spec = input(f"  {BOLD}What should {branch_name} of {task_name} cover?{RESET} ").strip()
        if not spec:
            print(f"  {YELLOW}Cancelled.{RESET}")
            return

        subtasks: dict = {}
        if self.executor.claude.available:
            print(f"  {CYAN}Claude decomposing {branch_name}…{RESET}", flush=True)
            decomp_prompt = (
                f"Break this concern into 2-4 concrete subtasks for a solo developer project.\n\n"
                f"Concern: {spec}\n\n"
                f"Reply with a JSON array only — no explanation, no markdown fences:\n"
                f'[{{"name": "{branch_letter}1", "description": "actionable prompt"}}, ...]\n\n'
                f"Rules:\n"
                f"- name: uppercase '{branch_letter}' + digit, e.g. {branch_letter}1 {branch_letter}2\n"
                f"- description: self-contained question or instruction Claude can answer headlessly\n"
                f"- 2 to 4 items"
            )
            success, output = self.executor.claude.run(decomp_prompt, branch_name)
            if success:
                import re as _re
                m = _re.search(r'\[.*?\]', output, _re.DOTALL)
                if m:
                    try:
                        items = json.loads(m.group())
                        for item in items[:4]:
                            raw_name = str(item.get("name", "")).upper().strip()
                            if not raw_name.startswith(branch_letter) or not raw_name[1:].isdigit():
                                raw_name = f"{branch_letter}{len(subtasks) + 1}"
                            subtasks[raw_name] = {
                                "status":      "Pending",
                                "shadow":      "Pending",
                                "last_update": self.step,
                                "description": item.get("description", "").strip(),
                                "output":      "",
                            }
                    except (json.JSONDecodeError, Exception):
                        pass

        if not subtasks:
            subtasks[f"{branch_letter}1"] = {
                "status": "Pending", "shadow": "Pending",
                "last_update": self.step, "description": spec, "output": "",
            }

        self.dag[task_name]["branches"][branch_name] = {
            "status": "Pending",
            "subtasks": subtasks,
        }
        if branch_name not in self.memory_store:
            self.memory_store[branch_name] = []

        # Re-open parent task if it was Verified
        if self.dag[task_name].get("status") == "Verified":
            self.dag[task_name]["status"] = "Running"

        st_list = list(subtasks.keys())
        print(f"  {GREEN}Added {branch_name} → {', '.join(st_list)} to {task_name}{RESET}")
        time.sleep(0.6)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_prioritize_branch(self) -> None:
        """Print available branches (hook for future interactive selection)."""
        branches = [
            (task_name, branch_name)
            for task_name, task_data in self.dag.items()
            for branch_name in task_data.get("branches", {})
        ]
        print(f"\n  {BOLD}Available branches:{RESET}")
        for t, b in branches:
            print(f"    {CYAN}{t}{RESET} / {b}")
        print(f"\n  {DIM}Extend _cmd_prioritize_branch() to select and "
              f"boost priority for a specific branch.{RESET}")
        input(f"  {DIM}Press Enter…{RESET}")
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_set(self, args: str) -> None:
        """set KEY=VALUE — update runtime config."""
        global STALL_THRESHOLD, SNAPSHOT_INTERVAL, VERBOSITY

        parts = args.split("=", 1)
        if len(parts) != 2:
            print(f"  {YELLOW}Usage: set KEY=VALUE{RESET}")
            return

        key, val = parts[0].strip().upper(), parts[1].strip()
        try:
            if key == "STALL_THRESHOLD":
                STALL_THRESHOLD = int(val)
                self.healer.stall_threshold  = STALL_THRESHOLD
                self.planner.stall_threshold = STALL_THRESHOLD
                self.display.stall_threshold = STALL_THRESHOLD
                print(f"  {GREEN}STALL_THRESHOLD = {STALL_THRESHOLD}{RESET}")

            elif key == "SNAPSHOT_INTERVAL":
                SNAPSHOT_INTERVAL = int(val)
                print(f"  {GREEN}SNAPSHOT_INTERVAL = {SNAPSHOT_INTERVAL}{RESET}")

            elif key == "VERBOSITY":
                VERBOSITY = val.upper()
                print(f"  {GREEN}VERBOSITY = {VERBOSITY}{RESET}")

            elif key == "VERIFY_PROB":
                self.executor.verify_prob = float(val)
                print(f"  {GREEN}VERIFY_PROB = {val}{RESET}")

            elif key == "AUTO_STEP_DELAY":
                global AUTO_STEP_DELAY
                AUTO_STEP_DELAY = float(val)
                print(f"  {GREEN}AUTO_STEP_DELAY = {AUTO_STEP_DELAY}s{RESET}")

            elif key == "AUTO_SAVE_INTERVAL":
                global AUTO_SAVE_INTERVAL
                AUTO_SAVE_INTERVAL = int(val)
                print(f"  {GREEN}AUTO_SAVE_INTERVAL = {AUTO_SAVE_INTERVAL}{RESET}")

            elif key == "CLAUDE_ALLOWED_TOOLS":
                global CLAUDE_ALLOWED_TOOLS
                CLAUDE_ALLOWED_TOOLS = val
                self.executor.claude.allowed_tools = val
                label = val if val else "(none — headless)"
                print(f"  {GREEN}CLAUDE_ALLOWED_TOOLS = {label}{RESET}")

            elif key == "ANTHROPIC_MAX_TOKENS":
                self.executor.anthropic.max_tokens = int(val)
                print(f"  {GREEN}ANTHROPIC_MAX_TOKENS = {val}{RESET}")

            elif key == "ANTHROPIC_MODEL":
                self.executor.anthropic.model = val
                print(f"  {GREEN}ANTHROPIC_MODEL = {val}{RESET}")

            elif key == "CLAUDE_SUBPROCESS":
                enabled = val.lower() not in ("0", "off", "false", "no")
                self.executor.claude.available = enabled
                label = "on (subprocess)" if enabled else "off (SDK/dice-roll fallback)"
                print(f"  {GREEN}CLAUDE_SUBPROCESS = {label}{RESET}")

            else:
                print(f"  {YELLOW}Unknown key '{key}'. "
                      f"Valid: STALL_THRESHOLD, SNAPSHOT_INTERVAL, "
                      f"VERBOSITY, VERIFY_PROB, AUTO_STEP_DELAY, AUTO_SAVE_INTERVAL, "
                      f"CLAUDE_ALLOWED_TOOLS, ANTHROPIC_MAX_TOKENS, ANTHROPIC_MODEL, "
                      f"CLAUDE_SUBPROCESS{RESET}")
        except ValueError:
            print(f"  {RED}Invalid value '{val}' for {key}{RESET}")

        time.sleep(0.5)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_export(self) -> None:
        """export — write all Claude outputs to solo_builder_outputs.md"""
        stats = dag_stats(self.dag)
        lines = [
            "# Solo Builder — Claude Outputs\n",
            f"Step: {self.step}  |  Verified: {stats['verified']}/{stats['total']}\n",
            "---\n",
        ]
        count = 0
        for task_name, task_data in self.dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    out = st_data.get("output", "").strip()
                    if not out:
                        continue
                    desc = st_data.get("description", "").strip()
                    lines.append(f"## {st_name} — {task_name} / {branch_name}\n")
                    if desc:
                        lines.append(f"**Prompt:** {desc}\n\n")
                    lines.append(f"{out}\n\n")
                    count += 1
        if count == 0:
            print(f"  {YELLOW}No Claude outputs to export yet.{RESET}")
            return
        path = os.path.join(_HERE, "solo_builder_outputs.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  {GREEN}Exported {count} outputs → {path}{RESET}")

    def _cmd_depends(self, args: str) -> None:
        """depends [<Task N> <Task M>] — add dependency, or print dep graph."""
        parts = args.strip().split(" ", 1)
        if len(parts) < 2:
            # Print dependency tree
            print(f"\n  {BOLD}{CYAN}Dependency Graph{RESET}")
            print(f"  {'─' * 40}")
            for t_name, t_data in self.dag.items():
                deps = t_data.get("depends_on", [])
                t_status = t_data.get("status", "?")
                color = STATUS_COLORS.get(t_status, WHITE)
                blocked = any(
                    self.dag.get(d, {}).get("status") != "Verified"
                    for d in deps
                )
                tag = f"  {DIM}[blocked]{RESET}" if blocked else ""
                dep_str = (
                    f"  {DIM}← {', '.join(deps)}{RESET}" if deps else f"  {DIM}(root){RESET}"
                )
                print(f"  {color}{t_name}{RESET} [{format_status(t_status)}]{dep_str}{tag}")
            print(f"  {'─' * 40}")
            return
        raw_target, raw_dep = parts[0].strip(), parts[1].strip()

        # Accept "Task 3", "task 3", "3" all as valid
        def _normalise(s: str) -> str:
            s = s.strip("'\"")
            if s.isdigit():
                return f"Task {s}"
            return s.title() if s[0].islower() else s

        target = _normalise(raw_target)
        dep    = _normalise(raw_dep)

        if target not in self.dag:
            print(f"  {YELLOW}Task '{target}' not found. Tasks: {list(self.dag)}{RESET}")
            return
        if dep not in self.dag:
            print(f"  {YELLOW}Task '{dep}' not found. Tasks: {list(self.dag)}{RESET}")
            return
        if target == dep:
            print(f"  {YELLOW}A task cannot depend on itself.{RESET}")
            return

        deps = self.dag[target].setdefault("depends_on", [])
        if dep not in deps:
            deps.append(dep)
            print(f"  {GREEN}{target} now depends on {dep}.{RESET}")
        else:
            print(f"  {YELLOW}{target} already depends on {dep}.{RESET}")
        time.sleep(0.4)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_undepends(self, args: str) -> None:
        """undepends <Task N> <Task M> — remove Task M from Task N's depends_on."""
        parts = args.strip().split(" ", 1)
        if len(parts) < 2:
            print(f"  Usage: undepends <task> <dep-to-remove>")
            return
        raw_target, raw_dep = parts[0].strip(), parts[1].strip()

        def _normalise(s: str) -> str:
            s = s.strip("'\"")
            if s.isdigit():
                return f"Task {s}"
            return s.title() if s[0].islower() else s

        target = _normalise(raw_target)
        dep    = _normalise(raw_dep)

        if target not in self.dag:
            print(f"  {YELLOW}Task '{target}' not found.{RESET}")
            return
        deps = self.dag[target].get("depends_on", [])
        if dep not in deps:
            print(f"  {YELLOW}{target} does not depend on {dep}.{RESET}")
            return
        deps.remove(dep)
        print(f"  {GREEN}Removed: {target} no longer depends on {dep}.{RESET}")
        time.sleep(0.4)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _find_subtask(self, st_name: str):
        """Return (task_name, task_data, branch_name, branch_data, st_data) for st_name.

        When multiple tasks share a subtask name (name collision from add_task), the
        LAST match wins — i.e. the most-recently-added task takes priority.
        Returns None if not found.
        """
        match = None
        for task_name, task_data in self.dag.items():
            for branch_name, branch_data in task_data.get("branches", {}).items():
                if st_name in branch_data.get("subtasks", {}):
                    match = (task_name, task_data, branch_name, branch_data,
                             branch_data["subtasks"][st_name])
        return match

    def _cmd_describe(self, args: str) -> None:
        """describe <subtask> <text> — attach a description to any subtask."""
        parts = args.strip().split(" ", 1)
        if len(parts) < 2:
            print(f"  Usage: describe <subtask_name> <description text>")
            return
        st_target, desc = parts[0].upper(), parts[1].strip()
        found = self._find_subtask(st_target)
        if not found:
            print(f"  {YELLOW}Subtask '{st_target}' not found.{RESET}")
            return
        task_name, task_data, branch_name, branch_data, st = found
        st["description"] = desc
        # Jump straight to Running so Claude executes it next step,
        # bypassing the Pending queue entirely. This prevents starvation
        # when a high-staleness backlog would bury the newly-described task.
        st["status"]      = "Running"
        st["shadow"]      = "Pending"
        st["output"]      = ""
        st["last_update"] = self.step
        branch_data["status"] = "Running"
        task_data["status"]   = "Running"
        print(f"  {GREEN}Description set on {st_target} ({task_name}) — queued for Claude next step.{RESET}")
        self.display.render(self.dag, self.memory_store, self.step,
                            self.alerts, self.meta.forecast(self.dag))

    def _cmd_verify(self, args: str) -> None:
        """verify <subtask> [note] — hard-set a subtask Verified (human confirmation)."""
        parts     = args.strip().split(" ", 1)
        st_target = parts[0].upper() if parts and parts[0] else ""
        if not st_target:
            print(f"  Usage: verify <subtask_name> [optional note]")
            return
        note  = parts[1].strip() if len(parts) > 1 else "Manually verified"
        found = self._find_subtask(st_target)
        if not found:
            print(f"  {YELLOW}Subtask '{st_target}' not found.{RESET}")
            return
        task_name, task_data, branch_name, branch_data, st = found
        prev              = st.get("status", "Pending")
        st["status"]      = "Verified"
        st["shadow"]      = "Done"
        st["output"]      = note
        st["last_update"] = self.step
        self.executor._roll_up(self.dag, task_name, branch_name)
        print(f"  {GREEN}v {st_target} ({task_name}) verified (was {prev}). Note: {note[:60]}{RESET}")
        self.display.render(self.dag, self.memory_store, self.step,
                            self.alerts, self.meta.forecast(self.dag))

    def _cmd_tools(self, args: str) -> None:
        """tools <ST> <toollist> — set allowed tools for a subtask and re-queue it.

        toollist examples:
          Read,Glob,Grep          — read-only filesystem access
          Bash,Read,Write,Glob    — full read/write + shell
          none / ""               — headless (no tools, default)
        """
        parts = args.strip().split(" ", 1)
        if len(parts) < 2:
            print(f"  Usage: tools <subtask> <comma-separated tools | none>")
            print(f"  Example: tools H1 Read,Glob,Grep")
            return
        st_target = parts[0].upper()
        tool_val  = "" if parts[1].strip().lower() in ("none", "") else parts[1].strip()

        found = self._find_subtask(st_target)
        if not found:
            print(f"  {YELLOW}Subtask '{st_target}' not found.{RESET}")
            return
        task_name, task_data, branch_name, branch_data, st = found
        st["tools"] = tool_val
        # Re-queue so it re-runs with new tools
        if st.get("status") == "Verified":
            st["status"] = "Running"
            st["shadow"] = "Pending"
            st["output"] = ""
            branch_data["status"] = "Running"
            task_data["status"]   = "Running"
        label = tool_val if tool_val else "(none — headless)"
        print(f"  {GREEN}Tools set on {st_target} ({task_name}): {label}{RESET}")
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_output(self, args: str) -> None:
        """output <subtask> — print full Claude output for a subtask."""
        st_target = args.strip().upper()
        if not st_target:
            print(f"  Usage: output <subtask_name>")
            return
        found = self._find_subtask(st_target)
        if not found:
            print(f"  {YELLOW}Subtask '{st_target}' not found.{RESET}")
            return
        task_name, _, _, _, st = found
        out = st.get("output", "")
        if out:
            print(f"\n  {BOLD}{CYAN}Output for {st_target} ({task_name}):{RESET}")
            print(f"  {out}\n")
        else:
            print(f"  {YELLOW}No output for {st_target} ({task_name}) yet.{RESET}\n")

    def _cmd_help(self) -> None:
        W = 60
        print(f"\n  {BOLD}{CYAN}Solo Builder — Commands{RESET}")
        print(f"  {'─' * W}")
        rows = [
            ("run",                    "Execute one agent pipeline step"),
            ("auto [N]",               "Run N steps automatically (default: until done)"),
            ("snapshot",               "Generate a PDF timeline snapshot"),
            ("save",                   "Save current state to disk"),
            ("load",                   "Load last saved state from disk"),
            ("reset",                  "Reset DAG to initial state, clear save"),
            ("status",                 "Show detailed DAG statistics"),
            ("add_task",               "Append a new Task (Claude decomposes spec)"),
            ("add_branch <Task N>",    "Add a new branch to an existing task"),
            ("export",                  "Write all Claude outputs to solo_builder_outputs.md"),
            ("depends",                 "Print dependency graph"),
            ("depends <T> <dep>",      "Add dependency: Task T depends on dep"),
            ("undepends <T> <dep>",    "Remove a dependency from Task T"),
            ("describe <ST> <text>",   "Attach a real Claude task description to a subtask"),
            ("verify <ST> [note]",     "Hard-set a subtask Verified (human confirmation)"),
            ("tools <ST> <toollist>",  "Set allowed tools for a subtask (re-queues it)"),
            ("output <ST>",            "Print full Claude output for a subtask"),
            ("set KEY=VALUE",          "Change runtime config"),
            ("  STALL_THRESHOLD=N",    "Steps before self-healing fires"),
            ("  SNAPSHOT_INTERVAL=N",  "Steps between auto-snapshots"),
            ("  VERBOSITY=INFO|DEBUG", "Toggle debug output"),
            ("  VERIFY_PROB=0.0-1.0",  "Subtask completion probability"),
            ("  AUTO_STEP_DELAY=0.4",  "Seconds between auto steps"),
            ("  AUTO_SAVE_INTERVAL=5", "Steps between auto-saves"),
            ("  CLAUDE_ALLOWED_TOOLS=", "Default tools for all Claude subtasks"),
            ("  ANTHROPIC_MAX_TOKENS=","SDK response token limit (default 300)"),
            ("  ANTHROPIC_MODEL=",     "SDK model (default claude-sonnet-4-6)"),
            ("  CLAUDE_SUBPROCESS=off","Route all subtasks through SDK instead"),
            ("help",                   "Show this help"),
            ("exit",                   "Quit (auto-saves state)"),
        ]
        for cmd, desc in rows:
            print(f"  {GREEN}{cmd:<28}{RESET} {desc}")
        print(f"  {'─' * W}")
        input(f"  {DIM}Press Enter to continue…{RESET}")
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    # ── Main loop ────────────────────────────────────────────────────────────
    def start(self) -> None:
        """Run the interactive CLI loop, offering to resume saved state."""
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                saved_step = saved.get("step", 0)
                saved_v    = dag_stats(saved.get("dag", {})).get("verified", 0)
                saved_t    = dag_stats(saved.get("dag", {})).get("total", 0)
                print(f"  {CYAN}Saved state found: step {saved_step}, "
                      f"{saved_v}/{saved_t} verified.{RESET}")
                ans = input(f"  {BOLD}Resume? [Y/n]:{RESET} ").strip().lower()
                if ans in ("", "y", "yes"):
                    ok = self.load_state()
                    if ok:
                        print(f"  {GREEN}Resumed from step {self.step}.{RESET}")
                        time.sleep(0.5)
            except Exception:
                pass  # corrupt save → start fresh

        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag) if self.step else "N/A",
        )
        while self.running:
            try:
                raw = input(f"\n  {BOLD}{CYAN}solo-builder >{RESET} ")
                self.handle_command(raw)
            except (KeyboardInterrupt, EOFError):
                print(f"\n  {YELLOW}Interrupted — type 'exit' to quit.{RESET}")
                self.display.render(
                    self.dag, self.memory_store, self.step,
                    self.alerts, self.meta.forecast(self.dag),
                )


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def _splash() -> None:
    lines = [
        "╔══════════════════════════════════════════════════════╗",
        "║      SOLO BUILDER — AI AGENT CLI  v1.1               ║",
        "║                                                       ║",
        "║  DAG · Shadow · Self-Heal · Auto-Run · Persistence   ║",
        "╚══════════════════════════════════════════════════════╝",
    ]
    print(f"\n{BOLD}{CYAN}")
    for line in lines:
        print(f"  {line}")
    print(RESET)

    if not _PDF_OK:
        print(f"  {YELLOW}[!] matplotlib not found — PDF snapshots disabled.")
        print(f"      Install with: pip install matplotlib{RESET}\n")
    time.sleep(0.6)


def _acquire_lock(lock_path: str) -> None:
    """Write a PID lockfile; exit if another instance is already running."""
    if os.path.exists(lock_path):
        try:
            pid = int(open(lock_path).read().strip())
            os.kill(pid, 0)          # Raises if process doesn't exist
            print(f"\n  Solo Builder is already running (PID {pid}).")
            print(f"  If that process is stale, delete {lock_path} and retry.\n")
            sys.exit(1)
        except (ProcessLookupError, PermissionError):
            os.remove(lock_path)     # Stale lock — clean up
    with open(lock_path, "w") as f:
        f.write(str(os.getpid()))


def _release_lock(lock_path: str) -> None:
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    _LOCK_PATH = os.path.join(_HERE, "state", "solo_builder.lock")
    os.makedirs(os.path.join(_HERE, "state"), exist_ok=True)
    _acquire_lock(_LOCK_PATH)
    try:
        _splash()
        cli = SoloBuilderCLI()
        cli.start()
    finally:
        _release_lock(_LOCK_PATH)
