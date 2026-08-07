# Workstream Registration Protocol (v1)

Contract surface: `workstream-registration/v1` (KTD3, PLAN:188). This document is the
versioned protocol contract for registration and unregister states and authority
transitions (U2, PLAN:367-379). It defines inspection, drafting, confirmation,
write/read-back, linking, retry, unregister, and stop behavior. It does not change
product authority (`VISION.md`), the marker contract (`workstream.schema.json`), or the
result vocabulary (frozen at PLAN:391/PLAN:556; `registration-result.schema.json` is
authored by U3).

## 1. Purpose and scope

The protocol governs how an Arjim instance moves a workspace through registration and
unregistration without ever turning an unconfirmed draft, an invalid marker, a device
path, or a regenerated identity into authoritative workstream memory (PLAN:42).

Invariants that hold for every transition in this document:

- **No transition writes before exact confirmation.** The only writes in the protocol
  (marker creation, lock files, conditional delete) happen inside the `writing`,
  `deleting`, and `occupied-invalid` resolution states, all entered only after exact
  operator confirmation (PLAN:379). The machine-readable table in section 13 marks every
  transition `writes_before_confirmation: false`.
- **Create-only marker writes.** The final marker is opened with exclusive-create
  semantics and never silently replaces an existing marker (R4, PLAN:96; KTD13, PLAN:198).
- **Identity is never regenerated.** Retries, relinking, and read-back failures recover
  an existing identity after a successful write; they never create a second one (R14,
  PLAN:118; PLAN:375).
- **Unregister is a confirmed conditional delete** with the presence precondition
  inverted relative to registration (KTD10, PLAN:195).

## 2. Vocabulary

- **Marker** — the durable document at `.workstream/workstream.json` (R10, PLAN:111;
  KTD2, PLAN:187). Registration authority.
- **Marker path** — the fixed location `.workstream/workstream.json` within a workspace
  (CONCEPTS.md:31). Frozen; do not reopen (PLAN:551).
- **`.workstream` parent** — the directory that holds the marker and the lock file.
- **Stable target handle** — the identity anchor for confirmation; defined in section 3
  (PLAN:200).
- **State names** — the state/transition table in section 13 uses exactly the ids below.
  The frozen result vocabulary names (`registered`, `linked-existing`, `cancelled`,
  `stopped`, `written-unverified`, `registered-unlinked`, `unregistered`,
  `occupied-invalid`, `invalid-marker-resolved`, `invalid-deleted-unverified`,
  `changed-marker-stopped`, `conflict` — PLAN:391, 556) are states in the table; there is
  deliberately no `invalid-marker` outcome (PLAN:556; CONCEPTS.md:62).

## 3. Stable target handle

For the declared local filesystem profile (Windows NTFS; POSIX-compatible local
filesystems, PLAN:170), the stable target handle is a tuple of:

1. the filesystem identity of the inspected workspace directory, and
2. the identity of its `.workstream` parent,

captured with platform directory/file identity APIs rather than a path string
(PLAN:200). When `.workstream` is absent at inspection, the parent component is the
explicit `ABSENT` sentinel.

Rules:

- Symlink aliases are equivalent only when they resolve to the same captured identities.
- Parent substitution, redirected marker components, or a different workspace-directory
  identity invalidates the confirmation (PLAN:200).
- If the declared identity APIs are unavailable on the host, the inspection fails closed
  (no draft, no confirmation, no write) and reports `stopped` (PLAN:200).
- The profile records which identity APIs are supported; the compatibility declaration
  (U4/U11) records the tested profile.

## 4. State reference (prose)

Every state below documents entry conditions, side effects, allowed transitions,
terminal-or-recovery path, and retry behavior. The machine-readable table in section 13
is authoritative for transition validity; the prose is the normative explanation.

### 4.1 `inspection`

- **Entry conditions:** The operator points at a workspace location (initial point,
  retry, relink, or recovery after any terminal state). Read-only.
- **Side effects:** Captures the stable target handle (workspace-directory identity +
  parent identity or `ABSENT` sentinel), observed marker presence, marker validity
  (raw-guard + Draft 2020-12 + version dispatch, KTD3), and marker identity. Nothing is
  written. Redirection of the marker path or a marker component that resolves to a
  different identity than the captured tuple is rejected.
