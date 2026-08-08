# Workstream Registration — Operator Guide

This guide shows you how to do the day-to-day operations of workstream registration v1: register a workspace, link it, rebuild local routing state, retire a registration, resolve an invalid marker (the manifest file at `.workstream/manifest.json`), and recover a stale lock. It assumes you have the CLI installed ([installation](installation.md)) and have done one registration before ([quickstart](quickstart.md)); it does not re-teach either. Every command, output shape, and exit code below was verified against the installed CLI on the tested profile (Windows NTFS, CPython 3.14.6). Paths, target handles, digests, and identities are shown with placeholders where machine-specific; digest values are example output and differ on every invocation.

For the full command/flag/outcome details and the exit-code and result-envelope tables, see the [reference](reference.md). For what the marker is, why confirmation exists, and how the pieces work, see [how it works](how-it-works.md).

## Before you start

- The CLI is installed and on your PATH: `workstream-registration --help` prints the seven commands. If not, see [installation](installation.md).
- You have a workspace: an ordinary folder you want to become a registered workstream. Every command takes explicit workspace paths — v1 never scans for workspaces.

## Register a workspace for the first time

`register` is an interactive session: it inspects the workspace, shows a preview of the exact draft, and writes only after you type the exact confirmation line.

```text
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
```

1. Review the preview. Label, kind, and record-source *type* tokens are shown; record-source URI content is always `<redacted>`.
2. Type `confirm <digest>` — the exact line from the current preview — and press Enter. Nothing is written before this line.
3. A successful registration reports:

```text
outcome: registered
identity: <uuid>
```

Exit code 0. The marker now exists at `.workstream/manifest.json` inside the workspace, and the workspace is linked into the local projection. The `identity` is the workstream's permanent RFC 4122 v4 UUID — it is never regenerated.

**Clean cancel paths:** typing anything other than the exact `confirm <digest>` line, or closing stdin, performs no write and reports `outcome: cancelled`, exit code 2. A raw interrupt (Ctrl+C) also aborts before any write but exits with an interrupt traceback rather than the clean envelope — use a mismatched line or closed stdin for a clean cancel.

### The confirmation rules that matter day to day

- The digest is in-memory and process-ephemeral: it is generated for this invocation only, so a digest copied from an earlier run is always rejected. The `confirm` line must come from the preview currently on your screen.
- The confirmation is single-use and bound to the workspace's stable target handle, the observed marker absence, and the exact draft. If anything changes between preview and confirmation, the operation stops without writing and you start again from a fresh preview.
- Record-source URI content is never echoed by the CLI or diagnostics (the marker file itself does contain the URIs — see [how it works](how-it-works.md)).

## Re-establish routing state (day-to-day linking)

`register` again on a workspace that already holds a valid marker needs **no confirmation and writes nothing** — it degrades to linking. Use this after a projection wipe, after a device change, or just to re-establish routing state:

```text
> workstream-registration register <workspace> --label "Q3 planning" --record-source "planner=https://tasks.example.invalid/q3-planning"
outcome: linked-existing
identity: <uuid>
```

Exit code 0. The identity is the one already in the marker. `link <workspace>` does the same thing without the register flags — it reads a supported valid marker unchanged and links it.

## Rebuild local routing state after projection loss

The projection is replaceable, device-local state; deleting it never unregisters anything. Rebuild it from the markers:

```text
> workstream-registration rebuild <workspace-a> <workspace-b>
rebuild: rebuilt (2 entries)
```

Exit code 0. Pass each workspace explicitly — one path means one workspace, no recursive traversal. The rebuild is transactional: if any root is inaccessible or holds an invalid marker, the whole rebuild fails and the previous projection is unchanged:

```text
> workstream-registration rebuild <workspace-a> <broken-path>
rebuild: failed
error: rebuild root failed: <broken-path>: IdentityUnavailableError
```

(`rebuild: failed` goes to stdout; the `error:` line goes to stderr. Exit code 3.)

## Recover from `registered-unlinked`

The marker is authoritative and verified; only the local link failed. One command restores routing state — no confirmation, no write to the marker:

```text
> workstream-registration link <workspace>
outcome: linked-existing
identity: <uuid>
```

Exit code 0. `rebuild` also repairs this state.

## Retire a registration

`unregister` is a confirmed conditional delete: the preview is bound to the marker's exact identity, and the delete happens only after the exact confirmation line.

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

Exit code 0. The delete is conditional: the marker is re-read and compared after lock acquisition and again immediately before the delete, and completion requires verified absence. A later registration of the same workspace is a fresh registration with a fresh identity. If the marker changed under you at any comparison, the operation stops with `changed-marker-stopped` and nothing is deleted (see troubleshooting).

## Resolve an `occupied-invalid` marker

When inspection reports `occupied-invalid` — a malformed, partial (interrupted write), or unsupported-version marker — the CLI will never overwrite it. Resolution is the only path that removes it:

```text
> workstream-registration inspect <workspace>
state: occupied-invalid
outcome: occupied-invalid
diagnostics: count=1 code=SCHEMA_INVALID
```

```text
> workstream-registration resolve-invalid <workspace>
preview: resolve-invalid
  workspace: <workspace>
  marker path: <workspace>\.workstream\manifest.json
  state: occupied-invalid
  marker_identity: <none>
  marker_length: <bytes>
  marker_digest_sha256: <sha256>
  target_handle: <workspace-handle>:<parent-handle>
  lock_status: <absent|stale|held>
  digest: <digest>
confirm <digest>
outcome: invalid-marker-resolved
```

