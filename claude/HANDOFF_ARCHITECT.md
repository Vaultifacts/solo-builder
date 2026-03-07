# HANDOFF TO ARCHITECT (from RESEARCH)

## Task
TASK-024

## Finding
advance_state.ps1 line 51 writes STATE.json directly via Set-Content.
If the process is interrupted mid-write (power loss, Ctrl-C, crash),
the file is left partially written, causing a corrupt JSON parse on
next run.

## Fix
Write to a temp file (STATE.json.tmp) then rename atomically. On
Windows/NTFS, Move-Item -Force is effectively atomic for same-volume
moves. The temp file is adjacent to STATE.json so it's always on the
same volume.

## Scope
- tools/advance_state.ps1 only
- No other files modified
