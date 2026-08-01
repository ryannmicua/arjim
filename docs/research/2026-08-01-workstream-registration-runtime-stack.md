# Technical Assessment: Runtime and JSON Schema Draft 2020-12 Validation Stack

**Research date:** 2026-08-01
**Scope:** Web research and decision support only. No repository was accessed and no implementation code was produced.
**Decision status:** Recommendation for a later implementation decision; not a standards certification.
**Source policy:** Primary sources were preferred: specifications, official runtime/library documentation, project repositories, release records, conformance tooling, and security advisories.

## Executive decision

Select this as the default implementation stack:

> **CPython 3.14.x + `jsonschema` 4.26.x, using `Draft202012Validator`, with an adapter-owned bounded raw-input guard and Python's `sqlite3` module for the replaceable local link projection.**

Pin exact patch versions when implementation begins and require the pinned stack to pass the contract's portable conformance-fixture corpus before it declares compatibility.

### Why this stack is the best fit

1. `jsonschema` explicitly documents full JSON Schema Draft 2020-12 support and exposes version-specific validation plus iterable, programmatically inspectable errors.[S6][S7]
2. Python's standard JSON decoder exposes the hooks needed to detect duplicate object names before they collapse into a mapping and to reject non-JSON constants such as `NaN` and `Infinity`.[S8]
3. Python provides direct exclusive-create file semantics, explicit file synchronization, reliable read-back primitives, and a mature transactional local database in the standard library.[S9][S10][S11]
4. The stack has the smallest operational and dependency footprint of the three finalists while still meeting the adapter's later filesystem and local-persistence needs.
5. Its main gap - no native JSON nesting-depth limit in the standard decoder - is bounded and explicit. The contract already requires a pre-parse layer, so depth can be enforced in the same raw-input guard that handles byte size, strict UTF-8, duplicate names, and Unicode safety.

### Runner-up

**Java 25 LTS + networknt `json-schema-validator` 3.x + Jackson 3.1.x** is the strongest alternative where JVM deployment is already standard or native parser constraints are valued more highly than footprint. Jackson offers strict duplicate detection and nesting constraints, and Java has excellent create-only and file-forcing primitives. It is heavier, requires an additional persistence choice, and its dependency chain needs tighter version management.

### TypeScript/Node position

**Node.js 24 LTS + Ajv 8.20.x** is fully viable when TypeScript ecosystem fit is the overriding organizational constraint. Ajv has explicit Draft 2020-12 support. It ranks third here because JavaScript's standard JSON parse result has already lost duplicate-name information, so a separate raw tokenizer/parser is mandatory; Node's built-in SQLite module is also still a release candidate as of the research date.[S14][S18][S21][S22]

## Settled contract boundaries

This assessment does not reopen any of the following decisions:

- The contract remains runtime-neutral.
- Marker, result, fixture, and protocol surfaces are independently versioned.
- JSON Schema Draft 2020-12 is the declared schema dialect.
- A runtime must declare compatibility with the validation profile and pass the portable fixture corpus before claiming compliance.
- The marker remains one closed JSON document at `.workstream/workstream.json` within a workspace folder.
- The fixed raw-input limits remain: 64 KiB UTF-8, maximum JSON container depth 8, 256-character label, 64-character ASCII type token, 2,048-character URI, and at most 32 record homes.
- Registration remains inspect, Arjim-drafted self-description, exact operator confirmation, create-only write, read-back verification, then replaceable local link projection.
- Unregistration remains an exact-identity-bound confirmed conditional delete, complete only after read-back verifies absence.
- Record-home URIs remain untrusted, are never dereferenced, and may contain credentials.
- Diagnostics must not echo URIs, labels, secrets, or local device paths.
- The marker's workspace reference remains the literal `.`.

## Research method and confidence scale

Candidates were assessed against:

1. Verified Draft 2020-12 support and maintenance status.
2. Raw-input safety fit: duplicate names, exact byte cap, strict UTF-8, nesting depth, controls, and bidirectional controls.
3. Closed-object enforcement and structured diagnostics.
4. Create-only write, read-back, conditional-delete workflow, and interruption recovery.
5. Replaceable local projection persistence.
6. Operational footprint and likely maintenance burden.

Confidence labels used throughout:

- **High:** Directly supported by a current primary source, with no material inference.
- **Medium:** Supported by primary sources but includes implementation judgment, a portability caveat, or a version-publication uncertainty.
- **Low:** Not verified from a primary source. Such a claim should not be used as a decision basis.

## Maintenance and release snapshot

Observed on 2026-08-01:

