---
title: Trustworthy Awareness Tier - Plan
type: feat
date: 2026-08-09
topic: awareness-tier
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: ce-brainstorm
execution: code
---

# Trustworthy Awareness Tier - Plan

## Goal Capsule

- **Objective:** Ship v1 of Arjim's honest on-demand awareness foundation — a read-only awareness tier that delivers Outcome 1 ("what needs me") in v1 and the on-demand half of Outcome 2 (portfolio and "what changed"), with honest freshness and coverage, plus a required configure step that settles each workstream's conventions. v1 is not the fulfilled near-term promise; the proactive half of Outcome 2 ("keeps me posted" without waiting to be asked) lands when scheduled delivery arrives (deferred per R18).
- **Product authority:** VISION.md — near-term promise (VISION.md:30-34), Conditions of trust (VISION.md:129-170), initial success tests (VISION.md:172-210).
- **Open blockers:** None at this revision. Conventions-file location/naming, the report artifact format, the awareness state-vocabulary contract's schema, and the v1 conventions' optional fields are deferred to planning.

## Product Contract

### Summary

A read-only awareness tier — its only write is the operator-confirmed conventions file: every registered workstream appears in a portfolio view, alongside a "what needs me" view and a git-only "what changed" view, each answer marked with its freshness and coverage. After registration, a required configure step settles each workstream's conventions — Arjim's recommended defaults or the workspace's own — and every answer honors the six-state boundary rule, so unknown is never reported as nothing.

### Problem Frame

Registration is Arjim's only working capability (README.md:7). It answers one question — "is this a registered workstream?" — but the vision's promise is awareness: the operator should stop doing the rounds across tools, get one view of what needs attention, and know exactly what Arjim could and could not verify. Machine scan, registry consumption, status, progress, and freshness are all explicitly deferred (README.md:23; contracts/workstream-registration/README.md:25). The awareness tier is the designed-but-unbuilt heart of the near-term promise: without it, registration produces an inventory that answers no questions.

### Key Decisions

- **Local/self-hosted sources first** — coverage now, connectors later. (session-settled: user-directed — chosen over external connectors in v1: checkable sources earn trust before API connectors do.) Governs R9.
- **Workspace-declared awareness semantics** — the workspace defines what "needs me" means and its own freshness windows; Arjim recommends and scaffolds defaults, never owns them. (session-settled: user-directed — chosen over Arjim-internal profiles: the declaration's durable home is the workspace, not Arjim's cache.) Governs R1, R2, R6, R6b, R6c, R11, R14.
- **Required configure step after registration** — conventions are settled by accepting recommended defaults or specifying the workspace's own; a registered-but-unconfigured workstream is a gap item, never silently checked. (session-settled: user-directed — chosen over optional scaffold: settlement is a lifecycle requirement, not polish.) Governs R1, R2, R3, R3b, R4.
- **Scaffold writes are confirmed and create-only** — the same trust pattern as registration; a conventions file is never overwritten. (session-settled: user-directed — chosen over print-only recommend: the confirmed-write path already exists and is trusted via the marker.) Governs R3, R3b, R14, R15.
- **Check state in the replaceable projection** — rebuild may reset awareness history; the answer is then unknown, never nothing, and re-derivation from the workspace is possible but not guaranteed. (session-settled: user-approved — the reset consequence was surfaced and accepted.) Governs R12, R12b, R7b.
- **Explicit path inventory** — awareness reads markers from operator-supplied workspace paths; machine scan stays deferred. (session-settled: user-directed — chosen over machine scan in v1: discovery is a later capability, and honest coverage starts from an explicit list.) Governs R5, R5b.
- **Git-only delta** — "what changed" covers git-backed sources; everything else reports unsupported. (session-settled: user-directed — chosen over file-snapshot delta and over deferring delta: one honest mechanism beats a weak generic one.) Governs R7, R7b.
- **Both CLI and report surfaces, on demand** — interactive answers plus a regenerated report artifact; no scheduler in v1. (session-settled: user-directed — chosen over CLI-only and over cadence: "keeps me posted" is served by the artifact, not a background process.) Governs R16, R17, R18.
- **Awareness-owned state vocabulary** — the six-state boundary (VISION.md:135-142) is expressed through two deterministic, awareness-owned, versioned closed vocabularies: a per-source execution result and a derived aggregate answer state, both defined in a new awareness-tier contract. The registration schema is not modified. (session-settled: user-directed — pressure-test recommendation: the registration vocabulary cannot express the boundary.) Governs R8, R10, R13.
- **Reference, never copy — wipe-safe awareness** — Arjim never stores durable copies of workspace-declared information that could drift; awareness reads by reference from workspace-owned declarations, and wiping markers or Arjim data loses nothing of the workstream. Missing referenced information is flagged as a resolvable gap item and may be scaffolded into the workspace for adoption, never fabricated. (session-settled: user-directed — decided in the 2026-08-09 pressure-test review: reference-not-copy over carrying fields in the conventions file.) Governs R12, R12b, R14b, R20.

