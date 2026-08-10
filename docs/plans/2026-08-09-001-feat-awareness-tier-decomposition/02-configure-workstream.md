---
title: AT-02 - Configure a Workstream
type: vertical-slice-plan
date: 2026-08-10
source_units: [U2, U3]
depends_on: [AT-01]
---

# AT-02 - Configure a Workstream

## Objective and Outcome

Complete F1 end to end: a registered workspace can accept recommended conventions or workspace-owned conventions, confirm exact content, create the first conventions file or conditionally update an existing one, verify it by read-back, and receive the exact KTD13 configure outcome and exit code.

## Split/Regroup Decision

U2 alone is a horizontal read/write lifecycle. U3 supplies marker-authority checks, recommendation preview, confirmation, CLI interaction, and result reporting. They are regrouped because neither is an independently useful configure outcome without the other. Their source order remains U2 before U3.

## Source Traceability

| Source | Coverage |
|---|---|
| U-IDs | U2 then U3 |
| Requirements | R1, R2, R3, R3b, R4, R12b, R14, R15; supporting R19-R20 boundaries |
| KTDs | KTD1, KTD2, KTD6 recommendation loading, KTD10 timestamps, KTD13 configure outcomes, KTD14 initial parser, KTD16 bounded errors, KTD20 naming |
| Flow | F1 complete |
| Acceptance examples | AE5 configure half, AE6 complete, AE12 configure half |

## Dependencies

- AT-01 must pass before conventions parsing or recommendation loading begins.
- Use the existing public `registration_lock` and marker authority without modifying protected registration files.

## Files Likely Touched

- `src/awareness/__init__.py`
- `src/awareness/filesystem.py`
- `src/awareness/conventions.py`
- `src/awareness/errors.py`
- `src/awareness/configure.py`
- `src/awareness/cli.py`
- `src/awareness/recommended_defaults.py`
- `tests/python/test_awareness_conventions.py`
- `tests/python/test_awareness_configure.py`
- `tests/contracts/awareness/conventions/valid/minimal-conventions.json`
- `tests/contracts/awareness/conventions/invalid/invalid-schema-version.json`
- `tests/contracts/awareness/conventions/invalid/invalid-rules-shape.json`
- `tests/contracts/awareness/configure/transitions/result-configured.json`
- `tests/contracts/awareness/configure/transitions/result-configured-existing-changed.json`

## Implementation Approach

1. Implement awareness-owned conventions path, create-only write, bounded read, absence verification, and conditional update primitives for `.workstream/conventions.json`.
2. Acquire the existing shared `.workstream/.registration.lock` through the public registration filesystem interface; do not call marker-bound create/read/absence primitives.
3. Mirror registration's confirmation, identity recapture, exclusive create/fsync, conditional compare-and-replace, directory fsync, reopen, validation, and exact read-back algorithms.
4. Dispatch readers on `schema_version`; dispatch embedded adapter rules on `adapter_contract_version`; reject generic version keys.
5. Implement the exact configure family from KTD13 and keep `AWARENESS_OUTCOME_EXIT_CODE` separate from registration's table.
6. Treat a valid marker at the supplied path as authority. Projection membership never decides `not-registered`.
7. Materialize recommended defaults from the frozen AT-01 resource, explicitly enable marker sources, retain the declared default freshness value, and permit workspace-owned overrides.
8. Bind the exact current file into updates. Re-read immediately before writing and stop without writing on any difference.
9. Persist only bounded attribution: accepted defaults use `assistant-drafted`; operator-supplied content uses `operator-confirmed`.
10. Report create/read-back partial success under the source-plan outcomes; never report completion when verification failed.

## Test Scenarios

1. AE6 happy path: confirmed exact content is created exclusive-create, read back, compared, and reported `configured` with exit 0.
2. AE6 partial paths: create success followed by read-back failure or mismatch is never reported configured.
3. AE5 configure half: a conditional update of existing conventions follows R3b and reports `configured-existing-changed`; recommendation-revision gap derivation and rendering remain AT-04 and AT-05 responsibilities.
4. R3b race: modifying the current file after draft binding yields `stopped`, no write, and unchanged replacement content.
5. AE12 configure half: unsupported conventions `schema_version` returns `schema-unsupported`, stable `UNSUPPORTED_CONVENTIONS_SCHEMA`, and exit 3 without writing.
6. Missing marker returns `not-registered` exit 3 before drafting.
7. Corrupt conventions return `conventions-invalid` and are never overwritten.
8. Cancellation returns `cancelled` exit 2 with no write.
9. Workspace or destination-parent identity replacement fails closed before write or during read-back.
10. Concurrent register/configure operations serialize through the shared lock.
11. Attribution distinguishes accepted recommendations from operator-supplied content without storing identity free text.
12. Protected registration sources and registration exit mapping remain unchanged.

## Verification Commands

Run in order:

| Command | Expected exit | Evidence |
|---|---:|---|
| `python -m pytest tests/python/test_awareness_conventions.py -v` | 0 | Create/update/read-back, identity, attribution, version dispatch, and configure outcome primitives pass. |
| `python -m pytest tests/python/test_awareness_configure.py -v` | 0 | F1 interaction, recommendation acceptance, conditional update, cancellation, marker authority, exits, and protected-source checks pass. |

## Stop and Escalation Conditions

- Stop if the shared lock cannot be used without changing a protected registration file.
- Stop if the write cannot satisfy exact confirmation, pre-write identity recapture, exclusive-create/conditional-update, fsync, and exact read-back.
- Stop if a new configure outcome or exit code appears necessary.
- Stop if a conventions change would overwrite corrupt content, store confirmation text/operator identity, or collapse version spaces.

## Out of Scope

- Automatic configure during registration.
- Silent defaults for unconfigured workstreams.
- Inventory management, source checks, public portfolio/needs-me/changed/report commands, and declaration scaffolding.
- Updating existing declarations or modifying the registration CLI.
