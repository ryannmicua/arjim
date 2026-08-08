---
title: "Workstream Registration — State Machine"
date: 2026-08-07
verified: 2026-08-07
---

# State Machine

The protocol defines seventeen states — five flow states and twelve outcome states — and the transitions between them. The machine-readable table in the protocol (§13, `contracts/workstream-registration/v1/registration-protocol.md`) is authoritative; this page distills it. Every transition in the protocol carries `writes_before_confirmation: false`: no transition writes before exact operator confirmation.

The **marker** — the manifest file at `.workstream/manifest.json` — is the durable document these states read and write: registration states create it, linking states read it, unregister and resolution states delete it, and the recovery states determine what a fresh inspection will find.

The twelve outcome states are exactly the frozen result vocabulary — the same names a result envelope reports — while the five flow states (`inspection`, `draft-ready`, `writing`, `unregister-draft`, `deleting`) never surface as outcomes. See [design-decisions.md](design-decisions.md) for the vocabulary rule and exit codes, and `src/workstream_registration/registration.py:118-127` / `unregister.py:69-70` for the constants.

## The 17 states

| State | Meaning | Outgoing transitions (protocol §13) | Terminal / recovery | Exit code when it is the outcome |
|---|---|---|---|---|
| `inspection` | Read-only observation: capture the stable target handle, marker presence/validity, marker identity. Nothing is written. | `draft-ready`, `linked-existing`, `occupied-invalid`, `unregister-draft`, `stopped` | Entry state for every flow; non-terminal | — |
| `draft-ready` | Canonical confirmation envelope produced; awaiting exact operator confirmation. | `writing`, `cancelled`, `inspection` (confirmation expired) | Non-terminal | — |
| `writing` | Confirmed create-only write + read-back under the per-workspace lock. | `registered`, `registered-unlinked`, `written-unverified`, `conflict`, `linked-existing` (create collision), `occupied-invalid` (collision), `inspection` (interruption) | Non-terminal | — |
| `unregister-draft` | Unregister intent bound to the marker's exact identity, target, and presence; awaiting confirmation. | `deleting`, `cancelled`, `inspection` (expiry / marker-state change), `changed-marker-stopped` | Non-terminal | — |
| `deleting` | Confirmed conditional delete + absence read-back. | `unregistered`, `changed-marker-stopped` | Non-terminal | — |
| `registered` | Marker written, read back, verified, projection linked. | — | Terminal | 0 |
| `linked-existing` | Supported valid marker read unchanged and linked; no write, no confirmation. | — | Terminal | 0 |
| `cancelled` | Rejection, EOF, or digest mismatch at a confirmation point; no write. | — | Terminal | 2 |
| `stopped` | Operational no-write stop (missing/inaccessible workspace, redirected marker components, unavailable identity APIs, unwritable). | — | Terminal | 2 |
| `written-unverified` | Marker write succeeded but read-back verification failed (incl. read-back from a different target); identity never regenerated. | `inspection` (recovery) | Recovery | 5 |
| `registered-unlinked` | Marker written and read-back verified, but the projection/link update failed; marker stays authoritative. | `linked-existing` (relink recovery) | Recovery | 5 |
| `unregistered` | Confirmed conditional delete completed; absence read-back verified. | — | Terminal | 0 |
| `occupied-invalid` | A marker is present but invalid, partial (interrupted write), or unsupported-version; never overwritten. Covers every invalid marker — there is no separate `invalid-marker` outcome. | `invalid-marker-resolved`, `invalid-deleted-unverified`, `cancelled` (resolution) | Inspection outcome; resolution is the recovery path | 3 |
| `invalid-marker-resolved` | Confirmed resolution delete completed; absence read-back verified. | — | Terminal | 0 |
| `invalid-deleted-unverified` | Resolution delete succeeded but absence read-back failed; the marker may or may not be absent; nothing rewritten. | `inspection` (recovery) | Recovery | 5 |
| `changed-marker-stopped` | During unregister/resolution: cooperation unavailable, or a changed marker/target/identity observed at any re-read; no delete. | `inspection` (recovery) | Recovery | 4 |
| `conflict` | Projection write-time conflict: the captured target already holds a different identity; marker unchanged. The only in-scope duplicate signal. | — | Terminal | 4 |

