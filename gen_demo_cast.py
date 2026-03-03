#!/usr/bin/env python3
"""Generates a synthetic asciinema v2 cast for the main Solo Builder demo (v2.1)."""
import json

G  = "\033[92m"   # green  (Verified)
M  = "\033[95m"   # magenta (Review)
Y  = "\033[93m"   # yellow  (Running / pending)
C  = "\033[96m"   # cyan
BL = "\033[34m"   # blue    (SDK executing)
B  = "\033[1m"    # bold
D  = "\033[2m"    # dim
R  = "\033[0m"    # reset

events = []
t = 0.0


def out(text, dt=0.08):
    global t
    t += dt
    events.append([round(t, 3), "o", text])


def type_chars(text, dt=0.065):
    global t
    for ch in text:
        t += dt
        events.append([round(t, 3), "o", ch])


header = {
    "version": 2, "width": 80, "height": 30,
    "timestamp": 1709500000,
    "title": "Solo Builder v2.1 — AI-agent DAG pipeline demo",
    "idle_time_limit": 2.0,
}

# ── Scene 1: mid-run status display ───────────────────────────────────────────
out(f"\r\n  {B}{C}SOLO BUILDER v2.1{R}  │  Step: 20  │  ETA: ~14 steps  ({G}50% done{R})\r\n", 0.3)
out(f"\r\n", 0.1)
out(f"  {G}▶ Task 0{R}  [{G}Verified{R}]\r\n", 0.07)
out(f"    {C}├─ Branch A{R} [{G}Verified{R}]  {G}████████████████████{R}  5/5\r\n", 0.07)
out(f"    {C}└─ Branch B{R} [{G}Verified{R}]  {G}████████████████████{R}  3/3\r\n", 0.07)
out(f"\r\n", 0.07)
out(f"  {G}▶ Task 1{R}  [{G}Verified{R}]\r\n", 0.07)
out(f"\r\n", 0.07)
out(f"  {Y}▶ Task 2{R}  [{Y}Running{R}]\r\n", 0.07)
out(f"    {C}├─ Branch E{R} [{M}Review{R}]    {D}░░░░░░░░░░░░░░░░░░░░{R}  0/5  {D}← awaiting verify{R}\r\n", 0.07)
out(f"    {C}└─ Branch F{R} [{Y}Running{R}]   {G}████████{R}{D}░░░░░░░░░░░░{R}  2/4\r\n", 0.07)
out(f"\r\n", 0.07)
out(f"  {D}▶ Tasks 3-6  [Pending]{R}\r\n", 0.07)
out(f"\r\n", 0.07)
out(f"  Overall [{G}══════════{R}░░░░░░░░░░] {G}35✓{R} {M}2⏸{R} {Y}4▶{R} {D}29●{R} / 70  ({G}50.0%{R})\r\n", 0.1)
out(f"\r\n", 0.5)

# ── Scene 2: `auto 3` — three steps with SDK executing in blue ─────────────────
out(f"{C}{B}solo-builder >{R} ", 0.3)
type_chars("auto 3")
out(f"\r\n", 0.3)
out(f"  {D}Running 3 steps automatically…{R}\r\n", 0.1)
out(f"\r\n", 0.2)

# Step 21
out(f"  {D}Step 21 — advancing up to 6 subtasks…{R}\r\n", 0.15)
out(f"  {BL}SDK executing E1, E2, E3, F3, F4…{R}\r\n", 0.2)
out(f"  {G}Verified:{R} F3, F4\r\n", 0.15)
out(f"  {M}Review:{R}   E1, E2, E3  {D}(REVIEW_MODE gate){R}\r\n", 0.15)
out(f"  {D}Step 21 — {G}35✓{R} {M}5⏸{R} {Y}1▶{R} {D}29●{R} / 70{R}\r\n", 0.2)
out(f"\r\n", 0.3)

# Step 22
out(f"  {D}Step 22 — advancing up to 6 subtasks…{R}\r\n", 0.15)
out(f"  {BL}SDK executing E4, E5, F5, C1, C2, C3…{R}\r\n", 0.2)
out(f"  {G}Verified:{R} F5, C1, C2, C3\r\n", 0.15)
out(f"  {M}Review:{R}   E4, E5  {D}(REVIEW_MODE gate){R}\r\n", 0.15)
out(f"  {D}Step 22 — {G}39✓{R} {M}7⏸{R} {Y}0▶{R} {D}24●{R} / 70{R}\r\n", 0.2)
out(f"\r\n", 0.3)

# Step 23
out(f"  {D}Step 23 — advancing up to 6 subtasks…{R}\r\n", 0.15)
out(f"  {BL}SDK executing D1, D2, D3…{R}\r\n", 0.2)
out(f"  {G}Verified:{R} D1, D2, D3\r\n", 0.15)
out(f"  {D}Step 23 — {G}42✓{R} {M}7⏸{R} {Y}0▶{R} {D}21●{R} / 70{R}\r\n", 0.2)
out(f"\r\n", 0.4)

out(f"  {D}Auto-run complete (3/3 steps).{R}\r\n", 0.1)
out(f"\r\n", 0.5)

# ── Scene 3: verify a Review-gated subtask ────────────────────────────────────
out(f"{C}{B}solo-builder >{R} ", 0.3)
type_chars("verify E1 output looks correct")
out(f"\r\n", 0.3)
out(f"  {G}✓ E1 (Task 2) verified (was Review). Note: output looks correct{R}\r\n", 0.15)
out(f"\r\n", 0.4)

out(f"{C}{B}solo-builder >{R} ", 0.2)
type_chars("verify E2 logic checked, LGTM")
out(f"\r\n", 0.3)
out(f"  {G}✓ E2 (Task 2) verified (was Review). Note: logic checked, LGTM{R}\r\n", 0.15)
out(f"\r\n", 0.5)

# ── Scene 4: updated status + export ─────────────────────────────────────────
out(f"  {Y}▶ Task 2{R}  [{Y}Running{R}]\r\n", 0.07)
out(f"    {C}├─ Branch E{R} [{Y}Running{R}]   {G}████████{R}{D}░░░░░░░░░░░░{R}  2/5\r\n", 0.07)
out(f"    {C}└─ Branch F{R} [{G}Verified{R}]  {G}████████████████████{R}  4/4\r\n", 0.07)
out(f"\r\n", 0.1)
out(f"  Overall [{G}══════════════{R}░░░░░░░░] {G}44✓{R} {M}5⏸{R} {Y}2▶{R} {D}19●{R} / 70  ({G}62.9%{R})\r\n", 0.1)
out(f"\r\n", 0.5)

out(f"{C}{B}solo-builder >{R} ", 0.3)
type_chars("export")
out(f"\r\n", 0.3)
out(f"  {G}Exported 44 outputs → solo_builder_outputs.md{R}\r\n", 0.15)
out(f"\r\n", 1.5)

out(f"{C}{B}solo-builder >{R} ", 0.1)

print(json.dumps(header))
for e in events:
    print(json.dumps(e))
