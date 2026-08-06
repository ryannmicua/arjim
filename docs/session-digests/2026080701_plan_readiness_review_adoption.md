---
lorespec: "0.1"
id: "2026080701"
date: "2026-08-07"
source: "opencode"
topic: "Adopt fable-5 readiness-review findings into the workstream registration plan via a glm-5.2 draft review, reconcile marker terminology, and compound the review-adoption practice"
tags: [plan-review, contract-edit, exit-code, operator-decision, cross-model-review, glossary-drift, workstream-registration]
classification:
  type: drafting
  secondary_type: technical
  domains: [workstream-registration-planning, plan-governance]
  value: high
trails: [workstream-registration-planning, readiness-review-adoption]
---

## Session Arc

### Started
User asked to be brought up to speed on the arjim repo (planning-only; implementation-ready workstream registration plan; 08-04 terminology rename committed; Proof sync pending).

### Pivots
- **External readiness review:** user invoked `/paseo-advisor` with Claude Fable 5 (OpenRouter) to review the implementation-ready plan for overlooked items, readiness, and measurable success measures. Verdict: GO-WITH-FIXES — C1 (critical: CONCEPTS.md vs plan disagree on marker path/name, drift introduced by the same 08-04 commit), M1-M4 (major: KTD13 lock ordering unimplementable; Windows ACL gate infeasible via stdlib; missing schema version field; open min-record-sources/default-kind), m1-m5 (minor).
- **Draft-then-review:** user directed: draft the edits, have a glm-5.2 model review the draft (CE-code-review correctness lens), incorporate findings, then apply. glm-5.2 approved-with-fixes and caught a real defect: the new exit-code mapping referenced `invalid-marker`, an outcome absent from the plan's own frozen U3 result vocabulary (malformed markers report `occupied-invalid`).
- **Wrap-up:** user requested wrapup skill, which produced this digest, the compounded solution doc, and the CONCEPTS.md "Registration outcome" entry.

### Ended
All 13 edits applied to the plan and CONCEPTS.md fully reconciled (zero "manifest" occurrences), decisions recorded as a dated operator-decision section, solution doc written and grounding-validated, working tree dirty (uncommitted) on `main`, branch 1 ahead of origin (local commit `ddd127e` "Add workstream registration readiness review").

## ARTIFACTS

