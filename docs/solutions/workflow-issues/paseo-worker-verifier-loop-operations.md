---
title: "Paseo worker/verifier loop operations: lost finish notifications, memory pressure, and dispatch recovery"
date: 2026-08-07
category: workflow-issues
module: paseo orchestration (dispatcher loop)
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - "Running a multi-day Paseo worker/verifier loop with an LLM dispatcher/orchestrator"
  - "Long autonomous orchestrations where agent finish notifications can be silently lost and the loop stalls until polled"
  - "Memory-constrained environments (e.g. Windows) with many concurrent opencode processes consuming locked server memory"
  - "Recovering a stalled lane when an agent has finished but the completion notification never arrived"
  - "Running parallel agent lanes with worktree isolation that must be cleaned up by archiving finished agents"
tags: [paseo, agent-orchestration, dispatcher-loop, heartbeat, finish-notification, memory-pressure, worker-verifier, recovery]
---

# Running multi-day Paseo worker/verifier loops on Windows: finish notifications, memory pressure, and verification discipline

## Context

An 11-unit implementation loop ("workstream-registration") was run over multiple days as a Paseo orchestrator dispatching worker agents (implement a unit from a plan) and verifier agents (fresh-context, adversarial review plus regression-test proof) in a worktree-isolated workspace on Windows. Three operational realities emerged that the loop had to be designed around rather than "fixed": (1) Paseo finish notifications are silently lost — observed 4+ times (U7 verifier, U8 worker, U8 verifier, and later rounds), with the loop stalling each time until someone polled; (2) Windows memory pressure accumulates as finished lane agents keep their OpenCode server processes alive, eventually crashing agents mid-run with Bun "Illegal instruction" errors, "OpenCode server exited with code 3221226505" (0xC0000409, stack buffer overrun), exit 2147942402, and pytest stack-overflow exits (-1073741571 / 0xC00000FD), once with 34 opencode processes and ~1.4 GB free RAM; and (3) verification only caught real defects when the verifier had a fresh context, an adversarial brief, and a different model family than the worker.

These are the operating conditions of the platform on this machine, not defects to be reported or chased. The loop design that worked: assume notifications may not arrive, treat memory as a renewable resource you must explicitly reclaim, and make the verifier genuinely independent.

## Guidance

**1. Design the loop assuming finish notifications are lost.**

- Do not wait on the notification. Treat the heartbeat as the primary scheduler: `paseo heartbeat create --cron "*/10 * * * *"` with a prompt to check the lane keeps a dispatcher prompt arriving every 10 minutes. When it fires, poll the lane and process anything finished.
- Recovery when a notification was lost: pull the agent's final verdict from its timeline via `paseo_get_agent_activity <id>` or `paseo logs <id>` — the final verdict is in the timeline even when the finish notification never arrives.
- Use `paseo ls` for a fast lane-wide status check: it shows each agent's status; the attentionReason (e.g., `finished`) is surfaced by the MCP agent-status tools (`list_agents` / `get_agent_status`), which together distinguish "done, waiting to be processed" from "stalled".
- Never treat a stalled lane as a platform bug requiring a fix before continuing. Process the finished work and move on. If a session is genuinely broken (event-stream failure), redispatch a fresh agent rather than resuming the crashed session.

**2. Treat memory as a finite, explicitly reclaimed resource on Windows.**

- Symptom cluster to recognize: Bun "Illegal instruction" crashes, "OpenCode server exited with code 3221226505" (0xC0000409), exit 2147942402, pytest exit -1073741571 (0xC00000FD stack overflow), many opencode processes accumulating in Task Manager. These correlate with finished lane agents whose locked server memory was never freed.
- After a round completes, archive finished lane agents with `paseo archive <id>` — a soft-delete that frees the locked OpenCode server memory while preserving the agent's history. Use archive, NOT `kill` (kill loses the history you still need to extract verdicts from).
- Before running pytest after a memory-clean, clear the stale cache at the repo root — `Remove-Item .pytest_cache -Recurse` (or `pytest --cache-clear`; the `.pytest_cache` dir lives at the pytest rootdir, which is the repo root where `pyproject.toml` sits — gitignored runtime artifact, intentionally absent from the tree): a stale cache left by a crashed verifier session caused a stack-overflow crash (exit -1073741571) that a clean cache avoided (U11 verifier evidence; the same spec command then passed 359 tests with exit 0, confirmed by two subsequent clean runs).
- After event-stream failures, redispatch fresh agents instead of resuming the crashed session — resumed sessions inherit whatever memory/cache state killed them.

**3. Make verification genuinely independent and adversarial.**

