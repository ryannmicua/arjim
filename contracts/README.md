# Workstream Protocol

The assistant-neutral standard by which any assistant recognizes a workstream and how its work is organized. Any assistant can implement the Workstream Protocol against the contract surfaces in this directory; Arjim is one conforming implementation, not the standard's owner.

## What lives here

`contracts/` is the home of the Workstream Protocol's contract surfaces: the marker schema, the registration protocol, the result vocabulary, and the conformance schemas that index the conformance corpus (which itself lives under `tests/contracts/`). None of these surfaces are Arjim-internal — they are the assistant-neutral standard.

## Current v1 contract and implementation boundary

The current versioned contract set is [workstream-registration/](workstream-registration/README.md), starting at the [v1 marker schema](workstream-registration/v1/workstream.schema.json) and [registration protocol](workstream-registration/v1/registration-protocol.md). That directory remains the concrete v1 contract and implementation-boundary document: it states what the v1 implementation must honor, where the conformance corpus lives, and the tested support profile. This index does not replace it.

## Scope

- The Workstream Protocol is workstream-specific for now. Projects, people, recurring responsibilities, and operational processes are future headroom, not active protocol kinds.
- This index claims no executable behavior and describes no repository split; `contracts/` documents the standard, it does not run anything.
- There is no generalized protocol family yet. The standard generalizes beyond workstreams only when a real second domain appears.
