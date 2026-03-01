"""
Generate a synthetic asciinema v2 cast file for the Solo Builder demo.
Run:  python make_demo_cast.py > demo.cast
Then: upload demo.cast to https://asciinema.org
"""
import json, sys, time as _time

W, H = 100, 40

def cast(events: list) -> None:
    header = {"version": 2, "width": W, "height": H,
              "timestamp": 1740800000, "title": "Solo Builder — AI Agent CLI demo"}
    print(json.dumps(header))
    t = 0.0
    for delay, text in events:
        t += delay
        print(json.dumps([round(t, 3), "o", text]))

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[34m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

SEP = "═" * 72

events = [
    # splash
    (0.1,  f"\r\n{BOLD}{CYAN}"),
    (0.05, "  ╔══════════════════════════════════════════════════════╗\r\n"),
    (0.05, "  ║      SOLO BUILDER — AI AGENT CLI  v1.0               ║\r\n"),
    (0.05, "  ║                                                       ║\r\n"),
    (0.05, "  ║  DAG · Shadow · Self-Heal · Auto-Run · Persistence   ║\r\n"),
    (0.05, f"  ╚══════════════════════════════════════════════════════╝{RESET}\r\n"),
    (0.6,  f"  {CYAN}No saved state found — starting fresh.{RESET}\r\n\r\n"),

    # header
    (0.4,  f"\033[2J\033[H{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI  │  Step: {YELLOW}0{CYAN}  │  ETA: N/A{RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),

    # task tree
    (0.1,  f"  {BOLD}{CYAN}▶ Task 0{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch A{RESET} [{YELLOW}Pending{RESET}]\r\n"),
    (0.05, f"    │  Progress [{YELLOW}--------------------{RESET}] 0/5\r\n"),
    (0.05, f"    │    {YELLOW}◦ A1{RESET}  {YELLOW}Pending{RESET}\r\n"),
    (0.05, f"    │    {YELLOW}◦ A2{RESET}  {YELLOW}Pending{RESET}\r\n"),
    (0.05, f"    │    {YELLOW}◦ A3{RESET}  {YELLOW}Pending{RESET}\r\n"),
    (0.1,  f"\r\n  {BOLD}{YELLOW}▶ Task 1{RESET}  [{YELLOW}Pending{RESET}]  {DIM}[blocked → Task 0]{RESET}\r\n\r\n"),
    (0.05, f"  Overall [{YELLOW}--------------------{RESET}] {YELLOW}0✓{RESET} {CYAN}0▶{RESET} {YELLOW}70●{RESET} / 70  (0.0%)\r\n\r\n"),
    (0.05, f"  {DIM}Commands: run │ auto [N] │ verify │ describe │ tools │ export │ help │ exit{RESET}\r\n"),
    (0.05, f"  {SEP}\r\n\r\n"),

    # prompt + auto command
    (0.8,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    (0.05, "a"), (0.06, "u"), (0.07, "t"), (0.06, "o"), (0.5, "\r\n"),
    (0.3,  f"  {CYAN}Auto-run: until complete  │  delay=0.4s  │  Ctrl+C to pause{RESET}\r\n"),

    # step 1 — start subtasks
    (0.5,  f"\033[2J\033[H{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI  │  Step: {YELLOW}1{CYAN}  │  ETA: ~69 steps  (1% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 0{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch A{RESET} [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    │  Progress [{YELLOW}--------------------{RESET}] 0/5\r\n"),
    (0.05, f"    │    {CYAN}◦ A1{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ A2{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {YELLOW}◦ A3{RESET}  {YELLOW}Pending{RESET}   age=1\r\n"),
    (0.3,  f"  {BLUE}SDK executing A1, A2…{RESET}\r\n"),

    # step 2 — A1, A2 verified
    (1.2,  f"\033[2J\033[H{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI  │  Step: {YELLOW}2{CYAN}  │  ETA: ~67 steps  (3% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 0{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch A{RESET} [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    │  Progress [{GREEN}========------------{RESET}] 2/5\r\n"),
    (0.05, f"    │    {GREEN}◦ A1{RESET}  {GREEN}Verified{RESET}  age=0\r\n"),
    (0.05, f"    │      {DIM}↳ • Natural language task creation — Convert vague ideas into…{RESET}\r\n"),
    (0.05, f"    │    {GREEN}◦ A2{RESET}  {GREEN}Verified{RESET}  age=0\r\n"),
    (0.05, f"    │      {DIM}↳ Solo Builder is a Python terminal CLI that harnesses AI…{RESET}\r\n"),
    (0.05, f"    │    {CYAN}◦ A3{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ A4{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.3,  f"  {BLUE}SDK executing A3, A4…{RESET}\r\n"),

    # fast-forward several steps
    (1.0,  f"\033[2J\033[H{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI  │  Step: {YELLOW}8{CYAN}  │  ETA: ~52 steps  (11% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 0{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"    {GREEN}├─ Branch A{RESET} [{GREEN}Verified{RESET}]  Progress [{GREEN}===================={RESET}] 5/5\r\n"),
    (0.05, f"    {GREEN}└─ Branch B{RESET} [{GREEN}Verified{RESET}]  Progress [{GREEN}===================={RESET}] 3/3\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 1{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch C{RESET} [{CYAN}Running{RESET}]  Progress [{GREEN}========------------{RESET}] 2/4\r\n"),
    (0.05, f"    {CYAN}└─ Branch D{RESET} [{GREEN}Verified{RESET}]  Progress [{GREEN}===================={RESET}] 2/2\r\n\r\n"),
    (0.05, f"  {BOLD}{YELLOW}▶ Task 2{RESET}  [{YELLOW}Pending{RESET}]  {DIM}[blocked → Task 1]{RESET}\r\n"),
    (0.3,  f"  {BLUE}SDK executing C3, C4…{RESET}\r\n"),
    (0.05, f"  Overall [{GREEN}========------------{RESET}] {GREEN}14✓{RESET} {CYAN}4▶{RESET} {YELLOW}52●{RESET} / 70  (20.0%)\r\n"),

    # mid-run: user types verify command
    (1.5,  f"\r\n  {BOLD}{CYAN}solo-builder >{RESET} "),
    (0.08, "v"), (0.07, "e"), (0.06, "r"), (0.07, "i"), (0.06, "f"), (0.07, "y"),
    (0.05, " "), (0.06, "C"), (0.07, "3"), (0.05, " "),
    (0.06, "r"), (0.07, "e"), (0.06, "v"), (0.07, "i"), (0.06, "e"), (0.07, "w"),
    (0.06, "e"), (0.07, "d"), (0.06, " "), (0.07, "a"), (0.06, "n"), (0.07, "d"),
    (0.06, " "), (0.07, "a"), (0.06, "p"), (0.07, "p"), (0.06, "r"), (0.07, "o"),
    (0.06, "v"), (0.07, "e"), (0.06, "d"),
    (0.5,  "\r\n"),
    (0.2,  f"  {GREEN}✓ C3 (Task 1) verified (was Running). Note: reviewed and approved{RESET}\r\n"),

    # jump to near completion
    (2.0,  f"\033[2J\033[H{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI  │  Step: {YELLOW}60{CYAN}  │  ETA: ~8 steps  (86% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 0{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 1{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 2{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 3{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 4{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 5{RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}└─ Branch N{RESET} [{CYAN}Running{RESET}]  Progress [{GREEN}===============-----{RESET}] 4/5\r\n"),
    (0.05, f"  {BOLD}{YELLOW}▶ Task 6{RESET}  [{YELLOW}Pending{RESET}]  {DIM}[blocked → Tasks 1-5]{RESET}\r\n\r\n"),
    (0.3,  f"  {BLUE}SDK executing N5…{RESET}\r\n"),
    (0.05, f"  Overall [{GREEN}========================----{RESET}] {GREEN}60✓{RESET} {CYAN}2▶{RESET} {YELLOW}8●{RESET} / 70  (85.7%)\r\n"),

    # Task 6 synthesis — Claude subprocess with tools
    (1.5,  f"\033[2J\033[H{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI  │  Step: {YELLOW}68{CYAN}  │  ETA: ~2 steps  (97% done){RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Tasks 0-5{RESET}  [{GREEN}Verified{RESET}]\r\n\r\n"),
    (0.05, f"  {BOLD}{CYAN}▶ Task 6  (synthesis){RESET}  [{CYAN}Running{RESET}]\r\n"),
    (0.05, f"    {CYAN}├─ Branch O{RESET} [{CYAN}Running{RESET}]  Progress [{GREEN}========------------{RESET}] 1/3\r\n"),
    (0.05, f"    │    {GREEN}◦ O1{RESET}  {GREEN}Verified{RESET}  age=0\r\n"),
    (0.05, f"    │      {DIM}↳ 64 of 70 subtasks verified · Task 5 has most subtasks…{RESET}\r\n"),
    (0.05, f"    │    {CYAN}◦ O2{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.05, f"    │    {CYAN}◦ O3{RESET}  {CYAN}Running{RESET}   age=0\r\n"),
    (0.3,  f"  {CYAN}Claude executing O1…{RESET}   {DIM}(Read · Glob · Grep tools){RESET}\r\n"),
    (0.3,  f"  {BLUE}SDK executing O2, O3…{RESET}\r\n"),

    # 100% complete
    (2.0,  f"\033[2J\033[H{BOLD}{CYAN}{SEP}{RESET}\r\n"),
    (0.05, f"{BOLD}{CYAN}  SOLO BUILDER — AI AGENT CLI  │  Step: {YELLOW}70{CYAN}  │  ETA: {GREEN}COMPLETE{RESET}\r\n"),
    (0.05, f"{CYAN}{SEP}{RESET}\r\n\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 0{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 1{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 2{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 3{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 4{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 5{RESET}  [{GREEN}Verified{RESET}]\r\n"),
    (0.05, f"  {BOLD}{GREEN}▶ Task 6{RESET}  [{GREEN}Verified{RESET}]\r\n\r\n"),
    (0.3,  f"  Overall [{GREEN}================================{RESET}] {GREEN}70✓{RESET} {CYAN}0▶{RESET} {YELLOW}0●{RESET} / 70  (100.0%)\r\n\r\n"),
    (0.5,  f"  {DIM}Commands: run │ auto [N] │ verify │ describe │ export │ exit{RESET}\r\n"),
    (0.05, f"  {SEP}\r\n\r\n"),

    # export
    (1.0,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    (0.08, "e"), (0.07, "x"), (0.06, "p"), (0.07, "o"), (0.06, "r"), (0.07, "t"),
    (0.5,  "\r\n"),
    (0.4,  f"  {GREEN}Exported 70 outputs → solo_builder_outputs.md{RESET}\r\n\r\n"),

    # exit
    (0.8,  f"  {BOLD}{CYAN}solo-builder >{RESET} "),
    (0.08, "e"), (0.07, "x"), (0.06, "i"), (0.07, "t"),
    (0.5,  "\r\n"),
    (0.3,  f"  {CYAN}Solo Builder shutting down. Steps: 70  │  Healed: 0  │  State saved.{RESET}\r\n\r\n"),
]

cast(events)