- Dispatch verifiers with a fresh context (they should not share the worker's session, prompts, or accumulated assumptions) and an adversarial brief — explicitly "your job is to break the fix, not confirm it".
- Use a different model family for the verifier than the worker where possible. Same-family confirmations missed real defects; a different-family verifier found them.
- Verify with regression-test proof, not vibes: the verifier must demonstrate the new tests genuinely fail against old code and pass with the fix, then return GREEN/RED with that evidence.
- Isolate concurrent lane agents in separate worktrees when they touch the same repo, so parallel runs cannot interfere with each other's working trees or test runs.

## Why This Matters

A multi-day loop's bottleneck is not agent speed — it is the orchestrator's ability to keep the pipeline fed. Lost finish notifications were the single most common stall cause (4+ incidents across the run); without the heartbeat-and-poll pattern each one silently halted the loop until a human polled. Memory pressure compounds with notification losses: finished agents that are never archived keep holding server memory, so every unprocessed finish both stalls the loop and brings the machine closer to the next crash — the 34-process / 1.4 GB-free observation came immediately before a crash round. Treating these as expected conditions (rather than error paths to fix) let the loop recover in minutes instead of debugging sessions. The verification discipline is what made the loop trustworthy end-to-end: the P1 icacls regex bug and the projection race were both caught by review, and the independent verifier proved the regression tests genuinely fail against old code — without that, "GREEN" would have been a rubber stamp and the loop's output would have shipped broken code.

## When to Apply

- Any time you run a multi-day or multi-agent Paseo worker/verifier implementation loop from an orchestrator that depends on finish notifications to advance.
- On Windows specifically (or any machine where a crashed agent process leaves memory held until explicitly reclaimed) — the Bun/0xC0000409 crash cluster is the tell.
- When dispatching any verification step where the verifier could share assumptions with the worker (same session, same model family, confirmatory framing).
- When parallel agents work the same repository and worktree isolation is available.

## Examples

**Lost finish notification — recovery (from the run's session history):**

- "The verifier has finished (attentionReason: finished at 05:17) but its completion notification never reached me. Pulling its final verdict from its activity." → `paseo_get_agent_activity <id>` yielded the verdict; lane advanced without restarting anything.
- "Worker finished (again without a notification). Pulling its verdict and confirming the fix landed." → verdict pulled; fix verified against the worktree.
- "two finish notifications were lost so far (U7 verifier, U8 worker); both times the loop stalled until you or I polled. Creating a heartbeat that prompts me every 10 minutes to check the lane and surface anything finished-but-unprocessed." → `paseo heartbeat create --cron "*/10 * * * *"` ended the stall-without-poll class of incident.

**Memory pressure — cleanup and redispatch:**

- "Memory is tight again (1.4 GB free, 34 opencode processes). Cleaning up finished lane agents and redispatching the verifier." → `paseo archive <finished-id>` for each finished lane agent (soft-delete; history preserved for verdict extraction), then redispatch fresh.
- "U11 verifier crashed (same event-stream failure). Checking memory pressure, then redispatching fresh." → crash after memory-clean traced to stale `.pytest_cache` at the repo root; `Remove-Item .pytest_cache -Recurse` (or `pytest --cache-clear`), then the exact spec command passed cleanly: 359 passed, exit 0, ~101 s, confirmed twice more.

**Verification that caught real defects:**

- Worker committed 2 fixes → fresh minimax-m3 verifier ran the regression tests against OLD code first: they failed as expected; against the fix: GREEN with the failing/passing evidence attached. The same adversarial review round caught the P1 icacls regex bug and the projection race — both missed by same-family confirmations.

**Anti-patterns to avoid:**

- Waiting on the notification and doing nothing else — stalls until a human polls.
- `paseo delete` / `paseo_kill_agent` instead of `archive` for finished agents — frees memory but destroys the history you still need for verdicts.
- Resuming a crashed session after an event-stream failure — the resumed session inherits the memory/cache state that killed it.
- Resuming the crashed session's pytest without clearing `.pytest_cache` — guaranteed replay of the stack-overflow crash.

## Related

- `docs/solutions/best-practices/readiness-review-adoption-before-execution.md` — the fresh-context cross-model review discipline this doc extends from plan-review into orchestrated execution loops (cross-link both directions).
- `docs/solutions/logic-errors/owner-only-acl-verification-missed-inherited-aces.md` and `docs/solutions/logic-errors/select-then-insert-race-maps-duplicate-target-conflict-to-integrity-error.md` — the concrete verification wins that the adversarial fresh-context verifier discipline produced.
- The plan and unit breakdown for the 11-unit workstream-registration loop (the run that produced this learning).
