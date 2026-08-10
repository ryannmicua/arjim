---
title: AT-04 - Produce Honest Git Awareness
type: vertical-slice-plan
date: 2026-08-10
source_units: [U5, U6, U7]
depends_on: [AT-01, AT-02, AT-03]
---

# AT-04 - Produce Honest Git Awareness

## Objective and Outcome

Given inventory paths or a one-shot path set, produce one immutable awareness observation that safely reads supported git sources, evaluates configured needs-me rules, computes exact changed baselines and current-window freshness, derives the canonical aggregate state, projects portfolio/reference data, and atomically finalizes only eligible result/baseline pairs.

## Split/Regroup Decision

U5 ends at an adapter observation and candidate baseline; U6 supplies storage but no complete check; U7 closes the path through inventory, conventions, freshness, rules, aggregate derivation, reference read-through, and atomic finalization. U5 and U6 are therefore horizontal layers when isolated. Regrouping U5+U6+U7 creates the smallest complete domain-level awareness outcome while preserving their internal dependency order.

## Source Traceability

| Source | Coverage |
|---|---|
| U-IDs | U5 then U6 then U7 |
| Requirements | R0, R1, R2, R4, R5, R5b, R6, R6b, R6c, R7, R7b, R8, R9, R10, R11, R12, R12b, R13, R14, R14b, R15, R19, R20 |
| KTDs | KTD4-KTD10, KTD12, KTD16-KTD17, KTD19-KTD20; KTD11 consumption; implementation side of KTD3 and KTD13 |
| Flow | F2 check and derivation half; public surface remains AT-05 |
| Acceptance examples | AE1-AE5 engine halves, AE7-AE12 engine/render-model halves, AE15, AE16 rendering/offer half; adapter/database portions of AE14 |

## Dependencies

- AT-01 schemas, registry data, rules data, exact enums, KTD9, and version names.
- AT-02 supported conventions reader and recommended-default resource.
- AT-03 inventory and one-shot path selection.
- Existing owner-only helpers and system git binary on the tested profile.

## Files Likely Touched

- `src/awareness/adapters/__init__.py`
- `src/awareness/adapters/git.py`
- `src/awareness/adapters/dispatch.py`
- `src/awareness/adapters/types.py`
- `src/awareness/needs_me.py`
- `src/awareness/projection.py`
- `src/awareness/baselines.py`
- `src/awareness/rebuild.py`
- `src/awareness/check.py`
- `src/awareness/clock.py`
- `tests/python/test_awareness_git_adapter.py`
- `tests/python/test_awareness_adapter_dispatch.py`
- `tests/python/test_awareness_projection.py`
- `tests/python/test_awareness_baselines.py`
- `tests/python/test_awareness_rebuild.py`
- `tests/python/test_awareness_check.py`
- `tests/python/test_awareness_needs_me.py`
- `tests/contracts/awareness/adapters/canary/canary-git-uri.json`
- `tests/contracts/awareness/adapters/canary/canary-git-author-email.json`
- `tests/contracts/awareness/adapters/canary/canary-git-stdout-stderr.json`
- `tests/contracts/awareness/adapters/canary/canary-branch-name.json`
- `tests/contracts/awareness/adapters/git/tracking-ref-head-different.json`
- `tests/contracts/awareness/projection/canary/canary-projection-row.json`
- `tests/contracts/awareness/check/transitions/result-current.json`
- `tests/contracts/awareness/check/transitions/result-incomplete.json`
- `tests/contracts/awareness/check/transitions/result-bootstrap.json`
- `tests/contracts/awareness/check/transitions/result-unconfigured.json`
- `tests/contracts/awareness/check/transitions/result-mixed-bootstrap-failed.json`
- `tests/contracts/awareness/check/transitions/result-nothing-pending.json`
- `tests/contracts/awareness/check/transitions/result-no-needs-me-rules.json`

## Implementation Approach

