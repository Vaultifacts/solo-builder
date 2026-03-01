# Solo Builder — Claude Outputs

Step: 71  |  Verified: 70/70

---

## A1 — Task 0 / Branch A

**Prompt:** List 5 key features a solo developer AI project management tool needs. Bullet points.


- **Task breakdown & prioritization** — AI decomposes goals into actionable tasks and surfaces what to work on next
- **Context persistence** — remembers project history, decisions, and progress across sessions without manual note-taking
- **Blocker detection** — identifies when you're stuck and suggests concrete unblocking actions or alternative approaches
- **Scope management** — flags scope creep and keeps features tied to the core goal to prevent endless yak-shaving
- **Progress summarization** — generates concise status reports so you always know where the project stands at a glance


## A2 — Task 0 / Branch A

**Prompt:** Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.


**Solo Builder** is a Python terminal CLI that uses AI agents to manage your projects as a directed acyclic graph — automatically tracking dependencies, surfacing what's blocked, and telling you exactly what to work on next.

Stop juggling tasks in spreadsheets or bloated project tools; Solo Builder keeps solo developers in flow by turning your project's natural task structure into an intelligent, agent-driven command center that runs right where you already work.


## A3 — Task 0 / Branch A

**Prompt:** Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.


Based on reading the codebase — the CLI, API, dashboard, and journal — here are 3 concrete improvements ranked by solo-dev impact:

---

## 1. Human-in-the-Loop Verification (`verify <ST> [note]`)

**The gap:** Subtasks without a `description` field advance to `Verified` via a probability roll (`EXEC_VERIFY_PROB = 0.6`). There's no way to mark real work done — work you did outside the CLI (a design decision, a manual deploy, a code review).

**The fix:** Add a `verify <ST> [note]` command that hard-sets a subtask to `Verified`, appends an entry to `journal.md` with a timestamp and your note, and triggers the Verifier rollup. This closes the loop between simulated progress and actual human output.

**Why it matters:** Right now the DAG can show 80% verified with 0% of it being real. One command makes the tool honest.

---

## 2. Velocity-Based ETA in `status` and `/status` API

**The gap:** The system tracks `step` counts but not wall-clock time. The journal explicitly identified this as a key need: *"Progress estimation — realistic time/effort tracking calibrated to your actual velocity."* Currently there's no way to know how long remaining work will actually take.

**The fix:** Store a `verified_at` ISO timestamp when each subtask transitions to `Verified`. Add a `velocity` calculation (subtasks verified per hour over the last 10 verifications) to `status` output and the `/status` API response. Display as: `ETA: ~2h 20min (4.3 subtasks/hr)`.

**Why it matters:** Solo devs make daily scope decisions — ship now vs. keep building. An ETA grounded in real velocity replaces gut feel with data.

---

## 3. Dashboard Live Control via File-Signal Bridge

**The gap:** The REST API has a `POST /tasks/<id>/trigger` endpoint that returns `202 Accepted` but does nothing — the CLI is a separate process with no IPC. The dashboard is read-only, polling is absent, and there's no live refresh.

**The fix:** Two parts:
- In `app.py`, make `POST /trigger` write a signal file (e.g., `state/trigger_<task_id>.signal`)  
- In `solo_builder_cli.py`, have the `auto` loop check for signal files at each step and inject a forced-run on the targeted task, then delete the file

Add `<meta http-equiv="refresh" content="5">` to `dashboard.html` for instant live polling with no dependencies.

**Why it matters:** The dashboard becomes an actual project HUD rather than a static report — you can kick off a stuck task from the browser without touching the terminal.


## A4 — Task 0 / Branch A

**Prompt:** What are 3 risks of building a self-healing agent system, and one mitigation for each?


## 3 Risks of Self-Healing Agent Systems

**1. Runaway Remediation Loops**
The agent's fix triggers a new failure, which triggers another fix, ad infinitum — consuming resources or corrupting state progressively.
- **Mitigation:** Implement a circuit breaker with a max-retry budget per time window. After N failed heal attempts, escalate to a human or halt rather than continuing.

**2. Incorrect Root Cause Attribution**
The agent diagnoses the wrong cause and "heals" by changing something unrelated, masking the real issue or introducing new bugs.
- **Mitigation:** Require the agent to emit a structured hypothesis with confidence score before acting. Low-confidence or low-specificity diagnoses get routed to human review rather than auto-remediation.

**3. Privilege Escalation / Blast Radius**
A self-healing agent needs enough permissions to fix things — but those same permissions can cause catastrophic damage if the agent acts on bad reasoning or is manipulated via prompt injection in logs/error messages.
- **Mitigation:** Apply least-privilege scoping per action type (e.g., the agent can restart a service but cannot modify IAM policies or delete data). Use a separate approval gate for any destructive action.


## A5 — Task 0 / Branch A

**Prompt:** Write a tagline for Solo Builder in under 10 words.


**Build solo. Ship fast. Think with AI.**


## B1 — Task 0 / Branch B

**Prompt:** Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.


A **Shadow Agent** runs silently in parallel with a primary agent, observing the same inputs and producing its own outputs for comparison or monitoring purposes — without affecting the live response.

A **Verifier Agent** actively evaluates another agent's output against defined criteria (correctness, safety, policy) and can block or flag the response before it reaches the user or downstream system.


## B2 — Task 0 / Branch B

**Prompt:** List 3 real-world use cases for a DAG-based AI project tracker.


## 3 Real-World Use Cases for a DAG-Based AI Project Tracker

**1. Solo SaaS Build Pipeline**
Track the dependency chain from idea → spec → backend → frontend → testing → deployment. A DAG ensures you can't mark "write API endpoints" complete until "design schema" is done — enforcing logical order and surfacing blockers automatically.

**2. Content Production Workflow**
A creator or agency managing blog posts, videos, or social campaigns. Each piece of content has upstream dependencies (research → outline → draft → edit → design → publish). The DAG prevents publishing before editing and highlights which tasks are on the critical path.

