# Workstream Registration — Reference

Reference material for the `workstream-registration` CLI v1: every command with its flags and outcomes, the exit-code table, the `--json` result envelope with its fields and diagnostics codes, the two non-vocabulary command surfaces, and the support profile and conformance suite. All output shapes, exit codes, and diagnostic `safe_path` values in this page were verified against the installed CLI on the tested profile (Windows NTFS, CPython 3.14.6). Paths, target handles, digests, and identities are shown with placeholders where machine-specific; digest values are example output and differ on every invocation.

For how to *use* these commands to achieve goals, see the [operator guide](guide.md). For what the pieces are and why, see [how it works](how-it-works.md). For a first registration in about five minutes, see the [quickstart](quickstart.md). To install the CLI, see [installation](installation.md).

## Command reference

All commands accept `--json` before or after the command name to emit the stable result envelope instead of the human summary (see [Result envelope](#result-envelope---json-)). `register`, `unregister`, `resolve-invalid`, and `recover-lock` are single-process interactive sessions; `inspect`, `link`, and `rebuild` are not.

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

## Exit codes

Exit codes are derived from the result envelope outcome, so the `--json` outcome and the exit code never diverge (verified for every command above). CLI usage errors produce no envelope and exit 3.

| Exit code | Outcomes (and other meanings) | Meaning |
|---|---|---|
| 0 | `registered`, `linked-existing`, `unregistered`, `invalid-marker-resolved` | Success. |
| 2 | `cancelled`, `stopped` | No-write stop: operator cancelled (rejection/EOF/digest mismatch) or an operational condition (missing/inaccessible workspace, identity APIs unavailable, redirected marker components). |
| 3 | `occupied-invalid` | Invalid or inaccessible input: an invalid/partial/unsupported marker is present at the marker path. Also all CLI usage errors (no envelope). |
| 4 | `conflict`, `changed-marker-stopped` | Conflict: a captured target already holds a different identity, or cooperation could not be established / a changed marker, target, or identity was observed. No write or delete. |
| 5 | `written-unverified`, `registered-unlinked`, `invalid-deleted-unverified` | Partial success: the marker may exist (or be deleted) but the implementation could not verify it end-to-end. |
| 6 | — | Safe internal failure (no envelope). The CLI prints a fixed bounded message, never a raw traceback. |

## Result envelope (`--json`)

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
| `capabilities` | Present in the closed schema, omitted by the CLI: reserved for per-record-source capability claims, keyed by 0-based index into the marker's `record_sources`. The CLI never emits it in this version, since no dereference is ever performed. |

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

**Diagnostics.** `diagnostics` is `{count, items: [...]}`; each item carries a `phase` (raw-guard phases `read`/`utf8`/`depth`/`duplicates`/`nonfinite`/`controls`, then `schema`, `write`, `read-back`, `link`, `projection`, `operation`), a stable `code`, and a bounded `safe_path` — always the fixed marker path `.workstream/manifest.json`. Codes are a closed enum — the operator-relevant ones:

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

## Support profile and conformance

**Pinned runtime:** CPython 3.14.6 with `jsonschema` 4.26.0; stdlib `sqlite3` (3.50.4 bundled) is required — a build without it fails the conformance runner explicitly (exit 2) and cannot run the projection. Install with `pip install -e .[dev]` from the repository root — see [installation](installation.md).

**Tested filesystem profile:** Windows NTFS — the conformance corpus, integration tests, and CLI lifecycle E2E run on NTFS. POSIX-compatible local filesystems are the declared target: the POSIX branches (owner-only enforcement via the standard library, liveness checks via `os.kill(pid, 0)`) are implemented fail-closed but **not tested on this host** — POSIX behavior is declared untested, not proven. No compliance claim is made for network or synchronized filesystems.

**Projection store location:** per-user application data — `%LOCALAPPDATA%\workstream-registration\projection` on Windows, `$XDG_DATA_HOME/workstream-registration/projection` (or `~/.local/share/workstream-registration/projection`) on POSIX. The `WORKSTREAM_REGISTRATION_STORE_DIR` environment variable relocates it. The store directory, database, and SQLite sidecars are owner-only enforced and verified before use and after creation.

**Conformance suite:** the implementation is proven against the contract corpus by

```text
python -m workstream_registration.conformance_runner
```

The runner loads the expectation manifest (87 fixtures: 18 valid, 18 invalid, 2 warn, 9 raw, 40 transition), executes every mandatory fixture exactly once, asserts the state-table and result-vocabulary invariants, and exits 0 only when all pass — verified: `conformance: PASS`, `failures: 0`. The full test suite runs with `pytest` from the repository root (362 tests). The authoritative contracts live under `contracts/workstream-registration/`; when the CLI and this page conflict, the contracts win.