- **Allowed transitions:**
  - `inspection -> draft-ready` when the marker is absent (parent absent or present)
    and a registration draft can be produced.
  - `inspection -> linked-existing` when a supported valid marker is present (KTD7,
    PLAN:192): linking reads it unchanged; no confirmation, no write, identity never
    regenerated.
  - `inspection -> occupied-invalid` when a marker is present but invalid, partial
    (interrupted write), or unsupported-version (PLAN:556; CONCEPTS.md:62).
  - `inspection -> unregister-draft` when the operator requests unregister of a valid
    supported marker.
  - `inspection -> stopped` on missing/inaccessible/non-directory workspace, redirected
    marker components, or unavailable identity APIs (fail closed, PLAN:200).
- **Terminal or recovery path:** Non-terminal; every outcome routes to a follow-on
  state.
- **Retry behavior:** Inspection is idempotent and re-runnable; a retry re-captures the
  target handle and re-observes marker state (a marker may appear, disappear, or change
  between inspections — each retry starts from the fresh observation).

### 4.2 `draft-ready`

- **Entry conditions:** A canonical confirmation envelope (section 5) has been produced
  from a successful inspection of a marker-absent workspace (parent absent or present).
  Awaiting operator confirmation.
- **Side effects:** Operator preview (field summary: label, local paths, and structural
  fields shown; record-source URI content redacted) and an in-memory HMAC-SHA-256 digest
  of the envelope under a process-ephemeral key. The key and digest are never persisted
  or logged; full record-source URI content is never echoed (KTD6, PLAN:191; PLAN:546).
  The confirmation is single-use and unexpired.
- **Allowed transitions:**
  - `draft-ready -> writing` on exact confirmation after pre-write revalidation
    (section 5, "Consumption"): workspace identity unchanged, expected parent transition
    succeeded, draft revalidated, lock acquired. The confirmation is consumed.
  - `draft-ready -> cancelled` on operator rejection, EOF, or digest mismatch — writes
    nothing (F4, PLAN:83; AE4, PLAN:129).
  - `draft-ready -> inspection` when the confirmation is expired (see section 5:
    a new inspection, a second write attempt, a terminal transition, or a marker-state
    change expires unused confirmation). The unused confirmation is discarded.
- **Terminal or recovery path:** Non-terminal; confirmation or expiry routes onward.
- **Retry behavior:** A new inspection produces a new draft and a new confirmation; an
  old digest is never accepted across invocations because the HMAC key is
  process-ephemeral (KTD6, PLAN:191; PLAN:475).

### 4.3 `writing`

- **Entry conditions:** Exact confirmation consumed and the per-workspace lock held
  (section 6). The first and only state in which a marker write may occur.
- **Side effects:** Exclusive-create of the final marker at `.workstream/workstream.json`
  (no replacement), complete write of the bounded document, flush, request
  synchronization, close; reopen, re-run raw-guard + schema validation, verify exact
  identity (read-back); then projection update (KTD13, PLAN:198). The lock is released on
  normal or exceptional exit.
- **Allowed transitions:**
  - `writing -> registered` — read-back verified, exact identity matches, projection
    update linked (AE1; PLAN:126).
  - `writing -> registered-unlinked` — read-back verified, but the projection/link
    update failed (AE7, PLAN:132; the failure mapping is owned by U10, PLAN:451/453).
  - `writing -> written-unverified` — read-back failure (including read-back resolving
    to a different target than the confirmed one, PLAN:452); identity is never
    regenerated (PLAN:451).
  - `writing -> conflict` — projection write-time conflict: the captured target already
    holds a different identity; the marker is unchanged (PLAN:528, 556).
  - `writing -> linked-existing` — exclusive-create collision: another writer created
    the marker first and it reads back valid and supported; read unchanged, no write
    (concurrent create; R4, PLAN:96).
  - `writing -> occupied-invalid` — exclusive-create collision where the existing marker
    is invalid or partial; it is never overwritten (KTD13, PLAN:198).
  - `writing -> inspection` — exceptional exit/interruption (out-of-band, e.g. process
    kill) after parent-and-lock creation and before/during marker creation; the lock is
    released on exit; recovery is a fresh inspection, which observes an empty parent
    (no-transition retry variant) or a partial marker (`occupied-invalid`).
- **Terminal or recovery path:** Result outcomes reachable from `writing` are
  `registered`, `registered-unlinked`, `written-unverified`, `conflict`,
  `linked-existing`, and `occupied-invalid`; the interruption path routes to a fresh
  `inspection`.
- **Retry behavior:** Retries recover an existing identity after a successful write;
  they never create a second identity (PLAN:375). If the marker was actually written and
  is valid, a retry degrades to linking (`linked-existing`).