**3. AI Model Development Lifecycle**
Track tasks across data collection → preprocessing → feature engineering → model training → evaluation → deployment → monitoring. Each stage depends on the previous, and some branches (e.g., multiple model experiments) run in parallel — a perfect DAG structure that flat to-do lists can't represent.

---

The core value in all three: **DAGs make implicit dependencies explicit**, so you can see what's blocked, what's parallelizable, and what the critical path is — things a flat task list or kanban board can't show.


## B3 — Task 0 / Branch B

**Prompt:** In one sentence, explain what a MetaOptimizer does in an AI pipeline.


A MetaOptimizer is a higher-level optimization algorithm that tunes the hyperparameters or learning strategies of other optimizers, effectively "learning how to learn" to improve model training efficiency and performance.


## C1 — Task 1 / Branch C

**Prompt:** What does a DAG (Directed Acyclic Graph) represent in software project management? Answer in one paragraph.


In software project management, a Directed Acyclic Graph (DAG) represents the dependency relationships between tasks or components, where each node is a task and each directed edge indicates that one task must complete before another can begin. The "acyclic" constraint ensures there are no circular dependencies — no task can transitively depend on itself — which makes it possible to determine a valid execution order. DAGs are used in build systems (like Make, Bazel, or webpack), CI/CD pipelines, task schedulers, and package managers to resolve the correct sequence of operations: given a DAG, a topological sort produces one or more valid orderings that respect all dependencies. They also enable parallelism analysis — tasks with no dependency relationship between them can safely run concurrently — making DAGs a foundational data structure for optimizing build times and orchestrating complex workflows.


## C2 — Task 1 / Branch C

**Prompt:** List 3 advantages of using a priority queue to schedule software tasks.


1. **Efficient task ordering** — Tasks are always dequeued in priority order (O(log n) insertion/extraction), so high-priority work runs first without scanning the entire queue.

2. **Dynamic re-prioritization** — New urgent tasks inserted at runtime automatically surface ahead of lower-priority pending work, making the scheduler responsive to changing conditions.

3. **Prevents starvation with aging** — Priority queues can incorporate aging (gradually increasing priority of waiting tasks), ensuring low-priority tasks eventually run rather than being indefinitely blocked by higher-priority arrivals.


## C3 — Task 1 / Branch C

**Prompt:** Explain the concept of task staleness in a project management system in 2 sentences.


Task staleness refers to the condition where a task's information, priority, or relevance has become outdated relative to the current state of a project — often because time has passed, dependencies have changed, or the context in which it was created no longer exists. Stale tasks can mislead teams by cluttering backlogs with obsolete work, causing effort to be spent on things that no longer deliver value or that conflict with newer decisions.


## C4 — Task 1 / Branch C

**Prompt:** What is a shadow state in an agent-based system? Give one concrete example.


## Shadow State in Agent-Based Systems

**Shadow state** is a private, internal representation of the world that an agent maintains independently of the authoritative external state. The agent acts based on its shadow state rather than querying the ground truth on every decision, which can lead to the agent operating on stale or incorrect assumptions.

---

### Concrete Example

An AI coding agent is given the task: "Delete all `.tmp` files, then run the test suite."

1. The agent reads the directory and builds its shadow state: `[build.tmp, cache.tmp, session.tmp]`
2. It deletes `build.tmp` and `cache.tmp`
3. **Meanwhile**, another process creates `new_artifact.tmp` — but the agent's shadow state doesn't know this
4. The agent "knows" it has cleaned up all `.tmp` files (its shadow state says so) and proceeds to run tests
5. The test suite fails because `new_artifact.tmp` interferes — but the agent is confused because according to its shadow state, no `.tmp` files exist

The agent's internal model of the world diverged from reality. That divergence is the shadow state problem.

---

### Why It Matters

In multi-agent systems this compounds: Agent A's shadow state of what Agent B did may be wrong, leading to cascading incorrect decisions. Solutions include **explicit re-querying** (invalidate cached state before acting), **event-driven updates** (subscribe to change notifications), or **optimistic locking** (verify assumptions right before committing an action).


## D1 — Task 1 / Branch D

**Prompt:** Describe 2 strategies for preventing task starvation in a priority-based scheduler.


## Preventing Task Starvation in a Priority-Based Scheduler

### 1. Aging

Gradually increase the priority of a task the longer it waits in the ready queue.

- Each time a scheduling cycle passes without a task being selected, its effective priority is incremented by some delta.
- Eventually, even the lowest-priority task ages up to the point where it gets scheduled.
- After execution, its priority resets to the original value.

```
effective_priority = base_priority + (wait_time / aging_factor)
```

**Trade-off:** Requires tracking wait time per task and adds overhead to priority recalculation each cycle.

---

### 2. Priority Ceiling / Time-Slice Guarantee

Reserve a minimum time slice or scheduling slot for low-priority tasks regardless of higher-priority demand.

- The scheduler guarantees that every task at any priority level gets CPU time within a bounded window (e.g., at least once every N cycles).
- Often implemented as a **two-tier policy**: a high-priority queue runs normally, but a background queue is force-scheduled periodically.
- Similar to the **multi-level feedback queue (MLFQ)** approach where tasks that haven't run recently get a temporary boost into a higher queue.

```
if task.time_since_last_run > starvation_threshold:
    promote to higher queue temporarily
```

**Trade-off:** Harder to tune the threshold — too aggressive and high-priority tasks lose throughput; too lenient and starvation still occurs.

---

**Key difference:** Aging is *reactive* (priority grows over time), while the time-slice guarantee is *proactive* (a slot is reserved before starvation occurs).


## D2 — Task 1 / Branch D

**Prompt:** What is the difference between optimistic and pessimistic task verification? One paragraph.