| Stack | Current evidence | Maturity judgment | Confidence |
|---|---|---|---|
| Python 3.14.x + `jsonschema` 4.26.x | Python 3.14 has a published maintenance schedule; `jsonschema` documentation is at 4.26.0 and the project lists 4.26.0 as its latest release.[S6][S12][S13] | Strong production candidate: mature runtime, mature major library line, active release activity | High |
| Node.js 24.x + Ajv 8.20.x | Node 24 is Active LTS; Ajv 8.20.0 was released in April 2026 and explicitly added/supports the Node 22/24 lines.[S17][S18] | Strong production candidate, subject to a separate raw parser and persistence choice | High |
| Java 25 + networknt 3.x + Jackson 3.1.x | Java 25 is LTS; networknt's current README/POM identify 3.0.6, Java 17+, and Jackson 3.1.4; Jackson 3.1 is an LTS branch.[S23][S24][S27][S28] | Strong production candidate, with an artifact-publication check before exact pinning | Medium-High |

## Critical cross-runtime conclusions

### 1. Schema validation begins after raw JSON concerns

JSON Schema validates an instance's data model and structure. It does not preserve facts that an ordinary parser may discard, such as duplicate object member names, and it does not define an exact byte-length ceiling for the original representation.[S1]

Therefore, every compliant adapter needs the same logical validation pipeline:

1. Bound the raw read to 65,537 bytes so the adapter can distinguish an allowed 65,536-byte input from an oversized one without reading an unbounded file.
2. Require strict UTF-8 decoding; do not permit silent replacement of malformed sequences or automatic acceptance of UTF-16/UTF-32.
3. Count object and array container depth with a token-aware scanner and reject depth above 8. Braces and brackets inside strings must not affect the count.
4. Detect duplicate object member names before they are collapsed into a runtime map/object.
5. Reject syntax extensions such as `NaN` and positive or negative infinity.
6. Scan decoded object names and string values for the contract's forbidden controls and bidirectional-control set.
7. Validate the parsed value with the exact Draft 2020-12 schema version.
8. Normalize all failures into bounded, contract-owned diagnostic codes.

This is not a workaround for a weak validator. It is the correct separation between raw-representation checks and JSON Schema instance validation.

### 2. Unknown properties are schema semantics, not parser strictness

Closed-object behavior must be expressed by the settled schemas with Draft 2020-12 keywords such as `additionalProperties: false` and, where composition requires it, `unevaluatedProperties: false`.

Ajv's "strict mode" is useful for rejecting ambiguous or silently ignored schema constructs, but Ajv explicitly states that strict mode does not change validation results for otherwise valid schemas.[S15] It must not be confused with instance-side unknown-property rejection.

All three shortlisted validators can enforce closed objects when the schema expresses that rule.

### 3. URI format assertion should remain disabled unless the profile explicitly requires it

Draft 2020-12 requires support for the format-annotation vocabulary, while format assertion is optional and is required to be disabled by default for the annotation vocabulary.[S1]

For this contract:

- Do not enable generic URI `format` assertion merely as a hardening measure.
- Do not reject a URI because it has a credential-bearing authority component.
- Do not dereference any record-home URI.
- Enforce only the schema's settled structural and length constraints plus any explicitly fixture-defined string policy.

This avoids turning valid untrusted data into an implementation-dependent rejection.

### 4. Unicode safety is an application rule above JSON syntax

Raw unescaped C0 controls are invalid JSON. Escaped control characters, however, decode to legitimate string values; the JSON Schema specification explicitly notes that NUL can appear in a JSON string.[S1][S4]

Consequently, a stronger contract rule that rejects controls or bidirectional overrides must scan decoded object names and string values. It cannot rely on syntax parsing alone.

The portable fixture manifest should define the exact prohibited code-point set. For bidirectional controls, the Unicode `Bidi_Control` property is the strongest stable source and currently covers U+061C, U+200E-U+200F, U+202A-U+202E, and U+2066-U+2069.[S5]

### 5. Validator messages are not safe diagnostics

All shortlisted libraries provide useful structured error data, but their native messages or parameters can include instance values, property names, paths, schema values, or excerpts. Those are unsuitable for the contract's no-echo rule.

The adapter should map parser and validator failures to a small, versioned diagnostic vocabulary such as phase, stable code, bounded safe path, and count. It should not pass through:

- native human-readable messages;
- instance values;
- labels, URIs, credential fragments, or secret-looking values;
- unknown property names;
- source snippets;
- local filesystem paths;
- schema values that may mirror sensitive instance data.

Bound both the number of reported diagnostics and the total serialized diagnostic size.

## Candidate comparison

