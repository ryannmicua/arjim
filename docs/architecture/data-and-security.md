---
title: "Workstream Registration — Data and Security"
date: 2026-08-07
verified: 2026-08-07
---

# Data and Security

This page covers everything the system reads, bounds, and refuses to emit: the marker schema, record sources as untrusted data, the raw-input guard phases, the no-echo structural guarantees, the canary tripwire, and the confirmation-digest semantics. The security posture in one line: **every input is bounded before it is parsed, every failure is bounded before it is reported, and record-source URI content is structurally incapable of appearing in any output.**

## The marker schema

The **marker** — the manifest file at the marker path `.workstream/manifest.json` — is one closed JSON document (KTD2, PLAN:187; `src/workstream_registration/filesystem.py:147`). The contract is `contracts/workstream-registration/v1/workstream.schema.json`; readers dispatch on the required `version` field **before** applying the closed schema (KTD3, PLAN:188; `src/workstream_registration/validation.py:157-178`, `validation.py:206`).

| Field | Constraint (v1) | Notes |
|---|---|---|
| `version` | JSON integer, `const: 1` | Version dispatch key; any other value → `UNSUPPORTED_VERSION`, never authority (`validation.py:157-178`). |
| `identity` | RFC 4122 v4 UUID, lowercase | Arjim-generated permanent identity; never regenerated (R14, PLAN:118). |
| `label` | Required, non-empty, ≤ 256 bytes | Operator-facing name; a label is data, not an instruction. |
| `kind` | `direct` \| `proxy` | `direct` = regular workspace; `proxy` = proxy workspace holding the marker for a workstream whose real location cannot store assistant metadata. |
| `workspace` | Literal `.` | Durable/device-local separation: device paths and traversal are invalid (KTD4, PLAN:189). |
| `record_sources` | Array of 1-32 unique typed URI references | Each entry: `type` (ASCII, ≤ 64 chars) + `uri` (ASCII, ≤ 2,048 chars; RFC 3986 ASCII means the character limit is also the byte budget). |

Raw-byte bounds are guard obligations, not schema keywords: 256 KiB (262,144 bytes), nesting depth 8, no duplicate keys, no non-finite constants, no controls or bidi overrides (KTD11, PLAN:196). The label/type/URI caps are enforced by the schema (`workstream.schema.json:21-27, 63-76`).

## Record sources as untrusted data

Record sources are typed absolute URIs accepted as untrusted data (KTD5, PLAN:190):

- **Never dereferenced.** Any syntactically well-formed URI is accepted regardless of scheme or credential-bearing content; format assertion is disabled by construction — the validator is built without a `format_checker`, and no code ever fetches a URI (`src/workstream_registration/validation.py:145-154`). Unsupported type/scheme pairs remain valid data with a non-dereferenceable capability status.
- **Never inspected for secrets.** The 08-01 operator decision removed URI secret-scanning as an obligation: the operator decides what the marker may contain (PLAN:538).
- **Never echoed.** URI content is redacted in every preview (`src/workstream_registration/cli.py:166-171`), absent from diagnostics (below), and absent from the projection schema — the SQLite schema has **no URI field at all**, so record-source content is never copied into local state (`src/workstream_registration/projection.py:17-20`).
- **Malformed URIs warn without invalidating the marker** (AE9, PLAN:134); validity is syntactic only.

## The raw-input guard phases

The guard runs on raw bytes **before** any JSON materialization, in a strictly ordered pipeline (`src/workstream_registration/raw_guard.py:264-280`; KTD11, PLAN:196). The guard terminates; it never "fixes":