**Optimistic task verification** assumes a task succeeded unless evidence indicates otherwise — it proceeds immediately after an action and only checks for errors reactively (e.g., catching exceptions). **Pessimistic task verification** assumes a task may have failed and actively confirms success before proceeding — it polls, retries, or waits for explicit confirmation signals (e.g., checking a database record was written before returning success). Optimistic verification is faster and simpler but risks silent failures or race conditions, while pessimistic verification is more robust and reliable but slower and more complex to implement.


## E1 — Task 2 / Branch E

**Prompt:** What are 3 benefits of self-healing automation in a software pipeline?


Three benefits of self-healing automation in a software pipeline:

1. **Reduced downtime** — Failed steps (flaky tests, transient network errors, resource exhaustion) are automatically retried or rerouted without human intervention, keeping the pipeline flowing.

2. **Lower operational burden** — Engineers aren't paged for recoverable failures. The system handles common failure modes (restarting stuck agents, re-provisioning failed nodes) autonomously, freeing the team for higher-value work.

3. **Faster mean time to recovery (MTTR)** — Automated remediation triggers in seconds, whereas human response can take minutes to hours. This compresses the feedback loop and keeps deployments on schedule.


## E2 — Task 2 / Branch E

**Prompt:** Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.


A MetaOptimizer learns from an agent's historical performance data to dynamically tune hyperparameters, prompt strategies, and tool-selection policies — adapting the agent's behavior without manual intervention. Over time, it identifies patterns in successes and failures, enabling the agent to route tasks more efficiently, reduce token waste, and improve output quality through continuous self-optimization loops.


## E3 — Task 2 / Branch E

**Prompt:** List 3 metrics that indicate an AI agent system is performing well.


Three key metrics for a well-performing AI agent system:

1. **Task Completion Rate** — The percentage of assigned tasks successfully completed without human intervention or retries. High completion rate indicates the agent can handle its intended workload reliably.

2. **Latency / Time-to-Result** — How quickly the agent completes tasks end-to-end. Low and consistent latency means the agent isn't getting stuck in loops, retrying excessively, or over-calling tools.

3. **Tool Call Accuracy / Grounding Rate** — The ratio of tool calls that return useful, expected results vs. failed, hallucinated, or redundant calls. High accuracy here means the agent is reasoning correctly about *when* and *how* to use its tools.


## E4 — Task 2 / Branch E

**Prompt:** What is the difference between reactive and proactive error handling in agent systems? One sentence each.


**Reactive** error handling detects and responds to failures *after* they occur (e.g., catching exceptions, retrying failed steps).

**Proactive** error handling anticipates and prevents failures *before* they occur (e.g., validating inputs, checking preconditions, setting resource limits).


## E5 — Task 2 / Branch E

**Prompt:** Give one example of a heuristic weight that a MetaOptimizer might adjust in a task planner.


A MetaOptimizer might adjust the **deadline urgency multiplier** — a weight that scales how much a task's priority score increases as its due date approaches.

For example:

```
priority_score = base_priority * (1 + urgency_weight * days_remaining⁻¹)
```

If `urgency_weight = 2.0`, tasks get a moderate priority boost as deadlines near. The MetaOptimizer could lower it to `0.5` if it observes that aggressive deadline-chasing causes too many context switches, or raise it to `5.0` if missed deadlines are frequent.


## F1 — Task 2 / Branch F

**Prompt:** What is the role of a Verifier agent in a multi-agent pipeline? 2 sentences.


A Verifier agent reviews the output of other agents in the pipeline to check for correctness, consistency, or adherence to specified constraints before passing results downstream. It acts as a quality gate, catching errors or hallucinations early to prevent flawed outputs from propagating through the system.


## F2 — Task 2 / Branch F

**Prompt:** Describe how memory snapshots help with debugging in an agent system. One paragraph.


Memory snapshots help debug agent systems by capturing the full state of an agent's working memory, context, and intermediate reasoning at specific points in time, allowing developers to replay or inspect exactly what the agent "knew" when it made a decision. Instead of relying solely on logs of actions taken, snapshots preserve the in-context data — tool call results, accumulated conversation history, variable bindings, and any retrieved knowledge — so you can pinpoint whether a failure stemmed from bad input data, a reasoning error, a tool returning unexpected output, or state corruption from a previous step. This is especially valuable in long multi-step pipelines where the root cause of a downstream failure may have originated several turns earlier; snapshots let you bisect the timeline, restore the agent to a known-good state, and re-run from that point with modified conditions rather than re-executing the entire expensive run from scratch.


## F3 — Task 2 / Branch F

**Prompt:** List 2 ways a ShadowAgent could detect state inconsistencies in a DAG pipeline.


Two ways a ShadowAgent could detect state inconsistencies in a DAG pipeline:

1. **Checksum/Hash Comparison at Node Boundaries**
   Each node emits a hash of its output state. The ShadowAgent independently recomputes expected hashes from upstream inputs and compares them at each edge. A mismatch signals that a node's output diverged from its deterministic expectation — catching silent data corruption or non-deterministic execution.

2. **Topological Invariant Auditing**
   The ShadowAgent tracks dependency ordering invariants (e.g., node B must always execute after node A completes with a valid state). It monitors execution timestamps and state tokens across the DAG and flags violations where a downstream node holds a stale or pre-update state version from an ancestor — catching race conditions or out-of-order execution bugs.


## F4 — Task 2 / Branch F

**Prompt:** What is the difference between a branch and a task in a DAG-based project tracker? One sentence.


A **branch** represents a parallel line of work (a divergent path in the DAG), while a **task** is an individual node in the graph with specific dependencies and outputs.


## G1 — Task 3 / Branch G

**Prompt:** What is continuous integration and how does it relate to automated project management? One paragraph.


Continuous integration (CI) is a software development practice where team members frequently merge code changes into a shared repository — typically multiple times per day — triggering automated pipelines that build, test, and validate the code on each commit. Tools like GitHub Actions, CircleCI, or Jenkins run these pipelines automatically, catching integration bugs early before they compound. In the context of automated project management, CI acts as the enforcement layer: it can automatically update issue trackers (closing tickets when tests pass), trigger deployment workflows, generate status reports, enforce code quality gates, and even notify stakeholders — all without human intervention. This closes the loop between writing code and managing the project lifecycle, turning what was once a manual, error-prone handoff process into a continuous, auditable feedback loop tied directly to the codebase.


