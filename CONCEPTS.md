# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Workstream

Anything Arjim manages as one unit — a project, recurring responsibility, operational process, shared initiative, or other ongoing work. A workstream exists as a durable registration only once it is registered and Arjim knows its workspace and authoritative record sources.

## Workstream Protocol

The assistant-neutral standard by which any agent recognizes a workstream and how its work is organized. It lives in `contracts/` — the marker schema, registration protocol, result vocabulary, and conformance schemas, backed by a conformance corpus under `tests/contracts/`. Arjim is one conforming implementation of the Workstream Protocol, not its owner; the standard is implementable by any assistant. The concrete v1 contract set is `contracts/workstream-registration/`, an implementation-boundary directory distinct from the standard's home in `contracts/`. The planned domains (projects, people, recurring responsibilities, operational processes) are future headroom, not current protocol scope.

## Workspace

Where a workstream keeps its lasting records — a folder plus the connected systems (Planner, SharePoint, email, repository) that hold its authoritative state. It tells Arjim where each authoritative record lives. The workspace is the durable source of truth; assistant working copies and device-local state never become authoritative.

## Regular workspace

The location where a workstream actually lives — the folder that holds its lasting records (or holds the workspace reference that identifies them). A regular workspace is the direct counterpart of a proxy workspace.

## Proxy workspace

A workspace that points to another workstream because that workstream cannot hold its own metadata. The marker records proxy kind and lives in the proxy; its record sources reference the real system or tool where the workstream's records are maintained.

## Marker

The durable, assistant-neutral document through which Arjim and other assistants discover and recognize a workstream. It is one closed JSON document containing the workstream's self-description: an Arjim-generated permanent identity, a mutable operator-facing label, the workspace reference, and its record sources. It is the manifest file at `.workstream/manifest.json`.

The marker is the registration authority. Registration writes it only after the operator confirms the exact draft, uses create-only semantics so it never silently replaces an existing marker, and completes only when read-back verifies the recorded workstream identity. Local inventory is a replaceable projection; the marker is not.

Marker terminology:

- **Marker** — the everyday short form of **workspace marker**. Use the full term on first mention or when it must stand on its own.
- **Marker file** — the physical JSON file at `.workstream/manifest.json`. Use this term when discussing filesystem behavior such as creation, locking, deletion, permissions, or read-back.
- **Marker path** — the fixed location `.workstream/manifest.json` within a workspace.
- **Marker contents** — the data recorded in the marker, including the workstream identity, operator-facing label, workspace relationship, and record sources.
- **Marker schema** — the versioned contract that defines the allowed structure and values of a marker.
- **Marker version** — the schema version that a reader uses to select the correct validation contract.
- **Workstream identity** — the permanent identifier recorded in the marker. It identifies the workstream across devices, assistants, workspace moves, and local projection rebuilds.
- **Marker presence** — whether a marker exists at the marker path. Presence makes the workspace a registration or discovery candidate but does not by itself establish a valid registration.
- **Marker validity** — whether the marker satisfies its raw-input limits and schema.
- **Supported marker** — a valid marker whose version the current reader understands. An unsupported version is not interpreted as registration authority by that reader.

## Record source

The authoritative location where a workstream's records are maintained — a typed URI reference to a system or tool such as Planner, SharePoint, or email (in the data-vault sense: the provenance of the workstream's truth). Record sources are accepted as untrusted data. Registration, generic marker parsing, and capability classification never dereference a record source, never inspect it for credentials or tokens, and diagnostics never echo them. The only component that may resolve a record source is a checking adapter (see Checking adapter) that explicitly supports its type and applies that type's validation, least-access, redaction, and data-retention rules. Validity is syntactic only; an unsupported scheme stays valid but non-dereferenceable.

## Checking adapter

The awareness capability that reads a supported record source: dispatch on the declared source type, validate the type-specific locator, enforce least access, and read only the signals the type declares. It is the only component allowed to dereference a record source, and it never echoes or persists raw URI content, credentials, or tokens. Checking adapters and their check semantics are versioned and listed in the awareness contracts (awareness plan R0).

## Point-and-read registration

The v1 entry path by which an operator registers a workstream: point Arjim at the workspace, inspect, draft, confirm, write, read back, and link. The term is internal plan vocabulary; it never reaches the operator-facing surface (which simply says register, link, rebuild, unregister).

## Local link projection

Replaceable, device-local routing state derived by reading markers, so an assistant can find registered workstreams without a remembered map of tools. It never becomes registration authority: deleting local routing state never unregisters a workstream, and a rebuild begins from the markers.

