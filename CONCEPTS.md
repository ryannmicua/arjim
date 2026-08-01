# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Workstream

Anything Arjim manages as one unit — a project, recurring responsibility, operational process, shared initiative, or other ongoing work. A workstream exists as a durable registration only once it is registered and Arjim knows its workspace and authoritative record homes.

## Workspace

Where a workstream keeps its lasting records — a folder plus the connected systems (Planner, SharePoint, email, repository) that hold its authoritative state. It tells Arjim where each authoritative record lives. The workspace is the durable source of truth; assistant working copies and device-local state never become authoritative.

## Marker

The durable, assistant-neutral registration record a registered workstream holds in its workspace. It is one closed JSON document containing the workstream's self-description: an Arjim-generated permanent identity, a mutable operator-facing label, the workspace reference, and its record homes.

The marker is the registration authority. Registration writes it only after the operator confirms the exact draft, uses create-only semantics so it never silently replaces an existing marker, and completes only when read-back verifies its identity. Local inventory is a replaceable projection; the marker is not.

## Record home

A typed URI reference to the authoritative location of a workstream's lasting records (a system or tool such as Planner, SharePoint, or email). Record homes are accepted as untrusted data: adapters never dereference them, never inspect them for credentials or tokens, and diagnostics never echo them. Validity is syntactic only; an unsupported scheme stays valid but non-dereferenceable.

## Local link projection

Replaceable, device-local routing state derived by reading workspace markers, so an assistant can find registered workstreams without a remembered map of tools. It never becomes registration authority: deleting local routing state never unregisters a workstream, and a rebuild begins from the markers.

## Registration

The confirmed process that makes a workspace a registered workstream: inspect the workspace, draft the self-description, obtain the operator's exact confirmation, write the marker with create-only semantics, verify it by read-back, then derive the local link. Nothing is written before exact confirmation, and no existing marker is ever replaced.

## Unregistration

The confirmed process that retires a registration: draft an unregister intent bound to the marker's exact identity, obtain confirmation, conditionally delete the marker only if it still matches, and complete only when read-back verifies absence. It is the durable way to resolve a duplicate registration or retire a workstream.

## Relationships

- A **Workstream** is registered in a **Workspace**, which holds its **Marker**.
- A **Marker** references **Record homes**; the record homes, not the marker, point to where the workstream's lasting records live.
- The **Local link projection** is derived from **Markers** and never outranks them.

## Flagged ambiguities

- "record home" and "workspace reference" were used interchangeably — they are distinct. The workspace reference is the literal `.` in the marker identifying the workspace itself; a record home is a URI to a separate authoritative system and is never a workspace reference.