## G2 — Task 3 / Branch G

**Prompt:** List 3 common causes of technical debt in solo developer projects.


1. **Skipping tests** — Solo devs often prioritize shipping over test coverage, making future changes risky and regressions hard to catch.

2. **Premature or absent abstractions** — Either over-engineering early (building for scale that never comes) or copy-pasting code repeatedly instead of extracting shared logic.

3. **Deferred dependency upgrades** — Staying on outdated libraries to avoid breakage, until the gap becomes too large to bridge without significant rework.


## G3 — Task 3 / Branch G

**Prompt:** Describe the MVP (Minimum Viable Product) concept in 2 sentences.


An MVP is the simplest version of a product that delivers core value to early users while requiring the least development effort. It exists to validate assumptions quickly, gather real feedback, and avoid building features nobody wants.


## G4 — Task 3 / Branch G

**Prompt:** What is a sprint in agile methodology? One sentence.


A sprint is a fixed-length iteration (typically 1–4 weeks) in which a team completes a defined set of work from the product backlog.


## G5 — Task 3 / Branch G

**Prompt:** List 3 developer tools a solo builder could use alongside an AI task manager.


Here are 3 developer tools that pair well with an AI task manager for solo builders:

1. **Linear** — Lightweight issue tracker with keyboard-first UX and automation hooks; integrates cleanly with AI-generated task lists via API.

2. **Cursor / Claude Code** — AI-native code editors that can act on task descriptions directly, closing the loop between planning and execution.

3. **Zapier / n8n** — Workflow automation to pipe task updates between your AI manager, GitHub, Slack, calendar, and other tools without custom glue code.


## G6 — Task 3 / Branch G

**Prompt:** What is the difference between async and sync task execution in pipelines? One paragraph.


In a pipeline, **synchronous (sync) execution** runs tasks sequentially — each task must complete before the next begins, blocking the thread until done, which is simple to reason about but can be slow when tasks involve waiting (I/O, network, disk). **Asynchronous (async) execution** allows tasks to be initiated without blocking — the pipeline can hand off a task, continue scheduling other work, and resume when the result is ready (via callbacks, promises, or `await`), enabling concurrency within a single thread. The key tradeoff is that sync is easier to debug and reason about (linear control flow, predictable errors), while async maximizes throughput by overlapping I/O-bound work, but introduces complexity around ordering, error propagation, and race conditions. In practice, pipelines with heavy I/O (API calls, file reads, database queries) benefit most from async, while CPU-bound transform steps often gain little from it.


## H1 — Task 3 / Branch H

**Prompt:** Describe the concept of a 'Definition of Done' in software projects. 2 sentences.


A **Definition of Done (DoD)** is a shared, explicit checklist of criteria that a feature or task must meet before it's considered complete — covering things like code review, tests passing, and documentation. It ensures the entire team has a common understanding of "done," preventing half-finished work from being declared complete prematurely.


## H2 — Task 3 / Branch H

**Prompt:** List 3 ways to reduce context-switching costs for a solo developer.


1. **Batch similar work into time blocks** — Group all code review, emails, and deploys into dedicated slots rather than interleaving them. Context has a "warm-up" cost; staying in one mode longer amortizes it.

2. **Write a daily "re-entry note" before stopping** — Leave a 3-5 line note at the top of your current file or task tracker: what you were doing, what's next, and any open questions. Eliminates the 10-15 min reconstruction cost when you return.

3. **Use a single canonical task list, not scattered notes** — One source of truth (a `TODO.md`, Linear board, or similar) means you spend zero time remembering *where* your tasks live. The less cognitive overhead to find "what's next," the faster you re-engage.


## H3 — Task 3 / Branch H

**Prompt:** What is the Pomodoro technique and how might it help a solo developer? One paragraph.


The Pomodoro technique is a time management method where you work in focused 25-minute intervals (called "pomodoros") separated by short 5-minute breaks, with a longer 15–30 minute break after every four cycles. For a solo developer, it's particularly useful because there's no external structure or manager to keep you on track — the technique provides that rhythm artificially. It combats the two failure modes solo work tends to produce: hyperfocus burnout (losing hours in a tunnel without rest) and constant context-switching (checking Slack, email, or social media). The forced breaks give your brain time to consolidate what you've built, and the defined work blocks make vague tasks feel concrete and time-boxed, which reduces the paralysis of staring at an empty file wondering where to start.


## H4 — Task 3 / Branch H

**Prompt:** Give 2 examples of how AI can assist with project estimation for a solo developer.


Here are 2 examples of how AI can assist with project estimation for a solo developer:

---

**1. Task Decomposition & Complexity Scoring**

A solo dev describes a feature in plain language (e.g., "add user authentication with OAuth"). AI breaks it down into granular subtasks, flags hidden complexity (token refresh, edge cases, testing), and assigns relative effort scores based on the tech stack — surfacing work the dev may have underestimated.

**2. Historical Pattern Matching**

AI analyzes past project notes, commit history, or journal entries to identify how long similar tasks *actually* took vs. how long they were estimated to take. It then applies a calibration factor to future estimates, reducing the optimism bias that solo devs commonly experience.

---

Both approaches shift estimation from gut-feel guessing to data-informed planning — especially valuable without a team to sanity-check scope.


## I1 — Task 3 / Branch I

**Prompt:** What is scope creep and how can a solo developer prevent it? One paragraph.


Scope creep is the gradual, unplanned expansion of a project's requirements beyond what was originally defined — features get added, goals shift, and "just one more thing" becomes the default mode until the project balloons in size, stalls, or never ships. For a solo developer, the best defenses are: write a short, explicit spec before coding (even a bullet list) and treat it as a contract with yourself; use a "not now" list to capture ideas without acting on them immediately; timebox work into fixed sprints with defined deliverables; and ruthlessly apply the question "does this help the user do the core thing?" before adding anything new. Shipping a focused v1 is always worth more than endlessly polishing a v0.


