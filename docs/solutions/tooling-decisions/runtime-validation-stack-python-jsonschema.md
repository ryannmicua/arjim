---
title: "Runtime and JSON Schema Validation Stack: CPython 3.14 + jsonschema 4.26"
date: 2026-08-02
category: tooling-decisions
module: workstream-registration
problem_type: tooling_decision
component: tooling
severity: medium
applies_when:
  - choosing a runtime for JSON Schema Draft 2020-12 validation
  - bounding raw JSON input before schema validation in an adapter
  - selecting a replaceable local store for device-local projection state
  - deciding whether to enable format assertion for untrusted URI data
tags:
  - jsonschema
  - draft-2020-12
  - runtime-selection
  - workstream-registration
  - python
  - tooling-decision
---

# Runtime and JSON Schema Validation Stack: CPython 3.14 + jsonschema 4.26

## Context

The workstream registration contract is runtime-neutral by design — the marker, result, fixture, and protocol surfaces are each independently versioned, and the schema dialect is JSON Schema Draft 2020-12 (see `docs/research/2026-08-01-workstream-registration-runtime-stack.md`, "Settled contract boundaries"). That neutrality left one open gap: the contract says *what* a compliant adapter must accept and reject but not *how* it is implemented. An implementation stack had to be chosen.

Choosing it surfaced a raw-JSON safety problem that no JSON Schema validator covers by itself. The research document's critical cross-runtime conclusion is that "schema validation begins after raw JSON concerns": JSON Schema validates an instance's data model and structure, but it does not preserve facts an ordinary parser discards — duplicate object member names collapse into a mapping, the exact original byte count is lost, and non-JSON constants such as `NaN` and `Infinity` can be silently accepted. Raw unescaped C0 controls are invalid JSON, but *escaped* control characters decode to legitimate string values (the JSON Schema spec explicitly notes NUL can appear in a JSON string), so controls and bidirectional overrides cannot be rejected by syntax parsing alone. The contract's fixed raw limits (256 KiB / 262,144-byte UTF-8, container depth 8, 256-byte label, 64-byte ASCII type token, 2,048-byte ASCII record-source URI, 32 record sources) plus its no-echo diagnostics rule therefore impose adapter-owned checks that sit in front of the validator.

## Guidance

Adopt **CPython 3.14.x + `jsonschema` 4.26.x, using `Draft202012Validator` explicitly**, as the initial implementation target. Per the research doc's recommendation, `jsonschema` documents full Draft 2020-12 support and exposes version-specific validators plus iterable, programmatically inspectable errors; the Python standard library covers the remaining adapter responsibilities. Pin exact patch versions at implementation start and require the pinned stack to pass the contract's portable conformance-fixture corpus (plus the official JSON Schema Test Suite and Bowtie) before it declares compatibility.

