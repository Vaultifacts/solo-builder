"""Auto-run command for SoloBuilderCLI — extracted from solo_builder_cli.py."""
import os
import json
import time


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
                _vtrigger = os.path.join(_HERE, "state", "verify_trigger.json")
                while _waited < self._runtime_cfg["AUTO_STEP_DELAY"]:
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
