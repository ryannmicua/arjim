---
title: "Agent dispatch must match the worker's model to the task's role (impl = deepseek-v4-flash, planning/escalation = frontier OpenAI, audit = minimax-m3)"
date: 2026-08-09
category: workflow-issues
module: paseo orchestration (agent dispatch model routing)
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - "Dispatching or creating a Paseo agent for an implementation task"
  - "Dispatching or creating a Paseo agent for planning or escalation work that needs a frontier model"
  - "Dispatching or creating a Paseo agent for audit/review work"
  - "Choosing the provider/model string for a new agent (opencode-go/... workhorses vs opencode/openai/<model> frontier models)"
  - "Reusing the model of one task role (e.g. a planning worker) for a different role (e.g. implementation)"
tags: [paseo, agent-dispatch, model-routing, orchestration-preferences, provider-routing, workflow]
---

# Route dispatched agents by role: match the model to the task's role, not the previous agent's model

## Context

Dispatching agents (Paseo/opencode workers) is a recurring operation in this repo's workflow: implementation units from a plan, planning/committee sessions, audit and review passes, and second-opinion escalations all get dispatched as agents with a chosen model. The model choice is not cosmetic — each role has an assigned model (and thinking/features settings) codified in `~/.paseo/orchestration-preferences.json`, with explicit budget rules behind it.

The friction that surfaced this guidance: during a documented dispatch session, a dispatcher reused a planning worker's model (gpt-5.6-luna, a frontier OpenAI model) for an implementation task. The operator corrected it with "impl should be handled by deepseek-v4-flash". The mistake was not malice — it was a dispatcher reaching for "the model that was just used for the previous task" instead of reading the model off the role of the new task. That reuse pattern, left unchecked, burns the limited OpenAI budget on work the primary workhorse should do, and it misallocates frontier reasoning to work that does not need it.

## Guidance

Read the dispatch target from the role, never from the previous agent. Before dispatching any agent, name the role (impl / planning / audit / default) and pick the model the preference file assigns to that role — not the model of the agent you happen to have been working with.

The role→model routing table, from `~/.paseo/orchestration-preferences.json`:

| Role | Model | Settings | Budget posture |
|---|---|---|---|
| impl | `opencode-go/deepseek-v4-flash` | `thinkingOptionId=max`, `features.auto_accept=true`, `features.fast_mode=true`, `modeId=build` | effectively unlimited |
| planning | `opencode/openai/gpt-5.6-sol` | `thinkingOptionId=high` | limited — reserve for high-value planning only |
| audit (lead reviewer) | `opencode-go/minimax-m3` | `thinkingOptionId=auto` | cross-family contrast from impl |
| audit (second opinion / escalation) | `opencode/openai/gpt-5.6-sol` | `thinkingOptionId=high` | limited — only when the first review is contested or high-stakes |
| default | `opencode-go/deepseek-v4-flash` | `thinkingOptionId=max`, `modeId=default` | effectively unlimited |

Routing rules the preference file states explicitly (quote):

- `"impl: model=opencode-go/deepseek-v4-flash, thinkingOptionId=max, features.auto_accept=true, features.fast_mode=true, modeId=build"`
- `"planning: model=opencode/openai/gpt-5.6-sol, thinkingOptionId=high (limited budget - reserve for high-value planning only)"`
- `"audit: model=opencode-go/minimax-m3, thinkingOptionId=auto (lead reviewer - cross-family contrast from impl). For a second opinion, escalate to model=opencode/openai/gpt-5.6-sol, thinkingOptionId=high."`
- `"PROVIDER ROUTING: For OpenAI models, prefer routing via the opencode provider as opencode/openai/<model> (e.g. opencode/openai/gpt-5.6-sol). DeepSeek workhorses stay on opencode-go."`
- `"deepseek-v4-flash is the primary workhorse with effectively unlimited usage. Use it for all impl, research, scheduled, and recurring work."`
- `"Claude and OpenAI budgets are limited. Reserve Claude (claude-opus-5) for human-skill work (ui) and OpenAI (opencode/openai/gpt-5.6-sol) for planning. Use them only when the task specifically requires their reasoning strength."`

## Why This Matters

Three failure modes follow from ignoring role-based routing:

