---
name: execute-ce-plan
description: Coordinate dispatcher-led execution of an existing implementation-ready Compound Engineering plan through implementation, simplification, independent review and repair, knowledge capture, PR creation, Copilot review, CI and feedback resolution, and a verified merge-ready verdict. Use after dispatch-setup when the operator asks to execute, ship, or drive a CE plan to merge-ready without merging it.
---

# Execute a CE Plan

Coordinate the complete delivery run while remaining the dispatcher. Delegate every implementation or repository mutation, independently verify every worker claim, and stop at a merge-ready verdict. Never merge.

## Load the Operating Contract

Read both bundled references before dispatching work:

- `references/stage-contracts.md` for stage order, gates, invocations, and terminal states.
- `references/dispatch-briefs.md` for the bounded briefs sent to workers, verifiers, advisors, and the merge-readiness loop.

Resolve referenced skill names against the host's available-skills list and invoke the exact listed entry. Names may carry a plugin namespace.

Adopt `dispatch-setup` for the entire run if it is not already active. Preserve its boundaries: coordinate and record; do not implement, fix, stage, commit, push, reply to review threads, or edit the plan yourself.

## Authority

Treat explicit invocation of this skill with a plan as authority to:

- create or use an isolated feature branch or worktree;
- implement the plan, run checks, and create ordinary commits;
- simplify behavior-preservingly;
- push the feature branch and open or update its PR;
- request reviews and fix, commit, push, reply to, and resolve valid feedback on that PR.

Do not treat it as authority to merge, force-push, rebase, weaken verification, change a settled contract, edit unrelated work, approve gated CI, or expand the plan's scope. Live operator instructions may narrow or revoke authority immediately.

## Establish the Run

1. Resolve one explicit plan path. Do not select among multiple plausible plans by recency.
2. Require an existing code plan that is implementation-ready. For `ce-unified-plan/v1`, require `artifact_readiness: implementation-ready` and `execution: code`. Route a requirements-only plan back to `ce-plan` and stop.
3. Read the plan's Goal Capsule, dependencies, Implementation Units, Verification Contract, Definition of Done, scope boundaries, freeze points, and `session-settled:` decisions. Derive unit order and exit bars from the plan; never invent session-sized phases.
4. Read `VISION.md` and answer its three "How to use this vision" questions in the run ledger. State clearly when the work is only a technical foundation. Read applicable `AGENTS.md`, `CONCEPTS.md`, and relevant entries under the resolved CE artifact root's `solutions/` directory.
5. Inspect the branch, worktree, remotes, working tree, `gh` availability/authentication, and any existing PR. Treat pre-existing changes as operator-owned. Isolate the run when they overlap or make attribution uncertain.
6. Create `tmp/execute-ce-plan/<run-id>/run.md`. Record the plan path and digest, branch/worktree, authority, stage state, worker/verifier identities and model families, decisions, receipts, blockers, PR URL, and final head SHA. Never record credentials or raw secret-shaped values. Recheck the plan digest before every stage; an unexpected change returns the run to preflight.
7. Publish a short stage-level task view. Keep only one stage in progress. Do not mirror nested CE skill internals.

## Separate Roles

- Use one mutation lane at a time in a checkout. A CE stage may manage its own internal subagents; treat that skill as the stage engine and do not reproduce its internals.
- Invoke `goal-prompt-generator` for every worker brief. Require an objective, definition of done, allowed and forbidden scope, verification gates, and stop conditions.
- Use a fresh verifier from a different model family after every mutating stage or repair round. The verifier is read-only and receives the plan, actual diff/head, and receipts—not the worker's reasoning transcript.
- Never accept an initialization message, "started," "read the files," a plan of future work, or a bare success claim as completion. Require the receipt in `references/stage-contracts.md`. Ask the same agent once for the missing terminal receipt; replace it if the second return is still incomplete.
- Do not report a worker claim as fact until independent evidence supports it.

## Route Decisions

Classify each decision before acting:

- **Mechanical execution choice:** let the bounded worker decide when the plan and repo patterns determine the answer.
- **Implementation-level judgment:** invoke `paseo-escalate` with a self-contained, read-only brief asking for options, tradeoffs, and a recommendation. The advisor decides nothing. Record its advice; the dispatcher makes and records the decision.
- **Contract, scope, authority, product, or destructive choice:** stop and ask the operator. An advisor may clarify options, but the dispatcher cannot approve the change.

Two consecutive verifier failures on the same stage, an invalidated settled decision, a broken dependency, a post-freeze contract change, secret-shaped output, or an exhausted round/budget is an operator escalation—not another autonomous attempt.

## Execute in Order

Follow the exact stages and gates in `references/stage-contracts.md`:

1. Implement with `ce-work` in return-to-caller mode.
2. Verify implementation completeness against the plan.
3. Simplify eligible code with `ce-simplify-code`.
4. Run the `ce-code-review` review-repair loop, always reviewing again after fixes.
5. Run `ce-test-browser mode:pipeline` when user-visible browser behavior is in scope; repair failures through the mutation lane and repeat code review afterward.
6. Capture each qualifying non-trivial learning with `ce-compound mode:headless depth:full`, one learning per invocation.
7. Commit the attestation candidate with `ce-commit` and require a clean working tree.
8. Run a final `ce-code-review mode:agent` over that exact committed head. No product-code mutation may occur after this gate without invalidating it.
9. Create or update the PR with `ce-commit-push-pr mode:pipeline archive:off branding:on`.
10. Drive the PR through `pr-merge-ready-loop`, which requests Copilot review, uses an independent merge-readiness judge, and delegates CI/review mutation to `ce-babysit-pr` and `ce-resolve-pr-feedback`.

If a PR-stage fix changes the head, require a new Copilot review on that head and a new judge assessment. A review of an older SHA never proves the current head ready.

## Communicate

Report only meaningful state changes using this shape:

- Status
- What changed
- Evidence
- Next step
- Operator input needed, or `none`

Keep raw tool output and agent transcripts out of operator updates. Name plan units or requirements when they materially aid traceability.

## Finish

Return exactly one honest terminal class from `references/stage-contracts.md`. A successful run ends at `ready-to-merge`, with the PR URL, current head SHA, current-head Copilot review, green non-empty CI, independent judge verdict, plan verification summary, documented learnings, and residuals. Say explicitly that the PR was not merged.

Never output DONE merely because a worker stopped, a PR exists, CI was green on an older head, or all feedback visible at one moment was handled.
