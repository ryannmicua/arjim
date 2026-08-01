---
title: Python Registration Plan Rewrite - Plan
type: docs
date: 2026-08-02
origin: docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md
execution: knowledge-work
---

# Python Registration Plan Rewrite - Plan

## Objective

Rewrite `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md` in place as one implementation-ready plan for a Python workstream-registration product.
The rewrite will retain a portable workspace marker and durable behavioral contracts without presenting the system as a runtime-neutral adapter ecosystem.

The existing plan and its published Proof document remain unchanged until this approach is executed.

---

## Inputs and Authority

- `VISION.md` remains product authority, especially durable workspace memory, honest access boundaries, operator-confirmed writes, and reduced management work.
- `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md` supplies the Product Contract, settled decisions, implementation detail, and stable identifiers to preserve where their concepts survive.
- `docs/research/2026-08-01-workstream-registration-runtime-stack.md` supports the settled CPython 3.14.x, `jsonschema` 4.26.x, raw-input, filesystem, and SQLite choices.
- `docs/raid.md` must be reconciled with the rewritten plan because it cites the current plan and contains runtime and secret-handling assumptions derived from earlier revisions.
- For files carrying `proof_url`, the local markdown remains canonical and the Proof editing protocol in `AGENTS.md` governs synchronization.

---

## Rewrite Strategy

### Preserve the Product Contract

Keep the existing problem frame, actors, flows, requirements, acceptance examples, and scope boundaries unless the Python-only direction makes a statement demonstrably false.
Preserve stable KD, R, F, and AE identifiers; when removing or consolidating an item, leave gaps and repair every `Governs`, `Covers`, and inline reference instead of renumbering.
Record the rewrite as a Product Contract restructuring with no product-scope change unless review identifies a real behavioral change requiring operator approval.

### Replace the Adapter Architecture

State CPython 3.14.x as the v1 product runtime and treat `src/workstream_registration/` as the implementation, not a reference adapter.
Remove the contract-first/reference-adapter split, multi-runtime compatibility claims, adapter SDK framing, and obligations whose only purpose is future language implementations.
Continue to describe `.workstream/workstream.json`, JSON schemas, stable results, and fixtures as portable workspace-data and behavioral contracts because those surfaces protect durable memory and cross-device readability.

### Reassign Technical Decisions

Replace KTD1 with the single-runtime delivery decision and consolidate the current runtime-selection material around it.
Retain the raw-input, redacted-diagnostic, create-only write, read-back, interruption-recovery, conditional-delete, and replaceable-projection decisions because they protect trust independently of runtime portability.
Rewrite each retained KTD so a contract invariant has one owner and Python mechanisms appear only in the implementation decision that realizes it.

### Rebuild the Delivery Sequence

Organize the work as one dependency chain:

1. Establish the Python package, pinned runtime dependencies, schemas, result vocabulary, and test harness.
2. Build the bounded raw-input and Draft 2020-12 validation pipeline with normalized diagnostics.
3. Implement registration inspection, exact confirmation, create-only publication, read-back, and recovery.
4. Implement confirmed unregister and the replaceable SQLite projection.
5. Expose the operator CLI and prove the complete point-and-read lifecycle.

Retain existing U-IDs when a unit's central concept survives; assign new IDs only when units are split and leave gaps for deleted units.
Remove the separate `Reference Adapter Units` phase and any unit that exists only to publish cross-runtime adapter guidance.

### Tighten Verification

Keep the project-owned schema, raw-byte, transition, lifecycle, permission, concurrency, interruption, projection, CLI, no-network, and no-echo tests.
Do not require Bowtie or the complete upstream JSON Schema Test Suite as product release gates unless the rewrite finds a product-specific need to revalidate the third-party validator.
Replace cross-runtime compatibility declarations with a supported Python/runtime/filesystem profile when such a declaration remains useful.
Maintain the stop condition that point-and-read registration cannot be claimed until the Python CLI completes the authoritative write/read-back lifecycle and its project conformance corpus passes.

---

## Deliverable Shape

The rewritten source plan will remain at `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md` with `artifact_contract: ce-unified-plan/v1`, `artifact_readiness: implementation-ready`, and `execution: code`.
Its title, Goal Capsule, Planning Contract, implementation-unit structure, Verification Contract, Definition of Done, and work-relationship summary will consistently describe one Python implementation.

The rewrite will also update `docs/raid.md` so its source references and active assumptions agree with the plan.
The existing Proof document for each changed file will be read at its current revision and updated from the final local markdown.

---

## Defaults and Boundaries

- Python is the only active runtime; Node, Java, and a general adapter ecosystem are deferred.
- The JSON marker remains portable data, but runtime-neutral executable behavior is not an active deliverable.
- The CLI is the v1 operator surface; machine scanning, registry consumption, portfolio awareness, and broader automation remain deferred.
- `compatibility.md` is retained only if it becomes a concrete Python and filesystem support declaration; otherwise its obligations move into the plan and tests or are removed.
- Exact dependency patch versions remain an implementation-start decision unless current repository manifests already establish them when the rewrite executes.
- No code, schemas, fixtures, or runtime behavior are implemented as part of the document rewrite.

---

## Review and Completion Checks

- The rewritten plan answers the three questions in `VISION.md`: which outcome it advances, what could reduce trust, and how successful registration will reduce operator work.
- Product behavior and stable identifiers are preserved or explicitly accounted for; no removed adapter language silently deletes a trust requirement.
- Every retained rule has one normative owner, and summaries, KTDs, units, tests, and Definition of Done cite rather than contradict that owner.
- Every active implementation unit has repo-relative file paths, dependencies, concrete test scenarios, and an outcome-based verification rule.
- The plan contains no remaining `reference adapter`, `future adapter`, cross-runtime compliance, or portable SDK claims except in clearly deferred context.
- `docs/raid.md` agrees with the rewritten URI policy, runtime decision, risks, assumptions, and dependencies.
- A headless document review reports no unresolved P0/P1 coherence or feasibility issue before Proof synchronization.
- Proof revisions for changed published documents match the final local markdown, while tokens and owner secrets remain confined to `tmp/proof-state.json`.
