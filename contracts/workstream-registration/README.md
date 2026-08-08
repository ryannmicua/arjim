# Workstream Registration Contracts

Versioned contracts for the Arjim workstream registration and discovery feature: the durable workspace marker, the registration and unregister protocol, the portable result vocabulary, and the conformance corpus that proves the Python implementation honors them. These documents are the implementation boundary; the planning artifact that produced them is not part of an implementer's required reading.

## 1. What these contracts are

This directory holds the portable, versioned contracts for **point-and-read workstream registration**: an operator points the Python CLI at a workspace, confirms one exact draft, and a durable marker at `.workstream/manifest.json` becomes the registration record that survives any assistant, device, or local-state rebuild. Each contract surface is versioned independently (JSON Schema Draft 2020-12; marker version `1`); a reader dispatches on the version before applying the closed schema.

Executable behavior is not part of this directory. The Python implementation belongs under `src/workstream_registration/` and is not yet implemented (section 5). These contracts define what that implementation must honor.

## 2. Scope boundary: active vs deferred

### Active in this version

- The v1 marker schema and the marker path `.workstream/manifest.json` — the only v1 marker that makes a workspace a registration or discovery candidate.
- Registration and unregister authority: inspect, draft, exact-draft confirmation, create-only write, read-back, linking, confirmed conditional delete, retries, and partial success.
- Portable contracts: result vocabulary, warning and error taxonomy, schemas, protocol text, and conformance fixtures.
- One Python 3.14.x implementation with `jsonschema` 4.26.x: raw-input guard, bundled Draft 2020-12 validation, normalized bounded diagnostics, create-only write and read-back, confirmed conditional delete, replaceable SQLite projection, operator CLI, and conformance runner.

### Deferred — designed, but not functional in this version

- Machine scan of workspaces and registry consumption as working entry paths. `register`, `link`, `rebuild`, `unregister`, `inspect`, `resolve-invalid`, and `recover-lock` operate on explicit operator-supplied paths only; this version never auto-discovers roots.
- Registry publishing by Arjim. Registries are read-only discovery aids: they point to metadata, never hold it.
- Purpose, lifecycle state, and a designated decision record source inside the marker.
- Workstream status, progress, next actions, and freshness.
- Cross-device root rediscovery and wipe-and-rebuild proof.
- Any second runtime, runtime-selection abstraction, or general implementation package.

Nothing in these contracts claims that machine scan or registry consumption functions; the only planned working entry path is point-and-read.

## 3. Contract files

The files form the pipeline **fixture envelope → manifest → marker → protocol → results**; each is a closed, versioned surface. Paths are given from the repository root.

### `contracts/workstream-registration/v1/conformance-case.schema.json`

- **Purpose:** the fixture envelope. One case per fixture file, either `parsed-value` (the decoded JSON document in `payload`) or `raw-byte` (base64 raw bytes in `payload_base64`, never parsed as a JSON document).
- **Role in the pipeline:** wraps every corpus input so the runner can feed it to the raw guard and the validator uniformly.

### `contracts/workstream-registration/v1/expectations.schema.json`

- **Purpose:** the manifest contract. Every fixture has exactly one expectation entry: `id`, fixture path, category (`mandatory` | `capability` | `warning`), expected result, and requirement/acceptance-example coverage tags.
- **Role in the pipeline:** the single index of the corpus; the runner loads `tests/contracts/workstream-registration/expectations.json`, asserts every path exists and matches, and executes every case exactly once.

### `contracts/workstream-registration/v1/workstream.schema.json` — the marker

- **Purpose:** the marker contract — the durable, assistant-neutral self-description written at `.workstream/manifest.json` (2026-08-07 operator decision, digest 2026080702).
- **Role in the pipeline:** the registration authority. Closed fields: required integer `version` (v1 allowed value `1`), `identity` (RFC 4122 v4 lowercase UUID), required non-empty `label` (256-byte cap), required `kind` (`direct|proxy`), literal `.` workspace reference, and 1-32 typed `record_sources` (ASCII type token up to 64 characters, ASCII URI up to 2,048).

### `contracts/workstream-registration/v1/registration-protocol.md`

- **Purpose:** the state and authority protocol for registration, linking, unregister, invalid-marker resolution, and stop behavior, with a machine-readable state/transition table.
- **Role in the pipeline:** defines when each write may happen (only after exact confirmation), the stable target handle, the canonical confirmation envelope, cooperative lock rules, and terminal/recovery paths.

