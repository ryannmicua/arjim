---
title: Workstream Registration and Discovery Plan - Readiness Review
date: 2026-08-06
type: document-review
source_document: docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md
source_type: unified-plan
source_readiness: implementation-ready
status: complete
review_route: paseo/opencode/openrouter/anthropic/claude-fable-5
review_question: anything overlooked, readiness for execution, measurability of success measures
---

# Workstream Registration and Discovery Plan - Readiness Review

## Verdict: GO-WITH-FIXES

The plan is unusually rigorous: the authority model, unit sequencing (U5 -> U1 -> U2 -> U3 -> U4 -> U6 -> ... -> U11), and executable verification gates are coherent and well-traced, and settled decisions are recorded so an implementing agent cannot mistake them for drift. But it ships with one genuine cross-document contradiction on the single most important stable identifier (the marker filename), one self-contradictory lifecycle rule (lock placement in KTD13), and a handful of contract holes that U1 will freeze if not settled first. All are cheap document-level fixes; none require redesign. Fix them before handing to execution - an agent that follows the plan's own Agent Execution Rules will otherwise either freeze the wrong contract or stall on a contradiction.

## Findings

### Critical

- **C1. The plan and CONCEPTS.md disagree on the marker's canonical path and name.** Plan (R10, KTD2, KTD13, U1): the durable artifact is the marker at `.workstream/workstream.json`, and the 2026-08-04 operator decision says "marker" is retained. CONCEPTS.md: the artifact is the "workstream manifest", canonical path `.workstream/manifest.json`, with a full "Manifest terminology" block. Git verification: the same commit (`6b965de`, the 08-04 terminology standardization) introduced both - it renamed CONCEPTS.md's "Marker" section to "Workstream manifest" and changed the path to `manifest.json`, while leaving the plan on "marker"/`workstream.json`. The session digest (A1, D3) says marker was retained, so CONCEPTS.md looks like unrecorded drift, but nothing in the repo says which is authoritative. R10 says the marker path is "the only v1 marker that makes a workspace a registration or discovery candidate"; U1 freezes it. If unreconciled, the implementer either freezes the wrong filename or burns a session deciding. Fix first; record the resolution as a dated operator decision (repo insight I3: undocumented renames get treated as drift).

### Major

