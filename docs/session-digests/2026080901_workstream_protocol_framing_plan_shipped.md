---
lorespec: "0.1"
id: "2026080901"
date: "2026-08-09"
source: "opencode"
topic: "Workstream Protocol framing plan implemented, reviewed, and shipped"
tags: [workstream-protocol, docs, planning, dispatch, paseo, ce-work, kw-review]
classification:
  type: technical
  secondary_type: operational
  domains: [docs, planning, agent-orchestration]
  value: medium
trails: [workstream-protocol-framing, agent-dispatch, paseo-provider-routing]
---

## Session Arc

### Started
The operator primed a dispatch persona (dispatch-setup skill) and asked to deepen the requirements-only Workstream Protocol framing plan into an implementation plan via ce-plan.

### Pivots
- **Provider-routing correction:** The operator asked where to record "use OpenAI models via the opencode provider, not opencode-go" so other agents see it. Investigation showed the rule spans `~/.paseo/orchestration-preferences.json` (behavioral layer), `dispatch-setup`, and the hardcoding `paseo-delegate`/`paseo-escalate` skills. The rule was softened to a nudge, not a prohibition, and synced to heypogi's dotfiles.
- **Impl-worker model correction:** A gpt-5.6-luna agent was dispatched for implementation; the operator flagged impl must be handled by deepseek-v4-flash per orchestration-preferences. Cancelled (no edits landed), redispatched on deepseek-v4-flash at max reasoning.
- **kw:review availability:** The named kw:review subagent types aren't in this opencode environment; the reviewer ran both lenses inline and cross-checked facts against source.

### Ended
The framing plan was implemented (4 doc files), reviewed by kw:review (0 P1/P2, 1 P3), the P3 fixed, and the change committed (`c1714d2`) and pushed to main.

## ARTIFACT

- **A1. Implementation-ready framing plan** — `docs/plans/2026-08-08-001-docs-workstream-protocol-framing-plan.md`, upgraded in place from requirements-only to `implementation-ready` (ce-unified-plan/v1), with units U1-U4 in dependency order, per-unit Verification bars, a gate table, and a Definition of Done. Sequencing `U1 -> U2 -> U3 -> U4`.
- **A2. Workstream Protocol doc surface (delivered)** — four files: `VISION.md` (Workstream Protocol paragraph), `CONCEPTS.md` (glossary entry sharpened), `contracts/README.md` (new standard index, created), `README.md` (root pointer + registration reframed as conforming implementation). Committed as `c1714d2`.
- **A3. Provider-routing preferences** — `~/.paseo/orchestration-preferences.json` and heypogi's `dotfiles/paseo/orchestration-preferences.json` synced; `paseo-escalate`/`paseo-delegate` SKILL.md updated. Rule: for OpenAI models prefer `opencode/openai/<model>`; impl workhorse stays deepseek-v4-flash.

## DECISION

- **D1. Doc-surface decision** — Issue: should a `contracts/`-level README exist for the Workstream Protocol identity? Decision: create `contracts/README.md` as the standard index PLUS a root `README.md` pointer; the existing `contracts/workstream-registration/README.md` stays as the v1 implementation-boundary doc. Warrant: Outcome 6 cross-assistant framing needs a discoverable, assistant-neutral standard home distinct from the impl-boundary doc. Status: settled. Instance_of: plan's deferred-to-planning question resolved by operator.
- **D2. OpenAI provider routing** — Issue: which provider hosts OpenAI models when one is needed? Decision: prefer `opencode/openai/<model>` (e.g. `opencode/openai/gpt-5.6-sol`); no "never use codex" prohibition. DeepSeek workhorses stay on `opencode-go`. Warrant: `opencode-go` is the configured gateway; OpenAI models are reachable there; the operator wanted a nudge not a hard ban. Status: settled.
- **D3. Finished-plan disposal** — Issue: what to do with a completed registration plan? Decision: per CE, finished plans are left in place as decision artifacts (shipment derived from git, not recorded in the doc); the repo's `archive/` folder is a local convention. The completed registration plan was `git mv`'d to `archive/` and pushed (`7bd12f0`). Warrant: CE treats plans as decision artifacts; shipment status lives in git history. Status: settled (repo-local convention adopted).

## INSIGHT

- **I1. CE treatment of finished plans.** ce-work explicitly never mutates a plan; whether it shipped is derived from git. Superseded plans use `superseded_by:` frontmatter, not folder moves. Deleting (not archiving) is preferred for stale solution docs. Source: CE docs (ce-work.md, ce-compound-refresh.md). Confidence: high.
- **I2. Provider routing has three layers.** `~/.paseo/orchestration-preferences.json` is the behavioral layer paseo skills read; `dispatch-setup` defers to it; `paseo-delegate`/`paseo-escalate` hardcode providers and skip preferences. A routing rule only sticks if updated in the enforcing layers. Confidence: high.
- **I3. Deepseek-v4-flash is the impl workhorse.** Per orchestration-preferences, implementation routes to `opencode-go/deepseek-v4-flash` (thinking=max, auto-accept, fast, build). Frontier OpenAI models (gpt-5.6-sol/luna) are for planning/escalation, not impl. Confidence: high.

## PATTERN

- **P1. Visual "is a plan implemented?" check (local).** Run `git log --oneline --grep="feat" -- <plan>`; a top `feat:`/`fix:`/merge PR commit indicates shipped; only `docs:`/`add plan` commits indicate planned-but-not-implemented. Cross-check target deliverable files exist on disk. Instance_of: CE's "shipment derived from git" principle.
- **P2. Dispatch worker model selection (local).** Match the worker's model to the task role from orchestration-preferences: impl = deepseek-v4-flash, planning = frontier OpenAI (opencode/openai/gpt-5.6-sol), audit/review = minimax-m3. Do not reuse a planning worker's model for an implementation task.

## SOLUTION

- **S1. `openai` provider not configured.** The native `openai` provider returns "not configured"; OpenAI models live under `codex` and `opencode-go`/`opencode/openai/*`. Fix: route OpenAI models via `opencode/openai/<model>`, which is configured. Caveat: the rule is a preference nudge, not enforced hard ban.

## OPEN_QUESTION

- **Q1. Sync remaining worktree copies.** Two `.worktrees/` copies of `orchestration-preferences.json` (`feat-paseo-plan-exec-supervisor`, `opencode-learn`) were not synced; the operator did not ask to touch them. Whether they should be kept in sync remains open.

## Connections

- A1 —[led_to]→ A2
- A2 —[instance_of]→ A1
- D1 —[informed_by]→ I1
- D2 —[related_to]→ I2
- D3 —[informed_by]→ I1
- P1 —[instance_of]→ I1
- P2 —[informed_by]→ I3

## Trail Updates

- **workstream-protocol-framing:** plan upgraded, implemented, reviewed, shipped (A1, A2).
- **agent-dispatch:** dispatch persona used end-to-end (worker→verifier→operator report); worker model corrected per role (P2).
- **paseo-provider-routing:** routing preferences added and synced to heypogi dotfiles (A3, D2, I2, I3).
