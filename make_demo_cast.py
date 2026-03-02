"""
Generate a synthetic asciinema v2 cast file for the Solo Builder v2.0 demo.
Run:  python make_demo_cast.py > demo.cast
Then: ./agg.exe demo.cast demo.gif --cols 100 --rows 35 --speed 1.5
"""
import json

W, H = 100, 35

def cast(events: list) -> None:
    header = {"version": 2, "width": W, "height": H,
              "timestamp": 1740800000, "title": "Solo Builder v2.0 — AI Agent CLI"}
    print(json.dumps(header))
    t = 0.0
    for delay, text in events:
        t += delay
        print(json.dumps([round(t, 3), "o", text]))

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
MAGENTA = "\033[95m"
BLUE    = "\033[34m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"
CLR     = "\033[2J\033[H"

SEP  = "═" * 72
SEP2 = "─" * 72

def _type(chars, base=0.07):
    return [(base + (i % 3) * 0.01, c) for i, c in enumerate(chars)]

events = [
    # ── Splash ──────────────────────────────────────────────────────────────
    (0.1,  f"\r\n{BOLD}{CYAN}"),
    (0.05, f"  ╔══════════════════════════════════════════════════════╗\r\n"),
    (0.05, f"  ║      SOLO BUILDER  v2.0 — AI AGENT CLI               ║\r\n"),
    (0.05, f"  ║                                                       ║\r\n"),
    (0.05, f"  ║  SDK Runner · REVIEW_MODE · Telegram Bot · DAG v2    ║\r\n"),
    (0.05, f"  ╚══════════════════════════════════════════════════════╝{RESET}\r\n"),
    (0.5,  f"  {CYAN}No saved state — starting fresh.{RESET}\r\n\r\n"),

    # ── Step 0 display ───────────────────────────────────────────────────────
    (0.4,  f"{CLR}{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER v2.0  │  Step: {YELLOW}0{CYAN}  │  ETA: N/A{RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{YELLOW}▶ Task 0{RESET}  [{YELLOW}Pending{RESET}]\r\n"),
    (0.05, f"    {YELLOW}├─ Branch A{RESET} [{YELLOW}Pending{RESET}]  {DIM}Progress [--------------------] 0/5{RESET}\r\n"),
    (0.05, f"    {YELLOW}└─ Branch B{RESET} [{YELLOW}Pending{RESET}]  {DIM}Progress [--------------------] 0/3{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{YELLOW}▶ Task 1{RESET}  [{YELLOW}Pending{RESET}]  {DIM}[blocked → Task 0]{RESET}\r\n"),
    (0.05, f"  {BOLD}{YELLOW}▶ Task 2{RESET}  [{YELLOW}Pending{RESET}]  {DIM}[blocked → Task 1]{RESET}\r\n\r\n"),
    (0.05, f"  Overall [{YELLOW}----------------------------{RESET}] {YELLOW}0✓{RESET} {CYAN}0▶{RESET} {YELLOW}70●{RESET} / 70  (0.0%)\r\n\r\n"),
    (0.05, f"  {DIM}Commands: run │ auto [N] │ verify │ describe │ tools │ export │ help │ exit{RESET}\r\n"),
    (0.05, f"  {SEP}\r\n\r\n"),

    # ── Enable REVIEW_MODE ───────────────────────────────────────────────────
    (0.8,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    *_type("set REVIEW_MODE=on"),
    (0.5,  "\r\n"),
    (0.2,  f"  {GREEN}REVIEW_MODE = on (subtasks pause at Review for verify){RESET}\r\n\r\n"),

    # ── auto ─────────────────────────────────────────────────────────────────
    (0.5,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    *_type("auto"),
    (0.5,  "\r\n"),
    (0.3,  f"  {CYAN}Auto-run: until complete  │  delay=0.4s  │  Ctrl+C to pause{RESET}\r\n"),

    # ── Step 1: Running ──────────────────────────────────────────────────────
    (0.6,  f"{CLR}{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER v2.0  │  Step: {YELLOW}1{CYAN}  │  ETA: ~69 steps  (1% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 0{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch A{RESET} [{CYAN}Running{RESET}]  Progress [{YELLOW}--------------------{RESET}] 0/5\r\n"),
    (0.05, f"    │    {CYAN}◦ A1{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ A2{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ A3{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ A4{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ A5{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    {CYAN}└─ Branch B{RESET} [{CYAN}Running{RESET}]  Progress [{YELLOW}--------------------{RESET}] 0/3\r\n"),
    (0.05, f"    │    {CYAN}◦ B1{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.3,  f"\r\n  {BLUE}SDK executing A1, A2, A3, A4, A5, B1…{RESET}\r\n"),
    (0.05, f"  Overall [{YELLOW}----------------------------{RESET}] {YELLOW}0✓{RESET} {CYAN}6▶{RESET} {YELLOW}64●{RESET} / 70  (0.0%)\r\n"),

    # ── Step 2: A1-B1 all in Review (REVIEW_MODE gate) ──────────────────────
    (1.4,  f"{CLR}{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER v2.0  │  Step: {YELLOW}2{CYAN}  │  ETA: ~68 steps  (0% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 0{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch A{RESET} [{MAGENTA}Review{RESET}]  Progress [{YELLOW}--------------------{RESET}] 0/5\r\n"),
    (0.05, f"    │    {MAGENTA}◦ A1{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0  {DIM}⏸ awaiting verify{RESET}\r\n"),
    (0.05, f"    │      {DIM}↳ • Natural language task creation — Convert vague ideas into…{RESET}\r\n"),
    (0.05, f"    │    {MAGENTA}◦ A2{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0  {DIM}⏸ awaiting verify{RESET}\r\n"),
    (0.05, f"    │      {DIM}↳ Solo Builder is a Python terminal CLI that harnesses AI…{RESET}\r\n"),
    (0.05, f"    │    {MAGENTA}◦ A3{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0  {DIM}⏸ awaiting verify{RESET}\r\n"),
    (0.05, f"    │    {MAGENTA}◦ A4{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0  {DIM}⏸ awaiting verify{RESET}\r\n"),
    (0.05, f"    │    {MAGENTA}◦ A5{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0  {DIM}⏸ awaiting verify{RESET}\r\n"),
    (0.05, f"    {CYAN}└─ Branch B{RESET} [{MAGENTA}Review{RESET}]  Progress [{YELLOW}--------------------{RESET}] 0/3\r\n"),
    (0.05, f"    │    {MAGENTA}◦ B1{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0  {DIM}⏸ awaiting verify{RESET}\r\n"),
    (0.05, f"\r\n  Overall [{YELLOW}----------------------------{RESET}] {YELLOW}0✓{RESET} {MAGENTA}6⏸{RESET} {CYAN}0▶{RESET} {YELLOW}64●{RESET} / 70  (0.0%)\r\n"),

    # ── verify A1 ────────────────────────────────────────────────────────────
    (1.2,  f"\r\n  {BOLD}{CYAN}solo-builder >{RESET} "),
    *_type("verify A1 feature list looks solid"),
    (0.5,  "\r\n"),
    (0.2,  f"  {GREEN}✓ A1 (Task 0) verified (was Review). Note: feature list looks solid{RESET}\r\n"),

    # ── verify A2 A3 ─────────────────────────────────────────────────────────
    (0.3,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    *_type("verify A2 great elevator pitch"),
    (0.5,  "\r\n"),
    (0.2,  f"  {GREEN}✓ A2 (Task 0) verified (was Review). Note: great elevator pitch{RESET}\r\n"),

    (0.3,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    *_type("verify A3 accepted"),
    (0.5,  "\r\n"),
    (0.2,  f"  {GREEN}✓ A3 (Task 0) verified (was Review). Note: accepted{RESET}\r\n"),

    # ── Telegram /verify ─────────────────────────────────────────────────────
    (0.4,  f"\r\n  {DIM}📱 Telegram: /verify A4 lgtm  →  queued via verify_trigger.json{RESET}\r\n"),
    (0.05, f"  {GREEN}✓ A4 (Task 0) verified (was Review). Note: lgtm{RESET}\r\n"),
    (0.05, f"  {GREEN}✓ A5 (Task 0) verified (was Review). Note: Telegram verify{RESET}\r\n"),
    (0.05, f"  {GREEN}✓ B1 (Task 0) verified (was Review). Note: Telegram verify{RESET}\r\n"),

    # ── Step 6: Task 0 complete, more running ────────────────────────────────
    (0.8,  f"{CLR}{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER v2.0  │  Step: {YELLOW}6{CYAN}  │  ETA: ~52 steps  (11% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 0{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"    {GREEN}├─ Branch A{RESET} [{GREEN}Verified{RESET}]  Progress [{GREEN}===================={RESET}] 5/5\r\n"),
    (0.05, f"    {GREEN}└─ Branch B{RESET} [{GREEN}Verified{RESET}]  Progress [{GREEN}===================={RESET}] 3/3\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 1{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch C{RESET} [{MAGENTA}Review{RESET}]  Progress [{YELLOW}--------------------{RESET}] 0/4\r\n"),
    (0.05, f"    │    {MAGENTA}◦ C1{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0\r\n"),
    (0.05, f"    │      {DIM}↳ CLI tools let Claude read files, glob patterns, and grep…{RESET}\r\n"),
    (0.05, f"    │    {MAGENTA}◦ C2{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0\r\n"),
    (0.05, f"    {CYAN}└─ Branch D{RESET} [{MAGENTA}Review{RESET}]  Progress [{YELLOW}--------------------{RESET}] 0/2\r\n"),
    (0.3,  f"  {BLUE}SDK executing C3, C4, D1, D2…{RESET}\r\n"),
    (0.05, f"  Overall [{GREEN}======----------------------{RESET}] {GREEN}8✓{RESET} {MAGENTA}2⏸{RESET} {CYAN}4▶{RESET} {YELLOW}56●{RESET} / 70  (11.4%)\r\n"),

    # ── Fast forward to step 20 ──────────────────────────────────────────────
    (2.0,  f"{CLR}{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER v2.0  │  Step: {YELLOW}20{CYAN}  │  ETA: ~18 steps  (50% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 0{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 1{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 2{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 3{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch G{RESET} [{MAGENTA}Review{RESET}]  Progress [{GREEN}========------------{RESET}] 3/6\r\n"),
    (0.05, f"    │    {MAGENTA}◦ G4{RESET}  {MAGENTA}Review{RESET}   shadow={GREEN}Done{RESET}   age=0\r\n"),
    (0.05, f"    │      {DIM}↳ A/B testing lets solo devs compare two feature variants…{RESET}\r\n"),
    (0.05, f"    {CYAN}├─ Branch H{RESET} [{MAGENTA}Review{RESET}]  Progress [{GREEN}========------------{RESET}] 2/4\r\n"),
    (0.05, f"    {CYAN}└─ Branch I{RESET} [{GREEN}Verified{RESET}]  Progress [{GREEN}===================={RESET}] 3/3\r\n"),
    (0.3,  f"  {BLUE}SDK executing G5, G6, H3, H4…{RESET}\r\n"),
    (0.05, f"  Overall [{GREEN}==============----------{RESET}] {GREEN}35✓{RESET} {MAGENTA}2⏸{RESET} {CYAN}4▶{RESET} {YELLOW}29●{RESET} / 70  (50.0%)\r\n"),

    # ── Step 25: near end, Task 6 synthesis ──────────────────────────────────
    (2.0,  f"{CLR}{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER v2.0  │  Step: {YELLOW}25{CYAN}  │  ETA: ~2 steps  (94% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Tasks 0-5{RESET}  [{GREEN}Verified{RESET}]\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 6  (synthesis){RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch O{RESET} [{CYAN}Running{RESET}]  Progress [{GREEN}--------{RESET}{YELLOW}------------{RESET}] 1/3\r\n"),
    (0.05, f"    │    {GREEN}◦ O1{RESET}  {GREEN}Verified{RESET}  age=0\r\n"),
    (0.05, f"    │      {DIM}↳ Tasks completed: 64/70 · Task 4 has most subtasks…{RESET}\r\n"),
    (0.05, f"    │    {CYAN}◦ O2{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ O3{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    {CYAN}├─ Branch P{RESET} [{CYAN}Running{RESET}]  Progress [{YELLOW}--------------------{RESET}] 0/3\r\n"),
    (0.05, f"    │    {CYAN}◦ P1{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.3,  f"  {CYAN}Claude executing O1…{RESET}  {DIM}(Read · Glob · Grep tools){RESET}\r\n"),
    (0.3,  f"  {BLUE}SDK executing O2, O3, P1…{RESET}\r\n"),
    (0.05, f"  Overall [{GREEN}========================----{RESET}] {GREEN}66✓{RESET} {CYAN}4▶{RESET} {YELLOW}0●{RESET} / 70  (94.3%)\r\n"),

    # ── 100% complete ────────────────────────────────────────────────────────
    (2.0,  f"{CLR}{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER v2.0  │  Step: {YELLOW}27{CYAN}  │  ETA: {GREEN}COMPLETE{RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 0{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 1{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 2{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 3{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 4{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 5{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 6  (synthesis){RESET}  [{GREEN}Verified{RESET}]\r\n\r\n"),
    (0.05, f"    {GREEN}└─ Branch P{RESET} [{GREEN}Verified{RESET}]  last output:\r\n"),
    (0.05, f"    │    {DIM}↳ Here's a haiku about autonomous agents managing projects:{RESET}\r\n"),
    (0.05, f"    │    {DIM}↳   Code flows through the graph — agents heal what stalls,{RESET}\r\n"),
    (0.05, f"    │    {DIM}↳   All 70 tasks: {GREEN}done{RESET}{DIM}.{RESET}\r\n\r\n"),
    (0.4,  f"  Overall [{GREEN}================================{RESET}] {GREEN}70✓{RESET} {CYAN}0▶{RESET} {YELLOW}0●{RESET} / 70  (100.0%)\r\n\r\n"),
    (0.3,  f"  {DIM}Commands: run │ auto [N] │ verify │ describe │ export │ exit{RESET}\r\n"),
    (0.05, f"  {SEP}\r\n\r\n"),

    # ── export ───────────────────────────────────────────────────────────────
    (1.0,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    *_type("export"),
    (0.5,  "\r\n"),
    (0.4,  f"  {GREEN}Exported 70 outputs → solo_builder_outputs.md{RESET}\r\n\r\n"),

    # ── exit ─────────────────────────────────────────────────────────────────
    (0.8,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    *_type("exit"),
    (0.5,  "\r\n"),
    (0.3,  f"  {CYAN}Solo Builder shutting down. Steps: 27  │  Healed: 0  │  State saved.{RESET}\r\n\r\n"),
]

cast(events)
