---
title: AT-01 - Awareness Contract Foundation
type: vertical-slice-plan
date: 2026-08-10
source_units: [U1]
depends_on: []
---

# AT-01 - Awareness Contract Foundation

## Objective and Outcome

Create the executable awareness contract set that every later slice consumes. The outcome is a version-dispatched schema and fixture corpus that freezes the two seven-value enums, KTD9 derivation, conventions/inventory/result shapes, adapter registry data, recommended defaults, compatibility, attribution shape, explicit-inventory metadata, and protected-source expectations without implementing adapters.

## Why This Is a Safe Vertical Boundary

U1 is a contract foundation rather than an operator-facing feature. It remains a standalone slice because it produces an independently executable artifact: bundled schemas, fixtures, registry data, compatibility declarations, and negative tests. Combining it with configure or checking would hide contract drift inside a much larger review. This is the smallest safe boundary because AT-02 through AT-04 cannot implement stable behavior until these names and shapes are frozen.

## Source Traceability

| Source | Coverage |
|---|---|
| U-ID | U1, kept intact |
| Requirements | R8, R9, R10, R11, R12, R13, R14, R14b, R15, R19, R20 |
| KTDs | KTD2-KTD9, KTD20; contract-facing portions of KTD13, KTD15-KTD17 |
| Flows | F2 contract inputs and result envelope only; no runtime flow |
| Acceptance examples | AE2-AE5, AE7-AE12, and AE14-AE16 contract shapes only; executable behavior remains with later slices |

Cross-slice ownership is intentional. This slice does not claim an AE complete merely because its envelope validates.

## Dependencies

None. Use the source plan and existing registration contract as read-only authorities.

## Files Likely Touched

- `contracts/awareness/v1/awareness-result.schema.json`
- `contracts/awareness/v1/awareness-protocol.md`
- `contracts/awareness/v1/conventions.schema.json`
- `contracts/awareness/v1/inventory.schema.json`
- `contracts/awareness/v1/adapter-registry.json`
- `contracts/awareness/v1/git/rules-v1.json`
- `contracts/awareness/v1/recommended-default-conventions.json`
- `contracts/awareness/v1/compatibility.md`
- `contracts/awareness/README.md`
- `contracts/README.md`
- `tests/python/test_awareness_contracts.py`
- `tests/contracts/awareness/fixtures/minimal-awareness-result.json`
- `tests/contracts/awareness/expectations.json`

## Implementation Approach

1. Create the awareness contract as a sibling of `contracts/workstream-registration/`, with integer `awareness_contract_version` dispatch independent of registration.
2. Freeze the exact per-source enum `current | stale | failed | inaccessible | unsupported | not-checked | bootstrap`.
3. Freeze the exact aggregate enum `current | stale | incomplete | nothing-pending | unconfigured | no-needs-me-rules | bootstrap` and encode KTD9 as the only normative derivation source.
4. Define the conventions schema with `schema_version`, `recommended_profile_revision`, per-adapter `adapter_contract_version`, explicit source enablement, rules enabled by list presence, freshness windows, declaration references, durable dispositions, and bounded attribution.
5. Define the inventory-list JSON envelope with `inventory_contract_version`, ordered paths, and explicit-inventory metadata. Do not add a completeness boolean.
6. Define registry and rules data for the one supported v1 adapter and the behind-only recommended behavior. Registry implementation resolution remains AT-04.
7. Define recommended profile revision 1 with the source plan's 24-hour integer default and documented minimum git rules.
8. Document references-only reports, missing-declaration-only scaffolding, attribution, opaque baseline behavior, privacy sinks, and all five exact version spaces.
9. Seed `tests/contracts/awareness/expectations.json` with the eight protected paths and the pinned values from source U1 without changing or recomputing those values in this decomposition.
10. Reject generic version keys and inventory completeness claims in executable negative fixtures.

## Test Scenarios

1. All bundled schemas validate their minimal valid fixtures.
2. Both closed enums contain exactly seven source-plan values with no aliases.
3. KTD9 data expresses every row and exact precedence, including mixed bootstrap/failure and unconfigured/failure discriminators.
4. Enabled and disabled source entries validate; a rule is enabled by presence only.
5. Attribution accepts only the two source-plan actors with bounded UTC time and digest reference.
6. Inventory envelopes with empty and populated path lists retain explicit scope and unknown global completeness.
7. Unsupported conventions schema numbers remain syntactically valid while reader rejection is left to AT-02.
8. A generic version key and a completeness claim fail validation.
9. Registry data and rules paths are syntactically valid, but implementation imports are not attempted.
10. Expectations contain exactly the eight protected registration paths and the source-plan pinned values.

## Verification Commands

| Command | Expected exit | Evidence |
|---|---:|---|
| `python -m pytest tests/python/test_awareness_contracts.py -v` | 0 | Schemas, fixtures, exact enums/KTD9 data, enablement, rules data, version naming, completeness rejection, and expectations baseline pass. |

## Stop and Escalation Conditions

- Stop if any enum value, KTD9 row/order, version-space name, recommended v1 rule, field boundary, or inventory-scope claim differs from the source plan.
- Stop if registry implementation resolution is required before AT-04.
- Stop if a protected path or pinned value appears stale; do not regenerate it without fresh readiness review and a dated operator decision.
- Stop if satisfying a schema requires a marker change, generic version field, new dependency, or copied workspace value.

## Out of Scope

- Adapter implementation or import-path resolution.
- Conventions filesystem lifecycle and configure interaction.
- Inventory SQLite storage.
- Check execution, state persistence, CLI/report rendering, scaffolding, and conformance runner implementation.
- Any source type beyond the source plan's v1 support.
