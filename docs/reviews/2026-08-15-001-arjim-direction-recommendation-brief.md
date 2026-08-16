---
title: Arjim Direction Recommendation Brief
date: 2026-08-15
type: product-direction-recommendation
status: proposed
decision_owner: operator
acceptance_owner: operator
primary_source: VISION.md
comparison_source: docs/research/firstmate-deep-dive.md
review_route: codex/gpt-5.6-luna plus repository-grounded primary audit
recommendation: narrow-and-continue
---

# Work Brief: Validate Arjim's Daily Awareness Loop

## Executive Recommendation

Continue Arjim, but narrow and reorder the next milestone.

Arjim is building the right foundational technology: durable workspace-owned truth, explicit uncertainty, replaceable local state, and gradually earned authority. The implementation is rigorous and aligned with the product's conditions of trust. The product risk is sequencing. Arjim has built a highly complete registration subsystem before proving the daily management loop that should make the operator stop checking other tools.

Freeze further registration expansion. Do not execute the current awareness-tier plan unchanged as one U1-U11 program. Treat it as a design reference and contract inventory. First validate the smallest real loop that can answer, for a few actual workstreams:

1. What needs me?
2. What changed?
3. What could Arjim not verify?

The next milestone should be **one trustworthy daily management loop**, not **complete awareness infrastructure**.

The decisive product test is:

> After registration, does Arjim let the operator retire a recurring tool-checking round, or does it become another system the operator must maintain?

## Decision Summary

### Preserve

- Workspace-owned `.workstream/manifest.json` authority.
- The replaceable local projection.
- Exact confirmation, create-only writes, conditional updates, and read-back verification.
- No-echo, bounded-diagnostic, and fail-closed guarantees.
- The existing Workstream Registration v1 contract and conformance suite.
- The Workstream Protocol as a lightweight assistant-neutral boundary.
- The vision's distinction among current, stale, nothing found after a complete check, inaccessible, unsupported, and not checked.

### Change

- Replace the next all-at-once infrastructure shipment with a pilot-sized vertical slice.
- Select the first checking adapter from observed operator burden, not from implementation convenience.
- Make the first useful attention answer the acceptance criterion.
- Deliver the result to the operator during the pilot instead of requiring the operator to remember another command.
- Measure setup friction and recurring work removed before expanding contract and connector breadth.
- Treat explicit inventory as a disclosed pilot limitation, not the intended long-term discovery architecture.

### Defer

- Additional runtimes.
- Registry publishing.
- Generalization beyond workstreams.
- Cross-device reconstruction.
- Multi-assistant coordination.
- Broad connector architecture beyond the first validated source.
- Production-grade scheduling and notification infrastructure.
- New protocol version spaces and broad conformance machinery not required by the pilot slice.
- Further registration hardening unless a demonstrated defect requires it.

### Explicit Non-Recommendation

Do not pivot Arjim into a FirstMate clone. FirstMate manages agent execution and software delivery. Arjim's intended job is cross-workstream awareness and, later, administration of authoritative records. FirstMate is a model for closing a narrow user loop, not a replacement product direction.

## Purpose

Prove or disprove that Arjim's trustworthy-awareness thesis reduces the operator's real management burden before investing further in generalized protocols, state machinery, adapters, discovery, and conformance.

This work is needed because the existing registration capability is technically complete but does not yet deliver the near-term promise in `VISION.md`: a trustworthy view of every registered workstream, the items needing attention, and the boundary of what Arjim could verify.

## Outcome

At completion, the operator has evidence from 3-5 real workstreams showing whether a thin Arjim awareness loop can replace at least one recurring tool-checking round without creating false reassurance or disproportionate setup work.

The work ends with one of three recorded decisions:

- **Continue:** the pilot replaces a meaningful recurring check and justifies expanding awareness.
- **Rework:** the loop is useful, but source choice, setup friction, delivery, or semantics must change before expansion.
- **Narrow or stop:** the loop does not reduce work enough to justify further platform investment.

## Why This Recommendation

### What Is Proven

The current executable product is Workstream Registration v1:

