"""
profiler_harness.py — Solo Builder performance profiler (reusable).
Run against any settings; reports structured metrics.
"""
import os, sys, copy, json, time, tracemalloc, contextlib, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

tracemalloc.start()
_mem_baseline = tracemalloc.get_traced_memory()[0]

import solo_builder_cli as cli

M = {
    "step_wall": [], "step_cpu": [],
    "planner_t": [], "executor_t": [], "verifier_t": [],
    "healer_find_t": [], "shadow_detect_t": [],
    "sdk_call_t": [], "claude_call_t": [], "sdktool_call_t": [],
    "sdk_jobs_per_step": [], "claude_jobs_per_step": [],
    "sdktool_jobs_per_step": [], "dice_jobs_per_step": [],
    "verified_per_step": [],
    "queue_depth": [], "mem_samples": [],
    "healer_events": [], "healer_heals": [],
}

_orig_prioritize       = cli.Planner.prioritize
_orig_execute_step     = cli.Executor.execute_step
_orig_verify           = cli.Verifier.verify
_orig_find_stalled     = cli.SelfHealer.find_stalled
_orig_heal             = cli.SelfHealer.heal
_orig_detect_conflicts = cli.ShadowAgent.detect_conflicts
_orig_sdk_run          = cli.AnthropicRunner.run
_orig_sdktool_run      = cli.SdkToolRunner.run
_orig_claude_run       = cli.ClaudeRunner.run
_orig_render           = cli.TerminalDisplay.render


def _p_prioritize(self, dag, step):
    t0 = time.perf_counter(); r = _orig_prioritize(self, dag, step)
    M["planner_t"].append(time.perf_counter() - t0); return r

def _p_execute_step(self, dag, priority_list, step, memory_store):
    sdk_t, claude_t, sdktool_t = [], [], []

    orig_sdk      = type(self.anthropic).run
    orig_sdktool  = type(self.sdk_tool).run
    orig_claude   = type(self.claude).run

    def _sdk(inner, prompt):
        t0 = time.perf_counter(); r = _orig_sdk_run(inner, prompt)
        sdk_t.append(time.perf_counter() - t0); M["sdk_call_t"].append(sdk_t[-1]); return r

    def _sdktool(inner, prompt, tools_str):
        t0 = time.perf_counter(); r = _orig_sdktool_run(inner, prompt, tools_str)
        sdktool_t.append(time.perf_counter() - t0); M["sdktool_call_t"].append(sdktool_t[-1]); return r

    def _claude(inner, prompt, st_name, tools=""):
        t0 = time.perf_counter(); r = _orig_claude_run(inner, prompt, st_name, tools)
        claude_t.append(time.perf_counter() - t0); M["claude_call_t"].append(claude_t[-1]); return r

    type(self.anthropic).run  = _sdk
    type(self.sdk_tool).run   = _sdktool
    type(self.claude).run     = _claude

    t0 = time.perf_counter()
    actions = _orig_execute_step(self, dag, priority_list, step, memory_store)
    M["executor_t"].append(time.perf_counter() - t0)

    type(self.anthropic).run  = orig_sdk
    type(self.sdk_tool).run   = orig_sdktool
    type(self.claude).run     = orig_claude

    M["sdk_jobs_per_step"].append(len(sdk_t))
    M["sdktool_jobs_per_step"].append(len(sdktool_t))
    M["claude_jobs_per_step"].append(len(claude_t))
    started   = sum(1 for a in actions.values() if a == "started")
    verified  = sum(1 for a in actions.values() if a in ("verified","review"))
    dice      = max(0, len(actions) - started - len(sdk_t) - len(sdktool_t) - len(claude_t))
    M["dice_jobs_per_step"].append(dice)
    M["verified_per_step"].append(verified)
    return actions

def _p_verify(self, dag):
    t0 = time.perf_counter(); r = _orig_verify(self, dag)
    M["verifier_t"].append(time.perf_counter() - t0); return r

def _p_find_stalled(self, dag, step):
    t0 = time.perf_counter(); r = _orig_find_stalled(self, dag, step)
    M["healer_find_t"].append(time.perf_counter() - t0)
    for _, _, st, age in r: M["healer_events"].append((step, st, age))
    return r

def _p_heal(self, dag, stalled, step, mem, alerts):
    r = _orig_heal(self, dag, stalled, step, mem, alerts)
    M["healer_heals"].append(r if isinstance(r, int) else (len(r) if r else 0))
    return r

def _p_detect_conflicts(self, dag):
    t0 = time.perf_counter(); r = _orig_detect_conflicts(self, dag)
    M["shadow_detect_t"].append(time.perf_counter() - t0); return r

def _p_render(self, *a, **kw): pass