### 4.4 `unregister-draft`

- **Entry conditions:** Inspection found a valid supported marker and the operator
  requested unregister (KTD10, PLAN:195; PLAN:169).
- **Side effects:** An unregister intent bound to the marker's exact identity, the stable
  target handle, and the observed marker presence; operator preview with redacted
  record-source URI content; in-memory HMAC digest as in section 5. Nothing is deleted.
- **Allowed transitions:**
  - `unregister-draft -> deleting` — exact confirmation, cooperative-writer lock
    established (section 6), and the post-lock re-read matches the confirmation (exact
    identity + stable target + observed presence).
  - `unregister-draft -> cancelled` — operator rejection/EOF/digest mismatch; no delete.
  - `unregister-draft -> inspection` — confirmation expired or the marker state changed
    (e.g. present-absent-present) before confirmation; fresh inspection required.
  - `unregister-draft -> changed-marker-stopped` — cooperation cannot be established
    (lock unobtainable within the bounded timeout, or held by a live non-cooperating
    writer), or the post-lock re-read shows a changed marker, target, or identity;
    no delete (KTD10, PLAN:195).
- **Terminal or recovery path:** Non-terminal; routes to `deleting`, `cancelled`,
  `inspection`, or `changed-marker-stopped`.
- **Retry behavior:** Recovery from any stop requires a fresh inspection, a new
  unregister draft, and a new confirmation (KTD10, PLAN:195).

### 4.5 `deleting`

- **Entry conditions:** Exact unregister confirmation consumed and the cooperative lock
  held; the post-lock re-read already matched.
- **Side effects:** Immediately before delete, re-read and compare the marker against
  the confirmation again (two-phase re-check, PLAN:463); then conditional delete; then
  absence read-back; then projection update (KTD13, PLAN:198; KTD10, PLAN:195). Lock
  released on normal or exceptional exit.
- **Allowed transitions:**
  - `deleting -> unregistered` — pre-delete re-read matches, delete performed, absence
    read-back verifies the marker is gone (AE8, PLAN:133).
  - `deleting -> changed-marker-stopped` — pre-delete re-read differs (marker replaced
    between the post-lock re-read and the delete); no delete.
- **Terminal or recovery path:** Terminal outcomes `unregistered` or
  `changed-marker-stopped`.
- **Retry behavior:** Same as `unregister-draft`: fresh inspection, new draft, new
  confirmation.

### 4.6 `registered` (terminal)

- **Entry conditions:** Write/read-back verified and projection linked (AE1, PLAN:126).
- **Side effects:** The marker is the durable registration record; the projection holds
  replaceable routing state only.
- **Allowed transitions:** None.
- **Terminal or recovery path:** Terminal success.
- **Retry behavior:** Re-running `register` on the same workspace degrades to linking
  and reports `linked-existing` without confirmation or write (PLAN:475, 555).

### 4.7 `linked-existing` (terminal)

- **Entry conditions:** Inspection (or a create-collision re-read) found a supported
  valid marker (KTD7, PLAN:192; AE2, PLAN:127).
- **Side effects:** Linking reads the marker unchanged; no confirmation, no write;
  identity never regenerated.
- **Allowed transitions:** None.
- **Terminal or recovery path:** Terminal success.
- **Retry behavior:** Idempotent; any later link/rebuild repeats the same outcome.

### 4.8 `cancelled` (terminal)

- **Entry conditions:** Operator rejection, EOF, or digest mismatch at any confirmation
  point (registration, unregister, or invalid-marker resolution); or a material
  draft/target change invalidating a confirmation before consumption (F4, PLAN:83).
- **Side effects:** No marker write, no delete, no projection change.
- **Allowed transitions:** None.
- **Terminal or recovery path:** Terminal no-write outcome (exit code 2, PLAN:556).
- **Retry behavior:** The operator starts again: fresh inspection, new draft, new
  confirmation. The expired/invalidated confirmation is never reused.

### 4.9 `stopped` (terminal)

- **Entry conditions:** Operational no-write stop: missing/inaccessible/non-directory
  workspace, redirected marker components, target-alias mismatch (identities differ),
  unavailable identity APIs (fail closed), or unwritable location (F5, PLAN:84;
  PLAN:200; R8-R9).
- **Side effects:** No write; bounded diagnostic; no draft.
- **Allowed transitions:** None.
- **Terminal or recovery path:** Terminal no-write outcome (exit code 2, PLAN:556).
- **Retry behavior:** The operator corrects the input condition and re-inspects.

