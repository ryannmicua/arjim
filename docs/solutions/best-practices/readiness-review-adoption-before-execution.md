---
module: workstream-registration-planning
date: 2026-08-06
problem_type: best_practice
component: documentation
severity: high
applies_when:
  - executing an implementation-ready plan that passed readiness review
  - editing contract documents or specs with frozen vocabulary
  - applying review findings from an external advisor model
symptoms:
  - glossary terminology drifts from plan-frozen contract names
  - edit drafts reference outcome names outside the frozen result vocabulary
  - review findings applied without recording them as dated operator decisions
tags:
  - plan-review
  - contract-edit
  - exit-code
  - operator-decision
  - cross-model-review
  - glossary-drift
---
# Review adoption: a third readiness review still found unimplementable contract details and silent drift before an "implementation-ready" plan started executing

The learning here is the **review-adoption practice** that emerged when an implementation-ready CE unified plan took a third, fresh cross-model readiness review just before execution began. The individual findings that review produced (the marker-vs-manifest contradiction, the lock-ordering fix, the platform gate, the schema holes) are evidence for the practice, not the lesson itself.

## Context

The workstream registration and discovery plan (`docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md`) was marked `implementation-ready` and had already survived two reviews: the 2026-08-02 discovery-plan readiness review and an anti-sycophancy review, followed by a terminology standardization commit (`6b965de`, 2026-08-04) that renamed "record home" to "record source" and proxy-folder to proxy/regular workspace while explicitly retaining "marker" (`docs/session-digests/2026080401_record_source_terminology_rename.md:32` — "Marker", "point-and-read", "register"/"unregister" retained; `:56-62` records the D3 decision).

A third readiness review was then run as a fresh cross-model pass — Claude Fable 5 via OpenRouter through the paseo-advisor skill (`docs/reviews/2026-08-06-001-workstream-registration-plan-readiness-review.md:9`). Its verdict was GO-WITH-FIXES: the review still found one critical cross-document contradiction, three major unimplementable or unsettled contract details, and one major pair of open defaults, all on a plan that had already been reviewed twice and deemed ready.

The contradiction was the sharpest case of silent drift: at review time the plan asserted the durable artifact as the marker at `.workstream/workstream.json` (R10 at plan:111, KTD2 at plan:187, KTD13 at plan:198, U1 at plan:362 — a declared contract path, not an on-disk file; the repo was planning-only), while CONCEPTS.md had drifted to "workstream manifest" at `.workstream/manifest.json` — and git verification showed the same commit (`6b965de`, the 08-04 standardization) introduced both, changing CONCEPTS.md while leaving the plan on "marker", contradicting the 08-04 decision that "marker" was retained (`review:23`, digest `:56-62`). The standardization commit itself was the drift source: it renamed a glossary entry without recording a decision that the glossary term had changed, so the rename looked like an error, not a ruling. (The 2026-08-07 operator decision later reversed this direction: `.workstream/manifest.json` is now the canonical marker path in every living artifact, superseding the plan-side path asserted at review time — digest `docs/session-digests/2026080702_marker_path_rename_manifest_json.md`, D1; the recorded-rename governance pattern that makes that a ruling rather than new drift is the positive-case companion to this doc, see Related.)

The major findings: KTD13's lock ordering was self-contradictory for first registration — the lock lives at `.workstream/.registration.lock`, inside a parent that must not exist yet per the KTD6 `ABSENT -> created-parent-identity` envelope (plan:198, plan:191; `review:27`); U10's mandatory fail-closed owner-only ACL gate is not implementable via stdlib on Windows, the operator's own platform (`review:29`, U10 at plan:455-465); and U1's closed-object enumeration omits the version field its own dispatch rule requires (`review:31`, KTD3 at plan:188, U1 at plan:362). The two open defaults were minimum record-source count and default `kind`, which U1 would freeze implicitly if not settled first (`review:33-36`).

All findings were then applied as dated operator decisions recorded inside the plan under "From the 2026-08-06 operator decision (review adoption)" (`plan:549-557`): the marker/manifest reconciliation naming the plan authoritative (`plan:551`), the atomic parent-plus-lock acquisition rule (`plan:552`), the Windows `icacls` enforcement path with fail-closed (`plan:553`), the closed-field decisions that freeze at U1 (`plan:554`), the register-degrades-to-link behavior (`plan:555`), the complete exit-code mapping (`plan:556`), and the VISION trust-rule precedence (`plan:557`).