| Candidate | Draft 2020-12 | Duplicate names | Exact 64 KiB and depth 8 | Closed objects | Unicode controls | Structured diagnostics | Adapter filesystem fit | Local projection | Overall |
|---|---|---|---|---|---|---|---|---|---|
| **Python 3.14.x + `jsonschema` 4.26.x** | Full support documented; explicit `Draft202012Validator` | Yes through `object_pairs_hook`; not safe by default | Byte cap externally; depth through token-aware pre-parser | Yes through schema | Post-decode scan required | Rich error objects and paths; normalize before reporting | Exclusive `x`, `fsync`, read-back, unlink | Stdlib transactional `sqlite3` | **Recommended** |
| **Java 25 LTS + networknt 3.x + Jackson 3.1.x** | Draft 2020-12 documented and bundled | Native Jackson strict duplicate detection | External byte cap; native parser depth constraint | Yes through schema | Post-decode scan required | Machine-readable networknt output; normalize before reporting | `CREATE_NEW`, `FileChannel.force`, read-back, delete | Additional embedded DB/JDBC choice or snapshot | **Close second** |
| **Node.js 24 LTS + Ajv 8.20.x** | All Draft 2020-12 keywords documented | Separate raw tokenizer/parser mandatory; `JSON.parse` overwrites earlier duplicates | External byte cap and tokenizer depth guard | Yes through schema | Fatal UTF-8 decode plus post-decode scan | Structured Ajv error objects; sanitize parameters/messages | `wx`, file sync, read-back, unlink | Built-in `node:sqlite` still release candidate; external store or snapshot preferred | **Viable third** |

### Requirement-level confidence

| Claim | Python | Java | Node |
|---|---:|---:|---:|
| Draft 2020-12 support | High | High | High |
| Production-active release line | High | Medium-High | High |
| Duplicate-name rejection path | High | Medium-High | High that a separate parser is required |
| Exact raw-byte cap | High via adapter guard | High via adapter guard | High via adapter guard |
| Depth cap | High via adapter guard | High with Jackson constraint plus fixture verification | High via adapter guard |
| Closed-object enforcement | High | High | High |
| Control/Bidi_Control rejection | High as adapter policy | High as adapter policy | High as adapter policy |
| Safe bounded diagnostics | High if normalized | High if normalized | High if normalized |
| Atomic fail-if-target-exists create | High on supported local filesystems | High on supported local filesystems | High on supported local filesystems; Node documents a network-filesystem caveat |
| Atomic compare-current-content-and-delete | Not provided | Not provided | Not provided |
| Transactional local projection | High with `sqlite3` | Medium; external choice required | Medium-Low with built-in module because it remains release candidate |

## Weighted decision score

This is an evidence-based decision aid, not a performance benchmark or standards score.

| Criterion | Weight | Python + `jsonschema` | Java + networknt/Jackson | Node + Ajv |
|---|---:|---:|---:|---:|
| Draft 2020-12 support and maturity | 25 | 24 | 24 | 24 |
| Raw-input guard fit | 20 | 17 | 19 | 14 |
| Safe structured diagnostics | 15 | 13 | 14 | 13 |
| Filesystem lifecycle and recovery | 20 | 18 | 19 | 18 |
| Replaceable local persistence | 10 | 10 | 6 | 6 |
| Operational footprint and maintenance | 10 | 9 | 6 | 8 |
| **Total** | **100** | **91** | **88** | **83** |

Interpretation:

- Python wins on the combined decision, mainly because the standard library covers the remaining adapter responsibilities with little additional dependency risk.
- Java wins the parser-constraint category but loses points on footprint and local-persistence selection.
- Node/Ajv is excellent at schema validation and ecosystem fit but needs the most deliberate raw-JSON parsing choice.

## Candidate assessment: Python

### Proposed stack

- CPython 3.14.x; current documentation at research time identifies 3.14.6, and the 3.14 line has a published maintenance schedule.[S9][S12]
- `jsonschema` 4.26.x, explicitly using `Draft202012Validator` rather than relying on an implicit latest-draft default.[S6][S7][S13]
- Python standard JSON decoder only when configured with duplicate-preserving pair hooks and invalid-constant rejection.
- Adapter-owned raw token/depth and Unicode guard.
- Standard-library `sqlite3` for local projection.

### Validation fit

**Draft support - High confidence.** `jsonschema` states full Draft 2020-12 support and exposes `Draft202012Validator`, `iter_errors`, schema checking, and structured error paths.[S6][S7]

**Unknown properties - High confidence.** Enforced by the closed schemas. No separate Python-library strict flag is needed for instance-side additional-property rejection.

**Duplicate names - High confidence, configuration required.** Python's default decoder accepts repeated names and keeps the last value. The documented `object_pairs_hook` receives every object's ordered name/value pairs before they become a dictionary, enabling rejection before information loss.[S8]

**Non-JSON constants - High confidence, configuration required.** Python's default decoder accepts `NaN`, `Infinity`, and `-Infinity`; `parse_constant` is the documented interception point and must be configured to reject them.[S8]

**Exact UTF-8 - High confidence, configuration required.** Do not pass raw bytes directly to `json.loads`, because Python can recognize UTF-8, UTF-16, or UTF-32 byte input. Decode the bounded bytes strictly as UTF-8 first, then parse the resulting text.[S8]

**Depth - High confidence that a pre-parser is required.** The standard decoder does not expose a contract-level maximum container-depth option. A small token-aware scan can enforce depth 8 before materializing the full object.

**Controls and bidi - High confidence.** Use a post-decode recursive scan of all string keys and values against the contract's fixture-defined prohibited set.

