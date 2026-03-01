# Solo Builder — Live Journal

## A4 · Task 0 / Branch A · Step 35

**Prompt:** What are 3 risks of building a self-healing agent system, and one mitigation for each?

## Risks of Self-Healing Agent Systems

**1. Runaway remediation loops**
The agent misdiagnoses a root cause, applies a fix, observes no improvement, and retries — escalating resource usage or cascading failures rather than recovering.

*Mitigation:* Implement a circuit breaker with a maximum retry budget and mandatory human escalation after N failed heal attempts. Never let the agent retry the same action without a state change.

---

**2. Privilege escalation via autonomous decisions**
A self-healing agent needs broad permissions to restart services, roll back deployments, or modify configs. A compromised or confused agent can abuse those permissions at machine speed.

*Mitigation:* Apply least-privilege scoping per action type (e.g., read-only observability, write-only to a specific restart endpoint) and require out-of-band approval for any action above a defined blast-radius threshold.

---

**3. Observability blindness (healing in the dark)**
The agent acts on metrics or logs that are themselves corrupted, delayed, or missing — producing confident but wrong decisions based on a false picture of system state.

*Mitigation:* Treat the telemetry pipeline as a first-class dependency. Before any healing action, validate signal freshness and cross-reference at least two independent data sources (e.g., metrics + health endpoint) before concluding a fault exists.

---

## A2 · Task 0 / Branch A · Step 2

**Prompt:** Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.

Solo Builder is a Python terminal CLI that harnesses AI agents to manage complex projects through a DAG-based task graph, automatically tracking dependencies and orchestrating work in the right order. It turns ambitious solo projects into manageable pipelines — letting one person operate with the leverage of a whole team.

---

## A1 · Task 0 / Branch A · Step 2

**Prompt:** List 5 key features a solo developer AI project management tool needs. Bullet points.

- **Task prioritization** — AI-ranked backlog so you focus on highest-impact work, not just what's loudest
- **Context persistence** — remembers project state, decisions, and blockers across sessions without re-explaining everything
- **Scope creep detection** — flags when new tasks expand beyond original goals or sprint boundaries
- **Dependency mapping** — tracks what blocks what, so you don't start tasks that can't complete yet
- **Progress estimation** — realistic time/effort tracking calibrated to your actual velocity, not optimistic guesses

---

## A4 · Task 0 / Branch A · Step 4

**Prompt:** What are 3 risks of building a self-healing agent system, and one mitigation for each?

## 3 Risks of Self-Healing Agent Systems

**1. Runaway remediation loops**
An agent misdiagnoses a root cause, applies a "fix" that worsens the problem, detects the worsened state, applies another fix — spiraling into cascading failures.

*Mitigation:* Enforce a **circuit breaker** with a maximum retry count and a cooldown period. After N failed healing attempts, halt and escalate to a human rather than continuing to act.

---

**2. Privilege escalation via tool misuse**
A self-healing agent needs broad permissions to restart services, modify configs, or redeploy code. A compromised or hallucinating agent can abuse those same permissions destructively.

*Mitigation:* Apply **least-privilege scoping** — issue time-limited, action-scoped credentials per healing task (e.g., "restart service X only") rather than persistent admin access. Log and audit every action taken.

---