### Requirements

**Boundary**

- R0. Awareness introduces checking adapters, a capability distinct from registration. Registration, generic marker parsing, and capability classification continue to treat record-source URIs as opaque, untrusted data and never dereference them. An awareness adapter may resolve and read a record source only after dispatching on a supported declared type, validating the type-specific locator, enforcing least access, and never echoing, persisting, or reporting raw URI content, credentials, or token material. Supported types and their check semantics are versioned and listed in the awareness contracts.

**Configure step**

- R1. A registered workstream produces no source-derived check results until its conventions are settled in a required configure step. The portfolio and configuration-gap evaluation still run for an unconfigured workstream; it appears as a resolvable gap item per R4 and is never silently checked.
- R2. The configure step settles conventions by accepting Arjim's recommended defaults or the workspace's own.
- R3. The first configure write is create-only and operator-confirmed, with read-back verification: the operator confirms the exact resulting file content under the registration trust pattern (in-memory digest, exclusive-create, fsync, reopen, re-validate, exact-identity verify); the file is read back and compared before the operation is reported complete. Changing an existing conventions file follows R3b. Any partial success (create ok, read-back failed, or a re-read mismatch) is reported under registration's retries-and-partial-success semantics, never silently treated as complete.
- R3b. Changing an existing conventions file is a confirmed conditional update: the current file is read and its exact content bound into the draft, the operator confirms the exact resulting content, the file is re-read and compared immediately before the write, and any difference stops the operation without writing. R3's create-only rule applies to the first write only. The conventions file carries two distinct version fields: `schema_version` (used for version dispatch, R14) and `recommended_profile_revision` (the most recent Arjim recommendation revision the workspace's conventions were settled against, supporting R15).
- R4. A registered-but-unconfigured workstream appears as a resolvable gap item; it is never silently checked under defaults.

**Awareness views**

