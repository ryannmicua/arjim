---
date: 2026-08-01
topic: arjim-raid-log
artifact_contract: ce-raid/v1
sources:
  - docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md
proof_url: https://www.proofeditor.ai/d/fpi7ic3c?token=6dbf1865-33a1-4c66-b70e-7ce678907fd9
proof_slug: fpi7ic3c
---

# Arjim RAID Log

Risks, Assumptions, Issues, and Dependencies register. Each register has an **Active** table (open items) and a **Resolved** table (closed items). The local file is canonical; edits to entries that carry a `proof_url` are pushed to their Proof doc.

Seeded from the workstream registration and discovery plan (`docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md`).

## Risks (R)

### Active

| ID | Title | Impact | Likelihood | Owner | Opened | Mitigation / Notes |
|---|---|---|---|---|---|---|
| R-001 | Contract without executable proof | High | Medium | Arjim CE | 2026-08-01 | A malformed schema or contradictory fixture can survive manual review. Mitigation: one expectation manifest, every fixture declares its expected result, and the pinned Python implementation executes the complete project corpus. |
| R-002 | Path portability | Medium | Medium | Arjim CE | 2026-08-01 | Device paths in the workspace reference would break cross-device identity. Mitigation: fixtures reject device paths in the workspace reference; record-home URIs may be local-resource but stay untrusted, non-dereferenceable data. |
| R-003 | Resource exhaustion | Medium | Low | Arjim CE | 2026-08-01 | A shared marker can be hostile before schema validation. Mitigation: KTD9 pre-parse and collection bounds; fixtures cover exact-limit and over-limit inputs. |
| R-004 | URI overclaim | High | Medium | Arjim CE | 2026-08-01 | Structural validity does not prove access, ownership, or safety. Mitigation: KTD5 prohibits automatic dereference, warns on malformed URIs, and distinguishes `not-checked`, `unsupported`, and inaccessible states. |
| R-005 | Secret leakage | High | Medium | Arjim CE | 2026-08-01 | URI syntax can contain sensitive-looking content. Mitigation: KTD9 accepts credential-bearing URIs as untrusted data, the Python implementation never inspects or dereferences URI content, never echoes sensitive values, and warns only on malformed syntax. |
| R-006 | Schema lock-in | Medium | Medium | Arjim CE | 2026-08-01 | A closed provider enum would force schema changes per integration. Mitigation: keep record-home type tokens open as workspace data and report unsupported capability separately in the Python implementation. |

### Resolved

| ID | Title | Impact | Opened | Resolved | Resolution |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Assumptions (A)

### Active

| ID | Assumption | Owner | Opened | Notes |
|---|---|---|---|---|
| A-001 | `VISION.md` remains product authority. | Arjim CE | 2026-08-01 | Any change to the plan must stay consistent with VISION.md. |
| A-002 | The operator is the sole v1 human actor. | Arjim CE | 2026-08-01 | No other human roles in scope for v1. |
| A-003 | Record homes are typed, absolute URI references validated for structure only; any syntactically valid URI is accepted regardless of scheme or credential-bearing components, and malformed ones warn. Provider access and ownership checks are deferred. | Arjim CE | 2026-08-01 | Reflects KD10 resolution. |
| A-004 | Record-home URIs are accepted as untrusted data even when credential-bearing; the Python implementation never dereferences or inspects them and diagnostics never echo them. The operator decides what the marker may contain. | Arjim CE | 2026-08-01 | Reflects KD10 resolution. |
| A-005 | Unregister uses the same operator-confirmation authority as registration; the Python implementation does not delete a marker without a confirmed exact identity. | Arjim CE | 2026-08-01 | Reflects KD9 / KTD10. |

### Resolved

| ID | Assumption | Opened | Resolved | Resolution |
|---|---|---|---|---|
| — | — | — | — | — |

## Issues (I)

### Active

| ID | Title | Severity | Owner | Opened | Status |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

### Resolved

| ID | Title | Severity | Opened | Resolved | Resolution |
|---|---|---|---|---|---|
| I-001 | URI validity and secret policy conflict | P1 | 2026-08-01 | 2026-08-01 | v1 accepts any syntactically valid record-home URI regardless of scheme or credential-bearing components; malformed URIs warn without invalidating the marker (KD10, KTD5, KTD9). Unsupported providers remain valid data with non-dereferenceable capability; diagnostics never echo URI content, labels, or secrets; the Python implementation does not inspect URI content. |
| I-002 | Create-only consistency domain | P1 | 2026-08-01 | 2026-08-01 | v1 permits weaker storage — no strongly consistent exclusive creation — and surfaces distinct identities as a `duplicate-registration` outcome that stops for operator-directed unregister (R15, R16; KTD10). Identical marker copies sharing one identity remain valid markers and are not duplicates. |

## Dependencies (D)

### Active

| ID | Dependency | Owner | Opened | Notes |
|---|---|---|---|---|
| D-003 | Exact Python dependency patch and filesystem profile selection. | Arjim CE | 2026-08-01 | CPython 3.14.x, `jsonschema` 4.26.x, `Draft202012Validator`, and SQLite are resolved; U6 records exact patches and the tested local filesystem profile before compatibility is claimed (KTD1, KTD11). |
| D-002 | `VISION.md` as product authority. | Arjim CE | 2026-08-01 | The plan defers to VISION.md for durable memory, access honesty, authority, and rebuildability. |

### Resolved

| ID | Dependency | Opened | Resolved | Resolution |
|---|---|---|---|---|
| D-001 | Future runtime and validation library selection. | 2026-08-01 | 2026-08-02 | Runtime selection is resolved to CPython 3.14.x with `jsonschema` 4.26.x, explicit `Draft202012Validator`, and stdlib `sqlite3`; exact patch pins and the supported local filesystem are tracked separately as D-003. |
