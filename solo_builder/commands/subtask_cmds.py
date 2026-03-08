"""Subtask commands for SoloBuilderCLI."""
from utils.helper_functions import (
    format_status, BOLD, RESET, GREEN, YELLOW, CYAN, DIM, RED,
)


class SubtaskCommandsMixin:
    """Mixin: subtask manipulation commands."""

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