1. Resolve registry entries by exact `(record_source_type, adapter_contract_version)` and validate implementation/rules-schema paths inside the awareness contract tree.
2. Return structured `unsupported` for unsupported declared pairs and structured `not-checked` for malformed type tokens without exposing the token value.
3. Resolve only workspace-relative git locators inside an identity-bound workspace; capture and revalidate workspace, target, repository, `.git` directory, and real-index identities around every subprocess and result read.
4. Hash or verify the real index, seed an isolated temporary index, set `GIT_OPTIONAL_LOCKS=0`, restrict git execution to the source plan's exhaustive command set, and prove the real index unchanged across every outcome.
5. Collect no subjects, author identity, filenames, source free text, raw diagnostics, or other unapproved data.
6. Return a frozen observation and bounded candidate baseline containing only the KTD17 fields. Never persist from adapter code and never serialize a raw branch/ref name.
7. Implement exact tracking-ref deltas using the prior committed tracking-ref endpoint, then advance the candidate to the endpoint observed during the current check.
8. Implement the two recommended git rules exactly: unresolved merge/rebase/cherry-pick conflict state and behind-only divergence. Ahead-only remains a change signal.
9. Create one owner-only `awareness-state.db` with exactly the two KTD12 tables and allow-listed columns. Enforce the bounded opaque payload cap.
10. Atomically commit an eligible result and candidate baseline together. Roll back both on injected failure. Adapter code receives no write-capable handle.
11. Implement `awareness rebuild` as one transaction clearing both state tables and performing no checks. Preserve conventions and inventory.
12. Prepare one pending observation from inventory/override paths, readable marker/conventions state, enabled required sources, adapter results, rules, freshness, aggregate, declaration references, and candidate baselines.
13. Implement KTD9 verbatim, with the readable-conventions guard before source dispatch and the rule-count gate before match count.
14. Recompute freshness from current conventions using per-source override before default and `now < deadline`; never trust a stored diagnostic deadline.
15. Produce due dates only from adapter structured fields. V1 git items omit the field.
16. Read bounded declaration values only for live projection; retain references/time/freshness in durable projection inputs.
17. Finalize eligible results exactly once only after publication success. Reusing an observation for multiple views cannot rerun checks or advance state twice.

## Test Scenarios

1. AE1: unreadable/unsupported conventions yield `unconfigured`, a configuration gap, no source dispatch, and no per-source results.
2. AE2: unsupported declared source yields per-source `unsupported` and aggregate `incomplete`.
3. AE3: all-current with enabled zero matches yields `nothing-pending`; zero enabled rules yields `no-needs-me-rules`.
4. Every KTD9 row executes, including bootstrap plus failure yielding `incomplete` and unconfigured plus induced failure yielding `unconfigured` with no scan.
5. Disabled sources are neither dispatched nor represented and cannot affect aggregate state.
6. AE4: rebuild clears both tables transactionally; next successful git check is `bootstrap`; durable conventions dispositions remain.
7. AE7/AE8 model halves: only inventory paths appear and metadata remains `explicit-inventory` with unknown global completeness.
8. AE9: matching git rules produce required fields and omit due date; no rule fabricates one.
9. AE10: first success bootstraps; committed successive checks report exact non-repeating deltas; failed checks and reset cases do not advance the prior baseline.
10. AE11: override beats default; one tick before deadline is current; exact deadline is stale; changing the declared window changes the next judgement.
11. AE12 model half: unsupported conventions version produces aggregate `unconfigured`, stable gap code, and no source status.
12. AE15: live read-through values are available only to the live projection; durable projection inputs retain references/time/freshness.
13. AE16 model half: missing reference produces a resolvable gap and scaffold offer without fabricated information.
14. Locator containment, missing repository, remote scheme, identity replacement, subprocess failure, timeout, malformed output, detached/unborn/branch-switch/forced-reset, and dirty/indexed repository cases follow source outcomes.
15. Normal result/baseline and rebuild failures roll back to logical row equality.
16. Privacy fixtures from adapter and state origins are absent from candidate payloads, database bytes, observations, and bounded errors according to R19.
17. Report publication failure simulation leaves prior state unchanged; final surface publication itself lands in AT-05.

## Verification Commands

Run in order:

| Command | Expected exit | Evidence |
|---|---:|---|
| `python -m pytest tests/python/test_awareness_adapter_dispatch.py tests/python/test_awareness_git_adapter.py -v` | 0 | Registry resolution, read-only git, exact deltas, locator/identity, index immutability, rules, reset matrix, candidate boundaries, and adapter privacy pass. |
| `python -m pytest tests/python/test_awareness_projection.py tests/python/test_awareness_baselines.py tests/python/test_awareness_rebuild.py -v` | 0 | Exact tables, owner-only storage, atomic result/baseline commit, rebuild rollback, inventory-removal invariant, and storage privacy pass. |
| `python -m pytest tests/python/test_awareness_check.py tests/python/test_awareness_needs_me.py -v` | 0 | One observation, KTD9, disabled-source exclusion, freshness override/boundary/window change, rules, references, bootstrap, and finalization boundaries pass. |

## Stop and Escalation Conditions

- Stop if git is unavailable, a locator cannot be checked without broader source access, or the real index changes in any test path.
- Stop on any prohibited-value echo or persistence outside R19's explicit carve-outs.
- Stop if any failure/partial/report-publication path advances a baseline or result incorrectly.
- Stop if KTD9 cannot be implemented exactly from AT-01 data, or if `nothing-pending` could occur without complete fresh non-bootstrap coverage and at least one enabled rule.
- Stop if storage needs a third table, extra column, decoded baseline field, conventions digest, declaration copy, or new dependency.
- Stop if a protected registration file must change.

## Out of Scope

- Public CLI/report publication and console-script registration.
- Workspace declaration writes.
- Non-git adapters, non-git delta, commit subjects, inferred due dates, scheduling, and proactive delivery.
- Machine scan, lifecycle-state field, and dedicated current-status view.