Exit codes come from `OUTCOME_EXIT_CODE` (`src/workstream_registration/cli.py:107-120`), which the conformance runner asserts against the corpus.

## Transition diagram

The full §13 transition set, GitHub-renderable:

```mermaid
stateDiagram-v2
    [*] --> inspection
    inspection --> draft-ready: marker absent (parent absent or present)
    inspection --> linked-existing: supported valid marker (KTD7)
    inspection --> occupied-invalid: invalid / partial / unsupported marker
    inspection --> unregister-draft: operator requests unregister
    inspection --> stopped: missing / inaccessible / redirected / identity APIs unavailable
    draft-ready --> writing: exact confirmation + pre-write revalidation + lock acquired
    draft-ready --> cancelled: rejection / EOF / digest mismatch
    draft-ready --> inspection: confirmation expired
    writing --> registered: read-back verified + projection linked
    writing --> registered-unlinked: read-back verified, link failed
    writing --> written-unverified: read-back failed (incl. different target)
    writing --> conflict: projection write-time conflict
    writing --> linked-existing: create collision, existing marker valid
    writing --> occupied-invalid: create collision, existing marker invalid
    writing --> inspection: interruption (out-of-band)
    unregister-draft --> deleting: exact confirmation + cooperative lock established
    unregister-draft --> cancelled: rejection / EOF / digest mismatch
    unregister-draft --> inspection: confirmation expired / marker-state change
    unregister-draft --> changed-marker-stopped: cooperation unavailable or re-read differs
    deleting --> unregistered: conditional delete + absence read-back verified
    deleting --> changed-marker-stopped: pre-delete re-read differs
    occupied-invalid --> invalid-marker-resolved: confirmed resolution + absence verified
    occupied-invalid --> invalid-deleted-unverified: delete ok, absence unverified
    occupied-invalid --> cancelled: resolution rejected / EOF / mismatch
    registered-unlinked --> linked-existing: relink reads the valid marker unchanged
    written-unverified --> inspection: recovery (fresh inspection)
    changed-marker-stopped --> inspection: recovery (fresh draft + confirmation)
    invalid-deleted-unverified --> inspection: recovery (re-inspection)
```

Recovery transitions are exactly four: `written-unverified → inspection`, `registered-unlinked → linked-existing`, `changed-marker-stopped → inspection`, `invalid-deleted-unverified → inspection` (protocol §13; verified in `docs/usage/how-it-works.md:173`).

## The unregister flow

Unregister is the mirror image of registration with the presence precondition inverted (KTD10). The full sequence is `src/workstream_registration/unregister.py:279-362`:

1. **Confirmation checks** — no confirmation, a consumed confirmation, or a different workspace path → `cancelled`, no delete (`unregister.py:299-305`).
2. **Fresh inspection** — a missing/inaccessible workspace → `stopped`; an invalid marker → `occupied-invalid`; an absent marker → `stopped` (nothing to delete; `unregister.py:306-317`).
3. **Pre-lock comparison** — the re-captured target handle and the raw marker bytes must match the confirmation-bound envelope; a changed target → `changed-marker-stopped` (`unregister.py:320-326`).
4. **Consume the confirmation** (`unregister.py:327`), then acquire the cooperative lock within the bounded timeout; an unobtainable lock → `changed-marker-stopped` (`unregister.py:329-331`).
5. **Post-lock re-read** — the marker is re-read and compared with the confirmation again (`unregister.py:332-344`).
6. **Pre-delete re-read** — immediately before the delete, the marker is re-read and compared a third time (`unregister.py:346-352`).
7. **Conditional delete** — `conditional_delete_marker` deletes only when the on-disk bytes equal the confirmation-bound bytes exactly (`unregister.py:353-354`; `filesystem.py:729-748`).
8. **Absence read-back** — verified absence → `unregistered` (exit 0), with best-effort projection entry removal (`unregister.py:355-358`); an unverifiable absence after a bounded retry → `changed-marker-stopped` (fail closed, `unregister.py:355-360`).

