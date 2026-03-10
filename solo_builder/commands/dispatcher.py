"""Dispatcher and CLI loop for SoloBuilderCLI — extracted from solo_builder_cli.py."""
import os
import json
import sys
import time
from typing import Optional

from utils.helper_functions import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW


class DispatcherMixin:
    """Mixin: handle_command dispatcher and start() CLI loop."""

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

        elif cmd == "cache":
            self._cmd_cache()

        elif cmd == "cache clear":
            self._cmd_cache(clear=True)

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

    def _cmd_set(self, args: str) -> None:
        """set KEY=VALUE — update runtime config."""
        parts = args.split("=", 1)
        if len(parts) != 2:
            bare = args.strip().upper()
            _current: dict = {
                "STALL_THRESHOLD":    str(self._runtime_cfg["STALL_THRESHOLD"]),
                "SNAPSHOT_INTERVAL":  str(self._runtime_cfg["SNAPSHOT_INTERVAL"]),
                "VERBOSITY":          self._runtime_cfg["VERBOSITY"],
                "VERIFY_PROB":        str(self.executor.verify_prob),
                "AUTO_STEP_DELAY":    str(self._runtime_cfg["AUTO_STEP_DELAY"]),
                "AUTO_SAVE_INTERVAL": str(self._runtime_cfg["AUTO_SAVE_INTERVAL"]),
                "CLAUDE_ALLOWED_TOOLS": self._runtime_cfg["CLAUDE_ALLOWED_TOOLS"] or "(none)",
                "ANTHROPIC_MAX_TOKENS": str(self.executor.anthropic.max_tokens),
                "ANTHROPIC_MODEL":    self.executor.anthropic.model,
                "CLAUDE_SUBPROCESS":  "on" if self.executor.claude.available else "off",
                "REVIEW_MODE":        "on" if self.executor.review_mode else "off",
                "WEBHOOK_URL":        self._runtime_cfg["WEBHOOK_URL"] or "(not set)",
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
                self._runtime_cfg["STALL_THRESHOLD"] = v
                self.healer.stall_threshold  = v
                self.planner.stall_threshold = v
                self.display.stall_threshold = v
                print(f"  {GREEN}STALL_THRESHOLD = {v}{RESET}")
                self._persist_setting("STALL_THRESHOLD", v)

            elif key == "SNAPSHOT_INTERVAL":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                self._runtime_cfg["SNAPSHOT_INTERVAL"] = v
                print(f"  {GREEN}SNAPSHOT_INTERVAL = {v}{RESET}")
                self._persist_setting("SNAPSHOT_INTERVAL", v)

            elif key == "VERBOSITY":
                v = val.upper()
                if v not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                    raise ValueError("must be one of DEBUG, INFO, WARNING, ERROR")
                self._runtime_cfg["VERBOSITY"] = v
                print(f"  {GREEN}VERBOSITY = {v}{RESET}")
                self._persist_setting("VERBOSITY", v)

            elif key == "VERIFY_PROB":
                v = float(val)
                if not 0.0 <= v <= 1.0:
                    raise ValueError("must be between 0.0 and 1.0")
                self._runtime_cfg["EXEC_VERIFY_PROB"] = v
                self.executor.verify_prob = v
                print(f"  {GREEN}VERIFY_PROB = {val}{RESET}")
                self._persist_setting("EXECUTOR_VERIFY_PROBABILITY", v)

            elif key == "AUTO_STEP_DELAY":
                v = float(val)
                if v < 0:
                    raise ValueError("must be >= 0")
                self._runtime_cfg["AUTO_STEP_DELAY"] = v
                print(f"  {GREEN}AUTO_STEP_DELAY = {v}s{RESET}")
                self._persist_setting("AUTO_STEP_DELAY", v)

            elif key == "AUTO_SAVE_INTERVAL":
                v = int(val)
                if v < 1:
                    raise ValueError("must be >= 1")
                self._runtime_cfg["AUTO_SAVE_INTERVAL"] = v
                print(f"  {GREEN}AUTO_SAVE_INTERVAL = {v}{RESET}")
                self._persist_setting("AUTO_SAVE_INTERVAL", v)

            elif key == "CLAUDE_ALLOWED_TOOLS":
                self._runtime_cfg["CLAUDE_ALLOWED_TOOLS"] = val
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
                self._runtime_cfg["WEBHOOK_URL"] = val
                # _fire_completion is a module-level function that reads WEBHOOK_URL from
                # solo_builder_cli's namespace — update it there so it sees the new value.
                _sb = sys.modules.get("solo_builder_cli") or sys.modules.get("solo_builder.solo_builder_cli")
                if _sb is not None:
                    _sb.WEBHOOK_URL = val
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
