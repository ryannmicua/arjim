---
title: AT-06 - Canonical Vocabulary and Final Conformance
type: vertical-slice-plan
date: 2026-08-10
source_units: [U9, U10]
depends_on: [AT-01, AT-02, AT-03, AT-04, AT-05]
strictly_last_unit: U10
---

# AT-06 - Canonical Vocabulary and Final Conformance

## Objective and Outcome

Finish the awareness tier by adding the single planned canonical vocabulary entry, then implementing the strictly-last executable conformance runner that proves every contract, acceptance example, trust boundary, lifecycle gate, and registration regression on clean inputs while rejecting corrupted executable coverage.

## Split/Regroup Decision

U9 is documentation plus an executable coherence check, not an independent product capability. U10 is integration-only and must be strictly last. They are regrouped into the final governance outcome with an internal hard boundary: complete and verify U9 first; make U10 the last implementation action across the entire decomposition. Nothing follows U10 except running its final gates and producing the implementation report.

## Source Traceability

| Source | Coverage |
|---|---|
| U-IDs | U9 first, U10 strictly last |
| Requirements | U9: R0, R20. U10 primary list: R6b, R7b, R8, R10, R11, R13, R14, R18, R19. Integration audit covers all R0-R20 and suffixed requirements. |
| KTDs | KTD18 in U9; executable proof of KTD1-KTD20 in U10 |
| Flows | Final executable proof of F1 and F2 |
| Acceptance examples | U10 binds AE1-AE16 to named assertions; source U10 explicitly emphasizes AE12-AE14 |

## Dependencies

- Every earlier slice and every earlier source-unit gate must pass.
- U11 and U8 are complete in source order.
- U9 is completed and verified before U10 begins.
- U10 is the strictly-last implementation action.

## Files Likely Touched

- `CONCEPTS.md`
- `tests/python/test_awareness_concepts.py`
- `src/awareness/conformance_runner.py`
- `tests/contracts/awareness/expectations.json`
- `tests/python/test_awareness_conformance_runner.py`
- `tests/contracts/awareness/fixtures/closed-enum-source.json`
- `tests/contracts/awareness/fixtures/closed-enum-aggregate.json`
- `tests/contracts/awareness/fixtures/canary-uri.json`
- `tests/contracts/awareness/fixtures/canary-author-email.json`
- `tests/contracts/awareness/fixtures/bootstrap-baseline.json`
- `tests/contracts/awareness/fixtures/precedence-bootstrap-failed.json`
- `tests/contracts/awareness/fixtures/precedence-incomplete-stale.json`
- `tests/contracts/awareness/fixtures/precedence-unconfigured-failed-canary.json`
- `tests/contracts/awareness/fixtures/precedence-rules-zero.json`
- `tests/contracts/awareness/fixtures/precedence-matches-zero.json`
- `tests/contracts/awareness/fixtures/disabled-source-excluded.json`
- `tests/contracts/awareness/fixtures/scaffold-trust-path.json`
- `tests/contracts/awareness/fixtures/version-space-naming.json`
- `tests/contracts/awareness/fixtures/canary-marker-origin.json`
- `tests/contracts/awareness/fixtures/canary-conventions-origin.json`
- `tests/contracts/awareness/fixtures/canary-git-output-error-origin.json`
- `tests/contracts/awareness/fixtures/canary-scaffold-input-output-origin.json`
- `tests/contracts/awareness/fixtures/canary-branch-name.json`
- `tests/contracts/awareness/fixtures/coverage-corrupt-assertion.json`

## Implementation Approach

### U9 portion: vocabulary coherence

1. Add only the `Awareness projection` entry to `CONCEPTS.md`.
2. Define it as replaceable device-local awareness state, cleared by `awareness rebuild`, distinct from registration projection, while inventory remains durable operator-curated input and non-reconstructible in v1.
3. Do not re-amend the existing Record source or Checking adapter entries.
4. Verify canonical text and protected registration source expectations before U10 begins.

### U10 portion: strictly-last conformance