- A Python CLI implements `register`, `inspect`, `link`, `rebuild`, `unregister`, `resolve-invalid`, and `recover-lock`.
- Registration uses a durable marker, exact confirmation, create-only writes, stable filesystem identities, cooperative locks, read-back verification, bounded diagnostics, and a replaceable SQLite projection.
- The implementation contains approximately 6,036 lines of Python and 4,966 lines of Python tests.
- The registration contract contains approximately 1,939 lines across six versioned contract files.
- Repository verification on 2026-08-15 produced `368 passed, 1 skipped`.
- The Workstream Registration conformance runner passed all 87 mandatory fixtures, lifecycle and rebuild end-to-end checks, state-table checks, CLI-contract checks, the blacklist, and the canary no-echo scan.

The technical substrate is therefore credible. This recommendation does not propose rewriting it.

### What Is Not Proven

The repository contains no implemented awareness package or awareness contracts. The following remain unbuilt:

- Checking adapters.
- Workstream configuration for awareness semantics.
- Portfolio, needs-me, changed, and current-status answers.
- Freshness evaluation.
- Machine discovery or registry consumption.
- Proactive delivery.
- External-system connectors.
- Cross-device reconstruction.
- The vision's 30-day management-effort baseline.
- Evidence that routine tool visits have decreased.

The existing awareness plan acknowledges that registration is the only working capability and that awareness is designed but unbuilt.

### The Sequencing Problem

The active awareness design is roughly 1,010 lines, plus roughly 953 lines of decomposition. It specifies eleven implementation units, five independent version spaces, workspace conventions, a durable inventory, a separate awareness-state database, references-only reports, opaque Git baseline tokens, scaffolding, privacy matrices, and a dedicated conformance runner.

The same plan intentionally defers:

- Proactive delivery.
- Lifecycle state.
- A dedicated current-status view.
- Machine discovery.
- Planner, SharePoint, and email connectors.
- Non-Git change detection.
- Effort-baseline capture.
- Evaluation of the vision's 75% reduction target.

Its only supported v1 source is local Git. Its minimum needs-me rules cover unresolved merge, rebase, or cherry-pick conflicts and being behind a configured local tracking ref. That may be useful, but the repository contains no evidence that these conditions cause the operator's current management rounds.

The plan can therefore pass extensive technical gates while still failing the product promise: "I stop doing the rounds."

## FirstMate Comparison

### FirstMate's Product Loop

The supplied FirstMate research describes a complete software-delivery supervision loop:

1. The captain makes a request.
2. FirstMate resolves and briefs the work.
3. A crewmate works in an isolated worktree.
4. A tokenless watcher absorbs routine activity and wakes the first mate only for actionable state.
5. Durable status and wake records survive conversation failure.
6. Work is delivered as a PR, approved local merge, or investigation report.
7. Teardown fails closed until work is proven landed or safely retained.

The value is visible because the loop terminates in a user-relevant outcome.

### Productive Convergence

Arjim and FirstMate both:

- Reject conversation memory as authority.
- Keep important state durable across restarts.
- Fail closed when state is ambiguous.
- Distinguish unknown from success.
- Make authority explicit.
- Treat recovery and attribution as product behavior.

### Productive Differentiation

- FirstMate manages agent execution and delivery.
- Arjim should manage awareness across workstreams and authoritative record sources.
- FirstMate's durable state is private operational state.
- Arjim's marker is shared workspace state intended to be readable by multiple conforming assistants.
- FirstMate can eventually be one source Arjim observes rather than a product Arjim duplicates.

### Lesson to Adopt

Adopt FirstMate's loop discipline:

- Begin with a narrow job.
- Complete the loop through an operator-relevant result.
- Keep monitoring silent until attention is required.
- Surface decisions and outcomes instead of internal machinery.
- Make delivery and recovery part of the acceptance criteria.

Do not copy its harness adapters, agent-fleet supervision, secondmate hierarchy, Relay, or delivery-control machinery into Arjim.

## Dates

- **Recommendation date:** 2026-08-15.
- **Pilot duration:** 10 business days after the operator selects the pilot workstreams.
- **Implementation timing:** decided only after the pilot identifies the first source and validates its needs-me semantics.
- **Hard deadline:** none established.