### 4.10 `written-unverified`

- **Entry conditions:** Marker write succeeded but read-back verification failed —
  including read-back resolving from a different target than the confirmed one
  (PLAN:452; KTD13, PLAN:198).
- **Side effects:** The marker may exist and be valid; the identity is never regenerated
  (PLAN:451).
- **Allowed transitions:** None in-protocol; recovery is `written-unverified -> inspection`
  (section 13).
- **Terminal or recovery path:** Terminal partial-completion outcome (exit code 5,
  PLAN:556); recovery is a fresh inspection: a valid marker degrades to linking, a
  partial/invalid marker reports `occupied-invalid`, an absent marker permits a new
  registration with a fresh draft.
- **Retry behavior:** Retries recover an existing identity after a successful write;
  they never create a second identity (PLAN:375).

### 4.11 `registered-unlinked`

- **Entry conditions:** Marker written and read-back verified, but the local projection
  or link update failed (AE7, PLAN:132). The failure mapping is owned by U10
  (PLAN:451, 453); this document fixes the state now.
- **Side effects:** The marker remains authoritative; local routing state is absent or
  stale.
- **Allowed transitions:** `registered-unlinked -> linked-existing` on a later relink
  that reads the valid marker unchanged (section 13).
- **Terminal or recovery path:** Terminal outcome at write time (exit code 5, PLAN:556);
  recovery is the relink path (`link <workspace>`), which reuses the identity.
- **Retry behavior:** Relink and rebuild are idempotent; they never regenerate the
  identity and never edit the marker.

### 4.12 `unregistered` (terminal)

- **Entry conditions:** Confirmed conditional delete completed and absence read-back
  verified (AE8, PLAN:133; KTD10, PLAN:195).
- **Side effects:** The marker is absent at `.workstream/workstream.json`; the local
  projection entry may be removed. Deleting projection state never unregisters and is
  independent of this outcome (PLAN:319).
- **Allowed transitions:** None.
- **Terminal or recovery path:** Terminal success (exit code 0, PLAN:556).
- **Retry behavior:** A later re-registration is a fresh registration and generates a
  fresh identity (AE8, PLAN:133).

### 4.13 `occupied-invalid`

- **Entry conditions:** Inspection (or a create-collision re-read) found a marker at the
  marker path that is invalid, partial (interrupted write), or unsupported-version
  (KTD13, PLAN:198; PLAN:556; CONCEPTS.md:62). `occupied-invalid` covers every invalid
  marker present at the path; there is no separate `invalid-marker` outcome.
- **Side effects:** The invalid marker is never overwritten. Resolution is a separate
  bounded `resolve-invalid` envelope: marker-component identity, bounded byte
  length/digest, target handle, and current lock status are previewed and confirmed
  within the same process (PLAN:451; PLAN:475).
- **Allowed transitions:**
  - `occupied-invalid -> invalid-marker-resolved` — operator-confirmed resolution after
    active/stale lock checks and a confirmed target-handle match; delete; absence
    read-back verified (PLAN:451, 475).
  - `occupied-invalid -> invalid-deleted-unverified` — resolution delete succeeded but
    absence read-back failed (PLAN:451).
  - `occupied-invalid -> cancelled` — resolution rejected/EOF/digest mismatch; no write.
- **Terminal or recovery path:** Inspection outcome is terminal for the inspection
  command (exit code 3, PLAN:556); resolution is a recovery path via the transitions
  above.
- **Retry behavior:** Retry = a fresh operator-confirmed resolution envelope. A
  re-inspection that finds the marker gone reports resolution-complete behavior for
  `invalid-deleted-unverified` recovery (PLAN:451).

### 4.14 `invalid-marker-resolved` (terminal)

- **Entry conditions:** Confirmed resolution delete completed and absence read-back
  verified (PLAN:451).
- **Side effects:** The invalid marker is gone; the path is free for a new registration.
- **Allowed transitions:** None.
- **Terminal or recovery path:** Terminal success (exit code 0, PLAN:556).
- **Retry behavior:** Re-inspection then permits a fresh registration.

### 4.15 `invalid-deleted-unverified`

- **Entry conditions:** Resolution delete succeeded but absence read-back failed
  (PLAN:451).
- **Side effects:** The marker may or may not be absent; nothing is rewritten.
- **Allowed transitions:** None in-protocol; recovery is `invalid-deleted-unverified -> inspection`
  (section 13).
