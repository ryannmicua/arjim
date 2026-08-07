# Workstream Registration — Operator Guide

The operator guide for workstream registration (v1): the durable workspace marker, the seven commands, the confirmation protocol, the result vocabulary and exit codes, and the boundaries of what this version does and does not do. All commands, output shapes, and exit codes in this guide were verified against the installed CLI on the tested profile (Windows NTFS, CPython 3.14.6). Paths, target handles, digests, and identities are shown with placeholders where machine-specific; digest values are example output and differ on every invocation.

## Contents

1. [Purpose](#1-purpose)
2. [Concepts](#2-concepts)
3. [Command reference](#3-command-reference)
4. [Typical workflows](#4-typical-workflows)
5. [The confirmation flow](#5-the-confirmation-flow)
6. [Exit codes](#6-exit-codes)
7. [Result envelope (`--json`)](#7-result-envelope---json-)
8. [Scope boundaries](#8-scope-boundaries)
9. [Troubleshooting](#9-troubleshooting)
10. [Support profile and conformance](#10-support-profile-and-conformance)

---

## 1. Purpose

Workstream registration is the v1 entry path by which a workspace becomes a registered workstream. You point the CLI at a workspace, inspect it, confirm one exact draft, and the CLI writes a durable marker at `.workstream/manifest.json`. The marker is the registration record, and it is the point of the feature:

- **It survives any assistant, device, or local-state rebuild.** The marker is a plain JSON document inside the workspace. It does not live inside a chat history, an assistant cache, or a tool-specific store, so wiping or replacing any local state does not destroy the registration.
- **It preserves identity across rebuilds.** The marker carries a permanent workstream identity (RFC 4122 v4 UUID) that is never regenerated. Re-linking, rebuilding, and recovery after read-back failures all recover the existing identity; a second identity is never created for the same registration.
- **It is assistant-neutral.** Any reader that understands the v1 marker contract can recognize the workspace. Nothing about the marker binds it to a particular assistant or runtime.

The CLI is the only working entry path in this version. There is no machine scan, no registry consumption, and no auto-discovery: every command operates on explicit operator-supplied paths. Registration is workstream registration — you point, you confirm, it reads back.

**Why confirmation exists.** Nothing is written before the operator confirms the exact draft. Confirmation is the boundary between "a draft exists in memory" and "the workspace is now a registered workstream," and it exists because a marker is authoritative: it makes the workspace a discovery candidate for any conforming reader, and an unconfirmed or wrong draft must never become that. The same rule applies in reverse to unregistration: deleting the marker retires the registration, so the delete is a confirmed conditional delete bound to the exact identity observed at inspection.

## 2. Concepts

### Marker

The durable, assistant-neutral document at `.workstream/manifest.json` within a workspace. It is the registration authority. Its fields are closed by the v1 marker contract:

| Field | Rule |
|---|---|
| `version` | Required integer; v1 allows `1`. Readers dispatch on it before applying the schema. |
| `identity` | RFC 4122 v4 UUID, lowercase. Permanent; never regenerated. |
| `label` | Required, non-empty, at most 256 bytes. A mutable operator-facing name. A label is data, not an instruction. |
| `kind` | `direct` or `proxy`. `direct` = the workstream actually lives here; `proxy` = this workspace holds the marker for a workstream whose real location cannot store assistant metadata. |
| `workspace` | The literal `.` self-reference. Device paths and traversal are invalid. |
| `record_sources` | 1–32 typed absolute URI references (see below). Duplicates are invalid. |

On disk the marker is a single compact JSON document, e.g.:

```json
{"version":1,"identity":"<uuid>","label":"Q3 planning","kind":"direct","workspace":".","record_sources":[{"type":"planner","uri":"https://tasks.example.invalid/q3-planning"}]}
```

The marker is written with create-only semantics: an existing marker is never silently replaced. Registration completes only when read-back re-validates the file and verifies the exact identity.

Marker terminology that matters when reading output and errors:

- **Marker presence** — whether a marker exists at the marker path. Presence makes the workspace a registration or discovery candidate but does not by itself establish a valid registration.
- **Marker validity** — whether the marker satisfies its raw-input limits and schema (raw guard first, then Draft 2020-12 validation, then version dispatch).
- **Supported marker** — a valid marker whose version the current reader understands. An unsupported version is not interpreted as registration authority by that reader; inspection reports it as `occupied-invalid`.
- **Marker path** — the fixed location `.workstream/manifest.json`. Frozen (2026-08-07 operator decision, digest 2026080702); it is the only marker that makes a workspace a registration or discovery candidate.

### Stable target handle

Every confirmation is bound to a **stable target handle**, not a path string: the packed platform directory/file identity pair (on Windows NTFS, the volume serial and file index from `os.stat`; on POSIX, `st_dev`/`st_ino`), plus the identity of the `.workstream` parent — or the explicit `ABSENT` sentinel when the parent does not exist yet. The CLI prints it as a compact `<workspace>:<parent>` pair. Consequences:

- A confirmation is invalidated if the workspace-directory identity or the marker components change between preview and write (parent substitution, redirected marker components, or a different workspace identity).
- Symlink aliases are equivalent only when they resolve to the same captured identities.
- When the identity APIs are unavailable on a host, inspection fails closed: no draft, no confirmation, no write, outcome `stopped`.

### Workstream identity

The permanent identifier recorded in the marker. It identifies the workstream across devices, assistants, workspace moves, and projection rebuilds. It is generated once at draft time and recovered, never regenerated, on every later path: linking reads it unchanged, retries after a successful write reuse it, and only a confirmed unregister followed by a fresh registration produces a new one.

### Record sources

Typed URI references to the authoritative locations of a workstream's records (Planner, SharePoint, email, and so on). Record sources are **untrusted data**:

- The implementation **never dereferences** them — no connection is made, nothing is fetched.
- It **never inspects them for credentials, tokens, or secrets**.
- **URI content is never echoed**: the CLI preview always shows `uri=<redacted>`, and diagnostics never carry URI content.
- Validity is syntactic only. Any well-formed URI is accepted regardless of scheme. An unsupported scheme stays a valid marker with a non-dereferenceable capability status; a malformed URI warns without invalidating the marker.

The `capabilities` array of the result envelope reports per-record-source status by 0-based index into the marker's `record_sources`, never by URI.

### Local link projection

Replaceable, device-local routing state derived by reading markers, so an assistant can find registered workstreams without a remembered map. It is a SQLite database in a private, owner-only directory (see [Support profile](#10-support-profile-and-conformance) for the location). The projection:

- is **never registration authority** — deleting the projection database never unregisters anything; a rebuild begins from the markers;
- is **owner-only enforced** (icacls on Windows, mode bits on POSIX) and fails closed when enforcement cannot be established;
- stores marker identity, label, marker version, target handle, local routing path, state, and a deterministic input ordinal — the schema has **no URI field at all**, so record-source content and credentials are never copied into it.

### Outcomes vocabulary

Every registration, inspection, linking, and unregister operation reports exactly one outcome from the frozen v1 vocabulary (there is deliberately no `invalid-marker` outcome — a malformed marker reports `occupied-invalid`):

`registered`, `linked-existing`, `cancelled`, `stopped`, `written-unverified`, `registered-unlinked`, `unregistered`, `occupied-invalid`, `invalid-marker-resolved`, `invalid-deleted-unverified`, `changed-marker-stopped`, `conflict`

Each outcome is a terminal or recovery state of the registration protocol; meanings are given per command below and in the [exit-code table](#6-exit-codes).

## 3. Command reference

All commands accept `--json` before or after the command name to emit the stable result envelope instead of the human summary (see [Result envelope](#7-result-envelope---json-)). `register`, `unregister`, `resolve-invalid`, and `recover-lock` are single-process interactive sessions; `inspect`, `link`, and `rebuild` are not.

### `register <workspace> --label <label> --record-source <type>=<uri>... [--kind direct|proxy]`

- **Flags:** `--label` (required), `--record-source` (required, repeatable, format `<type>=<uri>`, at least one), `--kind` (optional, `direct` default, `proxy` otherwise). Malformed `--record-source` entries, a missing `--label`, or an invalid `--kind` are usage errors (exit 3, no envelope).
- **What it does:** inspects the workspace, drafts the marker (generating a fresh identity), previews the exact draft, and writes it only after exact confirmation. The write is create-only; after the write the file is reopened, re-validated, and the identity verified (read-back); only then is the projection linked.
- **When to use it:** to register a workspace for the first time (or after an unregister). Re-running `register` on a workspace that already holds a valid supported marker degrades to linking: no preview, no confirmation, no write, and `linked-existing` is reported.
- **Resulting outcomes:** `registered` (write verified and linked), `linked-existing` (existing valid marker), `cancelled` (rejection/EOF/digest mismatch — no write), `stopped` (operational stop — no write), `occupied-invalid` (existing invalid/partial marker, never overwritten), `conflict` (projection write-time conflict: the captured target already holds a different identity; the marker is unchanged), `written-unverified` (write succeeded but read-back failed; the identity is never regenerated), `registered-unlinked` (write verified but the projection link failed; the marker remains authoritative).

### `inspect <workspace>`

- **Flags:** none.
- **What it does:** read-only inspection. Captures the stable target handle, observes marker presence and validity (raw-input guard + Draft 2020-12 validation + version dispatch), and reports the state. Nothing is written.
- **When to use it:** to check what state a workspace is in — `draft-ready` (no marker), `linked-existing` (valid supported marker), `occupied-invalid` (invalid/partial/unsupported marker), or `stopped` (missing/inaccessible/non-directory workspace, redirected marker components, or unavailable identity APIs).
- **Resulting outcomes:** inspection maps onto the result vocabulary: a valid marker reports `linked-existing`; an invalid marker reports `occupied-invalid` (exit 3); a missing or inaccessible workspace reports `stopped` (exit 2). A marker-absent workspace reports `draft-ready` in the human state line but maps to `stopped` on the result surface — the vocabulary has no draft-ready outcome, and inspection never writes.

### `link <workspace>`

- **Flags:** none.
- **What it does:** reads a supported valid marker unchanged and links it into the projection. No confirmation, no write, no new identity.
- **When to use it:** to (re-)establish local routing state for a workspace whose marker you know exists — for example after projection loss, before a full `rebuild`, or when a registration was left `registered-unlinked`.
- **Resulting outcomes:** `linked-existing` (linked), `stopped` (no marker at the marker path, or operational stop), `occupied-invalid` (invalid marker at the path).

### `rebuild <workspace>...`

- **Flags:** none. One or more positional workspace paths; each path means one workspace, no recursive traversal.
- **What it does:** transactionally replaces the projection from the explicit ordered list of roots. Symlink aliases deduplicate by target handle (first input's ordinal is retained); stale entries are repaired in the same transaction; any inaccessible or invalid root returns a non-success and the previous projection is left unchanged.
- **When to use it:** to rebuild local routing state from the ground up after projection loss or corruption. It is not a result-vocabulary operation: it reports its own stable surface, `{status, entries, detail}`.
- **Result:** human output `rebuild: rebuilt (<n> entries)` on success (exit 0), or `rebuild: failed` plus an `error:` line on stderr naming the failing root (exit 3). With `--json`, the full report is emitted on success and failure alike.

### `unregister <workspace>`

- **Flags:** none.
- **What it does:** a confirmed conditional delete. It drafts an unregister intent bound to the marker's exact identity, the stable target handle, and the observed marker presence; after exact confirmation it establishes the cooperative lock, re-reads and compares the marker after lock acquisition and again immediately before the delete (two-phase re-check), deletes, and completes only when absence read-back verifies the marker is gone. Recovery from any stop is a fresh inspection, a new draft, and a new confirmation.
- **When to use it:** to retire a registration, or to resolve a duplicate registration you own. It is the durable way to remove a marker; deleting the projection entry alone never unregisters.
- **Resulting outcomes:** `unregistered` (delete + verified absence), `cancelled` (rejection/EOF/digest mismatch — no delete), `changed-marker-stopped` (cooperation could not be established — e.g. the lock is held by a live writer — or a changed marker/target/identity was observed at a re-read; no delete), `stopped`/`occupied-invalid` (inspection found no valid supported marker).

### `resolve-invalid <workspace>`

- **Flags:** none.
- **What it does:** resolves an `occupied-invalid` marker. It previews the invalid marker's component identity (when one can be extracted), bounded byte length, SHA-256 digest of the file, the stable target handle, and the current lock status, and deletes only after the active/stale lock checks and a confirmed target-handle match. The invalid marker is never overwritten; resolution is delete, then absence read-back.
- **When to use it:** when inspection reports `occupied-invalid` — a malformed, partial (interrupted write), or unsupported-version marker blocks registration, and this is the only path that removes it. On a workspace that is not `occupied-invalid`, the command errors (exit 3).
- **Resulting outcomes:** `invalid-marker-resolved` (delete + verified absence; the path is free for a fresh registration), `invalid-deleted-unverified` (delete succeeded but absence read-back failed — re-inspect; an absent marker is treated as resolved, a still-present one needs a fresh resolution), `cancelled` (rejection/EOF/digest mismatch — no delete).

### `recover-lock <workspace>`

- **Flags:** none.
- **What it does:** an interactive, target-handle-bound recovery of a stale per-workspace lock (`.workstream/.registration.lock`). It previews the target handle and the observed lock state, and after confirmation replaces the lock only when it is stale — lease expired **and** the owning process is no longer alive. A live owner's lock is never broken. Not a result-vocabulary operation: it reports `{workspace, lock_state}` with `lock_state` in `absent | recovered | held`.
- **When to use it:** when a registration or unregister stopped because a lock could not be acquired and inspection of the lock file shows a dead owner (for example, after a crashed or killed process). On a workspace with no lock it confirms and reports `absent`; on a held lock it reports `held` (exit 4) and changes nothing.
- **Result:** human output `lock: <state>`. Exit 0 for `absent`/`recovered`, 4 for `held`, 2 for cancellation/EOF/digest mismatch.

## 4. Typical workflows

### First registration and day-to-day linking

```text
# register once (interactive)
> workstream-registration register <workspace> --label "Q3 planning" --record-source "planner=https://tasks.example.invalid/q3-planning" --record-source "email=https://mail.example.invalid/inbox"

preview: register
  workspace: <workspace>
  marker path: <workspace>\.workstream\manifest.json
  label: Q3 planning
  kind: direct
  record_sources: 2
    [0] type=planner uri=<redacted>
    [1] type=email uri=<redacted>
  digest: <digest>
confirm <digest>
outcome: registered
identity: <uuid>
```

`register` again on the same workspace — after a projection wipe, after a device change, or just to re-establish routing state — needs no confirmation and writes nothing:

```text
> workstream-registration register <workspace> --label "Q3 planning" --record-source "planner=https://tasks.example.invalid/q3-planning"
outcome: linked-existing
identity: <uuid>
```

The identity is the one already in the marker; it is never regenerated.

### Rebuilding local routing state after projection loss

```text
> workstream-registration rebuild <workspace-a> <workspace-b>

rebuild: rebuilt (2 entries)
```

The projection is replaced transactionally from the explicit roots; the markers are only read. If one root is invalid or inaccessible the rebuild fails as a whole and the previous projection is unchanged:

```text
> workstream-registration rebuild <workspace-a> <broken-path>
rebuild: failed
error: rebuild root failed: <broken-path>: IdentityUnavailableError
```

(`rebuild: failed` goes to stdout; the `error:` line goes to stderr. Exit code 3.)

### Recovery from `registered-unlinked`

The marker is authoritative and verified; only the local link failed. One command restores routing state — no confirmation, no write to the marker:

```text
> workstream-registration link <workspace>
outcome: linked-existing
identity: <uuid>
```

### Retiring a registration

```text
> workstream-registration unregister <workspace>
preview: unregister
  workspace: <workspace>
  marker path: <workspace>\.workstream\manifest.json
  identity: <uuid>
  label: Q3 planning
  kind: direct
  record_sources: 2
    [0] type=planner uri=<redacted>
    [1] type=email uri=<redacted>
  digest: <digest>
confirm <digest>
outcome: unregistered
```

The delete is conditional: the marker is re-read and compared after lock acquisition and again immediately before the delete, and completion requires verified absence. A later registration of the same workspace is a fresh registration with a fresh identity.

## 5. The confirmation flow

`register`, `unregister`, `resolve-invalid`, and `recover-lock` share the same interactive shape: preview, digest, confirm, act — and nothing acts before exact confirmation.

**The preview.** Every interactive command prints a preview on stdout before asking for confirmation. The register preview, verified against the real CLI, looks like this:

```text
preview: register
  workspace: <workspace>
  marker path: <workspace>\.workstream\manifest.json
  label: Q3 planning
  kind: direct
  record_sources: 2
    [0] type=planner uri=<redacted>
    [1] type=email uri=<redacted>
  digest: <digest>
confirm <digest>
```

The label, local paths, kind, and record-source type tokens are shown; **record-source URI content is always `<redacted>`**. The unregister preview additionally shows the bound `identity`; the resolve-invalid preview shows the marker-component identity, byte length, SHA-256 digest, target handle, and lock status; the recover-lock preview shows the target handle and lock status.

**The digest.** The `digest` is an HMAC-SHA-256 digest of the canonical confirmation envelope under a key generated once per process (`secrets` random, 32 bytes):

- it is **in-memory and process-ephemeral** — the key and the digest are never persisted and never logged;
- it is **same-process only** — a digest printed by one invocation is never accepted by another (the key differs), so copying a digest from an earlier run always rejects;
- it is **single-use** — consumed by the write it authorizes; a new inspection, a second write attempt, a terminal transition, or a marker-state change expires an unused confirmation.

**Confirmation.** The operator confirms by typing the exact line `confirm <digest>` on stdin. This is the only input that permits a write or delete. Everything else is a clean cancel: any other input (digest mismatch or rejection) and end-of-file both perform no write and report `outcome: cancelled`, exit code 2. Note that a raw interrupt such as Ctrl+C aborts the process without writing (nothing is written before confirmation anyway) but exits with an interrupt traceback rather than the clean cancelled envelope — use a mismatched line or closed stdin for a clean cancel.

Two verified live behaviors worth internalizing:

```text
# copy the digest from run 1 into run 2 -> rejected, because the key is process-ephemeral
> workstream-registration register <workspace> --label "X" --record-source "t=https://x.example.invalid"
... digest: <run-1-digest> ...
confirm <run-1-digest>
outcome: cancelled
diagnostics: count=1 code=CONFIRMATION_REJECTED
```

```text
# unregister while another process holds the live lock -> stopped, no delete
> workstream-registration unregister <workspace>
... preview ... confirm <digest>
outcome: changed-marker-stopped
diagnostics: count=1 code=LOCK_UNAVAILABLE
```

## 6. Exit codes

Exit codes are derived from the result envelope outcome, so the `--json` outcome and the exit code never diverge (verified for every command above). CLI usage errors produce no envelope and exit 3.

| Exit code | Outcomes (and other meanings) | Meaning |
|---|---|---|
| 0 | `registered`, `linked-existing`, `unregistered`, `invalid-marker-resolved` | Success. |
| 2 | `cancelled`, `stopped` | No-write stop: operator cancelled (rejection/EOF/digest mismatch) or an operational condition (missing/inaccessible workspace, identity APIs unavailable, redirected marker components). |
| 3 | `occupied-invalid` | Invalid or inaccessible input: an invalid/partial/unsupported marker is present at the marker path. Also all CLI usage errors (no envelope). |
| 4 | `conflict`, `changed-marker-stopped` | Conflict: a captured target already holds a different identity, or cooperation could not be established / a changed marker, target, or identity was observed. No write or delete. |
| 5 | `written-unverified`, `registered-unlinked`, `invalid-deleted-unverified` | Partial success: the marker may exist (or be deleted) but the implementation could not verify it end-to-end. |
| 6 | — | Safe internal failure (no envelope). The CLI prints a fixed bounded message, never a raw traceback. |

## 7. Result envelope (`--json`)

Every result-vocabulary operation emits the same closed envelope (contract version 1), on one line, with the `--json` flag. Verified shape for a successful registration:

```json
{"version":1,"outcome":"registered","validity":"valid","effects":{"marker_written":true,"marker_deleted":false,"read_back_verified":true,"absence_verified":false,"linked":true,"projection":"linked"},"identity":"<uuid>"}
```

Fields:

| Field | Meaning |
|---|---|
| `version` | Result contract version; v1 = 1. Readers dispatch on it before applying the closed schema. |
| `outcome` | One of the 12 frozen outcome names. |
| `validity` | `valid`, `valid-with-warnings`, `invalid`, or `not-applicable`. Invalid markers never promote claimed values to authority. |
| `effects` | Structural write/read-back/link effects: `marker_written`, `marker_deleted`, `read_back_verified`, `absence_verified`, `linked` (booleans) and `projection` (`linked` / `unlinked` / `conflict` / `none`). This is what expresses partial success (e.g. `marker_written: true` with `read_back_verified: false` = `written-unverified`). |
| `identity` | Present only when verified: a valid-class marker whose read-back verified. Same shape as the marker identity. |
| `diagnostics` | Present only when there is something to report: `{count, items:[{phase, code, safe_path, ...}]}` with a closed set of stable codes (e.g. `SCHEMA_INVALID`, `WORKSPACE_INACCESSIBLE`, `CONFIRMATION_REJECTED`, `LOCK_UNAVAILABLE`, `MARKER_CHANGED`). Never carries native validator messages, instance values, URI content, or secrets. |

Verified examples of the two diagnostics-bearing envelopes:

```json
{"version":1,"outcome":"cancelled","validity":"not-applicable","effects":{"marker_written":false,"marker_deleted":false,"read_back_verified":false,"absence_verified":false,"linked":false,"projection":"none"},"diagnostics":{"count":1,"items":[{"phase":"operation","code":"CONFIRMATION_REJECTED","safe_path":".workstream/manifest.json"}]}}
```

```json
{"version":1,"outcome":"occupied-invalid","validity":"invalid","effects":{"marker_written":false,"marker_deleted":false,"read_back_verified":false,"absence_verified":false,"linked":false,"projection":"none"},"diagnostics":{"count":1,"items":[{"phase":"schema","code":"SCHEMA_INVALID","safe_path":".workstream/manifest.json"}]}}
```

Linking a valid marker reports the read-verified, projection-linked shape (identical for `inspect` on a registered workspace):

```json
{"version":1,"outcome":"linked-existing","validity":"valid","effects":{"marker_written":false,"marker_deleted":false,"read_back_verified":true,"absence_verified":false,"linked":true,"projection":"linked"},"identity":"<uuid>"}
```

**Diagnostics.** `diagnostics` is `{count, items: [...]}`; each item carries a `phase` (raw-guard phases `read`/`utf8`/`depth`/`duplicates`/`nonfinite`/`controls`, then `schema`, `write`, `read-back`, `link`, `projection`, `operation`), a stable `code`, and a bounded `safe_path` (the marker path, e.g. `.workstream/manifest.json`). Codes are a closed enum — the operator-relevant ones:

| Code | When you see it |
|---|---|
| `SCHEMA_INVALID` | The marker at the marker path fails schema validation (`occupied-invalid`). |
| `UNSUPPORTED_VERSION` | The marker's version is not 1; not interpreted as authority. |
| `WORKSPACE_INACCESSIBLE` | Workspace missing, inaccessible, or not a directory (`stopped`). |
| `IDENTITY_API_UNAVAILABLE` / `PATH_REDIRECTED` / `TARGET_ALIAS_MISMATCH` | Platform identity or marker-component failures; inspection fails closed. |
| `CONFIRMATION_REJECTED` | Cancel, EOF, or digest mismatch at a confirmation point. |
| `CONFIRMATION_EXPIRED` / `DRAFT_CHANGED` / `TARGET_CHANGED` | The single-use confirmation no longer matches the current state. |
| `LOCK_UNAVAILABLE` | Lock could not be acquired within the bound (`changed-marker-stopped` on unregister; no write on registration). |
| `MARKER_CHANGED` / `IDENTITY_MISMATCH` | Re-read showed a different marker or identity; operation stopped without write/delete. |
| `READ_BACK_FAILED` / `READ_BACK_TARGET_MISMATCH` | Read-back verification failed (`written-unverified`). |
| `PROJECTION_LINK_FAILED` / `PROJECTION_CONFLICT` | Projection link failure (`registered-unlinked`) or write-time conflict (`conflict`). |
| `ABSENCE_READ_BACK_FAILED` | Delete succeeded but absence could not be verified (`invalid-deleted-unverified`). |
| `SAFE_INTERNAL_ERROR` | Internal failure mapped to the safe exit-6 path. |

Diagnostics never carry native validator messages, instance values, property names, URI content, or secrets.

The two non-vocabulary commands have their own stable surfaces, also emitted with `--json`:

- `rebuild`: `{"status":"rebuilt","entries":[...],"detail":""}` (or `status: "failed"` with a bounded `detail` naming the failing root).
- `recover-lock`: `{"workspace":"<workspace>","lock_state":"absent"|"recovered"|"held"}`.

The envelope's `capabilities` field is part of the closed schema but is omitted when no capability claim is made — the CLI never emits it in this version, since no dereference is ever performed.

## 8. Scope boundaries

This version is **workstream registration only**, and the contracts claim nothing beyond it. Explicitly **not** functional in this version:

- **Machine scan of workspaces.** `register`, `link`, `rebuild`, `unregister`, `inspect`, `resolve-invalid`, and `recover-lock` operate on explicit operator-supplied paths only; this version never auto-discovers roots. The operator must know where each workspace lives, including any proxy workspace: v1 cannot recover locations it is never pointed at.
- **Registry consumption.** Registry publishing by Arjim is designed but deferred. Registries are read-only discovery aids: they point to metadata, never hold it.
- **Marker fields not in the v1 schema.** Purpose, lifecycle state, and a designated decision record source inside the marker are deferred; the closed schema has no such fields.
- **Workstream status, progress, next actions, and freshness.** This version registers and links; it does not answer "what needs me".
- **Cross-device root rediscovery and wipe-and-rebuild proof.** Designed later; not in this version.
- **Any second runtime.** Python 3.14.x is the only implementation; there is no runtime-selection abstraction or general implementation package.

Automatic duplicate detection and resolution are also out of scope: if the same workstream exists in two places, that is the operator's call, and v1's only duplicate signal is the projection write-time `conflict` outcome.

## 9. Troubleshooting

### `outcome: stopped` with `WORKSPACE_INACCESSIBLE` on `inspect` or `register`

The path is missing, inaccessible, or not a directory. Correct the path and re-inspect. Related stop codes fail closed in the same way: `PATH_REDIRECTED` for redirected marker components (a marker path component that resolves to a different identity than the captured target) and `IDENTITY_API_UNAVAILABLE` on hosts where the platform identity APIs cannot be used — in every case there is no draft, no confirmation, no write.

### `occupied-invalid` — malformed, partial, or unsupported marker

Inspection found something at the marker path that is not a valid v1 marker: a malformed document, an interrupted partial write, or an unsupported version. It is never overwritten and never silently replaced — registration on such a workspace reports `occupied-invalid` (exit 3). Resolution is the explicit, confirmed `resolve-invalid` command (section 3). If you prefer not to resolve, you can also inspect the file yourself, but the CLI will not touch it.

### Lock contention — `LOCK_UNAVAILABLE` / `changed-marker-stopped` / `held`

Every marker write and delete goes through a cooperative per-workspace lock (`.workstream/.registration.lock`, bounded JSON metadata `{owner_id, pid, target_handle, started_at, lease_until}`, 60-second lease). Rules that matter operationally:

- A lock is **stale** only when its lease has expired **and** its owner process is no longer alive. A live owner's lock is never broken.
- If registration or unregister cannot acquire the lock within the bounded timeout, the operation stops without writing or deleting: unregister reports `changed-marker-stopped` with `LOCK_UNAVAILABLE` (exit 4).
- If a previous process died while holding the lock, wait out the lease or run `recover-lock` (which requires the confirmed target-handle match) to replace it. Verified sequence: a stale lock previews as `lock_status: stale`, recovers to `lock: recovered` (exit 0); a fresh lock previews as `held` and stays `lock: held` (exit 4) even after confirmation.

### `changed-marker-stopped` semantics

During unregister (or resolution), cooperation could not be established, or a changed marker, target, or identity was observed at one of the re-reads. **No delete happened; the marker is untouched.** Recovery is always: fresh inspection → new draft → new confirmation. Do not attempt to work around it by hand-deleting; a changed marker between confirmation and delete is exactly the condition the two-phase re-check exists to catch.

### `written-unverified` / `registered-unlinked` — partial success

- `written-unverified` (exit 5): the marker write succeeded but read-back verification failed. The marker may exist and be valid, but the implementation cannot claim it — and the identity is never regenerated. Re-inspect: a valid marker degrades to linking, a partial/invalid one reports `occupied-invalid`, an absent one permits a fresh registration.
- `registered-unlinked` (exit 5): the marker is written and verified, but the local projection/link update failed. The marker remains authoritative. Run `link <workspace>` or `rebuild` to restore routing state; both reuse the identity and never edit the marker.

### Projection rebuild after loss

The projection is replaceable and never authoritative: deleting the projection database never unregisters anything. Rebuild from the markers with `rebuild <workspace>...`, passing each workspace explicitly. The rebuild is transactional: if any root is inaccessible or holds an invalid marker, the previous projection is left unchanged and the command exits 3 with a bounded error naming the failing root. One path means one workspace — no recursive traversal.

### `invalid-deleted-unverified` — resolution delete unverified

The resolution delete succeeded but absence read-back failed; the marker may or may not be absent and nothing is rewritten. Re-inspect: an absent marker is treated as resolved, a still-present marker needs a fresh `resolve-invalid`. There is no blind re-delete.

### `conflict` — duplicate workstreams

The projection reported a write-time conflict: the captured target already holds a different identity. The marker is unchanged and remains authoritative; the projection does not link it. v1 performs no automatic duplicate detection or resolution — the operator owns any multiple copies. Decide which copy is intended and use confirmed `unregister` on the other.

### Unregister reports `changed-marker-stopped` after the delete succeeded

If unregister's absence read-back fails after a successful conditional delete, the result reports `changed-marker-stopped` even though the marker was deleted. This lies within the disclosed non-cooperating-writer residual race (below): the frozen v1 vocabulary has no delete-succeeded-but-absence-unverified unregister outcome, and completion is defined only via verified absence. Re-inspect the workspace to see the actual state.

### Non-cooperating external writers (disclosed residual limitation)

The time-of-check/time-of-use race against **non-cooperating external writers** is a documented residual limitation, not a claimed atomic guarantee: registration's create-only write and unregister's conditional delete are safe against cooperating writers (the lock protocol), but an external writer that does not cooperate can race the check-then-act window. This is disclosed rather than hidden — if you manage marker files by hand alongside the CLI, you own that race.

### Exit code 6 — safe internal failure

Unexpected internal failures exit 6 with a fixed bounded message, never a raw traceback carrying instance content. Treat as a bug report; the workspace state is unchanged.

## 10. Support profile and conformance

**Pinned runtime:** CPython 3.14.6 with `jsonschema` 4.26.0; stdlib `sqlite3` (3.50.4 bundled) is required — a build without it fails the conformance runner explicitly (exit 2) and cannot run the projection. Install with `pip install -e .[dev]` from the repository root.

**Tested filesystem profile:** Windows NTFS — the conformance corpus, integration tests, and CLI lifecycle E2E run on NTFS. POSIX-compatible local filesystems are the declared target: the POSIX branches (owner-only enforcement via the standard library, liveness checks via `os.kill(pid, 0)`) are implemented fail-closed but **not tested on this host** — POSIX behavior is declared untested, not proven. No compliance claim is made for network or synchronized filesystems.

**Projection store location:** per-user application data — `%LOCALAPPDATA%\workstream-registration\projection` on Windows, `$XDG_DATA_HOME/workstream-registration/projection` (or `~/.local/share/workstream-registration/projection`) on POSIX. The `WORKSTREAM_REGISTRATION_STORE_DIR` environment variable relocates it. The store directory, database, and SQLite sidecars are owner-only enforced and verified before use and after creation.

**Conformance suite:** the implementation is proven against the contract corpus by

```text
python -m workstream_registration.conformance_runner
```

The runner loads the expectation manifest (87 fixtures: 18 valid, 18 invalid, 2 warn, 9 raw, 40 transition), executes every mandatory fixture exactly once, asserts the state-table and result-vocabulary invariants, and exits 0 only when all pass — verified: `conformance: PASS`, `failures: 0`. The full test suite runs with `pytest` from the repository root (362 tests). The authoritative contracts live under `contracts/workstream-registration/`; when the CLI and this guide conflict, the contracts win.