cli.Planner.prioritize           = _p_prioritize
cli.Executor.execute_step        = _p_execute_step
cli.Verifier.verify              = _p_verify
cli.SelfHealer.find_stalled      = _p_find_stalled
cli.SelfHealer.heal              = _p_heal
cli.ShadowAgent.detect_conflicts = _p_detect_conflicts
cli.TerminalDisplay.render       = _p_render

print(f"  Settings: MAX_PER_STEP={cli.EXEC_MAX_PER_STEP}  "
      f"DAG_INTERVAL={cli.DAG_UPDATE_INTERVAL}  "
      f"MAX_TOKENS={cli.ANTHROPIC_MAX_TOKENS}")
print("  Initializing…")

null_out = open(os.devnull, "w", encoding="utf-8")
with contextlib.redirect_stdout(null_out):
    instance = cli.SoloBuilderCLI()

total_st = sum(1 for t in instance.dag.values()
               for b in t.get("branches",{}).values()
               for s in b.get("subtasks",{}).values())
print(f"  DAG: {len(instance.dag)} tasks, {total_st} subtasks")
print("  Running…\n")

def _qdepth(dag):
    return sum(1 for t in dag.values()
               for b in t.get("branches",{}).values()
               for s in b.get("subtasks",{}).values()
               if s.get("status") in ("Pending","Running"))

wall0 = time.perf_counter(); cpu0 = time.process_time()
step = 0
while step < 300:
    depth = _qdepth(instance.dag)
    cur, peak = tracemalloc.get_traced_memory()
    M["queue_depth"].append((step, depth))
    if step % 10 == 0:
        M["mem_samples"].append((step, cur, peak))
    if depth == 0:
        break
    sw0 = time.perf_counter(); sc0 = time.process_time()
    with contextlib.redirect_stdout(null_out):
        instance.run_step()
    M["step_wall"].append(time.perf_counter() - sw0)
    M["step_cpu"].append(time.process_time() - sc0)
    step = instance.step
    if step % 10 == 0:
        v = sum(1 for t in instance.dag.values()
                for b in t.get("branches",{}).values()
                for s in b.get("subtasks",{}).values()
                if s.get("status") == "Verified")
        print(f"  step {step:>4}  verified {v}/{total_st}  queue={depth}  mem={cur/1024:.0f}KB", flush=True)

wall_total = time.perf_counter() - wall0
cpu_total  = time.process_time() - cpu0
null_out.close(); tracemalloc.stop()

total_steps = instance.step
verified_f  = sum(1 for t in instance.dag.values()
                  for b in t.get("branches",{}).values()
                  for s in b.get("subtasks",{}).values()
                  if s.get("status") == "Verified")

def _s(lst, lbl, unit="ms", sc=1000):
    if not lst: return f"  {lbl:<42} n/a"
    mn=min(lst)*sc; mx=max(lst)*sc; av=statistics.mean(lst)*sc
    md=statistics.median(lst)*sc
    p95=sorted(lst)[int(len(lst)*.95)]*sc if len(lst)>=10 else mx
    return (f"  {lbl:<42} avg={av:8.2f}{unit}  med={md:8.2f}{unit}  "
            f"min={mn:6.2f}  max={mx:8.2f}  p95={p95:8.2f}")

print("\n\n" + "═"*82)
print("  SOLO BUILDER — OPTIMIZED PERFORMANCE PROFILE")
print("═"*82)
print(f"""
  Config active:
    EXECUTOR_MAX_PER_STEP  = {cli.EXEC_MAX_PER_STEP}   (baseline: 2)
    DAG_UPDATE_INTERVAL    = {cli.DAG_UPDATE_INTERVAL}   (baseline: 1)
    ANTHROPIC_MAX_TOKENS   = {cli.ANTHROPIC_MAX_TOKENS} (baseline: 300)
    SdkToolRunner          = active (baseline: subprocess)

  ── EXECUTION OVERVIEW ──────────────────────────────────────────────────────
  Total wall time        : {wall_total:.2f}s
  CPU time used          : {cpu_total:.2f}s
  CPU utilization        : {cpu_total/wall_total*100:.1f}%
  Total steps executed   : {total_steps}
  Steps per minute       : {total_steps/wall_total*60:.1f}
  Subtasks total         : {total_st}
  Subtasks verified      : {verified_f}
  Completion             : {verified_f/total_st*100:.1f}%
  Avg step wall time     : {statistics.mean(M["step_wall"])*1000:.1f} ms
  Avg step CPU time      : {statistics.mean(M["step_cpu"])*1000:.2f} ms
""")

print("  ── PER-AGENT TIMING ────────────────────────────────────────────────────────")
print(_s(M["planner_t"],       "Planner.prioritize()"))
print(_s(M["executor_t"],      "Executor.execute_step()"))
print(_s(M["verifier_t"],      "Verifier.verify()"))
print(_s(M["healer_find_t"],   "SelfHealer.find_stalled()"))
print(_s(M["shadow_detect_t"], "ShadowAgent.detect_conflicts()"))
if M["sdk_call_t"]:
    print(_s(M["sdk_call_t"],      "AnthropicRunner.run() [SDK direct]"))
