"""TerminalDisplay: full-screen DAG renderer."""
from typing import Any, Dict, List, Optional
from utils.helper_functions import (
    make_bar, dag_stats, branch_stats, shadow_stats,
    memory_depth, format_status, format_shadow,
    YELLOW, GREEN, CYAN, BLUE, MAGENTA, WHITE, BOLD, DIM, RESET,
    STATUS_COLORS, ALERT_STALLED, BAR_WIDTH,
)

class TerminalDisplay:
    """Renders the full-screen terminal mini-graph."""

    _WIDTH = 72

    def __init__(self, bar_width: int = BAR_WIDTH, stall_threshold: int = 5) -> None:
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