The pilot is intentionally shorter than the vision's eventual 30-day baseline. It is a high-information product-direction test, not the final measurement period for the 75% reduction target.

## Roles

- **Decision owner:** Operator.
- **Acceptance owner:** Operator.
- **Pilot operator:** Operator, with Arjim or an assisting agent producing the daily result.
- **Work owner:** The implementation session or agent assigned after the source-selection decision.
- **Advisor evidence:** Native `codex/gpt-5.6-luna` review plus the repository-grounded primary audit performed on 2026-08-15.

## Scope

### In Scope

- Select 3-5 real workstreams representative of the operator's actual management burden.
- Record the operator's normal checking rounds and the questions that trigger them.
- Record true needs-me items, meaningful changes, missed items, inaccessible sources, and unsupported sources.
- Measure registration and configuration effort.
- Select the first source based on observed burden and signal quality.
- Define the smallest needs-me and changed semantics for that source.
- Build or simulate one thin vertical awareness slice.
- Produce one operator-facing daily result during the pilot.
- Preserve honest freshness and coverage in every answer.
- Compare Arjim's result with the operator's normal tool rounds.
- Record a continue, rework, or narrow/stop decision.
- Identify which parts of the existing awareness plan remain justified after the pilot.

### Out of Scope

- Rewriting Workstream Registration v1.
- Implementing all awareness U1-U11 units as currently decomposed.
- Claiming global workstream completeness from explicit inventory.
- Supporting every declared record-source type.
- Building production scheduling infrastructure.
- Performing workstream delivery work.
- Shared authoritative writes or action-tier automation.
- Cross-device synchronization or reconstruction.
- Assistant-to-assistant coordination.
- Generalizing the Workstream Protocol to projects, people, processes, or recurring responsibilities.
- Building a FirstMate-style coding-agent supervisor.

## Requirements

### R1. Real-Workstream Grounding

The pilot must use 3-5 current workstreams that the operator genuinely checks. Synthetic fixtures may test mechanics but cannot establish product value.

### R2. Baseline Capture

For each pilot workstream, record:

- Which tools or sources the operator checks.
- What question caused each check.
- Time spent checking.
- What required attention.
- What changed but did not require attention.
- What was unavailable or could not be verified.
- Whether the check could reasonably have been skipped if Arjim's result existed.

### R3. Source Selection

Choose the first source only after baseline observation. Selection should favor:

- High frequency in normal checking rounds.
- High concentration of meaningful needs-me signals.
- Authoritative structured state.
- Read-only access suitable for the trust tier.
- A result that can retire or materially shorten a recurring operator round.

Local Git is a candidate, not a predetermined winner. Planner, email, SharePoint, GitHub state, or a FirstMate fleet snapshot may be stronger candidates if the evidence shows they cause more management work.

### R4. Thin Vertical Slice

The slice must traverse one complete path:

1. Resolve registered pilot workstreams.
2. Check the selected authoritative source.
3. Produce one immutable observation per check.
4. Classify freshness and coverage.
5. Derive needs-me items and meaningful changes.
6. Render checked, failed, inaccessible, unsupported, and not-checked sources explicitly.
7. Deliver one consolidated result to the operator.

### R5. Trust Boundary

- Never report `nothing-pending` unless every required source for that answer was successfully checked within its declared freshness window and at least one applicable needs-me rule was evaluated.
- Never turn missing, inaccessible, unsupported, stale, or unchecked state into an empty result.
- Keep source records authoritative; Arjim's observation remains a working view.
- Use read-only access during the pilot except for existing confirmed workspace-registration behavior.
- Do not copy credentials, tokens, or unnecessary source content into reports or durable state.

### R6. Operator Experience

- The pilot result must be presented in management language.
- Internal machinery, adapters, tokens, projections, and database details should appear only in diagnostics when needed.
- The primary result must answer what needs attention, what changed, and what remains unknown.
- During the pilot, delivery may be concierge or use existing orchestration. A production scheduler is not required.

### R7. Measurement

Measure:

