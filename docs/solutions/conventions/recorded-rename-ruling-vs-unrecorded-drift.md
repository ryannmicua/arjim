---
title: "Plan governance: a recorded rename is a ruling, an unrecorded one is drift"
date: 2026-08-07
category: conventions
module: plan governance (docs/plans + session digests)
problem_type: convention
component: documentation
severity: low
applies_when:
  - "renaming or reversing a frozen artifact path or name covered by a do-not-reopen clause in a plan"
  - "superseding an earlier dated decision clause with a new decision, including reversing the earlier ruling's direction"
  - "reconciling glossary or marker-path drift, when you must decide whether it is drift (reconcile back) or a ruling (record and accept)"
  - "editing a plan's asserted value after a dated operator decision changed it, instead of silently rewriting the clause"
  - "deciding whether historical records should be updated after a rename that intentionally resolves their drift"
tags: [plan-governance, decision-digest, drift-vs-ruling, rename, supersession, session-digests, frozen-markers]
---

# A recorded rename is a ruling; an unrecorded one is drift — and the ruling direction can reverse

The learning is the **plan-governance convention** for renaming settled names and paths: a dated decision digest written *before* any artifact edit converts a rename — even a reversal of an earlier "do not reopen" ruling — into a ruling, while the same rename executed silently looks like drift. The convention is documented from a three-act governance history in this repo about one filename: `.workstream/workstream.json` → `.workstream/manifest.json`.

## Context

Three events, one filename, two different governance outcomes:

1. **2026-08-04 — the unrecorded rename that looked like drift.** The terminology standardization commit `6b965de` renamed CONCEPTS.md's "Marker" entry to "Workstream manifest" at `.workstream/manifest.json` while the plan stayed on "marker" at `.workstream/workstream.json`. The same commit's recorded D3 decision said "marker" is retained (digest 2026080401 D3, `docs/session-digests/2026080401_record_source_terminology_rename.md:56-62`), so the commit contradicted its own recorded ruling, and a later agent could not distinguish the rename from a mistake — "An unrecorded rename looks like an error, not a ruling" (`docs/session-digests/2026080701_plan_readiness_review_adoption.md:93-94`). Digest insight I3 had predicted exactly this failure mode two days earlier: plan decisions marked `session-settled` are treated as authoritative, and a rename without a recorded operator decision looks like drift to the next agent (`2026080401:72-73`).

2. **2026-08-06 — the reconcile that surfaced the question as a decision.** The readiness review's C1 finding caught the CONCEPTS.md/plan contradiction (`docs/solutions/best-practices/readiness-review-adoption-before-execution.md:33`), and the adoption reconciled CONCEPTS.md back to the plan, adding a "do not reopen the name or path" clause at PLAN:551 inside the plan's "From the 2026-08-06 operator decision (review adoption)" section (`docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md:549-557`). That reconcile step looked like the end of the story; it was the setup for the reversal.

3. **2026-08-07 — the recorded reversal that made it a ruling.** The operator decided the *other* direction: `.workstream/manifest.json` becomes canonical everywhere it is a living artifact (digest 2026080702 D1, `docs/session-digests/2026080702_marker_path_rename_manifest_json.md:43-48`). The difference between the 08-04 "drift" and the 08-07 "ruling" is exactly the decision record (I1, `2026080702:60-61`). Summing digest A2's per-file inventory gives 78 occurrences in living artifacts; the historical files named in A2's scope note retain the old path (12 occurrences currently: archive plan 1, research 1, review 2, prior digest 2, solutions 4, output-html 2) (session history).

The guidance below is the execution pattern the 08-07 session used — the digest-first, supersession-recording workflow that made a one-day-later reversal of a "do not reopen" clause a ruling rather than a new drift.

## Guidance

1. **Write the dated decision digest FIRST, before any artifact edit.** Create `docs/session-digests/YYYYMMDDNN_<slug>.md` before the first rename edit, so the rename commit can cite it (P1, `2026080702:68-69`). The digest must record: the ruling itself (what changes *and* what is retained — "the term 'marker' is retained; only the filename changes", D1 `:44`), what it supersedes (exact earlier decision IDs plus clause locations: "the path part of the 2026-08-04 D3 decision (digest 2026080401) and PLAN:551", `:46`), the scope (what is intentionally NOT rewritten, D2 `:50-52`), and side-effect hashes (the frozen schema sha256 changed because the schema description string contained the path; the new hash was recorded in the digest, A1 `:32`).

2. **Rewrite the superseded clause in place, recording the supersession** — who decided, when, which digest, what exactly is superseded — instead of silently editing the asserted value. PLAN:551 was rewritten to name the 2026-08-07 decision and its digest ("the 2026-08-07 operator decision (digest `docs/session-digests/2026080702_marker_path_rename_manifest_json.md`) supersedes the filename part of those clauses... the marker is written at `.workstream/manifest.json`, while the term 'marker' is retained", `plan:551`). Earlier decision narrative (the 08-04 and 08-06 entries at `plan:544-557`) is NOT rewritten; the supersession is stated, not retrofitted (P1, `2026080702:68-69`).

