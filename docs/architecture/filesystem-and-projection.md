---
title: "Workstream Registration — Filesystem and Projection"
date: 2026-08-07
verified: 2026-08-07
---

# Filesystem and Projection

This page covers the two layers that make the lifecycle safe on disk: the filesystem primitives (stable target handle, cooperative lock, create-only write, conditional delete) and the replaceable SQLite projection. Everything here is owned by `src/workstream_registration/filesystem.py` and `src/workstream_registration/projection.py` (KTD13, PLAN:198; U10, PLAN:463). The behavior described is the **current design**; where a fix incident shaped it, this page links to the solution doc instead of re-telling the story.

## The stable target handle

Confirmation and every re-validation bind to a **stable target handle**, never a path string (PLAN:200): the packed `(device, file-index)` identity of the inspected workspace directory plus the identity of its `.workstream` parent, or the explicit `ABSENT` sentinel when the parent does not exist (`TargetHandle`, `src/workstream_registration/filesystem.py:206-218`; capture at `filesystem.py:255-292`; identity via `os.stat` `st_dev`/`st_ino` at `filesystem.py:157-185`). Rules:

- Symlink aliases are equivalent only when they resolve to the same captured identities (`filesystem.py:266-277`).
- A marker path that resolves outside the workspace (redirected marker component) is rejected (`filesystem.py:188-203`, `filesystem.py:278-281`).
- When identity APIs are unavailable, inspection fails closed — no draft, no confirmation, no write — and reports `stopped` (`filesystem.py:170-184`).

## The cooperative lock

The per-workspace lock file lives at `.workstream/.registration.lock` (`LOCK_FILENAME`, `src/workstream_registration/filesystem.py:89`) and is created with exclusive-create semantics carrying bounded JSON metadata `{owner_id, pid, target_handle, started_at, lease_until}` (`LockMetadata`, `filesystem.py:351-391`; creation `filesystem.py:422-440`; default lease 60 s, `filesystem.py:95`).

| Property | Design | Enforced at |
|---|---|---|
| **Atomic absent-parent step** | When `.workstream` is absent, lock acquisition and parent creation are one atomic step: create the parent without replacement, then exclusively create the lock within it. When the parent exists, the lock is acquired without creating or altering it (08-06 decision, PLAN:552). | `filesystem.py:471-514` (`os.mkdir` + exclusive lock create) |
| **Bounded acquisition** | Acquisition retries within a bounded timeout; an unobtainable lock stops with no write (`stopped` for registration, `changed-marker-stopped` for unregister). | `filesystem.py:517-553`; caller timeouts `registration.py:144`, `unregister.py:329-331` |
| **Release on normal and exceptional exit** | The lock is a context manager; release deletes the lock only when still owned by this `owner_id` — another owner's lock is never broken. | `filesystem.py:579-614`, `filesystem.py:556-576` |
| **Staleness = lease expired AND owner dead** | A lock is stale only when both hold. The liveness check **fails safe**: a failed check (access denied, unknown error) treats the owner as alive. A live owner's lock is never broken. | `filesystem.py:403-405` (`is_stale`), `filesystem.py:315-333` (`_pid_alive`), Windows branch `filesystem.py:336-348` |
| **Confirmed recovery** | A stale lock is replaced only by `recover-lock` after an in-process confirmation whose target handle matches both the lock metadata and the current workspace; malformed metadata or a live owner raises `LockNotRecoverableError`. | `filesystem.py:622-662`; CLI surface `cli.py:314-377` |

The two P1 fixes that hardened this area are recorded as solution docs, not re-narrated here: the liveness/ACL verification gap (`docs/solutions/logic-errors/owner-only-acl-verification-missed-inherited-aces.md`) and the projection race mapping (`docs/solutions/logic-errors/select-then-insert-race-maps-duplicate-target-conflict-to-integrity-error.md`).

## Create-only marker write and read-back

The final marker — the manifest file at `.workstream/manifest.json` — is written with exclusive-create semantics — `os.open(..., O_CREAT | O_EXCL | O_WRONLY)` — so an existing marker is never replaced; the complete bounded document is written, flushed, `os.fsync`-ed, and closed (`write_marker_create_only`, `src/workstream_registration/filesystem.py:665-695`; `MAX_MARKER_READ_BYTES = 262_145`, `filesystem.py:92`). An occupied path raises `CreateCollisionError` — never an overwrite.

After the write, the marker is reopened and read back bounded to the raw cap plus one byte (`read_marker`, `filesystem.py:698-710`), then the registration flow re-runs the raw guard and schema validation, verifies the exact identity (never regenerated), and verifies the read-back target handle matches the confirmed one (`_readback_and_project`, `registration.py:961-1002`). Outcomes:

- read-back verified + projection linked → `registered`;
- read-back verified, link failed → `registered-unlinked` (marker stays authoritative);
- read-back failed (including resolving from a different target) → `written-unverified`, identity never regenerated;
- exclusive-create collision: the existing marker is read — a valid supported marker degrades to `linked-existing` (read unchanged, no write), anything else is `occupied-invalid` and never overwritten (`_collision_result`, `registration.py:921-958`).

Only after read-back verification does the projection update (KTD13, PLAN:198). An interrupted partial marker is occupied and invalid; only an explicit operator-confirmed `resolve-invalid` may remove it (see [state-machine.md](state-machine.md)).

## Conditional delete and absence verification