- Routine checking rounds before and during the pilot.
- Time spent checking authoritative tools.
- True attention items found by Arjim.
- Attention items missed by Arjim.
- False-positive needs-me items.
- False `nothing-pending` claims.
- Setup and configuration time.
- Number of times the operator still opens the source to verify Arjim's answer.
- Whether at least one recurring round can be retired.

### R8. Protocol Restraint

- Reuse the existing registration contract.
- Add only the minimum awareness contract needed for the selected source and pilot result.
- Do not introduce a new version space, database, scaffold, or artifact unless the vertical slice cannot be made trustworthy without it.
- Record deferred generalization rather than implementing it speculatively.

### R9. Independent-Consumer Test

Ask one independent reader or assistant to consume the existing Workstream Protocol marker without relying on Arjim's Python implementation. Use the result to decide whether assistant-neutral standardization is creating real interoperability or only internal ceremony.

### R10. Roadmap Decision

At pilot completion, map the evidence back to the existing awareness plan:

- Keep units required by demonstrated behavior.
- Simplify or resequence units whose contracts exceed the validated loop.
- Defer units with no observed user value.
- Replace Git-specific assumptions if another source wins selection.

## Constraints, Risks, and Dependencies

### Constraints

- `VISION.md` remains canonical product authority.
- Trust conditions in `VISION.md` are non-negotiable.
- Registration behavior must not regress.
- The pilot operates read-only against record sources.
- The operator's existing `docs/research/firstmate-deep-dive.md` remains comparison evidence, not an implementation specification.
- The tested registration profile is CPython 3.14.6 on Windows NTFS; POSIX paths are implemented but unproven on this host.

### Risks

1. **Pilot source bias.** Selecting Git because it is easy to implement may validate engineering convenience rather than operator value.
2. **Concierge illusion.** Manual preparation may hide future integration cost. Record the manual steps and time explicitly.
3. **Configuration burden.** Registration, inventory, conventions, and source mapping may cost more than the recurring checks they replace.
4. **False reassurance.** An incomplete source set may appear comprehensive if coverage language is not prominent.
5. **Overfitting.** A loop that works for one software repository may not generalize to Planner, email, or shared initiatives.
6. **Protocol inflation.** A second large contract may form before a second consumer or demonstrated user behavior exists.
7. **On-demand regression.** A command-only result may reproduce the need to remember and initiate every check.
8. **Measurement noise.** Ten business days may contain too few attention events. Treat low event volume as inconclusive rather than successful.

### Dependencies

- Operator selection of representative pilot workstreams.
- Read access to their authoritative sources.
- A lightweight capture method for normal checking rounds.
- Existing Workstream Registration v1 behavior.
- A source-specific definition of needs-me and meaningful change.
- A delivery route the operator will actually see during the pilot.

## Assumptions

- The operator is both the product owner and initial user.
- A 10-business-day pilot is sufficient to choose the first source and detect obvious value or friction, but not to validate the final 75% reduction target.
- Existing registration is stable enough to freeze during the pilot.
- The first useful slice may be narrower than the existing awareness plan.
- Manual or concierge delivery is acceptable for learning, provided its hidden labor is measured.
- No deadline requires shipping the full awareness plan before the pilot concludes.

## Deliverables

1. **Pilot baseline and observation log** covering 3-5 real workstreams for 10 business days.
2. **First-source decision record** explaining why the selected source is the highest-leverage awareness target.
3. **Thin awareness slice** or faithful concierge simulation covering source check, freshness, coverage, needs-me, changed, and delivery.
4. **Pilot evaluation report** comparing Arjim's answers with normal operator rounds.
5. **Revised awareness roadmap decision** identifying what to keep, change, defer, or stop in the current plan.
6. **Independent-consumer note** recording whether another assistant or reader can consume the Workstream Protocol marker usefully.
7. **Documentation corrections** for known factual drift in the registration contracts README and test-count reference.

## Acceptance Criteria

### Deliverable: Pilot Baseline and Observation Log

1. The log covers at least three real, active workstreams.
2. It spans ten business days or records an operator-approved reason for stopping early.
3. Each checking round records source, question, time spent, result, and whether action was required.
4. Attention items, meaningful non-attention changes, failures, and unknowns are distinguishable.
5. The log contains enough evidence to rank candidate first sources.
6. Sensitive source content is excluded unless required for the evaluation.

