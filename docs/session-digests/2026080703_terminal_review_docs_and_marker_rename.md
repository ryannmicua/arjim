---
lorespec: "0.1"
id: "2026080703"
date: "2026-08-07"
source: "opencode"
topic: "Workstream registration terminal verification, code-review follow-ups, P2 issue filing, user docs (Diataxis), and the .workstream/manifest.json marker-path rename"
tags: [workstream-registration, ce-code-review, manifest-rename, diataxis-docs, paseo-orchestration, dated-decisions, marker-path]
classification:
  type: technical
  secondary_type: operational
  domains: [workstream-registration, plan-governance, documentation]
  value: high
trails: [workstream-registration-planning, marker-path-rename, docs-usage]
---

## Session Arc

### Started
This session is the closing arc of the workstream-registration implementation loop: the terminal verification pass had just confirmed TERMINAL SUCCESS (all 11 units, 13 gates, 14 DoD items green on the committed tree), and the operator opened the post-implementation phase: "What did we do so far?"

### Pivots
- **Review discovered two P1 bugs** — the ce-code-review (MiniMax-M3 audit lead) found the icacls ACE regex captured only the last flag group (inherited `(I)` invisible) and a latent SELECT-then-INSERT race mapping to the wrong status. Both were confirmed against source by the orchestrator before being presented; the operator ordered fixes, which landed as two atomic commits verified GREEN by an independent minimax-m3 verifier.
- **P2s became GitHub issues** — after first being documented as follow-ups, the operator changed course: all six P2 findings were filed as issues #2–#7 on ryannmicua/arjim under a new `follow-up` label, with self-contained bodies (the audit report lives only in local tmp/).
- **"Point-and-read" was called out as operator-facing jargon** — the operator's own 08-04 D3 decision said it "never reaches the operator-facing surface"; the docs had violated that. All operator-facing surfaces now say plain "workstream registration"; the term remains only in implementer-facing artifacts.
- **The marker path was renamed to `.workstream/manifest.json`** — the operator decided the other direction from the 08-06 drift-reconciliation, deliberately adopting the previously-rejected name, and ordered it recorded as a dated decision superseding D3's path part and PLAN:551. The frozen schema hash changed as a consequence (recorded in the new digest).
- **Diataxis restructure of the docs** — the operator required the guide be written per the write-docs-diataxis skill and asked for a visual explanation grounded in code; the docs round produced five quadrant-clean files including how-it-works.md with three mermaid diagrams whose every symbol was independently verified against real file:line anchors.

### Ended
All work pushed to `origin/feat/workstream-registration` (21 commits vs main, HEAD==origin), docs review GREEN-WITH-NITS with all four nits applied, decision digest and rename verified by a deepseek-v4-flash verifier per the operator's explicit model choice. Open items: PR decision (operator), docs/raid.md staleness, tmp/liveview cleanup.

## ARTIFACTS