Non-negotiable adapter responsibilities (all grounded in the research doc's claims, not invented API details):

- **Bounded raw-input guard**, run before any schema validation:
  - Read at most 262,145 bytes so an allowed 262,144-byte input is distinguishable from an oversized one without reading an unbounded file.
  - Strict UTF-8 decode only — do not pass raw bytes straight to `json.loads`, because Python can recognize UTF-8, UTF-16, or UTF-32 byte input; decode strictly as UTF-8 first, then parse the text.
  - Token-aware depth scan rejecting depth above 8, counting only actual containers (braces/brackets inside strings must not count).
  - Duplicate-name rejection via the decoder's `object_pairs_hook`, which receives every object's ordered name/value pairs before they collapse into a dict.
  - Reject `NaN`, `Infinity`, and `-Infinity` via `parse_constant`.
  - Post-decode scan of decoded object names and string values for the contract's prohibited controls and `Bidi_Control` set (per the research doc, the Unicode `Bidi_Control` property is the strongest stable source).
- **Explicit `Draft202012Validator`** — never rely on an implicit latest-draft default.
- **Bundled schemas, blocked network `$ref`** — an untrusted marker must never cause HTTP, file, or other unintended resource access.
- **`format` assertion disabled** — Draft 2020-12 makes format assertion optional and disabled by default for the annotation vocabulary; do not enable generic URI `format` assertion as "hardening," and do not reject a URI for a credential-bearing authority component.
- **Normalized redacted diagnostics** — native validator messages/parameters can embed instance values, property names, URIs, labels, secrets, snippets, or local paths and must never be emitted. Map failures to a small versioned vocabulary (phase, stable code, bounded safe path, count) and cap diagnostic count and total serialized size.
- **Exclusive-create write + read-back** for registration: `open(path, 'x')`, write the complete bounded document, flush, `os.fsync`, close, reopen, re-run the raw guards and schema validation, verify exact identity, then report complete and update the projection.
- **Cooperative lock + re-check/delete/absence** for unregistration: no stdlib/portable primitive atomically deletes a path only if its bytes still match, so use lock, bounded read + exact identity compare, immediate re-read + re-compare, delete, absence read-back; document the residual race against non-cooperating writers.
- **`sqlite3` local projection** — replaceable, device-local, transactional; never authoritative. Note `sqlite3` is optional at CPython build time, so the compatibility declaration should require a build that includes it (or a separately tested snapshot alternative).

## Why This Matters

The raw-representation checks and JSON Schema validation are a correct separation, not a workaround for a weak validator. JSON Schema has no opinion about bytes, encoding, duplicate keys, non-finite extensions, or nesting depth beyond what a parser happened to preserve; the adapter owns those facts before any schema runs. Unknown-property rejection is likewise **schema semantics, not parser strictness**: closed objects must be expressed in the settled schemas with Draft 2020-12 keywords like `additionalProperties: false` (and `unevaluatedProperties: false` where composition requires it) — Ajv's "strict mode," for contrast, is schema hygiene and does not change validation results for otherwise valid schemas. Validator messages are unsafe to surface because the contract's no-echo rule means diagnostics must never carry instance values, labels, URIs, credential fragments, or local paths; only adapter-owned redaction can guarantee that. Finally, the stdlib covers the remaining adapter needs — exclusive-create file semantics, explicit sync, read-back, a transactional local database — with the smallest dependency and operational footprint of the three finalists (Python 91 / Java 88 / Node 83 on the research doc's weighted decision score).

## When to Apply

Apply this guidance when:

- Implementing the workstream registration reference adapter (the plan's adapter units U6–U11, which must not reopen the resolved stack).
- Declaring runtime compatibility — the pinned stack must pass the contract corpus plus the external Draft 2020-12 suites, and exact patch versions are recorded.
- Considering a future runtime port — the contract stays runtime-neutral, and the fixture corpus (raw-byte channel + parsed-value channel) is the portable boundary every adapter must pass.

Conditions that would justify **Java 25/networknt/Jackson** instead (from the research doc): Java/JVM packaging and support are organizational standards; the adapter must integrate into an existing JVM host; a tested embedded database dependency is already approved; native parser depth and duplicate constraints are preferred over a small adapter-owned pre-parser; or the team accepts the larger dependency and deployment footprint. Conditions that would justify **Node 24/Ajv** instead: TypeScript fit materially reduces delivery risk, a production-approved duplicate-aware tokenizer/parser is already available, a mature local persistence option is approved, and the team accepts Node 24's lifecycle and network-filesystem caveats.

## Examples

**Raw-input guard pipeline vs. relying on a validator alone.** Relying on `Draft202012Validator` alone would accept a 256 KiB file, silently keep the *last* duplicate key, parse `NaN`, mis-decode UTF-16 bytes, and never notice depth 40 — none of which are schema concerns. The guard instead runs `read(262145) → strict UTF-8 decode → token-aware depth scan (max 8) → object_pairs_hook duplicate rejection → parse_constant NaN/Infinity rejection → post-decode control/Bidi_Control scan → then Draft 2020-12 validation`. Depth-8 inputs reach normal validation; depth-9 inputs stop before schema validation.

**Safe diagnostic normalization vs. passing through native messages.** A native `jsonschema` `ValidationError` message may interpolate an instance value, unknown property name, or a credential-bearing URI — all forbidden by the no-echo rule. The adapter consumes only structural fields (validator identifier, safe path) and emits its own bounded codes (phase + stable code + count), never the native text.

**Create-only registration vs. silent overwrite.** Write with `open(final_path, 'x')` so the write fails if the path already exists — the atomic protection for the no-silent-replacement decision — then flush, `os.fsync`, close, reopen, re-run raw guards and schema validation, and verify exact identity before reporting success. An interrupted write leaves an occupied-invalid marker that later inspection reports as such and never overwrites. Unregistration uses the conditional-delete protocol: cooperative lock, read + exact identity compare, immediate re-read + re-compare, delete, absence read-back — because no stdlib call atomically means "delete only if current bytes equal this."

## Related

- Primary source: `../../research/2026-08-01-workstream-registration-runtime-stack.md` — the full technical assessment, candidate comparison, weighted decision score, and primary-source citations this guidance is grounded in.
- Implementation plan: `../../plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md` — resolves the runtime (KTD11) and owns the raw guard (KTD12), diagnostics (KTD13), and filesystem lifecycle (KTD14) as non-reopenable technical decisions.