## I2 — Task 3 / Branch I

**Prompt:** List 3 warning signs that a solo software project is at risk of failure.


1. **Scope creep without shipping** — Constantly adding features before releasing anything. If the MVP keeps expanding, the project may never reach users.

2. **No external feedback loop** — Building in isolation with no users, testers, or peers reviewing the work. Without external signal, you can spend months solving the wrong problem.

3. **Motivation tied to novelty, not completion** — High energy at the start, but declining interest once the "fun" technical parts are done and the unglamorous work (testing, docs, deployment, support) begins.


## I3 — Task 3 / Branch I

**Prompt:** Describe the concept of 'bikeshedding' and why it's a risk for solo developers. 2 sentences.


Bikeshedding is the tendency to spend disproportionate time on trivial, easy-to-visualize decisions (like picking a color scheme or folder naming convention) while avoiding harder, more important work. For solo developers it's especially dangerous because there's no team to redirect focus — you can burn hours on inconsequential choices with no one to call you out.


## J1 — Task 4 / Branch J

**Prompt:** What are 3 principles of clean code that every solo developer should follow?


Three clean code principles every solo developer should follow:

1. **Obvious naming over clever naming** — Variables, functions, and files should say *what* they do, not *how*. `getUserById()` beats `fetch()`. You'll thank yourself six months later when you've forgotten the context.

2. **One thing, one place** — Each function does one thing; each piece of logic lives in one place. Duplication is the fastest way to create bugs that are hard to track down, especially when working alone with no one to catch inconsistencies.

3. **Delete dead code** — If it's commented out or unused, remove it. You have git for history. Dead code creates false signals about what the system actually does and slows down every future read of the file.

The common thread: you are your own future code reviewer. Write for that person.


## J2 — Task 4 / Branch J

