---
lorespec: "0.1"
id: "2026080702"
date: "2026-08-07"
source: "opencode"
topic: "Dated operator decision renaming the canonical marker path from .workstream/workstream.json to .workstream/manifest.json in every living artifact, superseding the 'do not reopen the name or path' clause"
tags: [operator-decision, marker-path, rename, ruling-not-drift, workstream-registration]
classification:
  type: decision
  secondary_type: technical
  domains: [workstream-registration-planning, plan-governance]
  value: high
trails: [workstream-registration-planning, marker-path-rename]
---

## Session Arc

### Started
The operator issued a dated decision on 2026-08-07: the canonical marker path `.workstream/workstream.json` is renamed to `.workstream/manifest.json` everywhere it is a LIVING artifact. This deliberately supersedes the path part of the plan's "do not reopen the name or path" clause (PLAN:551) and the path retention in the 2026-08-04 D3 decision (digest 2026080401). Historical records are NOT rewritten; the decision record makes the rename a ruling, not drift.

### Pivots
- **Ruling over drift:** Repo insight I2 (digest 2026080701) established that an unrecorded rename looks like an error, not a ruling. This session's rename is recorded here before any artifact changes, so implementing agents treat it as settled rather than as a contradiction to reconcile.
- **Same-round terminology pass:** In the same round, operator-facing surfaces drop the internal "point-and-read" vocabulary for the plain term "workstream registration" (CLI help, pyproject description, README, quickstart, guide). "Point-and-read" remains in implementer-facing artifacts (plan, CONCEPTS.md, contracts README/protocol) per the 2026-08-04 D3 decision.

### Ended
Digest written; rename applied across code, fixtures, contracts, docs, plan, and CONCEPTS.md; full verification green (362 pytest tests, 87/87 conformance); two atomic commits (decision first, then rename).

## ARTIFACTS

