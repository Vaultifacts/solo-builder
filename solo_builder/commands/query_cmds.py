"""Read-only query commands for SoloBuilderCLI."""
import os
import json
from utils.helper_functions import (
    dag_stats, branch_stats, shadow_stats,
    format_status, BOLD, RESET, GREEN, YELLOW, CYAN, DIM, RED, MAGENTA, WHITE,
    STATUS_COLORS,
)


class QueryCommandsMixin:
    """Mixin: read-only query commands."""

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
        _st = self._runtime_cfg["STALL_THRESHOLD"]
        print(f"\n  {BOLD}{YELLOW}Stalled Subtasks{RESET}  (threshold: {_st} steps)")
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
        print(f"  {DIM}SelfHealer auto-resets after {_st} steps{RESET}\n")

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
                mins = eta_steps * self._runtime_cfg["AUTO_STEP_DELAY"] / 60
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
            ("cache",                  "Show response cache hit/miss stats"),
            ("cache clear",            "Show cache stats then wipe all entries"),
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