- **Terminal or recovery path:** Terminal partial-completion outcome (exit code 5,
  PLAN:556); recovery is re-inspection: an absent marker is treated as resolved, a
  still-present marker needs a fresh `resolve-invalid` (PLAN:451).
- **Retry behavior:** See recovery; no blind re-delete.

### 4.16 `changed-marker-stopped`

- **Entry conditions:** During unregister or resolution, cooperation could not be
  established, or a changed marker, target, or identity was observed at any re-read
  (KTD10, PLAN:195; PLAN:463).
- **Side effects:** No delete; the marker is untouched.
- **Allowed transitions:** None in-protocol; recovery is `changed-marker-stopped -> inspection`
  (section 13).
- **Terminal or recovery path:** Terminal stop outcome (exit code 4, PLAN:556).
- **Retry behavior:** Recovery requires a fresh inspection, a new unregister draft, and
  a new confirmation (KTD10, PLAN:195).

### 4.17 `conflict` (terminal)

- **Entry conditions:** Projection write-time conflict: the captured target already
  holds a different identity (PLAN:528). This is the only in-scope duplicate signal
  (PLAN:542); it is projection-write-time only (PLAN:556).
- **Side effects:** The marker is unchanged and remains authoritative; the projection
  does not link it.
- **Allowed transitions:** None.
- **Terminal or recovery path:** Terminal outcome (exit code 4, PLAN:556).
- **Retry behavior:** Duplicate workstreams are left to the operator, who owns any
  multiple copies; v1 performs no automatic duplicate detection or resolution
  (PLAN:542).

## 5. The canonical confirmation envelope (KTD6)

The single-use confirmation is bound to a canonical semantic envelope (KTD6, PLAN:191)
containing, in order:

1. **Contract versions** — marker contract version (v1 = `1`), the conformance/result
   surface version, and the protocol version this document identifies.
2. **Every parsed marker field, in order** — `version`, `identity`, `label`, `kind`,
   `workspace` (literal `.`), and every `record_sources` entry (`type`, `uri`) in the
   declared order. Property ordering is significant for the envelope; insignificant
   whitespace may change during serialization. Duplicate JSON keys are invalid
   (KTD11, PLAN:196) and never reach the envelope.
3. **The stable target handle** per the declared filesystem profile (section 3):
   filesystem-identity tuple; the `ABSENT` sentinel for the `.workstream` parent
   component when absent; fail-closed when identity APIs are unavailable.
4. **Observed marker absence** — the explicit observation that no marker exists at the
   marker path at inspection time.

The expected first-registration parent transition is represented explicitly in the
envelope as `.workstream: ABSENT -> created-parent-identity`; that transition is
permitted only when the workspace-directory identity remains unchanged and is not itself
a handle mismatch (KTD6, PLAN:191).

**No-transition retry variant (08-06 decision, PLAN:552):** a retry that observes an
existing `.workstream` parent with no marker is a no-transition confirmation variant:
the captured parent identity must match, the marker must remain absent, and the draft is
revalidated before writing. The envelope carries the parent identity instead of the
`ABSENT` sentinel and declares no parent transition.

**Consumption:** the implementation revalidates the same workspace identity before
writing, captures and revalidates the newly created parent identity, and verifies the
marker during read-back. The current attempt consumes the confirmation only after
pre-write revalidation and the expected parent transition succeed. A new operator
inspection, a second write attempt, a terminal transition, or a marker-state change
expires unused confirmation (KTD6, PLAN:191).

**Operator surface:** the CLI presents a field summary — label, local paths, and
structural fields shown; record-source URI content redacted — plus an in-memory
HMAC-SHA-256 digest of the envelope using a process-ephemeral key. The key and the
digest are never persisted or logged, and full record-source URI content is never
echoed (KTD6, PLAN:191; PLAN:546). Confirmation is `confirm <digest>` read from stdin;
cancellation, EOF, or a mismatched digest performs no write (PLAN:475).

## 6. Confirmation and rejection

- **Confirm (exact draft only):** `confirm <digest>` matches the in-memory digest of the
  current envelope. This is the only path that permits a write. The confirmation is
  single-use and process-local; a digest is never accepted across invocations.
- **Reject:** operator cancellation, EOF, or digest mismatch. Writes nothing. Enters
  `cancelled` (no write) for the current invocation.

## 7. Lock acquisition (KTD13)

Before any marker write, the per-workspace cooperative lock is acquired:

- **Absent parent:** lock acquisition and parent creation are one atomic step — create
  the parent directory without replacement, then exclusively create
  `.workstream/.registration.lock` within it — before any marker write (PLAN:198, 552).