Exit code 0. The preview shows the marker's component identity (when extractable), bounded byte length, SHA-256 digest, the target handle, and the current lock status; the delete happens only after the active/stale lock checks and a confirmed target-handle match. On a workspace that is not `occupied-invalid`, the command errors on stderr and exits 3.

## Recover a stale lock

If a registration or unregister stopped because a lock could not be acquired, and the lock's owner process is dead (for example after a crash), recover it with a target-handle-bound confirmation:

```text
> workstream-registration recover-lock <workspace>
preview: recover-lock
  workspace: <workspace>
  target_handle: <workspace-handle>:<parent-handle>
  lock_status: stale
  digest: <digest>
confirm <digest>
lock: recovered
```

Exit code 0. The lock is replaced only when it is stale — lease expired **and** the owning process is no longer alive. A live owner's lock is never broken: it previews as `lock_status: held` and stays `lock: held` (exit 4) even after confirmation. On a workspace with no lock, confirmation reports `lock: absent` (exit 0).

## Troubleshooting

### `outcome: stopped` with `WORKSPACE_INACCESSIBLE` on `inspect` or `register`

The path is missing, inaccessible, or not a directory. Correct the path and re-inspect. Related stop codes fail closed the same way: `PATH_REDIRECTED` for redirected marker components and `IDENTITY_API_UNAVAILABLE` on hosts where the platform identity APIs cannot be used — in every case there is no draft, no confirmation, no write.

### `occupied-invalid` — malformed, partial, or unsupported marker

Something is at the marker path that is not a valid v1 marker. It is never overwritten and never silently replaced. Resolution is the explicit, confirmed `resolve-invalid` command above. If you prefer not to resolve, you can inspect the file yourself — the CLI will not touch it.

### Lock contention — `LOCK_UNAVAILABLE` / `changed-marker-stopped` / `held`

Every marker write and delete goes through a cooperative per-workspace lock (`.workstream/.registration.lock`, bounded JSON metadata, 60-second lease). Rules that matter operationally:

- A lock is **stale** only when its lease has expired **and** its owner process is no longer alive. A live owner's lock is never broken.
- If registration or unregister cannot acquire the lock within the bounded timeout, the operation stops without writing or deleting: unregister reports `changed-marker-stopped` with `LOCK_UNAVAILABLE` (exit 4).
- If a previous process died holding the lock, wait out the lease or run `recover-lock` (which requires the confirmed target-handle match) to replace it.

### `changed-marker-stopped` during unregister

Cooperation could not be established, or a changed marker, target, or identity was observed at one of the re-reads. **No delete happened; the marker is untouched.** Recovery is always: fresh inspection → new draft → new confirmation. Do not hand-delete as a workaround; a changed marker between confirmation and delete is exactly the condition the two-phase re-check exists to catch.

### `written-unverified` / `registered-unlinked` — partial success (exit 5)

- `written-unverified`: the marker write succeeded but read-back verification failed. The marker may exist and be valid, but the implementation cannot claim it — and the identity is never regenerated. Re-inspect: a valid marker degrades to linking, a partial/invalid one reports `occupied-invalid`, an absent one permits a fresh registration.
- `registered-unlinked`: the marker is written and verified, but the local projection/link update failed. The marker remains authoritative. Run `link <workspace>` or `rebuild` to restore routing state; both reuse the identity and never edit the marker.

### Projection rebuild after loss

The projection is replaceable and never authoritative: deleting the projection database never unregisters anything. Rebuild from the markers with `rebuild <workspace>...`, passing each workspace explicitly. The rebuild is transactional: if any root is inaccessible or holds an invalid marker, the previous projection is left unchanged and the command exits 3 with a bounded error naming the failing root.

### `invalid-deleted-unverified` — resolution delete unverified

The resolution delete succeeded but absence read-back failed; the marker may or may not be absent and nothing is rewritten. Re-inspect: an absent marker is treated as resolved, a still-present marker needs a fresh `resolve-invalid`. There is no blind re-delete.

### `conflict` — duplicate workstreams

The projection reported a write-time conflict: the captured target already holds a different identity. The marker is unchanged and remains authoritative; the projection does not link it. v1 performs no automatic duplicate detection or resolution — the operator owns any multiple copies. Decide which copy is intended and use confirmed `unregister` on the other.

### Exit code 6 — safe internal failure

Unexpected internal failures exit 6 with a fixed bounded message, never a raw traceback carrying instance content. Treat as a bug report; the workspace state is unchanged.

### Non-cooperating external writers (disclosed residual limitation)

Registration's create-only write and unregister's conditional delete are safe against *cooperating* writers (the lock protocol), but an external writer that does not cooperate can race the check-then-act window. This is disclosed rather than hidden — if you manage marker files by hand alongside the CLI, you own that race.

## Related material

- [Installation](installation.md) — prerequisites, venv vs global install, verify/uninstall.
- [Quickstart](quickstart.md) — first registration in about five minutes.
- [Reference](reference.md) — command reference, exit codes, result envelope, diagnostics codes, support profile and conformance.
- [How it works](how-it-works.md) — what the marker is, why confirmation exists, the lifecycle, the data flow, the outcome overview, scope boundaries.