if M["sdktool_call_t"]:
    print(_s(M["sdktool_call_t"],  "SdkToolRunner.run() [SDK+tools]"))
if M["claude_call_t"]:
    print(_s(M["claude_call_t"],   "ClaudeRunner.run() [subprocess]"))

total_sdk    = sum(M["sdk_jobs_per_step"])
total_sdktool= sum(M["sdktool_jobs_per_step"])
total_claude = sum(M["claude_jobs_per_step"])
total_dice   = sum(M["dice_jobs_per_step"])
avg_util     = statistics.mean(
    (s+c+st)/cli.EXEC_MAX_PER_STEP
    for s,c,st in zip(M["sdk_jobs_per_step"],M["claude_jobs_per_step"],M["sdktool_jobs_per_step"])
) * 100
sat_steps = sum(
    1 for s,c,st in zip(M["sdk_jobs_per_step"],M["claude_jobs_per_step"],M["sdktool_jobs_per_step"])
    if s+c+st >= cli.EXEC_MAX_PER_STEP
)

print(f"""
  ── CONCURRENCY / EXECUTOR ──────────────────────────────────────────────────
  EXECUTOR_MAX_PER_STEP          : {cli.EXEC_MAX_PER_STEP}
  SDK (no-tools) jobs total      : {total_sdk}
  SDK+tools jobs total           : {total_sdktool}
  Claude subprocess jobs total   : {total_claude}
  Dice-roll fallbacks            : {total_dice}
  Avg SDK jobs/step              : {statistics.mean(M["sdk_jobs_per_step"]):.2f}
  Avg SDK+tools jobs/step        : {statistics.mean(M["sdktool_jobs_per_step"]):.2f}
  Avg executor utilization       : {avg_util:.1f}%
  Saturated steps (≥MAX)         : {sat_steps}/{total_steps} ({sat_steps/total_steps*100:.0f}%)
  Steps with 0 active jobs       : {sum(1 for s,c,st in zip(M["sdk_jobs_per_step"],M["claude_jobs_per_step"],M["sdktool_jobs_per_step"]) if s+c+st==0)}
  Max thread concurrency         : {max(s+c+st for s,c,st in zip(M["sdk_jobs_per_step"],M["claude_jobs_per_step"],M["sdktool_jobs_per_step"]))}
""")

depths = [d for _,d in M["queue_depth"] if d>0]
nzv    = [v for v in M["verified_per_step"] if v>0]
zsteps = M["verified_per_step"].count(0)
print(f"  ── DAG / QUEUE ─────────────────────────────────────────────────────────────")
print(f"  Queue depth avg                : {statistics.mean(depths):.1f}")
print(f"  Steps with ≥1 verification     : {len(nzv)}/{total_steps}")
print(f"  Steps with 0 verifications     : {zsteps}/{total_steps}  ({zsteps/total_steps*100:.0f}%)")
if nzv: print(f"  Verifications/productive step  : avg={statistics.mean(nzv):.2f}  max={max(nzv)}")

print(f"""
  ── SELF-HEALER EVENTS ──────────────────────────────────────────────────────
  Stall detections               : {len(M["healer_events"])}
  Heals performed                : {sum(M["healer_heals"])}""")
for sn, st, age in M["healer_events"]:
    print(f"    step {sn:>3}  {st:<6}  stall_age={age}")

print(f"""
  ── MEMORY ──────────────────────────────────────────────────────────────────
  Peak                           : {max(p for _,_,p in M["mem_samples"])/1024:.0f} KB
  Final                          : {M["mem_samples"][-1][1]/1024:.0f} KB""")

print(f"""
  ── PLANNER CACHE ───────────────────────────────────────────────────────────
  DAG_UPDATE_INTERVAL            : {cli.DAG_UPDATE_INTERVAL}
  Planner recomputes             : {len(M["planner_t"])}
  Cache reuse steps              : {total_steps - len(M["planner_t"])}  ({(total_steps - len(M["planner_t"]))/total_steps*100:.0f}% steps served from cache)""")

print(f"""
  ── STEP TIMING DISTRIBUTION ────────────────────────────────────────────────
  Bucket       Count   %""")
for (lo,hi), lbl in [((0,100),"<100ms"),((100,500),"100-500ms"),
                      ((500,2000),"500ms-2s"),((2000,5000),"2s-5s"),((5000,99999),">5s")]:
    cnt = sum(1 for t in M["step_wall"] if lo <= t*1000 < hi)
    bar = "█"*(cnt*40//max(total_steps,1))
    print(f"  {lbl:<12} {cnt:>5}   {cnt/total_steps*100:5.1f}%  {bar}")

print("\n" + "═"*82)
print("  END OF OPTIMIZED PROFILE")
print("═"*82 + "\n")