| Phase | Check | Rejects | Cap / rule |
|---|---|---|---|
| `read` | Bounded read | Inputs over 262,144 bytes (the read cap is 262,145 so an allowed marker is distinguishable from an oversized one) | `raw_guard.py:61`, `filesystem.py:91-92` |
| `utf8` | Strict UTF-8 | BOM signatures (UTF-8/16/32) and malformed sequences; alternate encodings | `raw_guard.py:136-146`, `raw_guard.py:276-279` |
| `depth` | Token-aware depth scan | Nesting above 8; brackets inside strings never count | `raw_guard.py:149-172` (`MAX_DEPTH`, `raw_guard.py:62`) |
| `duplicates` | Duplicate-name rejection | Repeated names at root and nested (duplicate-preserving hook) | `raw_guard.py:186-201` |
| `nonfinite` | Constant rejection | `NaN`, `Infinity`, `-Infinity` outside strings | `raw_guard.py:191-203` |
| `controls` | Controls + bidi scan | C0 (U+0000-U+001F), C1 (U+007F-U+009F), and the `Bidi_Control` set (U+200E/F, U+202A-U+202E, U+2066-U+2069) in names and values, root and nested | `raw_guard.py:89-103`, `raw_guard.py:209-242` |
| `schema` | Clean pass | — | Continues to version dispatch + Draft 2020-12 (`validation.py:206`) |

```mermaid
flowchart LR
    raw["raw marker bytes<br/>(bounded read: MAX_READ_BYTES)"] --> g1
    subgraph guard["raw_guard.guard (raw_guard.py:264)"]
        g1["1. read<br/>size <= 262,144 bytes"] --> g2["2. utf8<br/>no BOM, strict UTF-8"]
        g2 --> g3["3. depth<br/>nesting <= 8"]
        g3 --> g4["4. duplicates<br/>no repeated names"]
        g4 --> g5["5. nonfinite<br/>no NaN / Infinity"]
        g5 --> g6["6. controls<br/>no C0/C1/Bidi_Control"]
        g6 --> g7["7. clean pass → schema phase"]
    end
    g7 --> parse["json.loads (registration.py:492)"]
    parse --> dispatch{"version dispatch<br/>(validation.py:69)"}
    dispatch -->|"version == 1"| schema["validate_marker<br/>Draft 2020-12, bundled schema<br/>(validation.py:206)"]
    dispatch -->|"any other version"| unsup["UNSUPPORTED_VERSION<br/>not authority"]
    schema -->|valid| marker["marker is registration authority<br/>state: linked-existing"]
    schema -->|invalid| occ["occupied-invalid<br/>never overwritten"]
    g1 -->|reject| fail1["diagnostics: phase=read, code=READ_LIMIT"]
    g2 -->|reject| fail2["diagnostics: phase=utf8, code=UTF8_INVALID"]
    g3 -->|reject| fail3["diagnostics: phase=depth, code=DEPTH_LIMIT"]
    g4 -->|reject| fail4["diagnostics: phase=duplicates, code=DUPLICATE_KEYS"]
    g5 -->|reject| fail5["diagnostics: phase=nonfinite, code=NON_FINITE"]
    g6 -->|reject| fail6["diagnostics: phase=controls, code=CONTROL_CHARACTER"]
    fail1 & fail2 & fail3 & fail4 & fail5 & fail6 --> diag["diagnostics.single / from_guard_result<br/>(diagnostics.py:329, 336)"]
    schema -->|invalid| diag2["diagnostics.normalize<br/>code=SCHEMA_INVALID<br/>(diagnostics.py:306)"]
    diag & diag2 --> out["result envelope / outcome vocabulary<br/>safe_path always .workstream/manifest.json<br/>(diagnostics.py:77)"]
```

(Verified; identical to `docs/usage/how-it-works.md:120-146`.) Guard rejection codes map onto the closed diagnostic vocabulary via `GUARD_CODE_MAP` (`src/workstream_registration/diagnostics.py:169-177`), so a diagnostic's `phase` identifies exactly which guard check failed.

## No-echo structural guarantees

Diagnostics are bounded and normalized (KTD12, PLAN:197) — and the no-echo rule is **structural**, not contractual:

