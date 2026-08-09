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

- **Objective:** Ship v1 of Arjim's near-term promise — a read-only awareness tier (Outcomes 1+2): portfolio, "what needs me", and "what changed" views with honest freshness/coverage, plus a required configure step that settles each workstream's conventions.
- **Product authority:** VISION.md — near-term promise (VISION.md:30-34), Conditions of trust (VISION.md:129-170), initial success tests (VISION.md:172-210).
- **Open blockers:** None. Conventions-file location/naming and the report artifact format are deferred to planning.

## Product Contract

### Summary

A read-only awareness tier — its only write is the operator-confirmed conventions file: every registered workstream appears in a portfolio view, alongside a "what needs me" view and a git-only "what changed" view, each answer marked with its freshness and coverage. After registration, a required configure step settles each workstream's conventions — Arjim's recommended defaults or the workspace's own — and every answer honors the six-state boundary rule, so unknown is never reported as nothing.

### Problem Frame

Registration is Arjim's only working capability (README.md:7). It answers one question — "is this a registered workstream?" — but the vision's promise is awareness: the operator should stop doing the rounds across tools, get one view of what needs attention, and know exactly what Arjim could and could not verify. Machine scan, registry consumption, status, progress, and freshness are all explicitly deferred (README.md:23; contracts/workstream-registration/README.md:25). The awareness tier is the designed-but-unbuilt heart of the near-term promise: without it, registration produces an inventory that answers no questions.

### Key Decisions

- **Local/self-hosted sources first** — coverage now, connectors later. (session-settled: user-directed — chosen over external connectors in v1: checkable sources earn trust before API connectors do.) Governs R9.
- **Workspace-declared awareness semantics** — the workspace defines what "needs me" means and its own freshness windows; Arjim recommends and scaffolds defaults, never owns them. (session-settled: user-directed — chosen over Arjim-internal profiles: the declaration's durable home is the workspace, not Arjim's cache.) Governs R1, R11, R14.
- **Required configure step after registration** — conventions are settled by accepting recommended defaults or specifying the workspace's own; a registered-but-unconfigured workstream is a gap item, never silently checked. (session-settled: user-directed — chosen over optional scaffold: settlement is a lifecycle requirement, not polish.) Governs R1, R4.
- **Scaffold writes are confirmed and create-only** — the same trust pattern as registration; a conventions file is never overwritten. (session-settled: user-directed — chosen over print-only recommend: the confirmed-write path already exists and is trusted via the marker.) Governs R3.
- **Check state in the replaceable projection** — rebuild may reset awareness history; the answer is then unknown, never nothing, and re-derivation from the workspace is possible but not guaranteed. (session-settled: user-approved — the reset consequence was surfaced and accepted.) Governs R12.
- **Explicit path inventory** — awareness reads markers from operator-supplied workspace paths; machine scan stays deferred. (session-settled: user-directed — chosen over machine scan in v1: discovery is a later capability, and honest coverage starts from an explicit list.) Governs R5.
- **Git-only delta** — "what changed" covers git-backed sources; everything else reports unsupported. (session-settled: user-directed — chosen over file-snapshot delta and over deferring delta: one honest mechanism beats a weak generic one.) Governs R7.
- **Both CLI and report surfaces, on demand** — interactive answers plus a regenerated report artifact; no scheduler in v1. (session-settled: user-directed — chosen over CLI-only and over cadence: "keeps me posted" is served by the artifact, not a background process.) Governs R16-R18.

### Requirements

**Configure step**

- R1. A registered workstream is not checkable until its conventions are settled in a required configure step.
- R2. The configure step settles conventions by accepting Arjim's recommended defaults or the workspace's own.
- R3. The configure write is create-only and operator-confirmed, with read-back verification; an existing conventions file is never overwritten.
- R4. A registered-but-unconfigured workstream appears as a resolvable gap item; it is never silently checked under defaults.

**Awareness views**

- R5. The portfolio view shows every registered workstream from the explicit path inventory, with its label, workspace, and record sources (Outcome 2).
- R6. The "what needs me" view shows items requiring the operator's decision, approval, or help across workstreams, each tagged with workstream, record source, requested action, and due date when one exists (Outcome 1).
- R7. The "what changed" view covers git-backed sources: new commits, branch movement, and status changes since the last successful check.
- R8. Every view answer shows when it was checked, which required record sources were checked, and which failed, were skipped, or are unsupported.

**Checking and trust metadata**

- R9. V1 checks local/self-hosted source types; any other declared type reports `unsupported` per the capability vocabulary (registration-result.schema.json:784-801) and never counts as checked.
- R10. "Nothing pending" is reported only when every required record source was checked successfully within its declared freshness window; an incomplete check is unknown, never nothing (VISION.md:51, 146).
- R11. Freshness windows are declared per workstream in its conventions; Arjim recommends defaults the workspace may override.
- R12. Check state (last-check times, per-source results, delta baselines) lives in the replaceable SQLite projection; after a rebuild it is unknown, never nothing, and may be re-derivable from the workspace but that is not guaranteed.
- R13. Awareness answers honor the six-state boundary rule of VISION.md:133-142 — current, stale, nothing after a complete check, required source inaccessible, required source unsupported, check not performed — with unknown never reported as nothing.

**Conventions artifact**

- R14. The conventions file is schema'd and versioned; readers dispatch on version, and an unsupported version is not interpreted, mirroring the marker rule.
- R15. Arjim ships versioned recommended default conventions; when its recommendation advances, workspaces still on the older version surface a gap item the operator can resolve, defer, or knowingly accept.

**Surfaces**