**Diagnostics - High confidence.** `ValidationError` exposes validator identifiers and instance/schema paths, and errors can be iterated lazily. The adapter must consume structural fields only and emit its own redacted codes rather than native messages or instance data.[S6][S7]

### Adapter capabilities

**Create-only write - High confidence.** Python's `open` mode `x` is exclusive creation and fails if the file already exists.[S9]

**Flush and read-back - High confidence.** The adapter can flush buffered data, call `os.fsync`, close, reopen, read the file, rerun raw and schema validation, and compare the canonical identity expected by the protocol. Python documents `os.fsync` on Unix and Windows.[S10]

**Conditional delete - Medium confidence because of filesystem race semantics.** Python can read, compare, unlink, and verify absence, but it has no single cross-platform primitive that atomically means "delete this path only if its current bytes or identity equal X." Use the protocol described in the filesystem section below.

**Local projection - High confidence.** `sqlite3` is a mature, lightweight, serverless disk database with transactions and explicit commit/rollback behavior. It is a strong fit for replaceable, device-local routing state.[S11]

Caveat: `sqlite3` is an optional CPython module at build time. The runtime compatibility declaration should require a build that includes it, or the adapter should select a separately tested snapshot-store alternative.

### Material risks

- Unsafe defaults must be overridden: duplicate keys and non-finite numbers are otherwise accepted.
- Depth enforcement is adapter-owned rather than decoder-native.
- Care is needed not to serialize Python exception text into diagnostics.
- Filesystem behavior must be tested on the supported local filesystems; network mounts should not be assumed compliant.

## Candidate assessment: Java

### Proposed stack

- Java 25 LTS.[S27]
- Current stable networknt `json-schema-validator` 3.x line, with the exact released artifact verified before pinning.
- Jackson 3.1.x LTS, at least 3.1.1; the current networknt project POM reviewed during research specifies Jackson 3.1.4 and Java 17 as its compilation baseline.[S23][S24][S28]
- A separately selected embedded JDBC store or a replaceable atomic snapshot for local projection.

### Validation fit

**Draft support - High confidence.** networknt documents support for Draft 2020-12, bundles the Draft 2020-12 meta-schemas, and supports a Draft 2020-12 dialect selection.[S23]

**Unknown properties - High confidence.** Enforced by the contract schemas.

**Duplicate names - Medium-High confidence.** Jackson's official parser documentation describes strict duplicate detection that throws on duplicate object field names. The exact Jackson 3.1.4 generated API page was not successfully retrieved in this research session, but the feature is long-standing and networknt 3.x is built on Jackson 3.1.4.[S24][S29]

**Depth - High confidence with release-fixture verification.** Jackson provides stream-read constraints including maximum nesting depth. The exact configured behavior should be covered by the project's raw fixture corpus.

**Byte size - High confidence only with an external raw-byte guard.** Enforce the exact 64 KiB limit before Jackson. A 2026 Jackson advisory showed that some `maxDocumentLength` parser paths could bypass configured length constraints in Jackson 3.0.0 through 3.1.0; 3.1.1 patched the issue. The networknt POM's Jackson 3.1.4 is beyond the patched version, but the contract should still use its own exact bounded read.[S30]

**Controls and bidi - High confidence.** Post-decode scan required, as with every runtime.

**Diagnostics - High confidence.** networknt exposes structured validation messages and machine-readable output forms. Native messages and arguments still need redaction and bounded mapping.[S23]

**URI handling - High confidence.** networknt documents annotation-only format behavior for Draft 2019-09 and later by default. Keep format assertions disabled for this contract unless a future declared profile explicitly changes that.[S23]

### Adapter capabilities

**Create-only write - High confidence.** Java NIO's `CREATE_NEW` fails when the target exists; its existence check and creation are documented as atomic with respect to other filesystem activities.[S25]

**Flush and read-back - High confidence.** `FileChannel.force` requests that file updates be written to the underlying storage device. Read-back can be performed with Java NIO after close.[S26]

**Conditional delete - Medium confidence.** `Files.deleteIfExists` is not an atomic compare-and-delete. Java documentation also warns that existence checks and moves may not be atomic unless specific filesystem support exists. Use a cooperative lock, immediate re-read, exact identity comparison, delete, and absence verification.[S25]

**Local projection - Medium confidence.** The JDK does not include an embedded relational database. A mature JDBC-backed embedded store or a versioned atomic snapshot can satisfy the replaceable projection requirement, but that choice adds another dependency decision not needed in the Python stack.

### Material risks

- Higher packaging and runtime footprint.
- More dependency-chain version management.
- Exact networknt artifact publication should be checked before pinning. The project README and POM identified 3.0.6, but one repository index observed during research lagged behind that version.
- Jackson constraints must be configured explicitly and covered by fixtures.
- Optional regex engines can affect full ECMA-262 regular-expression compatibility; run the official suite against the exact configuration.

## Candidate assessment: TypeScript/Node

### Proposed stack

