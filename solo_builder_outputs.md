# Solo Builder — Claude Outputs

_70 verified outputs · 70 steps_


---

# Task 0


## Branch A


### A1

**Prompt:** List 5 key features a solo developer AI project management tool needs. Bullet points.


- **Task & context persistence** — remembers project state, decisions, and blockers across sessions without re-explaining
- **Autonomous task breakdown** — converts vague goals into concrete, prioritized subtasks with dependencies
- **Progress tracking with smart reminders** — surfaces stale tasks and unfinished work without manual updates
- **Integrated code/repo awareness** — links tasks directly to files, commits, and PRs so context is never lost
- **Friction-free capture** — quick add from anywhere (CLI, chat, voice) so ideas don't get dropped mid-flow


### A2

**Prompt:** Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.


**Solo Builder** is a Python terminal CLI that leverages AI agents to manage complex projects as dependency-aware task graphs (DAGs), automatically sequencing work and surfacing what's actionable right now. Built for solo developers and indie hackers, it replaces scattered to-do lists with an intelligent co-pilot that understands project structure and keeps you moving forward.


### A3

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


### A4

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


### A5

**Prompt:** Write a tagline for Solo Builder in under 10 words.


**Build solo. Ship faster. Own everything.**


## Branch B


### B1

**Prompt:** Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.


A **Shadow Agent** runs in parallel alongside a primary agent, silently observing its inputs and outputs without intervening — used for monitoring, logging, or A/B testing alternative behaviors without affecting the main flow.

A **Verifier Agent** actively evaluates the output of another agent against defined criteria (correctness, safety, constraints) and can block, flag, or trigger a retry if the output fails validation — acting as a quality gate rather than a passive observer.


### B2

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


### B3

**Prompt:** In one sentence, explain what a MetaOptimizer does in an AI pipeline.


A MetaOptimizer is a higher-level optimization component that tunes the hyperparameters or learning strategies of underlying optimizers, effectively "learning how to learn" to improve overall model training efficiency.


---

# Task 1


## Branch C


### C1

**Prompt:** What does a DAG (Directed Acyclic Graph) represent in software project management? Answer in one paragraph.


A DAG (Directed Acyclic Graph) in software project management represents the dependency relationships between tasks, where each node is a task and each directed edge indicates that one task must complete before another can begin — with the "acyclic" constraint ensuring there are no circular dependencies (i.e., no task can depend on itself directly or indirectly). This structure is foundational to build systems (like Make, Bazel, or Gradle), CI/CD pipelines, workflow orchestrators (like Airflow or Prefect), and package managers, because it allows the system to determine a valid execution order (topological sort), identify which tasks can run in parallel, and pinpoint the critical path — the longest chain of dependent tasks that determines the minimum total completion time.


### C2

**Prompt:** List 3 advantages of using a priority queue to schedule software tasks.


1. **Efficient scheduling by importance** — Higher-priority tasks (e.g., UI updates, critical errors) are processed before lower-priority background work, ensuring responsiveness without manual sorting.

2. **O(log n) insertion and extraction** — Adding a task or pulling the next task costs O(log n) time, making it far more efficient than a sorted list (O(n) insertion) for dynamic workloads.

3. **Natural preemption support** — When a high-priority task arrives mid-queue, it automatically surfaces to the front without reordering the entire queue, making it well-suited for real-time and event-driven systems.


### C3

**Prompt:** Explain the concept of task staleness in a project management system in 2 sentences.


Task staleness refers to the condition where a task has not been updated, progressed, or acted upon within an expected timeframe, causing it to fall out of sync with the current state of the project. Stale tasks can mislead teams about actual progress, create bottlenecks, and obscure blockers that need attention.


### C4

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


## Branch D


### D1

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


### D2

**Prompt:** What is the difference between optimistic and pessimistic task verification? One paragraph.


**Optimistic task verification** assumes a task succeeded unless evidence suggests otherwise — it proceeds immediately after an action and only checks for failures reactively (e.g., catching exceptions or checking results after the fact). **Pessimistic task verification** assumes a task may have failed and actively confirms success before proceeding — it waits for explicit confirmation, polls for state changes, or validates preconditions and postconditions at each step. Optimistic verification is faster and lower-overhead but risks cascading failures when an undetected error propagates through subsequent steps; pessimistic verification is slower and more defensive but catches problems early and prevents work built on a faulty foundation, making it preferable for irreversible or high-stakes operations.


---

# Task 2