- **Existing parent:** the lock is acquired without creating or altering the parent
  (PLAN:198, 552).
- **Lock file:** created with exclusive-create semantics; bounded JSON metadata
  `{owner_id, pid, target_handle, started_at, lease_until}` (PLAN:198).
- **Timeout:** acquisition is bounded; a lock that cannot be acquired within the bound is
  a non-success stop for unregister (`changed-marker-stopped`, no delete) and a stop
  with no write for registration (KTD10, PLAN:195; KTD13, PLAN:198).
- **Release:** on normal and exceptional exit (finally semantics).
- **Stale-lock rule:** a lock is stale only when its lease has expired and its owner
  process is no longer alive (or the declared platform-equivalent liveness check says
  so). Recovery requires an in-process confirmation whose target handle matches the lock
  metadata and the current workspace (`recover-lock`, PLAN:475). A live owner's lock is
  never broken.
- **In-process confirmation recovery:** if the same process holds the lock from an
  interrupted attempt and the target handle matches, confirmation recovery may proceed
  without a new external actor.

## 8. Create-only write and read-back

After confirmation and lock acquisition (`writing` state):

1. Open the final marker with exclusive-create semantics (never replace).
2. Write the complete bounded document; flush; request synchronization (`os.fsync` on
   the declared profile); close.
3. Reopen; re-run raw-guard and schema validation; verify exact identity.
4. Only then report registration and update the projection (KTD13, PLAN:198; PLAN:233).

An interrupted partial or invalid marker is occupied and invalid and is never
overwritten; inspection reports `occupied-invalid`, and only an explicit
operator-confirmed resolution may remove it (KTD13, PLAN:198; PLAN:451).

## 9. Existing supported marker

A valid supported marker is registration authority: linking reads it unchanged, requires
no confirmation, performs no write, and never regenerates the identity (KTD7, PLAN:192).
`register` on such a workspace degrades to linking and reports `linked-existing`
(PLAN:475, 555).

## 10. Invalid and occupied markers

An invalid, partial, or unsupported-version marker at the marker path reports
`occupied-invalid` on inspection (PLAN:556; CONCEPTS.md:62). Resolution is a separate
bounded, operator-confirmed `resolve-invalid` envelope previewed and confirmed in the
same process (PLAN:451, 475), following the lock checks and target-handle-match rules in
section 7. Successful absence read-back reports `invalid-marker-resolved`; the
delete-succeeded/read-back-failed branch reports `invalid-deleted-unverified` and
requires re-inspection (PLAN:451).

## 11. Unregister (KTD10)

Unregister is a confirmed conditional delete with the presence precondition inverted:

- Confirmation binds to the marker's exact identity, the stable target handle, and the
  observed marker presence.
- The cooperative-writer lock is established before deletion; if cooperation cannot be
  established, the implementation stops without deleting (`changed-marker-stopped`).
- After lock acquisition the marker is re-read and compared with the confirmation; it is
  re-read and compared again immediately before the delete (two-phase, PLAN:463).
- Delete proceeds only when both comparisons match; completion requires absence
  read-back (`unregistered`).
- Any changed marker, target, or identity observed at either comparison stops the
  operation without deleting (`changed-marker-stopped`); recovery is a fresh inspection,
  a new unregister draft, and a new confirmation.

**Residual limitation (disclosed, not an atomic guarantee):** the
time-of-check/time-of-use race against non-cooperating external writers is a documented
residual limitation, not a claimed atomic guarantee (KTD10, PLAN:195; KTD13, PLAN:198).

## 12. Terminal states and recovery matrix

| Terminal state | Exit code (PLAN:556) | Recovery |
|---|---|---|
| `registered` | 0 | re-run `register` -> `linked-existing` |
| `linked-existing` | 0 | none needed; idempotent |
| `unregistered` | 0 | fresh registration (fresh identity, AE8) |
| `invalid-marker-resolved` | 0 | fresh registration |
| `cancelled` | 2 | fresh inspection + new draft + new confirmation |
| `stopped` | 2 | correct input condition; re-inspect |
| `occupied-invalid` (inspection) | 3 | operator-confirmed `resolve-invalid` |
| `conflict` | 4 | operator resolves duplicates (PLAN:542) |
| `changed-marker-stopped` | 4 | fresh inspection + new draft + new confirmation |
| `written-unverified` | 5 | fresh inspection (valid -> linked-existing; partial -> occupied-invalid; absent -> new draft) |
| `registered-unlinked` | 5 | relink / rebuild reuses identity |
| `invalid-deleted-unverified` | 5 | re-inspection (absent = resolved; present = fresh resolve-invalid) |