A second model (glm-5.2) reviewed the drafted edits before they were applied and caught a draft-only defect: the new exit-code mapping text referenced an `invalid-marker` outcome that does not exist in the plan's own frozen result vocabulary — U3 has no such outcome, malformed-marker inspection reports `occupied-invalid` (`plan:391`), and the 08-06 decision now states exactly that (`plan:556`). That was precisely the kind of `--json`-vs-exit-code divergence the mapping was meant to close, and it would have shipped as a new contradiction.

CONCEPTS.md was reconciled to the plan — the glossary then defined the marker with canonical path `.workstream/workstream.json` (`CONCEPTS.md:23`) and contained no "manifest" occurrences. That reconcile direction was itself superseded on 2026-08-07: the operator ruling moved the canonical path to `.workstream/manifest.json`, which CONCEPTS.md:23 now states (digest 2026080702, D1). The 08-06 decisions are uncommitted working-tree changes on `main` (the local commit `ddd127e` "Add workstream registration readiness review" is ahead of origin); nothing described here is claimed as merged. The success-measure mechanizations the review proposed — the canary fixture corpus, `covers` tags in expectations, the state-table assertion, and the DoD grep blacklist (`review:58-67`) — were deliberately deferred into U5/U1/U11 execution per the review verdict ("item 5 can ride along inside U5/U1/U11 execution", `review:77`).

## Guidance

1. **Run a fresh readiness review immediately before executing an implementation-ready plan, even when prior reviews passed.** Settled-looking plans can still be unimplementable in specific spots — lock ordering (KTD13 at plan:198 made first registration impossible as written, `review:27`), and platform feasibility of fail-closed gates (stdlib `os.chmod` cannot produce owner-only ACLs on Windows, `review:29`) — and they can carry silent cross-document drift introduced by the very commits that "standardized" terminology (the 08-04 rename commit introduced the manifest drift it appeared to be resolving, `review:23`). A fresh model with no memory of the plan's intent reads it adversarially; prior reviewers carry the assumptions that created the gaps.

2. **Apply review findings as dated operator decisions recorded in the plan, with rationale — never as silent edits.** The repo's own insight I3 is that undocumented renames get treated as drift by the next agent (`digest:72-73`); the readiness review's C1 was caused by exactly that failure mode and its fix recommendation repeats the rule (`review:23`, `review:71`). The 08-06 adoption records each resolution with its reasoning and its authority (`plan:549-557`), so an implementing agent can distinguish a decision from an inconsistency.

3. **When drafting edits to a contract document, verify two things before applying: (a) every BEFORE string exactly matches the live file, and (b) every new reference — outcome names, enum values, identifiers — exists in the document's own frozen vocabulary.** A self-review can cite terms that do not exist: the drafted exit-code mapping referenced `invalid-marker`, a name absent from U3's frozen result vocabulary, which reports `occupied-invalid` for malformed-marker inspection (`plan:391`, `plan:556`). A fresh-model draft review caught this before the edit landed. Check new terms against the document's own enumerated sets, not against memory.

4. **Reconcile glossary drift by treating the canonical artifact (the plan/contract) as authoritative and updating the glossary (CONCEPTS.md) to match — and record the reconciliation.** The plan's R10/KTD2/U1 and the 08-04 decision settled "marker" at `.workstream/workstream.json`, and the 08-06 reconcile made CONCEPTS.md follow (`CONCEPTS.md:23`, `plan:551`). That path was later superseded by a recorded operator ruling, not new drift: the 2026-08-07 decision moved the canonical path to `.workstream/manifest.json` in every living artifact (digest 2026080702, D1; see Related for the governance pattern that makes a recorded reversal a ruling). Do not "fix" the plan to match a drifted glossary entry, and do not leave the glossary inconsistent with the contract it is supposed to gloss.

5. **Defer mechanization of soft success measures into the units that can execute them, and document that deferral explicitly in the review.** The review's five "not measurable as written" success-measure fixes (rebuild E2E, U4 verification checklist, state-table assertion, DoD grep blacklist, `covers` tags — `review:61-67`) were recorded as the mechanism for each (`review:63-67`), and the canary corpus was added as a tightening of the already-measurable trust test (`review:58`); all were deferred into U5/U1/U11 execution rather than bolted on before implementation (`review:77`). The verdict conversion to plain GO required only the four decision items; mechanization rode along.

## Why This Matters

The alternative to each rule is a distinct, costly failure mode that was almost realized in this run:

- Skipping the third review would have handed the implementer a plan whose own Agent Execution Rules (`plan:31`) tell it to follow the plan as authoritative — so it would have either frozen the wrong filename into the schema at U1 (U1 freezes the marker contract; `plan:362` and the 08-04 decision text "the kind values `direct|proxy` freeze at U1", `plan:547`; the 08-06 adoption repeats "freeze at U1", `plan:554`) or stalled on the KTD13 contradiction at U9, which the review called "literally unimplementable as specified" (`review:72`).
- The lock contradiction and the Windows ACL gate are not polish; they are "literally unimplementable as specified" (`review:72`) and "the product dead on the operator's Windows machine" (`review:73`). A plan that passes two reviews can still be unimplementable where it touches the real platform and the real filesystem.
- The `invalid-marker` draft defect shows why edit drafting is a verification target of its own: the fix for one divergence (exit codes vs result vocabulary) would have shipped a second one, because the fixer referenced a vocabulary term that does not exist. Fresh-model draft review catches what self-review cannot.
- Unreconciled glossary drift is worse than wrong: it is ambiguous about who is wrong. The plan and CONCEPTS.md both claimed authority for different filenames, and only a recorded operator decision could break the tie without another agent burning a session deciding (`review:23`).

## When to Apply

- **Any repo with CE pipeline artifacts** — plans marked `implementation-ready` (frontmatter `artifact_readiness: implementation-ready`, as at plan:7) — **before execution starts**, especially when the plan will freeze an identifier or schema: U1 freezes the marker schema (`plan:362`), and the 08-04/08-06 decisions both say "freeze at U1" (`plan:547`, `plan:554`).
- **When terminology or contract documents have been renamed or "standardized" by prior commits.** Those commits are prime drift sources: the fix that looks like it resolved terminology can itself leave contradictory vocabulary behind (the 08-04 commit, `review:23`, `digest:32`).
- **When findings will be applied by editing a contract document** — run the draft through a fresh model before applying, and validate every new reference against the document's frozen vocabularies.
- **When a review verdict is GO-WITH-FIXES** — the verdict pattern of "recorded decisions now, mechanization during execution" (`review:77`) is the generalizable shape: decisions that change contract content land as dated decisions before execution; measurement machinery lands inside the units that can execute it.
- Specifically in **arjim**, before U1 begins (the next contract unit after U5), so the settled names, paths, and closed fields are the ones that freeze.

## Examples

- **Drift introduced by the standardization commit itself:** the 08-04 rename commit `6b965de` changed CONCEPTS.md's "Marker" entry to "Workstream manifest" at `.workstream/manifest.json` while leaving the plan on "marker"/`workstream.json`, contradicting its own recorded D3 decision that "marker" is retained (`digest:56-62`). A later agent could not distinguish an unrecorded rename from a mistake; only a dated operator decision could (`review:23`).
- **Unimplementable ordering found in review:** KTD13 required acquiring a lock that lives inside a parent directory that must not exist on first registration (`plan:198` vs the KTD6 envelope at `plan:191`). The adoption decision resolved it as one atomic step — create the parent without replacement, then exclusively create the lock within it — and explicitly mapped the cancellation residue (empty `.workstream/`) onto the existing KTD6 no-transition confirmation variant and the U2 "interrupted parent-created retry" fixture (`plan:552`).
- **Platform feasibility of a fail-closed gate:** U10's mandatory owner-only permission verification with fail-closed would have made the projection permanently fail closed on Windows, where stdlib has no ACL API — so `register` could never complete `linked` and the goal-capsule work-reduction test could never pass on the operator's own machine. Resolved by naming Windows NTFS and POSIX as targets and permitting the built-in `icacls` tool on Windows (`plan:553`; the enforcement line also updated in the dependencies block at `plan:170`).
- **Draft review catching a nonexistent vocabulary term:** the exit-code mapping draft referenced `invalid-marker`; the plan's U3 result vocabulary has no such outcome — malformed-marker inspection reports `occupied-invalid` (`plan:391`). The adopted mapping states this explicitly ("the result vocabulary has no separate `invalid-marker` outcome", `plan:556`), closing the very divergence the mapping existed to prevent.
- **Mechanized success measures deferred with a documented home:** the review called the work-reduction test "unfalsifiable as written" and prescribed a scripted E2E bound to U11's rebuild-after-projection-loss scenario (`review:63`), the canary corpus into U5/U1 (`review:58`), `covers` tags into the U5 expectations manifest (`review:67`), the state-table assertion into U2's protocol (`review:65`), and the DoD grep blacklist into the DoD (`review:66`) — with the verdict explicitly carrying item 5 into U5/U1/U11 execution (`review:77`).

## Related

- `../conventions/recorded-rename-ruling-vs-unrecorded-drift.md` — the positive-pattern companion to this doc: a rename recorded as a dated operator decision is a ruling (digest 2026080702), where this doc's reconcile-back rule is the negative case. The two are complementary facets of the same governance story, not duplicates.