### `contracts/workstream-registration/v1/registration-result.schema.json`

- **Purpose:** the portable result envelope every operation emits (CLI `--json`), separating protocol outcome, marker validity, write/read-back/link effects, verified identity, per-record-source capability status, warnings, and bounded diagnostics.
- **Role in the pipeline:** the stable result vocabulary; its outcome names are frozen and every one is a state in the protocol's table.

### `contracts/workstream-registration/v1/compatibility.md`

- **Purpose:** the concrete Python and filesystem support profile — pinned dependencies, tested filesystem profile, owner-only enforcement, and residual limitations.
- **Role in the pipeline:** the support declaration; exact patches are recorded at implementation start and finalized at U11.

## 4. Fixture corpus

The conformance corpus lives under `tests/contracts/workstream-registration/`, indexed by `expectations.json` (87 entries today, all category `mandatory`):

- `valid/` (18) — valid markers: acceptance-example markers, field-boundary markers, canary-bearing markers, instruction-like labels that remain data.
- `invalid/` (18) — schema rejections: missing/unknown fields, malformed UUID, kind, or version, bad workspace references, duplicate record sources, field-limit violations.
- `warn/` (2) — valid-with-warnings markers (e.g., a malformed record-source URI).
- `raw/` (9) — raw-byte inputs for the raw guard: oversized input, malformed UTF-8, BOM prefix, trailing content, duplicate keys, depth 8/9, NaN/infinity, control characters.
- `transitions/` (40) — protocol and result cases: every result outcome plus transition scenarios carrying the `inputs` vocabulary (scenario, observed state, draft, bound identity, confirmation, lock, projection, twist).

## 5. Python package layout — implemented

The layout below is implemented and passes the complete project corpus on the tested profile (see `v1/compatibility.md`):

```text
src/workstream_registration/
  raw_guard.py
  validation.py
  diagnostics.py
  filesystem.py
  registration.py
  unregister.py
  projection.py
  cli.py
  conformance_runner.py
pyproject.toml
tests/python/
  test_raw_guard.py
  test_validation.py
  test_diagnostics.py
  test_filesystem.py
  test_registration.py
  test_unregister.py
  test_projection.py
  test_cli.py
  test_conformance_runner.py
```

Module responsibilities:

- `raw_guard.py` — bounded raw-input pipeline: read cap, strict UTF-8, token-aware depth scan, duplicate-key rejection, non-finite constant rejection, control and `Bidi_Control` scan.
- `validation.py` — bundled Draft 2020-12 validation with network `$ref` retrieval disabled.
- `diagnostics.py` — normalized bounded diagnostics; native validator messages are never emitted.
- `filesystem.py` — filesystem lifecycle: cooperative lock, exclusive-create marker write, flush/sync/close, read-back, interruption recovery.
- `registration.py` — inspect, draft, exact confirmation, create-only write, read-back, and link flow.
- `unregister.py` — confirmed conditional delete with absence read-back.
- `projection.py` — replaceable SQLite local routing projection.
- `cli.py` — operator surface: `register`, `inspect`, `link`, `rebuild`, `unregister`, `resolve-invalid`, `recover-lock`.
- `conformance_runner.py` — executes every fixture from the manifest exactly once.
- `tests/python/` — unit and integration tests per module.
- `pyproject.toml` — the pinned project scaffold (CPython 3.14.x, `jsonschema` 4.26.x).

## 6. Validation profile (Draft 2020-12)

- `Draft202012Validator` from `jsonschema` 4.26.x.
- Only bundled schemas and meta-schemas are loaded; `$ref` resolution outside the bundle fails closed — network `$ref` retrieval is disabled.
- Generic format assertion is disabled; format checks are not part of v1 validation.

## 7. Raw-input checks — before schema validation

The raw guard runs on the byte input before any JSON Schema validation:

1. Bound the read to 262,145 bytes — enough to distinguish an allowed 262,144-byte (256 KiB) marker from an oversized one.
2. Require strict UTF-8; alternate encodings and BOM prefixes are rejected.
3. Token-aware depth scan: container depth maximum 8; brackets inside strings are ignored.
4. Reject duplicate names (keys).
5. Reject `NaN` and infinities.
6. Scan decoded names and values for prohibited control characters and the Unicode `Bidi_Control` set.