## 13. MECHANIZATION: machine-readable state/transition table (REV:65; spec:346-350)

The table below is machine-readable (a single JSON fenced block). Every state named by
any fixture's declared outcome exists in `states`; every state either has >= 1 outgoing
transition or carries `terminal: true` (G3, spec:195-203). A state carries
`terminal: true` only when it has no outgoing transitions; states with documented
recovery paths carry the recovery transition instead. Every transition carries its guard
and declares whether it writes before exact confirmation (all are `false` — PLAN:379).

```json
{
  "protocol": "workstream-registration/v1",
  "states": [
    {"id": "inspection", "terminal": false},
    {"id": "draft-ready", "terminal": false},
    {"id": "writing", "terminal": false},
    {"id": "unregister-draft", "terminal": false},
    {"id": "deleting", "terminal": false},
    {"id": "registered", "terminal": true},
    {"id": "linked-existing", "terminal": true},
    {"id": "cancelled", "terminal": true},
    {"id": "stopped", "terminal": true},
    {"id": "written-unverified", "terminal": false},
    {"id": "registered-unlinked", "terminal": false},
    {"id": "unregistered", "terminal": true},
    {"id": "occupied-invalid", "terminal": false},
    {"id": "invalid-marker-resolved", "terminal": true},
    {"id": "invalid-deleted-unverified", "terminal": false},
    {"id": "changed-marker-stopped", "terminal": false},
    {"id": "conflict", "terminal": true}
  ],
  "transitions": [
    {"from": "inspection", "to": "draft-ready", "guard": "marker absent (parent absent or present); stable target handle captured; registration draft produced", "writes_before_confirmation": false},
    {"from": "inspection", "to": "linked-existing", "guard": "supported valid marker present (KTD7); no confirmation, no write, identity never regenerated", "writes_before_confirmation": false},
    {"from": "inspection", "to": "occupied-invalid", "guard": "marker present but invalid/partial/unsupported-version (incl. interrupted partial write); never overwritten", "writes_before_confirmation": false},
    {"from": "inspection", "to": "unregister-draft", "guard": "operator requests unregister of a valid supported marker; draft bound to exact identity + stable target + observed presence (KTD10)", "writes_before_confirmation": false},
    {"from": "inspection", "to": "stopped", "guard": "missing/inaccessible/non-directory workspace, redirected marker components, or identity APIs unavailable; fail closed (PLAN:200)", "writes_before_confirmation": false},
    {"from": "draft-ready", "to": "writing", "guard": "exact confirmation; pre-write revalidation (workspace identity unchanged; expected parent transition ABSENT->created-parent-identity, or no-transition retry variant); draft revalidated; single-use confirmation consumed; lock acquired", "writes_before_confirmation": false},
    {"from": "draft-ready", "to": "cancelled", "guard": "operator rejection, EOF, or digest mismatch; no write", "writes_before_confirmation": false},
    {"from": "draft-ready", "to": "inspection", "guard": "confirmation expired (new inspection, second write attempt, terminal transition, or marker-state change); unused confirmation discarded", "writes_before_confirmation": false},
    {"from": "writing", "to": "registered", "guard": "exclusive create, complete write, flush, fsync, close, reopen, re-validation, exact identity verification; projection linked", "writes_before_confirmation": false},
    {"from": "writing", "to": "registered-unlinked", "guard": "read-back verified but projection/link update failed (U10 owns the mapping); marker authoritative", "writes_before_confirmation": false},
    {"from": "writing", "to": "written-unverified", "guard": "read-back failure (incl. read-back from a different target); identity never regenerated", "writes_before_confirmation": false},
    {"from": "writing", "to": "conflict", "guard": "projection write-time conflict: captured target already holds a different identity; marker unchanged", "writes_before_confirmation": false},
    {"from": "writing", "to": "linked-existing", "guard": "exclusive-create collision; existing marker valid and supported; read unchanged, no write (concurrent create)", "writes_before_confirmation": false},
    {"from": "writing", "to": "occupied-invalid", "guard": "exclusive-create collision; existing marker invalid/partial; never overwritten", "writes_before_confirmation": false},
    {"from": "writing", "to": "inspection", "guard": "exceptional exit/interruption; lock released; fresh inspection required (empty parent or partial marker observed)", "writes_before_confirmation": false},
    {"from": "unregister-draft", "to": "deleting", "guard": "exact confirmation; cooperative lock established; post-lock re-read matches confirmation (exact identity + stable target + observed presence)", "writes_before_confirmation": false},
    {"from": "unregister-draft", "to": "cancelled", "guard": "operator rejection/EOF/digest mismatch; no delete", "writes_before_confirmation": false},
    {"from": "unregister-draft", "to": "inspection", "guard": "confirmation expired or present-absent-present marker-state change; fresh inspection required", "writes_before_confirmation": false},
    {"from": "unregister-draft", "to": "changed-marker-stopped", "guard": "cooperation cannot be established, or post-lock re-read shows changed marker/target/identity; no delete (KTD10)", "writes_before_confirmation": false},
    {"from": "deleting", "to": "unregistered", "guard": "pre-delete re-read matches; conditional delete; absence read-back verified", "writes_before_confirmation": false},
    {"from": "deleting", "to": "changed-marker-stopped", "guard": "pre-delete re-read differs (marker replaced between re-reads); no delete", "writes_before_confirmation": false},
    {"from": "occupied-invalid", "to": "invalid-marker-resolved", "guard": "operator-confirmed resolution (same-process preview + digest); active/stale lock checks; target-handle match; delete; absence read-back verified", "writes_before_confirmation": false},
    {"from": "occupied-invalid", "to": "invalid-deleted-unverified", "guard": "resolution delete succeeded but absence read-back failed", "writes_before_confirmation": false},
    {"from": "occupied-invalid", "to": "cancelled", "guard": "resolution rejected/EOF/digest mismatch; no write", "writes_before_confirmation": false},
    {"from": "registered-unlinked", "to": "linked-existing", "guard": "later relink reads the valid marker unchanged; no write, no confirmation (AE7)", "writes_before_confirmation": false},
    {"from": "written-unverified", "to": "inspection", "guard": "recovery: fresh inspection (valid -> linked-existing, partial -> occupied-invalid, absent -> new draft); identity never regenerated", "writes_before_confirmation": false},
    {"from": "changed-marker-stopped", "to": "inspection", "guard": "recovery: fresh inspection + new unregister draft + new confirmation (KTD10)", "writes_before_confirmation": false},
    {"from": "invalid-deleted-unverified", "to": "inspection", "guard": "recovery: re-inspection; absent marker treated as resolved; still-present marker needs fresh resolve-invalid (PLAN:451)", "writes_before_confirmation": false}
  ]
}
```