## Branch E


### E1

**Prompt:** What are 3 benefits of self-healing automation in a software pipeline?


1. **Reduced downtime** — Automated detection and recovery from failures (flaky tests, transient network errors, crashed services) keeps pipelines running without waiting for human intervention.

2. **Lower operational burden** — Engineers spend less time on reactive firefighting (restarting stuck jobs, re-triggering failed deploys) and more time on feature work.

3. **Faster feedback loops** — Automatic retries, rollbacks, and self-correction mean failures resolve in seconds/minutes rather than hours, so code quality signals reach developers quickly.


### E2

**Prompt:** Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.


A MetaOptimizer learns from an agent's historical performance data — tracking which strategies, prompts, or hyperparameters led to better outcomes — and automatically adjusts the agent's configuration to favor higher-performing approaches over time. By treating the optimization process itself as a learning problem, it enables agents to compound improvements across sessions rather than starting fresh each run.


### E3

**Prompt:** List 3 metrics that indicate an AI agent system is performing well.


Here are 3 key metrics for evaluating AI agent system performance:

1. **Task Completion Rate** — The percentage of tasks the agent successfully completes end-to-end without human intervention or failure. Higher is better; low rates indicate reasoning gaps, tool failures, or unclear goal handling.

2. **Latency / Time-to-Resolution** — How long the agent takes to complete tasks from start to finish, including tool calls and reasoning steps. Useful for identifying inefficiencies in planning or excessive back-and-forth.

3. **Hallucination / Error Rate** — The frequency of factually incorrect outputs, failed tool calls, or logical errors per task. Low error rates signal reliable grounding and good tool use; high rates indicate the agent is guessing rather than verifying.


### E4

**Prompt:** What is the difference between reactive and proactive error handling in agent systems? One sentence each.


**Reactive**: The agent detects and responds to errors *after* they occur (e.g., catching exceptions, retrying failed tool calls).

**Proactive**: The agent anticipates and prevents errors *before* they occur (e.g., validating inputs, checking preconditions, planning for known failure modes).


### E5

**Prompt:** Give one example of a heuristic weight that a MetaOptimizer might adjust in a task planner.


A **MetaOptimizer** might adjust the **urgency decay rate** — the weight that controls how quickly a task's priority score increases as its deadline approaches.

For example:

```
priority_score = base_importance * (1 + urgency_weight * e^(time_remaining / deadline))
```

If the optimizer observes that tasks are consistently being picked up too late (deadline misses are common), it increases `urgency_weight` so the exponential ramp starts steeper and earlier — causing the planner to pull deadline-sensitive tasks into the active queue sooner.

Conversely, if the planner is constantly preempting long-running tasks to service near-deadline work (causing fragmentation and context-switch overhead), the optimizer reduces `urgency_weight` to smooth out the priority curve.


## Branch F


### F1

**Prompt:** What is the role of a Verifier agent in a multi-agent pipeline? 2 sentences.


A Verifier agent checks the output of other agents for correctness, completeness, or adherence to requirements before passing results downstream. It acts as a quality gate, catching errors or hallucinations early to prevent bad data from propagating through the pipeline.


### F2

**Prompt:** Describe how memory snapshots help with debugging in an agent system. One paragraph.


Memory snapshots capture the full state of an agent's working memory — variables, conversation history, tool call results, task queues — at a specific point in time, creating a reproducible checkpoint you can inspect after a failure. When an agent produces unexpected output or crashes mid-task, you can load the snapshot and replay execution from that exact state rather than re-running the entire job from scratch, which is especially valuable in long multi-step workflows where the failure occurs late in the chain. Snapshots also let you compare states before and after a suspicious action (a tool call, an LLM response, a memory update) to isolate exactly where reasoning went wrong, turning an otherwise opaque "the agent did something weird" into a concrete diff between two known states. In multi-agent systems, per-agent snapshots additionally help you trace which agent introduced a bad assumption that cascaded downstream — acting as the equivalent of a core dump for distributed, non-deterministic AI processes.


### F3

**Prompt:** List 2 ways a ShadowAgent could detect state inconsistencies in a DAG pipeline.


Two ways a ShadowAgent could detect state inconsistencies in a DAG pipeline:

**1. Checksum / Hash Comparison at Node Boundaries**

The ShadowAgent shadows each node's output by computing a deterministic hash (e.g., SHA-256) of the output payload before it propagates downstream. On replay or re-execution, it recomputes the hash and compares — a mismatch signals that a node produced a different result given the same inputs, indicating non-determinism, a mutated upstream dependency, or silent data corruption mid-pipeline.