### A1. Readiness review doc (fable-5) — `docs/reviews/2026-08-06-001-workstream-registration-plan-readiness-review.md`
- **What:** Full readiness review of the plan with verdict GO-WITH-FIXES: C1 (critical) marker/manifest path contradiction; M1 KTD13 lock-acquisition order impossible for first registration; M2 fail-closed owner-only ACL gate unimplementable via stdlib on Windows (operator's platform); M3 marker schema omits the version field readers dispatch on; M4 minimum record-source count and default kind left open; m1-m5 minors (VISION precedence, double re-read ambiguity, register-on-existing unspecified, partial exit-code mapping, circular U5 gate). Includes success-measure audit: 5 measures "not measurable as written" each with a concrete mechanization.
- **Committed:** locally as `ddd127e` (ahead of origin).

### A2. Applied plan edits + CONCEPTS.md reconcile
- **What:** 13 edits to `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md` (Agent Execution Rules precedence; filesystem-profile dependency; KTD13 atomic lock+parent creation; U1 closed-object with required version field `1`, RFC 4122 v4 UUID, non-empty label, required kind, 1-32 record sources; U1 scenarios; U5 verification de-circularized; U9 lock alignment; U10 two-phase re-read + icacls enforcement; U11 CLI `--kind` default, register-degrades-to-link, complete exit-code mapping, scenarios; Deferred/Open filesystem-profile entry resolved; new "From the 2026-08-06 operator decision (review adoption)" section with 7 recorded decisions) and a full manifest→marker terminology reconcile of `CONCEPTS.md` (`.workstream/workstream.json` canonical).
- **Evolution:** draft first written to `tmp/plan-edits-2026-08-06-draft.md`, reviewed by glm-5.2 (APPROVE-WITH-FIXES), findings incorporated (dropped `invalid-marker` from mapping, em-dash style, KTD6/U2 no-change note, non-exact locator fix), then applied.
- **State:** uncommitted working-tree changes.

### A3. Compounded solution — `docs/solutions/best-practices/readiness-review-adoption-before-execution.md`
- **What:** Knowledge-track solution doc: "Review adoption: a third readiness review still found unimplementable contract details and silent drift before an implementation-ready plan started executing." Five rules of guidance: fresh readiness review before execution; apply findings as dated operator decisions; verify contract-edit drafts against frozen vocabulary (BEFORE strings + outcome names); reconcile glossary drift with the plan authoritative; defer success-measure mechanization into executing units. Grounding-validated: 39 claims verified, 2 corrected, all plan-line citations checked.
- **State:** untracked (new file).

### A4. CONCEPTS.md "Registration outcome" entry
- **What:** New glossary entry defining the closed result vocabulary (registered, linked-existing, unregistered, occupied-invalid, invalid-marker-resolved, changed-marker-stopped), its freeze in the plan's U3 result contract, its CLI exit-code mapping, and that occupied-invalid covers all invalid markers with no separate invalid-marker outcome.

## DECISIONS

### D1. Marker terminology reconciled; the plan is authoritative
- **Decision:** The durable artifact is the **marker** at `.workstream/workstream.json` (R10, KTD2, KTD4, KTD13, U1, 08-04 decision); CONCEPTS.md's "workstream manifest"/`manifest.json` was drift and now follows the plan.
- **Issue:** Same-commit contradiction: `6b965de` renamed CONCEPTS.md to "manifest" while the plan kept "marker".
- **Positions:** Fix the plan to manifest; fix CONCEPTS.md to marker.
- **Arguments:** The 08-04 decision explicitly retained "marker"; the plan is the implementation contract whose U1 freezes the schema; a glossary follows the contract, not vice versa.
- **Warrant:** The canonical artifact outranks its glossary, and a recorded decision must break ties so agents don't burn sessions deciding.
- **Qualifier:** always. **Status:** settled (recorded in plan).

### D2. Lock acquisition and parent creation are one atomic step when `.workstream` is absent
- **Decision:** When the parent is absent, create it without replacement then exclusively create `.workstream/.registration.lock` within it before any marker write; cancellation leaves an empty parent handled by the KTD6 no-transition retry variant (fresh inspection required).
- **Issue:** KTD13 ordered lock acquisition before parent creation, physically impossible.
- **Warrant:** First-registration exclusivity needs the lock to exist before any marker write, and the envelope model already defines the empty-parent retry path.
- **Qualifier:** always. **Status:** settled.

### D3. v1 platform: Windows NTFS + POSIX; stdlib on POSIX, built-in `icacls` on Windows, fail closed otherwise
- **Decision:** The declared filesystem profile targets Windows NTFS and POSIX-compatible local filesystems; owner-only enforcement uses stdlib on POSIX and the built-in `icacls` tool on Windows (a subprocess to a Windows built-in, not a Python dependency — KTD1 footprint intact); fail closed when the declared profile's enforcement cannot be established.
- **Issue:** U10's owner-only gate was impossible via stdlib on the operator's own platform.
- **Warrant:** A fail-closed gate that can never pass on the target platform makes the product dead on that platform; naming the mechanism makes the gate executable.
- **Qualifier:** always. **Status:** settled.

### D4. Marker schema closed-field decisions freeze at U1
- **Decision:** Required `version` field (JSON integer, v1 allowed value `1`) that readers dispatch on; identity is RFC 4122 v4 lowercase UUID; label required and non-empty (256-byte cap); `kind` required in schema with CLI default `direct`; record-source list required, 1-32.
- **Issue:** U1's closed-object enumeration omitted the version field KTD3 requires readers to dispatch on; min count and default kind were open.
- **Warrant:** A closed schema omitting a required dispatch field is a contradiction; defaults are cheapest before U1 freezes the contract.
- **Qualifier:** always. **Status:** settled.

### D5. `register` on an existing valid marker degrades to linking (`linked-existing`, no write, no confirmation)
- **Issue:** CLI behavior on already-marked workspace was unspecified. **Status:** settled.

### D6. Complete exit-code mapping; the result vocabulary has NO `invalid-marker` outcome
- **Decision:** 0 registered/linked-existing/unregistered/invalid-marker-resolved; 2 cancelled/stopped; 3 invalid-inaccessible input incl. occupied-invalid inspection; 4 conflict/changed-marker-stopped; 5 written-unverified/registered-unlinked/invalid-deleted-unverified; 6 internal failure. Malformed markers report `occupied-invalid`.
- **Issue:** The draft's mapping cited `invalid-marker`, absent from U3's frozen vocabulary (caught by glm-5.2); mapping was exemplar-only before.
- **Warrant:** Exit codes must map only to the frozen result vocabulary or --json/exit-code divergence returns.
- **Qualifier:** always. **Status:** settled.

### D7. VISION Condition of Trust 5 is an operator obligation the implementation does not police
- **Decision:** Session-settled operator decisions govern where they interpret VISION; no secret-scanning obligation is reinstated.
- **Warrant:** Two authoritative sources need a stated tiebreak for implementing agents. **Status:** settled.

## INSIGHTS

### I1. Contract-edit drafts must reference only names in the document's own frozen vocabularies
A fresh-model draft review caught the exit-code mapping referencing `invalid-marker`, which does not exist in the plan's U3 result vocabulary (malformed markers report `occupied-invalid`). The fix for one divergence nearly shipped a second one. Self-review cannot reliably catch this; checking new references against the document's own enumerated sets can. Source: glm-5.2 review of the draft. Confidence: high.

### I2. Standardization commits can introduce the very drift they appear to resolve
The 08-04 terminology commit `6b965de` renamed CONCEPTS.md's Marker entry to "Workstream manifest"/`manifest.json` while leaving the plan on "marker" — contradicting its own recorded D3 decision that marker is retained. An unrecorded rename looks like an error, not a ruling. Source: git show of `6b965de`; review C1. Confidence: high.

### I3. Fresh-model readiness reviews add value even after two prior reviews passed
The plan had passed the 08-02 review and an anti-sycophancy review; a third, adversarial, no-memory review still found one critical and four major defects, including "literally unimplementable as specified" (KTD13) and "the product dead on the operator's Windows machine" (U10 gate). Source: fable-5 review. Confidence: high.

## PATTERNS

### P1. Readiness-review adoption loop (local)
Before executing an implementation-ready plan: (1) run a fresh cross-model readiness review (different family, no memory of intent); (2) draft the findings as concrete document edits with exact BEFORE strings; (3) review the DRAFT with a second fresh model seeded with a correctness persona (verifies BEFORE matches, frozen-vocabulary references, cross-references); (4) incorporate; (5) apply edits as dated operator decisions recorded IN the plan, never as silent edits; (6) defer success-measure mechanization into the units that can execute it, documenting the deferral. Repo insight I3 is the warrant for step 5.

### P2. Mechanical claim grounding for contract-adjacent docs (local)
Solution docs citing plan/review/digest line numbers: run a semantic grounding validator subagent that quotes the defining source line for every citation, verifies outcome names against enumerated sets, and counts countable assertions; use ce-compound's validate-doc-claims.py for paths/SHAs; confirm-intentional contract paths (planning-only repos have no on-disk contract files).

## NEXT_STEPS

### N1. Commit the plan + CONCEPTS.md changes and the solution doc (now)
Three files are uncommitted (plan edits, CONCEPTS.md reconcile + Registration outcome, new solutions doc); the review doc is already committed locally as `ddd127e`. Use ce-commit; the branch is already 1 ahead of origin.

### N2. Proof sync plan and RAID (still pending)
From the 08-04 digest: both carry proof_url frontmatter and were edited since last publish; run `/ce-proof`. The plan changed again on 08-06.

### N3. Execute U5 then U1 per the plan's sequencing (soon)
The plan reads GO after the adoption. U1 freezes the schema including the newly decided version field, kind default, and 1-32 record sources; carry the deferred success-measure mechanizations (canary corpus, covers tags, state-table assertion, DoD grep blacklist, rebuild E2E) inside U5/U1/U11 execution.

### N4. Note the stale generated snapshot (someday)
`output-html/workstream-registration-plan-2026-08-01.html` predates the 08-06 adoption; kept intentionally as a dated artifact per the 08-04 digest.

## Connections

- D1-D7 —[led_to]→ A2
- I1 —[informed_by]→ glm-5.2 draft review; —[informed]→ D6
- I2 —[informed_by]→ A1 (C1); —[informed]→ D1
- I3 —[informed_by]→ A1
- A1 —[led_to]→ P1
- P1 —[instance_of]→ A3
- A4 —[informed_by]→ D6
- P2 —[instance_of]→ A3 grounding run

## Trail Updates

- **workstream-registration-planning:** extended with the 2026-08-06 operator decisions (marker reconcile, lock atomicity, platform, schema fields, exit codes) — plan now GO per the fable-5 verdict.
- **readiness-review-adoption:** created by this session (solution doc + digest).