### A1. Decision digest (this file)
- **What:** The dated operator decision that makes the path rename a ruling. Canonical marker path is now `.workstream/manifest.json`; the term "marker" itself is retained (only the filename changes).
- **Supersedes:** the path part of the 2026-08-04 D3 decision (digest 2026080401) and PLAN:551 "do not reopen the name or path". The rename is recorded, so it is a ruling, not drift. The frozen schema sha256 (`6d32356103d915842daa183272fbff8a6a480560411441eed8ac052f6664c22d`, verified during the terminal pass and ce-code-review; recorded in this session's operating map and exit spec, not in any repo commit) is superseded because the schema description string changes; the NEW hash after the rename is: `6cd7a020be08c3478a0220ca719265ec43f2966b11fff531431a6b0f96adea0f`.

### A2. Rename across living artifacts
- **What:** `.workstream/workstream.json` → `.workstream/manifest.json` (and the `workstream.json` filename constant → `manifest.json`) in: `src/workstream_registration/filesystem.py` (MARKER_FILENAME, marker_path docstring), `src/workstream_registration/diagnostics.py` (SAFE_PATH_MARKER), 9 `tests/contracts/workstream-registration/transitions/result-*.json` fixture files (every `safe_path` value, 40 occurrences total), `contracts/workstream-registration/README.md` (5), `contracts/workstream-registration/v1/registration-protocol.md` (4), `contracts/workstream-registration/v1/workstream.schema.json` (description string — frozen-schema content change), `CONCEPTS.md` (2), `README.md` (1), `docs/usage/quickstart.md` (6), `docs/usage/guide.md` (9), and the plan's living assertions (line 34 guidance, R10, KTD2, KTD4, U4 verification lines 405/561, and the line 551 supersession rewrite).
- **Scope note:** Historical records are intentionally left as historical: `docs/reviews/`, `docs/solutions/`, `docs/research/`, `docs/plans/archive/`, `docs/session-digests/2026080701*`, and `output-html/` still carry the old path; they record what was decided when it was decided and are not rewritten.

### A3. Operator-facing terminology pass (same round)
- **What:** "point-and-read" → "workstream registration" (plain) in operator-facing surfaces only: `docs/usage/quickstart.md`, `docs/usage/guide.md`, root `README.md`, the CLI help string (`src/workstream_registration/cli.py`), and the `pyproject.toml` description. "Point-and-read" stays in the plan, CONCEPTS.md, and the contracts README/protocol as internal plan vocabulary per D3 (2026-08-04).

## DECISIONS

### D1. Canonical marker path renamed to `.workstream/manifest.json`
- **Decision:** The canonical marker path is `.workstream/manifest.json` — the durable, assistant-neutral self-description of a workstream is now written at that path in every living artifact. The term "marker" is retained; only the filename changes.
- **Issue:** The 2026-08-06 readiness review (C1, digest 2026080701) found CONCEPTS.md had drifted to "workstream manifest" at `.workstream/manifest.json` while the plan asserted `.workstream/workstream.json`, and the adoption reconciled CONCEPTS.md to the plan with a "do not reopen the name or path" clause (PLAN:551). The operator now decides the other direction: the path itself changes.
- **Supersedes:** the path part of the 2026-08-04 D3 decision (digest 2026080401: "marker" and "point-and-read" retained) and PLAN:551 ("do not reopen the name or path"). The term "marker" is still retained; only the filename part of those rulings is superseded. The frozen schema sha256 (`6d32356103d915842daa183272fbff8a6a480560411441eed8ac052f6664c22d`, verified during the terminal pass and ce-code-review; recorded in this session's operating map and exit spec, not in any repo commit) is superseded because the schema description string changes; the NEW hash after the rename is: `6cd7a020be08c3478a0220ca719265ec43f2966b11fff531431a6b0f96adea0f`.
- **Warrant:** A dated, recorded decision outranks an earlier clause; unrecorded renames are treated as drift (insight I2, digest 2026080701), and recorded ones as rulings. The operator's 2026-08-07 decision is the ruling.
- **Qualifier:** always (v1). **Status:** settled (recorded in plan, digest 2026080702).

### D2. Historical records are not rewritten
- **Decision:** `docs/reviews/`, `docs/solutions/`, `docs/research/`, `docs/plans/archive/`, `docs/session-digests/2026080701*`, and `output-html/` keep the old path as historical record. Verification greps exclude them.
- **Warrant:** Historical records document what was true when written; rewriting them would erase the drift history this decision resolves. **Status:** settled.

### D3. "point-and-read" drops from operator-facing surfaces only
- **Decision:** Operator-facing surfaces (CLI help, pyproject description, root README, quickstart, guide) say "workstream registration" (plain) instead of "point-and-read workstream registration". Implementer-facing artifacts (plan, CONCEPTS.md, contracts README/protocol) keep "point-and-read" as internal plan vocabulary per the 2026-08-04 D3 decision.
- **Warrant:** "Point-and-read" never reaches the operator-facing surface (CONCEPTS.md definition, D3 08-04); the same round as the path rename is the cheapest time to complete that boundary. **Status:** settled.

## INSIGHTS

### I1. A recorded rename is a ruling; an unrecorded one is drift — and the ruling direction can reverse
The 2026-08-06 adoption reconciled CONCEPTS.md's "manifest" drift back to the plan's "marker at `.workstream/workstream.json`" with a "do not reopen" clause. One day later the operator reopened and reversed the direction: `.workstream/manifest.json` becomes canonical. The difference between the 08-04 "drift" and the 08-07 "ruling" is exactly the decision record. Confidence: high.

### I2. The 08-04 rename introduced the drift the 08-06 adoption then enforced
CONCEPTS.md drifted to "workstream manifest"/`manifest.json` during the 2026-08-04 terminology commit (`6b965de`); the 08-06 adoption reverted CONCEPTS.md to the plan. The 08-07 decision now adopts the drifted direction deliberately — the reconcile step was not wasted; it surfaced the question as a decision. Confidence: high.

## PATTERNS

### P1. Dated-supersession clause (local)
When a later dated operator decision reverses an earlier "do not reopen" clause, rewrite the clause in place to record the supersession (who decided, when, which digest, what exactly is superseded) instead of silently editing the asserted value, and keep earlier decision narrative untouched. The decision digest is created BEFORE the artifact edits so the rename commit can cite it.

## NEXT_STEPS

### N1. None — full corpus re-verified green
Both commits landed; pytest 362/362, conformance 87/87 with all gates. Future work references `.workstream/manifest.json` (digest 2026080702) as the frozen marker path.

## Connections

- D1 —[supersedes_part_of]→ D3 (2026080401); —[supersedes_clause]→ PLAN:551
- I1, I2 —[informed_by]→ I2 (2026080701), review C1 (2026-08-06)
- A3 —[informed_by]→ D3 (2026080401)

## Trail Updates

- **workstream-registration-planning:** marker path ruling updated to `.workstream/manifest.json` per the 2026-08-07 operator decision; supersession recorded at PLAN:551.
- **marker-path-rename:** created by this session (decision digest + rename).