- Node.js 24.x LTS. Node's release schedule lists 24.x as Active LTS, moving to maintenance on 2026-10-20 and reaching end of life on 2028-04-30.[S18]
- Ajv 8.20.x, using the dedicated Draft 2020-12 Ajv class.[S14][S17]
- A production-stable raw JSON tokenizer/parser capable of duplicate-name and depth enforcement, or an adapter-owned bounded tokenizer.
- A mature external local store or a carefully designed replaceable snapshot. Do not make the built-in `node:sqlite` module the default while its documented status remains release candidate.[S21]

### Validation fit

**Draft support - High confidence.** Ajv documents support for all Draft 2020-12 keywords and requires a separate Ajv class for this dialect.[S14]

**Unknown properties - High confidence.** Enforced by the schema. Ajv strict mode should additionally remain enabled during schema compilation to catch unsupported or ignored schema constructs, but this is schema hygiene rather than unknown-instance-property enforcement. If the schemas contain annotation-only `format` keywords, configure `validateFormats: false` or explicitly register those names as ignored annotations so strict schema compilation does not turn them into assertions or unknown-format failures.[S15][S16]

**Duplicate names - High confidence that a separate raw layer is mandatory.** ECMAScript's `JSON.parse` specifies that earlier values for duplicate names are overwritten. Once Ajv receives the resulting object, the duplicate evidence is gone.[S22]

**Byte size - High confidence.** Bound the file read before decoding.

**Strict UTF-8 - High confidence, configuration required.** Node's `TextDecoder` supports fatal decoding; when `fatal` is true, malformed decoding raises instead of silently replacing invalid byte sequences.[S20]

Do not use ordinary `Buffer.toString('utf8')` as the contract's decoder because replacement behavior can hide malformed input. Node documents that fatal decoding is unavailable when ICU is disabled, so the runtime compatibility profile must require an ICU-enabled build or a separately tested strict UTF-8 decoder.[S20]

**Depth - High confidence that a tokenizer/pre-parser is required.** Ajv validates parsed values and does not provide a raw JSON nesting-depth parser limit.

**Controls and bidi - High confidence.** Post-decode scan required.

**Diagnostics - High confidence.** Ajv emits structured error objects. The adapter must not expose `message`, `data`, verbose schema data, or parameters that contain unknown property names or instance-derived values. Map only allowed structural fields into contract-owned codes. Keep data-mutating options such as property removal, default insertion, and type coercion disabled; validation must not silently alter the candidate marker.[S16]

### Adapter capabilities

**Create-only write - High confidence on supported local filesystems.** Node recommends opening with `wx` and handling `EEXIST` rather than checking first. Its documentation explicitly warns that the exclusive flag may not work on network filesystems.[S19]

**Flush and read-back - High confidence.** File handles expose sync operations; the adapter can close, reopen, and verify. Node also warns that concurrent filesystem modifications are not synchronized or thread-safe, so sequencing and locking are application responsibilities.[S19]

**Conditional delete - Medium confidence.** As with Python and Java, no single content-conditional delete primitive exists. Use the shared protocol described below.

**Local projection - Medium-Low for the standard-library path.** Node 24.18 documents `node:sqlite` at Stability 1.2, release candidate. A production decision should either accept and test that status explicitly, choose a mature external binding, or use a replaceable atomic snapshot.[S21]

### Material risks

- Additional parser/tokenizer dependency or adapter-owned parser logic.
- Ajv native errors require aggressive sanitization.
- Built-in SQLite stability is below the preferred production threshold.
- Exclusive create has a documented network-filesystem caveat.
- Node 24 moves from Active LTS to Maintenance LTS in October 2026; the implementation should account for its lifecycle.

## Filesystem lifecycle and interruption recovery

### Atomic create-only does not mean atomic complete-file publication

All three runtimes can request a create operation that fails when the final marker path already exists:

- Python: exclusive `x` mode.[S9]
- Java: `CREATE_NEW`.[S25]
- Node: `wx` / `O_EXCL`.[S19]

That atomically protects the no-silent-replacement decision on supported local filesystems. It does not guarantee that an observer can never see an empty or partially written file between creation and completion.

The portable baseline should therefore be:

1. Inspect before drafting and confirmation.
2. After exact confirmation, open the final marker path with fail-if-exists semantics.
3. Write the complete bounded document.
4. Flush and request file synchronization.
5. Close the handle.
6. Reopen and read back from the final path.
7. Re-run the same raw guards and schema validation.
8. Verify the exact marker identity and expected content.
9. Report registration complete only after read-back succeeds.
10. Update the local projection only after authoritative marker completion.

If interruption leaves an existing partial or invalid marker, a later inspection must report the path as occupied and invalid. It must not overwrite it. Recovery then requires an explicit operator-authorized resolution path outside silent registration.

A temp-file-and-rename design can improve complete-file visibility on some filesystems, but portable no-replace atomic rename semantics, directory-entry durability, and crash behavior differ by operating system and filesystem. It should not be assumed as the cross-runtime compliance baseline without a narrower supported-filesystem profile.

