---
title: "Windows: Paseo terminal keystrokes can echo without executing — launch serve processes detached"
date: 2026-08-08
category: workflow-issues
module: paseo orchestration (terminal / serve ops)
problem_type: workflow_issue
component: development_workflow
severity: low
applies_when:
  - "Launching a long-running process (file server, dev watcher, daemon) through a Paseo supervised terminal on Windows"
  - "Serving a static site or artifact to network viewers (e.g. over NetBird) and verifying it is actually up"
  - "Diagnosing 'connection refused' right after a command was sent to a Paseo terminal"
tags: [paseo, terminal, windows, process-launch, http-server, verification, netbird, serve]
---

# Windows: Paseo terminal keystrokes can echo without executing — launch serve processes detached

## Context

On 2026-08-08 the orchestrator needed to serve a single-file HTML system view (`tmp/system-view/index.html`) to viewers on the NetBird network. A Paseo supervised terminal was created with its working directory set to the serve directory, and the command `python -m http.server 8890 --bind 100.84.85.1` was sent via `paseo_send_terminal_keys`. The terminal echoed the command back (visible in the capture), but the command **never executed**: no server output, no python process spawned, and no listener on port 8890 — `Invoke-WebRequest` reported "actively refused". The same command launched detached via `Start-Process` with redirected logs came up immediately (listener in `Listen` state, HTTP 200 verified).

An echoed command in a Paseo terminal is evidence that keystrokes were delivered to the terminal buffer, not that the shell executed them. On this Windows host, delivery failed silently at least once.

## Guidance

**1. Verify by listener, not by echo.** After sending a command to a Paseo terminal, confirm the process actually runs before assuming the service is up:

- `Get-NetTCPConnection -LocalPort <port>` → look for `State = Listen` (and check the bound `LocalAddress`).
- Optionally `Invoke-WebRequest -Uri http://<addr>:<port>/` and assert the expected content marker.
- If the terminal shows the echoed command but no output and the port is not listening, assume delivery failed — do not retry the same path blindly.

**2. Prefer detached launch for long-running processes on Windows.** Skip terminal keystrokes entirely for servers:

```powershell
$p = Start-Process -FilePath python `
  -ArgumentList "-m","http.server","8890","--bind","100.84.85.1" `
  -WorkingDirectory "<serve-dir>" `
  -RedirectStandardOutput "<log>" -RedirectStandardError "<err.log>" `
  -WindowStyle Hidden -PassThru
# $p.Id → PID; verify with Get-NetTCPConnection, diagnose via the logs
```

This captures the PID, survives the terminal lifecycle, and writes stdout/stderr to files for diagnosis — strictly better observability than a supervised terminal for a process that should outlive the conversation.

**3. Bind deliberately.** Serve on the NetBird interface IP (e.g. `100.84.85.x`) to make the artifact reachable by network viewers, or `127.0.0.1` for local-only. A plain `http.server` default binds all interfaces — choose explicitly.

**4. If you do use a terminal:** confirm the shell prompt is ready before sending keys, wait a beat, and capture output after a short delay. A command that echoes but produces nothing within seconds is suspect regardless of prompt state.

## Why This Matters

The silent failure cost a full verify cycle plus a terminal kill and relaunch — minutes — and could easily have been misreported as "the server is broken" rather than "the command never ran". Port-listener verification turns an ambiguous echo into a binary check, and the detached-launch pattern removes the failure mode for the most common long-running case (file servers). Small lesson, cheap to encode, and it prevents a class of false "infrastructure broke" alarms.

## When to Apply

- Any time a serve/daemon/watch process is launched through a Paseo terminal on Windows.
- Any time a freshly "started" service refuses connections — check the listener before debugging the service.
- When serving an artifact to network viewers and you must confirm it is genuinely reachable on the intended interface.

## Examples

**Detached launch that worked (2026-08-08):**

```
$p = Start-Process python -ArgumentList "-m","http.server","8890","--bind","100.84.85.1" `
  -WorkingDirectory "<worktree>\tmp\system-view" `
  -RedirectStandardOutput "$env:TEMP\system-view-server.log" `
  -RedirectStandardError "$env:TEMP\system-view-server.err.log" -WindowStyle Hidden -PassThru
# → PID 17240; Get-NetTCPConnection -LocalPort 8890 → 100.84.85.1:8890 Listen
# → Invoke-WebRequest http://100.84.85.1:8890/ → HTTP 200, title marker present
```

**Anti-pattern that failed:**

- Created Paseo terminal (cwd = serve dir) → `paseo_send_terminal_keys "python -m http.server 8890 --bind 100.84.85.1"` → terminal echoed the command → assumed it ran → `Invoke-WebRequest` → "actively refused". No listener, no process, no output — delivery had failed.
- Retrying the same keystroke path instead of switching to a detached launch would have replayed the failure without diagnosis.

## Related

- `docs/solutions/workflow-issues/paseo-worker-verifier-loop-operations.md` — the companion doc on Paseo operating conditions on this Windows host (lost finish notifications, memory pressure, dispatch recovery); same category, complementary failure modes.
- `docs/architecture/` — the system view served by this pattern is a product of the architecture-doc-set workflow.