Any changed marker, target, or identity at any comparison stops without deleting; recovery always requires a fresh inspection, a new unregister draft, and a new confirmation.

## Recovery paths

### `recover-lock`

Recovers a stale per-workspace lock. The staleness rule is narrow: a lock is stale **only when its lease has expired AND its owner process is no longer alive** (`LockMetadata.is_stale`, `src/workstream_registration/filesystem.py:403-405`); the liveness check fails safe — a failed check treats the owner as alive, and a live owner's lock is never broken (`filesystem.py:315-333`). Recovery requires an in-process confirmation whose target handle matches both the lock metadata and the current workspace (`recover_lock`, `filesystem.py:622-662`). The CLI surface (`cli.py:314-377`) previews the target handle and observed lock state, reads `confirm <digest>`, and reports `{workspace, lock_state}` with `absent | recovered | held` (`cli.py:131-143`; exit 0 absent/recovered, 4 held, 2 cancelled).

### `resolve-invalid`

Resolves an `occupied-invalid` marker — the only path that may delete an invalid marker. The bounded resolution envelope previews the marker-component identity, byte length and SHA-256 digest, target handle, and current lock status, all confirmed in-process (`resolution_envelope`, `src/workstream_registration/registration.py:1038-1085`; preview `cli.py:293-305`). After active/stale lock checks and a confirmed target-handle match, the delete runs under the lock; verified absence → `invalid-marker-resolved` (exit 0), delete-ok/absence-unverified → `invalid-deleted-unverified` (exit 5, re-inspection required), rejection or changed marker → `cancelled` (`resolve_invalid`, `registration.py:1088-1145`).

### `rebuild`

Rebuilds the local projection from explicit operator-supplied workspace roots — never auto-discovered paths. It is a transactional replacement: one path means one workspace (no recursion), symlink aliases deduplicate by target handle retaining the first input's ordinal, stale entries are repaired in the same transaction, and any inaccessible or invalid root rolls the whole rebuild back leaving the previous projection unchanged (`Projection.rebuild`, `src/workstream_registration/projection.py:526-603`). It reports `{status, entries, detail}` (`projection.py:144-158`; CLI `cli.py:600-617`, exit 0 rebuilt / 3 failed).

## States → outcomes → exit codes

The twelve outcome states are the frozen vocabulary; the mapping below is asserted against the corpus by the conformance runner and can never diverge from `--json` output (PLAN:476; `src/workstream_registration/cli.py:104-120`):

| Outcome (state) | Exit | Kind | Recovery |
|---|---|---|---|
| `registered` | 0 | Terminal success | Re-run `register` degrades to linking. |
| `linked-existing` | 0 | Terminal success | None needed; idempotent. |
| `unregistered` | 0 | Terminal success | Fresh registration (fresh identity). |
| `invalid-marker-resolved` | 0 | Terminal success | Fresh registration. |
| `cancelled` | 2 | No-write stop | Fresh inspection → new draft → new confirmation. |
| `stopped` | 2 | No-write stop | Correct the input condition; re-inspect. |
| `occupied-invalid` | 3 | Invalid input | Operator-confirmed `resolve-invalid`. |
| `conflict` | 4 | Conflict | Operator resolves duplicates; no auto-resolution (PLAN:542). |
| `changed-marker-stopped` | 4 | Conflict | Fresh inspection → new draft → new confirmation. |
| `written-unverified` | 5 | Partial | Fresh inspection: valid → link, partial → resolve, absent → new draft. |
| `registered-unlinked` | 5 | Partial | `link` / `rebuild` restores routing state. |
| `invalid-deleted-unverified` | 5 | Partial | Re-inspect: absent = resolved, present = fresh `resolve-invalid`. |
| (safe internal failure) | 6 | No envelope | Report; no outcome produced (`cli.py:733-735`). |

## Related

- The authoritative machine-readable table: `contracts/workstream-registration/v1/registration-protocol.md` §13
- The vocabulary rule and exit-code freeze: [design-decisions.md](design-decisions.md)
- The lock, delete, and projection mechanics behind the recovery paths: [filesystem-and-projection.md](filesystem-and-projection.md)
