# Quickstart: Workstream Registration

Workstream registration is the v1 entry path of Arjim's workstream management: you point the Python CLI at a workspace, confirm one exact draft, and a durable marker at `.workstream/manifest.json` becomes the registration record that survives any assistant, device, or local-state rebuild. This guide takes you through a first registration in about five minutes.

## Prerequisites

- CPython 3.14.x (`3.14.6` is the pinned, tested runtime; the package requires `>=3.14,<3.15`).
- Install from the repository root:

  ```text
  pip install -e .[dev]
  ```

  This installs the `workstream-registration` console script and pytest. The runtime dependency `jsonschema` is pinned (`==4.26.0`); stdlib `sqlite3` is required for the local projection.

- The `workstream-registration` command must be on your `PATH` (it is installed into your Python `Scripts` directory).

## 1. Create a scratch workspace

A workspace is an ordinary folder. Create one to practice on:

```text
mkdir docs-demo
echo "# Docs demo" > docs-demo\README.md
```

Check the CLI is installed before continuing:

```text
> workstream-registration --help

workstream-registration - workstream registration (v1)
usage: workstream-registration [--json] <command> [args]
commands:
  register <workspace> --label <label> --record-source <type>=<uri>... [--kind direct|proxy]
  inspect <workspace>
  link <workspace>
  rebuild <workspace>...
  unregister <workspace>
  resolve-invalid <workspace>
  recover-lock <workspace>
```

## 2. Register the workspace

`register` is an interactive session. It inspects the workspace, shows you a preview of the exact draft it would write, and asks you to confirm by typing `confirm <digest>`. Type the line exactly as printed — the digest is generated in memory for this invocation only, so the `confirm` line must come from the current preview, not from an earlier run.

```text
> workstream-registration register docs-demo --label "Docs demo" --record-source "planner=https://tasks.example.invalid/docs-demo"

preview: register
  workspace: docs-demo
  marker path: docs-demo\.workstream\manifest.json
  label: Docs demo
  kind: direct
  record_sources: 1
    [0] type=planner uri=<redacted>
  digest: 2f9c6e1b7a04d5f38c21b9a0e6d4471c8b3f5e9d2a0c6b8d4e1f3a5c7d9b0a2e4
confirm 2f9c6e1b7a04d5f38c21b9a0e6d4471c8b3f5e9d2a0c6b8d4e1f3a5c7d9b0a2e4
```

Notes on the preview:

- `label` and `kind` are shown; record-source URI content is always shown as `<redacted>`.
- The digest, the `confirm` line, and the `identity` below are **example output** — every invocation produces different values.

Type the confirmation:

```text
confirm 2f9c6e1b7a04d5f38c21b9a0e6d4471c8b3f5e9d2a0c6b8d4e1f3a5c7d9b0a2e4
outcome: registered
identity: 615518c7-5331-4af7-a896-6cf4767d767f
```

`outcome: registered` with exit code 0 means the marker was written, read back, validated, and linked into the local projection. The `identity` is the workstream's permanent RFC 4122 v4 UUID — keep it, it identifies the workstream across devices and rebuilds.

The clean cancel paths are typing anything other than the exact `confirm <digest>` line, or closing stdin: no write happens, `outcome: cancelled`, exit code 2. (An interrupt such as Ctrl+C aborts the process before any write — nothing is written before confirmation — but it exits with a raw interrupt traceback rather than the clean `cancelled` envelope.)

## 3. Verify the marker file

Registration is complete only after read-back verification. The marker itself is a single compact JSON document at `.workstream/manifest.json`:

```text
> type docs-demo\.workstream\manifest.json

{"version":1,"identity":"615518c7-5331-4af7-a896-6cf4767d767f","label":"Docs demo","kind":"direct","workspace":".","record_sources":[{"type":"planner","uri":"https://tasks.example.invalid/docs-demo"}]}
```

(On POSIX shells use `cat docs-demo/.workstream/manifest.json`.)

The fields are frozen by the v1 marker contract: `version` (1), `identity` (RFC 4122 v4 UUID), `label`, `kind` (`direct` or `proxy`), the literal workspace reference `.`, and 1–32 typed `record_sources`. The `identity` above matches the one printed at registration.

## 4. Inspect and re-run

`inspect` is read-only. On a registered workspace it reports the linked registration:

```text
> workstream-registration inspect docs-demo

state: linked-existing
target_handle: <workspace-handle>:<parent-handle>
outcome: linked-existing
identity: 615518c7-5331-4af7-a896-6cf4767d767f
```

The `target_handle` is a platform filesystem identity (device/index pair), shown here with placeholders — its value is machine-specific. Exit code 0.

Running `register` again on the same workspace needs no confirmation and performs no write — it degrades to linking and reports `linked-existing` with the same identity. The identity is never regenerated.

### What if I cancel, or get the digest wrong?

Nothing is written before confirmation, so a mistake is cheap:

- Type anything other than the exact `confirm <digest>` line, or close stdin: `outcome: cancelled`, exit code 2, no file is created.
- Copy the digest from an earlier run into a new invocation: it is rejected, because the digest is keyed to the process that printed it. This is deliberate — the digest is in-memory and single-use, never accepted across invocations.
- Interrupt with Ctrl+C: the process aborts before any write (nothing is written before confirmation anyway), but exits with a raw interrupt traceback rather than the clean `cancelled` envelope.

After any cancel, re-run `register` — it starts fresh from a new inspection and prints a new preview with a new digest.

## 5. Unregister

`unregister` is also an interactive, confirmation-gated session. It previews the marker it would delete — bound to the exact identity — and requires the same in-process `confirm <digest>`:

```text
> workstream-registration unregister docs-demo

preview: unregister
  workspace: docs-demo
  marker path: docs-demo\.workstream\manifest.json
  identity: 615518c7-5331-4af7-a896-6cf4767d767f
  label: Docs demo
  kind: direct
  record_sources: 1
    [0] type=planner uri=<redacted>
  digest: 7d1e2f9a3b8c4d5e6f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6b
confirm 7d1e2f9a3b8c4d5e6f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6b
```

After confirmation, the marker is conditionally deleted (it is re-read and compared before and immediately before the delete) and absence is verified:

```text
confirm 7d1e2f9a3b8c4d5e6f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6b
outcome: unregistered
```

Exit code 0. A later registration of the same workspace is a fresh registration with a fresh identity.

## What's next

- Read the [operator guide](guide.md) for the full command reference, the outcome and exit-code vocabulary, `--json` result envelopes, lock recovery, invalid-marker resolution, and troubleshooting.
- Verify the implementation against the contract corpus at any time:

  ```text
  python -m workstream_registration.conformance_runner
  ```

  The runner executes every conformance fixture (87: valid, invalid, warn, raw, and transition cases) exactly once and exits 0 only when all mandatory fixtures pass. The full test suite runs with `pytest` from the repository root (362 tests).
- Want the machine-readable form? Add `--json` to any command — registration, linking, and unregister operations emit the stable result envelope described in the guide's result-envelope section.
