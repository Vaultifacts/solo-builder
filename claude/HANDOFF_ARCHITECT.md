# HANDOFF TO ARCHITECT (from RESEARCH)

## Task
TASK-026

## Finding
Five agent classes in solo_builder_cli.py are self-contained and can be
extracted cleanly: Planner, ShadowAgent, Verifier, SelfHealer, MetaOptimizer.
None of them access SoloBuilderCLI.self — they take DAG dicts and primitives.

External dependencies per class:
- Planner:       typing only
- ShadowAgent:   add_memory_snapshot (utils)
- Verifier:      typing only
- SelfHealer:    add_memory_snapshot + CYAN/RESET/ALERT_PREDICTIVE (utils) + logger
- MetaOptimizer: GREEN/RESET (utils) + Planner type reference

Import path: solo_builder/ is already in sys.path via _HERE setup in CLI.
Both solo_builder/__init__.py and utils/__init__.py exist — proper packages.

## Plan
1. Create solo_builder/agents/ package with __init__.py
2. One file per agent: planner.py, shadow_agent.py, verifier.py,
   self_healer.py, meta_optimizer.py
3. Each file imports what it needs from utils.helper_functions and logging
4. meta_optimizer.py imports Planner from .planner (relative import within package)
5. agents/__init__.py re-exports all five classes
6. solo_builder_cli.py: replace class bodies with `from agents import ...`

## Scope
- solo_builder/agents/__init__.py (new)
- solo_builder/agents/planner.py (new)
- solo_builder/agents/shadow_agent.py (new)
- solo_builder/agents/verifier.py (new)
- solo_builder/agents/self_healer.py (new)
- solo_builder/agents/meta_optimizer.py (new)
- solo_builder/solo_builder_cli.py (modified: remove 5 class bodies, add import)