**2. Topological Epoch Versioning**

Each node in the DAG is assigned a monotonically increasing epoch counter tied to its execution order. The ShadowAgent tracks expected vs. observed epoch sequences for every edge. If a downstream node's epoch is higher than its upstream parent's, or if two sibling nodes share the same epoch when they shouldn't, it reveals out-of-order execution, a skipped node, or a cycle that violated the acyclic constraint — all forms of state inconsistency.

---

Both approaches are complementary: hash comparison catches **data-level drift**, while epoch versioning catches **execution-order drift**.


### F4

**Prompt:** What is the difference between a branch and a task in a DAG-based project tracker? One sentence.


A **branch** represents a line of development (a sequence of commits diverging from a common ancestor), while a **task** is a discrete unit of work tracked in the project — branches are a version control concept, tasks are a project management concept.


---

# Task 3


## Branch G


### G1

**Prompt:** What is continuous integration and how does it relate to automated project management? One paragraph.


Continuous integration (CI) is a software development practice where developers frequently merge code changes into a shared repository — typically multiple times per day — and each merge triggers an automated pipeline that builds the project, runs tests, and reports results. It relates to automated project management in that CI systems (like GitHub Actions, GitLab CI, or Jenkins) can be extended beyond just building and testing to automatically update task boards, close issues when tests pass, trigger deployments, notify team channels, generate reports, and enforce quality gates that gate progress on a project. This tight feedback loop means project state (what's done, what's broken, what's blocked) stays synchronized with the actual code, reducing manual overhead and giving project managers real-time visibility into health and progress without requiring developers to manually update tickets or status trackers.


### G2

**Prompt:** List 3 common causes of technical debt in solo developer projects.


1. **Skipping tests** — Moving fast without unit/integration tests means bugs compound and refactoring becomes risky.

2. **Premature abstractions (or none at all)** — Either over-engineering early ("I might need this later") or copy-pasting instead of extracting shared logic, both create maintenance burden.

3. **Deferred dependency updates** — Letting packages fall behind means larger, riskier upgrade jumps later, often with breaking changes that cascade through the codebase.


### G3

**Prompt:** Describe the MVP (Minimum Viable Product) concept in 2 sentences.


An MVP is the simplest version of a product that delivers core value to early users and validates key assumptions with minimal development effort. It prioritizes learning over features, allowing you to gather real feedback before investing in a full build.


### G4

**Prompt:** What is a sprint in agile methodology? One sentence.


A sprint is a fixed-length iteration (typically 1–4 weeks) in which a development team completes a set of prioritized work items from the backlog.


### G5

**Prompt:** List 3 developer tools a solo builder could use alongside an AI task manager.


Here are 3 developer tools that pair well with an AI task manager for solo builders:

1. **Linear** — Lightweight issue tracking with keyboard-first UX. Great for turning AI-generated tasks into structured tickets with priorities and cycles.

2. **Vercel** — Zero-config deployments with instant preview URLs per commit. Lets you ship fast without devops overhead, so you stay focused on building.

3. **Supabase** — Postgres + auth + storage in one hosted platform. Reduces the infrastructure surface area a solo builder needs to manage, pairing well with AI-generated backend code.


### G6

**Prompt:** What is the difference between async and sync task execution in pipelines? One paragraph.


In a pipeline, **synchronous (sync) execution** processes tasks sequentially — each task must complete before the next begins, blocking the thread until it finishes, which is simple to reason about but wastes time when tasks involve waiting (I/O, network, disk). **Asynchronous (async) execution** allows tasks to be initiated without blocking the caller — when a task hits a wait point (e.g., a network request), control is yielded back so other tasks can run concurrently on the same thread (via an event loop, as in Node.js or Python's `asyncio`), or tasks are dispatched to separate threads/processes and results are collected later via callbacks, promises, or futures. The key practical difference is throughput: sync pipelines serialize work and are bottlenecked by the slowest step, while async pipelines overlap I/O-bound work and can saturate available resources — though async introduces complexity around error handling, ordering guarantees, and backpressure management.


## Branch H


### H1

**Prompt:** Describe the concept of a 'Definition of Done' in software projects. 2 sentences.


A **Definition of Done** (DoD) is a shared, explicit checklist of criteria that must be met before a work item (feature, task, or story) is considered complete — covering things like code review, tests passing, documentation, and deployment. It prevents ambiguity about "done" by ensuring all team members apply the same quality standard consistently.


### H2

**Prompt:** List 3 ways to reduce context-switching costs for a solo developer.


Here are 3 ways to reduce context-switching costs for a solo developer:

1. **Batch similar work into time blocks** — Group all code reviews, emails, and deploys into dedicated slots rather than interleaving them with deep work. Protect at least one 2–3 hour uninterrupted block daily for complex coding.

2. **Write "re-entry notes" before stopping work** — Before closing a task, write 2–3 sentences: what you were doing, what's broken/in-progress, and the next step. This eliminates the costly "where was I?" ramp-up when you return.

3. **Minimize WIP (work in progress)** — Finish one feature branch before starting another. Multiple open PRs, half-done refactors, and stale branches create cognitive overhead every time you `git status`. Fewer open loops = faster context reload.


### H3

**Prompt:** What is the Pomodoro technique and how might it help a solo developer? One paragraph.


The Pomodoro technique is a time management method where you work in focused 25-minute intervals (called "pomodoros") separated by 5-minute breaks, with a longer 15-30 minute break after every four cycles. For a solo developer, it's particularly useful because it combats the two biggest productivity killers in solo work: endless context-switching and the illusion of progress from scattered, unfocused effort. By committing to a single task for 25 minutes with no interruptions — no Slack, no email, no "quick" tab switches — you build momentum and actually finish things. The mandatory breaks prevent burnout and give your brain time to consolidate what you just worked on, which matters a lot for debugging and design thinking. It also creates a natural rhythm for a workday that otherwise has no external structure, which is one of the hardest challenges of working alone.


### H4

**Prompt:** Give 2 examples of how AI can assist with project estimation for a solo developer.


## AI-Assisted Project Estimation for Solo Developers

**1. Breaking Down Tasks and Generating Time Estimates**

A solo dev can describe a feature (e.g., "Add OAuth login with Google") and ask an AI to decompose it into subtasks with rough hour estimates. The AI draws on patterns from similar projects to flag hidden complexity — things like token refresh logic, session handling, and error states that are easy to underestimate. The result is a task list with estimates the dev can adjust based on their own skill level.

**2. Historical Pattern Matching Against Scope Creep**

After a few projects, a dev can feed AI their past estimates vs. actuals and ask it to identify where they consistently over- or under-estimate. The AI surfaces patterns like "you always underestimate database migration work by 3x" or "UI polish tasks run 50% over" — turning past mistakes into a calibration factor applied automatically to future estimates.

---

Both examples work well for solo developers because there's no team to do informal calibration with — AI acts as a second perspective on scope and effort.


## Branch I


### I1

**Prompt:** What is scope creep and how can a solo developer prevent it? One paragraph.


Scope creep is the gradual expansion of a project's requirements beyond its original boundaries, often caused by adding "just one more feature," accommodating new stakeholder requests, or discovering unexpected complexity mid-build — and for a solo developer it's especially dangerous because there's no team to push back or absorb the extra work. To prevent it, define a tight written spec before coding (even a single-page doc listing what's explicitly **in** and **out** of scope), use a strict prioritization method like MoSCoW (Must/Should/Could/Won't), time-box features so each one has a deadline, and ruthlessly defer anything that wasn't in the original spec to a "v2 backlog" rather than folding it in mid-sprint — the discipline of writing "v2" next to an idea rather than implementing it immediately is one of the most powerful habits a solo builder can develop.


### I2

**Prompt:** List 3 warning signs that a solo software project is at risk of failure.


1. **Scope creep without shipping** — Continuously adding features before releasing anything. If you haven't shipped a working version after weeks of work, the project rarely recovers.

2. **No real user feedback loop** — Building in isolation based on assumptions. If no one outside yourself has used or validated the core idea, you're likely solving a problem that doesn't exist or building the wrong solution.

3. **Avoided the hardest problem** — Spending time on UI, tooling, or peripheral features while the core technical or business challenge remains untouched. This is usually procrastination disguised as progress.


### I3

**Prompt:** Describe the concept of 'bikeshedding' and why it's a risk for solo developers. 2 sentences.


**Bikeshedding** is the tendency to spend disproportionate time on trivial, easy-to-discuss decisions (like what color to paint a bike shed) while neglecting complex, critical ones. For solo developers, it's especially dangerous because there's no team to redirect focus — you can burn hours debating folder naming conventions or color palettes while core features remain unbuilt.


---

# Task 4


## Branch J


### J1

**Prompt:** What are 3 principles of clean code that every solo developer should follow?


1. **Write code for your future self, not the current moment.** You'll forget context. Use clear, intention-revealing names over abbreviations or clever tricks. `calculateMonthlyRevenue()` beats `calcRev()` every time.

2. **Small functions, single responsibility.** If you can't describe what a function does in one sentence without using "and", split it. Short functions are easier to test, debug, and reuse.

3. **Delete dead code immediately.** As a solo dev, there's no one else to clean up commented-out blocks or unused functions. They become noise that slows you down. Version control is your safety net — trust it and delete freely.


### J2

**Prompt:** Describe the DRY (Don't Repeat Yourself) principle in one sentence with a concrete example.


DRY means every piece of knowledge should have a single, authoritative representation in a codebase — for example, instead of hardcoding `0.08` in five different tax calculation functions, define `TAX_RATE = 0.08` once and reference it everywhere.


### J3

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


### J4

**Prompt:** Pick 3 of the SOLID principles and explain each in one bullet point.


- **Single Responsibility Principle**: A class should have only one reason to change — each class does one thing and owns it completely.
- **Open/Closed Principle**: Code should be open for extension but closed for modification — add new behavior by extending, not by editing existing code.
- **Dependency Inversion Principle**: High-level modules should not depend on low-level modules; both should depend on abstractions — program to interfaces, not implementations.


### J5

**Prompt:** What is test-driven development (TDD)? Describe it in 2 sentences.


Test-driven development (TDD) is a software development practice where you write failing tests **before** writing the implementation code, then write the minimum code needed to make those tests pass. The cycle repeats in short iterations: **Red** (write a failing test) → **Green** (make it pass) → **Refactor** (clean up the code).


### J6

**Prompt:** List 3 benefits of writing unit tests for a solo developer project.


1. **Catch regressions fast** — When you revisit code after weeks away, tests immediately tell you if a change broke something, without needing to manually re-verify everything.

2. **Fearless refactoring** — You can restructure or optimize code with confidence, knowing the test suite will flag any behavioral changes you didn't intend.

3. **Living documentation** — Tests describe exactly how your code is supposed to behave, serving as always-up-to-date examples that are more reliable than comments or README notes.


### J7

**Prompt:** What is a linter and why should solo developers use one? One paragraph.


A **linter** is a static analysis tool that scans your source code for potential errors, style violations, and suspicious patterns without actually running the code — catching things like undefined variables, unreachable code, inconsistent formatting, or common logic mistakes before they cause runtime bugs. For solo developers, linters are especially valuable because there's no teammate to catch mistakes in code review; the linter acts as that second pair of eyes, enforcing consistency and flagging problems the moment you write them. The feedback loop is immediate and cheap, saving hours of debugging sessions that would otherwise be spent hunting down issues that a tool like ESLint or Ruff would have caught in milliseconds.


### J8

**Prompt:** Describe the difference between unit tests and integration tests in one sentence each.


**Unit tests** verify a single function or component in isolation, mocking all external dependencies.

**Integration tests** verify that multiple components or systems work correctly together with real (or minimally mocked) dependencies.


## Branch K


### K1

**Prompt:** What is semantic versioning (semver)? Give one example of a version bump and why.


Semantic versioning (semver) is a versioning scheme with the format **MAJOR.MINOR.PATCH**.

Each number has a specific meaning:

- **MAJOR** — breaking change (incompatible API change)
- **MINOR** — new feature, backwards-compatible
- **PATCH** — bug fix, backwards-compatible

**Example:**

A library is at `2.3.1`. You fix a null pointer bug with no API changes → bump to `2.3.2`.

The rule: *increment the relevant segment, reset all lower segments to zero.* So a new feature would go `2.3.1` → `2.4.0`, and a breaking change would go `2.3.1` → `3.0.0`.


### K2

**Prompt:** List 3 best practices for writing clear git commit messages.


1. **Use the imperative mood in the subject line** — Write "Add login validation" not "Added login validation" or "Adding login validation". This matches git's own generated messages (e.g., "Merge branch...").

2. **Keep the subject line under 50 characters** — Forces you to be concise and specific. If you can't summarize the change in 50 chars, the commit is probably doing too much.

3. **Explain *why*, not *what*, in the body** — The diff already shows *what* changed. Use the body (separated by a blank line) to explain the motivation, context, or trade-offs that aren't obvious from the code.


### K3

**Prompt:** What is a pull request and how does it help with code quality? One paragraph.


A pull request (PR) is a mechanism in version control platforms like GitHub or GitLab where a developer proposes merging changes from one branch into another, typically from a feature branch into `main`. It creates a structured review opportunity where teammates can inspect the diff, leave inline comments, request changes, and run automated checks (CI/CD tests, linters, static analysis) before any code reaches the shared codebase. This process enforces a quality gate: bugs and design issues get caught by reviewers who have fresh eyes, coding standards are enforced consistently, knowledge is shared across the team as everyone sees what changed and why, and the commit history stays clean with meaningful, reviewed changesets rather than unreviewed work-in-progress commits landing directly on the main branch.


### K4

**Prompt:** Describe the concept of self-code-review for a solo developer. 2 sentences.


Self-code-review is the practice of a solo developer critically examining their own code after a short time away from it, treating it as if written by someone else to catch bugs, logic errors, and design issues. It simulates the benefits of peer review by forcing a deliberate context switch — reading for correctness and clarity rather than just writing to make it work.


### K5

**Prompt:** What is continuous deployment and how does it benefit a solo developer project? 2 sentences.


**Continuous deployment (CD)** is the practice of automatically deploying every code change that passes automated tests directly to production, without manual intervention.

For a solo developer, it eliminates deployment toil and reduces context-switching — you commit code, tests run, and the app updates itself, letting you stay focused on building rather than ops.


---

# Task 5


## Branch L


### L1

**Prompt:** What are 3 key metrics a solo developer should track for a CLI tool project?


Three key metrics for a solo developer building a CLI tool:

1. **Command success rate** — percentage of invocations that exit 0. Catches regressions fast and surfaces the most-broken commands without needing user reports.

2. **Time-to-first-output** — how long from invocation until the user sees *something*. CLI tools live or die on perceived speed; even a spinner within 100ms matters.

3. **Error message frequency by type** — which specific errors are thrown most often. Tells you where users are hitting walls (bad inputs, missing config, auth failures) so you prioritize docs or UX fixes where they'll actually help.


### L2

**Prompt:** Describe the concept of a project roadmap in 2 sentences.


A project roadmap is a high-level visual or strategic plan that outlines the goals, milestones, and timeline for a project's development. It communicates the direction and priorities to stakeholders, helping teams align on what needs to be built, in what order, and by when.


### L3

**Prompt:** List 3 ways to gather user feedback on a solo developer CLI tool.


1. **GitHub Issues** — Add a feedback link in your CLI's help output or README pointing to a GitHub Issues template. Low friction for technical users who are already on GitHub.

2. **In-tool prompt** — After N uses or on exit, print a one-line prompt: `Found a bug or have feedback? → https://your-link`. Opt-in, non-blocking.

3. **Anonymous telemetry with opt-out** — Log usage events (commands run, errors hit) to a service like PostHog or a simple webhook. Be transparent in docs and honor `--no-telemetry`.


### L4

**Prompt:** What is feature prioritization and why is it important for solo developers? One paragraph.


Feature prioritization is the process of deciding which features, improvements, or bug fixes to work on first based on factors like user impact, business value, effort required, and strategic goals. For solo developers, it's especially critical because you have a single finite resource — your own time — with no team to parallelize work across. Without deliberate prioritization, it's easy to spend weeks building features that turn out to be low-impact while critical user needs go unmet, or to chase interesting technical problems instead of the work that actually moves the needle. Good prioritization frameworks (like MoSCoW, RICE scoring, or simple impact/effort matrices) help you cut through the noise, avoid building for hypothetical users, and ship a product that solves real problems — which is ultimately the only thing that matters for getting traction as a solo builder.


### L5

**Prompt:** Describe 2 ways AI can help a solo developer with project documentation.


## AI for Solo Developer Documentation

**1. Auto-generating docs from code**
AI can read your source files and produce README sections, API references, inline comments, or changelogs — saving you from writing boilerplate documentation manually. You describe what the code does once, and AI formats it consistently across the project.

**2. Keeping docs in sync with changes**
When you refactor a function or add a new endpoint, AI can diff your changes and flag or update outdated documentation, so your docs don't quietly fall behind the code over time.


### L6

**Prompt:** What is a changelog and why should every project have one? One sentence.


A changelog is a curated, human-readable file that documents notable changes made to a project over time, so users and contributors can quickly understand what changed between versions without reading raw commit history.


## Branch M


### M1

**Prompt:** List 3 strategies for getting early users for a solo developer tool.


1. **Post in niche communities where the problem lives** — Reddit (r/webdev, r/programming, r/SideProject), Hacker News "Show HN", and Discord servers. Lead with the problem you solved, not the product. Engage in comments before dropping a link.

2. **Write SEO-targeted content around the pain point** — A single well-ranked article or Stack Overflow answer that describes the exact problem your tool solves will drive warm traffic indefinitely. Costs nothing but time and compounds over months.

3. **Direct outreach to people already complaining publicly** — Search Twitter/X, GitHub Issues, or Reddit for people expressing the exact frustration your tool addresses. Reply with a genuine offer to try it free. Converts well because the pain is already confirmed.


### M2

**Prompt:** What is developer experience (DX) and why does it matter? One paragraph.


Developer experience (DX) refers to the overall quality of the experience developers have when building with, on top of, or alongside a product, platform, API, or codebase — encompassing everything from documentation clarity and tooling ergonomics to feedback loop speed, error message quality, and cognitive load. It matters because friction in the development process compounds: slow builds, confusing APIs, poor docs, and unclear errors all tax developer attention and morale, leading to slower iteration, more bugs, and higher churn on teams and third-party adopters. When DX is good, developers stay in flow, ship faster, make fewer mistakes, and genuinely enjoy their work — which translates directly to better products and stronger retention of both internal engineers and external ecosystem contributors.


### M3

**Prompt:** Describe 2 ways to measure whether a solo developer project is succeeding.


## Two Ways to Measure Solo Developer Project Success

**1. User/Revenue Traction**
Track whether real people are paying for or actively using what you built. Concrete signals: monthly recurring revenue (MRR), active user count, retention rate (do users come back?), or even just the number of people who paid once. The key is that external validation — someone outside your own head found it worth their time or money — is the clearest signal a project is succeeding vs. just existing.

**2. Shipping Velocity vs. Roadmap Progress**
Measure how consistently you're moving from idea to shipped feature. A simple metric: count features/fixes shipped per week or month, compared to your backlog. If velocity is steady or growing and the backlog is shrinking toward your v1 definition, the project is on track. If the backlog grows faster than you ship, or weeks pass with nothing deployed, that's a failure signal regardless of code quality.

The first measures *external* success (does it matter to anyone?), the second measures *internal* execution (are you actually building it?). Both matter — projects can fail by having users but never finishing, or by being "done" but unused.


### M4

**Prompt:** What is open source and what are 2 benefits of open-sourcing a solo developer project?


## What is Open Source?

Open source refers to software whose **source code is publicly available** for anyone to view, use, modify, and distribute. It's governed by a license (e.g., MIT, Apache, GPL) that defines what others can do with it.

---

## 2 Benefits for Solo Developers

**1. Community bug reports and contributions**
Others can find bugs you'd never catch alone, and occasionally submit fixes or features. Even if no one contributes code, having users file issues is valuable QA you'd otherwise have to pay for.

**2. Credibility and visibility**
A public GitHub repo with real code is a stronger portfolio signal than a description on a resume. It demonstrates how you actually write and structure code, which matters when attracting clients, employers, or collaborators.


## Branch N


### N1

**Prompt:** What are 3 signs that a software project is ready for its first public release?


1. **Core functionality is stable and tested** — The primary use cases work reliably, critical bugs are fixed, and there's at least basic test coverage. Edge cases can be addressed post-launch, but the main path shouldn't be broken.

2. **Documentation covers getting started** — A new user can install, configure, and run the project without asking questions. A README with prerequisites, installation steps, and a basic usage example is the minimum bar.

3. **You have a feedback and issue channel** — There's a way for users to report bugs or ask questions (GitHub Issues, a Discord, an email). Releasing without this means problems disappear into the void and you lose early adopter goodwill.


### N2

**Prompt:** Describe the concept of a 'soft launch' for a developer tool. 2 sentences.


A soft launch is a limited, low-key release of a tool to a small audience (beta users, waitlist members, or a specific community) before a full public launch, allowing you to gather real-world feedback and fix issues without the pressure of broad visibility. It's distinct from a hard launch in that there's minimal marketing push — the goal is validation and iteration, not maximum reach.


### N3

**Prompt:** List 3 things a developer should document before releasing an open-source project.


Here are 3 things a developer should document before releasing an open-source project:

1. **README** — Purpose, features, installation steps, and a quick-start example so users can get running immediately.

2. **Contributing guidelines** (`CONTRIBUTING.md`) — How to report issues, submit PRs, coding standards, and the review process so contributors know what's expected.

3. **License** (`LICENSE`) — The exact terms under which others can use, modify, and distribute the code. Without this, the project is legally "all rights reserved" by default.


### N4

**Prompt:** What is a README file and what are its 3 most important sections? One sentence each.


A README file is a text document (typically Markdown) placed at the root of a project that introduces and explains the project to anyone who encounters it.

**3 most important sections:**

1. **What it is** — A brief description of what the project does and the problem it solves.
2. **How to install/set it up** — The steps needed to get the project running on your machine.
3. **How to use it** — Basic usage examples or commands so users can get started immediately.


### N5

**Prompt:** Write a one-sentence mission statement for Solo Builder — an AI-powered CLI that manages DAG-based tasks for solo developers.


**Solo Builder** is an AI-powered CLI that helps solo developers ship faster by orchestrating complex, dependency-aware tasks as intelligent DAGs — so you can focus on building, not managing.


---

# Task 6


## Branch O


### O1

**Prompt:** Summarize in 3 bullet points how DAG-based task management (like Solo Builder) improves over a simple to-do list for a solo developer.


- **Dependency enforcement** — Tasks are only surfaced when their prerequisites are complete, preventing wasted effort on work that's blocked or out of order.
- **Critical path visibility** — The graph reveals which tasks have the most downstream dependencies, so you instinctively prioritize work that unblocks the most future tasks.
- **Cascading updates** — Changing or delaying one task automatically propagates impact through dependents, giving an accurate picture of what's actually next rather than a stale flat list.


### O2

**Prompt:** Describe how self-healing agents reduce manual intervention in a software project pipeline. One paragraph.


Self-healing agents reduce manual intervention by continuously monitoring pipeline health, detecting anomalies or failures in real time, and autonomously executing corrective actions — such as retrying failed builds, rolling back bad deployments, restarting crashed services, or scaling resources under load — without requiring a human to be paged. They encode operational runbooks as executable logic, so common failure modes (flaky tests, dependency timeouts, out-of-memory crashes) are resolved instantly through pre-defined remediation strategies rather than waking an on-call engineer at 3am. By closing the feedback loop automatically, they shift human attention from reactive firefighting to proactive improvement: engineers review post-incident summaries and tune agent thresholds instead of manually diagnosing and fixing the same recurring issues over and over.


### O3

**Prompt:** Write a 3-sentence executive summary of Solo Builder for a developer audience.


Solo Builder is a Python terminal CLI that orchestrates AI agents — Planner, Executor, Verifier, SelfHealer, ShadowAgent, and MetaOptimizer — to manage a DAG-based project task graph, enabling a solo developer to run multi-branch, dependency-aware workflows from a single interactive shell. The system tracks subtask lifecycle (Pending → Running → Verified), detects stalls and DAG inconsistencies automatically, and snapshots state as versioned PDFs with a persistent `journal.md`, giving developers an auditable record of project progress. Built entirely in Python with no external orchestration framework, Solo Builder is a lightweight, self-contained alternative to heavyweight project management tools — designed for one developer operating with the leverage of a coordinated agent team.


## Branch P


### P1

**Prompt:** What would a 'v2.0' of Solo Builder look like? List 3 major new features with one sentence each.


Based on the current Solo Builder — a Python terminal CLI with DAG-based task orchestration, multi-agent coordination (Planner, Executor, ShadowAgent, Verifier, SelfHealer, MetaOptimizer), and PDF snapshot reporting — here's what v2.0 could look like:

---

**1. Natural Language Task Ingestion**
Accept a freeform project description or spec doc and automatically decompose it into a populated DAG of tasks, branches, and dependencies without manual `add_task` commands.

**2. Real Codebase Awareness**
Integrate with the actual project directory so agents can read file state, detect completed work, and automatically advance subtask lifecycle based on observable artifacts (files, commits, test results) rather than manual status updates.

**3. Web UI / Dashboard**
Replace the terminal-only interface with a local browser dashboard that renders the DAG visually, shows agent activity in real-time, and lets you interact with tasks via click and drag rather than CLI commands.


### P2

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


### P3

**Prompt:** Write a haiku about software agents managing project tasks autonomously.


Silent agents hum,
Tasks cascade through logic trees—
Code ships while you sleep.