### Deliverable: First-Source Decision Record

1. The selected source is supported by baseline frequency and operator-burden evidence.
2. At least two credible alternatives are compared.
3. The record defines the selected source's authoritative state.
4. It defines the initial needs-me rules and meaningful-change rules.
5. It identifies required access, freshness, and failure semantics.
6. If Git is selected, the record explains why local Git state is a recurring management burden rather than merely easy to implement.

### Deliverable: Thin Awareness Slice

1. The slice checks the selected source for every included pilot workstream.
2. Every result shows check time, freshness, and coverage.
3. Failed, inaccessible, unsupported, stale, and not-checked sources remain visible.
4. `nothing-pending` is impossible under incomplete or stale coverage.
5. Needs-me items identify the workstream, source, and requested action.
6. Meaningful changes remain separate from needs-me items.
7. The operator receives one consolidated result without visiting each source first.
8. The slice does not modify authoritative source records.
9. Registration conformance remains green.

### Deliverable: Pilot Evaluation Report

1. The report compares Arjim's output with the operator's actual rounds.
2. It records true positives, missed items, false positives, and false `nothing-pending` claims.
3. The acceptable number of false `nothing-pending` claims is zero.
4. It records setup, configuration, and ongoing maintenance time.
5. It identifies whether at least one recurring checking round can be retired or materially shortened.
6. It distinguishes an inconclusive low-event pilot from a successful pilot.
7. Any exceptions or trust failures are documented.

### Deliverable: Revised Awareness Roadmap Decision

1. The decision is recorded as continue, rework, or narrow/stop.
2. Every retained implementation unit maps to observed pilot behavior or a non-negotiable trust condition.
3. Deferred units have an explicit reason and trigger for reconsideration.
4. Source-specific assumptions are not generalized without evidence.
5. The decision states whether the existing U1-U11 plan is superseded, revised, or retained as a later architecture reference.
6. The operator approves the decision before implementation expands.

### Deliverable: Independent-Consumer Note

1. A consumer other than the existing Python implementation attempts to read a valid marker.
2. The note records what was understandable from the contract alone.
3. Any Arjim-specific hidden assumptions are identified.
4. The result explicitly supports either continued standardization investment or a decision to keep the protocol minimal.

### Deliverable: Documentation Corrections

1. `contracts/workstream-registration/README.md` no longer says the implementation is unimplemented while later calling it implemented.
2. `docs/usage/reference.md` no longer freezes a stale test-count claim, or it reports the verified current count with an appropriate date.
3. The corrections do not alter contract behavior.
4. Documentation verification passes.

## Decision Gates

### Continue

Continue expanding awareness when all of the following are true:

- No false `nothing-pending` claim occurred.
- The operator trusts the source coverage shown.
- At least one recurring checking round can be retired or materially shortened.
- Setup and maintenance effort are acceptable relative to recurring work removed.
- The first source produces meaningful attention signals often enough to justify continued investment.
- The operator prefers receiving the consolidated result over performing the prior round.

### Rework

Rework before expanding when any of the following are true:

- The result is useful but requires excessive configuration.
- The selected source is too narrow or low-signal.
- The operator repeatedly opens the source to verify Arjim.
- Delivery is too easy to miss.
- Needs-me rules confuse changes with required action.
- Explicit inventory creates unacceptable completeness uncertainty.

### Narrow or Stop

Narrow the product further or stop awareness-platform investment when any of the following are true:

- No routine checking round can be retired.
- Setup and maintenance cost exceed the recurring work removed.
- The operator does not use or trust the consolidated result.
- Attention semantics cannot be derived reliably from authoritative sources.
- The product requires extensive source-specific machinery without producing a meaningful management outcome.

## Work Plan

### Phase 0: Freeze and Prepare

1. Freeze new registration capabilities and protocol expansion.
2. Preserve the registration suite as a regression gate.
3. Correct the two known documentation drift items.
4. Choose 3-5 pilot workstreams.
5. Create a lightweight observation log.

### Phase 1: Observe the Existing Rounds