3. **Leave historical records historical.** `docs/reviews/`, `docs/solutions/`, `docs/research/`, `docs/plans/archive/`, prior session digests (`2026080701*`), and generated `output-html/` keep the old path; rewriting them would erase the drift history the decision resolves (D2, `2026080702:50-52`; A2 scope note `:36`). Verification greps exclude them explicitly. Every remaining old-path reference earns a per-file justification: archived plan; research record; review record (it documents the drift this decision resolves); prior session record; compounded learning record; dated generated snapshot; and the decision record itself — whose whole purpose is to quote what it supersedes (session history).

4. **Verify the new state mechanically.** Grep for the old value across living artifacts must return zero — only historical files plus the digest's own quote of what it supersedes may still contain it. Full test suite and conformance must stay green: the 08-07 session closed with 362 pytest tests and 87/87 conformance, all gates (digest Ended, `2026080702:26`).

5. **Order commits digest-first.** Two atomic commits: the decision record first, then the rename — so the rename commit references a recorded decision (P1, `2026080702:68-69`; `:26` "decision first, then rename").

## Why This Matters

- **The cost of an unrecorded rename is ambiguity about who is wrong.** The plan and CONCEPTS.md each claimed authority for different filenames, and only a recorded operator decision could break the tie without another agent burning a session deciding (readiness doc:62; review C1). An unrecorded rename reads as a contradiction to reconcile; a recorded one reads as settled to implement (P1 warrant, `2026080702:47`).
- **Recording a reversal is what lets governance change direction at all.** Without the digest, the 08-06 "do not reopen the name or path" clause would have made the 08-07 decision an inconsistency for the next agent to "fix" back — repeating the 08-04 failure mode at higher cost, because this time the contradiction would be inside the plan itself. A dated, recorded decision outranks an earlier clause; that ordering rule is what makes reversals cheap and safe (D1 warrant, `2026080702:47`).
- **The reconcile step was not wasted; it enabled the reversal.** By surfacing the path question as a decision, the 08-06 adoption made the 08-07 reversal a ruling rather than a new drift (I2, `2026080702:63-64`). A "wrong"-direction reconcile is still progress: it converts an implicit choice into an explicit one that a later decision can flip with full traceability.
- **Renames have side effects beyond the string.** The frozen schema hash changed because the schema description string contained the path (A1, `2026080702:32`) — a rename of a path used inside a frozen artifact invalidates the artifact's identity, not just its text. Recording the new hash in the digest keeps that bookkeeping auditable.

## When to Apply

- Renaming any name, path, or term that appears in contract documents, frozen schemas, or plans carrying settled-status language ("do not reopen", "freeze at U1", "session-settled").
- Reversing an earlier recorded decision — especially a clause that explicitly says the name or path is not to be reopened.
- Any rename where implementer-facing artifacts (plan, contracts, CONCEPTS.md) and operator-facing surfaces could diverge: contract names, enum values, file paths, CLI flags, schema description strings.
- Applying terminology changes that a review flagged, so the next agent can distinguish a ruling from an unrecorded edit.
- In any repo with a plan-governance convention where plans record dated operator decisions and digests/solutions are the decision record.

## Examples

- **Drift (the anti-pattern):** the 08-04 commit `6b965de` renamed CONCEPTS.md's "Marker" entry to "Workstream manifest"/`manifest.json` while the plan stayed on "marker"/`workstream.json`, contradicting its own recorded D3 decision that "marker" is retained (`2026080401:56-62`). An unrecorded rename looks like an error, not a ruling (`2026080701:93-94`).
- **Reconcile (the setup):** the 08-06 readiness review's C1 finding caught the contradiction (`readiness-review-adoption-before-execution.md:33`); the adoption reconciled CONCEPTS.md to the plan and added the "do not reopen the name or path" clause (`plan:551` as written 08-06; adoption recorded at `plan:549-557`).
- **Reversal as ruling (the pattern):** on 08-07 the operator decided the other direction. Digest 2026080702 was written first (`P1`, `2026080702:68-69`); PLAN:551 was rewritten in place to record the supersession, naming the 2026-08-07 decision and its digest (`plan:551`); historical records were left untouched with per-file justification (D2, `:50-52`); verification was mechanical — old-path grep across living artifacts zero, 362/362 pytest, 87/87 conformance (`:26`); commits landed digest-first, two atomic commits (`:26`).
- **Side-effect hash:** the frozen schema sha256 changed because the schema description string contained the path; the superseded hash `6d323561...` and the new hash `6cd7a020...` are both recorded in the digest (A1, `2026080702:32`) so the frozen-schema change is auditable.
- **Per-file justification of retained old-path references** (session history): archived plan (dated record), research record, review record (documents the drift this decision resolves), prior session record, compounded learning record, dated generated snapshot (`output-html/`), and the decision record itself — its whole purpose is to quote what it supersedes.

## Related

- `docs/session-digests/2026080702_marker_path_rename_manifest_json.md` — the decision record (D1/D2/D3 decisions, I1/I2 insights, P1 pattern, A1/A2/A3 artifacts)
- `docs/session-digests/2026080701_plan_readiness_review_adoption.md` — I2: standardization commits can introduce the very drift they appear to resolve
- `docs/session-digests/2026080401_record_source_terminology_rename.md` — D3 ("marker", "point-and-read", "register"/"unregister" retained) and I3 (undocumented renames get treated as drift)
- `docs/solutions/best-practices/readiness-review-adoption-before-execution.md` — the 08-06 drift story and the review-adoption practice that preceded this convention (negative-case companion to this doc)
- `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md:551` — the rewritten supersession clause, in place
