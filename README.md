# Arjim

My digital assistant for managing workstreams, surfacing what needs attention, and keeping authoritative records in their workspaces.

See [VISION.md](VISION.md) for the direction and outcomes.

Status: Planning. Not yet implemented.

## Workstream registration

The first planned capability is point-and-read workstream registration: an operator points a Python CLI at a workspace, confirms one exact draft, and a durable marker at `.workstream/workstream.json` becomes the registration record. The versioned contracts — marker schema, registration protocol, result vocabulary, and conformance fixtures — already exist; see [contracts/workstream-registration/README.md](contracts/workstream-registration/README.md).

One Python implementation (CPython 3.14.x with `jsonschema` 4.26.x) is planned. Scope is point-and-read only: machine scan of workspaces and registry consumption are designed but deferred and not functional in this version. Nothing is implemented yet; the status line above remains the current state until the full conformance corpus passes.