### Conditional delete

No shortlisted runtime exposes a portable primitive equivalent to:

> Delete this path only if its current validated marker identity and bytes still equal the previously confirmed marker.

The defensible portable sequence is:

1. Acquire a cooperative per-workspace adapter lock.
2. Read the marker using the bounded validation pipeline.
3. Compare the marker's exact identity with the identity bound into the operator's confirmed unregister draft.
4. Immediately re-read and re-compare while holding the lock.
5. Delete the marker path.
6. Read back the path and verify absence.
7. Remove or rebuild the replaceable local projection only after absence is verified.

A non-cooperating external process can still race the final compare and delete. That time-of-check/time-of-use limitation must be documented. The adapter should minimize the window and never claim stronger filesystem isolation than it has.

### Filesystem compatibility declaration

Each runtime adapter should declare and test its supported filesystem profile. At minimum, conformance testing should distinguish:

- ordinary local filesystems on each supported operating system;
- symbolic-link and parent-directory substitution behavior;
- network or synchronized filesystems;
- read-only paths and permission failures;
- abrupt termination after create, during write, after flush, after close, and before read-back;
- concurrent cooperating adapter attempts.

Node explicitly cautions that exclusive creation may not work on network filesystems.[S19] Equivalent behavior should be tested rather than assumed for every runtime.

## Local link projection

The local projection is replaceable device-local routing state and must never become authoritative.

Recommended Python design basis:

- Store projection rows in a small SQLite database under an adapter-owned local application-data location.
- Use a transaction for each projection update.
- Include projection schema/version metadata and enough marker identity information to detect stale entries.
- Permit full rebuild from inspected workspace markers.
- Treat projection write failure as a retriable local-state failure, not a reason to modify or replace the marker.
- Never write local device paths into the marker's workspace reference; the marker continues to contain `.`.

Equivalent rules apply to Java or Node regardless of the chosen storage engine.

## Portable conformance-fixture corpus

### Fixture model

The independently versioned fixture corpus should have two input channels:

1. **Raw-byte fixtures**
   - Base64-encoded original bytes.
   - Used for byte ceiling, malformed UTF-8, BOM/encoding policy, duplicate names, depth, syntax extensions, control escapes, and parser behavior.

2. **Parsed-value envelopes**
   - A JSON value supplied after raw parsing concerns have been intentionally removed.
   - Used to isolate Draft 2020-12 schema semantics, closed objects, length/cardinality limits, independent surface versions, and normalized diagnostics.

An expectations manifest should identify, per fixture:

- stable fixture ID;
- fixture-corpus version;
- contract surface and schema version;
- input channel;
- expected terminating phase;
- expected accept/reject result;
- expected stable diagnostic code or bounded set of codes;
- optional safe logical path;
- whether execution must prove that no URI dereference or network schema retrieval occurred.

### Common runner sequence

Every runtime runner should perform the same conceptual steps:

1. Load only trusted, bundled contract schemas.
2. Base64-decode raw fixtures when applicable.
3. Apply exact byte, UTF-8, depth, duplicate-name, syntax, and Unicode checks.
4. Parse to the runtime value model.
5. Validate with the explicitly selected Draft 2020-12 validator.
6. Normalize the outcome into the versioned contract result form.
7. Compare only stable result fields with the expectations manifest.
8. Assert diagnostic count and serialized-size bounds.
9. Assert that forbidden fixture contents do not appear in diagnostics or logs.
10. Fail the compatibility claim on any mismatch.

### Runtime-specific execution

| Stack | Fixture runner approach |
|---|---|
| Python + `jsonschema` | Use the project's selected Python test runner, explicitly instantiate `Draft202012Validator`, feed raw fixtures through the bounded decoder/hooks, and compare normalized result objects. |
| Node + Ajv | Use `node:test` or the selected TypeScript test runner, instantiate the Draft 2020-12 Ajv class, feed raw fixtures through the selected duplicate-aware tokenizer, and compare normalized result objects. |
| Java + networknt | Use JUnit Platform, configure the Draft 2020-12 dialect and Jackson strict parsing constraints, then compare normalized result objects. |

### Required fixture categories

At minimum, include:

- exactly 64 KiB and 64 KiB plus one byte;
- malformed UTF-8 and disallowed alternate encodings;
- depth 8 and depth 9, including braces/brackets inside strings;
- duplicate object names at the root and nested levels;
- `NaN`, `Infinity`, and `-Infinity` tokens;
- raw unescaped controls and escaped controls that decode into strings;
- every fixture-defined bidirectional-control code point in keys and values;
- unknown/additional properties at every closed-object level;
- label, type-token, URI, and record-home boundary cases;
- a credential-bearing URI that must be accepted as untrusted data;
- a URI with an unsupported or unusual scheme that must not be dereferenced;
- exact literal `.` workspace reference cases;
- diagnostic non-echo cases containing canary labels, URIs, credentials, and secret-like values;
- schema reference attempts that would require network access, which must fail closed or be impossible because schemas are bundled;
- registration create collision, partial-write recovery, read-back mismatch, and projection-write failure;
- unregister identity mismatch, marker replacement between inspections, delete failure, and absence read-back.