1. **Budget burnout.** OpenAI (via the `opencode/openai` provider) is a limited resource; the preference file says so explicitly. Every implementation task misrouted to a frontier OpenAI model spends scarce budget on work `opencode-go/deepseek-v4-flash` should do with effectively unlimited usage — meaning the budget is not available later for the planning it was reserved for. Budget preservation is the whole reason the routing table exists.

2. **Model-strength mismatch.** Frontier models are reserved "only when the task specifically requires their reasoning strength". Implementation is not that case: it is the workhorse's job, with workhorse settings tuned for it (`auto_accept`, `fast_mode`, `build` mode). Putting a planning-strength model on an impl task is overkill that buys nothing; putting a workhorse on a planning task is underpowered. The role table is a strength-suitability map, not a style preference.

3. **Cross-family review contrast.** The audit role deliberately uses a different family from impl (`minimax-m3` as lead reviewer) so the reviewer does not share the worker's model-family blind spots — the same logic that mandates different-family verifiers in the worker/verifier loop. Misrouting an audit to the same family as the worker quietly turns review into rubber-stamping.

The observed mistake shows the cost concretely: a planning model (gpt-5.6-luna) was dispatched for an implementation task, and the operator had to stop and correct it — wasted budget, wrong-strength model, and a dispatch correction in the loop. The correction itself ("impl should be handled by deepseek-v4-flash") is the rule restated: the role defines the model.

## When to Apply

- **Dispatching implementation agents** (worker units from a plan, fixes, scheduled/recurring work): route to `opencode-go/deepseek-v4-flash` with the impl settings — never reuse whatever model the previous session used.
- **Dispatching planners or committees** (high-value planning, escalation of a decision): route to `opencode/openai/gpt-5.6-sol` via the opencode provider — and only when the task genuinely needs frontier reasoning.
- **Dispatching auditors/reviewers**: lead with `opencode-go/minimax-m3`; bring in `opencode/openai/gpt-5.6-sol` only as a contested/high-stakes second opinion — deliberately a different family than the primary for cross-model contrast.
- **Any dispatch where the role is not explicit**: name the role first. If you cannot name it, do not dispatch yet — default routing (`opencode-go/deepseek-v4-flash`, `thinkingOptionId=max`, `modeId=default`) is the fallback, not a planning model.
- **When a new task follows a different-role task in the same session** (the exact trap that produced the observed mistake): re-derive the model from the new role; do not carry the previous agent's model forward.

## Examples

**Before (the observed mistake).** A dispatch session was working with a planning agent on `opencode/openai/gpt-5.6-luna`. The next task was an implementation task — a unit of work to be built from a plan. The dispatcher reused the planning worker's model (gpt-5.6-luna) for the implementation agent. The operator corrected it: "impl should be handled by deepseek-v4-flash". The dispatch was redone with the impl role's model.

**After (the corrected dispatch).** The same implementation task, re-dispatched by role:

```
provider/model: opencode-go/deepseek-v4-flash
thinkingOptionId: max
features: { auto_accept: true, fast_mode: true }
modeId: build
```

**Correct dispatch, role by role.**

- Implementation unit from a plan → impl role → `opencode-go/deepseek-v4-flash` + impl settings.
- High-value planning / committee → planning role → `opencode/openai/gpt-5.6-sol`, `thinkingOptionId=high` (only when the reasoning is genuinely required).
- Review of the implemented unit → audit role → `opencode-go/minimax-m3` (lead), escalating to `opencode/openai/gpt-5.6-sol` only if the first review is contested or high-stakes.

The check in one question: "What role is this task, and what does the preference file route for that role?" — not "what model was I just using?"

## Related

- `docs/solutions/workflow-issues/paseo-worker-verifier-loop-operations.md` — the worker/verifier loop operations doc covers loop mechanics (finish-notification loss, memory reclamation, verifier independence), including the same cross-family-contrast principle for verifiers. This learning complements it on the model side: that doc says the verifier should be a different family than the worker; this learning says every dispatched role has its assigned model in the preference file. Loop operations is about how the loop runs; this learning is about which model each dispatched role gets.
- `docs/solutions/best-practices/readiness-review-adoption-before-execution.md` — cross-model review discipline (adopting a reviewer before executing); relevant context for the audit-role routing and escalation rules above.
- `docs/solutions/logic-errors/select-then-insert-race-maps-duplicate-target-conflict-to-integrity-error.md` — concrete evidence of the audit role assignment in practice (audit run by minimax-m3).