- R5. The portfolio view shows every registered workstream from the explicit path inventory, with its label, the local workspace path (from the inventory — not the marker's literal workspace self-reference), and its record sources (Outcome 2).
- R5b. The portfolio is computed from a per-user, versioned, owner-only inventory file that lists the explicit workspace paths the operator has declared. The inventory file is the durable source of truth for the portfolio. A per-call `--paths` flag may import or override the inventory for a one-shot check, but it does not silently redefine the durable portfolio. A workspace with a valid marker that is not in the inventory is not shown in the portfolio; the portfolio states that it covers only inventory paths and reports global completeness as unknown, never claimed.
- R6. The "what needs me" view shows items requiring the operator's decision, approval, or help across workstreams, each tagged with workstream, record source, requested action, and due date when one exists (Outcome 1).
- R6b. A source observation becomes a needs-me item only when a versioned adapter rule, enabled by the workstream's conventions, maps it to an operator decision, approval, or help request. Arjim's recommended defaults ship with a documented minimum rule set per supported source type; a workstream whose conventions declare no rules produces no needs-me items and is reported as "no needs-me rules declared", never as "nothing pending".
- R6c. A needs-me item's due date, when present, comes only from the checked authoritative record's structured due-date field (or an operator-declared mapping in the conventions for an adapter that exposes one). Conventions may not supply a literal substitute due date, and due dates are never inferred from commit age, branch names, freshness windows, or prose. Absent a due date, the field is omitted; the answer is never fabricated.
- R7. The "what changed" view covers git-backed sources: new commits, branch movement, ref and working-tree state changes, and any other git-derived change an adapter can observe. R7b defines the baseline and bootstrap semantics.
- R7b. The "what changed" baseline is per (workstream, record source). The first successful check of a pair establishes a baseline and reports "change history before <baseline> unavailable"; the answer is never "nothing changed". Failed or partial checks do not advance the baseline. After a projection rebuild the next successful check is a bootstrap check, not a delta result.
- R8. Every view answer shows when it was checked, which required record sources were checked, and the per-source execution state of every required source from the awareness-owned vocabulary (checked, stale, failed, unsupported, or not-checked); failed, skipped, and unsupported sources are named, never silently omitted.

**Checking and trust metadata**

- R9. V1 checks local/self-hosted source types; any other declared type reports `unsupported` per the capability vocabulary (registration-result.schema.json:784-801) and never counts as checked. A declared type with no supporting adapter reports `unsupported`; an unrecognized or malformed type token reports `not-checked` with a structured code. Neither counts as checked.
- R10. "Nothing pending" is reported only when the aggregate answer state is current and the workstream's conventions produce no needs-me items. A stale or incomplete aggregate is reported as such, never as "nothing pending" (VISION.md:51). Freshness is judged per record source: a source is current when it was checked within its declared freshness window (VISION.md:146).
- R11. Freshness windows are declared per record source in the workstream's conventions; a workstream may also declare a single default that applies to every record source without its own declaration. Arjim recommends defaults the workspace may override. A source is current when it was checked within its declared window; timestamps are ISO-8601 UTC, and clock-source and timezone behavior are defined at planning.
- R12. Check state (per-source execution results, baseline references, last-check timestamps, and last-error codes) lives in one or more awareness-owned tables in the replaceable SQLite projection; the exact shape is defined at planning. Nothing in the projection survives a rebuild; the next successful check is a bootstrap check per R7b. The conventions artifact (R3, R3b, R12b, R14b) is workspace-owned and survives a rebuild.
- R12b. Operator gap dispositions (deferred, accepted) and the accepted Arjim recommendation revision are recorded in the conventions artifact, not in the projection; they are durable and survive a projection rebuild.
- R13. Awareness answers honor the six-state boundary rule of VISION.md:135-142 — current, stale, nothing after a complete check, required source inaccessible, required source unsupported, check not performed — with unknown never reported as nothing (VISION.md:144). The plan instantiates these through two closed, awareness-owned, versioned vocabularies (per-source execution result; derived aggregate answer state) defined in a new awareness-tier contract; the registration schema is not modified.

**Conventions artifact**

- R14. The conventions file is schema'd and versioned; readers dispatch on version, and an unsupported version is not interpreted, mirroring the marker rule.
- R14b. The conventions artifact declares, by reference, where the workspace itself declares the workstream's purpose and its designated decision record source; awareness reads them by reference and never stores copies in markers, the projection, or reports. Where a referenced declaration is missing from the workspace, the workstream surfaces a resolvable gap item and Arjim may scaffold a draft declaration into the workspace for the operator to adopt; it never fabricates the information.
- R15. Arjim ships versioned recommended default conventions; when its recommendation advances, workspaces still on the older version surface a gap item the operator can resolve, defer, or knowingly accept.

**Surfaces**

- R16. Awareness answers are available as CLI commands on demand.
- R17. Awareness answers are also available as a generated report artifact the operator can regenerate on demand.
- R18. Awareness runs on demand only; there is no scheduled or proactive delivery in v1.
- R19. Awareness persists and renders only allow-listed fields. The projection may store: workstream identity, record-source index and type token, check status and stable code, check timestamps, freshness window, and an opaque per-source baseline token. It never stores raw URI content, credentials, tokens, file contents, commit messages, filenames, or free text from a source. The CLI and report may render: label, local workspace path (length-capped), record-source type and index, status, timestamps, branch and ref names, commit identifiers, and — where the conventions opt in — commit subjects capped at 120 characters. Anything outside the allow list is not persisted or rendered; if an adapter cannot produce a value within the budget, the field is omitted and the source is reported per its status.
- R20. Arjim never stores durable copies of workspace-declared information that could drift (purpose, decision record source, or similar); awareness reads such information by reference from the workspace. All Arjim-owned awareness data (projection, reports) is disposable: wiping markers or Arjim data loses nothing of the workstream. Where workspace declarations are missing, Arjim flags a resolvable gap item and may scaffold a draft declaration into the workspace for the operator to adopt; it never fabricates the missing information.

### How This Work Fits Together

<!-- ce-section: work-relationships -->

This plan owns the **awareness tier** (Outcomes 1+2) — the current active area from the vision's ordering. The broader breakdown is the current understanding, not a committed roadmap:

- Action tier (Outcome 4 — workstream admin, official filing, safe shared writes)
  - Depends on: awareness trust earned here; not active scope
- Machine scan of workspaces (registry consumption)
  - Depends on: the explicit-path inventory shape decided here (R5)
  - Enables: discovery without manual per-path entry
- External record-source connectors (Planner, SharePoint, email)
  - Depends on: the `unsupported` capability reporting defined here (R9)
- Proactive delivery (cadence, notifications)
  - Depends on: on-demand awareness working and the report artifact shape
- Cross-device (Outcome 5) and assistant coordination (Outcome 6)
  - Sequencing: per VISION.md:43-44 these outcomes are sequenced after the awareness tier; their internals do not block awareness work, and awareness work does not block them.

### Key Flows

- F1. Configure a workstream
  - **Trigger:** A workstream is registered and unconfigured.
  - **Steps:** Operator invokes configure; Arjim presents its recommended default conventions; operator accepts the defaults or provides the workspace's own; operator confirms the exact conventions; Arjim writes the conventions file create-only and verifies by read-back.
  - **Outcome:** The workstream is configured, or the operator defers and it remains a gap item per R4.
  - **Covers R1-R4, R3b, R12b, R14-R15.**

- F2. Run an awareness check
  - **Trigger:** Operator invokes an awareness command or report generation on demand.
  - **Steps:** Arjim loads the inventory from the explicit path list; reads each marker and its conventions; checks every required record source within its declared freshness window, reporting each as current, stale, inaccessible, or unsupported; assembles coverage; renders the portfolio, "what needs me", and "what changed" answers with their freshness and coverage metadata.
  - **Outcome:** Honest answers — "nothing pending" only when every required source was checked within its window; otherwise the boundary is shown per R13.
  - **Covers R5-R15, R16-R18, R19, R20; acceptance coverage is enumerated by AE1-AE16.**

### Acceptance Examples

- AE1. **Covers R1, R4, R6b.** Given a registered workstream with no conventions file, when the operator opens the portfolio, then the workstream appears with an "unconfigured" gap item and the "what needs me" view shows "no needs-me rules declared"; the workstream is not silently treated as checked or as nothing pending.
- AE2. **Covers R9, R10, R13.** Given a marker declaring a Planner URI, when an awareness check runs, then that source reports `unsupported` per the registration vocabulary, the per-source execution result reports `unsupported`, the coverage note shows it, and the aggregate answer state is incomplete — "nothing pending" is not claimed.
- AE3. **Covers R10, R13, R6b.** Given every required source reports current per the aggregate answer state and the workstream's conventions declare no enabled needs-me rules, when the operator asks "what needs me", then Arjim reports "nothing pending" with the check time and the source list.
- AE4. **Covers R7b, R12, R12b.** Given a rebuild of the projection, when the operator asks what changed, then the next successful check is a bootstrap check reporting "change history before <baseline> unavailable"; prior check state is unknown (not empty); durable dispositions in the conventions file remain.
- AE5. **Covers R3b, R14, R15, R12b.** Given a workspace on conventions `schema_version` 1 with `recommended_profile_revision` 1 and Arjim's recommendation at revision 2, when the operator opens the portfolio, then a gap item surfaces the version difference; the operator may resolve it (R3b re-read/compare/two-phase confirm), defer it (R12b disposition in the conventions file), or knowingly accept it (R12b accepted disposition in the conventions file).
- AE6. **Covers R2, R3.** Given a configure invocation that settles conventions, when the write is attempted, then the file is created exclusive-create, the operator confirms the exact resulting content, and the file is read back and compared before the operation is reported complete; any partial success (create ok, read-back failed, or comparison mismatch) is reported with registration's partial-success semantics, never silently treated as complete.
- AE7. **Covers R5.** Given a workstream in the explicit path inventory, when the operator opens the portfolio, then the workstream appears with its label, the local workspace path from the inventory (not the marker's literal workspace self-reference), and its record sources.
- AE8. **Covers R5b.** Given a workspace with a valid marker that is not in the inventory, when the operator opens the portfolio, then it does not appear and the portfolio states that it covers only inventory paths and cannot confirm the inventory is complete — completeness is reported as unknown, never claimed.
- AE9. **Covers R6, R6b, R6c.** Given a workstream with conventions declaring a needs-me rule and a record source with a structured due-date field, when the operator asks "what needs me", then the answer is one needs-me item per matching observation, tagged with workstream, record source, requested action, and the due date from the authoritative record. Given no due date on the matching record, the field is omitted — never fabricated. Given a workstream whose conventions declare no rules, the view reports "no needs-me rules declared", never "nothing pending".
- AE10. **Covers R7, R7b, R11.** Given a workstream whose git record source has an established baseline and a new commit appears, "what changed" reports the commit. Given the first successful check of that record source, the answer is "change history before <baseline> unavailable", never "nothing changed". Given a check that fails before establishing a baseline, no baseline advances; a subsequent successful check establishes a new baseline.
- AE11. **Covers R8, R10, R11, R13.** Given a workstream whose declared freshness window for a record source has passed since the last successful check, when the operator views the portfolio, then that source is reported as `stale` (a distinct per-source state in the closed vocabulary) and the aggregate answer state is stale — the answer is never "checked" or "nothing pending".
- AE12. **Covers R14.** Given a workspace whose conventions file declares an unsupported `schema_version`, when the operator opens the portfolio, then the workstream is reported as unreadable under the awareness vocabulary, never as checked or as nothing pending — mirroring the marker version rule.
- AE13. **Covers R16, R17, R18.** Given no operator invocation, no awareness answer is produced. Given a CLI invocation, the answer is available. Given a report-artifact regeneration, the answer is available. CLI and report render the same per-source states and the same aggregate answer state.
- AE14. **Covers R19.** Given a record-source URI containing a canary token, when the awareness projection and a generated report are inspected, then the canary token does not appear in the projection database, in the report artifact, or in the CLI output — mirroring the registration canary no-echo scan.
- AE15. **Covers R14b, R20.** Given a workstream whose workspace declares its purpose and designated decision record source at the referenced location, when the operator opens the portfolio, then both are rendered by reference from the workspace. Given that Arjim's projection and reports are wiped, then the workstream's own declarations are unchanged — wiping Arjim data loses nothing.
- AE16. **Covers R14b, R20, R4.** Given a workstream whose conventions reference a purpose or decision record source declaration that does not exist in the workspace, when the operator opens the portfolio, then a resolvable gap item flags the missing declaration and Arjim may scaffold a draft declaration into the workspace for the operator to adopt; the information is never fabricated.

### Success Criteria

The awareness and coverage targets in VISION.md:176-183 bind: every registered workstream appears in the portfolio; every answer shows check time, required sources checked, and failures/skips; "nothing pending" only after complete checks; every needs-me item tagged with workstream, record source, requested action, and due date.

The reduced-management-effort targets in VISION.md:186-189 are binding in principle, evaluated as follows. The 75% reduction target (VISION.md:187) is a post-pilot evaluation target: a separate pilot plan must define and capture the 30-day baseline, qualifying visits, supported-source eligibility, and measurement method before it is evaluated; v1 contains no visit-counting requirement (effort baseline capture is deferred). The "answer three questions from one Arjim view" target (VISION.md:188) binds in v1 via R5-R7. The VISION.md:189 identification target binds in v1 as: workspace and authoritative record sources from the marker and the inventory (R5); purpose and designated decision record source by reference from workspace declarations where they exist, with missing declarations surfaced as resolvable gap items (R14b, R20); lifecycle state remains deferred (see note below).

The success test's "marked active" language (VISION.md:180) depends on a lifecycle-state field the marker does not carry in v1 (deferred per contracts/workstream-registration/README.md:24); v1 treats every registered workstream as active, and the distinction lands with the field.

### Scope Boundaries

**Deferred for later**

- Machine scan of workspaces and automatic discovery (inventory is explicit paths only, R5).
- External connectors (Planner, SharePoint, email) — reported as `unsupported` per R9.
- The action tier: workstream admin, official filing, safe shared writes (Outcome 4).
- Proactive/cadenced delivery (R18).
- Non-git delta ("what changed" is git-only, R7).
- Lifecycle-state field in the marker; the "marked active" distinction.
- A dedicated "where each workstream stands" current-status view (VISION.md:63, 69) — v1's portfolio shows inventory plus freshness and coverage metadata per workstream; a standalone status view is not a v1 deliverable and lands with the lifecycle-state field.
- Cross-device (Outcome 5) and assistant coordination (Outcome 6).

**Outside this product's identity**

- Arjim performing the workstream's delivery work (VISION.md:95) — the awareness tier never writes to record sources.

### Dependencies / Assumptions

- Binding authority: VISION.md Conditions of trust #1 (VISION.md:133-142) and initial success tests (VISION.md:172-210) govern the trust behavior (R8, R10, R13).
- The v1 marker schema stays closed; the conventions file is a separate schema'd artifact, not a marker change.
- Record sources remain untrusted data to the registration path: it never dereferences or inspects URI content (CONCEPTS.md:46 as amended). Awareness checking adapters dereference only supported local source types under R0; capability is reported per source index, never by URI content.
- The marker carries no lifecycle state in v1, so the portfolio treats all registered workstreams as active (see Success Criteria note).
- Check state is fully cleared by a rebuild. The next successful check is a bootstrap check per R7b, not a delta result, and reports "change history before <baseline> unavailable"; reading the current git HEAD after a rebuild produces a new baseline, not a lost one, and the intervening history is reported unavailable.
- Markers and all Arjim-owned awareness data (projection, reports) are disposable: wiping them loses nothing of the workstream. Workspace-owned artifacts are the durable truth, and awareness reads workspace-declared information by reference (R20).

### Outstanding Questions

**Deferred to Planning**

- Conventions file location and naming under the workspace (e.g., under `.workstream/`).
- Exact CLI command names and the report artifact format (markdown vs HTML).
- Which local source types ship in v1 and their concrete check semantics (e.g., which git signals count as needs-me; the documented minimum rule set per R6b).
- Default freshness-window values and the recommended-default template contents.
- The awareness state-vocabulary contract's schema (per R13).
- Effort baseline capture — the 30-day pilot baseline (VISION.md:176), qualifying-visit definition, measurement method, and re-evaluation of the 75% target. v1 contains no visit-counting requirement.

**Resolve Before Planning**

- The home directory and version strategy of the new awareness-tier state-vocabulary contract (per R13). The plan declares the contract; planning chooses the home (e.g., `contracts/awareness/v1/awareness-result.schema.json`) and pins the version strategy. The operator approved the contract's existence (2026-08-09).
- Decided (2026-08-09, operator): purpose and designated decision record source are read by reference from workspace declarations, never stored by Arjim — R14b, R20. No further decision required.
- Confirmation that CONCEPTS.md:46 is amended to scope the no-dereference rule to registration adapters (companion edit to R0); recorded for traceability, not a planning blocker.

### Sources / Research

- VISION.md — product authority: near-term promise, conditions of trust, success tests.
- README.md:20-23 — current scope and explicit deferrals.
- contracts/workstream-registration/v1/registration-result.schema.json:778-801 — the capability-status vocabulary (`not-checked | unsupported | inaccessible`) R9 reuses.
- contracts/workstream-registration/README.md:20-25 — deferred marker fields (purpose, lifecycle state, decision record source) and deferred status/freshness.
- src/workstream_registration/projection.py:33-40, 446-461 — explicit-path rebuild and the projection schema R12 extends.
- docs/ideation/2026-08-01-arjim-improvement-ideation.md:62-68, 102-108, 130-138 — ideas 5 (per-workstream freshness contract) and 7 (coverage gaps as primary feed) shaped R11 and R15. Idea 2 (coverage-driven authority escalation) belongs to the deferred action tier and is not cited.