1. Record normal management checks for ten business days.
2. Capture the question behind each check.
3. Classify findings as needs-me, meaningful change, informational noise, or unknown.
4. Rank sources by frequency, time cost, and actionable-signal density.

### Phase 2: Select and Specify the First Source

1. Compare at least two candidate sources.
2. Choose the source most likely to retire a recurring round.
3. Define its minimum needs-me and changed semantics.
4. Define freshness, coverage, unavailable, unsupported, and failure behavior.
5. Identify the minimum durable state required.

### Phase 3: Produce the Thin Vertical Slice

1. Reuse registered workstream identities.
2. Check the selected source read-only.
3. Derive a single observation and consolidated result.
4. Deliver the result through a route the operator already attends to.
5. Keep the mechanics minimal and record manual effort.

### Phase 4: Evaluate

1. Compare the result with normal rounds.
2. Measure misses, false positives, trust failures, setup effort, and work removed.
3. Ask whether the operator can retire a recurring check.
4. Classify the outcome as continue, rework, or narrow/stop.

### Phase 5: Reframe the Roadmap

1. Map validated behavior to the current awareness plan.
2. Retain trust requirements that protected real answers.
3. Remove or defer speculative infrastructure.
4. Resequence implementation around vertical user outcomes.
5. Seek operator approval before starting the expanded implementation.

## Documentation and Strategy Notes

- `VISION.md` is present and serves as canonical product authority.
- No `STRATEGY.md` exists, so there is no vision/strategy conflict to resolve. Product prioritization currently lives directly in implementation plans.
- Root `AGENTS.md` instructs agents to use `VISION.md` and answer its three grounding questions, but it does not define a future `VISION.md` to `STRATEGY.md` precedence rule or alignment-check trigger.
- Do not create additional strategy ceremony during the pilot. If a `STRATEGY.md` is later introduced, derive it from pilot evidence and state that `VISION.md` governs conflicts.

## Repository Evidence

- `VISION.md:14-20` defines Arjim as the one assistant the operator can talk to about all work and rejects another maintained dashboard.
- `VISION.md:30-34` makes trustworthy awareness the near-term promise.
- `VISION.md:47-69` defines needs-me and keeps-me-posted outcomes.
- `VISION.md:133-150` defines honest knowledge boundaries and authority levels.
- `VISION.md:172-210` defines the pilot and reduction-of-management-work tests.
- `VISION.md:212-220` requires every new work item to name the outcome, trust risk, and evidence of reduced work.
- `README.md:7-23` identifies registration as the implemented capability and states its deferred boundaries.
- `contracts/workstream-registration/README.md:20-29` defers discovery, status, progress, freshness, cross-device reconstruction, and additional runtimes.
- `docs/plans/2026-08-09-001-feat-awareness-tier-plan.md:14-45` defines the planned awareness foundation and its limits.
- `docs/plans/2026-08-09-001-feat-awareness-tier-plan.md:146-168` defers the 30-day baseline, 75% reduction evaluation, proactive delivery, external connectors, lifecycle state, and current-status view.
- `docs/plans/2026-08-09-001-feat-awareness-tier-plan.md:963-975` selects Git as the only v1 adapter and defines five version spaces.
- `docs/research/firstmate-deep-dive.md:60-97` describes FirstMate's complete intake-to-delivery loop.
- `docs/research/firstmate-deep-dive.md:138-230` describes its watcher, durable wake queue, semantic busy state, and turn-end guards.
- `docs/research/firstmate-deep-dive.md:247-370` describes delivery, authority, and fail-closed teardown.

## Done Means

This brief is fulfilled when the operator has evidence—not architectural confidence alone—that a small Arjim awareness loop can replace a recurring management round while preserving honest uncertainty.

Completion requires:

- A 3-5-workstream pilot.
- A baseline of real checking behavior.
- Evidence-based selection of the first source.
- One complete source-to-attention-to-delivery loop.
- Zero false `nothing-pending` claims.
- Measured setup and ongoing effort.
- A recorded continue, rework, or narrow/stop decision.
- An operator-approved revision to the awareness roadmap before broader implementation begins.

Until those conditions are met, the current awareness plan should remain a design reference rather than an authorized all-at-once execution program.
