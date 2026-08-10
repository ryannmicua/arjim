---
title: AT-03 - Manage Explicit Inventory
type: vertical-slice-plan
date: 2026-08-10
source_units: [U4]
depends_on: [AT-01]
---

# AT-03 - Manage Explicit Inventory

## Objective and Outcome

Provide the durable, owner-only, operator-curated list of workspace paths that bounds the v1 portfolio. Add, remove, list, and one-shot path override behavior are independently executable without claiming global completeness or silently rewriting durable inventory.

## Why This Is a Vertical Boundary

U4 spans persistence, owner-only enforcement, target identity, add/remove/list behavior, stable JSON output, and deliberate replacement. Although AT-05 later wires the complete top-level awareness surface, this slice already delivers a coherent inventory-management outcome with an executable handler and contract gate.

## Source Traceability

| Source | Coverage |
|---|---|
| U-ID | U4, kept intact |
| Requirements | R5, R5b, R11, R19, R20 |
| KTDs | KTD11, inventory portion of KTD13-KTD14, KTD20 |
| Flow | F2 inventory input half |
| Acceptance examples | AE7 inventory half, AE8 inventory half; storage portion of AE14 |

## Dependencies

- AT-01 inventory schema and exact version-space naming.
- Existing owner-only helpers and store-directory resolution are reused without modifying protected registration files.

## Files Likely Touched

- `src/awareness/inventory.py`
- `src/awareness/cli_inventory.py`
- `tests/python/test_awareness_inventory.py`
- `tests/contracts/awareness/inventory-list/valid/minimal-inventory-list.json`

## Implementation Approach

1. Create `<store_dir>/awareness/inventory.db` with the same fail-closed owner-only enforcement model as registration projection storage.
2. Record `inventory_contract_version` independently from every other version space.
3. Create exactly the five source-plan columns: `target_handle`, `path`, `registered`, `ordinal`, and `last_modified`, with the declared key/nullability behavior.
4. Capture target handles, preserve stable ordering, collapse identity aliases, and require deliberate confirmed replacement on collision.
5. Implement exact KTD13 inventory outcomes and exits, including idempotent `inventory-not-found` and `already-in-inventory` exit 4.
6. Verify registration from the marker unless the source-plan one-shot exception is explicitly selected; projection membership is never authority.
7. Render `inventory list --json` through `inventory.schema.json`; do not treat the schema as a SQLite-row schema.
8. Accept repeatable per-call paths for downstream checks without writing or redefining the durable inventory.
9. Never add URI fields, record-source copies, declaration values, or an inventory-complete flag.

## Test Scenarios

1. AE7 inventory half: adding a registered workspace stores its captured target and operator-supplied local path.
2. AE8 inventory half: one inventoried workspace among multiple valid markers produces one entry; no unlisted workspace is inferred.
3. Empty and populated list envelopes state explicit scope without claiming completeness.
4. `PRAGMA table_info(inventory)` returns exactly the five source-plan columns and properties.
5. A target collision returns `already-in-inventory` unless deliberate replacement is selected.
6. Removing a missing path is idempotent and returns `inventory-not-found` exit 0.
7. A symlink/alias collapses to one target and retains first-input ordering.
8. An unregistered workspace returns `not-registered` unless the source-plan exception is explicitly used.
9. Owner-only enforcement failure raises bounded storage failure and writes no row.
10. Repeatable one-shot paths select only supplied workspaces and leave database rows unchanged.
11. A JSON completeness claim fails contract validation.

## Verification Commands

| Command | Expected exit | Evidence |
|---|---:|---|
| `python -m pytest tests/python/test_awareness_inventory.py -v` | 0 | Owner-only store, exact columns, add/remove/list outcomes, stable JSON envelope, deliberate replacement, and non-writing path override pass. |

## Stop and Escalation Conditions

- Stop if inventory requires machine scan, automatic marker discovery, or a completeness claim.
- Stop if owner-only enforcement cannot be established on the tested host.
- Stop if a new column, URI copy, source-content copy, or generic version field appears necessary.
- Stop if one-shot paths would mutate durable inventory.

## Out of Scope

- Machine scan and inventory reconstruction.
- Record-source caching or workspace declaration copies.
- Portfolio rendering, source checks, reports, and scheduler behavior.
- Changes to registration projection schema or lifecycle.