### External conformance checks

In release CI, run both:

- the official language-agnostic JSON Schema Test Suite for Draft 2020-12; and
- Bowtie against the exact pinned runtime, validator, configuration, and optional format/regex dependencies.[S2][S3]

These external suites supplement the contract corpus. They do not replace it, because they do not cover the contract's raw-byte, no-echo, filesystem, authority, or projection rules.

Current exact Bowtie pass percentages for the shortlisted pinned configurations were not verified from a stable primary-source snapshot during this research. networknt's repository includes self-reported test-suite figures but warns they may not be current. The implementation decision should therefore require a fresh CI run rather than cite a historical percentage.[S23]

## Security and configuration requirements common to all candidates

1. Bundle all trusted schemas and meta-schemas needed by the declared profile.
2. Disable network retrieval for `$ref` resolution. An untrusted marker must never cause HTTP, file, classpath, package, or other unintended resource access.
3. Keep Draft 2020-12 `format` assertion disabled unless the declared validation profile explicitly requires it.
4. Never dereference record-home URIs.
5. Do not canonicalize away credential-bearing URI components merely to validate them.
6. Reject malformed raw input before schema validation.
7. Do not log raw marker bytes, decoded values, native validation messages, or local paths.
8. Use stable adapter-owned diagnostics with strict count and size caps.
9. Treat the local projection as disposable and rebuildable.
10. Test all filesystem guarantees on each supported operating-system/filesystem combination.

## Recommendation decision record

### Decision

Adopt **CPython 3.14.x + `jsonschema` 4.26.x** as the initial implementation target, with:

- explicit `Draft202012Validator` selection;
- locally bundled schemas and blocked network reference retrieval;
- disabled generic format assertion;
- a bounded raw-input guard for exact byte count, strict UTF-8, nesting depth, duplicate names, non-finite numeric extensions, and Unicode policy;
- normalized redacted diagnostics;
- exclusive create, sync, close, and full read-back before completion;
- cooperative lock plus exact re-check/delete/absence verification for unregister;
- `sqlite3` as the replaceable device-local link projection;
- mandatory execution of the portable contract corpus, official JSON Schema Test Suite, and Bowtie before declaring compatibility.

### Rationale

This stack gives the best overall balance of verified Draft 2020-12 support, parser configurability, filesystem primitives, transactional local persistence, operational simplicity, and maintainability. Java's parser-level controls are stronger, but the advantage is not sufficient to offset its added footprint and persistence dependency for this small local adapter. Node/Ajv is highly credible but needs the most additional raw-parser and persistence decisions.

### Conditions that would justify selecting Java instead

Select Java 25/networknt/Jackson if one or more of these are already true for the delivery environment:

- Java/JVM packaging and support are organizational standards.
- The adapter must integrate directly into an existing JVM host.
- A tested embedded database dependency is already approved.
- Native parser depth and duplicate constraints are preferred over a small adapter-owned pre-parser.
- The team accepts the larger dependency and deployment footprint.

### Conditions that would justify selecting Node instead

Select Node 24/Ajv if:

- TypeScript integration and team fluency materially reduce delivery risk;
- a production-approved duplicate-aware JSON tokenizer/parser is already available;
- a mature local persistence option is already approved; and
- the team accepts Node 24's lifecycle and network-filesystem caveats.

## Verification gaps and claims not established

The following were not fully verified from primary sources and must be checked before dependency pinning:

1. **Current exact Bowtie pass percentages** for each proposed version/configuration. Confidence: Low; do not use historical percentages as acceptance evidence.
2. **networknt 3.0.6 availability in every intended artifact repository.** The project README and POM identify 3.0.6, while an observed central index appeared to lag. Confidence: Medium.
3. **The exact Jackson 3.1.4 generated API page for strict duplicate detection.** The feature is documented in official earlier Jackson core APIs and Jackson 3.1.4 is in networknt's POM, but the exact generated page was not retrieved. Confidence: Medium-High.
4. **Cross-platform directory-entry durability after sudden power loss.** File `fsync`/`force` support is documented, but durable create/delete directory metadata varies by platform/filesystem. Confidence: Medium and outside ordinary immediate read-back conformance.
5. **Network-filesystem exclusive-create semantics for Python and Java.** Do not infer support; declare local filesystem support unless separately tested. Confidence: Medium.
6. **A portable atomic compare-by-content-and-delete primitive.** No such primitive was found in the shortlisted standard APIs. The lock/re-check/delete/read-back sequence is an engineering protocol with a disclosed residual race against non-cooperating writers. Confidence: High.

## Final confidence assessment

