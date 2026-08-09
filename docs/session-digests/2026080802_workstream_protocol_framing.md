---
lorespec: "0.1"
id: "2026080802"
date: "2026-08-08"
source: "opencode"
topic: "Resume the workstream management brainstorm in arjim via agent handoff, converge on 'workstream is a standard' named Workstream Protocol, and write the requirements-only plan"
tags: [arjim, workstream-protocol, ce-brainstorm, requirements-plan, paseo-orchestration, agent-handoff]
classification:
  type: strategy
  secondary_type: drafting
  domains: [arjim, product-framing, plan-governance, paseo-operations]
  value: high
trails: [arjim-product-framing, workstream-protocol, plans-requirements-only]
---

## Session Arc

### Started
The operator asked to "bring" the idle Paseo agent `ddceb3db` (working in the `workstream-registration` git worktree under `~/.paseo/worktrees/2fewjc5w`, workspace `wks_4f68526bd0fb84b3`) into this workspace (`C:\Users\rmicua\arjim`).

### Pivots
- **Agents can't be re-homed — handoff instead** — inspection showed agents are pinned to the workspace they were created in; no move command exists. The operator chose "send prompt to existing agent", and the agent produced a self-contained handoff carrying the converged brainstorm state into arjim.
- **Frame inversion: product → standard** — the worktree brainstorm had pivoted from "spin off workstream management into its own product" to "workstream is a standard, not a product"; the handoff confirmed this supersedes the layered-product framing. Verified against the real repo (contracts/, conformance corpus, VISION, CONCEPTS all present).
- **Naming dialogue: Protocol vs Standard** — three candidate directions (mapping, orientation, context, identity-recognition) collapsed to identity-recognition; then "Workstream Protocol" beat "Workstream Standard" on distinctiveness and mechanism-naming, despite Standard's broader scope-coverage.
- **Requirements plan first** — the operator chose a requirements-only unified plan before any doc edits; the plan was written to `docs/plans/` and the Workstream Protocol term captured in CONCEPTS.md.

### Ended
Requirements-only unified plan written and checked (Complete / Consistent / Focused / Usable by planning), CONCEPTS.md updated, wrapup running. The VISION.md/CONCEPTS.md edits and `contracts/` repositioning remain as next steps.

## ARTIFACTS

### A1. Requirements-only plan — `docs/plans/2026-08-08-001-docs-workstream-protocol-framing-plan.md`
- **What:** unified plan (`artifact_contract: ce-unified-plan/v1`, `artifact_readiness: requirements-only`, `product_contract_source: ce-brainstorm`). Goal Capsule + Product Contract: Summary, Problem Frame, Key Decisions (standard-not-product, name, conformance ownership, identity decoupling, workstream-specific machinery), Requirements R1–R5 (VISION framing, CONCEPTS recording, headroom note, `contracts/` positioning, no code changes), Scope Boundaries (deferred: genericization, second-assistant demo, domain mapping; outside: structural split, implementation rename), one Outstanding Question deferred to planning (whether a `contracts/` README is warranted), Sources with repo-relative pointers.
- **Evolution:** scoping synthesis was re-presented three times (initial → name locked → protocol-vs-standard flip) before confirmation; each revision re-confirmed before writing.

### A2. CONCEPTS.md addition — "Workstream Protocol" entry
- **What:** new glossary term settled during the dialogue: the assistant-neutral standard living in `contracts/` (marker schema, registration protocol, result vocabulary, conformance corpus); Arjim is one conforming implementation, not its owner; planned domains are future headroom, not current protocol scope.

## DECISIONS

### D1. Carry the brainstorm into arjim via handoff, not agent relocation (2026-08-08)
- **Decision:** Paseo agents are workspace-pinned; the converging method is a self-contained handoff produced by the source agent, then resumed in the target workspace.
- **Issue:** how to "bring an agent to this workspace" when no move exists.
- **Positions:** (a) continue in a new arjim agent seeded with context; (b) send prompt to existing agent for a handoff; (c) only hand back the final plan.
- **Arguments:** (a) loses continuity and duplicates context; (b) preserves the source session's convergence and costs one prompt; (c) too late — decisions were still open (naming).
- **Warrant:** the handoff artifact carries decisions + forks + resume instructions, so continuity survives the workspace boundary without moving processes.
- **Qualifier:** usually. **Status:** settled.

### D2. Workstream is a standard, not a product (2026-08-08)
- **Decision:** `contracts/` (marker schema, registration protocol, result vocabulary, conformance corpus) is an assistant-neutral standard; Arjim is one conforming implementation of it. Ownership is by conformance, not by layer. Supersedes the earlier "standalone workstream-management product" framing.
- **Issue:** the original brainstorm asked about spinning off workstream management into its own product.
- **Positions:** standalone product owning durable machinery; workstream as an assistant-neutral standard.
- **Arguments:** the standard framing dissolves the product-boundary question; the repo already carries the skeleton (contracts/ + conformance runner, marker already "assistant-neutral" per CONCEPTS, VISION Outcome 6 = cross-assistant).
- **Warrant:** a standard is implementable by any assistant, which is exactly the Outcome 6 ground; no structural work needed to start.
- **Qualifier:** always. **Status:** settled.

