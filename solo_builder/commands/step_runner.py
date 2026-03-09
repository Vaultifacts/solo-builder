"""Step execution and persistence for SoloBuilderCLI — extracted from solo_builder_cli.py."""
import os
import json


class StepRunnerMixin:
    """Mixin: run_step, _take_snapshot, save_state, load_state, _consume_json_trigger."""

    def run_step(self) -> None:
        """Execute one full agent pipeline step."""
        self.step += 1
        step_alerts: list = []

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
