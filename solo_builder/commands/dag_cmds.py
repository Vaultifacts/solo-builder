"""DAG mutation and management commands for SoloBuilderCLI."""
import copy
import json
import os
import shutil
import sys
import time
from utils.helper_functions import (
    dag_stats, validate_dag, format_status, BOLD, RESET, GREEN, YELLOW, CYAN, DIM, RED, BLUE, MAGENTA,
)


class DagCommandsMixin:
    """Mixin: DAG mutation and management commands."""

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

    def _cmd_cache(self, clear: bool = False) -> None:
        """cache [clear] — show response cache stats; optionally wipe all entries."""
        cache = getattr(self.executor.anthropic, "cache", None)
        if cache is None:
            print(f"  {YELLOW}Cache is disabled (NOCACHE=1 or no cache configured).{RESET}")
            return
        s = cache.stats()
        total = s["hits"] + s["misses"]
        hit_rate = f"{s['hits'] / total * 100:.1f}%" if total else "n/a"
        cum_total = s["cumulative_hits"] + s["cumulative_misses"]
        cum_rate = f"{s['cumulative_hits'] / cum_total * 100:.1f}%" if cum_total else "n/a"
        print(f"\n  {BOLD}{CYAN}Response Cache{RESET}")
        print(f"  {'─' * 44}")
        print(f"  {'Hits this session':<24} {s['hits']}")
        print(f"  {'Misses this session':<24} {s['misses']}")
        print(f"  {'Hit rate (session)':<24} {hit_rate}")
        print(f"  {'─' * 44}")
        print(f"  {'Hits all sessions':<24} {s['cumulative_hits']:,}")
        print(f"  {'Misses all sessions':<24} {s['cumulative_misses']:,}")
        print(f"  {'Hit rate (all-time)':<24} {cum_rate}")
        print(f"  {'─' * 44}")
        print(f"  {'Entries on disk':<24} {s['size']}")
        print(f"  {'Est. tokens saved':<24} {s['estimated_tokens_saved']:,}")
        print(f"  {'─' * 44}")
        if clear:
            deleted = cache.clear()
            print(f"  {YELLOW}Cleared {deleted} cache entries.{RESET}")
        print()

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

