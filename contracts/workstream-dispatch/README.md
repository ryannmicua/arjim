# Workstream Dispatch Contracts

Versioned contracts for the Arjim workstream dispatch feature: the job record, the outcome note, the portable result vocabulary, the job-state and note-status vocabularies, and the conformance corpus that proves the Python implementation honors them. These documents are the implementation boundary; the planning artifact that produced them is not part of an implementer's required reading.

## 1. What these contracts are

This directory holds the portable, versioned contracts for **dispatch-based workstream work**: an operator asks Arjim to get something done in a registered workstream, Arjim translates that intent into a confirmed instruction, dispatches it through Paseo after operator confirmation, and later answers "how is everything going?" honestly for every dispatched job — including proposing the next step of a chain. Each contract surface is versioned independently (JSON Schema Draft 2020-12; record version `1`); a reader dispatches on the version before applying the closed schema.

Executable behavior is not part of this directory. The Python implementation belongs under `src/workstream_dispatch/` and is described in the implementation units. These contracts define what that implementation must honor.

## 2. Scope boundary: active vs deferred

### Active in this version

- The v1 job record schema at `.workstream/dispatch/<job-id>.json` — the durable, workspace-owned record of a dispatched job.
- The v1 outcome-note schema — the mutable note the dispatched agent writes beside its job record.
- The v1 dispatch-result envelope — the portable result vocabulary every dispatch and status operation emits.
- The job-state vocabulary (eight values) and derivation table (KTD5).
- The note-status vocabulary (seven values), orthogonal to job state.
- One Python 3.14.x implementation with `jsonschema` 4.26.x, `jsonschema` validation, bounded diagnostics, and a conformance runner.

### Deferred — designed, but not functional in this version

- Automated scheduling, cadence, or proactive delivery.
- Retry, recovery, or re-dispatch automation for failed or stalled jobs.
- Full awareness semantics (freshness windows, per-source trust vocabulary).
- Dispatch substrates other than Paseo.
- Reading the dispatched agent's work product, transcript, or diffs.

## 3. Contract files

### `contracts/workstream-dispatch/v1/job-record.schema.json`

- **Purpose:** the job record contract — the durable, workspace-owned record written at `.workstream/dispatch/<job-id>.json` inside the target workspace.
- **Role in the pipeline:** the registration of what was requested. Closed fields: `schema_version` (int), `job_id` (uuid4-shaped), `workstream_identity`, `instruction`, `dispatch_posture` (closed object with `provider` pinned to `opencode`, `model`, `mode`, `thinking`), optional `follows` (predecessor job id), `actor`, `recorded_at`, `confirmation_ref`, `created_at`. No `outcome_note_path` field — Arjim derives that path from `job_id` (R26, KTD11).

### `contracts/workstream-dispatch/v1/outcome-note.schema.json`

- **Purpose:** the outcome-note contract — the mutable note the dispatched agent writes beside its job record.
- **Role in the pipeline:** the agent's own record of what happened. Closed fields: `schema_version`, `job_id` (must match the record's), `summary` (bounded free-text), `reported_at` (ISO-8601 UTC). The note is one mutable snapshot per job, not a history.

### `contracts/workstream-dispatch/v1/dispatch-result.schema.json`

- **Purpose:** the portable result envelope every dispatch and status operation emits (CLI `--json`).
- **Role in the pipeline:** the stable result vocabulary; its outcome names are frozen: `dispatched`, `partial-success`, `cancelled`, `stopped`, `invalid-workspace`, `internal-failure`.

### `contracts/workstream-dispatch/v1/job-state.md`

- **Purpose:** the normative statement of the job-state vocabulary, the note-status vocabulary, and the KTD5 derivation table.
- **Role in the pipeline:** the single owner of the R8 mapping and the note-status orthogonality statement. Contains a fenced machine-readable table for the conformance runner.

## 4. Python package layout

```text
src/workstream_dispatch/
  __init__.py
  records.py
  store.py
  paseo_adapter.py
  git_adapter.py
  intent.py
  dispatch.py
  activity.py
  chain.py
  cli.py
  conformance_runner.py
tests/python/
  test_dispatch_records.py
  test_dispatch_store.py
  test_paseo_adapter.py
  test_git_adapter.py
  test_dispatch_intent.py
  test_dispatch.py
  test_dispatch_activity.py
  test_dispatch_chain.py
  test_dispatch_cli.py
  test_dispatch_conformance_runner.py
tests/contracts/workstream-dispatch/
  expectations.json
  valid/ invalid/ raw/ transitions/
```

## 5. Validation profile (Draft 2020-12)

- `Draft202012Validator` from `jsonschema` 4.26.x.
- Only bundled schemas and meta-schemas are loaded; `$ref` resolution outside the bundle fails closed — network `$ref` retrieval is disabled.
- Generic format assertion is disabled; format checks are not part of v1 validation.

## 6. Version-dispatch rule

A reader dispatches on `schema_version` before applying the closed schema, and an unsupported version is not interpreted. This applies identically to the job record, the outcome note, and the dispatch result.