**3. Evaluation drift (the agent marks itself healthy)**
The agent controls both the healing action *and* the health check. It can learn to satisfy the check without actually fixing the underlying issue (Goodhart's Law applied to agents).

*Mitigation:* Separate the **health oracle from the healing agent** — use an independent, read-only monitoring system to evaluate state. The healing agent cannot write to or influence the oracle's evaluation criteria.

---

## A3 · Task 0 / Branch A · Step 4

**Prompt:** Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.

Based on the actual codebase, here are 3 concrete improvements grounded in what's really there:

---

**1. Wire the Claude API into every task transition — not just hand-picked subtasks**

`EXECUTOR_VERIFY_PROBABILITY = 0.6` in `helper_functions.py:61` means 60% of subtasks are "verified" by a dice roll. The existing `CLAUDE_TIMEOUT` config key shows real API calls were planned but never connected for the bulk of tasks. Only A1–A5-type subtasks produce real Claude output; the rest simulate progress.

**Fix:** Replace the probability branch in the Executor with an actual `claude-haiku-4-5` call using the subtask `description` as the prompt. Real verification means the tool is actually doing work, not just counting to done.

---

**2. Add a `block` command to the CLI to explicitly mark a subtask as blocked, with a reason**

Right now the lifecycle is `Pending → Running → Verified | Failed`. There's no way to say "I can't proceed on this until X is resolved." As a solo dev, the most common real-world state is *blocked* — waiting on an API key, a decision, an external dep. The SelfHealer will eventually reset stalled tasks, but that's the wrong signal.

**Fix:** Add `block <subtask_id> <reason>` as a CLI command that sets a `"Blocked"` status and stores the reason string on the subtask. The Planner should skip blocked subtasks entirely, and the `status` display should surface them prominently.

---

**3. Make `snapshot` output a diff from the previous snapshot, not just current state**

`solo_builder_live_multi_snapshot.py` generates a full PDF of current state. That's fine for archiving, but as a solo dev reviewing progress, what you actually want to know is *what changed* — which tasks moved, which outputs were added, which stalls occurred — since the last snapshot.

**Fix:** On `snapshot`, load the previous snapshot JSON and diff it against current state. Print (or append to `journal.md`) a compact change summary: tasks completed, tasks regressed, new stalls, net progress percentage. One glance tells you whether the last work session moved the needle.

---

## A5 · Task 0 / Branch A · Step 6

**Prompt:** Write a tagline for Solo Builder in under 10 words.

**Build smarter. Ship faster. Solo.**

---

## B1 · Task 0 / Branch B · Step 6

**Prompt:** Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.

A **Shadow Agent** runs in parallel with a primary agent, observing its inputs and outputs without interfering — typically used for monitoring, logging, or testing a new agent version against production traffic before promoting it.

A **Verifier Agent** actively inspects the output of another agent after the fact to validate correctness, safety, or adherence to constraints — it can block, flag, or trigger retries if the output fails its checks.

---

## B3 · Task 0 / Branch B · Step 8

**Prompt:** In one sentence, explain what a MetaOptimizer does in an AI pipeline.

A MetaOptimizer is a higher-level optimization process that tunes the hyperparameters or learning strategies of one or more underlying optimizers, effectively "learning how to learn" to improve overall model training efficiency and performance.

---

## B2 · Task 0 / Branch B · Step 8

**Prompt:** List 3 real-world use cases for a DAG-based AI project tracker.

## 3 Real-World Use Cases for a DAG-Based AI Project Tracker

**1. Software Release Pipeline Management**
Track dependencies between tasks like "write tests → pass CI → code review → merge → deploy to staging → smoke test → deploy to prod." The DAG enforces that no step runs until its predecessors are complete, and an AI layer can predict bottlenecks (e.g., "code review is the critical path — 3 PRs waiting").

**2. Machine Learning Experiment Orchestration**
Data science workflows have natural DAG structure: raw data → cleaning → feature engineering → model training → evaluation → deployment. An AI tracker can detect when upstream changes (e.g., a new data source) invalidate downstream artifacts, flag which experiments need rerunning, and surface which node is blocking the most downstream work.

**3. Construction / Engineering Project Scheduling**
Building a structure requires strict ordering: foundation → framing → electrical rough-in → drywall → finishing. A DAG tracker with AI can flag schedule violations in real time, simulate the impact of a contractor delay on the critical path, and recommend task reordering to recover lost time — something Gantt charts alone can't do dynamically.

---

The common thread: DAGs shine when **order matters and dependencies are complex**. The AI layer adds value by surfacing the non-obvious — critical paths, cascading delays, and reoptimization opportunities.

---

## A2 · Task 0 / Branch A · Step 2

**Prompt:** Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.

Solo Builder is a Python terminal CLI that harnesses AI agents to manage complex projects as dependency-aware DAGs, automatically sequencing tasks so nothing falls through the cracks. It gives solo developers and small teams a lightweight, intelligent command center that thinks through project dependencies for you — so you can focus on building, not coordinating.

---

## A1 · Task 0 / Branch A · Step 2

**Prompt:** List 5 key features a solo developer AI project management tool needs. Bullet points.

- **Task & context persistence** — remembers project state, decisions, and blockers across sessions without re-explaining
- **Intelligent prioritization** — surfaces what to work on next based on dependencies, deadlines, and energy level
- **Friction-free capture** — quick input for ideas, bugs, and tasks without breaking flow (hotkeys, voice, CLI)
- **Progress visibility** — lightweight dashboards showing velocity, blockers, and what's shipping vs. stalled
- **AI-assisted breakdown** — converts vague goals into concrete, sized tasks with clear acceptance criteria

---

## A4 · Task 0 / Branch A · Step 4

**Prompt:** What are 3 risks of building a self-healing agent system, and one mitigation for each?

## Risks of Self-Healing Agent Systems

**1. Runaway remediation loops**
The agent misdiagnoses a failure, applies a fix that makes things worse, detects a new failure, and spirals — potentially causing an outage larger than the original.

*Mitigation:* Implement a **circuit breaker** with a max remediation attempts per time window. After N failed fixes, the system halts and pages a human instead of retrying.

---

**2. Privilege escalation surface**
A self-healing agent needs broad permissions to restart services, modify configs, and redeploy code — making it a high-value target. If compromised or manipulated (prompt injection via log data), it becomes an attacker's tool.

*Mitigation:* **Scope permissions to named actions, not raw capabilities.** The agent calls `restart_service("api")` via a hardened control plane, never executes arbitrary shell commands. Audit every action with a tamper-evident log.

---

**3. Drift from intended system state**
Over time, the agent accumulates patches and workarounds that diverge from the canonical infrastructure definition (IaC, config files). The "healed" state becomes undocumented and unreproducible.

*Mitigation:* **Write-through to source of truth.** Every remediation the agent applies must also open a PR or patch the IaC definition. If it can't express the fix declaratively, it escalates instead of applying it ad-hoc.

---

## A5 · Task 0 / Branch A · Step 6

**Prompt:** Write a tagline for Solo Builder in under 10 words.

**Build faster. Ship alone. Win big.**

---

## A3 · Task 0 / Branch A · Step 7

**Prompt:** Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.

The journal already has a previous answer to this same question (A3, Step 4). Here are 3 fresh, concrete improvements grounded in the actual code — distinct from the previous suggestions:

---

**1. Add a session startup briefing**

Right now the CLI opens cold with no orientation. As a solo dev returning after a day or two, you have to mentally reload all context. Fix: on startup, before dropping into the REPL, print a compact "where you left off" block using already-available data:

```
Last session: 3 tasks verified, 1 stalled, 2 pending
Next recommended: Branch B / Subtask 4 (Planner priority #1)
Unresolved alerts: 1 conflict on Branch A
```

All the data is in `state/solo_builder_state.json` and the existing `dag_stats`/`shadow_stats` helpers. This is a 20-line addition to the startup path in `solo_builder_cli.py`.

---

**2. Add an `export` command that dumps the DAG as a markdown checklist**

There's no way to get task state out of the tool. A solo dev needs to paste into a GitHub Issue, commit to a `CLAUDE.md`, or share progress. Fix: add `export [filepath]` to the CLI command table that serializes the current DAG as nested markdown checkboxes:

```markdown
- [ ] Branch A
  - [x] Subtask 1 (Verified)
  - [ ] Subtask 2 (Running)
```

`state/solo_builder_state.json` already holds all branches and subtasks. No new data needed — just a formatter.

---

**3. Timestamp subtasks and use it for real velocity in MetaOptimizer**

The `MetaOptimizer` generates "forecasts" but has no real timing data to work with. Every subtask transitions through states, but `started_at` and `completed_at` are never recorded. Fix: add two timestamp fields to the subtask dict on state transitions in the Executor. Then the MetaOptimizer can compute actual cycle time (time per subtask) and surface a calibrated estimate — "at current velocity, Branch B completes in ~4 more steps" — instead of a synthetic projection. This is the difference between a useful tool and a simulation.

---

## B1 · Task 0 / Branch B · Step 8

**Prompt:** Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.

A **Shadow Agent** runs in parallel alongside a primary agent, silently observing its inputs and outputs without interfering — used for monitoring, auditing, or testing a new agent against a live system before switching over. A **Verifier Agent** actively checks the output or reasoning of another agent after the fact, validating correctness, safety, or policy compliance before results are accepted or acted upon.

---

## B2 · Task 0 / Branch B · Step 9

**Prompt:** List 3 real-world use cases for a DAG-based AI project tracker.

## DAG-Based AI Project Tracker — 3 Real-World Use Cases

**1. ML Pipeline Dependency Management**
Track feature engineering → training → evaluation → deployment as nodes with directed edges. Automatically re-run only downstream steps when an upstream artifact (e.g., a dataset) changes — no manual bookkeeping of what's stale.

**2. Multi-Agent Task Orchestration**
In a system with specialized agents (researcher, coder, reviewer), the DAG encodes which agent outputs gate which agent inputs. The tracker surfaces bottlenecks, detects deadlocks, and lets you visualize parallel vs. sequential work across a long-running agentic session.

**3. Software Release Dependency Tracking**
Model a release as a DAG: design → implementation → unit tests → integration tests → staging → prod. The AI layer predicts risk scores per node (based on commit history, test flakiness, reviewer load) and flags the critical path before a release is attempted.

---

Common thread: DAGs are valuable when tasks have **partial ordering** (some things must precede others, but many can run in parallel) and the AI adds **predictive or adaptive routing** on top of the static dependency graph.

---

## B3 · Task 0 / Branch B · Step 10

**Prompt:** In one sentence, explain what a MetaOptimizer does in an AI pipeline.

A **MetaOptimizer** learns to optimize the optimizer itself — it dynamically adjusts hyperparameters (like learning rate, momentum, or architecture choices) during training rather than relying on fixed, hand-tuned values.

---

## A2 · Task 0 / Branch A · Step 2

**Prompt:** Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.

Solo Builder is a Python terminal CLI that harnesses AI agents to intelligently manage and execute project tasks as a directed acyclic graph, automatically resolving dependencies so work happens in the right order. It transforms how solo developers plan and ship projects by letting AI handle task orchestration while you stay focused on building.

---

## A1 · Task 0 / Branch A · Step 3

**Prompt:** List 5 key features a solo developer AI project management tool needs. Bullet points.

- **Task breakdown** — auto-decompose goals into actionable subtasks with dependencies
- **Context persistence** — remember project state, decisions, and progress across sessions
- **Priority management** — surface what to work on next based on deadlines, blockers, and effort
- **Progress tracking** — visual status of tasks (backlog → in progress → done) without overhead
- **AI-assisted planning** — generate estimates, spot risks, and suggest next steps from natural language input

---

## A4 · Task 0 / Branch A · Step 5

**Prompt:** What are 3 risks of building a self-healing agent system, and one mitigation for each?

## 3 Risks of Self-Healing Agent Systems

**1. Runaway Remediation Loops**
The agent misdiagnoses a failure, applies a "fix" that makes things worse, detects the new failure, and cycles indefinitely — consuming resources or corrupting state with each iteration.

*Mitigation:* Implement a circuit breaker with a max-retry budget and cooldown window. After N failed healing attempts on the same component, escalate to human review instead of retrying.

---

**2. Privilege Escalation via Healing Actions**
Self-healing often requires elevated permissions (restart services, modify configs, patch code). A compromised or hallucinating agent with those permissions becomes a high-impact attack surface.

*Mitigation:* Apply least-privilege boundaries per action type. Healing actions should run through a constrained tool manifest — e.g., "restart service X" is allowed, but "modify IAM policy" or "run arbitrary shell" is not, even if the agent requests it.

---

**3. Silent State Drift**
The agent successfully patches symptoms without fixing root causes, leaving the system in a subtly different state than intended. Over time, these silent divergences compound and become difficult to audit or reverse.

*Mitigation:* Require all healing actions to be declarative and logged to an append-only audit trail. Periodically reconcile actual state against a known-good baseline (e.g., using infrastructure-as-code diff) so drift is surfaced before it accumulates.

---

## A5 · Task 0 / Branch A · Step 7

**Prompt:** Write a tagline for Solo Builder in under 10 words.

**Build faster. Ship alone. Win anyway.**

---

## A3 · Task 0 / Branch A · Step 7

**Prompt:** Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.

Here are 3 concrete improvements grounded in what Solo Builder actually does today:

---

**1. Wire agents to real Claude calls instead of probabilistic simulation**

Right now `EXECUTOR_VERIFY_PROBABILITY = 0.6` means subtasks advance by random coin flip. The Planner, Executor, and Verifier agents should call Claude with the actual subtask description and current DAG state to make real decisions — does this subtask have enough context to proceed? Is the output actually verified? The journal proves the Claude integration already exists; it just isn't wired into the agent loop.

**Impact:** Turns the tool from a simulation into a real AI project manager.

---

**2. Add a `daily` command — AI-generated focus brief**

Each morning, call Claude with the current DAG state and output a short digest: what's stalled and why, what's unblocked and ready to run, and a single recommended next action. The `meta_history` and `alerts` already collected in state provide the raw material. This surfaces value without requiring the developer to read through the whole DAG.

**Impact:** Answers the #1 solo dev question: "what do I actually work on right now?"

---

**3. Git commit → subtask status sync**

Add a `git_sync` command (or post-commit hook) that scans recent git commits for task/subtask references (e.g., `[A4]` or `task-0-branch-a`) and automatically advances matching subtasks from `Running` to `Verified`. The SelfHealer already detects stalls via step counts — git activity is a stronger, ground-truth signal for real progress.

**Impact:** Makes the DAG reflect what's actually shipped, not simulated advancement.

---

## B1 · Task 0 / Branch B · Step 9

**Prompt:** Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.

A **Shadow Agent** runs in parallel with a primary agent, silently observing its inputs and outputs without intervening, typically used for monitoring, logging, or A/B testing a new agent against the current one.

A **Verifier Agent** actively evaluates the output of another agent against defined criteria (correctness, safety, format, etc.) and can block, flag, or trigger retry logic if the output fails validation.

---

## B2 · Task 0 / Branch B · Step 9

**Prompt:** List 3 real-world use cases for a DAG-based AI project tracker.

## 3 Real-World Use Cases for a DAG-Based AI Project Tracker

**1. Software Release Pipeline Management**
Track interdependent tasks across teams — e.g., "deploy to staging" can't run until "run integration tests" completes, which depends on "build Docker image." The DAG makes blockers and critical paths immediately visible, so PMs know exactly what's holding up a release.

**2. ML Model Development Lifecycle**
Nodes represent stages like data ingestion → preprocessing → feature engineering → training → evaluation → deployment. Dependencies are explicit (you can't evaluate a model that hasn't been trained), and the graph lets teams parallelize independent branches (e.g., running multiple preprocessing strategies simultaneously).

**3. Multi-Agent AI Workflow Orchestration**
When multiple AI agents collaborate on a complex task (research → summarize → critique → rewrite → publish), a DAG enforces execution order, surfaces which agents are blocked on upstream outputs, and enables partial re-runs — if the "critique" step fails, you only re-execute from that node, not the whole pipeline.

---

The core value in each case: **explicit dependency modeling** prevents out-of-order execution, enables parallel work where safe, and makes the critical path inspectable.

---

## B3 · Task 0 / Branch B · Step 11

**Prompt:** In one sentence, explain what a MetaOptimizer does in an AI pipeline.

A MetaOptimizer is a higher-level optimization component that automatically tunes the hyperparameters or learning strategies of underlying optimizers, effectively "learning how to learn" to improve overall model training efficiency and performance.

---

## C2 · Task 1 / Branch C · Step 13

**Prompt:** List 3 advantages of using a priority queue to schedule software tasks.

1. **O(log n) scheduling** — Insert and extract-min/max operations run in O(log n) time, making it efficient to always pick the highest-priority task next, even with thousands of queued tasks.

2. **Dynamic priority handling** — New high-priority tasks can be inserted at any time and will preempt lower-priority work naturally, without requiring a full resort of the queue.

3. **Deadline and starvation management** — Priority weights can encode deadlines or aging (gradually increasing priority of waiting tasks), preventing low-priority tasks from being starved indefinitely.

---

## C1 · Task 1 / Branch C · Step 13

**Prompt:** What does a DAG (Directed Acyclic Graph) represent in software project management? Answer in one paragraph.

A DAG (Directed Acyclic Graph) in software project management represents the dependency relationships between tasks, jobs, or components, where each node is a unit of work and each directed edge indicates that one task must complete before another can begin — with the "acyclic" constraint ensuring there are no circular dependencies (i.e., no task can depend on itself, directly or indirectly). This structure is fundamental to build systems (Make, Bazel, Gradle), CI/CD pipelines (GitHub Actions, Airflow), and package managers, as it allows the system to determine a valid execution order via topological sorting, identify which tasks can run in parallel, and pinpoint the critical path that determines the minimum total completion time.

---

## C3 · Task 1 / Branch C · Step 15

**Prompt:** Explain the concept of task staleness in a project management system in 2 sentences.

Task staleness refers to the condition where tasks in a project management system have not been updated, progressed, or reviewed within an expected timeframe, making their current status unreliable or outdated. It signals that a task may be blocked, forgotten, or deprioritized, and serves as a trigger for teams to re-evaluate and update those items to maintain an accurate project state.

---

## C4 · Task 1 / Branch C · Step 15

**Prompt:** What is a shadow state in an agent-based system? Give one concrete example.

## Shadow State in Agent-Based Systems

**Shadow state** is state that an agent believes to be true about the world, but which has diverged from actual reality — without the agent knowing it.

It's the gap between the agent's internal model and ground truth.

---

### Concrete Example: File System Agent

An agent is given the task: *"Refactor all TypeScript files in `/src`."*

1. The agent reads the directory at turn 1, building its internal list: `[auth.ts, user.ts, api.ts]`
2. Another process (a developer, a build step, a git checkout) **deletes `api.ts` and adds `routes.ts`** while the agent is mid-task
3. The agent continues operating on its cached list — it tries to edit `api.ts` (gone), and never touches `routes.ts` (unknown)

The agent's internal file list is **shadow state** — it looks real to the agent, but is stale.

---

### Why It Matters

Shadow state causes agents to:
- Make decisions based on outdated assumptions
- Skip or double-process resources
- Produce confidently wrong outputs with no error signal

### Mitigations
- **Re-read before write**: Always fetch current state immediately before acting on it
- **Optimistic locking**: Check a version/hash before committing changes
- **Short-lived caches**: Treat any cached state as expired after N seconds/turns
- **Event-driven updates**: Subscribe to changes rather than snapshot-and-hold

Shadow state is especially dangerous in multi-agent systems where multiple agents read and write shared resources concurrently.

---

## D2 · Task 1 / Branch D · Step 17

**Prompt:** What is the difference between optimistic and pessimistic task verification? One paragraph.

**Optimistic task verification** assumes a task succeeded unless there's explicit evidence of failure — you proceed immediately after issuing a command, only checking for errors if something goes wrong downstream. **Pessimistic task verification** assumes nothing succeeded until you actively confirm it — you check return codes, query state, or validate output before moving on. Optimistic verification is faster and lower-overhead but risks silently propagating failures; pessimistic verification is more reliable and catches issues early but adds latency and complexity. In agentic workflows, the right choice depends on the blast radius: low-stakes, reversible operations (e.g., reading a file) warrant optimism, while high-stakes or irreversible ones (e.g., deploying to production, sending a message) warrant pessimism.

---

## D1 · Task 1 / Branch D · Step 17

**Prompt:** Describe 2 strategies for preventing task starvation in a priority-based scheduler.

## Preventing Task Starvation in Priority-Based Schedulers

### 1. Aging

Gradually increase the priority of a task the longer it waits in the ready queue.

- Each time a scheduling cycle passes without a task being run, its effective priority is incremented
- Eventually, even the lowest-priority task reaches the highest priority and gets CPU time
- After execution, the priority is reset to its original value

**Example:** A task starts at priority 10 (low). Every N milliseconds it waits, priority decreases by 1 (toward 0 = highest). After enough cycles, it will preempt newly arrived high-priority tasks.

---

### 2. Priority Ceiling / Time-Slice Donation

Impose a maximum time that high-priority tasks can monopolize the CPU, and donate time slices to starving tasks.

- Track the **waiting time** of each task
- If a task exceeds a starvation threshold (e.g., 500ms without running), it is temporarily **boosted** to the highest priority band and given a guaranteed time slice
- Once it completes its slice, it returns to its original priority

This is essentially what Linux's Completely Fair Scheduler (CFS) does with its "starvation prevention" boosting for tasks in the expired run queue.

---

**Key difference:** Aging is *continuous and gradual* — priority drifts up over time. Time-slice donation is *threshold-triggered* — nothing happens until a hard deadline is crossed, then the task is forcibly promoted.

---

## E2 · Task 2 / Branch E · Step 19

**Prompt:** Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.

A MetaOptimizer monitors agent performance metrics across tasks and iteratively adjusts hyperparameters, prompting strategies, and tool selection policies to maximize long-term outcomes. By learning from historical success/failure patterns, it can dynamically tune the agent's decision-making heuristics — such as when to spawn subagents, which model tier to use, or how to structure prompts — without requiring manual intervention.

---

## E1 · Task 2 / Branch E · Step 19

**Prompt:** What are 3 benefits of self-healing automation in a software pipeline?

1. **Reduced downtime** — The system detects and recovers from failures automatically (retry logic, fallbacks, restarts) without waiting for human intervention, keeping pipelines running continuously.

2. **Lower operational toil** — Engineers spend less time on routine incident response and manual remediation, freeing them to focus on higher-value work rather than babysitting flaky builds or transient infrastructure failures.

3. **Faster feedback loops** — By automatically resolving known failure patterns (flaky tests, dependency timeouts, resource exhaustion), the pipeline maintains consistent throughput and developers get reliable feedback on their changes without delay.

---

## E4 · Task 2 / Branch E · Step 21

**Prompt:** What is the difference between reactive and proactive error handling in agent systems? One sentence each.

**Reactive**: The agent detects and responds to errors *after* they occur (e.g., catching exceptions, retrying failed tool calls).

**Proactive**: The agent anticipates and prevents errors *before* they occur (e.g., validating inputs, checking preconditions, verifying resource availability before acting).

---

## E3 · Task 2 / Branch E · Step 21

**Prompt:** List 3 metrics that indicate an AI agent system is performing well.

Here are 3 key metrics for evaluating AI agent system performance:

1. **Task Completion Rate** — The percentage of assigned tasks successfully completed without human intervention or error recovery. High rates indicate reliable autonomous execution.

2. **Latency / Time-to-Resolution** — Average time from task initiation to completion. Lower latency with consistent quality signals efficient tool use and minimal wasted cycles (retries, loops, dead ends).

3. **Tool Call Accuracy** — The ratio of useful/correct tool calls to total tool calls made. High accuracy means the agent selects the right tools with correct parameters on the first attempt, avoiding unnecessary API calls or permission denials.

---

## F1 · Task 2 / Branch F · Step 23

**Prompt:** What is the role of a Verifier agent in a multi-agent pipeline? 2 sentences.

A Verifier agent checks the output of other agents to ensure correctness, completeness, and adherence to requirements before passing results downstream. It acts as a quality gate, catching errors, hallucinations, or constraint violations that the primary agent may have introduced.

---

## E5 · Task 2 / Branch E · Step 23

**Prompt:** Give one example of a heuristic weight that a MetaOptimizer might adjust in a task planner.

A MetaOptimizer might adjust the **urgency decay rate** — the rate at which a task's priority score decreases (or increases) as its deadline approaches.

For example:

```
priority_score = base_priority * (1 + urgency_weight * e^(days_until_deadline * -decay_rate))
```

If the MetaOptimizer observes that tasks are consistently being completed too late, it increases `decay_rate` so urgency spikes earlier, giving the planner more lead time to schedule high-priority work.

---

## F2 · Task 2 / Branch F · Step 25

**Prompt:** Describe how memory snapshots help with debugging in an agent system. One paragraph.

Memory snapshots help debugging in agent systems by capturing the full state of an agent at a specific point in time — including active context, tool call history, intermediate results, variable bindings, and any accumulated memory — so you can inspect exactly what the agent "knew" and "decided" at each step. When an agent produces unexpected output or fails mid-task, replaying or diffing snapshots lets you pinpoint where the state diverged from expectations without having to re-run the entire (often expensive or non-deterministic) execution. They also enable time-travel debugging: you can rewind to a pre-failure snapshot, modify a variable or injected context, and re-run forward to test a fix in isolation. In multi-agent systems, cross-referencing snapshots from different agents at the same logical timestep reveals coordination bugs — like one agent acting on stale data because a peer's memory update hadn't propagated yet.

---

## F3 · Task 2 / Branch F · Step 25

**Prompt:** List 2 ways a ShadowAgent could detect state inconsistencies in a DAG pipeline.

## Two Ways a ShadowAgent Could Detect State Inconsistencies in a DAG Pipeline

### 1. Checksum/Hash Comparison at Node Boundaries

A ShadowAgent mirrors the primary pipeline and computes a deterministic hash (e.g., SHA-256) of the output state at each node transition. After each node executes, the shadow compares its hash against the primary's hash.

```
Primary:  NodeA → [state_hash: a3f9] → NodeB
Shadow:   NodeA → [state_hash: a3f9] → NodeB  ✓ consistent
                 [state_hash: b1c4] → NodeB  ✗ INCONSISTENCY DETECTED
```

**What it catches:** Non-deterministic execution, dropped/corrupted messages between nodes, divergent side effects.

---

### 2. Topological Replay with Invariant Assertion

The ShadowAgent independently replays the DAG execution from recorded inputs and asserts that invariants hold at each node — e.g., output cardinality, schema shape, or monotonicity of a counter.

```python
for node in topological_sort(dag):
    shadow_output = node.execute(shadow_inputs[node])
    assert invariants[node].check(shadow_output), f"Invariant violated at {node}"
```

**What it catches:** Logic errors that produce structurally valid but semantically wrong state (e.g., a node silently drops records, or a join produces duplicate rows). Checksums alone miss these because the shadow and primary diverge the same wrong way — invariant assertions catch *class-level* violations regardless.

---

**Key distinction:** Hashing detects *divergence between two executions*; invariant assertion detects *correctness violations within a single execution*.

---

## F4 · Task 2 / Branch F · Step 27

**Prompt:** What is the difference between a branch and a task in a DAG-based project tracker? One sentence.

A **branch** is a named pointer to a node in the DAG representing a line of work, while a **task** is an actual node in the DAG representing a unit of work with dependencies, status, and metadata.

---

## G1 · Task 3 / Branch G · Step 27

**Prompt:** What is continuous integration and how does it relate to automated project management? One paragraph.

Continuous integration (CI) is the practice of frequently merging developer code changes into a shared repository — typically multiple times per day — where each merge triggers an automated pipeline that builds the code, runs tests, and reports results. It relates to automated project management in that CI systems like GitHub Actions, GitLab CI, or Jenkins serve as the backbone for automating repetitive project tasks: running test suites, enforcing code quality checks, generating build artifacts, deploying to staging environments, and even updating issue trackers or notifying teams via Slack when something breaks. This means project management overhead (tracking what's broken, what's deployed, what's ready for review) is handled by the pipeline rather than manually, letting teams focus on building rather than coordinating.

---

## G3 · Task 3 / Branch G · Step 29

**Prompt:** Describe the MVP (Minimum Viable Product) concept in 2 sentences.

An MVP is the simplest version of a product that delivers core value to early users while requiring minimal development effort. It exists to validate key assumptions and gather real-world feedback before investing in full-scale development.

---

## G2 · Task 3 / Branch G · Step 29

**Prompt:** List 3 common causes of technical debt in solo developer projects.

1. **Skipping tests** — Solo devs often ship first and never circle back to add test coverage, leaving regressions to accumulate silently.

2. **Deferred refactoring** — Quick hacks and "I'll clean this up later" decisions pile up, making the codebase progressively harder to change safely.

3. **No documentation or architecture decisions recorded** — Context lives only in the developer's head, making future changes slower and riskier as memory fades.

---

## G4 · Task 3 / Branch G · Step 31

**Prompt:** What is a sprint in agile methodology? One sentence.

A sprint is a fixed-length iteration (typically 1–4 weeks) in which a team completes a defined set of work from the product backlog.

---

## G5 · Task 3 / Branch G · Step 31

**Prompt:** List 3 developer tools a solo builder could use alongside an AI task manager.

Three developer tools that pair well with an AI task manager for a solo builder:

1. **Linear** — Lightweight issue tracker with a clean API, good for syncing AI-generated tasks into a structured backlog with priorities and cycles.

2. **Gitpod / GitHub Codespaces** — Cloud dev environments that let you spin up a workspace per task/branch, reducing context-switching friction when jumping between AI-suggested work items.

3. **Doppler** — Secrets and environment variable management across environments. Keeps your `.env` complexity out of the AI task loop while staying accessible from any dev context.

---

## H1 · Task 3 / Branch H · Step 33

**Prompt:** Describe the concept of a 'Definition of Done' in software projects. 2 sentences.

A **Definition of Done** (DoD) is a shared, explicit checklist of criteria that every piece of work must satisfy before it can be considered complete — covering aspects like code review, tests passing, documentation, and deployment. It prevents ambiguity by ensuring all team members agree on what "finished" actually means, reducing the risk of incomplete work being shipped.

---

## G6 · Task 3 / Branch G · Step 33

**Prompt:** What is the difference between async and sync task execution in pipelines? One paragraph.

In a pipeline, **synchronous (sync) execution** means each task runs sequentially — a task must fully complete before the next one starts, blocking the thread/process during any waiting (I/O, network, computation). **Asynchronous (async) execution** allows tasks to be initiated without blocking; when a task hits a wait point (e.g., a network call), control yields back so other tasks can run concurrently on the same thread, resuming when the result is ready. In practice, sync pipelines are simpler to reason about and debug but can be slow when tasks involve I/O-bound work, while async pipelines (using constructs like `async/await`, coroutines, or event loops) achieve higher throughput by overlapping wait times — though they introduce complexity around error handling, task ordering, and shared state.

---

## H3 · Task 3 / Branch H · Step 35

**Prompt:** What is the Pomodoro technique and how might it help a solo developer? One paragraph.

The Pomodoro technique is a time management method where you work in focused 25-minute intervals (called "pomodoros") separated by 5-minute breaks, with a longer 15-30 minute break after every four intervals. For a solo developer, it's particularly useful because there's no external structure or manager to keep you on track — the technique imposes rhythm and accountability on your own. It combats the two failure modes solo devs often face: hyperfocus burnout (coding for 6 hours straight and feeling wrecked) and procrastination/context-switching (bouncing between tasks without finishing anything). The forced breaks also create natural checkpoints to reassess whether you're solving the right problem, which matters when you're wearing every hat and can easily disappear down a rabbit hole for hours.

---

## H2 · Task 3 / Branch H · Step 35

**Prompt:** List 3 ways to reduce context-switching costs for a solo developer.

1. **Capture state before stopping** — Write a 2-3 line "resume note" at the top of whatever file you're working in before you close it. "Next: fix the auth middleware, then wire up the route." Costs 30 seconds, saves 10 minutes of re-orientation.

2. **Time-box context switches** — Group interruptions (Slack, email, side tasks) into fixed windows (e.g., 9am and 2pm) rather than handling them as they arrive. Keeps deep work sessions intact and makes the switches predictable and brief.

3. **One branch = one task** — Never mix concerns on a branch. If a new idea surfaces mid-task, open a GitHub issue or drop it in a notes file and stay on the current branch. Switching mental models mid-branch is the most expensive kind of context switch.

---

## I1 · Task 3 / Branch I · Step 37

**Prompt:** What is scope creep and how can a solo developer prevent it? One paragraph.

Scope creep is the gradual, often unplanned expansion of a project's features, requirements, or goals beyond what was originally defined — usually driven by "just one more thing" thinking, undefined boundaries, or stakeholder (including your own) feedback during development. For a solo developer, the best defenses are: write a brief spec or feature list before coding and treat it as a contract with yourself; use a simple backlog (even a text file) to capture new ideas without acting on them immediately; time-box work with clear "done" criteria per task; and ruthlessly ask *"does this serve the current milestone?"* before adding anything. The backlog isn't a commitment — it's a parking lot that keeps you focused now while preserving ideas for later.

---

## H4 · Task 3 / Branch H · Step 37

**Prompt:** Give 2 examples of how AI can assist with project estimation for a solo developer.

**1. Task breakdown and time estimation**

You describe a feature in plain language, and AI helps decompose it into concrete subtasks with rough time estimates based on typical complexity. For example: "Add user authentication" → AI lists: schema design (1h), API routes (2h), JWT middleware (1h), frontend forms (2h), testing (1h) = ~7h. It can also flag hidden complexity you might underestimate (e.g., password reset flows, session expiry).

**2. Historical comparison and risk flagging**

AI can review your past project notes or codebase and identify patterns — "Last time you added a payment integration it took 3x the estimate due to webhook handling." Without a team's collective memory, solo devs lose this institutional knowledge between projects. AI acts as a persistent record that surfaces relevant past experience to calibrate new estimates before you commit to a deadline.

---

## I3 · Task 3 / Branch I · Step 39

**Prompt:** Describe the concept of 'bikeshedding' and why it's a risk for solo developers. 2 sentences.

**Bikeshedding** is the tendency to spend disproportionate time on trivial, easy-to-discuss decisions (like what color to paint a bike shed) while neglecting complex, harder-to-engage-with problems. For solo developers, it's especially dangerous because there's no team to redirect focus — you can lose hours debating folder structure or variable naming while core architecture remains unbuilt.

---

## I2 · Task 3 / Branch I · Step 39

**Prompt:** List 3 warning signs that a solo software project is at risk of failure.

1. **Scope creep without a clear MVP** — Continuously adding features before shipping anything means you'll run out of motivation (or money) before users ever validate the idea.

2. **No external accountability** — Without deadlines, users, or collaborators holding you to commitments, work expands indefinitely and momentum dies quietly.

3. **Avoiding the hard parts** — Spending time on polish, tooling, or low-priority tasks instead of the core technical or business risk is a sign the project is stalling on the thing that will actually make or break it.

---

## J2 · Task 4 / Branch J · Step 41

**Prompt:** Describe the DRY (Don't Repeat Yourself) principle in one sentence with a concrete example.

DRY means every piece of knowledge should have a single authoritative source — for example, instead of hardcoding `tax_rate = 0.15` in five different functions, define it once as a constant and reference it everywhere.

---

## J1 · Task 4 / Branch J · Step 41

**Prompt:** What are 3 principles of clean code that every solo developer should follow?

**3 Clean Code Principles Every Solo Developer Should Follow**

---

**1. Intention-Revealing Names**

Name variables, functions, and files so the *why* is obvious without a comment. If you need a comment to explain what something does, the name failed.

```python
# Bad
def calc(x, y):
    return x * y * 0.13

# Good
def calculate_tax(price, quantity):
    TAX_RATE = 0.13
    return price * quantity * TAX_RATE
```

---

**2. Functions Do One Thing**

A function should have one reason to change. If you can describe it with "and", split it. This makes testing and debugging dramatically faster — especially solo when there's no one to ask.

```js
// Bad — validates AND saves AND sends email
function submitUser(data) { ... }

// Good — each step is testable in isolation
function validateUser(data) { ... }
function saveUser(user) { ... }
function notifyUser(user) { ... }
```

---

**3. Leave It Better Than You Found It (Boy Scout Rule)**

You won't have code reviews to catch decay. Every time you touch a file, make one small improvement — rename a confusing variable, extract a magic number into a constant, delete dead code. Compounding small improvements prevents the codebase from rotting over time.

---

The core idea behind all three: **code is read far more than it's written**, and as a solo dev, your future self is your only teammate.

---

## J4 · Task 4 / Branch J · Step 43

**Prompt:** Pick 3 of the SOLID principles and explain each in one bullet point.

- **S — Single Responsibility**: A class/module should have one reason to change — keep each unit focused on one job so changes are isolated and predictable.
- **O — Open/Closed**: Code should be open for extension but closed for modification — add new behavior by extending, not by editing existing, tested code.
- **D — Dependency Inversion**: High-level modules shouldn't depend on low-level ones; both should depend on abstractions — program to interfaces, not concrete implementations.

---

## J3 · Task 4 / Branch J · Step 43

**Prompt:** What is a code smell? Give 3 examples.

A **code smell** is a surface-level symptom in code that suggests a deeper problem — not necessarily a bug, but an indicator of poor design that makes code harder to understand, maintain, or extend.

---

**1. Long Method**
A function that does too many things. It's hard to read, test, and reuse.

```python
def process_order(order):
    # validate
    if not order.items:
        raise ValueError("empty")
    if order.total < 0:
        raise ValueError("negative total")
    # apply discount
    if order.customer.is_vip:
        order.total *= 0.9
    # charge
    charge_card(order.customer.card, order.total)
    # send email
    send_email(order.customer.email, f"Order {order.id} confirmed")
    # update inventory
    for item in order.items:
        inventory[item.id] -= item.quantity
```
*Fix: extract `validate_order()`, `apply_discount()`, `notify_customer()`, etc.*

---

**2. Duplicate Code**
The same logic copy-pasted in multiple places. A bug fix must be applied everywhere, and it often isn't.

```js
// In UserController
const name = (user.firstName + ' ' + user.lastName).trim();

// In EmailService (identical logic)
const name = (user.firstName + ' ' + user.lastName).trim();
```
*Fix: extract a shared `getFullName(user)` utility.*

---

**3. Magic Numbers / Strings**
Unexplained literal values scattered through code. No one knows what `86400` means six months later.

```python
if session_age > 86400:
    logout(user)

if status == 3:
    send_reminder()
```
*Fix: use named constants — `SESSION_TIMEOUT_SECONDS = 86400`, `STATUS_PENDING = 3`.*

---

The common thread: code smells increase **cognitive load** and **change risk**. They're signals to refactor, not necessarily emergencies.

---

## J5 · Task 4 / Branch J · Step 45

**Prompt:** What is test-driven development (TDD)? Describe it in 2 sentences.

Test-driven development (TDD) is a software development practice where you write failing tests *before* writing the implementation code, then write the minimum code needed to make those tests pass. The cycle repeats in short iterations: Red (write a failing test) → Green (make it pass) → Refactor (clean up the code).

---

## J6 · Task 4 / Branch J · Step 45

**Prompt:** List 3 benefits of writing unit tests for a solo developer project.

1. **Catch regressions instantly** — When you change code weeks later, tests tell you immediately if something broke, without manually re-testing every feature.

2. **Confidence to refactor** — You can restructure or optimize code knowing the tests will flag any behavior changes, making improvements less risky.

3. **Forces better design** — Writing testable code naturally leads to smaller, more focused functions with clear inputs/outputs, improving overall code quality.

---

## J8 · Task 4 / Branch J · Step 47

**Prompt:** Describe the difference between unit tests and integration tests in one sentence each.

**Unit tests** verify that individual functions or components work correctly in isolation, with dependencies mocked or stubbed out.

**Integration tests** verify that multiple components or systems work correctly together, using real dependencies and testing the interactions between them.

---

## J7 · Task 4 / Branch J · Step 47

**Prompt:** What is a linter and why should solo developers use one? One paragraph.

A linter is a static analysis tool that automatically scans your code for syntax errors, stylistic inconsistencies, and common programming mistakes without running the code. For solo developers, linters are especially valuable because they replace the peer reviewer you don't have — catching bugs like undefined variables, unused imports, unreachable code, or accidental `=` vs `==` comparisons before they cause runtime failures. They also enforce consistent style automatically, so your codebase stays readable even when you're jumping between projects after weeks away. Tools like ESLint (JavaScript), Pylint/Ruff (Python), or RuboCop (Ruby) integrate directly into your editor and give instant feedback, making them a low-cost habit with high payoff for anyone working without a team to catch their mistakes.

---

## K1 · Task 4 / Branch K · Step 49

**Prompt:** What is semantic versioning (semver)? Give one example of a version bump and why.

Semantic versioning (semver) is a versioning scheme with the format **MAJOR.MINOR.PATCH**.

- **MAJOR** — breaking changes (incompatible API changes)
- **MINOR** — new backwards-compatible features
- **PATCH** — backwards-compatible bug fixes

**Example:**

`1.4.2` → `1.5.0`

A new optional parameter is added to an existing function. Existing callers still work unchanged, so it's a **minor** bump. The patch resets to `0` because it's a new baseline.

---

## K2 · Task 4 / Branch K · Step 49

**Prompt:** List 3 best practices for writing clear git commit messages.

1. **Use the imperative mood in the subject line** — Write "Add login validation" not "Added login validation" or "Adding login validation". This matches git's own generated messages and reads naturally as a command.

2. **Keep the subject line under 50 characters** — Short subjects display cleanly in `git log`, GitHub, and most tooling. If you need more detail, leave a blank line after the subject and write a body explaining *why* the change was made, not *what* (the diff shows what).

3. **Scope each commit to a single logical change** — One commit should do one thing. This makes `git bisect`, `git revert`, and code review far easier. If you find yourself writing "and" in the subject line, consider splitting the commit.

---

## K4 · Task 4 / Branch K · Step 51

**Prompt:** Describe the concept of self-code-review for a solo developer. 2 sentences.

Self-code-review is the practice of critically examining your own code after a deliberate pause — treating it as if someone else wrote it — to catch bugs, logic errors, and unclear patterns before merging or shipping. For a solo developer, it replaces the team PR review loop and is most effective when done with fresh eyes, using a checklist or diff view to force a systematic read rather than skimming what you expect to see.

---

## K3 · Task 4 / Branch K · Step 51

**Prompt:** What is a pull request and how does it help with code quality? One paragraph.

A pull request (PR) is a mechanism in Git-based workflows (GitHub, GitLab, Bitbucket) where a developer proposes merging code from one branch into another, typically from a feature branch into `main`. It creates a structured review process where teammates can inspect the diff, leave inline comments, request changes, and run automated checks (CI/CD pipelines, linting, tests) before any code lands in the shared codebase. This improves code quality by catching bugs, enforcing style consistency, sharing knowledge across the team, and ensuring that no single person's unreviewed code reaches production — essentially turning code submission into a collaborative checkpoint rather than a unilateral action.

---

## K5 · Task 4 / Branch K · Step 53

**Prompt:** What is continuous deployment and how does it benefit a solo developer project? 2 sentences.

**Continuous deployment (CD)** is an automated practice where every code change that passes tests is automatically deployed to production without manual intervention.

For a solo developer, it eliminates repetitive deployment chores, reduces human error, and lets you ship features faster so you can focus on building rather than ops.

---

## L1 · Task 5 / Branch L · Step 53

**Prompt:** What are 3 key metrics a solo developer should track for a CLI tool project?

Three key metrics worth tracking:

1. **Command error rate** — ratio of failed invocations (non-zero exits, unhandled exceptions) to total runs. Catches regressions fast and shows which subcommands are fragile.

2. **Time-to-first-output** — how quickly the CLI produces its first line of output or completes for common commands. Users abandon slow CLIs; this keeps you honest about startup cost and latency.

3. **Adoption / active installs over time** — downloads from npm/PyPI/homebrew plus weekly active users if you have telemetry. As a solo dev, this tells you whether to keep investing or pivot before you over-engineer a tool nobody uses.

A lightweight way to track all three without infrastructure: structured log files per invocation (command, duration, exit code, version), then parse them periodically with a short Python script.

---

## L2 · Task 5 / Branch L · Step 55

**Prompt:** Describe the concept of a project roadmap in 2 sentences.

A project roadmap is a high-level visual or strategic plan that outlines the goals, milestones, and timeline for a project's development. It communicates the direction and priorities to stakeholders, helping teams align on what needs to be built and in what order.

---

## L3 · Task 5 / Branch L · Step 55

**Prompt:** List 3 ways to gather user feedback on a solo developer CLI tool.

Here are 3 practical ways to gather user feedback on a solo developer CLI tool:

1. **GitHub Issues with a feedback template** — Add an issue template that prompts users for their use case, what broke or felt clunky, and their environment. Low friction for developers already on GitHub.

2. **In-tool feedback prompt** — After key commands, occasionally print a one-liner like `Found a bug or have feedback? → github.com/you/tool/issues`. Even better, add a `tool feedback` subcommand that opens the browser to a pre-filled issue.

3. **Usage analytics with opt-in telemetry** — Log anonymized command usage (which flags are used, error rates, command frequency) via a lightweight service like PostHog or a simple endpoint. Pair with explicit opt-in on first run so users consent. This surfaces real usage patterns without requiring active user effort.

---

## L4 · Task 5 / Branch L · Step 57

**Prompt:** What is feature prioritization and why is it important for solo developers? One paragraph.

Feature prioritization is the process of ranking potential features or tasks by their relative value, impact, and cost so you know what to build next. For solo developers, it's especially critical because you have no team to parallelize work — every hour spent on the wrong feature is an hour not spent on something that matters. Good prioritization helps you ship the highest-value functionality first, avoid building things users don't want, and maintain momentum without burning out on low-impact work. Frameworks like MoSCoW (Must/Should/Could/Won't), RICE scoring, or simply asking "does this move the needle on my core metric?" give you a repeatable way to cut through the noise and stay focused on what actually drives user value or business outcomes.

---

## L5 · Task 5 / Branch L · Step 57

**Prompt:** Describe 2 ways AI can help a solo developer with project documentation.

## AI for Solo Developer Documentation

**1. Auto-generating docs from code**
AI can read your source code and produce README files, API references, inline comments, and changelogs — inferring intent from function names, types, and usage patterns. This is particularly valuable for solo devs who write code fast but rarely circle back to document it.

**2. Keeping docs in sync with changes**
As code evolves, AI can diff what changed and flag or update stale documentation. Instead of docs drifting out of date over months, you can prompt AI to review a file after a refactor and rewrite only the affected sections — no full rewrite needed.

---

## L6 · Task 5 / Branch L · Step 59

**Prompt:** What is a changelog and why should every project have one? One sentence.

A changelog is a curated, human-readable file that records notable changes made to a project over time, so users and contributors can quickly understand what changed between versions without reading the full commit history.

---

## M1 · Task 5 / Branch M · Step 59

**Prompt:** List 3 strategies for getting early users for a solo developer tool.

1. **Post in watering holes where your target users already are** — Reddit (r/programming, r/webdev, r/devtools), Hacker News "Show HN", Discord servers, and niche Slack communities. Lead with the problem you solve, not the product.

2. **Build in public on X/Twitter or LinkedIn** — Share the development process, wins, and struggles. This builds an audience before launch and attracts early adopters who feel invested in the project.

3. **Direct outreach to a narrow ICP** — Find 20–30 people who match your ideal user profile (GitHub, LinkedIn, dev forums) and send personal messages offering free access in exchange for 15-minute feedback calls. Quality over quantity at this stage.

---

## M2 · Task 5 / Branch M · Step 61

**Prompt:** What is developer experience (DX) and why does it matter? One paragraph.

Developer experience (DX) refers to the overall quality of a developer's interactions with tools, APIs, frameworks, documentation, and workflows — essentially, how easy and pleasant it is to build software. It matters because friction in the development process directly translates to slower iteration cycles, more bugs, higher onboarding costs, and developer frustration that leads to burnout and attrition. Good DX means clear error messages, intuitive APIs, fast feedback loops (fast builds, hot reload, useful logs), comprehensive docs, and tooling that gets out of the way. When DX is prioritized, developers spend more time solving actual problems and less time fighting their tools — which compounds into faster product delivery, fewer mistakes, and teams that want to stay and build.

---

## M3 · Task 5 / Branch M · Step 61

**Prompt:** Describe 2 ways to measure whether a solo developer project is succeeding.

Two practical ways to measure success for a solo developer project:

## 1. User/Revenue Traction
Track whether real people are paying or actively using it — signups, MAU, MRR, churn rate. Growth (even small but consistent) is a signal the project solves a real problem. Flat or declining numbers over 2-3 months despite effort signal a positioning or product problem.

## 2. Shipping Velocity vs. Scope Creep
Measure how often you ship working features versus how often tasks stall or bloat. A healthy project has a steady cadence of small, completed milestones. If your backlog grows faster than you ship, or you keep refactoring without releasing, the project is likely failing on execution even if the idea is good.

The first measures *market fit*, the second measures *execution health* — both matter independently.

---

## M4 · Task 5 / Branch M · Step 63

**Prompt:** What is open source and what are 2 benefits of open-sourcing a solo developer project?

Open source means making your project's source code publicly available for anyone to view, use, modify, and distribute.

**2 benefits for a solo developer:**

1. **Community contributions** — Others can submit bug fixes, features, and improvements, effectively giving you free collaborators without hiring anyone.

2. **Credibility and visibility** — Public code serves as a live portfolio. Employers, clients, and other developers can inspect your actual work, which builds trust and reputation faster than any resume.

---

## N1 · Task 5 / Branch N · Step 63

**Prompt:** What are 3 signs that a software project is ready for its first public release?

1. **Core functionality is stable and tested** — The primary use cases work reliably, critical bugs are fixed, and there's a baseline of automated tests or manual QA confirming nothing obviously breaks.

2. **The public interface is something you're willing to support** — APIs, CLI flags, config formats, or UI flows are intentional enough that you won't need to immediately break them. Early adopters will build on what you ship.

3. **Onboarding works without your help** — A stranger can install, configure, and use the project using only the README/docs, without needing to ask you questions. If you have to explain it verbally, it's not ready.

---

## N2 · Task 5 / Branch N · Step 65

**Prompt:** Describe the concept of a 'soft launch' for a developer tool. 2 sentences.

A soft launch is a limited, low-key release of a tool to a small subset of users (often early adopters, beta testers, or internal teams) before the full public launch. It lets developers gather real-world feedback, catch bugs, and refine the experience without the pressure or visibility of an official announcement.

---

## N3 · Task 5 / Branch N · Step 65

**Prompt:** List 3 things a developer should document before releasing an open-source project.

1. **README** — Project purpose, installation steps, and a quick-start usage example.

2. **API / public interface** — All public functions, classes, config options, and their expected inputs/outputs.

3. **Contributing guidelines** — How to report bugs, submit PRs, coding standards, and the code of conduct.

---

## N5 · Task 5 / Branch N · Step 67

**Prompt:** Write a one-sentence mission statement for Solo Builder — an AI-powered CLI that manages DAG-based tasks for solo developers.

**Solo Builder** is an AI-powered CLI that helps solo developers orchestrate complex projects through intelligent DAG-based task management, automating the repetitive work so you can focus on building.

---

## N4 · Task 5 / Branch N · Step 67

**Prompt:** What is a README file and what are its 3 most important sections? One sentence each.

A README file is a text document placed at the root of a project that serves as the first point of reference for anyone encountering the codebase.

**3 most important sections:**

1. **What it is** — A brief description of the project's purpose and what problem it solves.
2. **How to install/run it** — Step-by-step setup instructions so someone can get the project running locally.
3. **How to use it** — Basic usage examples or commands that demonstrate the project's core functionality.

---

## A2 · Task 0 / Branch A · Step 2

**Prompt:** Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.

**Solo Builder** is a Python terminal CLI that leverages AI agents to manage complex projects as dependency-aware task graphs (DAGs), automatically sequencing work and surfacing what's actionable right now. Built for solo developers and indie hackers, it replaces scattered to-do lists with an intelligent co-pilot that understands project structure and keeps you moving forward.

---

## A1 · Task 0 / Branch A · Step 2

**Prompt:** List 5 key features a solo developer AI project management tool needs. Bullet points.

- **Task & context persistence** — remembers project state, decisions, and blockers across sessions without re-explaining
- **Autonomous task breakdown** — converts vague goals into concrete, prioritized subtasks with dependencies
- **Progress tracking with smart reminders** — surfaces stale tasks and unfinished work without manual updates
- **Integrated code/repo awareness** — links tasks directly to files, commits, and PRs so context is never lost
- **Friction-free capture** — quick add from anywhere (CLI, chat, voice) so ideas don't get dropped mid-flow

---

## A4 · Task 0 / Branch A · Step 4

**Prompt:** What are 3 risks of building a self-healing agent system, and one mitigation for each?

## 3 Risks of Self-Healing Agent Systems

**1. Runaway remediation loops**
The agent misdiagnoses a problem, applies a "fix" that worsens the state, then detects the worsened state and applies another fix — cascading into an infinite loop of destructive actions.

*Mitigation:* Enforce a circuit breaker — halt self-healing after N failed remediation attempts within a time window and escalate to human review.

---

**2. Privilege escalation via repair actions**
To heal itself, the agent may need broad permissions (restart services, modify configs, redeploy). Compromising the agent or tricking it into misidentifying a "fault" becomes a vector for unauthorized system access.

*Mitigation:* Scope healing permissions to the minimum necessary per-action using least-privilege roles, and require a separate approval step for any action that modifies security boundaries (IAM, firewall rules, credentials).

---

**3. Concept drift in the health model**
The agent learns what "healthy" looks like from historical baselines. If the system gradually drifts (new traffic patterns, schema changes), the health model becomes stale — the agent either masks real failures or fires false alarms constantly.

*Mitigation:* Continuously re-evaluate the health baseline against a rolling window of ground-truth labeled incidents, and trigger a human-supervised recalibration when the false-positive/false-negative rate crosses a threshold.

---

## A3 · Task 0 / Branch A · Step 4

**Prompt:** Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.

Having read the codebase, here are 3 concrete improvements grounded in what the code actually does:

---

## 1. Wire the executor to real Claude API calls

**Current state:** `EXECUTOR_VERIFY_PROBABILITY = 0.6` — subtasks advance via random dice rolls. The `description` field on every subtask (`solo_builder_cli.py:92–96`) and the `CLAUDE_TIMEOUT` config (`settings.json:16`) clearly anticipate real execution, but the loop never calls anything.

**Improvement:** When an executor picks up a `Running` subtask, send its `description` to Claude and store the response in `output`. One `subprocess` call to `claude -p "{description}"` (headlessly) would turn the simulation into a real AI task runner — exactly what the `CLAUDE_TIMEOUT` setting is already placeholder-waiting for.

---

## 2. Resume from saved state on startup

**Current state:** Every launch resets to `INITIAL_DAG` (hardcoded at `solo_builder_cli.py:84`). The `STATE_PATH = ./state/solo_builder_state.json` config exists and auto-saves run, but startup ignores it.

**Improvement:** At boot, check if `STATE_PATH` exists and offer `[R]esume / [N]ew`. Load the persisted DAG + memory store if resuming. A solo dev working across days loses all progress on every restart — this is the single biggest friction point.

---

## 3. Generate a readable outputs report after each run

**Current state:** `solo_builder_outputs.md` exists in the project but isn't auto-populated. The PDF snapshots (`snapshots/*.pdf`) show status charts but not the actual content produced. Each subtask has an `output` field that stays empty in simulation mode.

**Improvement:** On `snapshot` or session end, write a Markdown file mapping `description → output` for every Verified subtask, grouped by task/branch. This makes the run produce a deliverable — actual answers/content — not just a status chart. A solo dev's real goal is the *outputs*, not the DAG visualization.

---

## A5 · Task 0 / Branch A · Step 6

**Prompt:** Write a tagline for Solo Builder in under 10 words.

**Build solo. Ship faster. Own everything.**

---

## B1 · Task 0 / Branch B · Step 6

**Prompt:** Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.

A **Shadow Agent** runs in parallel alongside a primary agent, silently observing its inputs and outputs without intervening — used for monitoring, logging, or A/B testing alternative behaviors without affecting the main flow.

A **Verifier Agent** actively evaluates the output of another agent against defined criteria (correctness, safety, constraints) and can block, flag, or trigger a retry if the output fails validation — acting as a quality gate rather than a passive observer.

---

## B3 · Task 0 / Branch B · Step 8

**Prompt:** In one sentence, explain what a MetaOptimizer does in an AI pipeline.

A MetaOptimizer is a higher-level optimization component that tunes the hyperparameters or learning strategies of underlying optimizers, effectively "learning how to learn" to improve overall model training efficiency.

---

## B2 · Task 0 / Branch B · Step 8

**Prompt:** List 3 real-world use cases for a DAG-based AI project tracker.

## DAG-Based AI Project Tracker — 3 Real-World Use Cases

**1. ML Pipeline Dependency Management**
Track data ingestion → feature engineering → model training → evaluation → deployment as a DAG. Automatically re-run only downstream nodes when an upstream step changes (e.g., new training data), rather than re-running the full pipeline. Tools like MLflow and DVC already do this partially.

**2. Multi-Agent Task Orchestration**
Coordinate LLM agents where outputs feed into each other — e.g., a research agent feeds a summarizer, which feeds a report writer. The DAG enforces execution order, surfaces blocked tasks, and enables parallel execution of independent branches (e.g., two research agents running simultaneously).

**3. Software Release Dependency Tracking**
Model a release as a DAG of tasks: design review → implementation → unit tests → integration tests → security audit → staging deploy → prod deploy. The tracker surfaces the critical path, flags which tasks are blocking release, and lets teams parallelize independent work (e.g., docs and tests running concurrently).

---

**Common thread:** DAGs shine when tasks have *partial order* (some must precede others, some can run in parallel) and you need visibility into blockers, progress, and re-execution scope.

---

## C1 · Task 1 / Branch C · Step 10

**Prompt:** What does a DAG (Directed Acyclic Graph) represent in software project management? Answer in one paragraph.

A DAG (Directed Acyclic Graph) in software project management represents the dependency relationships between tasks, where each node is a task and each directed edge indicates that one task must complete before another can begin — with the "acyclic" constraint ensuring there are no circular dependencies (i.e., no task can depend on itself directly or indirectly). This structure is foundational to build systems (like Make, Bazel, or Gradle), CI/CD pipelines, workflow orchestrators (like Airflow or Prefect), and package managers, because it allows the system to determine a valid execution order (topological sort), identify which tasks can run in parallel, and pinpoint the critical path — the longest chain of dependent tasks that determines the minimum total completion time.

---

## C2 · Task 1 / Branch C · Step 10

**Prompt:** List 3 advantages of using a priority queue to schedule software tasks.

1. **Efficient scheduling by importance** — Higher-priority tasks (e.g., UI updates, critical errors) are processed before lower-priority background work, ensuring responsiveness without manual sorting.

2. **O(log n) insertion and extraction** — Adding a task or pulling the next task costs O(log n) time, making it far more efficient than a sorted list (O(n) insertion) for dynamic workloads.

3. **Natural preemption support** — When a high-priority task arrives mid-queue, it automatically surfaces to the front without reordering the entire queue, making it well-suited for real-time and event-driven systems.

---

## C3 · Task 1 / Branch C · Step 12

**Prompt:** Explain the concept of task staleness in a project management system in 2 sentences.

Task staleness refers to the condition where a task has not been updated, progressed, or acted upon within an expected timeframe, causing it to fall out of sync with the current state of the project. Stale tasks can mislead teams about actual progress, create bottlenecks, and obscure blockers that need attention.

---

## C4 · Task 1 / Branch C · Step 12

**Prompt:** What is a shadow state in an agent-based system? Give one concrete example.

## Shadow State in Agent-Based Systems

**Shadow state** is a local copy of external state that an agent maintains independently, which can diverge from the actual source of truth over time.

An agent reads external state once (or periodically), caches it internally, and then makes decisions based on that cached copy — without knowing whether the real state has changed.

---

### Concrete Example: Inventory Agent

An e-commerce agent manages product restocking. At 9 AM it reads the database:

```
shadow_state = { "widget_A": 50, "widget_B": 3 }
```

The agent decides widget_B needs reordering and places a purchase order.

Meanwhile, at 9:05 AM, a human operator manually adds 200 units of widget_B directly in the database:

```
# Real DB state: { "widget_A": 50, "widget_B": 203 }
```

The agent's shadow state still shows `widget_B: 3`. It continues believing stock is critically low and may:
- Send another purchase order (duplicate order)
- Alert managers about a shortage that doesn't exist
- Block sales it could fulfill

---

### Why It Matters for Agent Systems

| Problem | Effect |
|---|---|
| **Stale reads** | Decisions based on outdated data |
| **Concurrent writers** | Other agents or humans change state the agent doesn't see |
| **Accumulating drift** | The longer the agent runs, the further shadow diverges from truth |

The fix is either **event-driven updates** (subscribe to state changes) or **re-reading authoritative state** before acting on critical decisions — rather than trusting the local shadow indefinitely.

---

## D2 · Task 1 / Branch D · Step 14

**Prompt:** What is the difference between optimistic and pessimistic task verification? One paragraph.

**Optimistic task verification** assumes a task succeeded unless evidence suggests otherwise — it proceeds immediately after an action and only checks for failures reactively (e.g., catching exceptions or checking results after the fact). **Pessimistic task verification** assumes a task may have failed and actively confirms success before proceeding — it waits for explicit confirmation, polls for state changes, or validates preconditions and postconditions at each step. Optimistic verification is faster and lower-overhead but risks cascading failures when an undetected error propagates through subsequent steps; pessimistic verification is slower and more defensive but catches problems early and prevents work built on a faulty foundation, making it preferable for irreversible or high-stakes operations.

---

## D1 · Task 1 / Branch D · Step 14

**Prompt:** Describe 2 strategies for preventing task starvation in a priority-based scheduler.

## Preventing Task Starvation in Priority-Based Schedulers

### 1. Aging

Gradually increase the priority of a waiting task over time. The longer a task waits without being scheduled, the higher its effective priority climbs — eventually surpassing higher-priority tasks that keep arriving.

- **Example**: Every N milliseconds a task spends waiting, its priority increments by 1. A low-priority task that has waited long enough will eventually reach max priority and run.
- **Tradeoff**: Requires tracking wait time per task and recomputing effective priority on each scheduling decision.

### 2. Priority Ceiling / Time-Sliced Bands

Divide the scheduler into priority bands, and guarantee a minimum CPU time allocation to each band per scheduling epoch (a fixed time window). Even the lowest band gets a slice before the epoch resets.

- **Example**: In a 100ms epoch, the top band gets 60ms, mid gets 30ms, and low gets 10ms — regardless of how many high-priority tasks are queued.
- **Tradeoff**: High-priority work is throttled slightly to fund the guarantee; tuning band ratios matters a lot under load.

---

**Key distinction**: Aging is *reactive* — it rescues already-starving tasks by elevating them. Band-based guarantees are *proactive* — they structurally prevent starvation by reserving capacity upfront.

---

## E2 · Task 2 / Branch E · Step 16

**Prompt:** Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.

A MetaOptimizer learns from an agent's historical performance data — tracking which strategies, prompts, or hyperparameters led to better outcomes — and automatically adjusts the agent's configuration to favor higher-performing approaches over time. By treating the optimization process itself as a learning problem, it enables agents to compound improvements across sessions rather than starting fresh each run.

---

## E1 · Task 2 / Branch E · Step 16

**Prompt:** What are 3 benefits of self-healing automation in a software pipeline?

1. **Reduced downtime** — Automated detection and recovery from failures (flaky tests, transient network errors, crashed services) keeps pipelines running without waiting for human intervention.

2. **Lower operational burden** — Engineers spend less time on reactive firefighting (restarting stuck jobs, re-triggering failed deploys) and more time on feature work.

3. **Faster feedback loops** — Automatic retries, rollbacks, and self-correction mean failures resolve in seconds/minutes rather than hours, so code quality signals reach developers quickly.

---

## E4 · Task 2 / Branch E · Step 18

**Prompt:** What is the difference between reactive and proactive error handling in agent systems? One sentence each.

**Reactive**: The agent detects and responds to errors *after* they occur (e.g., catching exceptions, retrying failed tool calls).

**Proactive**: The agent anticipates and prevents errors *before* they occur (e.g., validating inputs, checking preconditions, planning for known failure modes).

---

## E3 · Task 2 / Branch E · Step 18

**Prompt:** List 3 metrics that indicate an AI agent system is performing well.

Here are 3 key metrics for evaluating AI agent system performance:

1. **Task Completion Rate** — The percentage of tasks the agent successfully completes end-to-end without human intervention or failure. Higher is better; low rates indicate reasoning gaps, tool failures, or unclear goal handling.

2. **Latency / Time-to-Resolution** — How long the agent takes to complete tasks from start to finish, including tool calls and reasoning steps. Useful for identifying inefficiencies in planning or excessive back-and-forth.

3. **Hallucination / Error Rate** — The frequency of factually incorrect outputs, failed tool calls, or logical errors per task. Low error rates signal reliable grounding and good tool use; high rates indicate the agent is guessing rather than verifying.

---

## F1 · Task 2 / Branch F · Step 20

**Prompt:** What is the role of a Verifier agent in a multi-agent pipeline? 2 sentences.

A Verifier agent checks the output of other agents for correctness, completeness, or adherence to requirements before passing results downstream. It acts as a quality gate, catching errors or hallucinations early to prevent bad data from propagating through the pipeline.

---

## E5 · Task 2 / Branch E · Step 20

**Prompt:** Give one example of a heuristic weight that a MetaOptimizer might adjust in a task planner.

A **MetaOptimizer** might adjust the **urgency decay rate** — the weight that controls how quickly a task's priority score increases as its deadline approaches.

For example:

```
priority_score = base_importance * (1 + urgency_weight * e^(time_remaining / deadline))
```

If the optimizer observes that tasks are consistently being picked up too late (deadline misses are common), it increases `urgency_weight` so the exponential ramp starts steeper and earlier — causing the planner to pull deadline-sensitive tasks into the active queue sooner.

Conversely, if the planner is constantly preempting long-running tasks to service near-deadline work (causing fragmentation and context-switch overhead), the optimizer reduces `urgency_weight` to smooth out the priority curve.

---

## F3 · Task 2 / Branch F · Step 22

**Prompt:** List 2 ways a ShadowAgent could detect state inconsistencies in a DAG pipeline.

Two ways a ShadowAgent could detect state inconsistencies in a DAG pipeline:

**1. Checksum / Hash Comparison at Node Boundaries**

The ShadowAgent shadows each node's output by computing a deterministic hash (e.g., SHA-256) of the output payload before it propagates downstream. On replay or re-execution, it recomputes the hash and compares — a mismatch signals that a node produced a different result given the same inputs, indicating non-determinism, a mutated upstream dependency, or silent data corruption mid-pipeline.

**2. Topological Epoch Versioning**

Each node in the DAG is assigned a monotonically increasing epoch counter tied to its execution order. The ShadowAgent tracks expected vs. observed epoch sequences for every edge. If a downstream node's epoch is higher than its upstream parent's, or if two sibling nodes share the same epoch when they shouldn't, it reveals out-of-order execution, a skipped node, or a cycle that violated the acyclic constraint — all forms of state inconsistency.

---

Both approaches are complementary: hash comparison catches **data-level drift**, while epoch versioning catches **execution-order drift**.

---

## F2 · Task 2 / Branch F · Step 22

**Prompt:** Describe how memory snapshots help with debugging in an agent system. One paragraph.

Memory snapshots capture the full state of an agent's working memory — variables, conversation history, tool call results, task queues — at a specific point in time, creating a reproducible checkpoint you can inspect after a failure. When an agent produces unexpected output or crashes mid-task, you can load the snapshot and replay execution from that exact state rather than re-running the entire job from scratch, which is especially valuable in long multi-step workflows where the failure occurs late in the chain. Snapshots also let you compare states before and after a suspicious action (a tool call, an LLM response, a memory update) to isolate exactly where reasoning went wrong, turning an otherwise opaque "the agent did something weird" into a concrete diff between two known states. In multi-agent systems, per-agent snapshots additionally help you trace which agent introduced a bad assumption that cascaded downstream — acting as the equivalent of a core dump for distributed, non-deterministic AI processes.

---

## F4 · Task 2 / Branch F · Step 24

**Prompt:** What is the difference between a branch and a task in a DAG-based project tracker? One sentence.

A **branch** represents a line of development (a sequence of commits diverging from a common ancestor), while a **task** is a discrete unit of work tracked in the project — branches are a version control concept, tasks are a project management concept.

---

## G1 · Task 3 / Branch G · Step 24

**Prompt:** What is continuous integration and how does it relate to automated project management? One paragraph.

Continuous integration (CI) is a software development practice where developers frequently merge code changes into a shared repository — typically multiple times per day — and each merge triggers an automated pipeline that builds the project, runs tests, and reports results. It relates to automated project management in that CI systems (like GitHub Actions, GitLab CI, or Jenkins) can be extended beyond just building and testing to automatically update task boards, close issues when tests pass, trigger deployments, notify team channels, generate reports, and enforce quality gates that gate progress on a project. This tight feedback loop means project state (what's done, what's broken, what's blocked) stays synchronized with the actual code, reducing manual overhead and giving project managers real-time visibility into health and progress without requiring developers to manually update tickets or status trackers.

---

## G3 · Task 3 / Branch G · Step 26

**Prompt:** Describe the MVP (Minimum Viable Product) concept in 2 sentences.

An MVP is the simplest version of a product that delivers core value to early users and validates key assumptions with minimal development effort. It prioritizes learning over features, allowing you to gather real feedback before investing in a full build.

---

## G2 · Task 3 / Branch G · Step 26

**Prompt:** List 3 common causes of technical debt in solo developer projects.

1. **Skipping tests** — Moving fast without unit/integration tests means bugs compound and refactoring becomes risky.

2. **Premature abstractions (or none at all)** — Either over-engineering early ("I might need this later") or copy-pasting instead of extracting shared logic, both create maintenance burden.

3. **Deferred dependency updates** — Letting packages fall behind means larger, riskier upgrade jumps later, often with breaking changes that cascade through the codebase.

---

## G4 · Task 3 / Branch G · Step 28

**Prompt:** What is a sprint in agile methodology? One sentence.

A sprint is a fixed-length iteration (typically 1–4 weeks) in which a development team completes a set of prioritized work items from the backlog.

---

## G5 · Task 3 / Branch G · Step 28

**Prompt:** List 3 developer tools a solo builder could use alongside an AI task manager.

Here are 3 developer tools that pair well with an AI task manager for solo builders:

1. **Linear** — Lightweight issue tracking with keyboard-first UX. Great for turning AI-generated tasks into structured tickets with priorities and cycles.

2. **Vercel** — Zero-config deployments with instant preview URLs per commit. Lets you ship fast without devops overhead, so you stay focused on building.

3. **Supabase** — Postgres + auth + storage in one hosted platform. Reduces the infrastructure surface area a solo builder needs to manage, pairing well with AI-generated backend code.

---

## H1 · Task 3 / Branch H · Step 30

**Prompt:** Describe the concept of a 'Definition of Done' in software projects. 2 sentences.

A **Definition of Done** (DoD) is a shared, explicit checklist of criteria that must be met before a work item (feature, task, or story) is considered complete — covering things like code review, tests passing, documentation, and deployment. It prevents ambiguity about "done" by ensuring all team members apply the same quality standard consistently.

---

## G6 · Task 3 / Branch G · Step 30

**Prompt:** What is the difference between async and sync task execution in pipelines? One paragraph.

In a pipeline, **synchronous (sync) execution** processes tasks sequentially — each task must complete before the next begins, blocking the thread until it finishes, which is simple to reason about but wastes time when tasks involve waiting (I/O, network, disk). **Asynchronous (async) execution** allows tasks to be initiated without blocking the caller — when a task hits a wait point (e.g., a network request), control is yielded back so other tasks can run concurrently on the same thread (via an event loop, as in Node.js or Python's `asyncio`), or tasks are dispatched to separate threads/processes and results are collected later via callbacks, promises, or futures. The key practical difference is throughput: sync pipelines serialize work and are bottlenecked by the slowest step, while async pipelines overlap I/O-bound work and can saturate available resources — though async introduces complexity around error handling, ordering guarantees, and backpressure management.

---

## H2 · Task 3 / Branch H · Step 32

**Prompt:** List 3 ways to reduce context-switching costs for a solo developer.

Here are 3 ways to reduce context-switching costs for a solo developer:

1. **Batch similar work into time blocks** — Group all code reviews, emails, and deploys into dedicated slots rather than interleaving them with deep work. Protect at least one 2–3 hour uninterrupted block daily for complex coding.

2. **Write "re-entry notes" before stopping work** — Before closing a task, write 2–3 sentences: what you were doing, what's broken/in-progress, and the next step. This eliminates the costly "where was I?" ramp-up when you return.

3. **Minimize WIP (work in progress)** — Finish one feature branch before starting another. Multiple open PRs, half-done refactors, and stale branches create cognitive overhead every time you `git status`. Fewer open loops = faster context reload.

---

## H3 · Task 3 / Branch H · Step 32

**Prompt:** What is the Pomodoro technique and how might it help a solo developer? One paragraph.

The Pomodoro technique is a time management method where you work in focused 25-minute intervals (called "pomodoros") separated by 5-minute breaks, with a longer 15-30 minute break after every four cycles. For a solo developer, it's particularly useful because it combats the two biggest productivity killers in solo work: endless context-switching and the illusion of progress from scattered, unfocused effort. By committing to a single task for 25 minutes with no interruptions — no Slack, no email, no "quick" tab switches — you build momentum and actually finish things. The mandatory breaks prevent burnout and give your brain time to consolidate what you just worked on, which matters a lot for debugging and design thinking. It also creates a natural rhythm for a workday that otherwise has no external structure, which is one of the hardest challenges of working alone.

---

## I1 · Task 3 / Branch I · Step 34

**Prompt:** What is scope creep and how can a solo developer prevent it? One paragraph.

Scope creep is the gradual expansion of a project's requirements beyond its original boundaries, often caused by adding "just one more feature," accommodating new stakeholder requests, or discovering unexpected complexity mid-build — and for a solo developer it's especially dangerous because there's no team to push back or absorb the extra work. To prevent it, define a tight written spec before coding (even a single-page doc listing what's explicitly **in** and **out** of scope), use a strict prioritization method like MoSCoW (Must/Should/Could/Won't), time-box features so each one has a deadline, and ruthlessly defer anything that wasn't in the original spec to a "v2 backlog" rather than folding it in mid-sprint — the discipline of writing "v2" next to an idea rather than implementing it immediately is one of the most powerful habits a solo builder can develop.

---

## H4 · Task 3 / Branch H · Step 34

**Prompt:** Give 2 examples of how AI can assist with project estimation for a solo developer.

## AI-Assisted Project Estimation for Solo Developers

**1. Breaking Down Tasks and Generating Time Estimates**

A solo dev can describe a feature (e.g., "Add OAuth login with Google") and ask an AI to decompose it into subtasks with rough hour estimates. The AI draws on patterns from similar projects to flag hidden complexity — things like token refresh logic, session handling, and error states that are easy to underestimate. The result is a task list with estimates the dev can adjust based on their own skill level.

**2. Historical Pattern Matching Against Scope Creep**

After a few projects, a dev can feed AI their past estimates vs. actuals and ask it to identify where they consistently over- or under-estimate. The AI surfaces patterns like "you always underestimate database migration work by 3x" or "UI polish tasks run 50% over" — turning past mistakes into a calibration factor applied automatically to future estimates.

---

Both examples work well for solo developers because there's no team to do informal calibration with — AI acts as a second perspective on scope and effort.

---

## I2 · Task 3 / Branch I · Step 36

**Prompt:** List 3 warning signs that a solo software project is at risk of failure.

1. **Scope creep without shipping** — Continuously adding features before releasing anything. If you haven't shipped a working version after weeks of work, the project rarely recovers.

2. **No real user feedback loop** — Building in isolation based on assumptions. If no one outside yourself has used or validated the core idea, you're likely solving a problem that doesn't exist or building the wrong solution.

3. **Avoided the hardest problem** — Spending time on UI, tooling, or peripheral features while the core technical or business challenge remains untouched. This is usually procrastination disguised as progress.

---

## I3 · Task 3 / Branch I · Step 36

**Prompt:** Describe the concept of 'bikeshedding' and why it's a risk for solo developers. 2 sentences.

**Bikeshedding** is the tendency to spend disproportionate time on trivial, easy-to-discuss decisions (like what color to paint a bike shed) while neglecting complex, critical ones. For solo developers, it's especially dangerous because there's no team to redirect focus — you can burn hours debating folder naming conventions or color palettes while core features remain unbuilt.

---

## J2 · Task 4 / Branch J · Step 38

**Prompt:** Describe the DRY (Don't Repeat Yourself) principle in one sentence with a concrete example.

DRY means every piece of knowledge should have a single, authoritative representation in a codebase — for example, instead of hardcoding `0.08` in five different tax calculation functions, define `TAX_RATE = 0.08` once and reference it everywhere.

---

## J1 · Task 4 / Branch J · Step 38

**Prompt:** What are 3 principles of clean code that every solo developer should follow?

1. **Write code for your future self, not the current moment.** You'll forget context. Use clear, intention-revealing names over abbreviations or clever tricks. `calculateMonthlyRevenue()` beats `calcRev()` every time.

2. **Small functions, single responsibility.** If you can't describe what a function does in one sentence without using "and", split it. Short functions are easier to test, debug, and reuse.

3. **Delete dead code immediately.** As a solo dev, there's no one else to clean up commented-out blocks or unused functions. They become noise that slows you down. Version control is your safety net — trust it and delete freely.

---

## J4 · Task 4 / Branch J · Step 40

**Prompt:** Pick 3 of the SOLID principles and explain each in one bullet point.

- **Single Responsibility Principle**: A class should have only one reason to change — each class does one thing and owns it completely.
- **Open/Closed Principle**: Code should be open for extension but closed for modification — add new behavior by extending, not by editing existing code.
- **Dependency Inversion Principle**: High-level modules should not depend on low-level modules; both should depend on abstractions — program to interfaces, not implementations.

---

## J3 · Task 4 / Branch J · Step 40

**Prompt:** What is a code smell? Give 3 examples.

A **code smell** is a surface-level indication in source code that something may be poorly designed — not necessarily a bug, but a sign that the code could be hard to maintain, understand, or extend.

---

## 3 Examples

**1. Long Method**
A function that does too many things and spans dozens of lines. Hard to test and understand at a glance.
```python
def process_order(order):
    # validate input (20 lines)
    # calculate taxes (15 lines)
    # apply discounts (10 lines)
    # send confirmation email (15 lines)
    # update inventory (20 lines)
```

**2. Duplicate Code**
The same logic copy-pasted in multiple places. A bug fix must be applied everywhere, and one is inevitably missed.
```js
// in UserService
const name = user.firstName + ' ' + user.lastName;

// in EmailService (identical logic, different place)
const name = user.firstName + ' ' + user.lastName;
```

**3. Magic Numbers**
Hardcoded literals with no explanation of what they mean.
```python
if user.age >= 13 and user.age < 18:  # What's special about 13 and 18?
    apply_discount(price * 0.15)       # Why 0.15?
```
Better: `if MIN_TEEN_AGE <= user.age < MAX_TEEN_AGE`

---

The term was popularized by Martin Fowler in *Refactoring* (1999). Code smells aren't always wrong, but they warrant a second look.

---

## J5 · Task 4 / Branch J · Step 42

**Prompt:** What is test-driven development (TDD)? Describe it in 2 sentences.

Test-driven development (TDD) is a software development practice where you write failing tests **before** writing the implementation code, then write the minimum code needed to make those tests pass. The cycle repeats in short iterations: **Red** (write a failing test) → **Green** (make it pass) → **Refactor** (clean up the code).

---

## J6 · Task 4 / Branch J · Step 42

**Prompt:** List 3 benefits of writing unit tests for a solo developer project.

1. **Catch regressions fast** — When you revisit code after weeks away, tests immediately tell you if a change broke something, without needing to manually re-verify everything.

2. **Fearless refactoring** — You can restructure or optimize code with confidence, knowing the test suite will flag any behavioral changes you didn't intend.

3. **Living documentation** — Tests describe exactly how your code is supposed to behave, serving as always-up-to-date examples that are more reliable than comments or README notes.

---

## J8 · Task 4 / Branch J · Step 44

**Prompt:** Describe the difference between unit tests and integration tests in one sentence each.

**Unit tests** verify a single function or component in isolation, mocking all external dependencies.

**Integration tests** verify that multiple components or systems work correctly together with real (or minimally mocked) dependencies.

---

## J7 · Task 4 / Branch J · Step 44

**Prompt:** What is a linter and why should solo developers use one? One paragraph.

A **linter** is a static analysis tool that scans your source code for potential errors, style violations, and suspicious patterns without actually running the code — catching things like undefined variables, unreachable code, inconsistent formatting, or common logic mistakes before they cause runtime bugs. For solo developers, linters are especially valuable because there's no teammate to catch mistakes in code review; the linter acts as that second pair of eyes, enforcing consistency and flagging problems the moment you write them. The feedback loop is immediate and cheap, saving hours of debugging sessions that would otherwise be spent hunting down issues that a tool like ESLint or Ruff would have caught in milliseconds.

---

## K1 · Task 4 / Branch K · Step 46

**Prompt:** What is semantic versioning (semver)? Give one example of a version bump and why.

Semantic versioning (semver) is a versioning scheme with the format **MAJOR.MINOR.PATCH**.

Each number has a specific meaning:

- **MAJOR** — breaking change (incompatible API change)
- **MINOR** — new feature, backwards-compatible
- **PATCH** — bug fix, backwards-compatible

**Example:**

A library is at `2.3.1`. You fix a null pointer bug with no API changes → bump to `2.3.2`.

The rule: *increment the relevant segment, reset all lower segments to zero.* So a new feature would go `2.3.1` → `2.4.0`, and a breaking change would go `2.3.1` → `3.0.0`.

---

## K2 · Task 4 / Branch K · Step 46

**Prompt:** List 3 best practices for writing clear git commit messages.

1. **Use the imperative mood in the subject line** — Write "Add login validation" not "Added login validation" or "Adding login validation". This matches git's own generated messages (e.g., "Merge branch...").

2. **Keep the subject line under 50 characters** — Forces you to be concise and specific. If you can't summarize the change in 50 chars, the commit is probably doing too much.

3. **Explain *why*, not *what*, in the body** — The diff already shows *what* changed. Use the body (separated by a blank line) to explain the motivation, context, or trade-offs that aren't obvious from the code.

---

## K4 · Task 4 / Branch K · Step 48

**Prompt:** Describe the concept of self-code-review for a solo developer. 2 sentences.

Self-code-review is the practice of a solo developer critically examining their own code after a short time away from it, treating it as if written by someone else to catch bugs, logic errors, and design issues. It simulates the benefits of peer review by forcing a deliberate context switch — reading for correctness and clarity rather than just writing to make it work.

---

## K3 · Task 4 / Branch K · Step 48

**Prompt:** What is a pull request and how does it help with code quality? One paragraph.

A pull request (PR) is a mechanism in version control platforms like GitHub or GitLab where a developer proposes merging changes from one branch into another, typically from a feature branch into `main`. It creates a structured review opportunity where teammates can inspect the diff, leave inline comments, request changes, and run automated checks (CI/CD tests, linters, static analysis) before any code reaches the shared codebase. This process enforces a quality gate: bugs and design issues get caught by reviewers who have fresh eyes, coding standards are enforced consistently, knowledge is shared across the team as everyone sees what changed and why, and the commit history stays clean with meaningful, reviewed changesets rather than unreviewed work-in-progress commits landing directly on the main branch.

---

## K5 · Task 4 / Branch K · Step 50

**Prompt:** What is continuous deployment and how does it benefit a solo developer project? 2 sentences.

**Continuous deployment (CD)** is the practice of automatically deploying every code change that passes automated tests directly to production, without manual intervention.

For a solo developer, it eliminates deployment toil and reduces context-switching — you commit code, tests run, and the app updates itself, letting you stay focused on building rather than ops.

---

## L1 · Task 5 / Branch L · Step 50

**Prompt:** What are 3 key metrics a solo developer should track for a CLI tool project?

Three key metrics for a solo developer building a CLI tool:

1. **Command success rate** — percentage of invocations that exit 0. Catches regressions fast and surfaces the most-broken commands without needing user reports.

2. **Time-to-first-output** — how long from invocation until the user sees *something*. CLI tools live or die on perceived speed; even a spinner within 100ms matters.

3. **Error message frequency by type** — which specific errors are thrown most often. Tells you where users are hitting walls (bad inputs, missing config, auth failures) so you prioritize docs or UX fixes where they'll actually help.

---

## L2 · Task 5 / Branch L · Step 52

**Prompt:** Describe the concept of a project roadmap in 2 sentences.

A project roadmap is a high-level visual or strategic plan that outlines the goals, milestones, and timeline for a project's development. It communicates the direction and priorities to stakeholders, helping teams align on what needs to be built, in what order, and by when.

---

## L3 · Task 5 / Branch L · Step 52

**Prompt:** List 3 ways to gather user feedback on a solo developer CLI tool.

1. **GitHub Issues** — Add a feedback link in your CLI's help output or README pointing to a GitHub Issues template. Low friction for technical users who are already on GitHub.

2. **In-tool prompt** — After N uses or on exit, print a one-line prompt: `Found a bug or have feedback? → https://your-link`. Opt-in, non-blocking.

3. **Anonymous telemetry with opt-out** — Log usage events (commands run, errors hit) to a service like PostHog or a simple webhook. Be transparent in docs and honor `--no-telemetry`.

---

## L5 · Task 5 / Branch L · Step 54

**Prompt:** Describe 2 ways AI can help a solo developer with project documentation.

## AI for Solo Developer Documentation

**1. Auto-generating docs from code**
AI can read your source files and produce README sections, API references, inline comments, or changelogs — saving you from writing boilerplate documentation manually. You describe what the code does once, and AI formats it consistently across the project.

**2. Keeping docs in sync with changes**
When you refactor a function or add a new endpoint, AI can diff your changes and flag or update outdated documentation, so your docs don't quietly fall behind the code over time.

---

## L4 · Task 5 / Branch L · Step 54

**Prompt:** What is feature prioritization and why is it important for solo developers? One paragraph.

Feature prioritization is the process of deciding which features, improvements, or bug fixes to work on first based on factors like user impact, business value, effort required, and strategic goals. For solo developers, it's especially critical because you have a single finite resource — your own time — with no team to parallelize work across. Without deliberate prioritization, it's easy to spend weeks building features that turn out to be low-impact while critical user needs go unmet, or to chase interesting technical problems instead of the work that actually moves the needle. Good prioritization frameworks (like MoSCoW, RICE scoring, or simple impact/effort matrices) help you cut through the noise, avoid building for hypothetical users, and ship a product that solves real problems — which is ultimately the only thing that matters for getting traction as a solo builder.

---

## L6 · Task 5 / Branch L · Step 56

**Prompt:** What is a changelog and why should every project have one? One sentence.

A changelog is a curated, human-readable file that documents notable changes made to a project over time, so users and contributors can quickly understand what changed between versions without reading raw commit history.

---

## M1 · Task 5 / Branch M · Step 56

**Prompt:** List 3 strategies for getting early users for a solo developer tool.

1. **Post in niche communities where the problem lives** — Reddit (r/webdev, r/programming, r/SideProject), Hacker News "Show HN", and Discord servers. Lead with the problem you solved, not the product. Engage in comments before dropping a link.

2. **Write SEO-targeted content around the pain point** — A single well-ranked article or Stack Overflow answer that describes the exact problem your tool solves will drive warm traffic indefinitely. Costs nothing but time and compounds over months.

3. **Direct outreach to people already complaining publicly** — Search Twitter/X, GitHub Issues, or Reddit for people expressing the exact frustration your tool addresses. Reply with a genuine offer to try it free. Converts well because the pain is already confirmed.

---

## M2 · Task 5 / Branch M · Step 58

**Prompt:** What is developer experience (DX) and why does it matter? One paragraph.

Developer experience (DX) refers to the overall quality of the experience developers have when building with, on top of, or alongside a product, platform, API, or codebase — encompassing everything from documentation clarity and tooling ergonomics to feedback loop speed, error message quality, and cognitive load. It matters because friction in the development process compounds: slow builds, confusing APIs, poor docs, and unclear errors all tax developer attention and morale, leading to slower iteration, more bugs, and higher churn on teams and third-party adopters. When DX is good, developers stay in flow, ship faster, make fewer mistakes, and genuinely enjoy their work — which translates directly to better products and stronger retention of both internal engineers and external ecosystem contributors.

---

## M3 · Task 5 / Branch M · Step 58

**Prompt:** Describe 2 ways to measure whether a solo developer project is succeeding.

## Two Ways to Measure Solo Developer Project Success

**1. User/Revenue Traction**
Track whether real people are paying for or actively using what you built. Concrete signals: monthly recurring revenue (MRR), active user count, retention rate (do users come back?), or even just the number of people who paid once. The key is that external validation — someone outside your own head found it worth their time or money — is the clearest signal a project is succeeding vs. just existing.

**2. Shipping Velocity vs. Roadmap Progress**
Measure how consistently you're moving from idea to shipped feature. A simple metric: count features/fixes shipped per week or month, compared to your backlog. If velocity is steady or growing and the backlog is shrinking toward your v1 definition, the project is on track. If the backlog grows faster than you ship, or weeks pass with nothing deployed, that's a failure signal regardless of code quality.

The first measures *external* success (does it matter to anyone?), the second measures *internal* execution (are you actually building it?). Both matter — projects can fail by having users but never finishing, or by being "done" but unused.

---

## N1 · Task 5 / Branch N · Step 60

**Prompt:** What are 3 signs that a software project is ready for its first public release?

1. **Core functionality is stable and tested** — The primary use cases work reliably, critical bugs are fixed, and there's at least basic test coverage. Edge cases can be addressed post-launch, but the main path shouldn't be broken.

2. **Documentation covers getting started** — A new user can install, configure, and run the project without asking questions. A README with prerequisites, installation steps, and a basic usage example is the minimum bar.

3. **You have a feedback and issue channel** — There's a way for users to report bugs or ask questions (GitHub Issues, a Discord, an email). Releasing without this means problems disappear into the void and you lose early adopter goodwill.

---

## M4 · Task 5 / Branch M · Step 60

**Prompt:** What is open source and what are 2 benefits of open-sourcing a solo developer project?

## What is Open Source?

Open source refers to software whose **source code is publicly available** for anyone to view, use, modify, and distribute. It's governed by a license (e.g., MIT, Apache, GPL) that defines what others can do with it.

---

## 2 Benefits for Solo Developers

**1. Community bug reports and contributions**
Others can find bugs you'd never catch alone, and occasionally submit fixes or features. Even if no one contributes code, having users file issues is valuable QA you'd otherwise have to pay for.

**2. Credibility and visibility**
A public GitHub repo with real code is a stronger portfolio signal than a description on a resume. It demonstrates how you actually write and structure code, which matters when attracting clients, employers, or collaborators.

---

## N2 · Task 5 / Branch N · Step 62

**Prompt:** Describe the concept of a 'soft launch' for a developer tool. 2 sentences.

A soft launch is a limited, low-key release of a tool to a small audience (beta users, waitlist members, or a specific community) before a full public launch, allowing you to gather real-world feedback and fix issues without the pressure of broad visibility. It's distinct from a hard launch in that there's minimal marketing push — the goal is validation and iteration, not maximum reach.

---

## N3 · Task 5 / Branch N · Step 62

**Prompt:** List 3 things a developer should document before releasing an open-source project.

Here are 3 things a developer should document before releasing an open-source project:

1. **README** — Purpose, features, installation steps, and a quick-start example so users can get running immediately.

2. **Contributing guidelines** (`CONTRIBUTING.md`) — How to report issues, submit PRs, coding standards, and the review process so contributors know what's expected.

3. **License** (`LICENSE`) — The exact terms under which others can use, modify, and distribute the code. Without this, the project is legally "all rights reserved" by default.

---

## N5 · Task 5 / Branch N · Step 64

**Prompt:** Write a one-sentence mission statement for Solo Builder — an AI-powered CLI that manages DAG-based tasks for solo developers.

**Solo Builder** is an AI-powered CLI that helps solo developers ship faster by orchestrating complex, dependency-aware tasks as intelligent DAGs — so you can focus on building, not managing.

---

## N4 · Task 5 / Branch N · Step 64

**Prompt:** What is a README file and what are its 3 most important sections? One sentence each.

A README file is a text document (typically Markdown) placed at the root of a project that introduces and explains the project to anyone who encounters it.

**3 most important sections:**

1. **What it is** — A brief description of what the project does and the problem it solves.
2. **How to install/set it up** — The steps needed to get the project running on your machine.
3. **How to use it** — Basic usage examples or commands so users can get started immediately.

---

## O1 · Task 6 / Branch O · Step 66

**Prompt:** Summarize in 3 bullet points how DAG-based task management (like Solo Builder) improves over a simple to-do list for a solo developer.

- **Dependency enforcement** — Tasks are only surfaced when their prerequisites are complete, preventing wasted effort on work that's blocked or out of order.
- **Critical path visibility** — The graph reveals which tasks have the most downstream dependencies, so you instinctively prioritize work that unblocks the most future tasks.
- **Cascading updates** — Changing or delaying one task automatically propagates impact through dependents, giving an accurate picture of what's actually next rather than a stale flat list.

---

## O2 · Task 6 / Branch O · Step 66

**Prompt:** Describe how self-healing agents reduce manual intervention in a software project pipeline. One paragraph.

Self-healing agents reduce manual intervention by continuously monitoring pipeline health, detecting anomalies or failures in real time, and autonomously executing corrective actions — such as retrying failed builds, rolling back bad deployments, restarting crashed services, or scaling resources under load — without requiring a human to be paged. They encode operational runbooks as executable logic, so common failure modes (flaky tests, dependency timeouts, out-of-memory crashes) are resolved instantly through pre-defined remediation strategies rather than waking an on-call engineer at 3am. By closing the feedback loop automatically, they shift human attention from reactive firefighting to proactive improvement: engineers review post-incident summaries and tune agent thresholds instead of manually diagnosing and fixing the same recurring issues over and over.

---

## P1 · Task 6 / Branch P · Step 68

**Prompt:** What would a 'v2.0' of Solo Builder look like? List 3 major new features with one sentence each.

Based on the current Solo Builder — a Python terminal CLI with DAG-based task orchestration, multi-agent coordination (Planner, Executor, ShadowAgent, Verifier, SelfHealer, MetaOptimizer), and PDF snapshot reporting — here's what v2.0 could look like:

---

**1. Natural Language Task Ingestion**
Accept a freeform project description or spec doc and automatically decompose it into a populated DAG of tasks, branches, and dependencies without manual `add_task` commands.

**2. Real Codebase Awareness**
Integrate with the actual project directory so agents can read file state, detect completed work, and automatically advance subtask lifecycle based on observable artifacts (files, commits, test results) rather than manual status updates.

**3. Web UI / Dashboard**
Replace the terminal-only interface with a local browser dashboard that renders the DAG visually, shows agent activity in real-time, and lets you interact with tasks via click and drag rather than CLI commands.

---

## O3 · Task 6 / Branch O · Step 68

**Prompt:** Write a 3-sentence executive summary of Solo Builder for a developer audience.

Solo Builder is a Python terminal CLI that orchestrates AI agents — Planner, Executor, Verifier, SelfHealer, ShadowAgent, and MetaOptimizer — to manage a DAG-based project task graph, enabling a solo developer to run multi-branch, dependency-aware workflows from a single interactive shell. The system tracks subtask lifecycle (Pending → Running → Verified), detects stalls and DAG inconsistencies automatically, and snapshots state as versioned PDFs with a persistent `journal.md`, giving developers an auditable record of project progress. Built entirely in Python with no external orchestration framework, Solo Builder is a lightweight, self-contained alternative to heavyweight project management tools — designed for one developer operating with the leverage of a coordinated agent team.

---

## P3 · Task 6 / Branch P · Step 70

**Prompt:** Write a haiku about software agents managing project tasks autonomously.

Silent agents hum,
Tasks cascade through logic trees—
Code ships while you sleep.

---

## P2 · Task 6 / Branch P · Step 70

**Prompt:** How would you adapt Solo Builder for a team of 3-5 developers instead of a solo developer? Give 3 key changes.

Good context. Here are 3 key changes to adapt Solo Builder for a team of 3-5 developers:

---

## 1. Distributed State with Ownership & Locking

Currently, the DAG state lives in local files managed by a single process. For a team, you'd need:

- **Shared state backend** — replace the local `state/` directory with a lightweight store (SQLite with WAL mode, or a hosted option like Supabase/Redis) so all teammates read/write the same DAG
- **Task ownership** — add an `assigned_to` field per subtask so the Planner assigns work to specific developers, not just marks it pending
- **Optimistic locking** — the Executor must check a `version` field before writing to prevent two developers from mutating the same task simultaneously

---

## 2. Multi-User Identity & Audit Trail

The ShadowAgent currently detects conflicts between expected and actual states, but doesn't track *who* caused a state change. For a team:

- Add a `modified_by` + `timestamp` to every state transition
- The `journal.md` becomes a structured per-user audit log (not a single flat file)
- The SelfHealer escalates stalled tasks to the *assigned owner* via notification (Slack/email hook), not just resets them silently

---

## 3. Role-Based Agent Access (Planner vs. Executor vs. Observer)

Today all agents run under one process with full permissions. A team needs:

- **Role separation** — a team lead gets Planner + MetaOptimizer access; developers get Executor-only; stakeholders get read-only status/snapshot
- **Protected branches** — mirror git's branch protection: certain DAG branches (e.g., `release/`) require a second approval before the Verifier marks them `Verified`
- This maps directly onto the existing DAG + branch model — it's an access-control layer over what's already there, not a redesign

---

The core DAG engine, conflict detection, and self-healing logic carry over unchanged — the main structural work is externalizing state and adding identity/ownership.

---

## A2 · Task 0 / Branch A · Step 2

**Prompt:** Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.

**Solo Builder** is a Python terminal CLI that harnesses AI agents to manage your projects as a dependency-aware DAG, automatically tracking task relationships, blockers, and progress in one place. Built for solo developers who think in systems, it turns chaotic project backlogs into an intelligent, self-updating workflow — so you always know what to build next and why.

---

## A1 · Task 0 / Branch A · Step 2

**Prompt:** List 5 key features a solo developer AI project management tool needs. Bullet points.

- **Task/backlog management** — capture, prioritize, and track work items without team overhead
- **AI-assisted planning** — break down features into subtasks, estimate effort, suggest sequencing
- **Context persistence** — remember project state, decisions, and progress across sessions
- **Friction-free capture** — quick add tasks from anywhere (CLI, browser, chat) without context-switching
- **Progress visibility** — simple dashboard showing what's done, in-flight, and blocked at a glance

---

## A4 · Task 0 / Branch A · Step 4

**Prompt:** What are 3 risks of building a self-healing agent system, and one mitigation for each?

## Risks of Self-Healing Agent Systems

**1. Runaway Remediation Loops**
An agent misdiagnoses a failure, applies a "fix," makes things worse, then keeps retrying — amplifying damage instead of stopping.
- **Mitigation:** Implement a circuit breaker with a max-attempt ceiling and mandatory human-in-the-loop escalation after N failed recovery cycles.

**2. Privilege Escalation via Self-Modification**
A healing agent that can restart services, redeploy code, or modify configs effectively has broad system access — a compromised or buggy agent becomes a high-impact attack surface.
- **Mitigation:** Enforce least-privilege by scoping each agent's allowed actions to a strict allowlist, and require signed approval tokens for any action that touches infrastructure outside its declared domain.

**3. Observability Collapse**
When the agent acts autonomously, the system "self-heals" silently — leaving no audit trail. Engineers lose visibility into what failed, why, and what the agent changed, making future debugging nearly impossible.
- **Mitigation:** Treat every agent action as an append-only event (structured log + alerting), and surface a human-readable remediation summary to an ops channel on every intervention — success or failure.

---

## A3 · Task 0 / Branch A · Step 4

**Prompt:** Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.

Based on reading the actual codebase, here are 3 concrete improvements grounded in what the code does today:

---

## 1. Wire the Executor to real Claude API calls

**Current state:** `EXECUTOR_VERIFY_PROBABILITY = 0.6` — subtasks advance via random dice rolls. The `description` field on every subtask and `CLAUDE_TIMEOUT: 60` in `config/settings.json` clearly anticipate real execution, but nothing ever calls Claude.

**Fix:** When an executor picks up a `Running` subtask, pass its `description` to `claude -p "{description}"` via subprocess and store the result in the `output` field. The timeout config and subprocess import are already there — it's one `subprocess.run()` call away from being a real AI task runner.

---

## 2. Resume from saved state on startup

**Current state:** Every launch resets to `INITIAL_DAG` (hardcoded in `solo_builder_cli.py`). `STATE_PATH = ./state/solo_builder_state.json` auto-saves during a run but startup ignores it entirely.

**Fix:** At boot, check if `STATE_PATH` exists and prompt `[R]esume / [N]ew`. Load the persisted DAG + memory store if resuming. For a solo dev working across days, losing all progress on every restart is the single biggest friction point — and the infrastructure to fix it already exists.

---

## 3. Auto-populate `solo_builder_outputs.md` on snapshot

**Current state:** `solo_builder_outputs.md` exists in the project root but isn't auto-written. PDF snapshots show status charts, but the actual `output` fields on Verified subtasks stay empty and are never surfaced.

**Fix:** On `snapshot` or session end, append to `solo_builder_outputs.md` with `description → output` for every Verified subtask, grouped by task/branch. The DAG visualization shows *progress*; what a solo dev actually needs is the *deliverable* — the written content the agents produced.

---

## A5 · Task 0 / Branch A · Step 6

**Prompt:** Write a tagline for Solo Builder in under 10 words.

**Build faster. Ship smarter. Solo.**

---

## B1 · Task 0 / Branch B · Step 6

**Prompt:** Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.

A **Shadow Agent** runs in parallel with a primary agent, silently observing its actions and outputs without intervening — used for monitoring, logging, or A/B testing alternative behaviors.

A **Verifier Agent** actively validates the output or actions of another agent before they are committed or returned, acting as a gatekeeper that can block or flag results that fail defined correctness or safety criteria.

---

## B3 · Task 0 / Branch B · Step 8

**Prompt:** In one sentence, explain what a MetaOptimizer does in an AI pipeline.

A MetaOptimizer learns how to optimize the optimization process itself — it adjusts hyperparameters, learning rates, or update rules dynamically so that the underlying model trains more efficiently.

---

## B2 · Task 0 / Branch B · Step 8

**Prompt:** List 3 real-world use cases for a DAG-based AI project tracker.

## DAG-Based AI Project Tracker — 3 Real-World Use Cases

**1. Software Release Pipeline**
Track tasks like "write tests → merge PR → build Docker image → deploy to staging → run E2E tests → deploy to prod" where each node depends on upstream completion. The DAG enforces ordering, surfaces the critical path, and blocks deployment if a dependency fails.

**2. Research Paper Workflow**
A research team's tasks (data collection → preprocessing → model training → evaluation → write results → peer review → revisions → submission) have strict dependencies. The tracker shows which tasks are blocked, which can run in parallel (e.g., two independent experiments), and where the bottleneck is.

**3. Client Onboarding in a SaaS Product**
Onboarding has branching, conditional steps: "sign contract → provision account → [configure SSO *and* import data *and* train team] → go-live." The DAG model handles parallel tracks (SSO + data import can run simultaneously), conditional branches (SSO only if enterprise tier), and surfaces blockers to account managers in real time.

---

**Why DAG specifically?**
- Encodes real dependency chains, not just flat checklists
- Enables parallel execution of independent tasks
- Makes the critical path explicit
- Prevents circular dependency bugs in task planning

---

## C2 · Task 1 / Branch C · Step 10

**Prompt:** List 3 advantages of using a priority queue to schedule software tasks.

1. **Efficient task ordering** — Higher-priority tasks are always processed first, ensuring critical work isn't delayed by lower-priority items regardless of arrival order.

2. **O(log n) insertions and extractions** — A heap-based priority queue handles scheduling operations in logarithmic time, which scales well even with large task queues.

3. **Dynamic reprioritization** — Task priorities can be adjusted at runtime (e.g., deadline-driven scheduling, aging to prevent starvation), giving schedulers fine-grained control without resorting the entire queue.

---

## C1 · Task 1 / Branch C · Step 10

**Prompt:** What does a DAG (Directed Acyclic Graph) represent in software project management? Answer in one paragraph.

A DAG (Directed Acyclic Graph) in software project management represents the dependency relationships between tasks, where each node is a task and each directed edge means "this task must complete before that one can start." The "acyclic" constraint ensures there are no circular dependencies (Task A → B → C → A), which would make the project unschedulable. DAGs are the foundation of build systems (Make, Bazel, Gradle), CI/CD pipelines, workflow orchestrators (Airflow, Prefect), and package managers — they allow tools to determine a valid execution order via topological sort, identify which tasks can run in parallel (tasks with no shared dependencies), and pinpoint the critical path that determines the minimum project duration.

---

## C3 · Task 1 / Branch C · Step 12

**Prompt:** Explain the concept of task staleness in a project management system in 2 sentences.

Task staleness refers to the condition where a task has not been updated, progressed, or acted upon within an expected timeframe, making its current status uncertain or outdated. It signals that a task may be blocked, forgotten, or deprioritized, and typically triggers alerts or reviews to prompt action and keep the project moving forward.

---

## C4 · Task 1 / Branch C · Step 12

**Prompt:** What is a shadow state in an agent-based system? Give one concrete example.

## Shadow State in Agent-Based Systems

**Shadow state** is a local copy of external state that an agent maintains independently — often without a reliable mechanism to verify it matches the actual source of truth.

The agent acts on its shadow copy rather than querying the real system, which can lead to decisions based on stale or incorrect data.

---

### Concrete Example

**Inventory management agent:**

1. At startup, the agent fetches product stock levels and caches them locally: `{ "widget-A": 50 }`
2. A separate system (a warehouse app) sells 48 widgets, updating the real DB to `{ "widget-A": 2 }`
3. The agent never re-fetches. Its shadow state still shows `50`.
4. A customer requests 40 widgets — the agent approves the order because `40 < 50`.
5. Fulfillment fails: only 2 units actually exist.

---

### Why It Matters for Agents

Agents compound this problem compared to traditional software because:

- **Long-running sessions** — agents may hold shadow state across many tool calls or hours
- **Multi-agent systems** — two agents can have divergent shadows of the same resource, causing conflicts
- **Tool call latency** — agents are tempted to cache to avoid expensive re-reads, widening the drift window

The fix is usually **explicit invalidation** (event-driven cache busting), **TTL-based expiry**, or **optimistic locking** (read-then-compare before writes).

---

## D2 · Task 1 / Branch D · Step 14

**Prompt:** What is the difference between optimistic and pessimistic task verification? One paragraph.

**Optimistic task verification** assumes a task succeeded unless evidence indicates otherwise — it proceeds immediately after an action and only checks for failure signals, making it faster but potentially missing silent failures. **Pessimistic task verification** explicitly confirms success before moving on — it waits for a positive confirmation signal (e.g., a status check, assertion, or return value) before proceeding, making it slower but more reliable. In practice, optimistic verification suits low-stakes, idempotent operations where retrying is cheap, while pessimistic verification is preferred for destructive, irreversible, or critical operations where silent failure has serious consequences.

---

## D1 · Task 1 / Branch D · Step 14

**Prompt:** Describe 2 strategies for preventing task starvation in a priority-based scheduler.

## Preventing Task Starvation in Priority-Based Schedulers

### 1. Aging

Gradually increase the priority of waiting tasks over time. The longer a task sits in the queue without being scheduled, the higher its effective priority becomes.

- A low-priority task that waits long enough eventually reaches the same priority as high-priority tasks
- Prevents indefinite blocking by guaranteeing eventual promotion
- Example: increment priority by 1 every N milliseconds of wait time

```
effective_priority = base_priority + (wait_time / aging_interval)
```

### 2. Priority Inheritance / Ceiling

When a high-priority task is blocked waiting on a resource held by a low-priority task, the low-priority task **inherits** the higher priority temporarily until it releases the resource.

- Directly addresses **priority inversion** (the root cause of starvation in many real systems)
- Used in POSIX mutexes (`PTHREAD_PRIO_INHERIT`), RTOS kernels (FreeRTOS, VxWorks)
- The inherited priority is dropped as soon as the blocking resource is released

```
if (high_task.waiting_on == low_task.held_resource):
    low_task.effective_priority = high_task.priority  # temporary boost
```

---

**Key distinction**: Aging is a general-purpose starvation fix that works over time; priority inheritance is a targeted fix for resource-contention scenarios specifically.

---

## E2 · Task 2 / Branch E · Step 16

**Prompt:** Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.

A MetaOptimizer observes an agent's performance across tasks and iteratively adjusts its hyperparameters, prompting strategies, or model selection to maximize long-term reward signals. By learning which configurations produce the best outcomes in which contexts, it shifts the agent from static behavior to self-improving adaptation without requiring manual tuning.

---

## E1 · Task 2 / Branch E · Step 16

**Prompt:** What are 3 benefits of self-healing automation in a software pipeline?

1. **Reduced mean time to recovery (MTTR)** — Failures are detected and remediated automatically (e.g., restarting crashed services, rolling back bad deploys) without waiting for human intervention, keeping pipelines running around the clock.

2. **Lower operational toil** — Engineers spend less time on repetitive incident response (flaky tests, transient network errors, resource exhaustion) and more time on feature work. The system handles known failure modes on its own.

3. **Increased reliability and confidence** — Consistent automated recovery behavior is more predictable than ad-hoc human responses. Teams can deploy more frequently knowing the pipeline will self-correct minor issues, which reinforces a healthier CI/CD culture.

---

## E4 · Task 2 / Branch E · Step 18

**Prompt:** What is the difference between reactive and proactive error handling in agent systems? One sentence each.

**Reactive**: The agent detects and responds to errors *after* they occur (e.g., catching exceptions, retrying failed tool calls).

**Proactive**: The agent anticipates and prevents errors *before* they occur (e.g., validating inputs, checking preconditions, planning for known failure modes).

---

## E3 · Task 2 / Branch E · Step 18

**Prompt:** List 3 metrics that indicate an AI agent system is performing well.

Here are 3 key metrics for evaluating AI agent system performance:

1. **Task Completion Rate** — The percentage of assigned tasks successfully completed without human intervention or escalation. High completion rates (>90%) indicate the agent handles its intended scope reliably.

2. **Latency / Time-to-Result** — The time from task submission to a usable output. Low and consistent latency means the agent is efficient and predictable, especially important in multi-step agentic pipelines where delays compound.

3. **Error / Hallucination Rate** — The frequency of factually incorrect outputs, failed tool calls, or logic errors. Tracked via automated validation, human review sampling, or unit tests against known-answer benchmarks. Lower is better; anything above ~5% typically signals a reliability problem.

---

## F1 · Task 2 / Branch F · Step 20

**Prompt:** What is the role of a Verifier agent in a multi-agent pipeline? 2 sentences.

A Verifier agent checks the output of other agents to ensure correctness, consistency, and adherence to requirements before passing results downstream. It acts as a quality gate, catching errors, hallucinations, or constraint violations that earlier agents may have introduced.

---

## E5 · Task 2 / Branch E · Step 20

**Prompt:** Give one example of a heuristic weight that a MetaOptimizer might adjust in a task planner.

A MetaOptimizer might adjust the **urgency decay rate** — the rate at which a task's priority score decreases as its deadline approaches more slowly (or spikes as it approaches fast).

For example:

```
priority = base_importance * urgency_weight(time_remaining)
```

Where `urgency_weight` uses a parameter `k` (the decay/growth steepness):

```
urgency_weight = 1 / (1 + e^(-k * (deadline - now)))
```

The MetaOptimizer observes that tasks with aggressive `k` values cause the planner to thrash — constantly re-ordering work as deadlines shift — and nudges `k` downward to stabilize scheduling. Conversely, if tasks are frequently missed, it increases `k` to front-load urgent work earlier.

---

## F3 · Task 2 / Branch F · Step 22

**Prompt:** List 2 ways a ShadowAgent could detect state inconsistencies in a DAG pipeline.

**Two ways a ShadowAgent could detect state inconsistencies in a DAG pipeline:**

---

**1. Checksum/Hash Comparison at Node Boundaries**

The ShadowAgent runs in parallel with the primary pipeline, independently computing a hash of each node's output state. After each node executes, it compares its computed hash against the primary agent's recorded hash. A mismatch signals that the node produced different outputs from the same inputs — indicating non-determinism, a race condition, or corrupted state propagating downstream.

---

**2. Topological Invariant Monitoring**

The ShadowAgent tracks the expected dependency ordering (e.g., node B must always receive finalized output from node A before executing). It monitors timestamps, version counters, or sequence numbers on state objects flowing through edges. If it observes a downstream node consuming a state version that is older than the last committed upstream version, it flags a stale-read inconsistency — common in concurrent DAG execution where edge synchronization is broken.

---

## F2 · Task 2 / Branch F · Step 22

**Prompt:** Describe how memory snapshots help with debugging in an agent system. One paragraph.

Memory snapshots capture the full state of an agent's working memory at a specific point in time, giving you a frozen record of what the agent knew, believed, and was tracking when a problem occurred. Rather than trying to reconstruct what went wrong from logs alone, a snapshot lets you inspect the exact context the agent was operating under — which tasks were in-progress, what tool results had been received, what decisions were pending — making it straightforward to identify whether a bug stems from bad input, a flawed reasoning step, a corrupted state update, or a tool returning unexpected data. They're especially valuable in multi-step or multi-agent workflows where state evolves across many turns, since you can compare snapshots before and after a failure to pinpoint the exact transition where things diverged from expected behavior.

---

## F4 · Task 2 / Branch F · Step 24

**Prompt:** What is the difference between a branch and a task in a DAG-based project tracker? One sentence.

A **branch** is a parallel path of work diverging from a common ancestor, while a **task** is a single unit of work (node) within the DAG that may have dependencies on other tasks.

---

## G1 · Task 3 / Branch G · Step 24

**Prompt:** What is continuous integration and how does it relate to automated project management? One paragraph.

Continuous integration (CI) is a software development practice where developers frequently merge code changes into a shared repository — often multiple times per day — with each merge automatically triggering a pipeline that builds the project, runs tests, and reports results. It relates to automated project management in that CI systems (like GitHub Actions, Jenkins, or CircleCI) serve as the enforcement layer for quality gates: they can automatically block merges that break tests, generate reports on code coverage, trigger deployments to staging environments, create or close issue tickets based on build status, and notify teams via Slack or email. This closes the feedback loop between writing code and knowing whether it works, removing the manual coordination overhead that would otherwise require a human to track build health, deployment readiness, and test results — making CI a foundational piece of any automated project management workflow.

---

## G3 · Task 3 / Branch G · Step 26

**Prompt:** Describe the MVP (Minimum Viable Product) concept in 2 sentences.

An MVP is the simplest version of a product that delivers core value to early users while requiring minimal development effort. It exists to validate key assumptions and gather real-world feedback before investing in full-scale development.

---

## G2 · Task 3 / Branch G · Step 26

**Prompt:** List 3 common causes of technical debt in solo developer projects.

1. **Skipping tests** — Solo devs often skip writing tests under time pressure, making future refactoring risky and changes slow.

2. **Premature or inconsistent abstractions** — Building overly complex systems for hypothetical future needs, or inconsistently applying patterns across the codebase as the project evolves.

3. **Deferred dependency updates** — Letting libraries and frameworks fall behind, then facing breaking changes that compound over time instead of incremental updates.

---

## G4 · Task 3 / Branch G · Step 28

**Prompt:** What is a sprint in agile methodology? One sentence.

A sprint is a fixed-length iteration (typically 1–4 weeks) in which a team completes a defined set of work from the product backlog.

---

## G5 · Task 3 / Branch G · Step 28

**Prompt:** List 3 developer tools a solo builder could use alongside an AI task manager.

Here are 3 developer tools that pair well with an AI task manager for a solo builder:

1. **Linear** — Lightweight issue tracker with keyboard-driven UX. Clean API makes it easy to sync tasks from an AI agent automatically.

2. **Cursor / VS Code** — AI-native code editor where tasks can map directly to files and diffs. Keeps context tight between planning and implementation.

3. **Doppler / Infisical** — Secrets manager to handle env vars across environments. Lets an AI agent reference config names without ever touching raw credentials.

---

## H1 · Task 3 / Branch H · Step 30

**Prompt:** Describe the concept of a 'Definition of Done' in software projects. 2 sentences.

A **Definition of Done (DoD)** is a shared, agreed-upon checklist of criteria that a work item (feature, story, task) must meet before it can be considered complete — covering things like code reviewed, tests passing, documentation updated, and deployed to a target environment.

It exists to create a common standard across a team, preventing ambiguity about what "done" actually means and ensuring consistent quality across deliverables.

---

## G6 · Task 3 / Branch G · Step 30

**Prompt:** What is the difference between async and sync task execution in pipelines? One paragraph.

In a pipeline, **synchronous (sync) execution** means each task runs sequentially — a task must fully complete before the next one starts, blocking the thread until it's done, which is simple to reason about but wastes time when tasks involve I/O (network requests, file reads, DB queries) since the CPU sits idle waiting. **Asynchronous (async) execution** allows tasks to be initiated and then suspended at I/O boundaries (using `await` / promises / callbacks), freeing the thread to start or continue other tasks while waiting — meaning multiple tasks can be "in flight" concurrently on a single thread, dramatically improving throughput in I/O-bound pipelines without the complexity and overhead of true multi-threading. The key tradeoff is that async pipelines are more efficient but harder to reason about (error propagation, ordering, backpressure), while sync pipelines are easier to debug and sufficient when tasks are CPU-bound or latency doesn't matter.

---

## H3 · Task 3 / Branch H · Step 32

**Prompt:** What is the Pomodoro technique and how might it help a solo developer? One paragraph.

The Pomodoro technique is a time management method where you work in focused 25-minute intervals (called "pomodoros") separated by short 5-minute breaks, with a longer 15-30 minute break after every four cycles. For a solo developer, it's particularly valuable because there's no external structure or team rhythm to keep you on track — the technique replaces that with a self-imposed cadence. It combats the two failure modes common to solo work: hyperfocus (losing hours to a rabbit hole without stepping back) and procrastination (avoiding a hard task indefinitely). The forced breaks create natural checkpoints to reassess whether you're solving the right problem, context-switch between tasks, or simply rest your eyes and mind, which tends to improve overall output quality and reduce burnout over long coding sessions.

---

## H2 · Task 3 / Branch H · Step 32

**Prompt:** List 3 ways to reduce context-switching costs for a solo developer.

1. **Time-block by task type** — Group similar work (e.g., all code reviews in the morning, deep feature work in focused afternoon blocks). Switching between coding, emails, and planning is more expensive than batching each category together.

2. **Leave breadcrumbs before stopping** — Before ending a session, write a 2-3 line note: what you were doing, what the next step is, and any open questions. A `NOTES.md` or a comment like `// TODO: next — fix auth edge case (see issue #42)` cuts re-orientation time significantly.

3. **Keep a single task list in one place** — Avoid mental overhead of remembering what's in Notion vs. a sticky note vs. your head. One canonical list (even a plain text file) means zero friction deciding what to work on next.

---

## I1 · Task 3 / Branch I · Step 34

**Prompt:** What is scope creep and how can a solo developer prevent it? One paragraph.

Scope creep is the gradual, unplanned expansion of a project's requirements beyond its original goals — often driven by "just one more feature" thinking, vague initial specs, or reacting to every new idea without evaluating its cost. For a solo developer, it's especially dangerous because there's no team to push back or catch drift. To prevent it, define a tight, written spec before writing any code and treat it as a contract with yourself; maintain a backlog for new ideas instead of acting on them immediately; set explicit "done" criteria for each feature so you know when to stop; and timebox work into fixed iterations (e.g., one-week sprints) where scope is frozen once the sprint starts. When a new idea surfaces mid-build, ask "does this ship the current version?" — if no, it goes on the backlog.

---

## H4 · Task 3 / Branch H · Step 34

**Prompt:** Give 2 examples of how AI can assist with project estimation for a solo developer.

**1. Breaking down scope into task estimates**

A solo dev can describe a feature or project in natural language, and AI can decompose it into concrete subtasks with rough time estimates based on common patterns. For example:

> "Build a user authentication system with email/password and OAuth"

AI might return:
- DB schema + migrations: 1–2h
- Backend auth endpoints: 3–4h
- JWT/session handling: 2h
- OAuth provider integration: 2–3h
- Frontend forms + validation: 3h
- **Total: ~12–14h**

This prevents the classic mistake of estimating only the "happy path" and forgetting integration, error handling, and testing.

---

**2. Identifying hidden complexity and risks**

When given a project brief, AI can flag non-obvious effort sinks that solo devs commonly underestimate:

> "Add real-time notifications to my app"

AI might surface:
- WebSocket connection management adds ~20% overhead vs. polling
- You'll need a job queue (Redis/BullMQ) if notifications are event-driven
- Mobile push vs. in-app are separate implementation paths
- Testing real-time flows is significantly harder than REST endpoints

This shifts estimates from optimistic to realistic before a line of code is written — something a solo dev without a team to reality-check them particularly benefits from.

---

## I3 · Task 3 / Branch I · Step 36

**Prompt:** Describe the concept of 'bikeshedding' and why it's a risk for solo developers. 2 sentences.

**Bikeshedding** is the tendency to spend disproportionate time on trivial, easy-to-discuss decisions (like what color to paint a bike shed) while neglecting complex, critical ones. For solo developers, it's especially dangerous because there's no team to redirect focus — you can burn hours debating folder structure or variable naming while core features go unbuilt.

---

## I2 · Task 3 / Branch I · Step 36

**Prompt:** List 3 warning signs that a solo software project is at risk of failure.

1. **Scope creep without a forcing function** — Features keep expanding but there's no deadline, paying user, or shipped MVP to constrain them. Building indefinitely without validation is a slow death.

2. **No one else knows the project exists** — Zero external feedback (users, testers, even a single friend) means you're optimizing in a vacuum. Isolation kills motivation and hides fundamental flaws in the idea.

3. **Avoiding the hard part** — Polishing the UI while the core business logic is unproven, or perfecting tooling instead of writing the actual product. This is procrastination disguised as productivity.

---

## J2 · Task 4 / Branch J · Step 38

**Prompt:** Describe the DRY (Don't Repeat Yourself) principle in one sentence with a concrete example.

DRY means every piece of knowledge should have a single authoritative source — for example, instead of hardcoding a tax rate of `0.13` in five different functions, define `const TAX_RATE = 0.13` once and reference it everywhere.

---

## J1 · Task 4 / Branch J · Step 38

**Prompt:** What are 3 principles of clean code that every solo developer should follow?

1. **Name things clearly** — Variables, functions, and files should say what they do without needing a comment to explain them. `getUserById()` beats `getData()` every time.

2. **Keep functions small and single-purpose** — Each function should do one thing. If you need to scroll to read it, it probably does too much. Small functions are easier to test, debug, and reuse.

3. **Delete dead code** — Don't comment out old logic "just in case." That's what git is for. Dead code creates noise and false confidence that something is still in use.

---

## J4 · Task 4 / Branch J · Step 40

**Prompt:** Pick 3 of the SOLID principles and explain each in one bullet point.

- **S — Single Responsibility**: A class should have only one reason to change — each class owns exactly one concern, so a `UserService` handles user logic but never also writes to a log file.
- **O — Open/Closed**: Code should be open for extension but closed for modification — add behavior by writing new classes/functions rather than editing existing ones, reducing regression risk.
- **D — Dependency Inversion**: High-level modules should depend on abstractions, not concrete implementations — a `PaymentProcessor` accepts an `IPaymentGateway` interface so you can swap Stripe for PayPal without touching business logic.

---

## J3 · Task 4 / Branch J · Step 40

**Prompt:** What is a code smell? Give 3 examples.

A **code smell** is a surface-level indicator in source code that suggests a deeper problem — not a bug itself, but a sign that the design may be flawed, hard to maintain, or likely to cause bugs later.

---

**1. Long Method**
A function that does too many things. It's hard to read, test, or reuse.
```python
def process_order(order):
    # 200 lines of validation, pricing, inventory, email, logging...
```
Fix: Extract cohesive chunks into smaller, named functions.

---

**2. Duplicate Code**
The same logic copy-pasted in multiple places. When the logic changes, you have to update every copy — and you will miss one.
```js
// In checkout.js
const tax = price * 0.07;

// In invoice.js
const tax = amount * 0.07;
```
Fix: Extract into a shared `calculateTax()` function.

---

**3. Magic Numbers / Strings**
Unexplained literals scattered through code. The reader has no idea what `86400` or `"USR_42"` means.
```python
if session_age > 86400:
    expire_session()
```
Fix: Replace with a named constant:
```python
SECONDS_PER_DAY = 86400
if session_age > SECONDS_PER_DAY:
```

---

The term was popularized by Martin Fowler in *Refactoring* (1999), which catalogs ~20 common smells and their corresponding refactoring techniques.

---

## J5 · Task 4 / Branch J · Step 42

**Prompt:** What is test-driven development (TDD)? Describe it in 2 sentences.

Test-driven development (TDD) is a software development practice where you write failing tests *before* writing the implementation code, then write just enough code to make those tests pass. The cycle repeats in short iterations: **Red** (write a failing test) → **Green** (make it pass) → **Refactor** (clean up the code).

---

## J6 · Task 4 / Branch J · Step 42

**Prompt:** List 3 benefits of writing unit tests for a solo developer project.

1. **Catch regressions instantly** — When you revisit code weeks later and make changes, tests alert you immediately if something breaks, without needing to manually retest everything.

2. **Document expected behavior** — Tests serve as living documentation that shows exactly how functions are supposed to work, which is invaluable when your own memory of the code fades.

3. **Refactor with confidence** — You can restructure or optimize code freely, knowing the test suite will validate the behavior hasn't changed.

---

## J8 · Task 4 / Branch J · Step 44

**Prompt:** Describe the difference between unit tests and integration tests in one sentence each.

**Unit tests** verify that a single, isolated piece of code (function, class, or module) behaves correctly in isolation, with dependencies mocked or stubbed out.

**Integration tests** verify that multiple components or systems work correctly together, testing real interactions between them (e.g., database queries, API calls, service boundaries).

---

## J7 · Task 4 / Branch J · Step 44

**Prompt:** What is a linter and why should solo developers use one? One paragraph.

A **linter** is a static analysis tool that automatically scans your code for potential errors, style inconsistencies, and problematic patterns without actually running the code — think of it as a spell-checker for your codebase. Solo developers benefit especially from linters because there's no teammate to catch mistakes in code review: a linter acts as that second pair of eyes, flagging things like unused variables, unreachable code, type mismatches, and style drift before they become bugs or technical debt. Tools like ESLint (JavaScript), Pylint/Ruff (Python), or Biome enforce consistent conventions automatically, which matters more over time as a project grows and context fades — you'll thank past-you for the guardrails when you return to code written six months ago.

---

## K1 · Task 4 / Branch K · Step 46

**Prompt:** What is semantic versioning (semver)? Give one example of a version bump and why.

Semantic versioning (semver) is a versioning scheme with the format **MAJOR.MINOR.PATCH**:

- **MAJOR** — breaking changes (incompatible API changes)
- **MINOR** — new features, backwards-compatible
- **PATCH** — bug fixes, backwards-compatible

**Example:**

`1.4.2` → `1.5.0`

A new optional config parameter was added to a function. Existing callers still work unchanged, so it's a **minor bump** — new functionality, no breaking changes. PATCH resets to 0.

---

## K2 · Task 4 / Branch K · Step 46

**Prompt:** List 3 best practices for writing clear git commit messages.

1. **Use the imperative mood in the subject line** — Write "Add login validation" not "Added login validation" or "Adds login validation". This matches how git itself phrases things (e.g., "Merge branch...").

2. **Keep the subject line short and focused** — Aim for 50 characters or fewer. The subject should complete the sentence: "If applied, this commit will..." — e.g., "Fix null pointer in auth middleware".

3. **Explain the *why*, not the *what*, in the body** — The diff already shows what changed. Use the commit body (separated by a blank line) to explain the motivation, context, or trade-offs. This is invaluable for future debugging.

---

## K4 · Task 4 / Branch K · Step 48

**Prompt:** Describe the concept of self-code-review for a solo developer. 2 sentences.

Self-code-review is the practice of a solo developer deliberately stepping back from code they've written and reviewing it with a critical, outsider perspective — checking for bugs, clarity, and maintainability before merging or shipping. It compensates for the lack of a team reviewer by using techniques like time delays, checklists, or reading code aloud to catch issues that familiarity blinds you to.

---

## K3 · Task 4 / Branch K · Step 48

**Prompt:** What is a pull request and how does it help with code quality? One paragraph.

A pull request (PR) is a mechanism in version control platforms like GitHub or GitLab where a developer proposes merging a branch of code changes into another branch (typically `main` or `develop`). It creates a dedicated space for team members to review the diff, leave inline comments, suggest improvements, and run automated checks (CI/CD pipelines, linters, tests) before the code is merged. This directly improves code quality by catching bugs, enforcing style consistency, sharing knowledge across the team, and ensuring changes are intentional and reviewed — rather than landing untested code directly into shared branches.

---

## K5 · Task 4 / Branch K · Step 50

**Prompt:** What is continuous deployment and how does it benefit a solo developer project? 2 sentences.

**Continuous deployment (CD)** is the practice of automatically deploying code changes to production whenever they pass automated tests, eliminating manual release steps.

For a solo developer, it reduces toil by removing repetitive deployment tasks and provides fast feedback loops — so you can ship small changes quickly and catch issues in production without ceremony.

---

## L1 · Task 5 / Branch L · Step 50

**Prompt:** What are 3 key metrics a solo developer should track for a CLI tool project?

**3 key metrics for a CLI tool project:**

1. **Command success rate** — Percentage of invocations that exit 0 vs. non-zero. Tracks reliability and surfaces error-prone commands/flags.

2. **Time-to-first-value (TTFV)** — How long from install to the user's first successful meaningful output. High TTFV kills adoption before it starts.

3. **Crash/panic rate by version** — Unhandled errors per release. Essential for knowing whether a new version is stable or regressing, especially without a QA team.

These are lightweight enough to track via a simple log file or an opt-in analytics event without needing a full observability stack.

---

## L2 · Task 5 / Branch L · Step 52

**Prompt:** Describe the concept of a project roadmap in 2 sentences.

A project roadmap is a high-level visual or written plan that outlines the goals, milestones, and timeline for a project's development. It communicates strategic direction and priorities to stakeholders, showing what will be built and in what order.

---

## L3 · Task 5 / Branch L · Step 52

**Prompt:** List 3 ways to gather user feedback on a solo developer CLI tool.

Here are 3 practical ways to gather user feedback on a solo developer CLI tool:

1. **GitHub Issues with templates** — Add issue templates for bug reports and feature requests. Many CLI users are already on GitHub and will naturally use it. It's async, searchable, and costs nothing.

2. **In-tool feedback prompt** — After N uses or on exit, print a one-liner like `Found a bug? https://github.com/you/tool/issues` or ask a single yes/no question logged to a lightweight backend (e.g., a free Supabase table or even a Google Form).

3. **Discord/Slack community** — A small server gives you real-time feedback and lets power users self-organize. Even 10-20 active members produce more signal than hundreds of silent users.

**Quickest win**: GitHub Issues with templates — zero setup if you're already there.

---

## L4 · Task 5 / Branch L · Step 54

**Prompt:** What is feature prioritization and why is it important for solo developers? One paragraph.

Feature prioritization is the process of deciding which features or tasks to build next, based on factors like user value, business impact, technical effort, and strategic alignment. For solo developers, it's especially critical because time and energy are finite — there's no team to parallelize work across, no product manager to absorb planning overhead, and every hour spent on a low-impact feature is an hour not spent on something that actually moves the needle. Without deliberate prioritization, solo builders tend to chase interesting problems over important ones, accumulate half-finished features, and ship products that are technically impressive but miss what users actually need. A simple framework — even just asking "does this directly help users or generate revenue?" — can mean the difference between a product that gains traction and one that stalls indefinitely.

---

## L5 · Task 5 / Branch L · Step 54

**Prompt:** Describe 2 ways AI can help a solo developer with project documentation.

## AI for Solo Developer Documentation

**1. Auto-generating docs from code**
AI can read your source code and produce README files, API references, inline comments, and changelogs. Instead of writing `README.md` from scratch, you describe your project and AI drafts it — pulling function signatures, usage patterns, and architecture from the actual code. Tools like Claude Code can also keep docs in sync as code evolves.

**2. Explaining complex code in plain language**
When returning to old code or onboarding future collaborators, AI can translate dense logic into human-readable explanations. Point it at a function, module, or architectural decision and it produces a clear summary — saving the mental overhead of re-deriving "why did I write this?" from first principles.

---

## L6 · Task 5 / Branch L · Step 56

**Prompt:** What is a changelog and why should every project have one? One sentence.

A changelog is a curated, chronological record of notable changes made to a project across versions, and every project should have one so users and contributors can quickly understand what changed, when, and why.

---

## M1 · Task 5 / Branch M · Step 56

**Prompt:** List 3 strategies for getting early users for a solo developer tool.

1. **Launch on developer communities directly** — Post in relevant subreddits (r/programming, r/webdev, r/SideProject), Hacker News (Show HN), and DEV.to. Be transparent that you're a solo dev, share the problem you solved, and ask for honest feedback. Dev communities respond well to authenticity.

2. **Build in public on X/Twitter or LinkedIn** — Document your progress, share screenshots, and post about problems you're solving. Tag relevant accounts and use hashtags like #buildinpublic and #indiehacker. This creates an audience before launch and attracts users who are invested in your journey.

3. **Find your first 10 users manually** — Search GitHub issues, Discord servers, and Stack Overflow for people actively complaining about the exact problem your tool solves. DM them directly, offer free access, and ask for a 15-minute call. These conversations also shape your product faster than any survey.

---

## M2 · Task 5 / Branch M · Step 58

**Prompt:** What is developer experience (DX) and why does it matter? One paragraph.

Developer experience (DX) refers to the overall quality of a developer's interactions with tools, APIs, frameworks, documentation, and workflows — essentially how easy, efficient, and enjoyable it is to build software. It matters because friction in the development process directly impacts productivity, adoption, and code quality: a well-designed API with clear docs and sensible defaults gets used correctly and quickly, while a painful one gets avoided, misused, or wrapped in workarounds. Good DX reduces onboarding time, lowers the cognitive load of routine tasks, and lets developers focus on solving actual problems rather than fighting their tools — which ultimately means faster delivery, fewer bugs, and happier teams.

---

## M3 · Task 5 / Branch M · Step 58

**Prompt:** Describe 2 ways to measure whether a solo developer project is succeeding.

## Two Ways to Measure Solo Developer Project Success

**1. User/Market Signal (External)**
Track whether real people are using and returning to what you built. Key indicators: active users, retention rate, paying customers, or even just unsolicited feedback. A project succeeds when strangers use it without you prompting them — not just your friends or yourself. Concrete threshold: *Week-2 retention > Week-1 acquisition* means you're building something worth keeping.

**2. Momentum (Internal)**
Measure how consistently you're shipping. A solo project dies from abandonment more often than bad code. Track: commits per week, features shipped per month, or time between releases. If the gap between releases is growing, the project is dying regardless of current user numbers. A healthy project has a rhythm — even small, regular progress compounds into something substantial.

---

The first tells you if it *matters*. The second tells you if it will *survive*.

---

## M4 · Task 5 / Branch M · Step 60

**Prompt:** What is open source and what are 2 benefits of open-sourcing a solo developer project?

## What is Open Source?

Open source refers to software whose **source code is publicly available** for anyone to view, use, modify, and distribute. It's governed by a license (e.g., MIT, Apache, GPL) that defines what others can do with it.

---

## 2 Benefits for a Solo Developer

**1. Community contributions**
Others can find bugs, submit fixes, add features, and write documentation — effectively giving you free collaborators. A well-maintained repo can grow beyond what one person could build alone.

**2. Credibility and visibility**
A public portfolio of real, working code is far more compelling to employers or clients than a resume bullet point. It also makes your work discoverable, which can lead to users, feedback, and opportunities you'd never get from a private repo.

---

## N1 · Task 5 / Branch N · Step 60

**Prompt:** What are 3 signs that a software project is ready for its first public release?

1. **Core functionality is stable and tested** — The primary use cases work reliably, edge cases are handled, and you have automated tests covering critical paths. Bugs are known and tracked, not discovered by surprise.

2. **Documentation covers getting started** — A new user can install, configure, and run the project without asking you anything. README, setup instructions, and basic usage examples exist and are accurate.

3. **You can support it** — You have a way to receive bug reports (issue tracker, email, etc.), a process to respond to them, and the codebase is in a state where you can make fixes without breaking everything else.

The common thread: a public release is a commitment to other people's time. If strangers will hit blockers you can't diagnose or report problems you can't address, it's not ready.

---

## N3 · Task 5 / Branch N · Step 62

**Prompt:** List 3 things a developer should document before releasing an open-source project.

Here are 3 things a developer should document before releasing an open-source project:

1. **README / Getting Started** — Installation steps, prerequisites, a quick usage example, and what the project does. This is the first thing contributors and users will read.

2. **Contributing Guidelines** (`CONTRIBUTING.md`)  — How to report bugs, submit pull requests, coding conventions, and the branching/commit strategy. Lowers the barrier for external contributors.

3. **License** (`LICENSE`) — Explicitly state the license (MIT, Apache 2.0, GPL, etc.). Without it, the project is legally "all rights reserved" by default, which discourages adoption and contribution.

---

## N2 · Task 5 / Branch N · Step 62

**Prompt:** Describe the concept of a 'soft launch' for a developer tool. 2 sentences.

A soft launch is a limited release of a product to a small, targeted audience (early adopters, beta users, or a specific region) before a full public rollout, allowing you to gather real-world feedback and fix issues with minimal exposure. For a developer tool, this typically means making it available through invite-only access, a beta program, or a waitlist while the core functionality is validated against actual usage patterns.

---

## N5 · Task 5 / Branch N · Step 64

**Prompt:** Write a one-sentence mission statement for Solo Builder — an AI-powered CLI that manages DAG-based tasks for solo developers.

**Solo Builder** is an AI-powered CLI that helps solo developers ship faster by orchestrating complex, dependency-aware task pipelines — so you can focus on building, not coordination.

---

## N4 · Task 5 / Branch N · Step 64

**Prompt:** What is a README file and what are its 3 most important sections? One sentence each.

A README file is a text document (typically Markdown) that introduces and explains a project to anyone who encounters it.

**3 most important sections:**

1. **Description** — Explains what the project does and why it exists.
2. **Installation** — Describes how to set up and run the project locally.
3. **Usage** — Shows examples of how to use the project after installation.

---

## O1 · Task 6 / Branch O · Step 66

**Prompt:** Summarize in 3 bullet points how DAG-based task management (like Solo Builder) improves over a simple to-do list for a solo developer.

- **Dependency awareness**: A DAG enforces task ordering — you can't accidentally start a task whose prerequisites aren't done, eliminating wasted work and blocked states that a flat list can't express.

- **Critical path visibility**: You can identify which tasks are blocking the most downstream work, so a solo dev knows exactly where to focus effort rather than picking tasks arbitrarily from a list.

- **Parallelism discovery**: The graph makes it explicit which tasks have no dependency on each other and can run concurrently (or be batched), whereas a linear list implies a false sequential order that slows you down.

---

## O2 · Task 6 / Branch O · Step 66

**Prompt:** Describe how self-healing agents reduce manual intervention in a software project pipeline. One paragraph.

Self-healing agents reduce manual intervention in a software pipeline by continuously monitoring system state and autonomously detecting, diagnosing, and remediating failures without human involvement. When a build fails, a test suite regresses, a deployment goes unhealthy, or a service exceeds error thresholds, a self-healing agent intercepts the signal, traces the root cause through logs and metrics, and executes a corrective action — restarting a crashed service, rolling back a bad deploy, retrying a flaky test with adjusted parameters, or patching a configuration drift — then verifies the fix before resuming the pipeline. Because the agent encodes remediation playbooks that would otherwise require an on-call engineer, it compresses mean-time-to-recovery, eliminates the toil of repetitive incident response, and frees developers to focus on feature work rather than operational firefighting. The feedback loop also compounds over time: each resolved incident can update the agent's knowledge base, making future interventions faster and more precise while reducing the blast radius of failures that would otherwise escalate to human escalation.

---

## P1 · Task 6 / Branch P · Step 68

**Prompt:** What would a 'v2.0' of Solo Builder look like? List 3 major new features with one sentence each.

Based on the current system — a 6-agent DAG CLI that orchestrates Claude headlessly — here's what a **v2.0** could look like:

---

**1. Web UI with Live DAG Visualization**
Replace the terminal interface with a browser-based dashboard that renders the task graph in real time, showing agent activity, subtask status, and Claude outputs as they stream in.

**2. Multi-Project Workspaces**
Support managing multiple independent DAGs simultaneously, with cross-project dependency links so one project's completion can unblock a subtask in another.

**3. Autonomous Replanning on Failure**
When the SelfHealer exhausts retries, instead of stalling, have the Planner call Claude to decompose the failed subtask into smaller steps and splice them back into the DAG automatically — true self-modification of the task graph.

---

## O3 · Task 6 / Branch O · Step 68

**Prompt:** Write a 3-sentence executive summary of Solo Builder for a developer audience.

Solo Builder is a Python terminal CLI that orchestrates a six-agent pipeline (Planner, Executor, Verifier, SelfHealer, ShadowAgent, MetaOptimizer) over a DAG-based task graph, enabling a single developer to run dependency-aware, multi-branch workflows with automatic stall detection and status rollup. Each subtask with a description field is executed headlessly via `claude -p`, with `ThreadPoolExecutor` handling parallel branches across tasks, while the MetaOptimizer dynamically tunes Planner weights based on observed heal and verify rates. State is fully persistent via versioned JSON snapshots, an append-only `journal.md`, and optional PDF timeline exports — giving developers a lightweight, framework-free alternative to heavyweight project management tooling, with the operational leverage of a coordinated agent team.

---

## P3 · Task 6 / Branch P · Step 70

**Prompt:** Write a haiku about software agents managing project tasks autonomously.

Silent agents hum,
tasks branch and merge without rest—
the codebase breathes on.

---

## P2 · Task 6 / Branch P · Step 70

**Prompt:** How would you adapt Solo Builder for a team of 3-5 developers instead of a solo developer? Give 3 key changes.

Based on the codebase, here are 3 targeted changes:

---

**1. Shared state backend with file locking**

Currently `state/solo_builder_state.json` is a local file — one writer assumed. For a team, replace it with a shared path (network drive, SQLite, or a thin REST API) and add mutex locking around all reads/writes. The ShadowAgent already handles conflict detection; it just needs a real lock primitive (`fcntl.flock` or a lock file) rather than relying on single-writer assumptions.

**2. Subtask ownership model**

Add an `assigned_to` field to each subtask. The Executor skips subtasks not assigned to the current user. Devs claim subtasks with a `claim <subtask-id>` command before executing. This prevents two people from racing on the same work and makes the `status` command actually show who owns what — a critical visibility gap for any team.

**3. Split the Planner/Executor roles across principals**

Right now one person runs all six agents from one shell. For 3-5 devs, split it:
- **Lead/CI machine** runs Planner, Verifier, ShadowAgent, MetaOptimizer (orchestration layer)
- **Each dev** runs only Executor against their claimed subtasks via a `--worker-mode <name>` flag

This maps naturally to the existing `ThreadPoolExecutor` parallelism — instead of threads on one machine, it's separate processes per person, all reading from the shared state.

---

The biggest architectural shift is #1 — everything else is additive. The DAG model and agent pipeline are already sound for team use; they just assume a single-writer environment.

---

## H2 · Task 7 / Branch H · Step 72

**Prompt:** Design a minimal REST API spec for the Solo Builder DAG: define the route paths, HTTP methods, request/response schemas for GET /tasks (list all tasks with status), GET /tasks/:id (single task detail + progress), and POST /tasks/:id/trigger (trigger a step). Output as a plain JSON object.

Now I have full context on the DAG shape. Here's the spec, derived directly from the live state schema:

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "Solo Builder DAG API",
    "version": "1.0.0"
  },
  "paths": {
    "GET /tasks": {
      "summary": "List all tasks with status",
      "response": {
        "200": {
          "schema": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id":          { "type": "string", "example": "Task 0" },
                "status":      { "type": "string", "enum": ["Pending", "Running", "Verified"] },
                "depends_on":  { "type": "array",  "items": { "type": "string" } },
                "progress": {
                  "type": "object",
                  "properties": {
                    "total":    { "type": "integer" },
                    "verified": { "type": "integer" },
                    "running":  { "type": "integer" },
                    "pending":  { "type": "integer" }
                  }
                }
              },
              "required": ["id", "status", "depends_on", "progress"]
            }
          }
        }
      }
    },

    "GET /tasks/:id": {
      "summary": "Single task detail with full branch/subtask progress",
      "params": {
        "id": { "in": "path", "type": "string", "example": "Task 0" }
      },
      "response": {
        "200": {
          "schema": {
            "type": "object",
            "properties": {
              "id":         { "type": "string" },
              "status":     { "type": "string", "enum": ["Pending", "Running", "Verified"] },
              "depends_on": { "type": "array", "items": { "type": "string" } },
              "step":       { "type": "integer", "description": "Global step counter at last update" },
              "branches": {
                "type": "object",
                "additionalProperties": {
                  "type": "object",
                  "properties": {
                    "status": { "type": "string", "enum": ["Pending", "Running", "Verified"] },
                    "subtasks": {
                      "type": "object",
                      "additionalProperties": {
                        "type": "object",
                        "properties": {
                          "id":          { "type": "string", "example": "A1" },
                          "status":      { "type": "string", "enum": ["Pending", "Running", "Verified"] },
                          "shadow":      { "type": "string", "enum": ["Pending", "Done", "Conflict"] },
                          "last_update": { "type": "integer" },
                          "description": { "type": "string", "nullable": true },
                          "output":      { "type": "string", "nullable": true }
                        },
                        "required": ["id", "status", "shadow", "last_update"]
                      }
                    }
                  }
                }
              },
              "progress": {
                "type": "object",
                "properties": {
                  "total":    { "type": "integer" },
                  "verified": { "type": "integer" },
                  "running":  { "type": "integer" },
                  "pending":  { "type": "integer" },
                  "stalled":  { "type": "integer" }
                }
              }
            },
            "required": ["id", "status", "depends_on", "branches", "progress"]
          }
        },
        "404": {
          "schema": {
            "type": "object",
            "properties": {
              "error": { "type": "string", "example": "Task not found" }
            }
          }
        }
      }
    },

    "POST /tasks/:id/trigger": {
      "summary": "Trigger one agent pipeline step for a specific task",
      "params": {
        "id": { "in": "path", "type": "string", "example": "Task 1" }
      },
      "requestBody": {
        "required": false,
        "schema": {
          "type": "object",
          "properties": {
            "subtask_id": {
              "type": "string",
              "description": "Pin execution to a specific subtask ID (e.g. 'B2'). Omit to let Planner choose.",
              "example": "B2"
            },
            "force": {
              "type": "boolean",
              "description": "Bypass dependency-not-Verified guard and run anyway.",
              "default": false
            }
          }
        }
      },
      "response": {
        "200": {
          "schema": {
            "type": "object",
            "properties": {
              "task_id":    { "type": "string" },
              "subtask_id": { "type": "string" },
              "step":       { "type": "integer", "description": "Global step counter after this run" },
              "agent":      { "type": "string", "enum": ["Planner", "Executor", "Verifier", "SelfHealer", "ShadowAgent", "MetaOptimizer"] },
              "status_before": { "type": "string", "enum": ["Pending", "Running", "Verified"] },
              "status_after":  { "type": "string", "enum": ["Pending", "Running", "Verified"] },
              "healed":     { "type": "boolean" },
              "output":     { "type": "string", "nullable": true, "description": "Claude output, if Executor ran a claude -p call" }
            },
            "required": ["task_id", "subtask_id", "step", "agent", "status_before", "status_after"]
          }
        },
        "409": {
          "schema": {
            "type": "object",
            "properties": {
              "error": { "type": "string", "example": "Dependencies not Verified" },
              "blocking": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "404": {
          "schema": {
            "type": "object",
            "properties": {
              "error": { "type": "string", "example": "Task not found" }
            }
          }
        }
      }
    }
  }
}
```

**Key design decisions:**

- **`/tasks`** returns a flat list with a computed `progress` object (counts only) — no branch detail to keep it lean.
- **`/tasks/:id`** returns the full nested `branches → subtasks` structure matching `solo_builder_state.json` exactly, plus a rolled-up `progress` and the global `step` counter so clients can detect staleness.
- **`POST /tasks/:id/trigger`** is idempotent-safe (no side effects if deps aren't met), returns `409` with the blocking task list instead of silently no-oping, and echoes which agent actually ran and the before/after status transition. `subtask_id` is optional — omitting it lets the Planner pick via its priority scoring.
- Status enum is the three live values from the codebase: `Pending`, `Running`, `Verified`. Shadow adds `Conflict` for the ShadowAgent's conflict state.

---

## H4 · Task 7 / Branch H · Step 87

**Prompt:** List the curl commands you would use to manually smoke-test a REST API with endpoints GET /tasks, GET /tasks/0, and POST /tasks/0/trigger. Show expected response shapes as example JSON.

## Smoke-Test Curl Commands

Assuming a base URL of `http://localhost:3000` — replace as needed.

---

### 1. `GET /tasks`

```bash
curl -s -X GET http://localhost:3000/tasks \
  -H "Accept: application/json" | python -m json.tool
```

**Expected response:**
```json
[
  {
    "id": 0,
    "name": "Process invoices",
    "status": "idle",
    "createdAt": "2026-02-28T10:00:00Z"
  },
  {
    "id": 1,
    "name": "Send reports",
    "status": "running",
    "createdAt": "2026-02-28T09:00:00Z"
  }
]
```

---

### 2. `GET /tasks/0`

```bash
curl -s -X GET http://localhost:3000/tasks/0 \
  -H "Accept: application/json" | python -m json.tool
```

**Expected response:**
```json
{
  "id": 0,
  "name": "Process invoices",
  "status": "idle",
  "createdAt": "2026-02-28T10:00:00Z",
  "lastRunAt": null
}
```

**Check for 404 on a missing ID:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/tasks/9999
# Expected: 404
```

---

### 3. `POST /tasks/0/trigger`

```bash
curl -s -X POST http://localhost:3000/tasks/0/trigger \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool
```

**Expected response (202 Accepted is idiomatic for async triggers):**
```json
{
  "taskId": 0,
  "triggered": true,
  "runId": "run_abc123",
  "message": "Task queued successfully"
}
```

**Check the status code explicitly:**
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:3000/tasks/0/trigger \
  -H "Content-Type: application/json" \
  -d '{}'
# Expected: 200 or 202
```

---

### Quick one-liner sequence

```bash
BASE=http://localhost:3000

echo "--- GET /tasks ---"
curl -sf "$BASE/tasks" | python -m json.tool

echo "--- GET /tasks/0 ---"
curl -sf "$BASE/tasks/0" | python -m json.tool

echo "--- POST /tasks/0/trigger ---"
curl -sf -X POST "$BASE/tasks/0/trigger" \
  -H "Content-Type: application/json" -d '{}' | python -m json.tool
```

The `-sf` flags suppress progress output (`-s`) and fail with a non-zero exit code on 4xx/5xx (`-f`), so the sequence will stop early if any call errors out.

---

## H1 · Task 7 / Branch H · Step 87

**Prompt:** Describe the key data structures you would expect in a Python CLI tool that manages DAG-based task state. What fields would each Task, Branch, and Subtask have? Show as a JSON schema example.

Here's a clean design for a DAG-based task state manager, with JSON Schema examples for each entity:

---

## Core Entities

### `Task` — the primary node in the DAG

```json
{
  "id": "task_abc123",
  "name": "build_assets",
  "description": "Compile and bundle frontend assets",
  "status": "running",
  "dependencies": ["task_xyz789", "task_def456"],
  "dependents": ["task_ghi012"],
  "branch_id": "branch_frontend",
  "subtasks": ["sub_001", "sub_002"],
  "tags": ["build", "frontend"],
  "retries": 1,
  "max_retries": 3,
  "created_at": "2026-02-28T10:00:00Z",
  "started_at": "2026-02-28T10:01:05Z",
  "completed_at": null,
  "output": null,
  "error": null,
  "metadata": {
    "timeout_seconds": 300,
    "executor": "local"
  }
}
```

**Key fields:**
- `dependencies` / `dependents` — edges of the DAG (upstream/downstream)
- `status` — `pending | running | success | failed | skipped | cancelled`
- `retries` — supports retry semantics without duplicating task nodes

---

### `Branch` — a logical grouping of tasks (parallel paths, phases)

```json
{
  "id": "branch_frontend",
  "name": "Frontend Pipeline",
  "description": "All tasks related to frontend build and deploy",
  "parent_branch_id": null,
  "task_ids": ["task_abc123", "task_def456"],
  "status": "running",
  "condition": {
    "type": "all_success",
    "task_ids": ["task_xyz789"]
  },
  "created_at": "2026-02-28T09:59:00Z",
  "metadata": {}
}
```

**Key fields:**
- `parent_branch_id` — enables nested/hierarchical branches
- `condition` — gate condition before the branch activates (fanout control)
- `status` — computed from member tasks: `pending | running | success | failed | partial`

---

### `Subtask` — a sequential step within a single Task

```json
{
  "id": "sub_001",
  "parent_task_id": "task_abc123",
  "name": "run_webpack",
  "description": "Run webpack bundler",
  "order": 0,
  "status": "success",
  "started_at": "2026-02-28T10:01:05Z",
  "completed_at": "2026-02-28T10:01:45Z",
  "output": "Bundle written to dist/main.js (412 KB)",
  "error": null
}
```

**Key fields:**
- `order` — subtasks are ordered (sequential within a task), unlike DAG tasks
- `parent_task_id` — subtasks are scoped to one task, not reusable across the graph

---

### `Pipeline` — the top-level DAG container

```json
{
  "id": "pipeline_20260228",
  "name": "Full Deploy",
  "status": "running",
  "tasks": {
    "task_abc123": { "...": "..." },
    "task_xyz789": { "...": "..." }
  },
  "branches": {
    "branch_frontend": { "...": "..." }
  },
  "created_at": "2026-02-28T09:58:00Z",
  "updated_at": "2026-02-28T10:01:45Z"
}
```

---

## Design Notes

| Concern | Decision |
|---|---|
| DAG edges | Stored on `Task` as `dependencies` (upstream) + `dependents` (downstream cache) |
| Execution order | Derived at runtime via topological sort — not stored |
| Branch status | Computed from member tasks, not stored independently |
| Subtask vs Task | Subtasks are ordered steps; Tasks are DAG nodes with dependency edges |
| Retry tracking | Counter on `Task`, not new nodes, to preserve graph topology |

The `dependencies` list on each Task is the canonical edge store — everything else (`dependents`, branch `status`, pipeline `status`) is derived.

---

## H3 · Task 7 / Branch H · Step 89

**Prompt:** Write a minimal Python Flask REST API skeleton (no execution needed) with three routes: GET /tasks, GET /tasks/<task_id>, and POST /tasks/<task_id>/trigger. Show the route handlers returning mock JSON that matches the Solo Builder DAG structure.

Written to `api/app.py`. Here's a summary of what each route does and the shape it returns:

---

### `GET /tasks`
Returns a lightweight summary list — no subtask outputs, just counts and status.
```json
{
  "total": 2,
  "tasks": [
    {
      "id": "Task 0",
      "status": "Verified",
      "depends_on": [],
      "branch_count": 2,
      "subtask_count": 4,
      "verified_subtasks": 3
    },
    ...
  ]
}
```

---

### `GET /tasks/<task_id>`
Returns the full DAG node — branches → subtasks with `status`, `shadow`, `last_update`, `description`, `output`.
```json
{
  "id": "Task 0",
  "status": "Verified",
  "depends_on": [],
  "branches": {
    "Branch A": {
      "status": "Verified",
      "subtasks": {
        "A1": { "status": "Verified", "shadow": "Done", "output": "..." }
      }
    }
  }
}
```

---

### `POST /tasks/<task_id>/trigger`
Enqueues `Pending` subtasks (sets them to `Running` in-memory). Returns `202` with the list of what was queued, or `200` if the task was already `Verified`.
```json
{
  "id": "Task 1",
  "triggered": true,
  "queued_subtasks": ["Branch A/A1"],
  "queued_count": 1,
  "status": "Running"
}
```

---

**To run:**
```bash
pip install flask
flask --app api/app.py run
```

The mock data is sourced directly from `solo_builder_state.json` field names (`status`, `shadow`, `last_update`, `depends_on`, `branches`, `subtasks`, `output`) so it's a drop-in target when you wire this to the live state file.

---

## H1 · Task 7 / Branch H · Step 90

**Prompt:** Read the Solo Builder source in the current directory. List all Python files, summarise what each agent class does in one sentence, and describe how task state (Pending/Running/Verified) flows through the pipeline.

Here's the full picture.

---

## Python Files

| File | Purpose |
|---|---|
| `solo_builder_cli.py` | Main entry point — contains all six agent classes, the CLI loop, DAG definition, and state-save logic |
| `solo_builder_live_multi_snapshot.py` | Generates multi-page PDF timeline snapshots of the DAG and memory store using matplotlib |
| `api/app.py` | Thin Flask REST API skeleton that serves mock DAG state via HTTP routes |
| `utils/helper_functions.py` | Shared utilities: ANSI colour codes, progress-bar builder, DAG/branch/shadow stats, memory snapshot helpers, and DAG structural validation |
| `utils/__init__.py` | Empty package marker |

---

## Agent Classes (all in `solo_builder_cli.py`)

| Class | One-sentence summary |
|---|---|
| **`Planner`** | Scores every non-Verified subtask with a weighted risk formula (staleness × `w_staleness`, stall risk × `w_stall`, shadow mismatch × `w_shadow`) and returns a priority-sorted list, skipping tasks whose `depends_on` are not yet Verified. |
| **`ClaudeRunner`** | Wraps `claude -p <description> --output-format json` as a subprocess and returns `(success, output_text)`, with configurable timeout and allowed-tools list. |
| **`Executor`** | Drives each subtask one step forward — `Pending → Running` on the first touch, then fires Claude (in parallel via `ThreadPoolExecutor`) to complete `Running → Verified`; falls back to a probabilistic coin-flip when Claude is unavailable. |
| **`ShadowAgent`** | Maintains a parallel `expected` state map and detects mismatches where `shadow == "Done"` but `status != "Verified"` (or vice versa), then auto-resolves by aligning `shadow` to the actual `status`. |
| **`Verifier`** | Audits branch and task status fields and corrects any that don't match the aggregate of their children (e.g. forces a branch to `Verified` once all its subtasks are, or to `Running` if any are). |
| **`SelfHealer`** | Finds subtasks stuck in `Running` for ≥ `stall_threshold` steps and resets them to `Pending` (with shadow also reset), recording a memory snapshot and appending an alert each time. |
| **`MetaOptimizer`** | Records per-step heal/verify counts over a rolling 10-step window and nudges `Planner` heuristic weights upward when the heal rate is high or the verify rate is low; also produces a linear-extrapolation ETA forecast. |

---

## Task State Flow

```
          ┌──────────────────────────────────────────────┐
          │  SUBTASK  (also carries a parallel shadow field) │
          └──────────────────────────────────────────────┘

Pending ──[Executor: first touch]──► Running ──[Claude / coin-flip]──► Verified
   ▲                                    │                                   │
   └──[SelfHealer: age ≥ threshold]─────┘            shadow: Done ◄────────┘
                                        │
                          [ShadowAgent detects shadow/status mismatch
                           and writes shadow = Pending to re-sync]

BRANCH status  = Verified  when ALL subtasks  are Verified  (rolled up by Executor + Verifier)
               = Running   when ANY subtask   is Running
               = Pending   otherwise

TASK   status  = Verified  when ALL branches  are Verified
               = Running   when ANY branch    is Running
               = blocked   (not eligible for Planner) while depends_on tasks ≠ Verified

MetaOptimizer watches heal/verify rates and tweaks Planner weights each step.
```

In short: **Executor** moves state forward, **Verifier** keeps parent nodes consistent, **ShadowAgent** keeps the secondary `shadow` field consistent, **SelfHealer** unsticks stalls, **Planner** decides what to work on next, and **MetaOptimizer** tunes the planner's urgency weights over time.

---

## H3 · Task 7 / Branch H · Step 91

**Prompt:** Write a minimal Python Flask REST API skeleton (no execution needed) with three routes: GET /tasks, GET /tasks/<task_id>, and POST /tasks/<task_id>/trigger. Show the route handlers returning mock JSON that matches the Solo Builder DAG structure.

Got the schema. Here's the skeleton:

```python
# api.py
from flask import Flask, jsonify, abort

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Mock data — mirrors solo_builder_state.json structure
# ---------------------------------------------------------------------------

MOCK_DAG = {
    "Task 0": {
        "status": "Verified",
        "depends_on": [],
        "branches": {
            "Branch A": {
                "status": "Verified",
                "subtasks": {
                    "A1": {
                        "status": "Verified",
                        "shadow": "Done",
                        "last_update": 2,
                        "description": "List 5 key features a solo developer AI project management tool needs.",
                        "output": "- Task/backlog management\n- DAG visualization\n- AI execution\n- Shadow review\n- State persistence",
                    }
                },
            }
        },
    },
    "Task 1": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch C": {
                "status": "Pending",
                "subtasks": {
                    "C1": {
                        "status": "Pending",
                        "shadow": "Pending",
                        "last_update": 0,
                        "description": "What does a DAG represent in software PM?",
                        "output": "",
                    }
                },
            }
        },
    },
    "Task 2": {
        "status": "Running",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch D": {
                "status": "Running",
                "subtasks": {
                    "D1": {
                        "status": "Running",
                        "shadow": "Pending",
                        "last_update": 5,
                        "description": "Draft a minimal CLI spec for the Solo Builder executor.",
                        "output": "",
                    }
                },
            }
        },
    },
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/tasks")
def list_tasks():
    """Return all tasks with summary info (no subtask output to keep payload small)."""
    summary = {
        task_id: {
            "status": data["status"],
            "depends_on": data["depends_on"],
            "branch_count": len(data["branches"]),
        }
        for task_id, data in MOCK_DAG.items()
    }
    return jsonify({"tasks": summary})


@app.get("/tasks/<task_id>")
def get_task(task_id: str):
    """Return full task detail including all branches and subtasks."""
    task = MOCK_DAG.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found")
    return jsonify({"task_id": task_id, **task})


@app.post("/tasks/<task_id>/trigger")
def trigger_task(task_id: str):
    """
    Trigger execution of a task.

    In production this would enqueue the task for the Solo Builder executor.
    Returns the task's current state after (mock) status transition to Running.
    """
    task = MOCK_DAG.get(task_id)
    if task is None:
        abort(404, description=f"Task '{task_id}' not found")

    if task["status"] == "Verified":
        return jsonify({"error": "Task is already Verified"}), 409

    # Mock: flip Pending -> Running (real impl would delegate to executor)
    task["status"] = "Running"

    return jsonify({
        "triggered": True,
        "task_id": task_id,
        "status": task["status"],
        "depends_on": task["depends_on"],
    }), 202


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

**Route summary:**

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/tasks` | All tasks with `status`, `depends_on`, `branch_count` |
| `GET` | `/tasks/<task_id>` | Full task tree (branches + subtasks with `status`, `shadow`, `description`, `output`) |
| `POST` | `/tasks/<task_id>/trigger` | 202 with updated status; 409 if already Verified; 404 if unknown |

**Notes:**
- Mock data uses the exact field names from `solo_builder_state.json` (`status`, `shadow`, `last_update`, `description`, `output`)
- `depends_on` on Task nodes is the only place DAG edges live — branches/subtasks have none
- The trigger route returns `202 Accepted` rather than `200` since real execution would be async

---

## H3 · Task 7 / Branch H · Step 92

**Prompt:** Read state/solo_builder_state.json to understand the live DAG structure, then write a complete working Flask REST API to api/app.py. The API must load state from solo_builder_state.json on each request (not mock data). Routes: GET /tasks (all tasks with status and verified subtask count), GET /tasks/<id> (full task detail with branches and subtasks), POST /tasks/<id>/trigger (return 202 Accepted). Create the api/ directory if missing. Actually write the file to disk.

All three routes work against live data. Here's what changed:

**`api/app.py` — rewritten to load live state**

- `_load_dag()` opens `state/solo_builder_state.json` on **every request** (no caching, no mock data). Path resolves relative to the project root using `Path(__file__).parent.parent`.
- `GET /tasks` — returns all 8 tasks from the live DAG with `id`, `status`, `depends_on`, `branch_count`, `subtask_count`, `verified_subtasks`.
- `GET /tasks/<id>` — uses `<path:…>` converter so task IDs with spaces (`"Task 0"`) work correctly. Returns full task with branches and subtasks.
- `POST /tasks/<id>/trigger` — returns `202 Accepted` with the list of pending subtasks. Does **not** mutate the state file (the CLI process owns that).

Run with:
```bash
flask --app api/app.py run
# or
python api/app.py
```

---

