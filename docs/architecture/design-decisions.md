---
title: "Workstream Registration — Design Decisions (KTD1-13)"
date: 2026-08-07
verified: 2026-08-07
---

# Design Decisions (KTD1-13)

The plan's Planning Contract freezes thirteen key technical decisions (KTD1-KTD13, PLAN:184-200). They are the "why" behind every page of this set. Each row below distills one decision: what was decided, why, where the code enforces it, and its current status — including supersessions by dated operator decisions. "PLAN:NNN" refers to `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md`; the full decision narrative, including earlier operator decisions, lives there.

## The decisions

| # | Decision (distilled) | Rationale (distilled) | Enforced at | Status |
|---|---|---|---|---|
| KTD1 | One Python implementation on CPython 3.14.x with `jsonschema` 4.26.x and `Draft202012Validator`; no second runtime or abstraction layer. | The contracts are runtime-neutral; one pinned runtime keeps the executable proof tractable (PLAN:186). | `pyproject.toml` (`requires-python`, `jsonschema==4.26.0`), `src/workstream_registration/validation.py:145-154`; pins recorded in `contracts/workstream-registration/v1/compatibility.md:9-13` (CPython 3.14.6, jsonschema 4.26.0, sqlite3 3.50.4) | Settled. Selection rationale: `docs/solutions/tooling-decisions/runtime-validation-stack-python-jsonschema.md` (this doc states the pins and links; it does not re-narrate the selection). |
| KTD2 | The **marker** — the manifest file at the marker path `.workstream/manifest.json` — is the durable, assistant-neutral self-description within a workspace. | The namespace stays portable and extensible while executable behavior lives in the package (PLAN:187). | `src/workstream_registration/filesystem.py:87-89` (`PARENT_DIRNAME`, `MARKER_FILENAME`), `filesystem.py:147-149` (`marker_path`), `diagnostics.py:77` (`SAFE_PATH_MARKER`) | **Superseded in part.** The filename part of the 08-04 D3 decision and PLAN:551 was superseded by the **2026-08-07 operator decision** (digest `docs/session-digests/2026080702_marker_path_rename_manifest_json.md`): the marker path is now `.workstream/manifest.json`, while the term **marker** is retained. The superseded filename under `.workstream/` is quoted only in historical records (the digest itself names what it supersedes; see the governance convention in `docs/solutions/conventions/recorded-rename-ruling-vs-unrecorded-drift.md`). The path is frozen; see the maintenance rule in [README.md](README.md#maintenance-rules). |
| KTD3 | Version each workspace-data contract surface independently (JSON Schema Draft 2020-12); readers dispatch on the `version` field before applying the closed schema. | Independent surface versions keep marker, result, fixture, and protocol evolution explicit (PLAN:188). | `src/workstream_registration/validation.py:157-178` (dispatch), `validation.py:69` (`SUPPORTED_MARKER_VERSION = 1`), `workstream.schema.json:11-14` and `registration-result.schema.json:17-19` (`version` `const`) | Settled. |
| KTD4 | Keep durable and device-local references separate: the marker carries the literal `.` workspace self-reference; absolute paths, symlink-resolved paths, and local link locations live only in implementation state. | A device path in the marker would break cross-device identity (PLAN:189; PLAN:303). | `workstream.schema.json:35-37` (`workspace` `const "."`), `src/workstream_registration/projection.py:17-20` (schema holds local routing path only) | Settled. |
| KTD5 | Record-source URIs are open typed references accepted as untrusted data: any syntactically valid URI is accepted regardless of scheme or credential-bearing content; malformed ones warn. Never dereferenced, never inspected for secrets, never echoed. | Structural validity does not prove access or safety; provider access and ownership checks are deferred (PLAN:190; PLAN:305-306). | `workstream.schema.json:70-75` (pattern-only URI bound), `src/workstream_registration/validation.py:145-154` (no format checker → no dereference), `cli.py:166-171` (redaction), `projection.py:17-20` (no URI field) | Settled. The 08-01 operator decision removed URI content secret-scanning as an obligation (PLAN:538). |
| KTD6 | Bind single-use confirmation to a canonical semantic envelope: contract versions, every parsed marker field in order, the stable target handle, observed marker absence, and the explicit parent transition; digested with HMAC-SHA-256 under a process-ephemeral key. | The operator's confirmation is the authority boundary for the write; the envelope makes it impossible to confirm something other than what will be written (PLAN:191). | `src/workstream_registration/registration.py:555-576` (envelope), `registration.py:173-182` (digest/key), `registration.py:638-648` (exact-digest confirm), `registration.py:864-890` (pre-write revalidation and consumption) | Settled. The no-transition retry variant (existing `.workstream` parent, marker absent) was added by the 08-06 operator decision (PLAN:552). |
| KTD7 | An existing supported marker is registration authority: linking reads it unchanged; invalid, unsupported, ambiguous, or conflicting markers stop for operator resolution rather than repair or identity regeneration. | Retries and relinks must never create a second identity or repair what the operator did not confirm (PLAN:192). | `src/workstream_registration/registration.py:532-542` (inspection → `linked-existing`), `registration.py:1005-1035` (`link`) | Settled. |
| KTD8 | Versioned conformance fixtures are the project test boundary; the Python implementation must pass the mandatory corpus before claiming protocol compliance. | A malformed schema or contradictory fixture can survive manual review; an executed corpus cannot (PLAN:302). | `src/workstream_registration/conformance_runner.py:1192` (`run`), `tests/contracts/workstream-registration/expectations.json` | Settled. |
| KTD9 | Bound and isolate untrusted marker data: byte cap, nesting depth, field lengths, record-source count; reject duplicate keys, controls, and bidi overrides; labels and URIs are data, never instructions. | A shared marker can be hostile before schema validation; bounds make that impossible to exploit (PLAN:194; PLAN:304). | `src/workstream_registration/raw_guard.py:61-62` (caps), `raw_guard.py:89-103` (bidi set), `diagnostics.py:80-84` (output caps) | Settled. |
| KTD10 | Unregister is a confirmed conditional delete with the presence precondition inverted: bind to exact identity + stable target + observed presence, establish the cooperative lock, re-read twice, delete only on exact match, complete only on verified absence. | Deleting a changed marker is as dangerous as overwriting one; the operator's confirmation must bind to the exact thing being deleted (PLAN:195). | `src/workstream_registration/unregister.py:279-362` (full sequence) | Settled. Residual limitation disclosed, not an atomic guarantee (see below). |
| KTD11 | Guard raw input before schema validation: bound read to 262,145 bytes, strict UTF-8, token-aware depth scan (max 8), duplicate-name rejection, non-finite rejection, controls and `Bidi_Control` scan. | Python's decoder accepts duplicate keys, non-finite constants, and alternate encodings unless configured; these must be owned before parsing (PLAN:196; PLAN:308). | `src/workstream_registration/raw_guard.py:264-280` (pipeline), `raw_guard.py:149-172` (depth), `raw_guard.py:175-206` (hooks) | Settled. |
| KTD12 | Normalize parser and validator failures into bounded Python-owned diagnostics: phase, stable code, bounded safe path, count — never native messages, instance values, property names, URI content, or secrets. | Native `jsonschema` messages can embed instance values and URI content; the no-echo guarantee must be structural (PLAN:197; PLAN:309). | `src/workstream_registration/diagnostics.py:306-326` (reads only `error.validator` + `error.path`), `diagnostics.py:77` (fixed safe path), `diagnostics.py:88-101` (closed phase enum), `diagnostics.py:103-166` (closed code enum) | Settled. |
| KTD13 | Filesystem lifecycle baseline: per-workspace cooperative lock (atomic absent-parent step; bounded JSON metadata; release on normal and exceptional exit), create-only write with flush/sync/close, read-back re-validation with exact identity, stale-lock recovery requiring in-process confirmation, fail-closed when identity APIs are unavailable. | Writes and deletes must be safe against cooperating writers and recoverable after interruption without ever guessing (PLAN:198). | `src/workstream_registration/filesystem.py:471-514` (atomic parent+lock step), `filesystem.py:517-553` (bounded acquisition), `filesystem.py:579-614` (context-manager release), `filesystem.py:622-662` (recovery), `filesystem.py:665-695` (create-only write) | Settled. The atomic absent-parent step and the interrupted-parent retry variant were added by the 08-06 operator decision (PLAN:552). |

## The frozen result vocabulary (12 outcomes, no `invalid-marker`)

The result contract freezes a closed vocabulary of twelve outcomes (PLAN:391, 556; `contracts/workstream-registration/v1/registration-result.schema.json:22-35`). The constants live at `src/workstream_registration/registration.py:118-127` and `unregister.py:69-70`. Every outcome name is a state in the protocol's machine-readable table (protocol §13), and each maps to exactly one exit code via `cli.OUTCOME_EXIT_CODE` (`src/workstream_registration/cli.py:107-120`).

There is deliberately **no `invalid-marker` outcome**: any invalid, partial (interrupted write), or unsupported-version marker at the marker path reports `occupied-invalid` (PLAN:556; `CONCEPTS.md`). Contract edits must reference only names from this vocabulary.

| Outcome | Exit | Meaning (one line) |
|---|---|---|
| `registered` / `linked-existing` / `unregistered` / `invalid-marker-resolved` | 0 | Terminal success. |
| `cancelled` / `stopped` | 2 | No-write stop (rejection/EOF/digest mismatch; operational stop). |
| `occupied-invalid` | 3 | Invalid input — invalid/partial/unsupported marker present, never overwritten. |
| `conflict` / `changed-marker-stopped` | 4 | Conflict — projection duplicate signal; changed marker/target/identity, no delete. |
| `written-unverified` / `registered-unlinked` / `invalid-deleted-unverified` | 5 | Partial completion with an explicit recovery path. |
| (safe internal failure, no envelope) | 6 | `SAFE_INTERNAL_ERROR`; no result envelope produced (`cli.py:102`, `cli.py:733-735`). |

`rebuild` and `recover-lock` are deliberately **not** outcome operations: they report their own stable surfaces (`{status, entries, detail}` for rebuild — `src/workstream_registration/projection.py:144-158`; `{workspace, lock_state}` with `absent \| recovered \| held` for recover-lock — `cli.py:131-143`).

## The process-ephemeral HMAC confirmation design

Confirmation is a same-process handshake, not a persisted artifact (KTD6, PLAN:191):

- The digest is HMAC-SHA-256 of the canonical envelope under a key generated once per process with `secrets.token_bytes(32)` (`src/workstream_registration/registration.py:173-182`). The key and digest are never persisted or logged.
- **Same-process only**: because the key differs per invocation, a digest copied from an earlier run is always rejected — the `confirm <digest>` line must come from the preview currently on screen (`cli.py:380-397`).
- **Single-use**: the confirmation is consumed by the write it authorizes; a new inspection, a second write attempt, a terminal transition, or a marker-state change expires an unused confirmation (`registration.py:864-890`).

Full semantics (including why cross-invocation rejection is deliberate) are in [data-and-security.md](data-and-security.md).

## Disclosed residual limitations

These are documented limitations, not claims of atomicity:

1. **Non-cooperating-writer time-of-check/time-of-use race.** Create-only writes and conditional deletes are safe against cooperating writers (the lock protocol); a non-cooperating external writer can race the check-then-act window. This is disclosed, not represented as an atomic guarantee (KTD10/PLAN:195, KTD13/PLAN:198; protocol §11; `contracts/workstream-registration/v1/compatibility.md:31-33`). One consequence is recorded as an operator decision: if unregister's absence read-back fails after a successful conditional delete, the result reports `changed-marker-stopped` — fail-closed within the frozen vocabulary (`compatibility.md:35-37`; `src/workstream_registration/unregister.py:355-360`).
2. **Cross-instance duplicate detection is deferred.** Multiple copies of a workstream are the operator's choice; v1 performs no automatic duplicate detection or resolution. The projection's write-time `conflict` outcome is the only in-scope duplicate signal (08-02 operator decision, PLAN:542; `src/workstream_registration/projection.py:653-659`).
3. **POSIX is declared, not tested.** The tested filesystem profile is Windows NTFS; POSIX branches are implemented fail-closed but not tested on the declaring host (`compatibility.md:17-19`).

## Related

- The full decision and requirement narrative: `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md` (KTDs at PLAN:184-200, operator decisions at PLAN:536-557)
- How the decisions shape behavior: [state-machine.md](state-machine.md), [data-and-security.md](data-and-security.md), [filesystem-and-projection.md](filesystem-and-projection.md)
- The governance convention for superseding these decisions: `docs/solutions/conventions/recorded-rename-ruling-vs-unrecorded-drift.md`
