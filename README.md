# Arjim

My digital assistant for managing workstreams, surfacing what needs attention, and keeping authoritative records in their workspaces.

See [VISION.md](VISION.md) for the direction and outcomes.

Status: implemented — point-and-read workstream registration (v1) is working on the tested profile.

## Workstream registration

The first capability is point-and-read workstream registration: an operator points the Python CLI at a workspace, confirms one exact draft, and a durable marker at `.workstream/workstream.json` becomes the registration record that survives any assistant, device, or local-state rebuild. The versioned contracts — marker schema, registration protocol, result vocabulary, and conformance fixtures — live under [contracts/workstream-registration/](contracts/workstream-registration/README.md), and the full conformance corpus passes on the pinned runtime.

The Python implementation (CPython 3.14.6 with `jsonschema` 4.26.0; see [compatibility.md](contracts/workstream-registration/v1/compatibility.md) for the exact tested profile) provides:

- **CLI**: `register`, `inspect`, `link`, `rebuild`, `unregister`, `resolve-invalid`, `recover-lock` — destructive commands are single-process interactive sessions that preview the draft (label and local paths shown; record-source URI content redacted) and confirm an in-memory HMAC digest; cancellation, EOF, or a digest mismatch performs no write.
- **Lifecycle**: raw-input guard, bundled Draft 2020-12 validation, bounded diagnostics, create-only write with read-back and exact-identity verification, confirmed conditional unregister with absence read-back, and a replaceable SQLite local projection.
- **Conformance**: `python -m workstream_registration.conformance_runner` executes every fixture from the expectation manifest exactly once and exits 0 only when all mandatory fixtures pass, including the state-table assertion, the requirement-coverage report, the grep blacklist, the canary no-echo scan, and the lifecycle and rebuild-after-projection-loss end-to-end runs.

Scope is point-and-read only: machine scan of workspaces and registry consumption are designed but deferred and not functional in this version; every command operates on explicit operator-supplied paths only.
