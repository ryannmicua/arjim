---
date: 2026-08-16
topic: firstmate-derived-candidates
mode: repo-grounded
status: candidate-backlog
source: docs/research/firstmate-deep-dive.md
related: docs/reviews/2026-08-15-001-arjim-direction-recommendation-brief.md
---

# Candidates Derived from the FirstMate Deep Dive

A pickup-able backlog, not a plan and not a commitment. Each entry names what to
build, why it is grounded in `VISION.md`, what must be true before starting it,
and a rough size. Nothing here is authorized; the 2026-08-15 direction brief
still gates expansion behind the pilot.

## The governing principle

Port the *problems* FirstMate solved, not the *mechanisms* it solved them with.
Most of FirstMate's machinery exists because it supervises live processes it
owns — incarnation tokens, per-harness busy-state contracts, turn-end guards,
the control plane, backend adapters. Arjim observes records it does not own and
cannot instrument. Those mechanisms are cost without benefit here.

What is worth taking is FirstMate's **loop discipline**: something observes
without being asked, something remembers what has not been handled, and
something puts the result where the operator already looks
(`firstmate-deep-dive.md:174-181` as read in the direction brief).

## Tier 1 — Build these; they close the loop

### C1. Durable attention-item ledger

**Build:** Stable identity for a needs-me item across checks, plus a durable
disposition (new / seen / deferred / resolved-in-source). An item surfaced last
week and never handled must be distinguishable from one found this morning.

**Why it ranks first:** It is load-bearing for C2 and C4. Without stable item
identity, proactive delivery re-notifies the same item forever, and Arjim cannot
honestly say "you have already seen this." It is a trust property, not a
convenience.

**FirstMate parallel:** the durable wake queue and keyed-decision ledger
(`firstmate-deep-dive.md:190-200`) — acknowledge only after handling, so an
interruption leaves the work durable. Take the semantics; skip the
generation-binding and watcher-crash recovery, which are process supervision.

**Grounding:** Outcome 1 (`VISION.md:47-57`); the boundary rule at
`VISION.md:133-144` — an unhandled item currently reads as a new item.

**Precondition:** none technical. Can start before the pilot concludes.

**Known collision:** KTD12 makes check state fully disposable
(`awareness-tier-plan.md:241`). Item identity must survive `awareness rebuild`
or the ledger is worthless. That likely means item state is workspace-owned
alongside conventions, not in `awareness-state.db` — a real design decision to
settle, not a detail.

**Size:** Medium. **Trust risk:** a stale disposition could suppress a live item;
suppression must fail open.

### C2. A delivery route the operator already attends to

**Superseded in part (2026-08-16):** `VISION.md` now states that the operator's
interface is Arjim itself and that tools are Arjim-operated. Arjim *is* the
delivery route; there is no separate surface to choose. What remains of this
candidate is narrower: what makes Arjim raise something unprompted, and what
evidence it shows about freshness and coverage when it does.

**Build:** One route that puts the consolidated result in front of the operator
without the operator initiating it. Concierge or manual during the pilot;
production infrastructure explicitly deferred.

### C2b. Conversational confirmation evidence

**Build:** A way for a confirmation given in conversation to be carried into a
tool invocation as evidence, so that an operator-authorized write is
distinguishable from an assistant-driven one.

**Why now:** `VISION.md` Conditions of trust #2 now states that a confirmation
step inside a tool proves only that Arjim ran it. Registration and awareness
both rest on exact-digest confirmation (R3, R3b, scaffold), and R19's
attribution enum already has the two actors — `operator-confirmed` and
`assistant-drafted` — but nothing determines which one is truthful under agent
operation.

**Settled (2026-08-16, operator): Arjim asserts and records.** Arjim states that
the operator gave concrete approval in conversation, and records that assertion
alongside what was approved. Concretely: `actor: operator-confirmed` is recorded
only when Arjim asserts a concrete conversational approval for that exact
content; everything else records `assistant-drafted`. The record carries the
digest of the approved content, the UTC time, and the fact that the channel was
a conversational assertion rather than a direct operator action.

**Known limit, to be stated plainly rather than papered over:** this is an audit
record, not proof. It is robust against drift and mistake; it is not robust
against a buggy or compromised Arjim, because Arjim is both the asserting party
and the recording party. Per `VISION.md` Conditions of trust #1, the boundary is
disclosed rather than overclaimed — an operator-confirmed record means "Arjim
asserts you approved this," not "this is independently provable."

**Revisit trigger:** when writes leave Arjim's own reach. Self-assertion is
proportionate while writes are local and single-assistant. It stops being
proportionate at Outcome 4 (filing decisions into shared authoritative records)
and Outcome 6 (a second assistant consuming the attribution), because
attribution then crosses a trust boundary and someone other than the asserting
party relies on it.

**Precondition:** none. Settled before AT-02, which is the configure/confirm
slice.

**Size:** Small. **Trust risk:** a weak evidence scheme silently upgrades
assistant-driven writes to operator-confirmed, which is the exact failure
`VISION.md:150-152` forbids. Mitigated here by disclosure, not by strength.

**Grounding:** Outcome 2 (`VISION.md:59-71`); `VISION.md:20` rejects "another
dashboard I have to maintain," which is what a CLI-plus-Markdown-file surface
becomes. Direction brief R6 and risk 7 (on-demand regression).

**Precondition:** pilot source selected (brief Phase 2), so there is something
worth delivering.

**Size:** Small during the pilot, by design — its purpose is to measure hidden
labor, not to eliminate it.

### C3. First-contact digest

**Build:** Render the ledger plus per-source freshness and coverage on first
contact of the day, in one ordered, bounded block.