- R16. Awareness answers are available as CLI commands on demand.
- R17. Awareness answers are also available as a generated report artifact the operator can regenerate on demand.
- R18. Awareness runs on demand only; there is no scheduled or proactive delivery in v1.

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
  - Can proceed independently of: awareness tier internals; later outcomes per VISION.md:43

### Key Flows

- F1. Configure a workstream
  - **Trigger:** A workstream is registered and unconfigured.
  - **Steps:** Operator invokes configure; Arjim presents its recommended default conventions; operator accepts the defaults or provides the workspace's own; operator confirms the exact conventions; Arjim writes the conventions file create-only and verifies by read-back.
  - **Outcome:** The workstream is configured, or the operator defers and it remains a gap item per R4.
  - **Covers R1-R3, R14-R15.**

- F2. Run an awareness check
  - **Trigger:** Operator invokes an awareness command or report generation on demand.
  - **Steps:** Arjim loads the inventory from the explicit path list; reads each marker and its conventions; checks every required record source within its declared freshness window, reporting each as current, stale, inaccessible, or unsupported; assembles coverage; renders the portfolio, "what needs me", and "what changed" answers with their freshness and coverage metadata.
  - **Outcome:** Honest answers — "nothing pending" only when every required source was checked within its window; otherwise the boundary is shown per R13.
  - **Covers R5-R13, R16-R18.**

### Acceptance Examples

- AE1. **Covers R4.** Given a registered workstream with no conventions file, when the operator opens the portfolio, then the workstream appears with an "unconfigured" gap item and no check results — it is not silently treated as checked or as nothing pending.
- AE2. **Covers R9-R10.** Given a marker declaring a Planner URI, when an awareness check runs, then that source reports `unsupported`, the coverage note shows it, and "nothing pending" is not claimed.
- AE3. **Covers R10.** Given every required source checked successfully within its freshness window, when the operator asks "what needs me", then Arjim reports "nothing pending" with the check time and the source list.
- AE4. **Covers R12.** Given a rebuild of the projection, when the operator asks what changed, then delta and freshness answers are unknown (not empty) until the next successful check.
- AE5. **Covers R15.** Given a workspace on conventions version 1 and Arjim's recommendation at version 2, when the operator opens the portfolio, then a gap item surfaces the version difference for the operator to resolve, defer, or accept.

### Success Criteria

The awareness and coverage targets in VISION.md:176-183 bind: every registered workstream appears in the portfolio; every answer shows check time, required sources checked, and failures/skips; "nothing pending" only after complete checks; every needs-me item tagged with workstream, record source, requested action, and due date.

The reduced-management-effort targets in VISION.md:186-189 bind: routine status-checking visits to tools holding authoritative records drop at least 75% from the 30-day baseline; "what am I working on", "what needs me", and "what changed" are answerable from one Arjim view without opening another tool; for every registered workstream Arjim identifies purpose, lifecycle state, workspace, authoritative record sources, and the designated decision record source without relying on the operator's memory.

The success test's "marked active" language (VISION.md:180) depends on a lifecycle-state field the marker does not carry in v1 (deferred per contracts/workstream-registration/README.md:24); v1 treats every registered workstream as active, and the distinction lands with the field.

### Scope Boundaries

**Deferred for later**

- Machine scan of workspaces and automatic discovery (inventory is explicit paths only, R5).
- External connectors (Planner, SharePoint, email) — reported as `unsupported` per R9.
- The action tier: workstream admin, official filing, safe shared writes (Outcome 4).
- Proactive/cadenced delivery (R18).
- Non-git delta ("what changed" is git-only, R7).
- Lifecycle-state field in the marker; the "marked active" distinction.
- Cross-device (Outcome 5) and assistant coordination (Outcome 6).

**Outside this product's identity**

- Arjim performing the workstream's delivery work (VISION.md:95) — the awareness tier never writes to record sources.

### Dependencies / Assumptions

- Binding authority: VISION.md Conditions of trust #1 (VISION.md:133-142) and initial success tests (VISION.md:172-210) govern the trust behavior (R8, R10, R13).
- The v1 marker schema stays closed; the conventions file is a separate schema'd artifact, not a marker change.
- Record sources remain untrusted data: adapters never dereference or inspect URI content (CONCEPTS.md:44-46), and capability is reported per source, never by URI content.
- The marker carries no lifecycle state in v1, so the portfolio treats all registered workstreams as active (see Success Criteria note).
- Check state may be partially re-derivable from the workspace (e.g., git history) after a rebuild, but that is not guaranteed (R12).

### Outstanding Questions

**Deferred to Planning**

- Conventions file location and naming under the workspace (e.g., under `.workstream/`).
- Exact CLI command names and the report artifact format (markdown vs HTML).
- Which local source types ship in v1 and their concrete check semantics (e.g., which git signals count as needs-me).
- Default freshness-window values and the recommended-default template contents.

**Resolve Before Planning**

- None.

### Sources / Research

- VISION.md — product authority: near-term promise, conditions of trust, success tests.
- README.md:20-23 — current scope and explicit deferrals.
- contracts/workstream-registration/v1/registration-result.schema.json:778-801 — the capability-status vocabulary (`not-checked | unsupported | inaccessible`) R9 reuses.
- contracts/workstream-registration/README.md:20-25 — deferred marker fields (purpose, lifecycle state, decision record source) and deferred status/freshness.
- src/workstream_registration/projection.py:33-40, 446-461 — explicit-path rebuild and the projection schema R12 extends.
- docs/ideation/2026-08-01-arjim-improvement-ideation.md:62-68, 102-108, 130-138 — ideas 2 (coverage-driven authority escalation), 5 (per-workstream freshness contract), 7 (coverage gaps as primary feed) that shaped R11 and R15.