Deletion happens only through the confirmed conditional-delete primitive: read the marker, compare the raw bytes to the confirmation-bound identity, and delete only on an exact match; a changed marker is left untouched (`conditional_delete_marker`, `src/workstream_registration/filesystem.py:729-748`). Absence is verified by read-back (`verify_marker_absent`, `filesystem.py:751-759`). Unregister applies two re-read comparisons (post-lock and immediately pre-delete) plus the conditional delete's own comparison, and completes only on verified absence; an unverifiable absence after a bounded retry stops fail-closed with `changed-marker-stopped` (`unregister.py:329-360`). The non-cooperating-writer race this cannot close is a disclosed residual limitation, not a claimed atomic guarantee (KTD10/PLAN:195; `contracts/workstream-registration/v1/compatibility.md:31-37`).

## The SQLite projection

The projection is replaceable, device-local routing state under a private owner-only directory in per-user application data (`default_store_dir`, `src/workstream_registration/projection.py:161-175`; overridable via `WORKSTREAM_REGISTRATION_STORE_DIR`, `projection.py:87`). It never becomes registration authority: deleting it never unregisters, and rebuild begins from the markers (`projection.py:1-8`; `CONCEPTS.md`).

### Schema

One table, created lazily and verified before every use (`Projection._connect`, `projection.py:366-397`):

```sql
CREATE TABLE IF NOT EXISTS projection (
  identity       TEXT NOT NULL,
  label          TEXT NOT NULL,
  marker_version TEXT NOT NULL,
  target_handle  BLOB NOT NULL,
  workspace_path TEXT NOT NULL,
  state          TEXT NOT NULL DEFAULT 'linked',
  ordinal        INTEGER NOT NULL,
  updated_at     TEXT NOT NULL,
  PRIMARY KEY (identity, target_handle)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_projection_target_handle
  ON projection (target_handle);
```

The schema carries marker identity, label, marker version, target handle, local routing path, state, and a deterministic input ordinal — and **no URI field at all**, so record-source content is never copied into local state (`projection.py:17-20`).

### Idempotency and conflict semantics

`Projection.update` (`projection.py:425-491`) upserts one row keyed by the idempotency key `(identity, target_handle)`:

- **Same key** → the local routing path and ordinal are replaced (idempotent relink/rebuild).
- **Different identity on one captured target** → `conflict` without changing the marker or any projection row — the only in-scope duplicate signal (PLAN:542). Detected by the SELECT-then-INSERT guard (`_ConflictOnTarget`, `projection.py:653-659`; `projection.py:437-443`) **and** by the `sqlite3.IntegrityError` branch that catches the INSERT racing the unique `target_handle` index across connections/processes (`projection.py:472-478`). That second branch is the current design; the incident that motivated it (the race degrading `conflict` to `projection-failed`) is recorded in `docs/solutions/logic-errors/select-then-insert-race-maps-duplicate-target-conflict-to-integrity-error.md`.
- **Store/enforcement failure** → `projection-failed`, never silent (`projection.py:479-485`).

The projection hook boundary (`registration.set_projection_hook` / `install_default_projection_hook`, `registration.py:342-367`) maps these statuses onto the outcome vocabulary in `registration._project` (`registration.py:761-829`): linked → `registered`/`linked-existing`; conflict → `conflict`; an unset or failing hook on a verified write → `registered-unlinked`.

### Owner-only enforcement

The store directory, the database file, and the SQLite sidecars (`-wal`, `-shm`, `-journal`) are enforced owner-only and verified **before use and after creation**; when the declared profile's enforcement cannot be established, or pre-existing permissions are weaker, the projection fails closed with `ProjectionStoreError` before use (`projection.py:110-115`, `projection.py:300-311`, `projection.py:344-421`):

- **Windows:** the built-in `icacls` tool — reset inheritance (`/inheritance:r`) and grant only the current user, then parse-verify the ACL (`_enforce_owner_only_windows`, `projection.py:199-224`; `_verify_owner_only_windows`, `projection.py:227-275`). Directory `(OI)(CI)` inheritance makes the sidecars inherit the owner-only ACL; sidecars are verified with `allow_inherited=True`, everything else strictly (`projection.py:356-364`).
- **POSIX:** `os.chmod` 0o700 (directory) / 0o600 (file) plus `os.stat` verification of owner and mode bits (`projection.py:278-297`).
- The strict-verification gap (inherited ACEs slipping past the ACE-regex parse) is history, not current behavior; the fix and its commit are recorded in `docs/solutions/logic-errors/owner-only-acl-verification-missed-inherited-aces.md`.

### Rebuild semantics

`Projection.rebuild` (`projection.py:526-603`) is a transactional replacement from an explicit ordered list of workspace paths: one path means one workspace (no recursive traversal), symlink aliases deduplicate by target handle while retaining the first input's ordinal, stale entries are repaired inside the same transaction, and **any inaccessible or invalid root returns a non-success leaving the previous projection unchanged** (rollback). Automatic discovery remains deferred (PLAN:463; PLAN:542).

## Related

- The recovery flows that use these primitives: [state-machine.md](state-machine.md)
- The no-echo guarantees that keep local state clean: [data-and-security.md](data-and-security.md)
- The verified behavioral walkthrough: `docs/usage/how-it-works.md:61-114`
- The support profile and tested filesystem: `contracts/workstream-registration/v1/compatibility.md`
