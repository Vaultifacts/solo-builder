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

import argparse
import asyncio
import logging
import logging.handlers
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
MAX_SUBTASKS_PER_BRANCH: int = _CFG.get("MAX_SUBTASKS_PER_BRANCH", 20)
MAX_BRANCHES_PER_TASK  : int = _CFG.get("MAX_BRANCHES_PER_TASK",   10)
CLAUDE_TIMEOUT        : int = _CFG.get("CLAUDE_TIMEOUT", 60)
CLAUDE_ALLOWED_TOOLS  : str = _CFG.get("CLAUDE_ALLOWED_TOOLS", "")
ANTHROPIC_MODEL       : str  = _CFG.get("ANTHROPIC_MODEL",      "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS  : int  = _CFG.get("ANTHROPIC_MAX_TOKENS", 300)
REVIEW_MODE           : bool = bool(_CFG.get("REVIEW_MODE",       False))
WEBHOOK_URL           : str  = _CFG.get("WEBHOOK_URL",            "")

# One-liner context injected at the front of every Claude prompt so the model
# knows what project it is working within, avoiding "I don't know what X is"
_PROJECT_CONTEXT = (
    "Context: Solo Builder is a Python terminal CLI that uses six AI agents "
    "(Planner, ShadowAgent, SelfHealer, Executor, Verifier, MetaOptimizer) "
    "and the Anthropic SDK to manage DAG-based software project tasks. "
)

# Resolve relative paths to script location
if not os.path.isabs(PDF_OUTPUT_PATH):
    PDF_OUTPUT_PATH = os.path.join(_HERE, PDF_OUTPUT_PATH)
if not os.path.isabs(STATE_PATH):
    STATE_PATH = os.path.join(_HERE, STATE_PATH)
_JOURNAL_RAW = _CFG.get("JOURNAL_PATH", "journal.md")
JOURNAL_PATH = _JOURNAL_RAW if os.path.isabs(_JOURNAL_RAW) else os.path.join(_HERE, _JOURNAL_RAW)

_LOG_PATH = os.path.join(_HERE, "state", "solo_builder.log")

# Module-level logger — handlers configured in _setup_logging() called from main()
logger = logging.getLogger("solo_builder")


def _setup_logging() -> None:
    """Configure a rotating file handler for structured log output."""
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False


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
    """Append one verified Claude result to the journal file."""
    parent = os.path.dirname(JOURNAL_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    exists = os.path.exists(JOURNAL_PATH)
    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        if not exists:
            f.write("# Solo Builder — Live Journal\n\n")
        f.write(f"## {st_name} · {task_name} / {branch_name} · Step {step}\n\n")
        if description:
            f.write(f"**Prompt:** {description}\n\n")
        f.write(f"{output}\n\n---\n\n")


def _append_cache_session_stats(cache, steps: int) -> None:
    """Append per-session ResponseCache hit/miss summary to the journal.

    Only writes if the cache was consulted at least once this session.
    Silently skips if cache is None or the journal cannot be written.
    """
    if cache is None:
        return
    try:
        s = cache.stats()
        total = s["hits"] + s["misses"]
        if total == 0:
            return  # cache unused this session — nothing worth logging
        hit_rate = s["hits"] / total * 100
        parent = os.path.dirname(JOURNAL_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        exists = os.path.exists(JOURNAL_PATH)
        with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
            if not exists:
                f.write("# Solo Builder — Live Journal\n\n")
            f.write(
                f"## Cache session summary · Step {steps}\n\n"
                f"| Metric | Value |\n"
                f"|--------|-------|\n"
                f"| Hits | {s['hits']} |\n"
                f"| Misses | {s['misses']} |\n"
                f"| Hit rate | {hit_rate:.1f}% |\n"
                f"| Entries on disk | {s['size']} |\n"
                f"| Est. tokens saved | {s['estimated_tokens_saved']:,} |\n"
                f"\n---\n\n"
            )
    except Exception:
        pass  # journal write failure is non-fatal


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTS (extracted to solo_builder/agents/)
# ═══════════════════════════════════════════════════════════════════════════════
from agents import Planner, ShadowAgent, Verifier, SelfHealer, MetaOptimizer  # noqa: F401

# ═══════════════════════════════════════════════════════════════════════════════
# RUNNERS (extracted to solo_builder/runners/)
# ═══════════════════════════════════════════════════════════════════════════════
from runners import ClaudeRunner, AnthropicRunner, SdkToolRunner, Executor  # noqa: F401

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
        if output and status in ("Verified", "Review"):
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
        review   = stats["review"]
        running  = stats["running"]
        pending  = stats["pending"]
        pct      = verified / total * 100 if total else 0

        overall = self._bar(verified, total, "=", "-", width=32)
        print(f"\n  {CYAN}{'─' * self._WIDTH}{RESET}")
        review_part = f"{MAGENTA}{review}⏸{RESET} " if review else ""
        print(
            f"  Overall [{GREEN}{overall}{RESET}] "
            f"{GREEN}{verified}✓{RESET} "
            f"{review_part}"
            f"{CYAN}{running}▶{RESET} "
            f"{YELLOW}{pending}●{RESET} "
            f"/ {total}  ({pct:.1f}%)"
        )
        print(f"\n  {DIM}Commands: run │ auto [N] │ pause │ resume │ add_task │ add_branch │ depends │ rename │ describe │ verify │ tools │ output │ export │ diff │ stats │ history │ branches │ filter │ graph │ config │ priority │ stalled │ heal │ agents │ forecast │ tasks │ search │ log │ snapshot │ save │ load │ reset │ help │ exit{RESET}")
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
        self._priority_cache: List = []
        self._last_priority_step: int = -(DAG_UPDATE_INTERVAL + 1)  # force first run
        self._last_verified_tasks: int = 0   # triggers cache refresh when a task unblocks

        # Agents
        self.planner  = Planner(stall_threshold=STALL_THRESHOLD)
        self.executor = Executor(max_per_step=EXEC_MAX_PER_STEP,
                                 verify_prob=EXEC_VERIFY_PROB,
                                 project_context=_PROJECT_CONTEXT,
                                 append_journal=_append_journal)
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

        # 1. Planner: prioritize (re-runs every DAG_UPDATE_INTERVAL steps,
        #    or immediately when a task flips to Verified — which unblocks dependents)
        verified_tasks = sum(
            1 for t in self.dag.values() if t.get("status") == "Verified"
        )
        if (self.step - self._last_priority_step) >= DAG_UPDATE_INTERVAL \
                or verified_tasks > self._last_verified_tasks:
            self._priority_cache     = self.planner.prioritize(self.dag, self.step)
            self._last_priority_step = self.step
            self._last_verified_tasks = verified_tasks
        priority = self._priority_cache

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

        # Heartbeat: write live counters every step for Discord bot real-time tracking
        _hb = os.path.join(_HERE, "state", "step.txt")
        try:
            _hb_v = _hb_t = _hb_p = _hb_r = _hb_rv = 0
            for _ht in self.dag.values():
                for _hb2 in _ht["branches"].values():
                    for _hs in _hb2["subtasks"].values():
                        _hb_t += 1
                        _st = _hs.get("status", "")
                        if _st == "Verified":  _hb_v  += 1
                        elif _st == "Pending": _hb_p  += 1
                        elif _st == "Running": _hb_r  += 1
                        elif _st == "Review":  _hb_rv += 1
            with open(_hb, "w") as _f:
                _f.write(f"{self.step},{_hb_v},{_hb_t},{_hb_p},{_hb_r},{_hb_rv}")
        except OSError:
            pass

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
        # Rotate backups: .3 → delete, .2 → .3, .1 → .2, current → .1
        if os.path.exists(STATE_PATH):
            for i in range(3, 1, -1):
                src = f"{STATE_PATH}.{i - 1}"
                dst = f"{STATE_PATH}.{i}"
                if os.path.exists(src):
                    try:
                        os.replace(src, dst)
                    except OSError:
                        pass
            try:
                import shutil
                shutil.copy2(STATE_PATH, f"{STATE_PATH}.1")
            except OSError:
                pass
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
            # Atomic write: serialize to temp file then replace — prevents corruption
            # if the process is killed mid-write (multiple surfaces read STATE_PATH)
            tmp_path = STATE_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, STATE_PATH)
            logger.info("state_saved step=%d path=%s", self.step, STATE_PATH)
            if not silent:
                print(f"  {GREEN}State saved → {STATE_PATH}{RESET}")
        except Exception as exc:
            logger.error("state_save_failed step=%d error=%s", self.step, exc)
            print(f"  {RED}Save failed: {exc}{RESET}")

    def load_state(self) -> bool:
        """
        Load state from disk into this instance.
        Returns True if loaded successfully, False otherwise.
        """
        if not os.path.exists(STATE_PATH):
            return False
        # Try primary state file; on JSON corruption fall back to most recent backup
        paths_to_try = [STATE_PATH] + [f"{STATE_PATH}.{n}" for n in (1, 2, 3)]
        for attempt_path in paths_to_try:
            if not os.path.exists(attempt_path):
                continue
            try:
                with open(attempt_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if attempt_path != STATE_PATH:
                    logger.warning("state_recovered from=%s", attempt_path)
                    print(f"  {YELLOW}Primary state corrupt — recovered from {attempt_path}{RESET}")
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
                logger.info("state_loaded step=%d path=%s", self.step, attempt_path)
                return True
            except (json.JSONDecodeError, KeyError):
                if attempt_path == STATE_PATH:
                    logger.warning("state_corrupt path=%s trying_backups=True", attempt_path)
                    print(f"  {YELLOW}State file corrupt — trying backups…{RESET}")
                continue
            except Exception as exc:
                logger.error("state_load_failed path=%s error=%s", attempt_path, exc)
                print(f"  {RED}Load failed: {exc}{RESET}")
                return False
        print(f"  {RED}All state files corrupt or missing — starting fresh.{RESET}")
        return False

    def _cmd_load_backup(self, args: str) -> None:
        """load_backup [1|2|3] — restore state from a backup file."""
        n = args.strip() or "1"
        if n not in ("1", "2", "3"):
            print(f"  Usage: load_backup [1|2|3]  (default: 1 = most recent)")
            return
        backup_path = f"{STATE_PATH}.{n}"
        if not os.path.exists(backup_path):
            print(f"  {YELLOW}Backup {backup_path} not found.{RESET}")
            avail = [str(i) for i in range(1, 4) if os.path.exists(f"{STATE_PATH}.{i}")]
            if avail:
                print(f"  Available backups: {', '.join(avail)}")
            else:
                print(f"  No backup files found.")
            return
        # Copy backup over main state, then load
        try:
            import shutil
            shutil.copy2(backup_path, STATE_PATH)
        except OSError as exc:
            print(f"  {RED}Copy failed: {exc}{RESET}")
            return
        ok = self.load_state()
        if ok:
            print(f"  {GREEN}Restored from backup .{n} — step {self.step}, "
                  f"{dag_stats(self.dag)['verified']} verified.{RESET}")
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )
        else:
            print(f"  {RED}Backup .{n} exists but failed to load.{RESET}")

    def _cmd_undo(self) -> None:
        """undo — restore state from the most recent backup (.1)."""
        backup_path = f"{STATE_PATH}.1"
        if not os.path.exists(backup_path):
            print(f"  {YELLOW}No backup available to undo.{RESET}")
            return
        prev_step = self.step
        try:
            import shutil
            shutil.copy2(backup_path, STATE_PATH)
        except OSError as exc:
            print(f"  {RED}Undo failed: {exc}{RESET}")
            return
        ok = self.load_state()
        if ok:
            print(f"  {GREEN}Undo: step {prev_step} -> {self.step} "
                  f"({dag_stats(self.dag)['verified']} verified){RESET}")
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )
        else:
            print(f"  {RED}Undo backup exists but failed to load.{RESET}")

    # ── Trigger helpers ────────────────────────────────────────────────────
    @staticmethod
    def _consume_json_trigger(path: str):
        """Read, parse, and atomically delete a JSON trigger file.

        Returns the parsed dict/list on success, or *None* if the file
        doesn't exist or can't be read.
        """
        if not os.path.exists(path):
            return None
        try:
            data = json.loads(open(path, encoding="utf-8").read())
            os.remove(path)
            return data
        except Exception:
            return None

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

        _trigger     = os.path.join(_HERE, "state", "run_trigger")
        _stoptrig    = os.path.join(_HERE, "state", "stop_trigger")
        _attrigger   = os.path.join(_HERE, "state", "add_task_trigger.json")
        _abtrigger   = os.path.join(_HERE, "state", "add_branch_trigger.json")
        _pbtrigger   = os.path.join(_HERE, "state", "prioritize_branch_trigger.json")
        _dtrigger    = os.path.join(_HERE, "state", "describe_trigger.json")
        _rntrigger   = os.path.join(_HERE, "state", "rename_trigger.json")
        _ttrigger    = os.path.join(_HERE, "state", "tools_trigger.json")
        _rtrigger    = os.path.join(_HERE, "state", "reset_trigger")
        _snaptrigger = os.path.join(_HERE, "state", "snapshot_trigger")
        _settrigger  = os.path.join(_HERE, "state", "set_trigger.json")
        _deptrigger  = os.path.join(_HERE, "state", "depends_trigger.json")
        _undeptrigger = os.path.join(_HERE, "state", "undepends_trigger.json")
        _undotrigger  = os.path.join(_HERE, "state", "undo_trigger")
        _pausetrigger = os.path.join(_HERE, "state", "pause_trigger")
        _healtrigger  = os.path.join(_HERE, "state", "heal_trigger.json")
        _dagimptrigger = os.path.join(_HERE, "state", "dag_import_trigger.json")
        try:
            while True:
                self.run_step()
                ran += 1

                stats = dag_stats(self.dag)
                if stats["verified"] == stats["total"]:
                    self.save_state(silent=True)   # flush JSON before bot reads it
                    _fire_completion(self.step, stats["verified"], stats["total"])
                    time.sleep(1.2)
                    break

                if limit is not None and ran >= limit:
                    break

                # Honour external triggers (dashboard Run Step, Discord/Telegram verify)
                # NOTE: check verify_trigger BEFORE breaking on run_trigger so that
                # external verify requests aren't skipped when auto-mode is running.
                _waited  = 0.0
                _stopped = False
                _vtrigger = os.path.join(_HERE, "state", "verify_trigger.json")
                while _waited < AUTO_STEP_DELAY:
                    if os.path.exists(_stoptrig):
                        try:
                            os.remove(_stoptrig)
                        except OSError:
                            pass
                        _stopped = True
                        break
                    # Pause gate: spin while pause_trigger exists (don't advance _waited)
                    while os.path.exists(_pausetrigger):
                        if _waited < 0.05:  # first detection — print once
                            print(f"  {YELLOW}Auto-run paused remotely. Waiting for resume…{RESET}", flush=True)
                            _waited = 0.05
                        time.sleep(0.2)
                        # Still honour stop during pause
                        if os.path.exists(_stoptrig):
                            break
                    vdata = self._consume_json_trigger(_vtrigger)
                    if vdata:
                        for e in (vdata if isinstance(vdata, list) else [vdata]):
                            self._cmd_verify(
                                f"{e.get('subtask', '')} {e.get('note', 'Discord verify')}"
                            )
                    adata = self._consume_json_trigger(_attrigger)
                    if adata:
                        spec = adata.get("spec", "").strip()
                        if spec:
                            self._cmd_add_task(spec)
                    abdata = self._consume_json_trigger(_abtrigger)
                    if abdata:
                        task_arg = abdata.get("task", "").strip()
                        spec     = abdata.get("spec", "").strip()
                        if task_arg and spec:
                            self._cmd_add_branch(task_arg, spec_override=spec)
                    pbdata = self._consume_json_trigger(_pbtrigger)
                    if pbdata:
                        pb_task   = pbdata.get("task", "").strip()
                        pb_branch = pbdata.get("branch", "").strip()
                        if pb_task and pb_branch:
                            self._cmd_prioritize_branch(pb_task, pb_branch)
                    ddata = self._consume_json_trigger(_dtrigger)
                    if ddata:
                        d_st   = ddata.get("subtask", "").strip().upper()
                        d_desc = ddata.get("desc", "").strip()
                        if d_st and d_desc:
                            self._cmd_describe(f"{d_st} {d_desc}")
                    rndata = self._consume_json_trigger(_rntrigger)
                    if rndata:
                        rn_st   = rndata.get("subtask", "").strip().upper()
                        rn_desc = rndata.get("desc", "").strip()
                        if rn_st and rn_desc:
                            self._cmd_rename(f"{rn_st} {rn_desc}")
                    tdata = self._consume_json_trigger(_ttrigger)
                    if tdata:
                        t_st    = tdata.get("subtask", "").strip().upper()
                        t_tools = tdata.get("tools", "").strip()
                        if t_st and t_tools:
                            self._cmd_tools(f"{t_st} {t_tools}")
                    sdata = self._consume_json_trigger(_settrigger)
                    if sdata:
                        s_key = sdata.get("key", "").strip()
                        s_val = sdata.get("value", "").strip()
                        if s_key and s_val:
                            self._cmd_set(f"{s_key}={s_val}")
                    healdata = self._consume_json_trigger(_healtrigger)
                    if healdata:
                        h_st = healdata.get("subtask", "").strip().upper()
                        if h_st:
                            self._cmd_heal(h_st)
                    depdata = self._consume_json_trigger(_deptrigger)
                    if depdata:
                        dep_target = depdata.get("target", "").strip()
                        dep_dep    = depdata.get("dep", "").strip()
                        if dep_target and dep_dep:
                            self._cmd_depends(f"{dep_target} {dep_dep}")
                    if os.path.exists(_undeptrigger):
                        try:
                            uddata = json.loads(
                                open(_undeptrigger, encoding="utf-8").read()
                            )
                            os.remove(_undeptrigger)
                            ud_target = uddata.get("target", "").strip()
                            ud_dep    = uddata.get("dep", "").strip()
                            if ud_target and ud_dep:
                                self._cmd_undepends(f"{ud_target} {ud_dep}")
                        except Exception:
                            pass
                    if os.path.exists(_rtrigger):
                        try:
                            os.remove(_rtrigger)
                        except OSError:
                            pass
                        self._cmd_reset()
                    if os.path.exists(_snaptrigger):
                        try:
                            os.remove(_snaptrigger)
                        except OSError:
                            pass
                        self._take_snapshot(auto=False)
                    if os.path.exists(_undotrigger):
                        try:
                            os.remove(_undotrigger)
                        except OSError:
                            pass
                        self._cmd_undo()
                    dagimpdata = self._consume_json_trigger(_dagimptrigger)
                    if dagimpdata and isinstance(dagimpdata.get("dag"), dict):
                        errors = validate_dag(dagimpdata["dag"])
                        if not errors:
                            self.save_state(silent=True)
                            self.dag = dagimpdata["dag"]
                            self.shadow.update_expected(self.dag)
                            self._last_priority_step = -(DAG_UPDATE_INTERVAL + 1)
                            src = dagimpdata.get("exported_step", "?")
                            print(f"  {GREEN}DAG imported via trigger (exported at step {src}){RESET}")
                            logger.info("dag_imported_via_trigger src_step=%s", src)
                    if os.path.exists(_trigger):
                        try:
                            os.remove(_trigger)
                        except OSError:
                            pass
                        break
                    time.sleep(0.05)
                    _waited += 0.05

                if _stopped:
                    print(f"\n  {YELLOW}Auto-run stopped remotely at step {self.step}.{RESET}")
                    time.sleep(0.5)
                    self.display.render(
                        self.dag, self.memory_store, self.step,
                        self.alerts, self.meta.forecast(self.dag),
                    )
                    break

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

        elif cmd.startswith("load_backup"):
            self._cmd_load_backup(raw[12:].strip())

        elif cmd == "undo":
            self._cmd_undo()

        elif cmd == "diff":
            self._cmd_diff()

        elif cmd.startswith("timeline "):
            self._cmd_timeline(raw[9:])

        elif cmd == "reset":
            self._cmd_reset()

        elif cmd == "status":
            self._cmd_status()

        elif cmd == "stats":
            self._cmd_stats()

        elif cmd == "history":
            self._cmd_history("")

        elif cmd.startswith("history "):
            self._cmd_history(raw[8:])

        elif cmd == "add_task":
            self._cmd_add_task()

        elif cmd.startswith("add_task "):
            self._cmd_add_task(raw[9:])

        elif cmd.startswith("add_branch"):
            _ab_parts = raw[10:].strip().split(None, 1)
            if len(_ab_parts) >= 2:
                self._cmd_add_branch(_ab_parts[0], spec_override=_ab_parts[1])
            else:
                self._cmd_add_branch(raw[10:])

        elif cmd.startswith("prioritize_branch"):
            _pb_parts = raw[17:].strip().split(None, 1)
            self._cmd_prioritize_branch(*_pb_parts)

        elif cmd == "export":
            self._cmd_export()

        elif cmd == "export_dag" or cmd.startswith("export_dag "):
            self._cmd_export_dag(raw[10:].strip() if cmd.startswith("export_dag ") else "")

        elif cmd.startswith("import_dag "):
            self._cmd_import_dag(raw[11:])

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

        elif cmd == "branches":
            self._cmd_branches("")

        elif cmd.startswith("branches "):
            self._cmd_branches(raw[9:])

        elif cmd.startswith("rename "):
            self._cmd_rename(raw[7:])

        elif cmd.startswith("search "):
            self._cmd_search(raw[7:])

        elif cmd.startswith("filter "):
            self._cmd_filter(raw[7:])

        elif cmd == "graph":
            self._cmd_graph()

        elif cmd == "log":
            self._cmd_log("")

        elif cmd.startswith("log "):
            self._cmd_log(raw[4:])

        elif cmd == "pause":
            self._cmd_pause()

        elif cmd == "resume":
            self._cmd_resume()

        elif cmd.startswith("set "):
            self._cmd_set(raw[4:])

        elif cmd == "config":
            self._cmd_config()

        elif cmd == "priority":
            self._cmd_priority()

        elif cmd == "stalled":
            self._cmd_stalled()

        elif cmd.startswith("heal "):
            self._cmd_heal(raw[5:])

        elif cmd == "agents":
            self._cmd_agents()

        elif cmd == "forecast":
            self._cmd_forecast()

        elif cmd == "tasks":
            self._cmd_tasks()

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

    def _cmd_add_task(self, spec_override: str = "") -> None:
        task_idx  = len(self.dag)
        task_name = f"Task {task_idx}"
        if task_name in self.dag:
            print(f"  {YELLOW}{task_name} already exists.{RESET}")
            return

        letter      = chr(ord("A") + task_idx % 26)
        branch_name = f"Branch {letter}"

        spec = spec_override.strip() if spec_override.strip() else \
               input(f"  {BOLD}What should {task_name} accomplish?{RESET} ").strip()

        # Parse optional dependency override: "My spec | depends: 5"
        dep_task = None
        if " | depends:" in spec:
            head, dep_raw = spec.split(" | depends:", 1)
            spec = head.strip()
            dep_raw = dep_raw.strip()
            if dep_raw.isdigit():
                dep_raw = f"Task {dep_raw}"
            if dep_raw in self.dag:
                dep_task = dep_raw
            else:
                print(f"  {YELLOW}Unknown dependency '{dep_raw}' — using default (last task).{RESET}")

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

        # Enforce subtask limit
        if len(subtasks) > MAX_SUBTASKS_PER_BRANCH:
            excess = list(subtasks)[MAX_SUBTASKS_PER_BRANCH:]
            for k in excess:
                del subtasks[k]
            print(f"  {YELLOW}Capped to {MAX_SUBTASKS_PER_BRANCH} subtasks (MAX_SUBTASKS_PER_BRANCH).{RESET}")

        # Auto-wire: new task depends on the last existing task (or explicit dep_task)
        last_task = dep_task if dep_task else (list(self.dag.keys())[-1] if self.dag else None)

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
        print(f"  {GREEN}Added {task_name} -> {branch_name} -> {', '.join(st_list)}{RESET}")
        time.sleep(0.6)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_add_branch(self, args: str, spec_override: str = "") -> None:
        """add_branch <Task N> [spec] — Claude-decompose a spec into a new branch on an existing task."""
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

        current_branches = len(self.dag[task_name].get("branches", {}))
        if current_branches >= MAX_BRANCHES_PER_TASK:
            print(f"  {YELLOW}{task_name} already has {current_branches} branches "
                  f"(limit: MAX_BRANCHES_PER_TASK={MAX_BRANCHES_PER_TASK}).{RESET}")
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

        spec = (
            spec_override.strip()
            if spec_override.strip()
            else input(f"  {BOLD}What should {branch_name} of {task_name} cover?{RESET} ").strip()
        )
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

        # Enforce subtask limit
        if len(subtasks) > MAX_SUBTASKS_PER_BRANCH:
            excess = list(subtasks)[MAX_SUBTASKS_PER_BRANCH:]
            for k in excess:
                del subtasks[k]
            print(f"  {YELLOW}Capped to {MAX_SUBTASKS_PER_BRANCH} subtasks (MAX_SUBTASKS_PER_BRANCH).{RESET}")

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
        print(f"  {GREEN}Added {branch_name} -> {', '.join(st_list)} to {task_name}{RESET}")
        time.sleep(0.6)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_prioritize_branch(self, task_arg: str = "", branch_arg: str = "") -> None:
        """prioritize_branch [<task> <branch>] — boost a branch to the front of the queue."""
        branches = [
            (task_name, branch_name)
            for task_name, task_data in self.dag.items()
            for branch_name in task_data.get("branches", {})
        ]

        if not task_arg:
            print(f"\n  {BOLD}Available branches:{RESET}")
            for t, b in branches:
                print(f"    {CYAN}{t}{RESET} / {b}")
            print()
            task_arg   = input(f"  Task (e.g. 0 or 'Task 0'): ").strip()
            branch_arg = input(f"  Branch name: ").strip()

        if task_arg.isdigit():
            task_arg = f"Task {task_arg}"

        if task_arg not in self.dag:
            print(f"  {YELLOW}Task '{task_arg}' not found.{RESET}")
            return

        branches_in_task = self.dag[task_arg].get("branches", {})
        if branch_arg not in branches_in_task:
            matches = [b for b in branches_in_task if branch_arg.upper() in b.upper()]
            if len(matches) == 1:
                branch_arg = matches[0]
            else:
                print(f"  {YELLOW}Branch '{branch_arg}' not found in {task_arg}. "
                      f"Available: {list(branches_in_task)}{RESET}")
                return

        boosted = 0
        for st_data in branches_in_task[branch_arg]["subtasks"].values():
            if st_data.get("status") == "Pending":
                st_data["last_update"] = self.step - 500
                boosted += 1

        # Force priority cache refresh so next step picks up the boost
        self._last_priority_step = -(DAG_UPDATE_INTERVAL + 1)

        print(f"  {GREEN}Boosted {boosted} Pending subtask(s) in {task_arg}/{branch_arg} "
              f"— they will be scheduled first.{RESET}")
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _persist_setting(self, cfg_key: str, value) -> None:
        """Silently write one key back to config/settings.json."""
        try:
            with open(_CFG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            cfg[cfg_key] = value
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass

    def _cmd_config(self) -> None:
        """config — display all runtime settings in a formatted table."""
        settings: dict = {
            "STALL_THRESHOLD":     str(STALL_THRESHOLD),
            "SNAPSHOT_INTERVAL":   str(SNAPSHOT_INTERVAL),
            "VERBOSITY":           VERBOSITY,
            "VERIFY_PROB":         str(self.executor.verify_prob),
            "AUTO_STEP_DELAY":     str(AUTO_STEP_DELAY),
            "AUTO_SAVE_INTERVAL":  str(AUTO_SAVE_INTERVAL),
            "CLAUDE_ALLOWED_TOOLS": CLAUDE_ALLOWED_TOOLS or "(none)",
            "ANTHROPIC_MAX_TOKENS": str(self.executor.anthropic.max_tokens),
            "ANTHROPIC_MODEL":     self.executor.anthropic.model,
            "CLAUDE_SUBPROCESS":   "on" if self.executor.claude.available else "off",
            "REVIEW_MODE":         "on" if self.executor.review_mode else "off",
            "WEBHOOK_URL":         WEBHOOK_URL or "(not set)",
        }
        print(f"\n  {BOLD}{CYAN}Runtime Settings{RESET}")
        print(f"  {'─' * 50}")
        for k, v in settings.items():
            print(f"  {CYAN}{k:<22}{RESET} {v}")
        print(f"  {'─' * 50}")
        print(f"  {DIM}Use: set KEY=VALUE to change{RESET}\n")

    def _cmd_set(self, args: str) -> None:
        """set KEY=VALUE — update runtime config."""
        global STALL_THRESHOLD, SNAPSHOT_INTERVAL, VERBOSITY
        global AUTO_STEP_DELAY, AUTO_SAVE_INTERVAL, CLAUDE_ALLOWED_TOOLS, WEBHOOK_URL

        parts = args.split("=", 1)
        if len(parts) != 2:
            bare = args.strip().upper()
            _current: dict = {
                "STALL_THRESHOLD":    str(STALL_THRESHOLD),
                "SNAPSHOT_INTERVAL":  str(SNAPSHOT_INTERVAL),
                "VERBOSITY":          VERBOSITY,
                "VERIFY_PROB":        str(self.executor.verify_prob),
                "AUTO_STEP_DELAY":    str(AUTO_STEP_DELAY),
                "AUTO_SAVE_INTERVAL": str(AUTO_SAVE_INTERVAL),
                "CLAUDE_ALLOWED_TOOLS": CLAUDE_ALLOWED_TOOLS or "(none)",
                "ANTHROPIC_MAX_TOKENS": str(self.executor.anthropic.max_tokens),
                "ANTHROPIC_MODEL":    self.executor.anthropic.model,
                "CLAUDE_SUBPROCESS":  "on" if self.executor.claude.available else "off",
                "REVIEW_MODE":        "on" if self.executor.review_mode else "off",
                "WEBHOOK_URL":        WEBHOOK_URL or "(not set)",
            }
            if bare in _current:
                print(f"  {CYAN}{bare} = {_current[bare]}{RESET}")
            else:
                print(f"  {YELLOW}Usage: set KEY=VALUE{RESET}")
            return

        key, val = parts[0].strip().upper(), parts[1].strip()
        try:
            if key == "STALL_THRESHOLD":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                STALL_THRESHOLD = v
                self.healer.stall_threshold  = STALL_THRESHOLD
                self.planner.stall_threshold = STALL_THRESHOLD
                self.display.stall_threshold = STALL_THRESHOLD
                print(f"  {GREEN}STALL_THRESHOLD = {STALL_THRESHOLD}{RESET}")
                self._persist_setting("STALL_THRESHOLD", STALL_THRESHOLD)

            elif key == "SNAPSHOT_INTERVAL":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                SNAPSHOT_INTERVAL = v
                print(f"  {GREEN}SNAPSHOT_INTERVAL = {SNAPSHOT_INTERVAL}{RESET}")
                self._persist_setting("SNAPSHOT_INTERVAL", SNAPSHOT_INTERVAL)

            elif key == "VERBOSITY":
                v = val.upper()
                if v not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                    raise ValueError("must be one of DEBUG, INFO, WARNING, ERROR")
                VERBOSITY = v
                print(f"  {GREEN}VERBOSITY = {VERBOSITY}{RESET}")
                self._persist_setting("VERBOSITY", VERBOSITY)

            elif key == "VERIFY_PROB":
                v = float(val)
                if not 0.0 <= v <= 1.0:
                    raise ValueError("must be between 0.0 and 1.0")
                self.executor.verify_prob = v
                print(f"  {GREEN}VERIFY_PROB = {val}{RESET}")
                self._persist_setting("EXECUTOR_VERIFY_PROBABILITY", self.executor.verify_prob)

            elif key == "AUTO_STEP_DELAY":
                v = float(val)
                if v < 0:
                    raise ValueError("must be >= 0")
                AUTO_STEP_DELAY = v
                print(f"  {GREEN}AUTO_STEP_DELAY = {AUTO_STEP_DELAY}s{RESET}")
                self._persist_setting("AUTO_STEP_DELAY", AUTO_STEP_DELAY)

            elif key == "AUTO_SAVE_INTERVAL":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                AUTO_SAVE_INTERVAL = v
                print(f"  {GREEN}AUTO_SAVE_INTERVAL = {AUTO_SAVE_INTERVAL}{RESET}")
                self._persist_setting("AUTO_SAVE_INTERVAL", AUTO_SAVE_INTERVAL)

            elif key == "CLAUDE_ALLOWED_TOOLS":
                CLAUDE_ALLOWED_TOOLS = val
                self.executor.claude.allowed_tools = val
                label = val if val else "(none — headless)"
                print(f"  {GREEN}CLAUDE_ALLOWED_TOOLS = {label}{RESET}")
                self._persist_setting("CLAUDE_ALLOWED_TOOLS", val)

            elif key == "ANTHROPIC_MAX_TOKENS":
                v = int(val)
                if v < 1 or v > 8192:
                    raise ValueError("must be between 1 and 8192")
                self.executor.anthropic.max_tokens = v
                print(f"  {GREEN}ANTHROPIC_MAX_TOKENS = {v}{RESET}")
                self._persist_setting("ANTHROPIC_MAX_TOKENS", v)

            elif key == "ANTHROPIC_MODEL":
                self.executor.anthropic.model = val
                print(f"  {GREEN}ANTHROPIC_MODEL = {val}{RESET}")
                self._persist_setting("ANTHROPIC_MODEL", val)

            elif key == "CLAUDE_SUBPROCESS":
                enabled = val.lower() not in ("0", "off", "false", "no")
                self.executor.claude.available = enabled
                label = "on (subprocess)" if enabled else "off (SDK/dice-roll fallback)"
                print(f"  {GREEN}CLAUDE_SUBPROCESS = {label}{RESET}")
                # CLAUDE_SUBPROCESS is not a config.json key — derived at runtime

            elif key == "REVIEW_MODE":
                enabled = val.lower() not in ("0", "off", "false", "no")
                self.executor.review_mode = enabled
                label = "on (subtasks pause at Review for verify)" if enabled else "off (auto-Verified)"
                print(f"  {GREEN}REVIEW_MODE = {label}{RESET}")
                self._persist_setting("REVIEW_MODE", enabled)

            elif key == "WEBHOOK_URL":
                if val and not val.startswith("http"):
                    print(f"  {YELLOW}Warning: WEBHOOK_URL should start with http/https "
                          f"(got {val!r}). Setting anyway.{RESET}")
                WEBHOOK_URL = val
                print(f"  {GREEN}WEBHOOK_URL = {val or '(cleared)'}{RESET}")
                self._persist_setting("WEBHOOK_URL", val)

            else:
                print(f"  {YELLOW}Unknown key '{key}'. "
                      f"Valid: STALL_THRESHOLD, SNAPSHOT_INTERVAL, "
                      f"VERBOSITY, VERIFY_PROB, AUTO_STEP_DELAY, AUTO_SAVE_INTERVAL, "
                      f"CLAUDE_ALLOWED_TOOLS, ANTHROPIC_MAX_TOKENS, ANTHROPIC_MODEL, "
                      f"CLAUDE_SUBPROCESS, REVIEW_MODE, WEBHOOK_URL{RESET}")
        except ValueError:
            print(f"  {RED}Invalid value '{val}' for {key}{RESET}")

        time.sleep(0.5)
        self.display.render(
            self.dag, self.memory_store, self.step,
            self.alerts, self.meta.forecast(self.dag),
        )

    def _cmd_export(self) -> tuple:
        """export — write all Claude outputs to solo_builder_outputs.md.

        Returns (path, count) so callers can include export info in JSON output.
        """
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
            lines.append("*No Claude outputs recorded yet — run steps with ANTHROPIC_API_KEY set.*\n")
        path = os.path.join(_HERE, "solo_builder_outputs.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if count == 0:
            print(f"  {YELLOW}No outputs yet — wrote header to {path}{RESET}", file=sys.stderr)
        else:
            print(f"  {GREEN}Exported {count} outputs → {path}{RESET}", file=sys.stderr)
        return path, count

    def _cmd_export_dag(self, args: str) -> None:
        """export_dag [file] — write current DAG structure to a JSON file."""
        path = args.strip() or os.path.join(_HERE, "dag_export.json")
        if not os.path.isabs(path):
            path = os.path.join(_HERE, path)
        payload = {
            "exported_step": self.step,
            "dag": self.dag,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"  {GREEN}DAG exported → {path}{RESET}")
        logger.info("dag_exported step=%d path=%s", self.step, path)

    def _cmd_import_dag(self, args: str) -> None:
        """import_dag <file> — replace current DAG with one loaded from a JSON file."""
        path = args.strip()
        if not path:
            print(f"  {YELLOW}Usage: import_dag <file>{RESET}")
            return
        if not os.path.isabs(path):
            path = os.path.join(_HERE, path)
        if not os.path.exists(path):
            print(f"  {RED}File not found: {path}{RESET}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  {RED}Failed to read {path}: {exc}{RESET}")
            return
        dag = payload.get("dag") if isinstance(payload, dict) and "dag" in payload else payload
        if not isinstance(dag, dict):
            print(f"  {RED}Invalid DAG file — expected a JSON object{RESET}")
            return
        errors = validate_dag(dag)
        if errors:
            print(f"  {RED}DAG validation failed:{RESET}")
            for e in errors:
                print(f"    {YELLOW}• {e}{RESET}")
            return
        self.save_state(silent=True)   # preserve current state as .1 backup before overwriting
        self.dag = dag
        self.shadow.update_expected(self.dag)
        self._last_priority_step = -(DAG_UPDATE_INTERVAL + 1)
        src_step = payload.get("exported_step", "?") if isinstance(payload, dict) else "?"
        print(f"  {GREEN}DAG imported from {path} (exported at step {src_step}){RESET}")
        logger.info("dag_imported path=%s src_step=%s", path, src_step)

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
        st.setdefault("history", []).append({"status": "Verified", "step": self.step})
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

        # Warn on unrecognised tool names
        _known_tools = {"Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch",
                        "WebSearch", "NotebookEdit", "Computer"}
        if tool_val:
            unknown = [t for t in tool_val.split(",") if t.strip() not in _known_tools]
            if unknown:
                print(f"  {YELLOW}Warning: unrecognised tool(s): {', '.join(unknown)}{RESET}")

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

    def _cmd_rename(self, args: str) -> None:
        """rename <ST> <text> — update a subtask's description inline."""
        parts = args.strip().split(" ", 1)
        st_target = parts[0].upper() if parts and parts[0] else ""
        if not st_target or len(parts) < 2 or not parts[1].strip():
            print(f"  Usage: rename <subtask> <new description>")
            return
        new_desc = parts[1].strip()
        found = self._find_subtask(st_target)
        if not found:
            print(f"  {YELLOW}Subtask '{st_target}' not found.{RESET}")
            return
        task_name, _, _, _, st = found
        old = (st.get("description") or "")[:40]
        st["description"] = new_desc
        print(f"  {GREEN}Renamed {st_target} ({task_name}): {new_desc[:60]}{RESET}")
        if old:
            print(f"  {DIM}Was: {old}{RESET}")

    def _cmd_timeline(self, args: str) -> None:
        """timeline <subtask> — print the full status history of a subtask."""
        st_target = args.strip().upper()
        if not st_target:
            print(f"  Usage: timeline <subtask_name>")
            return
        found = self._find_subtask(st_target)
        if not found:
            print(f"  {YELLOW}Subtask '{st_target}' not found.{RESET}")
            return
        task_name, _, _, _, st = found
        history = st.get("history", [])
        status = st.get("status", "Pending")
        print(f"\n  {BOLD}{CYAN}Timeline for {st_target} ({task_name}){RESET}")
        print(f"  Current: {format_status(status)}")
        if not history:
            print(f"  {DIM}No transitions recorded (subtask may predate history tracking).{RESET}")
        else:
            print(f"  {DIM}{'─' * 40}{RESET}")
            # Always show initial Pending
            print(f"    {DIM}Step 0{RESET}  {format_status('Pending')}  (initial)")
            for h in history:
                step = h.get("step", "?")
                hstatus = h.get("status", "?")
                print(f"    {DIM}Step {step}{RESET}  {format_status(hstatus)}")
        print()

    def _cmd_log(self, args: str) -> None:
        """log [subtask] — show journal entries, optionally filtered by subtask name."""
        import re as _re
        target = args.strip().upper()
        if not os.path.exists(JOURNAL_PATH):
            print(f"  {YELLOW}No journal file found.{RESET}")
            return
        try:
            content = open(JOURNAL_PATH, "r", encoding="utf-8").read()
        except Exception as exc:
            print(f"  {RED}Could not read journal: {exc}{RESET}")
            return
        blocks = _re.split(r"(?=^## )", content, flags=_re.MULTILINE)
        entries: list = []
        for block in blocks:
            if not block.strip().startswith("## "):
                continue
            m = _re.match(r"^## (\w+) · (Task \d+) / (Branch \w+) · Step (\d+)", block)
            if not m:
                continue
            st_name = m.group(1)
            if target and st_name.upper() != target:
                continue
            body = block[m.end():].strip()
            body = _re.sub(r"^\*\*Prompt:\*\*.*\n\n?", "", body).strip().rstrip("-").strip()
            entries.append((st_name, m.group(2), m.group(3), int(m.group(4)), body[:120]))
        label = f" for {target}" if target else ""
        print(f"\n  {BOLD}{CYAN}Journal{label}{RESET}  ({len(entries)} entr{'ies' if len(entries) != 1 else 'y'})")
        print(f"  {'─' * 50}")
        if not entries:
            print(f"  {DIM}No entries found.{RESET}")
        else:
            for st, task, branch, step, body in entries[-15:]:
                print(f"  {DIM}Step {step:<4}{RESET} {CYAN}{st:<5}{RESET} {DIM}{task} / {branch}{RESET}")
                if body:
                    print(f"    {DIM}{body}{RESET}")
        print()

    def _cmd_branches(self, args: str) -> None:
        """branches [Task N] — list all branches for a task with subtask counts and statuses."""
        target = args.strip()
        if not target:
            # Show all tasks with branch counts
            print(f"\n  {BOLD}{CYAN}Branches Overview{RESET}")
            print(f"  {'─' * 60}")
            for task_name, task_data in self.dag.items():
                branches = task_data.get("branches", {})
                print(f"  {BOLD}{task_name}{RESET}  ({len(branches)} branch{'es' if len(branches) != 1 else ''})")
                for br_name, br_data in branches.items():
                    subs = br_data.get("subtasks", {})
                    v = sum(1 for s in subs.values() if s.get("status") == "Verified")
                    r = sum(1 for s in subs.values() if s.get("status") == "Running")
                    p = len(subs) - v - r
                    bar = f"{GREEN}{v}✓{RESET} {CYAN}{r}▶{RESET} {YELLOW}{p}●{RESET}" if subs else f"{DIM}empty{RESET}"
                    print(f"    {CYAN}{br_name:<14}{RESET} {len(subs)} subtasks  {bar}")
            print()
            return
        # Normalise: "0" → "Task 0", "Task 0" kept as-is
        if target.isdigit():
            target = f"Task {target}"
        task_data = self.dag.get(target)
        if not task_data:
            print(f"  {YELLOW}Task '{target}' not found.{RESET}")
            return
        branches = task_data.get("branches", {})
        print(f"\n  {BOLD}{CYAN}{target} — Branches{RESET}  ({len(branches)})")
        print(f"  {'─' * 60}")
        for br_name, br_data in branches.items():
            subs = br_data.get("subtasks", {})
            v = sum(1 for s in subs.values() if s.get("status") == "Verified")
            r = sum(1 for s in subs.values() if s.get("status") == "Running")
            rv = sum(1 for s in subs.values() if s.get("status") == "Review")
            p = len(subs) - v - r - rv
            print(f"  {BOLD}{br_name}{RESET}  ({len(subs)} subtasks: "
                  f"{GREEN}{v}✓{RESET} {CYAN}{r}▶{RESET} {YELLOW}{p}●{RESET}"
                  f"{f' {YELLOW}{rv}⏳{RESET}' if rv else ''})")
            for st_name, st_data in subs.items():
                print(f"    {CYAN}{st_name:<5}{RESET} {format_status(st_data.get('status', 'Pending'))}"
                      f"  {DIM}{(st_data.get('description') or '')[:50]}{RESET}")
        print()

    def _cmd_search(self, args: str) -> None:
        """search <text> — find subtasks matching keyword in description or output."""
        query = args.strip().lower()
        if not query:
            print(f"  Usage: search <keyword>")
            return
        matches: list = []
        for task_name, task_data in self.dag.items():
            for branch_data in task_data.get("branches", {}).values():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    desc = (st_data.get("description") or "").lower()
                    out = (st_data.get("output") or "").lower()
                    if query in desc or query in out or query in st_name.lower():
                        matches.append((st_name, task_name, st_data.get("status", "Pending"),
                                        (st_data.get("description") or "")[:60]))
        print(f"\n  {BOLD}{CYAN}Search: '{args.strip()}'{RESET}  ({len(matches)} match{'es' if len(matches) != 1 else ''})")
        print(f"  {'─' * 50}")
        if not matches:
            print(f"  {DIM}No matches found.{RESET}")
        else:
            for st_name, task_name, status, desc in matches:
                print(f"  {CYAN}{st_name:<5}{RESET} {format_status(status)}  {DIM}{task_name} — {desc}{RESET}")
        print()

    def _cmd_filter(self, args: str) -> None:
        """filter <status> — show only subtasks matching a status."""
        target = args.strip().capitalize()
        valid = ("Verified", "Running", "Pending", "Review")
        if target not in valid:
            print(f"  Usage: filter <{' | '.join(valid)}>")
            return
        matches: list = []
        for task_name, task_data in self.dag.items():
            for branch_data in task_data.get("branches", {}).values():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    if st_data.get("status", "Pending") == target:
                        desc = (st_data.get("description") or "")[:50]
                        matches.append((st_name, task_name, desc))
        color = {"Verified": GREEN, "Running": CYAN, "Pending": YELLOW, "Review": YELLOW}.get(target, WHITE)
        print(f"\n  {BOLD}{color}{target} Subtasks{RESET}  ({len(matches)})")
        print(f"  {'─' * 50}")
        if not matches:
            print(f"  {DIM}None.{RESET}")
        else:
            for st_name, task_name, desc in matches:
                print(f"  {CYAN}{st_name:<5}{RESET} {DIM}{task_name} — {desc}{RESET}")
        print()

    def _cmd_graph(self) -> None:
        """graph — ASCII dependency graph with progress counters."""
        sym = {"Verified": "✅", "Running": "▶️", "Review": "⏸", "Pending": "⏳", "Blocked": "🔒"}
        print(f"\n  {BOLD}{CYAN}DAG Graph{RESET}")
        print(f"  {'─' * 50}")
        task_names = list(self.dag.keys())
        for t_name in task_names:
            t_data = self.dag[t_name]
            t_status = t_data.get("status", "Pending")
            icon = sym.get(t_status, "⏳")
            deps = t_data.get("depends_on", [])
            branches = t_data.get("branches", {})
            n_st = sum(len(b.get("subtasks", {})) for b in branches.values())
            n_v = sum(1 for b in branches.values()
                      for s in b.get("subtasks", {}).values()
                      if s.get("status") == "Verified")
            line = f"  {icon} {t_name} [{n_v}/{n_st}]"
            if deps:
                line += f"  {DIM}← {', '.join(deps)}{RESET}"
            print(line)
            dependents = [tn for tn in task_names
                          if t_name in self.dag[tn].get("depends_on", [])]
            for d in dependents:
                print(f"     └──▶ {d}")
        print(f"  {'─' * 50}\n")

    def _cmd_priority(self) -> None:
        """priority — show the planner's cached priority queue."""
        queue = self._priority_cache
        print(f"\n  {BOLD}{CYAN}Priority Queue{RESET}  ({len(queue)} candidates, step {self.step})")
        print(f"  {'─' * 60}")
        if not queue:
            print(f"  {DIM}Empty — all subtasks are Verified or blocked.{RESET}")
        else:
            for i, (task_name, branch_name, st_name, risk) in enumerate(queue[:20]):
                st_data = self.dag[task_name]["branches"][branch_name]["subtasks"][st_name]
                status = st_data.get("status", "Pending")
                color = STATUS_COLORS.get(status, WHITE)
                marker = f"{BOLD}▶{RESET} " if i < self.executor.max_per_step else "  "
                print(f"  {marker}{CYAN}{st_name:<5}{RESET} {color}{status:<9}{RESET} "
                      f"risk={YELLOW}{risk:<5}{RESET} {DIM}{task_name} / {branch_name}{RESET}")
            if len(queue) > 20:
                print(f"  {DIM}… and {len(queue) - 20} more{RESET}")
        print(f"  {'─' * 60}")
        print(f"  {DIM}Top {self.executor.max_per_step} (▶) will execute next step{RESET}\n")

    def _cmd_stalled(self) -> None:
        """stalled — show subtasks stuck longer than STALL_THRESHOLD."""
        stalled = self.healer.find_stalled(self.dag, self.step)
        print(f"\n  {BOLD}{YELLOW}Stalled Subtasks{RESET}  (threshold: {STALL_THRESHOLD} steps)")
        print(f"  {'─' * 55}")
        if not stalled:
            print(f"  {DIM}None — all Running subtasks are progressing normally.{RESET}")
        else:
            for task_name, branch_name, st_name, age in stalled:
                desc = (self.dag[task_name]["branches"][branch_name]["subtasks"][st_name]
                        .get("description") or "")[:40]
                print(f"  {YELLOW}{st_name:<5}{RESET} stalled {RED}{age}{RESET} steps  "
                      f"{DIM}{task_name} — {desc}{RESET}")
        print(f"  {'─' * 55}")
        print(f"  {DIM}SelfHealer auto-resets after {STALL_THRESHOLD} steps{RESET}\n")

    def _cmd_heal(self, args: str) -> None:
        """heal <subtask> — manually reset a Running subtask to Pending (SelfHealer action)."""
        st_target = args.strip().upper()
        if not st_target:
            print(f"  Usage: heal <subtask_name>")
            return
        found = self._find_subtask(st_target)
        if not found:
            print(f"  {YELLOW}Subtask '{st_target}' not found.{RESET}")
            return
        task_name, task_data, branch_name, branch_data, st = found
        prev = st.get("status", "Pending")
        if prev != "Running":
            print(f"  {YELLOW}{st_target} is {prev}, not Running — nothing to heal.{RESET}")
            return
        st["status"]      = "Pending"
        st["shadow"]      = "Pending"
        st["last_update"] = self.step
        add_memory_snapshot(self.memory_store, branch_name, f"{st_target}_manual_heal", self.step)
        self.healer.healed_total += 1
        print(f"  {GREEN}↻ {st_target} ({task_name}) reset to Pending (was Running).{RESET}")
        self.display.render(self.dag, self.memory_store, self.step,
                            self.alerts, self.meta.forecast(self.dag))

    def _cmd_agents(self) -> None:
        """agents — show agent stats (healer count, planner cache, executor, meta)."""
        cache_len = len(self._priority_cache)
        cache_age = self.step - self._last_priority_step
        print(f"\n  {BOLD}{CYAN}Agent Statistics{RESET}  (step {self.step})")
        print(f"  {'─' * 55}")
        print(f"  {CYAN}Planner{RESET}       cache: {cache_len} candidates, age: {cache_age} steps")
        print(f"                weights: stall={self.planner.w_stall:.2f}  "
              f"staleness={self.planner.w_staleness:.2f}  shadow={self.planner.w_shadow:.2f}")
        print(f"  {CYAN}Executor{RESET}      max_per_step: {self.executor.max_per_step}  "
              f"verify_prob: {self.executor.verify_prob:.2f}")
        print(f"  {CYAN}SelfHealer{RESET}    healed: {self.healer.healed_total}  "
              f"threshold: {self.healer.stall_threshold}")
        stalled_now = len(self.healer.find_stalled(self.dag, self.step))
        if stalled_now:
            print(f"                {YELLOW}currently stalled: {stalled_now}{RESET}")
        print(f"  {CYAN}ShadowAgent{RESET}   tracking {len(self.shadow.expected)} subtasks")
        print(f"  {CYAN}MetaOptimizer{RESET} history: {len(self.meta._history)} entries  "
              f"heal_rate: {self.meta.heal_rate:.2f}  verify_rate: {self.meta.verify_rate:.2f}")
        print(f"                forecast: {self.meta.forecast(self.dag)}")
        print(f"  {'─' * 55}\n")

    def _cmd_forecast(self) -> None:
        """forecast — detailed completion forecast with ETA, rate trends, projected finish."""
        stats = dag_stats(self.dag)
        total, verified = stats["total"], stats["verified"]
        remaining = total - verified
        pct = verified / total * 100 if total else 0
        print(f"\n  {BOLD}{CYAN}Completion Forecast{RESET}  (step {self.step})")
        print(f"  {'─' * 55}")
        print(f"  {CYAN}Progress{RESET}      {verified}/{total} verified ({pct:.1f}%)")
        print(f"  {CYAN}Remaining{RESET}     {remaining} subtasks")
        # Per-status breakdown
        running = sum(1 for t in self.dag.values()
                      for b in t.get("branches", {}).values()
                      for s in b.get("subtasks", {}).values()
                      if s.get("status") == "Running")
        pending = sum(1 for t in self.dag.values()
                      for b in t.get("branches", {}).values()
                      for s in b.get("subtasks", {}).values()
                      if s.get("status") == "Pending")
        review = sum(1 for t in self.dag.values()
                     for b in t.get("branches", {}).values()
                     for s in b.get("subtasks", {}).values()
                     if s.get("status") == "Review")
        print(f"  {CYAN}Breakdown{RESET}     {GREEN}{verified} ✓{RESET}  {CYAN}{running} ▶{RESET}  "
              f"{YELLOW}{pending} ⏳{RESET}  {MAGENTA}{review} ⏸{RESET}")
        # Rate trends from MetaOptimizer
        vr = self.meta.verify_rate
        hr = self.meta.heal_rate
        print(f"  {CYAN}Verify rate{RESET}   {vr:.2f} /step (last 10 steps)")
        print(f"  {CYAN}Heal rate{RESET}     {hr:.2f} /step (last 10 steps)")
        if vr > 0:
            eta_steps = remaining / vr
            print(f"  {CYAN}ETA{RESET}           ~{eta_steps:.0f} steps remaining")
            if self.executor.max_per_step > 0:
                mins = eta_steps * AUTO_STEP_DELAY / 60
                print(f"  {CYAN}Wall time{RESET}     ~{mins:.1f} min at current pace")
        else:
            print(f"  {CYAN}ETA{RESET}           {DIM}insufficient data{RESET}")
        # Progress bar
        bar = make_bar(pct / 100, 40) if total else "N/A"
        print(f"  {CYAN}Progress{RESET}      {bar}")
        print(f"  {'─' * 55}\n")

    def _cmd_tasks(self) -> None:
        """tasks — per-task summary table (status, branches, verified/total, deps)."""
        task_names = list(self.dag.keys())
        print(f"\n  {BOLD}{CYAN}Task Summary{RESET}  ({len(task_names)} tasks, step {self.step})")
        print(f"  {'─' * 65}")
        print(f"  {'Task':<12} {'Status':<10} {'Branches':>8} {'Verified':>10} {'Total':>6} {'Deps':>5}")
        print(f"  {'─' * 65}")
        for t_name in task_names:
            t = self.dag[t_name]
            status = t.get("status", "Pending")
            branches = t.get("branches", {})
            n_branches = len(branches)
            n_total = sum(len(b.get("subtasks", {})) for b in branches.values())
            n_verified = sum(1 for b in branches.values()
                            for s in b.get("subtasks", {}).values()
                            if s.get("status") == "Verified")
            deps = t.get("depends_on", [])
            n_deps = len(deps)
            color = STATUS_COLORS.get(status, WHITE)
            pct = round(n_verified / n_total * 100) if n_total else 0
            label = t_name[:11]
            print(f"  {label:<12} {color}{status:<10}{RESET} {n_branches:>8} "
                  f"{n_verified:>6}/{n_total:<4} {pct:>3}%{n_deps:>5}")
        print(f"  {'─' * 65}\n")

    def _cmd_history(self, args: str) -> None:
        """history [N] — show the last N status transitions across all subtasks (default 20)."""
        limit = 20
        if args.strip().isdigit():
            limit = int(args.strip())
        events: list = []
        for task_name, task_data in self.dag.items():
            for branch_data in task_data.get("branches", {}).values():
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    for h in st_data.get("history", []):
                        events.append((h.get("step", 0), st_name, task_name, h.get("status", "?")))
        events.sort(key=lambda x: x[0], reverse=True)
        events = events[:limit]
        print(f"\n  {BOLD}{CYAN}Recent Activity (last {limit}){RESET}")
        print(f"  {'─' * 50}")
        if not events:
            print(f"  {DIM}No history recorded yet.{RESET}")
        else:
            for step, st_name, task_name, status in events:
                print(f"  {DIM}Step {step:<4}{RESET} {CYAN}{st_name:<5}{RESET} {format_status(status)}  {DIM}({task_name}){RESET}")
        print()

    def _cmd_pause(self) -> None:
        """pause — write pause_trigger to pause a running auto loop."""
        p = os.path.join(_HERE, "state", "pause_trigger")
        if os.path.exists(p):
            print(f"  {YELLOW}Already paused.{RESET}")
            return
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write("1")
        print(f"  {YELLOW}Pause signal written — auto-run will pause after the current step.{RESET}")

    def _cmd_resume(self) -> None:
        """resume — remove pause_trigger to resume a paused auto loop."""
        p = os.path.join(_HERE, "state", "pause_trigger")
        if not os.path.exists(p):
            print(f"  {YELLOW}Not paused.{RESET}")
            return
        try:
            os.remove(p)
        except OSError:
            pass
        print(f"  {GREEN}Resumed — auto-run will continue.{RESET}")

    def _cmd_stats(self) -> None:
        """stats — per-task breakdown: subtasks verified, avg steps to complete."""
        print(f"\n  {BOLD}{CYAN}Per-Task Statistics{RESET}")
        print(f"  {'─' * 60}")
        print(f"  {BOLD}{'Task':<12} {'Verified':>8} {'Total':>6} {'Pct':>6} {'Avg Steps':>10}{RESET}")
        print(f"  {'─' * 60}")
        grand_v = grand_t = 0
        all_durations: list = []
        for task_name, task_data in self.dag.items():
            t_verified = t_total = 0
            durations: list = []
            for branch_data in task_data.get("branches", {}).values():
                for st_data in branch_data.get("subtasks", {}).values():
                    t_total += 1
                    if st_data.get("status") == "Verified":
                        t_verified += 1
                        history = st_data.get("history", [])
                        if len(history) >= 2:
                            first_step = history[0].get("step", 0)
                            last_step = history[-1].get("step", 0)
                            durations.append(last_step - first_step)
            pct = round(t_verified / t_total * 100, 1) if t_total else 0
            avg = f"{sum(durations) / len(durations):.1f}" if durations else "—"
            color = GREEN if t_verified == t_total and t_total > 0 else CYAN if t_verified > 0 else WHITE
            print(f"  {color}{task_name:<12}{RESET} {t_verified:>8} {t_total:>6} {pct:>5}% {avg:>10}")
            grand_v += t_verified
            grand_t += t_total
            all_durations.extend(durations)
        print(f"  {'─' * 60}")
        g_pct = round(grand_v / grand_t * 100, 1) if grand_t else 0
        g_avg = f"{sum(all_durations) / len(all_durations):.1f}" if all_durations else "—"
        print(f"  {BOLD}{'TOTAL':<12}{RESET} {grand_v:>8} {grand_t:>6} {g_pct:>5}% {g_avg:>10}")
        print()

    def _cmd_diff(self) -> None:
        """diff — show what changed in the last step vs the .1 backup."""
        backup_path = f"{STATE_PATH}.1"
        if not os.path.exists(backup_path):
            print(f"  {YELLOW}No backup to diff against (run at least 2 saves).{RESET}")
            return
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except Exception as exc:
            print(f"  {RED}Could not read backup: {exc}{RESET}")
            return

        old_dag = old.get("dag", {})
        new_dag = self.dag
        old_step = old.get("step", 0)
        changes = []

        for task_name, task_data in new_dag.items():
            old_task = old_dag.get(task_name, {})
            for branch_name, branch_data in task_data.get("branches", {}).items():
                old_branch = old_task.get("branches", {}).get(branch_name, {})
                for st_name, st_data in branch_data.get("subtasks", {}).items():
                    old_st = old_branch.get("subtasks", {}).get(st_name, {})
                    old_status = old_st.get("status", "?")
                    new_status = st_data.get("status", "?")
                    if old_status != new_status:
                        out = st_data.get("output", "")
                        preview = f" — {out[:60]}" if out and new_status in ("Verified", "Review") else ""
                        changes.append(
                            f"    {CYAN}{st_name:<5}{RESET} "
                            f"{format_status(old_status)} → {format_status(new_status)}"
                            f"{DIM}{preview}{RESET}"
                        )

        print(f"\n  {BOLD}Diff: step {old_step} → {self.step}{RESET}")
        if changes:
            for c in changes:
                print(c)
        else:
            print(f"  {DIM}No subtask status changes.{RESET}")
        print()

    def _cmd_help(self) -> None:
        W = 60
        print(f"\n  {BOLD}{CYAN}Solo Builder — Commands{RESET}")
        print(f"  {'─' * W}")
        rows = [
            ("run",                    "Execute one agent pipeline step"),
            ("auto [N]",               "Run N steps automatically (default: until done)"),
            ("pause",                  "Pause a running auto loop after current step"),
            ("resume",                 "Resume a paused auto loop"),
            ("snapshot",               "Generate a PDF timeline snapshot"),
            ("save",                   "Save current state to disk"),
            ("load",                   "Load last saved state from disk"),
            ("load_backup [1|2|3]",   "Restore from a backup (.1=newest, .3=oldest)"),
            ("undo",                   "Undo last step (restore from .1 backup)"),
            ("diff",                   "Show what changed since last save"),
            ("timeline <ST>",          "Print full status history of a subtask"),
            ("reset",                  "Reset DAG to initial state, clear save"),
            ("status",                 "Show detailed DAG statistics"),
            ("stats",                  "Per-task breakdown (verified, avg steps)"),
            ("history [N]",            "Show last N status transitions (default 20)"),
            ("branches [Task N]",      "List all branches for a task with subtask detail"),
            ("search <text>",          "Find subtasks by keyword (description/output)"),
            ("filter <status>",        "Show only subtasks matching a status"),
            ("graph",                  "ASCII dependency graph with progress counters"),
            ("config",                 "Display all runtime settings"),
            ("priority",               "Show the planner's priority queue (next to execute)"),
            ("stalled",                "Show subtasks stuck longer than STALL_THRESHOLD"),
            ("heal <ST>",              "Manually reset a Running subtask to Pending"),
            ("agents",                 "Show agent stats (healer, planner, executor, meta)"),
            ("forecast",               "Detailed completion forecast with ETA and rate trends"),
            ("tasks",                  "Per-task summary table (status, branches, verified)"),
            ("log [ST]",               "Show journal entries (optionally for one subtask)"),
            ("add_task [spec]",        "Append a new Task; inline spec skips the prompt"),
            ("add_branch <Task N> [spec]", "Add a new branch; inline spec skips the prompt"),
            ("export",                  "Write all Claude outputs to solo_builder_outputs.md"),
            ("depends",                 "Print dependency graph"),
            ("depends <T> <dep>",      "Add dependency: Task T depends on dep"),
            ("undepends <T> <dep>",    "Remove a dependency from Task T"),
            ("rename <ST> <text>",     "Update a subtask's description inline"),
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
    def start(self, headless: bool = False, auto_steps: Optional[int] = None,
              no_resume: bool = False, output_format: str = "text") -> None:
        """Run the CLI loop.  In headless mode: skip prompts, auto-run, then exit."""
        if not no_resume and os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                saved_step = saved.get("step", 0)
                saved_v    = dag_stats(saved.get("dag", {})).get("verified", 0)
                saved_t    = dag_stats(saved.get("dag", {})).get("total", 0)
                print(f"  {CYAN}Saved state found: step {saved_step}, "
                      f"{saved_v}/{saved_t} verified.{RESET}")
                if headless:
                    ok = self.load_state()
                    if ok:
                        print(f"  {GREEN}Resumed from step {self.step}.{RESET}")
                else:
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

        if headless:
            self._cmd_auto(str(auto_steps) if auto_steps is not None else "")
            self.save_state()
            return

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
        "║      SOLO BUILDER — AI AGENT CLI  v2.1               ║",
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


def _fire_completion(steps: int, verified: int, total: int) -> None:
    """Non-blocking: POST webhook and/or Windows toast on pipeline completion."""
    import threading

    def _webhook() -> None:
        if not WEBHOOK_URL:
            return
        try:
            import urllib.request, urllib.error
            payload = json.dumps({
                "event": "complete", "steps": steps,
                "verified": verified, "total": total,
            }).encode()
            req = urllib.request.Request(
                WEBHOOK_URL, data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            # Log failures — silent to the user but auditable
            try:
                import datetime
                _log = os.path.join(_HERE, "state", "webhook_errors.log")
                with open(_log, "a", encoding="utf-8") as _wf:
                    _wf.write(
                        f"{datetime.datetime.now(datetime.timezone.utc).isoformat()} "
                        f"POST {WEBHOOK_URL!r} failed: {exc}\n"
                    )
            except Exception:
                pass

    def _notify() -> None:
        try:
            msg = f"Solo Builder: {verified}/{total} verified in {steps} steps"
            subprocess.Popen(
                ["powershell.exe", "-WindowStyle", "Hidden", "-Command",
                 f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null;'
                 f'[System.Windows.Forms.MessageBox]::Show("{msg}", "Solo Builder Complete")'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    threading.Thread(target=_webhook, daemon=True).start()
    threading.Thread(target=_notify,  daemon=True).start()


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


def main() -> None:
    """Entry point — interactive or headless."""
    # ── status subcommand (fast path, no lock needed) ────────────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        _state_path = os.path.join(_HERE, "state", "solo_builder_state.json")
        if not os.path.exists(_state_path):
            print(json.dumps({"error": "no state file"}))
            return
        with open(_state_path) as _f:
            _state = json.load(_f)
        _s    = dag_stats(_state.get("dag", {}))
        _step = _state.get("step", 0)
        _pct  = round(_s["verified"] / _s["total"] * 100, 1) if _s["total"] else 0.0
        print(json.dumps({
            "step":     _step,
            "verified": _s["verified"],
            "running":  _s["running"],
            "pending":  _s["pending"],
            "total":    _s["total"],
            "pct":      _pct,
            "complete": _s["verified"] == _s["total"],
        }))
        return

    # ── watch subcommand (live progress bar, no lock needed) ─────────────────
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        _state_path = os.path.join(_HERE, "state", "solo_builder_state.json")
        _interval   = 2.0
        if len(sys.argv) > 2:
            try:
                _interval = float(sys.argv[2])
            except ValueError:
                pass
        print(f"  Watching pipeline every {_interval}s  (Ctrl+C to stop)", flush=True)
        try:
            while True:
                if not os.path.exists(_state_path):
                    print("\r  No state file — start the CLI first.                    ",
                          end="", flush=True)
                else:
                    try:
                        with open(_state_path) as _f:
                            _wstate = json.load(_f)
                    except (json.JSONDecodeError, OSError):
                        time.sleep(_interval)
                        continue
                    _s    = dag_stats(_wstate.get("dag", {}))
                    _step = _wstate.get("step", 0)
                    _pct  = round(_s["verified"] / _s["total"] * 100, 1) if _s["total"] else 0.0
                    _bar  = ("=" * int(_pct / 5)).ljust(20, "-")
                    if _s["verified"] == _s["total"]:
                        print(f"\r  {GREEN}Complete!{RESET} "
                              f"{_s['verified']}/{_s['total']} verified in {_step} steps.            ")
                        break
                    print(
                        f"\r  Step {_step:3d}  [{_bar}]  "
                        f"{GREEN}{_s['verified']:3d}✓{RESET}  "
                        f"{CYAN}{_s['running']:2d}▶{RESET}  "
                        f"{YELLOW}{_s['pending']:3d}●{RESET}  "
                        f"{_pct:5.1f}%",
                        end="", flush=True,
                    )
                time.sleep(_interval)
        except KeyboardInterrupt:
            print()
        return

    # ── .env loader (no external dependency) ────────────────────────────────
    _env_path = os.path.join(_HERE, ".env")
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

    # ── Argument parsing ─────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(prog="solo-builder", add_help=True)
    parser.add_argument(
        "--headless", action="store_true",
        help="Non-interactive mode: auto-run then exit (no prompts).",
    )
    parser.add_argument(
        "--auto", type=int, metavar="N", default=None,
        help="Steps to run in headless mode (omit for full pipeline).",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Ignore saved state and start a fresh pipeline.",
    )
    parser.add_argument(
        "--output-format", choices=["text", "json"], default="text",
        help="'json' sends final stats as JSON to stdout; all other output goes to stderr.",
    )
    parser.add_argument(
        "--webhook", metavar="URL", default=None,
        help="POST completion JSON to this URL (overrides WEBHOOK_URL in settings).",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress all display output (headless only). Combine with --output-format json "
             "for completely silent runs where only the JSON result reaches stdout.",
    )
    parser.add_argument(
        "--export", action="store_true",
        help="After the run, write all Claude outputs to solo_builder_outputs.md.",
    )
    args = parser.parse_args()

    # ── Apply flag overrides ─────────────────────────────────────────────────
    if args.webhook:
        global WEBHOOK_URL
        WEBHOOK_URL = args.webhook

    _json_mode  = args.headless and args.output_format == "json"
    _quiet_mode = args.headless and args.quiet
    _null_fh    = None
    if _quiet_mode:
        _null_fh   = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = _null_fh         # silence stderr first
    if _json_mode:
        sys.stdout = sys.stderr       # ANSI display → (possibly devnull) stderr; JSON → real stdout

    # ── Run ──────────────────────────────────────────────────────────────────
    _LOCK_PATH  = os.path.join(_HERE, "state", "solo_builder.lock")
    _STOP_PATH  = os.path.join(_HERE, "state", "stop_trigger")
    _RUN_PATH   = os.path.join(_HERE, "state", "run_trigger")
    _AT_PATH    = os.path.join(_HERE, "state", "add_task_trigger.json")
    _AB_PATH    = os.path.join(_HERE, "state", "add_branch_trigger.json")
    _PB_PATH    = os.path.join(_HERE, "state", "prioritize_branch_trigger.json")
    _D_PATH     = os.path.join(_HERE, "state", "describe_trigger.json")
    _T_PATH     = os.path.join(_HERE, "state", "tools_trigger.json")
    _R_PATH     = os.path.join(_HERE, "state", "reset_trigger")
    _SNAP_PATH  = os.path.join(_HERE, "state", "snapshot_trigger")
    _SET_PATH   = os.path.join(_HERE, "state", "set_trigger.json")
    _DEP_PATH   = os.path.join(_HERE, "state", "depends_trigger.json")
    _UDEP_PATH  = os.path.join(_HERE, "state", "undepends_trigger.json")
    _UNDO_PATH  = os.path.join(_HERE, "state", "undo_trigger")
    _PAUSE_PATH = os.path.join(_HERE, "state", "pause_trigger")
    _HEAL_PATH  = os.path.join(_HERE, "state", "heal_trigger.json")
    os.makedirs(os.path.join(_HERE, "state"), exist_ok=True)
    _setup_logging()
    logger.info("startup version=2.1.50 headless=%s auto=%s", args.headless, args.auto)
    # Clear stale triggers from previous runs
    _DAGIMPORT_PATH = os.path.join(_HERE, "state", "dag_import_trigger.json")
    for _stale in (_STOP_PATH, _RUN_PATH, _AT_PATH, _AB_PATH, _PB_PATH,
                   _D_PATH, _T_PATH, _R_PATH, _SNAP_PATH, _SET_PATH,
                   _DEP_PATH, _UDEP_PATH, _UNDO_PATH, _PAUSE_PATH, _HEAL_PATH,
                   _DAGIMPORT_PATH):
        try:
            os.remove(_stale)
        except FileNotFoundError:
            pass
    _acquire_lock(_LOCK_PATH)
    cli = None

    # Graceful SIGTERM handler — save state then exit cleanly
    import signal as _signal
    def _sigterm_handler(signum, frame):
        if cli is not None:
            try:
                cli.save_state(silent=True)
            except Exception:
                pass
        _release_lock(_LOCK_PATH)
        sys.exit(0)
    _signal.signal(_signal.SIGTERM, _sigterm_handler)

    try:
        _splash()
        cli = SoloBuilderCLI()
        cli.start(
            headless=args.headless,
            auto_steps=args.auto,
            no_resume=args.no_resume,
        )
    except Exception as _exc:
        logger.error("unhandled_exception error=%s", _exc, exc_info=True)
        raise
    finally:
        if cli is not None:
            logger.info("shutdown step=%d", cli.step)
        _export_path, _export_count = (None, 0)
        if args.export and cli is not None:
            _export_path, _export_count = cli._cmd_export()
        _release_lock(_LOCK_PATH)
        if cli is not None:
            _append_cache_session_stats(
                getattr(cli.executor.anthropic, "cache", None),
                cli.step,
            )
        if _quiet_mode:
            sys.stderr = sys.__stderr__
            if _null_fh:
                _null_fh.close()
        if _json_mode:
            sys.stdout = sys.__stdout__
            if cli is not None:
                stats = dag_stats(cli.dag)
                out = {
                    "steps":    cli.step,
                    "verified": stats["verified"],
                    "total":    stats["total"],
                    "complete": stats["verified"] == stats["total"],
                }
                if args.export:
                    out["export"] = {"path": _export_path, "count": _export_count}
                print(json.dumps(out))


if __name__ == "__main__":
    main()