## 14. Transition fixture `inputs` vocabulary

Transition fixtures under `tests/contracts/workstream-registration/transitions/` carry
kind `parsed-value` with the scenario's marker document in `payload` and the transition
context in the envelope's open `inputs` slot (conformance-case.schema.json,
U5 PLAN:341-352). The `inputs` vocabulary below is defined here (U2 owns it, PLAN:374):

- `scenario` — `"register" | "link" | "unregister" | "inspect"`: the command being
  executed.
- `observed` — the initial inspection observation:
  - `workspace_identity`: captured workspace-directory identity, or `null` when
    identity APIs are unavailable (fail closed).
  - `parent`: `"absent"`, or `{"identity": "<identity>"}` for a present `.workstream`
    parent.
  - `marker`: `"absent" | "valid" | "invalid" | "unsupported" | "partial"`.
  - `marker_identity`: observed marker identity or `null`.
- `draft` — the registration draft (marker-shaped object) or `null`.
- `bound_identity` — for `unregister` scenarios, the identity the confirmation is bound
  to; differs from the observed marker identity in the identity-mismatch twist.
- `confirmation` — `"exact" | "rejected" | "absent" | "mismatched" | "expired" | "reused"`.
- `lock` — `"absent" | "acquired" | "held-by-other" | "stale"`.
- `projection` — `"linked" | "unlinked" | "conflict" | "none"`.
- `twist` — the scenario variation: `"none" | "create-collision" |
  "read-back-other-target" | "redirected-marker-component" | "target-alias-mismatch" |
  "inaccessible-workspace" | "identity-apis-unavailable" | "draft-changed" |
  "target-changed" | "parent-created-interrupted" | "second-write-attempt" |
  "marker-state-change" | "marker-replaced" | "identity-mismatch"`.

The declared `outcome` of each fixture is the terminal state the scenario must reach
(section 13 vocabulary); every outcome used by a fixture exists in the state table
(G3, spec:195-203).
