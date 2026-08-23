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

## Q1 — resolved in proposal: role follows the checkout

**The question.** Does `AGENTS.md` serve the agent being Arjim, or the agent
building Arjim? It cannot serve both: the builder writes `src/`; Arjim must not.

FirstMate offers no answer to copy. Its two contracts never collide because the
firstmate home is never one of its own projects — the job description and a
project's build conventions live in different repositories
(`firstmate-deep-dive.md:476-478`). Arjim, once dogfooded, is one of its own
workstreams and hits a case the source design does not have.

**Proposed resolution.** The collision exists only when one directory holds both
roles. It dissolves across two checkouts of the same upstream:

- **Distro home** — a harness launched here becomes Arjim. Arjim writes to `src/`
  nowhere, here included. This is FirstMate hard rule 1
  (`firstmate-deep-dive.md:488`) and the dispatch plan's file-and-walk-away
  posture (`dispatch-loop-plan:42`) reaching the same place.
- **Workstream workspace** — an ordinary checkout, registered, that Arjim
  dispatches builder agents into. Dispatch R5 already requires a registered
  target.

No new mechanism is introduced; this is the tracked-home versus project split
(`firstmate-deep-dive.md:34-58`) applied to the self-referential case.

**File placement that follows.**

| File | Role | Present state |
|---|---|---|
| `AGENTS.md` (root) | Arjim's job description; clone and launch yields Arjim (`firstmate-deep-dive.md:19-21`) | Currently holds build conventions |
| `CLAUDE.md` | Symlink to `AGENTS.md` | Absent — the symlink is free to establish |
| `CONTRIBUTING.md` | Build conventions, relocated from today's `AGENTS.md` | Absent |

A dispatched builder loses nothing by the move: it arrives carrying prose
instruction (dispatch R1) that names `CONTRIBUTING.md`, so its context comes
through the instruction rather than ambient file loading.

**Disclosed weakness.** A session opened directly against the repository to
build Arjim will auto-load Arjim's job description and behave as Arjim,
refusing to write `src/`. The mitigation is a fixed routing block at the head of
`AGENTS.md` rather than a judgment call. This is the one point where the distro
layer depends on the agent reading correctly; the failure mode is a confused
builder, not a false trust claim, so it is disclosed rather than engineered
around.

**Rejected: two repositories.** Clean role separation, but premature — brief R8
warns against a second contract before a second consumer, the layers will
co-evolve tightly, and there is one operator. Reconsider when the distro is
installed somewhere that does not contain the product.

## Open question

**Q2. What is workspace identity when the workspace is a distributed VCS working
tree?** Surfaced by dogfooding: `.gitignore` does not list `.workstream/`, so a
marker written into this repository is committed by default.

The marker carries a permanent Arjim-generated identity (`CONCEPTS.md`, Marker)
and pins `workspace` to the literal `.` (KTD4) precisely so no device path can
break cross-device identity. Both presume the workspace is one durable location.
A clone breaks that presumption in each direction:

- **Committed** — every clone carries the same workstream identity, including
  the distro home and the workspace checkout that Q1 above separates into
  different roles. One identity in two places is the inverse of the second-identity
  hazard KTD7 guards against.
- **Ignored** — the marker does not survive a fresh clone. Outcome 3
  (`VISION.md:80-90`) requires workstream memory to survive an *Arjim* wipe and
  is silent on whether a fresh clone is the same workspace or a new one.

This is a Workstream Protocol question rather than a dogfooding detail, and it
is unresolved in the contract set. It needs an operator ruling before the
repository is registered.

## Dogfooding note

Registering this repository as a workstream is available with shipped code and
is the natural test of Q1's two-checkout resolution. It proves *mechanism* only.
Per brief Risk 1, it may not be counted as pilot evidence of reduced management
work: the operator does not perform checking rounds on this repository the way
the pilot's candidate sources demand.

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

Proposed, including Q1's resolution. Becomes settled on operator acceptance.

Q2 blocks registering this repository but blocks nothing else. On acceptance,
`CONCEPTS.md` gains an "Agent distro" entry, and the `AGENTS.md` to
`CONTRIBUTING.md` relocation is the first concrete change.