### D3. Name the standard "Workstream Protocol" (2026-08-08)
- **Decision:** the standard is named **Workstream Protocol**, decoupled from the `workstream-registration` implementation identity.
- **Issue:** the standard needed an assistant-neutral identity; candidates ranged over Workmark, Work Recognition Standard, Workstream Standard, Workstream Protocol.
- **Positions:** Standard (umbrella coverage of schema+protocol+vocabulary+conformance) vs Protocol (names the mechanism that makes it assistant-neutral).
- **Arguments:** Standard is more accurate on scope-coverage but is a weak, generic noun; Protocol is distinctive, brandable, names the recognition/exchange mechanism, and gives a cleaner future genericization story (one protocol per domain kind).
- **Warrant:** the name should tell what makes the artifact special (cross-assistant recognition), not what category it belongs to.
- **Qualifier:** in this case. **Status:** settled.

### D4. Requirements-only plan before doc edits (2026-08-08)
- **Decision:** the brainstorm produces the requirements-only unified plan first; VISION/CONCEPTS edits and `contracts/` repositioning follow.
- **Issue:** the agreed deliverable was doc edits; the operator asked for the plan artifact first.
- **Positions:** plan-first (durable handoff to planning) vs edits-only (plan is unnecessary ceremony for a framing decision).
- **Arguments:** the framing has enough structural decisions and scope boundaries that ce-plan or a future reader needs them in IDed, durable form.
- **Qualifier:** in this case. **Status:** settled — plan written; the VISION/CONCEPTS edits are the downstream implementation.

## INSIGHTS

### I1. Paseo agents are workspace-pinned; continuity crosses boundaries via handoff, not relocation
Agent state (cwd, workspace, session) is fixed at creation; the supported pattern for "bring this work here" is a self-contained handoff from the source agent. The handoff format that worked: current state → converged framing → agreed deliverable → open questions → resume instructions. Confidence: high (observed).

### I2. "Protocol" and "Standard" name different things for a contract corpus
For a contract spanning schema + interaction rules + result vocabulary + conformance corpus, "standard" is the accurate umbrella term, but "protocol" names the load-bearing mechanism (cross-assistant recognition/exchange). Naming after the mechanism wins on distinctiveness; naming after the category wins on coverage. Confidence: high.

### I3. A handoff-produced brainstorm can be resumed and written in a different repo than it started
The grounding dossier verified against the arjim checkout (contracts/, tests/contracts/, VISION, CONCEPTS) matched the handoff's claims — repo-relative paths and file names carried across unchanged, so the resume was clean. Confidence: high (observed).

## OPEN_QUESTION

### O1. Whether a `contracts/` README or index doc presents the Workstream Protocol identity
Carried in the plan as Deferred to Planning. The framing could live only in VISION.md + CONCEPTS.md, or `contracts/` could get a minimal identity doc. Blocks nothing; planning decides the doc surface.

## NEXT_STEP

### N1. Enrich the plan with ce-plan, or draft the VISION/CONCEPTS edits directly (operator)
The plan is requirements-only and Ready for Planning. The two routes: hand off to ce-plan to produce the implementation-ready plan for R1–R5 (VISION framing update, CONCEPTS update, `contracts/` positioning, minimal doc surface decision), or proceed straight to drafting the doc edits since the changes are documentation-only.

### N2. Reposition `contracts/` as the Workstream Protocol home (soon)
The identity decoupling decision (D3) implies `contracts/` is described as the standard's home, distinct from the `workstream-registration` implementation — but no structural rename in this plan's scope.

## Connections
- D1 —[led_to]→ A1; D1 —[informed_by]→ I1
- D2 —[informed_by]→ I2; D2 —[led_to]→ D3
- D3 —[led_to]→ A2; D3 —[led_to]→ N2
- A1 —[supersedes]→ workstream-registration-discovery-plan (positioning, not content)
- A1 —[depends_on]→ D4; O1 —[related_to]→ A1
- N1 —[follows_from]→ A1

## Trail Updates
- **arjim-product-framing:** converged "workstream is a standard, not a product"; name locked as Workstream Protocol; requirements-only plan written; CONCEPTS captured.
- **workstream-protocol:** new trail — standard identity, naming rationale, positioning requirements (R1–R5), deferred genericization.
- **plans-requirements-only:** first requirements-only unified plan under `docs/plans/` for the framing decision.
