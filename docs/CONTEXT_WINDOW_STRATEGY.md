# Context Window Management Strategy
**TASK-316 | Audit refs: AI-008 to AI-013**
Last updated: 2026-03-10

---

## Purpose

This document defines how Solo Builder manages context window growth for
Claude Code sessions. Without a strategy, `CLAUDE.md` and related files
grow unboundedly, consuming context on every session start and eventually
causing silent truncation or degraded performance.

---

## Context Sources

Claude Code loads context at session start from:

| Source | Typical size | Growth pattern |
|---|---|---|
| `~/.claude/CLAUDE.md` (global) | ~2 KB | Stable — updated manually |
| `CLAUDE.md` (project) | ~1 KB | Stable — updated manually |
| `memory/MEMORY.md` | ~4 KB | **Grows** — auto-updated each session |
| `memory/*.md` topic files | ~2–8 KB each | **Grows** — append-heavy |
| `claude/JOURNAL.md` | ~20–200+ KB | **Grows rapidly** — execution log |
| `claude/STATE.json` | ~5 KB | Bounded — current state only |
| System reminder injections | ~1–2 KB | Stable |

The primary growth risk is `JOURNAL.md` and `memory/MEMORY.md`.

---

## Compaction Triggers

The following conditions should trigger a compaction action:

| Trigger | Condition | Action |
|---|---|---|
| MEMORY.md line count | > 200 lines | Archive oldest entries to `memory/archive/YYYY-MM.md` |
| JOURNAL.md file size | > 100 KB | Archive entries older than 30 days to `claude/journal_archive/` |
| Session context usage | > 70% (Claude Code `/context` indicator) | Run `/compact` before next tool call |
| Session context usage | > 85% | Run `/clear` and start fresh session |
| Topic file size | Any topic file > 10 KB | Split into subtopics |

---

## MEMORY.md Discipline

`memory/MEMORY.md` is loaded into every session context automatically (lines
1–200 only; content after line 200 is truncated). Rules:

1. **Hard limit: 200 lines.** Entries beyond line 200 are invisible to the model.
2. **No duplication.** Before writing a new memory, check existing entries.
3. **Link, don't embed.** For detailed notes, link to a topic file in `memory/`.
4. **Prune stale entries.** When a fact is superseded, update or delete the old entry.
5. **No session-specific context.** Only stable cross-session facts belong here.

---

## JOURNAL.md Archival

`claude/JOURNAL.md` is a running execution log. It is not loaded automatically
but may be read by agents during task execution. Rules:

1. Entries older than 30 days may be archived without information loss.
2. Archive location: `claude/journal_archive/YYYY-MM.md` (one file per month).
3. Archive trigger: file size exceeds 100 KB.
4. The current `JOURNAL.md` retains only the last 30 days at any time.
5. A summary entry is written at the top of each archive file.

**Archive script** (to be created — tracked under AI-009):
```bash
# Conceptual — not yet implemented
python tools/archive_journal.py --older-than 30d
```

---

## CLAUDE.md Growth Control

Project-level `CLAUDE.md` currently contains only the workflow contract
(four commands + five references). It must not become a catch-all for
project state or operational notes.

**Rules:**
- Max 50 lines in project `CLAUDE.md`
- Operational notes → `memory/MEMORY.md` or topic files
- Design decisions → `docs/*.md`
- Temporary state → `claude/STATE.json`

---

## Compaction Procedure (manual, per session)

When session context reaches 70%+:

1. Run `/compact` — Claude Code summarises the conversation and clears prior
   messages, retaining a compressed summary.
2. Continue with reduced context usage.

When session context reaches 85%+:

1. Save any in-progress work notes to `memory/MEMORY.md` or a topic file.
2. Run `/clear` — full context reset.
3. Start next session; loaded files provide continuity.

---

## Automated Monitoring (future)

The following monitoring improvements are tracked but not yet implemented:

| Gap ID | Description | Status |
|---|---|---|
| AI-008 | No context window size monitoring | **Resolved — TASK-332** (`tools/context_window_check.py`) |
| AI-009 | No journal archival script | **Resolved — TASK-333** (`tools/archive_journal.py`) |
| AI-010 | No MEMORY.md line-count enforcement | **Resolved — TASK-332** (`tools/context_window_check.py`) |
| AI-011 | No CLAUDE.md size lint rule | **Resolved — TASK-332** (`tools/context_window_check.py`) |
| AI-012 | No compaction trigger in pre-commit hook | Open |
| AI-013 | No session context usage tracking | Open |

---

## Resolved by This Document

| Gap ID | Description | Status |
|---|---|---|
| AI-008 to AI-013 (strategy) | No context window management strategy | **Resolved by TASK-316** |

The strategy is defined. Automated enforcement tools are follow-on tasks.

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-10 | Initial strategy document (TASK-316). Compaction triggers, MEMORY.md discipline, JOURNAL.md archival rules defined. AI-008 to AI-013 strategy resolved. |
| 2026-03-10 | AI-008 resolved: `tools/context_window_check.py` (TASK-332) — warns at 150 lines, errors at 200; JOURNAL.md override 500/1000. AI-009 resolved: `tools/archive_journal.py` (TASK-333) — archives entries >30 days to `claude/journal_archive/YYYY-MM.md`. Both added to VERIFY.json. |
| 2026-03-10 | AI-010 and AI-011 resolved: same `tools/context_window_check.py` (TASK-332) already checks MEMORY.md and CLAUDE.md at 150/200 line thresholds. No additional tools required. |
