---
title: "Paseo agents are pinned to their creation workspace — resume in another workspace via a self-contained agent handoff"
date: 2026-08-09
category: workflow-issues
module: paseo orchestration (agent workspace management)
problem_type: workflow_issue
component: development_workflow
severity: low
applies_when:
  - "Needing to resume work started by a Paseo agent whose home workspace is a different workspace of the same project (e.g. a git-worktree home workspace vs. the current repo workspace)"
  - "A Paseo agent is pinned to the workspace it was created in and no move-agent command exists"
  - "Handing off an in-flight brainstorm, plan, or deliverable between Paseo agents in different workspaces"
tags: [paseo, agent, workspace, handoff, orchestration, worktree, resume, cross-workspace]
---

# Paseo agents are pinned to their creation workspace — resume in another workspace via a self-contained agent handoff

## Context

Paseo-orchestrated agents are workspace-pinned at creation: the agent's cwd, workspace, and session are fixed to the workspace it was created in, and there is no relocation primitive. `paseo agent --help` exposes ls/run/import/attach/logs/open/stop/delete/send/inspect/wait/mode/archive/reload/detach/update, none of which re-home an existing agent: `paseo agent update` only changes name/thinking/labels, and `paseo agent run --workspace <id>` creates a NEW agent in an existing workspace rather than moving one. This surfaced when an operator asked an agent to "bring this agent to this workspace": agent `ddceb3db` (Paseo agent ID, not a commit SHA; opencode provider) was homed in workspace wks_4f68526bd0fb84b3 (git worktree at C:\Users\rmicua\.paseo\worktrees\2fewjc5w\workstream-registration) and the target was workspace wks_0c58a9e5bbe4b9c5 in C:\Users\rmicua\arjim, both under the same project prj_e8a9fda2b751f0d4.

## Guidance

Do not try to move the agent — hand off the work instead. The working pattern:

1. Prompt the source agent (via `paseo agent send` / `paseo_send_agent_prompt`) to produce a self-contained handoff document.
2. Require the handoff to contain exactly five elements: (1) current state of the work, (2) converged framing and decisions, (3) the agreed deliverable and next step, (4) open questions or forks, and (5) explicit resume instructions for the new workspace.
3. In the target workspace, run a fresh agent (`paseo agent run --workspace <target-id>`) and give it the handoff as its opening context.
4. Verify the resume: the new agent should restate the deliverable and next step before continuing; if it cannot, the handoff is incomplete — send it back for a revision.

The handoff is the artifact that crosses the workspace boundary, not the agent. Agents belong to a workspace; a workspace's cwd can be a local checkout, a plain directory, or a git worktree under ~/.paseo/worktrees/ (or the configured `worktrees.root`).

## Why This Matters

Converged brainstorm and design state is expensive to produce and trivial to lose. Workspace boundaries (different checkouts, directories, or worktrees) are hard walls for pinned agents — there is no move command, so the naive request "bring this agent here" fails. The handoff pattern preserves converged state across that boundary without any tooling support, works for any provider (local or remote), and avoids copying session state that is not portable anyway. It turns an impossible operation into a repeatable, verifiable workflow.

## When to Apply

- An operator asks to "bring" an agent from one workspace to another (same or different project).
- Work must resume in a different checkout, directory, or git worktree than where it started.
- A long brainstorm or design conversation needs to continue in a fresh agent or a different opencode instance.
- Any time a session is pinned to a workspace/cwd that is no longer the right home for the work.

## Examples

The brainstorm "workstream is a standard, not a product" was converged in workspace wks_4f68526bd0fb84b3 (agent ddceb3db) and needed to continue in wks_0c58a9e5bbe4b9c5 (C:\Users\rmicua\arjim). Rather than moving the agent, the source agent was prompted to write a handoff covering the five elements above; a new agent was run in the target workspace with that handoff as its opening context. The resume was clean: the new agent picked up the framing without re-litigating decisions, the brainstorm re-converged under the name "Workstream Protocol", and it produced a requirements-only plan at docs/plans/2026-08-08-001-docs-workstream-protocol-framing-plan.md plus a CONCEPTS.md entry. No agent state was copied; only the handoff text crossed the boundary.

## Related

- docs/solutions/workflow-issues/paseo-worker-verifier-loop-operations.md — sibling operating-conditions doc; its "redispatch a fresh agent" guidance is consistent with workspace pinning.
- docs/solutions/workflow-issues/paseo-terminal-keystrokes-echo-without-executing-windows.md — companion paseo operating-condition on this Windows host.
- docs/session-digests/2026080802_workstream_protocol_framing.md — source decision record (D1, I1, I3) for this learning.
- docs/plans/2026-08-08-001-docs-workstream-protocol-framing-plan.md — the resume outcome produced by this pattern.