### A1. `docs/usage/` — five-file Diataxis documentation set
- **What:** quickstart.md (tutorial, 161 ln), guide.md (how-to, 213 ln), reference.md (lookup, 147 ln), how-it-works.md (explanation, 209 ln, three mermaid diagrams), installation.md (how-to, 107 ln). All live-verified against the installed CLI; every code citation checked real by an adversarial reviewer; zero "point-and-read" and zero old-path references (grep-gated).
- **Evolution:** superseded the original two-file docs round (quickstart + guide, commit 60f2ea2) that was reviewed GREEN with 4 polish nits; the nits were folded into the restructure and the four new-file review nits were applied in dc2fe94.
- **Source:** operator review directives (#1-#7), write-docs-diataxis skill, live CLI verification on CPython 3.14.6/Windows.

### A2. Decision digest `docs/session-digests/2026080702_marker_path_rename_manifest_json.md`
- **What:** dated 2026-08-07 operator ruling D1 (canonical marker path now `.workstream/manifest.json`, "marker" term retained), D2 (historical records not rewritten), D3 (point-and-read drops from operator-facing surfaces only). Records the superseded frozen schema sha256 (`6d323561…`) and the new one (`6cd7a020…`). Provenance of the old hash later corrected (4094ba0) after a verifier could not substantiate "recorded at U1" — the value was verified, the attribution was wrong.
- **Role:** the ruling that turned a previously-rejected rename direction into a decision, per repo insight "a recorded rename is a ruling; an unrecorded one is drift".

### A3. GitHub issues #2–#7 (label `follow-up`) on ryannmicua/arjim
- **What:** the six P2 code-review findings (envelope serialization inconsistency, confirmation.consumed timing, changed-marker-stopped post-delete semantics, _ENVELOPE_KEY fork-safety, release_lock silent unlink, partial ACL state on verify failure), each self-contained with severity, file:line, why-it-matters, and suggested fix.
- **Evolution:** superseded the earlier "documented follow-ups only" decision; issue bodies are the durable home since the 448-line audit report lives in gitignored tmp/.

### A4. Marker-path rename commit set (`1e2462a` + `6aaa1a4` + `4094ba0`)
- **What:** decision digest first, then the rename across 19 files (code constants MARKER_FILENAME/SAFE_PATH_MARKER, 9 conformance fixtures' safe_path values — 40 occurrences, contracts, plan R10/KTD2/KTD4, CONCEPTS.md, READMEs, docs). Verified GREEN by a deepseek-v4-flash verifier including a live register writing the new path. New frozen schema sha256 `6cd7a020be08c3478a0220ca719265ec43f2966b11fff531431a6b0f96adea0f`.

## DECISIONS

### D1. Verification/review model moving forward is `opencode-go/minimax-m3` (thinking on)
- **Decision:** All verification and review work uses MiniMax-M3 (thinking enabled), replacing the glm-5.2 verifier role from the implementation loop; it already matched the audit-lead role in orchestration-preferences.
- **Issue:** what model should verify fixes and review docs after the loop?
- **Warrant:** cross-family contrast from the deepseek builder is the property that makes review trustworthy; minimax-m3 is the configured audit lead.
- **Qualifier:** usually. **Status:** settled (one per-round override to deepseek-v4-flash occurred later for the rename verification, operator-directed).

### D2. Six P2 findings filed as GitHub issues, not fixed
- **Decision:** P2s from ce-code-review become issues #2–#7 with label `follow-up`; no fix round. Supersedes the earlier "documented follow-ups" stance.
- **Issue:** where should non-blocking review findings live so they are not lost?
- **Warrant:** issues are the durable, visible home; the audit report is local-only scratch.
- **Qualifier:** always (this session). **Status:** settled.

### D3. Marker path renamed `.workstream/workstream.json` → `.workstream/manifest.json` (operator, 2026-08-07)
- **Decision:** the durable marker is now written at `.workstream/manifest.json` in every living artifact; "marker" term retained. Recorded as digest 2026080702, superseding the path part of 08-04 D3 and PLAN:551 ("do not reopen the name or path").
- **Issue:** the operator expected manifest.json; the 08-06 adoption had enforced workstream.json after a CONCEPTS.md drift.
- **Positions:** keep workstream.json (frozen, do-not-reopen) vs rename to manifest.json (operator preference).
- **Arguments:** rename breaks the frozen path but a dated operator decision outranks a clause; keeping the name preserves the hash but contradicts the operator's mental model.
- **Warrant:** "a recorded rename is a ruling; an unrecorded one is drift" — the decision record converts the change from ambiguity to authority.
- **Qualifier:** always (v1). **Status:** settled (frozen schema hash changed to `6cd7a020…`).

### D4. Docs round: installation + Diataxis guide + visual, with 4 nits folded in
- **Decision:** docs/usage restructured per write-docs-diataxis (5 quadrant files), including installation.md and a code-grounded visual (how-it-works.md with mermaid); four earlier review nits included; four new nits applied in a follow-up commit (dc2fe94) after GREEN-WITH-NITS review.
- **Qualifier:** always. **Status:** settled, pushed.

## INSIGHTS

### I1. A recorded rename is a ruling; an unrecorded one is drift — and the ruling direction can reverse
The 08-06 adoption reverted CONCEPTS.md's "manifest" drift to the plan's "workstream.json" with a do-not-reopen clause; one day later the operator reopened and reversed the direction. The difference between "drift" and "ruling" was exactly the decision record. Confidence: high. (Also recorded in digest 2026080702.)

### I2. The 08-04 terminology commit was the drift source; the 08-06 reconcile surfaced the question as a decision
CONCEPTS.md drifted to "workstream manifest"/manifest.json in commit 6b965de while the plan stayed on "marker"; the adoption reverted it; the 08-07 decision adopted the drifted direction deliberately — the reconcile step was not wasted. Confidence: high.

### I3. The ce-code-review caught two real P1s that the exit-condition pass could not
The terminal pass verified spec-conformance; the audit's adversarial lens found a Windows icacls regex that hid the inherited `(I)` flag (no positive test existed) and a race path mapping IntegrityError to the wrong status. Confidence: high — both were verified against source and fixed with genuine regression tests (the inherited-flag test fails against the old regex).

### I4. Agent finish notifications can be silently lost; activity logs are the recovery
The manifest-rename worker completed both commits and verification but its finish notification never arrived; the agent sat idle with no requiresAttention flag. `paseo_get_agent_activity` (or `paseo logs`) recovered the completion evidence. Confidence: high.

### I5. Doc examples need live-verification discipline
Every command/flag/output/exit code in the docs round was verified against the installed CLI on scratch workspaces; the adversarial review re-checked ~60 code citations to exact lines and found zero factual errors. Live-verify-before-document proved itself as a standard. Confidence: high.

## PATTERNS

### P1. Dated-supersession clause (local)
When a later dated operator decision reverses an earlier "do not reopen" clause: rewrite the clause in place to record the supersession (who, when, which digest, what exactly is superseded) instead of silently editing the asserted value; keep earlier decision narrative untouched; create the decision digest BEFORE the artifact edits so the rename commit can cite it. (Instance: digest 2026080702 → PLAN:551.)

### P2. Review-follow-up loop (local to this orchestration)
Post-terminal review → triage findings to P1-fix vs P2-file vs P3-note → P1s: worker fixes with two atomic commits + full-suite re-verification → independent fresh-context verifier (different model family) with an adversarial brief ("your job is to break it") → arbitrate diff → push. P2s: self-contained GitHub issues. Nits: apply in small follow-up commit with grep-gates (zero old terms, zero stale citations).

### P3. Docs as five-quadrant Diataxis set with code-grounded diagrams (local)
quickstart=tutorial, guide=how-to, reference=lookup, how-it-works=explanation with mermaid diagrams whose every symbol is cited to real file:line, installation=how-to. Consistency gates: grep for banned old terms must be zero; all cross-links bidirectional; code fences balanced.

## OPEN_QUESTION

### O1. docs/raid.md is stale — who updates it and through which path?
D-003 still Active though resolved (CPython 3.14.6/jsonschema 4.26.0/sqlite3 3.50.4 recorded in compatibility.md at U6/U11); R-001/R-003–R-006 mitigations are implemented; nothing records post-implementation state or issues #2–#7. The file carries a proof_url (ce-raid/v1) so updates imply a /ce-proof sync step. Blocked on operator go/no-go.

## NEXT_STEP

### N1. Open the PR (operator decision, now)
Branch `feat/workstream-registration` is at 21 commits vs main, pushed, fully verified. `gh pr create` is one command away; the operator has repeatedly deferred. Urgency: now (only open gate left).

### N2. Delete tmp/liveview/ (someday)
Stopped HTML live view files still present; operator offered deletion twice without a verdict.

## Connections
- A2 —[led_to]→ A4; A4 —[instance_of]→ P1
- D3 —[supersedes_part_of]→ D3 (2026080401); D3 —[supersedes_clause]→ PLAN:551
- D1 —[informed_by]→ orchestration-preferences audit role
- A3 —[informed_by]→ ce-code-review report (tmp/ce-code-review-workstream-registration.md)
- I1/I2 —[informed_by]→ review C1 (2026-08-06), digest 2026080701
- A1 —[instance_of]→ P3; A1 —[informed_by]→ write-docs-diataxis skill
- I4 —[related_to]→ Paseo MCP escape-hatch tools
- O1 —[related_to]→ docs/raid.md, D-003, R-001/R-003-R-006

## Trail Updates
- **workstream-registration-planning:** marker path ruling updated to `.workstream/manifest.json` (digest 2026080702); plan and CONCEPTS.md updated; frozen hash now `6cd7a020…`.
- **marker-path-rename:** decision + rename + verification + provenance correction complete; branch pushed.
- **docs-usage:** five-file Diataxis set live at docs/usage/, review GREEN-WITH-NITS, nits applied (dc2fe94), pushed.