**Why:** Nearly free once C1 exists. Copy FirstMate's *conventions* verbatim —
absent versus empty is meaningful, output is bounded, truncation is named rather
than silent (`firstmate-deep-dive.md:99-136`). Skip the nine-stage lock,
bootstrap, and network staging.

**Grounding:** Outcome 2; the three questions at `VISION.md:188` answered from
one view.

**Precondition:** C1.

**Size:** Small.

## Tier 2 — Gated on pilot evidence

### C4. Unprompted checking

**Build:** Scheduled invocation of the existing on-demand path. An OS scheduled
task, not a watcher — Arjim's sources change on hour timescales and need no
absorb-versus-wake classification at 15-second cadence.

**Why the outcome is required:** Outcome 2 is "keeps me posted *without waiting
for me to ask*." The awareness plan concedes v1 does not fulfil it
(`awareness-tier-plan.md:16`, R18).

**Constraint to preserve:** keep AE13's structural assertion that
`src/awareness/` contains no scheduler, timer, daemon, or background thread.
Scheduling lives *outside* the package.

**Precondition:** pilot proves which source is worth polling and at what cadence.

**Size:** Small-to-medium. **Trust risk:** a silently failing schedule produces
confident stale answers; the digest must show last-successful-run age.

### C5. First non-git source, chosen by evidence

**Build:** Whichever source the pilot baseline shows actually causes the
operator's rounds.

**Explicitly not:** porting FirstMate's breadth. That it checks PRs, CI, and
mentions is evidence about FirstMate's user, not this one. Direction brief R3
requires selection from observed burden; local git is a candidate, not a winner.

**Precondition:** brief Phase 1-2 complete.

**Size:** Medium per adapter.

### C6. Unprotected-memory report

**Build:** A report answering "what exists only inside Arjim and is therefore
not protected," plus the wipe-and-rebuild exercise that proves it.

**Why:** This is already a standing obligation at `VISION.md:83` with no
mechanism behind it. FirstMate's `/stow` routes durable knowledge to its most
specific owner (`firstmate-deep-dive.md:472-484`); take that routing idea only.
The tiered memory with aging, decay, and cold archive is ceremony Arjim does not
need.

**Grounding:** Outcome 3 (`VISION.md:73-83`).

**Size:** Small for the report; medium for the rebuild test.

### C7. Discovery as scan-and-offer

**Build:** Bounded scan of approved roots that *offers* candidate workspaces for
operator confirmation. Never auto-registers.

**Why deferred, not dropped:** explicit inventory is a disclosed pilot
limitation (brief:53), and it leaves `global_registration_completeness`
permanently `unknown` (R5b). The inventory is also the one non-reconstructible
artifact in the design (R20). But this is idea 6 in the 2026-08-01 ideation
already; it does not need FirstMate to justify it.

**Precondition:** pilot shows inventory maintenance is a real burden.

**Size:** Medium.

### C8. Session-level concurrency story

**Build:** Whatever concurrent `awareness` invocations against one store
actually require — possibly nothing beyond what SQLite already gives.

**FirstMate parallel:** the per-home session lock with a named READ-ONLY
degraded mode (`firstmate-deep-dive.md:105-108`). The *degraded mode being
named rather than silent* is the part worth copying.

**Precondition:** concurrency actually bites. Do not pre-build.

**Size:** Small.

## Tier 3 — Recorded and deliberately not building

Kept here so they are not re-litigated from scratch.

| Candidate | Why not now | Reconsider when |
|---|---|---|
| Fleet-snapshot JSON contract | The report artifact already serves this; brief R8 warns against a second contract before a second consumer exists | A second consumer appears (see C9) |
| Condition→action watches ("notify when X") | This is C1 + C4 generalized; premature before either exists | C1 and C4 are both shipped and used |
| Write/action tier with graduated authority | Deferred *by design*; `VISION.md:97` requires awareness trust to be earned first. Building it now inverts the vision's own sequencing | Pilot returns "continue" and awareness is trusted in practice |
| Multi-device / multi-instance (secondmates, remote homes) | Outcome 5 mechanism is undesigned by intent (`VISION.md:113`) | Outcomes 1-4 are real |
| Self-update, version floors, bootstrap consent | Single operator, single repo — no fleet to keep converged | Arjim runs somewhere Arjim does not control |
| Per-harness adapters, control plane, teardown, Relay | Belongs to supervising owned processes. Not Arjim's job (brief:67-69) | Never, as a port. FirstMate may become a *source* Arjim observes (brief:171) |

### C9. Independent-consumer test (already in the brief)

Not a FirstMate learning, but it decides the fate of the Tier 3 snapshot-contract
row: brief R9 asks whether a reader other than the Python implementation can
consume the marker usefully. Its answer determines whether contract investment is
interoperability or ceremony.

## Sequencing

C1 → C2 → C3, then pilot outcome, then C4. C5 depends on pilot source selection.
C6 is independent and can be picked up any time. C7 and C8 wait for demonstrated
need.

This does not conflict with the direction brief. C1 is plausibly the "minimum
durable state required" its Phase 2 step 5 asks the pilot to identify, and C2
and C3 are what its R6 delivery requirement becomes once "concierge" stops being
a hand-wave.

## The three grounding questions, answered for this set as a whole

1. **Which outcome does this make real?** C1-C4 make Outcome 2's *unprompted*
   half real; C1 makes Outcome 1 honest across time rather than per-invocation;
   C6 discharges Outcome 3's stated proof obligation.
2. **What could this make less trustworthy?** Suppression. Every mechanism here
   that hides something from the operator — a disposition, a schedule, a digest
   bound — is a new way to under-report. Each must fail open and name its own
   failure, per `VISION.md:144`.
3. **How will the operator know it reduced work?** Only through the pilot's
   measurement (brief R7). None of these items may claim reduced effort on
   architectural grounds.