- The normalizer reads only `error.validator` (for the stable code) and `error.path` (for stable ordering and count truncation) from jsonschema errors. It never reads `message`, `instance`, `validator_value`, or `schema`, so native messages, instance values, property names, URI content, secrets, and snippets are impossible in the output (`src/workstream_registration/diagnostics.py:306-326`).
- Diagnostics carry only: a closed-enum `phase`, a closed-enum `code`, and the fixed bounded `safe_path` `.workstream/manifest.json` (`diagnostics.py:77`); optional bounded `label` (≤ 256) and `affected_local_path` (≤ 1,024) fields exist under caps but the normalizer never sets them (`diagnostics.py:185-209`).
- Every bound is enforced at serialization: count ≤ 32, per-field caps, and a derived 64 KiB serialized-size cap that paginates items (with `count` adjusted, never mid-field) so the emitted document always satisfies the result-schema shape (`diagnostics.py:80-84`, `diagnostics.py:252-274`).
- The result envelope itself carries no URI field; `identity` is a fixed 36-char lowercase-UUID pattern, structurally incapable of carrying URI content (`contracts/workstream-registration/v1/registration-result.schema.json:51-56`).

## The canary tripwire

The conformance corpus embeds canary values in fixtures — token-like and user-info-bearing values such as `fake-token-1` and `fake-token-2` declared per-fixture in `tests/contracts/workstream-registration/expectations.json` (`expectations.json:160-246`). The conformance runner collects every canary and scans all captured output — runner output, diagnostic items, and CLI subprocess output — and fails the run on any hit (`canary_values`, `src/workstream_registration/conformance_runner.py:947`; `canary_scan`, `conformance_runner.py:956-960`; tripwire at `conformance_runner.py:1320-1331`). This makes the no-echo guarantee machine-checked: if any code path ever leaked URI content, a fixture canary would trip the run.

**Secret-shaped on purpose.** The canary values are deliberately credential-shaped — token-like prefixes such as `ghp_...` (`canary-fake-token-2.json`), private-key headers and `AKIA...`-shaped access keys (`canary-key-shaped-1.json`), `sk_`-shaped strings (`canary-key-shaped-2.json`), and userinfo-bearing URIs such as `https://svc-account:fake-secret-token-9Xz2@...` (`canary-userinfo-uri-1.json`) — but they are fake by construction (declared per-fixture in `expectations.json:160-246`) and exist only to trip the no-echo scan. The shapes are the point: a canary that did not look like a real credential would test less of the guarantee. Repos running secret scanners (GitHub secret scanning, gitleaks/pre-commit scanners) should allowlist or dismiss these fixture paths rather than flag them — the values are intentional tripwire payload, not real secrets.

The canary discipline extends to the normalizer's own design: labels *may* be emitted under caps (08-04 operator decision, PLAN:546), so the normalizer simply never emits them — the guarantee stays structural even for content an operator might deliberately embed in a label (`src/workstream_registration/diagnostics.py:35-39`).

## Confirmation-digest semantics

The confirmation digest is the operator's authority boundary (KTD6, PLAN:191) — see [design-decisions.md](design-decisions.md) for the design and [system-overview.md](system-overview.md) for the flow. Its three deliberate properties:

1. **In-memory only.** The HMAC-SHA-256 key is generated once per process with `secrets.token_bytes(32)`; the key and digest are never persisted or logged (`src/workstream_registration/registration.py:173-182`). There is no digest artifact to replay.
2. **Same-process only.** Because the key differs per invocation, a digest from an earlier run is always rejected — the `confirm <digest>` line must come from the preview currently on screen (`cli.py:380-397`). This is why cross-invocation confirmation is impossible by construction.
3. **Single-use.** The confirmation is consumed by the write it authorizes; a new inspection, a second write attempt, a terminal transition, or a marker-state change expires an unused confirmation (`registration.py:864-890`). Unregister and resolve-invalid bind to the same mechanism with the same consumption rule (`unregister.py:299-327`, `registration.py:1103-1123`).

## Related

- The bounded-pipeline details in the verified usage doc: `docs/usage/how-it-works.md:116-152`
- The schema contract: `contracts/workstream-registration/v1/workstream.schema.json`; the result envelope contract: `contracts/workstream-registration/v1/registration-result.schema.json`
- The lock and projection mechanisms that keep local state replaceable and private: [filesystem-and-projection.md](filesystem-and-projection.md)