**Prompt:** Describe the DRY (Don't Repeat Yourself) principle in one sentence with a concrete example.


DRY means every piece of knowledge should have a single authoritative definition — for example, instead of hardcoding a tax rate of `0.08` in five different functions, define `TAX_RATE = 0.08` once and reference that constant everywhere.


## J3 — Task 4 / Branch J

**Prompt:** What is a code smell? Give 3 examples.


A **code smell** is a surface-level pattern in code that suggests a deeper problem — not necessarily a bug, but a sign that the design could be improved.

---

## 3 Examples

**1. Long Method**
A function that does too much. If you need to scroll to read a single method, it's doing more than one thing and should be broken up.

```python
def process_order(order):
    # 200 lines of validation, pricing, tax, shipping, email...
```

**2. Duplicate Code**
The same logic copy-pasted in multiple places. If you fix a bug in one copy, you have to remember to fix all the others — and you will forget.

```js
// In UserCard.jsx
const name = user.firstName + ' ' + user.lastName;

// In ProfilePage.jsx
const name = user.firstName + ' ' + user.lastName;  // again
```

**3. God Object / God Class**
A single class that knows and does everything. It accumulates responsibilities over time until it's impossible to test or change without side effects.

```python
class App:
    def handle_login(self): ...
    def send_email(self): ...
    def render_dashboard(self): ...
    def calculate_taxes(self): ...
    def connect_to_db(self): ...
    # 3000 more lines
```

---

The term was popularized by Martin Fowler in *Refactoring* (1999). Smells don't demand immediate fixes, but they signal where technical debt is accumulating.


## J4 — Task 4 / Branch J

**Prompt:** Pick 3 of the SOLID principles and explain each in one bullet point.


- **S — Single Responsibility**: A class or module should have one reason to change — do one thing and own it completely.
- **O — Open/Closed**: Code should be open for extension but closed for modification — add new behavior by adding new code, not by editing existing code.
- **D — Dependency Inversion**: High-level modules shouldn't depend on low-level modules; both should depend on abstractions — program to interfaces, not implementations.


## J5 — Task 4 / Branch J

**Prompt:** What is test-driven development (TDD)? Describe it in 2 sentences.


Test-driven development (TDD) is a software development practice where you write failing tests *before* writing the implementation code, then write the minimum code needed to make those tests pass. The cycle repeats in short iterations — Red (write failing test) → Green (make it pass) → Refactor (clean up) — ensuring code is always covered by tests and designed to be testable from the start.


## J6 — Task 4 / Branch J

**Prompt:** List 3 benefits of writing unit tests for a solo developer project.


1. **Catch regressions instantly** — When you revisit code weeks later and make changes, tests immediately tell you if you broke something that previously worked.

2. **Confidence to refactor** — You can restructure or optimize code without fear, knowing the test suite will validate behavior is preserved.

3. **Acts as living documentation** — Tests show exactly how your code is supposed to be used and what edge cases matter, which is invaluable when your memory of the implementation fades.


## J7 — Task 4 / Branch J

**Prompt:** What is a linter and why should solo developers use one? One paragraph.


A **linter** is a static analysis tool that scans your code for potential errors, style inconsistencies, and anti-patterns without actually running it — catching things like undefined variables, unused imports, unreachable code, or formatting that deviates from a chosen style guide. For solo developers, linters are especially valuable because there's no teammate to catch mistakes in code review: the linter acts as a tireless second pair of eyes, enforcing consistent conventions across your codebase even as it grows over months or years, reducing cognitive overhead when you return to old code, and catching bugs earlier (at write-time rather than runtime), which is far cheaper to fix. Tools like ESLint for JavaScript, Pylint/Ruff for Python, or Biome for TypeScript integrate directly into your editor and CI pipeline, making quality enforcement essentially free once configured.


## J8 — Task 4 / Branch J

**Prompt:** Describe the difference between unit tests and integration tests in one sentence each.


**Unit tests** verify individual functions or components in isolation, with dependencies mocked or stubbed out.

**Integration tests** verify that multiple components work correctly together, using real dependencies and testing the interactions between them.


## K1 — Task 4 / Branch K

**Prompt:** What is semantic versioning (semver)? Give one example of a version bump and why.


**Semantic versioning (semver)** is a versioning scheme with the format `MAJOR.MINOR.PATCH`:

- **MAJOR** — breaking change (incompatible API change)
- **MINOR** — new feature, backwards-compatible
- **PATCH** — bug fix, backwards-compatible

**Example:**

`1.4.2` → `1.5.0`

A new optional `--verbose` flag was added to a CLI tool. Existing usage still works, so it's a backwards-compatible feature addition — bump MINOR, reset PATCH to 0.


## K2 — Task 4 / Branch K

**Prompt:** List 3 best practices for writing clear git commit messages.


1. **Use the imperative mood in the subject line** — Write "Add login feature" not "Added login feature" or "Adding login feature". Git itself uses this convention (e.g., "Merge branch...").

2. **Keep the subject line under 50 characters** — A concise subject fits in `git log --oneline` without truncation. If more detail is needed, add a blank line after the subject followed by a body paragraph explaining *why*, not *what*.

3. **Reference the "why", not just the "what"** — The diff already shows *what* changed. A good commit message explains the reason or context: "Fix race condition in auth middleware causing intermittent 401s" beats "Fix bug".


## K3 — Task 4 / Branch K

**Prompt:** What is a pull request and how does it help with code quality? One paragraph.


A pull request (PR) is a mechanism in version control platforms like GitHub where a developer proposes merging changes from one branch into another, typically from a feature branch into the main branch. It helps with code quality by creating a structured review process: before code lands in the main codebase, teammates can examine the diff, leave inline comments, ask questions, catch bugs, and request changes. This peer review layer acts as a quality gate, enforcing coding standards, sharing knowledge across the team, and preventing regressions — all before the code affects production.


## K4 — Task 4 / Branch K

**Prompt:** Describe the concept of self-code-review for a solo developer. 2 sentences.


Self-code-review is the practice of a solo developer critically examining their own code after a short time gap — treating themselves as a skeptical reviewer rather than the original author. It surfaces bugs, unclear logic, and over-engineering that are invisible in the flow state of writing.


## K5 — Task 4 / Branch K

**Prompt:** What is continuous deployment and how does it benefit a solo developer project? 2 sentences.


Continuous deployment (CD) automatically releases every code change that passes tests directly to production, eliminating manual deployment steps. For a solo developer, this means faster iteration, reduced deployment friction, and more time focused on building features rather than managing releases.


## L1 — Task 5 / Branch L

**Prompt:** What are 3 key metrics a solo developer should track for a CLI tool project?


For a CLI tool project, the 3 most valuable metrics to track are:

1. **Adoption / Install rate** — how many unique installs or downloads per week. This tells you if discovery and onboarding are working. Track via npm downloads, pip stats, or a lightweight telemetry ping.

2. **Command usage frequency** — which commands/flags are actually used. Helps you prioritize features and deprecate dead code. A simple local log file or opt-in analytics (e.g., PostHog) works well.

3. **Error rate by command** — how often commands fail and with what exit codes. High error rates on a specific command signal UX problems or edge cases you haven't handled. Achievable with structured logging + periodic review.

These three give you a feedback loop: people find it → they use it → they succeed (or don't).


## L2 — Task 5 / Branch L

**Prompt:** Describe the concept of a project roadmap in 2 sentences.


A project roadmap is a high-level visual or written plan that outlines the goals, milestones, and timeline for a project from its current state to completion. It communicates strategic direction and priorities to stakeholders, helping teams stay aligned on what needs to be built, in what order, and by when.


## L3 — Task 5 / Branch L

**Prompt:** List 3 ways to gather user feedback on a solo developer CLI tool.


1. **GitHub Issues** — Add a `--feedback` flag or link in your CLI output that opens a pre-filled GitHub issue template. Low friction for developers already on GitHub.

2. **In-tool prompt** — After N uses or on exit, print a one-line prompt: `"Found a bug or have a suggestion? → https://..."`  Track opt-outs in a local config file to avoid spamming.

3. **Anonymous telemetry** — Log command usage/errors to a lightweight endpoint (e.g., a free Plausible instance or simple HTTP POST). Always opt-in with explicit consent on first run, and document it clearly in the README.


## L4 — Task 5 / Branch L

**Prompt:** What is feature prioritization and why is it important for solo developers? One paragraph.


Feature prioritization is the process of ranking and ordering product features or tasks by their relative value, impact, and urgency so that limited time and resources are directed toward the highest-leverage work first. For solo developers, it's especially critical because there's no team to parallelize work, no manager to absorb poor planning decisions, and no buffer for wasted effort — every hour spent on a low-value feature is an hour not spent on something that could move the needle. Without a prioritization framework (like RICE, MoSCoW, or simple impact-vs-effort scoring), solo builders tend to work on what's interesting rather than what's important, fall into endless polish cycles on features users don't care about, and ship products that feel incomplete in the areas that matter most. Good prioritization forces brutal honesty about what actually needs to exist for the product to succeed versus what would merely be nice to have.


## L5 — Task 5 / Branch L

**Prompt:** Describe 2 ways AI can help a solo developer with project documentation.


## 2 Ways AI Can Help a Solo Developer with Project Documentation

**1. Auto-generating docs from code**
AI can read your source code — functions, classes, API routes — and produce accurate README sections, API references, or inline docstrings. Instead of manually writing what a function does, you describe your intent and the AI drafts documentation that matches the actual implementation. This keeps docs in sync with code without the maintenance burden.

**2. Maintaining a living knowledge base**
As a solo dev, context lives entirely in your head. AI can act as a documentation co-pilot: summarizing decisions from your commit history, turning Slack/Discord notes into structured ADRs (Architecture Decision Records), or updating a `journal.md` as features ship. This offloads the cognitive overhead of "writing it down" so future-you (or an onboarding collaborator) has context without digging through git logs.


## L6 — Task 5 / Branch L

**Prompt:** What is a changelog and why should every project have one? One sentence.


A changelog is a file that records all notable changes made to a project over time, so users and contributors can quickly understand what changed, when, and why between versions.


## M1 — Task 5 / Branch M

**Prompt:** List 3 strategies for getting early users for a solo developer tool.


1. **Post in developer communities** — Share in relevant subreddits (r/programming, r/webdev, r/SideProject), Hacker News (Show HN), and niche Discord servers. Lead with the problem you solve, not the product.

2. **Build in public** — Tweet/post progress updates with screenshots and metrics. Developers follow builders. This compounds over time and attracts early adopters who want to give feedback.

3. **Find watering holes** — Go where your target users already hang out (GitHub discussions, Stack Overflow, specific Slack workspaces, forum threads about the problem your tool solves) and engage genuinely before mentioning your tool.


## M2 — Task 5 / Branch M

**Prompt:** What is developer experience (DX) and why does it matter? One paragraph.


Developer experience (DX) refers to the overall quality of a developer's interactions with tools, APIs, SDKs, documentation, workflows, and processes while building software. It's the developer-facing analog to user experience (UX) — encompassing how intuitive an API is to use, how fast a build system runs, how clear error messages are, how easily a local environment can be set up, and how well documentation answers real questions. DX matters because friction compounds: a confusing API causes bugs, a slow CI pipeline kills momentum, and poor docs force developers to reverse-engineer intent — all of which drain productivity, increase onboarding time, and raise the likelihood of misuse or abandonment. Great DX reduces cognitive load, accelerates iteration, and directly improves the quality and reliability of what developers ship.


## M3 — Task 5 / Branch M

**Prompt:** Describe 2 ways to measure whether a solo developer project is succeeding.


Two ways to measure whether a solo developer project is succeeding:

1. **User engagement / retention** — Are real users returning? Metrics like DAU/MAU ratio, session length, or repeat purchases tell you whether the product solves a genuine problem. A growing or stable retention rate beats vanity metrics like total signups.

2. **Revenue vs. time invested** — Track effective hourly rate (revenue ÷ hours worked). For a solo builder, this is the clearest signal of sustainability. Consistent month-over-month growth in this ratio means the project is compounding, not just treading water.


## M4 — Task 5 / Branch M

**Prompt:** What is open source and what are 2 benefits of open-sourcing a solo developer project?


## What is Open Source?

**Open source** means making your project's source code publicly available for anyone to view, use, modify, and distribute. It's governed by a license (e.g., MIT, Apache, GPL) that defines what others can and can't do with it.

---

## 2 Benefits for a Solo Developer

**1. Credibility & Portfolio Signal**
Public repos act as a live portfolio. Recruiters, clients, and collaborators can inspect your actual code quality — far more convincing than a resume bullet point. Stars and forks are social proof of usefulness.

**2. Free Bug Reports & Contributions**
Other developers will use your project in ways you never anticipated, surfacing edge cases and bugs you'd never find alone. Some will even submit fixes, saving you time you don't have as a solo dev.


## N1 — Task 5 / Branch N

**Prompt:** What are 3 signs that a software project is ready for its first public release?


Three signs a software project is ready for its first public release:

1. **Core features work reliably end-to-end** — The primary use cases complete without crashes or data loss. Edge cases may exist, but the happy path is stable and tested.

2. **You can onboard a stranger without hand-holding** — Documentation, setup instructions, and error messages are clear enough that someone unfamiliar with the codebase can install and use it successfully.

3. **You have a feedback and bug-triage path** — An issue tracker, contact method, or support channel exists so users can report problems and you can respond. Shipping without this means problems disappear into the void.


## N2 — Task 5 / Branch N

**Prompt:** Describe the concept of a 'soft launch' for a developer tool. 2 sentences.


A soft launch is a limited, quiet release of a developer tool to a small group of early users — without broad marketing — to gather real-world feedback and catch issues before the full public release. It lets you validate assumptions, fix rough edges, and build initial social proof while maintaining the ability to pivot quickly with minimal reputational risk.


## N3 — Task 5 / Branch N

**Prompt:** List 3 things a developer should document before releasing an open-source project.


1. **README** — Setup instructions, usage examples, and what the project does and why.
2. **Contributing guidelines** — How to report bugs, submit PRs, code style expectations, and the review process.
3. **License** — The terms under which others can use, modify, and distribute the code.


## N4 — Task 5 / Branch N

**Prompt:** What is a README file and what are its 3 most important sections? One sentence each.


A **README** is a text file (typically Markdown) that introduces and documents a project for anyone who encounters the repository.

**3 most important sections:**

1. **Project Description** — Explains what the project does and why it exists, giving readers immediate context on its purpose.
2. **Installation/Setup** — Provides the exact steps needed to get the project running on a local machine.
3. **Usage** — Shows how to actually use the project, typically with commands or code examples.


## N5 — Task 5 / Branch N

**Prompt:** Write a one-sentence mission statement for Solo Builder — an AI-powered CLI that manages DAG-based tasks for solo developers.


Solo Builder empowers solo developers to ship faster by orchestrating complex, dependency-aware workflows through an AI-driven CLI that thinks, plans, and executes tasks so you can focus on building.


## O1 — Task 6 / Branch O

**Prompt:** Summarize in 3 bullet points how DAG-based task management (like Solo Builder) improves over a simple to-do list for a solo developer.


- **Dependency awareness**: A DAG enforces task ordering by modeling which tasks block others, so you never start work that depends on incomplete prerequisites — unlike a flat list where ordering is manual and error-prone.

- **Parallel execution visibility**: The graph structure makes it immediately clear which tasks have no blockers and can run concurrently, letting a solo dev maximize throughput instead of working sequentially by default.

- **Cascading impact analysis**: When a task changes (delayed, skipped, re-scoped), a DAG automatically surfaces downstream effects — a flat to-do list requires you to mentally trace dependencies yourself, which breaks down as project complexity grows.


## O2 — Task 6 / Branch O

**Prompt:** Describe how self-healing agents reduce manual intervention in a software project pipeline. One paragraph.


Self-healing agents reduce manual intervention by continuously monitoring pipeline health and autonomously detecting, diagnosing, and remediating failures without human involvement. When a build breaks, a service crashes, or a test suite regresses, the agent intercepts the failure signal, queries relevant logs and metrics, identifies the root cause, and applies a targeted fix — whether that means retrying a flaky network call with backoff, reverting a bad dependency bump, restarting a crashed process, or patching a configuration drift. Because the agent encodes institutional knowledge about common failure modes, it can resolve the majority of routine incidents (failed deployments, environment mismatches, resource exhaustion, stale credentials) faster than a human on-call engineer could even acknowledge the alert, dramatically shrinking mean time to recovery. Engineers are only paged for novel or high-blast-radius failures that fall outside the agent's known remediation playbooks, shifting their attention from repetitive firefighting to higher-leverage work like designing new features or improving the agent's own failure taxonomy.


## O3 — Task 6 / Branch O

**Prompt:** Write a 3-sentence executive summary of Solo Builder for a developer audience.


Solo Builder is a Python terminal CLI that orchestrates a six-agent pipeline (Planner, Executor, Verifier, SelfHealer, ShadowAgent, MetaOptimizer) over a DAG-based task graph, enabling a solo developer to run dependency-aware, multi-branch workflows concurrently via `ThreadPoolExecutor` — with real subtasks executed headlessly through `claude -p`. State is persisted as versioned JSON, all Claude outputs are logged to an append-only `journal.md`, and the system self-corrects via stall detection and adaptive weight tuning — no external orchestration framework required. It's a lightweight, self-contained alternative to tools like Temporal or Prefect, purpose-built for one developer operating with the leverage of a coordinated AI agent team.


## P1 — Task 6 / Branch P

**Prompt:** What would a 'v2.0' of Solo Builder look like? List 3 major new features with one sentence each.


Based on the current architecture — a six-agent DAG pipeline with CLI-only interface and simulated execution — here are three v2.0 features:

1. **Real Code Execution Engine** — Replace the probability-based subtask simulation with an actual sandboxed execution layer (Docker or subprocess) so Claude-generated code is run, tested, and verified against real pass/fail output rather than random rolls.

2. **Natural Language DAG Builder** — Let users describe an entire project in plain English (e.g., "Build a SaaS billing page") and have the Planner auto-decompose it into a full multi-branch dependency graph, eliminating the need to manually wire tasks with `depends` commands.

3. **Persistent Agent Memory & Learning** — Give each agent (especially MetaOptimizer) cross-session memory so the system learns which task types stall most, which healing strategies work, and continuously tunes its own weights across projects — not just within a single run.


## P2 — Task 6 / Branch P

**Prompt:** How would you adapt Solo Builder for a team of 3-5 developers instead of a solo developer? Give 3 key changes.


---

## 1. Adapting Solo Builder for a Team of 3–5

**1. Replace single-owner state with shared, conflict-safe state**
The current `solo_builder_state.json` is a flat file owned by one process. For a team, migrate to a backend store (SQLite or Postgres) with row-level locking. Each developer claims subtasks via an atomic `status: InProgress (owner: dev@)` field, preventing double-assignment.

**2. Add a role/assignment layer to the DAG**
Branches and subtasks need an `assigned_to` field and optional skill tags (e.g., `frontend`, `infra`). The orchestrator routes tasks based on declared expertise rather than blindly queuing the next available item. A simple YAML roster file maps team members to tags.

**3. Introduce a PR/review gate between "Done" and "Verified"**
Solo Builder auto-advances `Done → Verified`. In a team context, insert a `PeerReview` status — another developer (or Claude acting as reviewer) must approve before the DAG advances. This preserves the self-healing audit trail while enforcing team quality gates.

---

## 2. State File Summary (`solo_builder_state.json`)

- **Tasks completed:** 68 of 70 subtasks are `Verified` or `Done` — the agent is at **step 70** with 2 subtasks still in-flight and zero self-heals triggered.
- **Most subtasks:** `Task 4 / Branch J` has the most work, with **8 subtasks** — the largest single branch in the DAG.
- **Notable Claude output** (from `Task 0 / Branch A / A1`): A clean five-bullet feature list for the tool itself — *task breakdown & prioritization, context persistence, blocker detection, scope management, progress summarization* — demonstrating the agent describing its own purpose from first principles.

---

## 3. Haikus

**On a self-healing AI agent:**

```
Broken node detected —
the graph rewrites its own path.
No human awake.
```

**On a DAG reaching 100% completion:**

```
Last edge turns to green.
The whole graph exhales at once —
nothing left to do.
```


## P3 — Task 6 / Branch P

**Prompt:** Write a haiku about software agents managing project tasks autonomously.


Here are all three deliverables:

---

**Haiku 1 — Agents managing tasks autonomously:**

```
Silent threads align
Each agent claims its next task
No manager waits
```

---

**State file summary — `state/solo_builder_state.json`:**

- **74 of 77 items verified** (tasks + subtasks) — the DAG is nearly fully complete, with only 3 items not yet in "Verified" state
- **Task 4 / Branch J had the most subtasks** — 8 subtasks, the heaviest branch in the entire graph
- **Notable Claude output (Task 0 / Branch A / A1):** A clean 5-point feature list for a solo dev AI tool — including "blocker detection," "scope management," and "progress summarization" — showing the agent was used to define Solo Builder's own requirements from day one

---

**Haiku 2 — Self-healing AI agent monitoring its own task graph:**

```
A node goes dark — cold
The agent reroutes itself
No panic. Just work.
```

**Haiku 3 — DAG reaches 100% completion:**

```
Last edge resolves
The graph exhales — nothing left
Done means nothing waits
```