5. Model the runner structure on the existing registration runner while requiring each `covers` claim to bind a unique assertion that actually executes and passes.
6. Fail on duplicate, missing, unknown, skipped, or failing assertion IDs.
7. Execute both exact enums, every KTD9 row/discriminator, disabled-source exclusion, rule presence semantics, immutable observation, atomic result/baseline behavior, exact tracking-ref deltas, reset/bootstrap matrix, and freshness override/boundary/window-change cases.
8. Execute the configure/view unsupported-version split, every KTD13 family/outcome/exit, explicit inventory metadata, exact inventory and state table shapes, references-only reports, attribution, identity revalidation, and real-index immutability.
9. Execute each required privacy origin separately and scan both databases plus every prohibited report/output/error sink. Keep actual fixture values confined to test fixtures and never emit them in runner diagnostics.
10. Execute missing-only scaffold authorization, shared locking, containment, identity, provenance, and unchanged-existing-declaration behavior.
11. Execute the structural no-background assertion and five exact version-space checks with generic-key rejection.
12. Require all eight protected files clean against `HEAD`, compare their raw working-tree bytes to AT-01 expectations on the declared checkout profile, and run registration conformance.
13. Add the corrupt-copy self-test: copy the clean corpus to temporary storage, retain coverage tags, inject the corrupt assertion fixture, and require nonzero runner exit. Exclude that fixture from the normal mandatory corpus.
14. Run lifecycle and wipe/rebuild scenarios proving workspace-owned artifacts and durable inventory survive while awareness state/history does not.
15. Produce bounded per-fixture outcomes and fail closed on any unproven claim.

## Test Scenarios

1. U9 test finds the single Awareness projection entry and confirms existing canonical vocabulary remains intact.
2. Clean mandatory corpus exits 0 and reports every named assertion passed.
3. Corrupt copied corpus retains tags but exits nonzero, proving coverage is executable rather than metadata-only.
4. Both seven-value enums and every KTD9 row/precedence discriminator execute exactly.
5. Disabled sources are absent from dispatch/results and zero-rule versus zero-match states remain distinct.
6. Exact tracking-ref deltas advance only after committed success; all reset cases bootstrap.
7. Freshness override, one-tick-before, exact-boundary, later, and convention-window-change cases execute.
8. Unsupported conventions produce the exact configure exit-3 and view exit-0 split.
9. Every KTD13 outcome family and exit mapping executes without extending registration's table.
10. Inventory and awareness databases expose only exact allowed columns and version metadata.
11. Complete privacy origin/sink matrix passes without diagnostics reproducing planted values.
12. References-only reports exclude declaration values; scaffold is missing-only and attributable.
13. Structural scan finds no scheduler/background mechanism.
14. Only the five exact version names are accepted in their positions.
15. Protected-source mutation simulation fails comparison; repository bytes pass; registration runner exits 0.
16. Wipe/rebuild leaves marker, conventions, declarations, and inventory unchanged, then reports bootstrap and unavailable prior history.

## Verification Commands

Run in this exact order:

| Order | Command | Expected exit | Evidence |
|---:|---|---:|---|
| 1 | `python -m pytest tests/python/test_awareness_concepts.py -v` | 0 | U9 vocabulary entry and protected-source coherence pass before U10. |
| 2 | `python -m pytest tests/python/test_awareness_conformance_runner.py -v` | 0 | Corrupt-copy negative self-test and runner failure modes pass. |
| 3 | `python -m awareness.conformance_runner` | 0 | Clean mandatory awareness corpus and all named executable assertions pass. |
| 4 | `python -m workstream_registration.conformance_runner` | 0 | Registration regression suite passes with protected sources unchanged. |

## Stop and Escalation Conditions

- Stop if any earlier slice is incomplete or red when U10 is about to begin.
- Stop if U9 would alter any canonical entry other than adding Awareness projection.
- Stop if executable coverage cannot bind every R/AE claim without adding behavior outside the source plan.
- Stop on any privacy sink failure, baseline/freshness/KTD9 violation, unsafe scaffold behavior, background mechanism, generic version key, protected-file difference, or registration regression.
- Stop if the corrupt fixture must enter the clean mandatory corpus or if the clean runner can pass on coverage tags alone.
- Do not implement any new feature, fixture semantics, or contract change after U10. A discovered contract defect requires a fresh review, dated operator decision, and resequenced plan rather than an in-place conformance workaround.

## Out of Scope

- New product behavior, adapters, schema fields, outcomes, exits, dependencies, or remediation code.
- Rewriting existing glossary entries.
- Weakening, skipping, quarantining, or conditionally bypassing any mandatory assertion.
- Committing, pushing, opening a PR, or publishing documentation.