| Decision element | Confidence |
|---|---|
| Python `jsonschema` fully supports Draft 2020-12 | High |
| Ajv fully supports Draft 2020-12 | High |
| networknt supports Draft 2020-12 | High |
| Raw pre-parse layer is required in every runtime | High |
| Python is the best overall default under the stated requirements | Medium-High; this is an architectural judgment based on weighted requirements, not an objective benchmark |
| Java is the strongest alternative | High |
| Node is viable but requires an additional duplicate-aware parser and a persistence choice | High |
| Credential-bearing URIs can remain accepted without enabling generic format assertion | High |
| Safe diagnostics require adapter-owned normalization rather than native messages | High |
| Create-only file creation is available on supported local filesystems | High |
| Conditional identity-bound delete requires a protocol rather than one portable atomic primitive | High |

## Primary sources

### Specifications and conformance tooling

- **[S1]** JSON Schema Draft 2020-12 validation vocabulary: <https://json-schema.org/draft/2020-12/json-schema-validation>
- **[S2]** Official JSON Schema Test Suite: <https://github.com/json-schema-org/JSON-Schema-Test-Suite>
- **[S3]** Bowtie implementation/conformance tooling: <https://docs.bowtie.report/en/stable/implementers/>
- **[S4]** RFC 8259, JSON: <https://www.rfc-editor.org/rfc/rfc8259.html>
- **[S5]** Unicode Character Database `PropList.txt`, including `Bidi_Control`: <https://www.unicode.org/Public/UCD/latest/ucd/PropList.txt>

### Python and `jsonschema`

- **[S6]** `jsonschema` 4.26 documentation and feature statement: <https://python-jsonschema.readthedocs.io/en/stable/>
- **[S7]** `jsonschema` validation API, versioned validators, errors, and format behavior: <https://python-jsonschema.readthedocs.io/en/stable/validate/>
- **[S8]** Python JSON decoder hooks and default extensions: <https://docs.python.org/3.14/library/json.html>
- **[S9]** Python `open`, including exclusive `x` mode: <https://docs.python.org/3.14/library/functions.html#open>
- **[S10]** Python `os.fsync`: <https://docs.python.org/3.14/library/os.html#os.fsync>
- **[S11]** Python `sqlite3`: <https://docs.python.org/3.14/library/sqlite3.html>
- **[S12]** Python 3.14 release schedule: <https://peps.python.org/pep-0745/>
- **[S13]** `jsonschema` 4.26.0 release: <https://github.com/python-jsonschema/jsonschema/releases/tag/v4.26.0>

### Node.js and Ajv

- **[S14]** Ajv Draft 2020-12 support: <https://ajv.js.org/json-schema.html#draft-2020-12-breaking>
- **[S15]** Ajv strict mode semantics: <https://ajv.js.org/strict-mode.html>
- **[S16]** Ajv API and structured errors: <https://ajv.js.org/api.html>
- **[S17]** Ajv 8.20.0 release: <https://github.com/ajv-validator/ajv/releases/tag/v8.20.0>
- **[S18]** Node.js release schedule: <https://github.com/nodejs/Release#release-schedule>
- **[S19]** Node.js 24 filesystem API and exclusive-create caveat: <https://nodejs.org/download/release/latest-v24.x/docs/api/fs.html>
- **[S20]** Node.js `TextDecoder` fatal decoding: <https://nodejs.org/download/release/latest-v24.x/docs/api/util.html#class-utiltextdecoder>
- **[S21]** Node.js 24 `node:sqlite` stability status: <https://nodejs.org/download/release/latest-v24.x/docs/api/sqlite.html>
- **[S22]** ECMAScript `JSON.parse`, including duplicate-name overwrite behavior: <https://tc39.es/ecma262/multipage/structured-data.html#sec-json.parse>

### Java, networknt, and Jackson

- **[S23]** networknt `json-schema-validator` project documentation: <https://github.com/networknt/json-schema-validator>
- **[S24]** networknt current project POM and dependency versions: <https://github.com/networknt/json-schema-validator/blob/master/pom.xml>
- **[S25]** Java 25 `Files` API, including `CREATE_NEW`: <https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/nio/file/Files.html>
- **[S26]** Java 25 `FileChannel.force`: <https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/nio/channels/FileChannel.html#force(boolean)>
- **[S27]** Oracle Java SE support roadmap: <https://www.oracle.com/java/technologies/java-se-support-roadmap.html>
- **[S28]** Jackson project release and LTS status: <https://github.com/FasterXML/jackson>
- **[S29]** Jackson official `StreamReadFeature.STRICT_DUPLICATE_DETECTION` documentation (earlier API line; feature continuity should be verified on the pinned 3.x artifact): <https://fasterxml.github.io/jackson-core/javadoc/2.14/com/fasterxml/jackson/core/StreamReadFeature.html>
- **[S30]** Jackson Core document-length constraint advisory and patched versions: <https://github.com/FasterXML/jackson-core/security/advisories/GHSA-2m67-wjpj-xhg9>
