---
title: "Workstream Registration — System Architecture and Design Documentation Set"
date: 2026-08-07
verified: 2026-08-07
---

# Workstream Registration — Architecture Documentation Set

This set documents the shipped workstream-registration feature: how the system works and why it is designed this way, so a reader understands it **without going through the codebase**. Every architectural claim carries a code citation (`src/...` file:line) and/or a plan citation (`PLAN:NNN`), so the docs can be re-verified against the tree mechanically.

The set describes the **current design**. Design history — incidents, root causes, fixes, and decision narratives — lives in `docs/solutions/` (see [Relationship to other documentation](#relationship-to-other-documentation)); this set states the current design and links to history, it never re-narrates it.

The subject of the set is the **marker** — the manifest file at `.workstream/manifest.json` — the durable self-description that registration writes and every flow reads or deletes. The terminology pairing convention is defined in [Relationship to other documentation](#relationship-to-other-documentation).

## What this set covers

| File | Covers |
|---|---|
| [`system-overview.md`](system-overview.md) | One page: what the system is, the layered architecture, the end-to-end register flow, and the five core invariants. Start here. |
| [`design-decisions.md`](design-decisions.md) | The KTD1-13 design decisions distilled (decision, rationale, where enforced, status incl. supersessions), the frozen result vocabulary, the confirmation-digest design, and the disclosed residual limitations. |
| [`state-machine.md`](state-machine.md) | The 17 protocol states, the unregister flow, the recovery paths, and how states map to the 12 outcomes and CLI exit codes. |
| [`data-and-security.md`](data-and-security.md) | The marker schema, record sources as untrusted data, the raw-input guard phases, the no-echo guarantees, the canary tripwire, and confirmation-digest semantics. |
| [`filesystem-and-projection.md`](filesystem-and-projection.md) | The cooperative lock, create-only marker writes, conditional delete, and the replaceable SQLite projection. |

## Reading order

1. **Overview** (`system-overview.md`) — what the system is and its shape.
2. **Design decisions** (`design-decisions.md`) — why it is shaped that way.
3. **State machine** (`state-machine.md`) — how the lifecycle behaves in every branch.
4. **Data and security** (`data-and-security.md`) — how untrusted input is bounded and what may never be emitted.
5. **Filesystem and projection** (`filesystem-and-projection.md`) — the primitives that make the lifecycle safe.

## Authority hierarchy

When documents disagree, this ordering decides; the lower document is wrong, not the higher one:

1. **`contracts/`** — the frozen, versioned contract surfaces (marker schema, result schema, registration protocol, compatibility declaration). Written by the plan, frozen at their units; the implementation must honor them.
2. **`docs/plans/`** — the design authority. `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md` carries the KTD1-13 decisions and R1-R15 requirements; contracts translate them into frozen surfaces.
3. **`src/`** — the executable interpretation. The code may implement only what the contracts and plan allow.
4. **`docs/` (this set and other documentation)** — descriptive. This set is verified against the tree, but describing something does not make it authoritative.

The same precedence is already stated for the usage docs (`docs/usage/how-it-works.md`): *"The contracts are the authority; when this page and a contract disagree, the contract wins."*

**When you find a genuine conflict** (contracts vs plan vs code disagree on an architectural claim): record it as a row in the [Conflict log](#conflict-log-maintenance-tasks) below and in the affected file's maintenance notes — do not silently pick a side in the documentation.

## Relationship to other documentation

| Area | Role | Boundary with this set |
|---|---|---|
| `docs/architecture/` (this set) | **Current design** — what the system is and why it is this way now. | Describes the present tree; cites but never re-narrates history. |
| `docs/solutions/` | **Problem history** — incidents, root causes, fixes, prevention. | Where a topic exists in both, this set states the current design and links to the solution doc for the story (e.g. the projection conflict mapping, the ACL-verification regex fix, the runtime-stack selection). |
| `contracts/workstream-registration/` | **Frozen authority** — the versioned contract surfaces. | This set distills and cross-references the contracts; the contracts are the tie-breaker (see authority hierarchy). |
| `docs/plans/` | **Design origin** — the KTD decisions, requirements, and dated operator decisions that produced the contracts. | This set cites `PLAN:NNN` for rationale; the plan records the full decision narrative and supersession history. |
| `docs/usage/` | **Operator-facing documentation** — install, quickstart, guide, how-it-works, reference. | `docs/usage/how-it-works.md` is the verified behavioral explanation; this set is the architecture-level counterpart and links to it. |
| `CONCEPTS.md` | **Vocabulary authority** — the shared domain terms. | This set uses its terms exactly: the concept is the **marker** — the manifest file at `.workstream/manifest.json` (2026-08-07 operator decision, digest `docs/session-digests/2026080702_marker_path_rename_manifest_json.md`). |

**Terminology pairing convention:** the concept is the **marker** and the filename is `manifest.json` at the marker path `.workstream/manifest.json` — they are not interchangeable. Every first mention of the marker in a document pairs the two explicitly (for example: *"the marker — the manifest file at `.workstream/manifest.json`"*); subsequent mentions may use "marker" alone. This set follows the convention in all six files.

## Maintenance rules

Which file to touch when the system evolves:

| Change | Touch | Also check |
|---|---|---|
| **(a) A dated operator decision changes a design value** (a path, a cap, a rule, a vocabulary term). | `design-decisions.md` — update the affected KTD's status line. | Record the supersession **first**, per the governance convention in `docs/solutions/conventions/recorded-rename-ruling-vs-unrecorded-drift.md`: write a dated decision digest before editing, name what is superseded, leave historical records historical, then rewrite the superseded clause in place citing the digest. Any affected file here gets a maintenance note linking the digest. |
| **(b) The state machine changes** (states, transitions, terminal/recovery paths). | `state-machine.md` — the state table, diagram, and recovery sections. | `system-overview.md` (invariants if authority rules change), `README.md` (index). The protocol's §13 machine-readable table (`contracts/workstream-registration/v1/registration-protocol.md`) is authoritative — change it first. |
| **(c) The schema changes** (marker fields, caps, version dispatch, result envelope). | `data-and-security.md` — the closed-field table, caps, and version-dispatch section. | `design-decisions.md` (KTD3 surface versioning, KTD9 bounds), `contracts/workstream-registration/v1/workstream.schema.json` (frozen surface — a new surface version, not an edit, unless the plan permits). |
| **(d) New CLI commands land** (or commands change their surface). | `system-overview.md` (layer description), `README.md` (index if scope changes). | `state-machine.md` if the command maps to new outcomes/exit codes; `contracts/workstream-registration/v1/registration-protocol.md` if a new outcome or state enters the vocabulary (the 12-outcome vocabulary is frozen — PLAN:391/556). |

**Last-verified convention:** every file's frontmatter carries `verified: YYYY-MM-DD`. When you re-verify a file's citations and anchors against the tree (e.g. after any of the changes above), update that date. A `verified` date older than the last tree change means the file needs re-verification.

**Validator note (adjudicated):** `validate-doc-claims.py` flags workspace-relative paths such as `.workstream/manifest.json` and `.workstream/.registration.lock` as "not found in the working tree" because it resolves citations against the repository, and these paths live inside a workspace, not the repo. That flag is a false positive for this set: the paths are frozen by contract (CONCEPTS.md; protocol §2) and are cited intentionally. All other flags (SHAs, repo paths, links) must resolve.

## Conflict log (maintenance tasks)

Rows are added when a genuine conflict between contracts, plan, or code is found while maintaining this set. Each row names the conflict, the date, and the resolution task.

| Date | Conflict | Resolution task |
|---|---|---|
| — | (none recorded) | — |