## Registration

The confirmed process that makes a workspace a registered workstream: inspect the workspace, draft the self-description, obtain the operator's exact confirmation, write the marker with create-only semantics, verify it by read-back, then derive the local link. Nothing is written before exact confirmation, and no existing marker is ever replaced.

## Unregistration

The confirmed process that retires a registration: draft an unregister intent bound to the exact workstream identity recorded in the marker, obtain confirmation, conditionally delete the marker only if it still matches, and complete only when read-back verifies absence. It is the durable way to resolve a duplicate registration or retire a workstream.

## Registration outcome

The closed result vocabulary that every registration, linking, and unregister operation reports, such as `registered`, `linked-existing`, `unregistered`, `occupied-invalid`, `invalid-marker-resolved`, and `changed-marker-stopped`. The outcome names and their meanings are frozen in the plan's result contract (U3) and map to CLI exit codes; contract edits must reference only names from this vocabulary. `occupied-invalid` covers every invalid marker present at the marker path — including an interrupted partial write — and is the inspection result for malformed markers; the vocabulary has no separate `invalid-marker` outcome.

## Configure

The required step that follows registration and makes a workstream checkable: the workspace's conventions are settled either by accepting Arjim's recommended defaults or by specifying the workspace's own. The first write is create-only, operator-confirmed, and read-back verified, mirroring registration; later changes follow a confirmed conditional update that re-reads and compares the file immediately before writing. A registered-but-unconfigured workstream surfaces as a gap item and is never silently checked under defaults.

## Conventions

The workspace-declared, schema'd, and versioned document that defines a workstream's awareness semantics: what counts as a "needs me" item (repo signals, a declared ledger, or other workspace-defined rules) and the freshness windows per record source. It records operator gap dispositions and, by reference, where the workspace declares the workstream's purpose and designated decision record source; Arjim never stores durable copies of workspace-declared information. Arjim may recommend defaults and scaffold them, but the workspace owns the conventions; an unsupported version is not interpreted, mirroring the marker rule.

## Relationships

- A **Workstream** is registered in a **Workspace** (a **Regular workspace** directly, or through a **Proxy workspace** when the workstream cannot hold its own metadata), which holds its **Marker**.
- A **Marker** references **Record sources**; the record sources, not the marker, point to where the workstream's lasting records live.
- The **Local link projection** is derived from **Markers** and never outranks them.

## Dispatch

The confirmed process that sends an operator-drafted instruction to a workspace agent. Dispatch follows strict ordering: write the job record create-only (U2), then spawn the agent (U4), then bind the job to the agent (U3). A record-write failure stops before spawning; a spawn failure after a successful write returns partial success naming the job. Dispatch requires operator confirmation via exact HMAC digest match (KTD8) before any write.

## Job record

The durable, schema-validated JSON document that records a dispatched instruction. Each job record lives at `.workstream/dispatch/<job-id>.json` inside the target workspace and carries the instruction, dispatch posture, confirmation reference, and creation timestamp. Job records use create-only write semantics (exclusive create) so an existing record is never silently replaced.

## Workspace agent

A background agent spawned by the Paseo adapter to execute a dispatched instruction within a workspace. The agent receives a fixed, content-free title (R23) and the instruction as a positional argument after `--` to prevent option injection (R30, KTD14). The agent's identity is bound to the job record via the dispatch store (U3).

## Job state

The derived current status of a dispatched job, computed through the KTD5 table as the single owner of state mapping. Job state combines the agent's lifecycle status (running, idle, closed, error), the presence of pending permissions, whether the agent is archived, and whether the Paseo daemon is reachable. The state vocabulary is: running, idle, needs-operator, not-found, unreachable, superseded, never-dispatched, failed.

## Chained dispatch

A dispatch whose instruction explicitly references a prior job via the `follows` field. The prior job's outcome note is read and its summary included in the context payload, giving the new agent the previous result. Chained dispatches preserve instruction ordering and confirmation semantics while enabling multi-step workflows.

## Flagged ambiguities

- "record source" and "workspace reference" were used interchangeably — they are distinct. The workspace reference is the literal `.` in the marker identifying the workspace itself; a record source is a URI to a separate authoritative system and is never a workspace reference.
- "drift" vs "ruling" — a rename or terminology change executed silently is drift (reconcile back to the settled value); the same change recorded as a dated operator decision before the edit is a ruling (accept and supersede the earlier clause).