- **M1. KTD13 lock acquisition is self-contradictory for first registration.** KTD13 says "acquire the per-workspace lock before parent or marker creation" - but the lock lives at `.workstream/.registration.lock`, inside the parent that does not exist yet (the envelope's `ABSENT -> created-parent-identity` case, KTD6). As written this is unimplementable: you cannot exclusively create a file in a directory that must not yet exist. The implementer must invent a resolution - create the parent as a side effect of locking (contradicting the ordering clause, muddying the ABSENT -> created-parent envelope transition, and leaving an empty `.workstream/` on cancellation, which may itself trip "marker-state change expires unused confirmation") - or relocate the lock. Decide explicitly: sibling lock file, or define lock acquisition as atomically creating parent + lock and fold that into the KTD6 envelope and the U2 "interrupted parent-created retry" fixture.

- **M2. Platform feasibility of the mandatory fail-closed permission gate is undecided - and the operator's platform is Windows.** U10 requires owner-only permissions/ACLs on the projection directory, database, and sidecars, verified before use, failing closed when enforcement is unavailable. KTD13/KTD10 require platform file-identity and process-liveness APIs. The dependency footprint is pinned to stdlib + `jsonschema` (KTD1). On Windows, `os.chmod` cannot produce owner-only ACLs and stdlib has no ACL API - so a literal reading makes the projection always fail closed on the operator's own machine, which means `register` can never complete `linked` and the Goal Capsule's work-reduction test cannot pass. The plan marks "confirm the local filesystem profile" as open-non-blocking, but it is blocking for U6/U10 on Windows. Decide now: the v1 target platform(s), and the permitted enforcement mechanism there (e.g., `icacls` subprocess, per-user `%LOCALAPPDATA%` default ACLs declared sufficient, or POSIX-only v1). The prior 08-02 review's residual concern flagged this and it was never resolved.

- **M3. The marker schema omits the version field it requires readers to dispatch on.** KTD3: "a reader dispatches on marker version before applying its closed schema." R9 names an "unsupported marker version" outcome. `ProjectionInput` carries `marker_version` (U9/U10). Yet U1's enumeration of the closed object - "lowercase UUID identity, bounded label, `direct|proxy` kind, literal `.` workspace reference, and bounded typed absolute record-source URIs" - has no version field. A closed schema with an unlisted-but-required field is a contradiction. Add the version field's name, format, and allowed value(s) to U1 before the schema freezes.

- **M4. Contract defaults left open from the 08-02 review will be frozen implicitly at U1.** Two of the prior review's deferred questions were never answered anywhere:
  - **Minimum record-source count.** U11's CLI requires at least one `--record-source`; the schema states only a max (32). If the schema allows zero, a zero-source marker is valid to link (F2) but impossible to create - an asymmetry the plan neither endorses nor forbids.
  - **Default `kind`.** CLI shows `[--kind direct|proxy]` as optional; whether omission defaults to `direct` or the schema requires the field is unstated.
  Both are one-line decisions now and versioned contract changes after U1. Related nits: empty-label validity and UUID version are also unstated; acceptable as implementer freedom if stated so.

### Minor

- **m1. VISION §5 vs KD10/KTD5 needs a stated precedence rule.** VISION's non-negotiable Condition of Trust 5 says workspaces "do not store passwords, access tokens, private keys, or other live credentials in shared files"; settled KD10 accepts credential-bearing URIs as valid data with no inspection. The plan's "acceptance is not a recommendation" language helps, but Agent Execution Rule 1 makes both VISION.md and session-settled decisions authoritative with no tiebreak. Add one sentence: VISION §5 is an operator obligation the implementation does not police, and session-settled operator decisions govern where they interpret VISION.

- **m2. U10's "re-read and compare, re-read and compare again" is ambiguous** - deliberate two-phase check or editing artifact? Specify once (e.g., re-read/compare after lock acquisition, again immediately before delete) or delete the duplication.

- **m3. `register` pointed at an already-marked workspace is unspecified at the CLI level.** F2/AE2 define linking; the result vocabulary has `linked-existing`; but whether `register` degrades to link, or errors and directs to `link`, is unstated. Either is fine - state it.

- **m4. Exit-code to outcome mapping is partial.** Eleven result outcomes (U3) map onto six exit codes with only exemplars given. `conflict`, `written-unverified`, `changed-marker-stopped` mappings are inferable but should be tabulated in U11 so `--json` and exit codes cannot diverge between implementations.

- **m5. U5's verification is circular at U5-time** ("sufficient for every fixture planned by U1-U3" cannot be checked before U1-U3 exist). Harmless in practice - the Fixture-structure gate re-verifies later - but say that U5 sufficiency is re-confirmed at each of U1-U3 so the implementer does not stall.

**Deferrals check (R12/R13):** the deferred scan/registry/root-scanning scope does not break v1's promise - R13 now honestly narrows the work-reduction claim ("v1 cannot recover locations it is never pointed at"), matching the 08-02 accepted gap. No flag.

## Success-measure assessment

**Measurable as written:**

- Stop condition (Goal Capsule) - corpus + gates green; objective.
- Verification Contract gates for U6-U11 (install, raw guard, validation, lifecycle, unregister, CLI/conformance, recovery/privacy) - all executable.
- Trust test (Goal Capsule) - decomposes onto AE4/AE5/AE8, identity-stability fixtures, and no-echo/canary assertions (U8, U11). One tightening: "secret-bearing diagnostic" is only testable if the canary set is a fixture, not tester improvisation - define the canary corpus (fake tokens, userinfo URIs, key-shaped strings) in U5/U1 so "never appears in stdout/stderr/logs/tracebacks/`--json`" is mechanical.
- DoD items on raw-guard limits, create-only/read-back, projection replaceability, pinned versions - executable.

**Not measurable as written, with fixes:**

1. **Work-reduction test: "without carrying a remembered map of tools"** (Goal Capsule) - unfalsifiable phrasing. Fix: restate as a scripted E2E in U11: register >= 2 workspaces (one proxy), delete the projection DB, run `rebuild <paths>`, assert identities/labels/routing equal the pre-deletion state with no record-source or identity re-entry - only workspace paths supplied. U11's "rebuild after projection loss" scenario is 90% there; bind the Goal Capsule sentence to it.
2. **U4 verification: "A new implementer can identify ... without reading this planning artifact"** - subjective. Fix: convert to a checklist (README names each contract file, marker path, runner invocation, compliance bar, support profile; all referenced paths resolve) plus optionally a fresh-agent dry-run that must answer five factual questions from the contracts alone.
3. **Protocol review gate (U2): "every documented state has entry conditions, side effects, allowed transitions, terminal or recovery path"** - currently a prose review. Fix: require a machine-readable state/transition table in `registration-protocol.md` and a runner assertion that every state named by any fixture appears in the table with >= 1 outgoing transition or a terminal flag.
4. **DoD: "No abandoned architecture language, duplicate fixtures, superseded protocol text..."** - vague. Fix: an explicit grep blacklist in the DoD ("record home", kind value `folder`, `capture-observation`, `marker-observation.schema.json`, `duplicate-registration`) plus the existing fixture-inventory gate for duplicates.
5. **DoD: "Every active requirement is cited by at least one implementation unit and covered by a fixture..."** and "contracts agree on field names, states, and authority boundaries" - verifiable only by hand today. Fix: add a `covers: [R#/AE#]` field to `expectations.json` entries so the conformance runner computes requirement coverage, and add a cross-reference check that every result-schema outcome appears in the protocol doc and vice versa.

## Prioritized actions before implementation

1. **Reconcile marker vs manifest - name and canonical path - between the plan and CONCEPTS.md (C1).** Minutes to fix; if left, the implementer freezes a contested identifier into R10/KTD2/U1. Record the resolution as a dated operator decision (repo insight I3: undocumented renames get treated as drift).
2. **Fix the KTD13 lock-placement contradiction (M1)** and define the cancel-after-parent-created state; update KTD6's envelope and the U2 interrupted-parent-created fixture accordingly. Without it U9 is literally unimplementable as specified.
3. **Decide the v1 platform and owner-only-enforcement mechanism (M2)** - name the target OS(es) and the permitted ACL/identity/liveness APIs before U6, or accept POSIX-only v1 explicitly. Left open, fail-closed rules make the product dead on the operator's Windows machine, and the discovery arrives at U10, the most expensive point.
4. **Close the U1 schema holes (M3, M4):** version field name/format, minimum record sources, default kind, empty-label rule. Four one-line decisions now; versioned contract changes later.
5. **Mechanize the soft gates (success-measure fixes 1-5):** canary fixture set, E2E rebuild scenario bound to the work-reduction test, `covers` tags in expectations, state-table assertion, DoD grep blacklist.

**What would change the verdict to plain GO:** items 1-4 applied as recorded decisions in the plan (item 5 can ride along inside U5/U1/U11 execution). Nothing challenges the settled runtime, the terminology (beyond reconciling the CONCEPTS.md conflict the 08-04 rename itself introduced), or the deliberate deferrals - those hold up.

## Notes

- Advisor: Claude Fable 5 (openrouter), read-only analysis. No files edited by the reviewer.
- Prior review (2026-08-02) remains the base; this review confirms its deferred items were not all closed and identifies what changed since.
