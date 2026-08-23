---
title: Arjim Is Packaged as an Agent Distro
date: 2026-08-23
type: product-direction-decision
status: proposed
decision_owner: operator
scope: packaging and interface shape
primary_source: VISION.md
comparison_source: docs/research/firstmate-deep-dive.md
amends: docs/reviews/2026-08-15-001-arjim-direction-recommendation-brief.md
related:
  - docs/plans/2026-08-17-001-feat-workstream-dispatch-loop-plan.md
  - docs/ideation/2026-08-16-firstmate-derived-candidates.md
---

# Arjim Is Packaged as an Agent Distro

## Decision

Arjim is delivered as an **agent distro** — the packaging shape defined at
`docs/research/firstmate-deep-dive.md:13-17`. A portable directory of
instructions, skills, policies, and state conventions turns a general-purpose
terminal coding agent into Arjim. The Python package becomes internal machinery
that Arjim runs, not a command surface the operator types at.

This decides *shape*, not scope. It authorizes no new capability, changes no
milestone sequencing, and does not alter the active dispatch plan.

## What this is not

FirstMate's *product* is not adopted. Agent-fleet supervision, worktrees, the
watcher, spawn/teardown, secondmates, Relay, and the control plane remain
excluded. That exclusion was recorded at
`docs/reviews/2026-08-15-001-arjim-direction-recommendation-brief.md:67-69` and
reaffirmed as a key decision at
`docs/plans/2026-08-17-001-feat-workstream-dispatch-loop-plan.md:42`. Both stand.

The brief's line 67 forbids cloning the product. It does not forbid the
packaging shape, which had no name in the repo when the brief was written. This
record supplies the name and the boundary so the two are not conflated again.

The governing principle already recorded at
`docs/ideation/2026-08-16-firstmate-derived-candidates.md:19-23` — port the
problems, not the mechanisms — applies unchanged. Packaging is a problem
FirstMate solved; its bash toolbelt is the mechanism, and the mechanism is not
inherited.

## Why now

The shape is already being adopted decision by decision, without a name.

- `VISION.md:21-27` states that the operator's interface is Arjim itself, that
  every tool is built for Arjim to run rather than the operator to invoke, and
  that a capability reachable only by typing a command is **not finished**.
- `docs/ideation/2026-08-16-firstmate-derived-candidates.md:64-68` retired the
  "choose a delivery route" candidate on the grounds that Arjim *is* the route.
- C2b (`ideation:74-114`) exists only because a tool's own confirmation prompt
  stops being the operator's authorization once an agent is the one running the
  tool.
- `docs/plans/2026-08-17-001-feat-workstream-dispatch-loop-plan.md:56` specifies
  the dispatch instruction as "prose intended for an agent, not a command line."

Four decisions in three artifacts, all describing an agent-operated Arjim,
none naming it. Naming it converts accretion into design: the layer can be
specified, bounded, and reviewed instead of appearing one requirement at a time.

By the vision's own standard, registration v1 is unfinished — it is reachable
only by typing commands. The repository currently contains no agent layer: no
harness configuration, no skills, and a root `AGENTS.md` that is repository
conventions for agents *building* Arjim, not a job description for an agent
*being* Arjim.

## The non-negotiable constraint

**The agent layer may narrate coverage. It may never compute it.**

`VISION.md:151` requires that unknown is never reported as nothing, and
`VISION.md:136-138` makes the conditions of trust non-negotiable. Confabulated
completeness is a language model's characteristic failure, so no coverage,
freshness, or state derivation may move into prompt text. Derivation stays in
the Python package and stays proved by the conformance corpus; the distro layer
renders results and never originates them.

FirstMate reaches the same conclusion by a different route: its trust
guarantees live in scripts and on-disk state, and its `AGENTS.md` carries
policy rather than computation. Arjim's version of that separation is stronger
because the computation is already contract-bound and executably verified.

## What the distro layer inherits

Adopted as packaging patterns, each to be specified separately before it is
built:

| Pattern | Source | Arjim's form |
|---|---|---|
| An operating contract the agent loads as its job description | `firstmate-deep-dive.md:19-21` | Distinct from repository build conventions — see Q1 |
| Tracked surface versus private per-instance home | `firstmate-deep-dive.md:34-58` | Third tier already exists: workspace-owned truth outlives both |
| Two-tier skills, internal and public standalone | `firstmate-deep-dive.md:509-514` | The public tier is the independent-consumer test (brief R9) made real |
| Operator-facing language is outcomes, never machinery | `firstmate-deep-dive.md:501-505` | Already required by `VISION.md:25` and brief R6 |
| Hard rules stated once, fail-closed, explicit precedence | `firstmate-deep-dive.md:488-495` | `VISION.md` conditions of trust move into the loaded contract |
| One-owner rule: restatement is a defect | `firstmate-deep-dive.md:535-537` | Already practiced across the plan set |

Explicitly not inherited: multi-harness adapter support. FirstMate supports six
harnesses because its captains differ. Arjim serves one operator. Support one
harness and structure the layer so a second is cheap; do not build for six.

## What this changes about existing work

Nothing is resequenced. The dispatch loop remains the active milestone.

One consequence is already in flight and needs no new ruling. Registration's
confirmation reads from stdin (`src/workstream_registration/cli.py:193`, `:243`,
`:287`, `:326`), which presumes a human at the terminal. Under an agent-operated
Arjim that presumption fails, which `VISION.md:161` already anticipates and C2b
already settled: Arjim asserts and records, and never records
`operator-confirmed` for a confirmation it produced itself. The dispatch plan
implements that at R3 (`dispatch-loop-plan:58`). This record only notes that the
distro decision is *why* C2b was necessary, and that registration v1 will need
the same treatment whenever it is next opened.

## Open question

**Q1. Does `AGENTS.md` serve the agent being Arjim, or the agent building
Arjim?** It cannot serve both. FirstMate avoids the collision because its
repository *is* its distro — the source is the toolbelt. Arjim's repository is
both a contract-bound Python product and the distro, and the two readers need
contradictory rules: the builder writes `src/`; Arjim must not. Settle the split
before any distro file is written, or the contract will be edited in two
directions at once.

## The three grounding questions

1. **Which outcome does this make real?** None directly. It is the delivery
   shape through which Outcomes 1, 2, and 4 reach the operator at all, given
   that `VISION.md:25` disqualifies a typed-command surface from counting as
   finished.
2. **What could this make less trustworthy?** Migration of derivation into
   prose. Every trust condition currently proved by the conformance corpus could
   be silently downgraded to an instruction a model may ignore. The constraint
   above exists to forbid exactly that, and any distro artifact that computes
   rather than renders is a defect.
3. **How will the operator know it reduced work?** Not from this record. The
   measurement obligation stays with the active milestone. Packaging may not
   claim reduced effort on architectural grounds.

## Status

Proposed. Becomes settled on operator acceptance, after which Q1 is the first
thing to resolve and `CONCEPTS.md` gains an "Agent distro" entry.