## 8. No-dereference and no-echo rules

- Record-source URIs are untrusted data: the implementation never dereferences them, never inspects them for credentials, tokens, or other secrets, and diagnostics never echo them. Unsupported type/scheme pairs remain valid data with a non-dereferenceable capability status; malformed URIs warn without invalidating the marker.
- Diagnostics are bounded and normalized: phase, stable code, bounded safe path, count — never native validator messages, instance values, property names, URI content, secrets, or snippets.
- The operator-facing label and affected local paths may be emitted under length caps (label up to 256 characters, affected local path up to 1,024); the operator keeps secrets out of labels.
- The CLI preview shows the label, local paths, and structural fields; record-source URI content is redacted. Confirmation is a same-process `confirm <digest>` of an in-memory HMAC-SHA-256 digest under a process-ephemeral key; the key and digest are never persisted or logged, and a digest is never accepted across invocations.

## 9. Confirmed conditional unregister

Unregister is a confirmed conditional delete:

- The unregister draft binds to the marker's exact identity, the stable target handle, and the observed marker presence.
- The cooperative per-workspace lock must be established; if cooperation cannot be established, the operation stops without deleting (`changed-marker-stopped`).
- After lock acquisition the marker is re-read and compared with the confirmation, and again immediately before the delete (two-phase re-check).
- Delete proceeds only when both comparisons match; completion requires absence read-back (`unregistered`).
- Any changed marker, target, or identity stops the operation without deleting; recovery is a fresh inspection, a new draft, and a new confirmation.
- The time-of-check/time-of-use race against non-cooperating external writers is a disclosed residual limitation (compatibility.md), not a claimed atomic guarantee.

## 10. Objective checklist (Traceability gate)

A fresh implementer verifies each of the following; every listed repository path resolves in the working tree. The marker path is a workspace-relative location, and the runner invocation is a command, not a file.

1. **Every contract file exists — all 7 (this README + 6 in `v1/`):**
   - `contracts/workstream-registration/README.md`
   - `contracts/workstream-registration/v1/conformance-case.schema.json`
   - `contracts/workstream-registration/v1/expectations.schema.json`
   - `contracts/workstream-registration/v1/workstream.schema.json`
   - `contracts/workstream-registration/v1/registration-protocol.md`
   - `contracts/workstream-registration/v1/registration-result.schema.json`
   - `contracts/workstream-registration/v1/compatibility.md`
2. **Marker path:** `.workstream/manifest.json` — the durable marker location within a workspace; the only marker that makes a workspace a registration or discovery candidate.
3. **Runner invocation:** `python -m workstream_registration.conformance_runner`.
4. **Compliance bar:** the runner exits 0 with every mandatory fixture executed exactly once across all expectation categories (indexed by `tests/contracts/workstream-registration/expectations.json`), and the full `pytest` suite passes on the pinned runtime.
5. **Support profile:** CPython 3.14.x with `jsonschema` 4.26.x, stdlib `sqlite3` required, and the tested filesystem profile per `contracts/workstream-registration/v1/compatibility.md`.

Referenced corpus paths (all exist in the working tree):

- `tests/contracts/workstream-registration/expectations.json`
- `tests/contracts/workstream-registration/valid/`
- `tests/contracts/workstream-registration/invalid/`
- `tests/contracts/workstream-registration/warn/`
- `tests/contracts/workstream-registration/raw/`
- `tests/contracts/workstream-registration/transitions/`

## 11. Five factual questions — answerable from these contracts alone

1. (a) What is the identity field name in the marker? → **`identity`** (RFC 4122 v4 lowercase UUID; see `workstream.schema.json`).
2. (b) Where is the marker written? → **`.workstream/manifest.json`** within the workspace.
3. (c) How is the conformance runner invoked? → **`python -m workstream_registration.conformance_runner`**.
4. (d) What is the compliance bar? → **Runner exit 0 with every mandatory fixture executed exactly once across all expectation categories, plus a green `pytest` suite on the pinned runtime.**
5. (e) What is the support profile? → **CPython 3.14.x, `jsonschema` 4.26.x, stdlib `sqlite3` required, tested filesystem profile in `v1/compatibility.md`.**

