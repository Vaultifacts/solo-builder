"""Auto-run command for SoloBuilderCLI — extracted from solo_builder_cli.py."""
import os
import time

from config.loader import BAR_WIDTH, DAG_UPDATE_INTERVAL
from utils.trigger_registry import get_default_registry


class AutoCommandsMixin:
    """Mixin: _cmd_auto() auto-run loop with trigger polling."""

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

        _state_dir = os.path.join(_HERE, "state")
        _treg      = get_default_registry()
        try:
            while True:
                self.run_step()
                ran += 1

                stats = dag_stats(self.dag)
                _pct = round(stats["verified"] / stats["total"] * 100, 1) if stats["total"] else 0.0
                _bar = make_bar(stats["verified"], stats["total"], width=BAR_WIDTH)
                _run_tag = f"  {CYAN}{stats['running']} running{RESET}" if stats["running"] else ""
                print(
                    f"\r  {CYAN}Step {self.step:4d}{RESET}  "
                    f"[{_bar}]  "
                    f"{GREEN}{stats['verified']}{RESET}/{stats['total']}  "
                    f"({_pct:.1f}%){_run_tag}",
                    end="", flush=True,
                )
                if stats["verified"] == stats["total"]:
                    print()  # end the progress line
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
                while _waited < self._runtime_cfg["AUTO_STEP_DELAY"]:
                    if _treg.consume(_state_dir, "stop"):
                        _stopped = True
                        break
                    # Pause gate: spin while pause_trigger exists (don't advance _waited)
                    while _treg.exists(_state_dir, "pause"):
                        if _waited < 0.05:  # first detection — print once
                            print(f"  {YELLOW}Auto-run paused remotely. Waiting for resume…{RESET}", flush=True)
                            _waited = 0.05
                        time.sleep(0.2)
                        # Still honour stop during pause
                        if _treg.exists(_state_dir, "stop"):
                            break
                    vdata = _treg.consume(_state_dir, "verify")
                    if vdata:
                        for e in (vdata if isinstance(vdata, list) else [vdata]):
                            self._cmd_verify(
                                f"{e.get('subtask', '')} {e.get('note', 'Discord verify')}"
                            )
                    adata = _treg.consume(_state_dir, "add_task")
                    if adata:
                        spec = adata.get("spec", "").strip()
                        if spec:
                            self._cmd_add_task(spec)
                    abdata = _treg.consume(_state_dir, "add_branch")
                    if abdata:
                        task_arg = abdata.get("task", "").strip()
                        spec     = abdata.get("spec", "").strip()
                        if task_arg and spec:
                            self._cmd_add_branch(task_arg, spec_override=spec)
                    pbdata = _treg.consume(_state_dir, "prioritize_branch")
                    if pbdata:
                        pb_task   = pbdata.get("task", "").strip()
                        pb_branch = pbdata.get("branch", "").strip()
                        if pb_task and pb_branch:
                            self._cmd_prioritize_branch(pb_task, pb_branch)
                    ddata = _treg.consume(_state_dir, "describe")
                    if ddata:
                        d_st   = ddata.get("subtask", "").strip().upper()
                        d_desc = ddata.get("desc", "").strip()
                        if d_st and d_desc:
                            self._cmd_describe(f"{d_st} {d_desc}")
                    rndata = _treg.consume(_state_dir, "rename")
                    if rndata:
                        rn_st   = rndata.get("subtask", "").strip().upper()
                        rn_desc = rndata.get("desc", "").strip()
                        if rn_st and rn_desc:
                            self._cmd_rename(f"{rn_st} {rn_desc}")
                    tdata = _treg.consume(_state_dir, "tools")
                    if tdata:
                        t_st    = tdata.get("subtask", "").strip().upper()
                        t_tools = tdata.get("tools", "").strip()
                        if t_st and t_tools:
                            self._cmd_tools(f"{t_st} {t_tools}")
                    sdata = _treg.consume(_state_dir, "set")
                    if sdata:
                        s_key = sdata.get("key", "").strip()
                        s_val = sdata.get("value", "").strip()
                        if s_key and s_val:
                            self._cmd_set(f"{s_key}={s_val}")
                    healdata = _treg.consume(_state_dir, "heal")
                    if healdata:
                        h_st = healdata.get("subtask", "").strip().upper()
                        if h_st:
                            self._cmd_heal(h_st)
                    depdata = _treg.consume(_state_dir, "depends")
                    if depdata:
                        dep_target = depdata.get("target", "").strip()
                        dep_dep    = depdata.get("dep", "").strip()
                        if dep_target and dep_dep:
                            self._cmd_depends(f"{dep_target} {dep_dep}")
                    uddata = _treg.consume(_state_dir, "undepends")
                    if uddata:
                        ud_target = uddata.get("target", "").strip()
                        ud_dep    = uddata.get("dep", "").strip()
                        if ud_target and ud_dep:
                            self._cmd_undepends(f"{ud_target} {ud_dep}")
                    if _treg.consume(_state_dir, "reset"):
                        self._cmd_reset()
                    if _treg.consume(_state_dir, "snapshot"):
                        self._take_snapshot(auto=False)
                    if _treg.consume(_state_dir, "undo"):
                        self._cmd_undo()
                    dagimpdata = _treg.consume(_state_dir, "dag_import")
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
                    if _treg.consume(_state_dir, "run"):
                        break
                    time.sleep(0.05)
                    _waited += 0.05

                if _stopped:
                    print(f"\n  {YELLOW}Auto-run stopped remotely at step {self.step}.{RESET}", flush=True)
                    time.sleep(0.5)
                    self.display.render(
                        self.dag, self.memory_store, self.step,
                        self.alerts, self.meta.forecast(self.dag),
                    )
                    break

        except KeyboardInterrupt:
            print(f"\n  {YELLOW}Auto-run paused at step {self.step}.{RESET}", flush=True)
            time.sleep(0.5)
            self.display.render(
                self.dag, self.memory_store, self.step,
                self.alerts, self.meta.forecast(self.dag),
            )
