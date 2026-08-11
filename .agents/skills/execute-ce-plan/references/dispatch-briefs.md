# Dispatch Briefs

Use these as structures, not copy-paste scripts. Fill every placeholder from the plan, repo, and current run. Send only task-local context; never send the raw operator conversation.

## Contents

- Implementation Worker
- Read-Only Verifier
- Review Fixer
- Higher-Reasoning Advisor
- Delivery Worker
- Merge-Readiness Coordinator
- Operator Update

## Implementation Worker

```markdown
## Objective
Execute `<plan-path>` using the exact available `ce-work` skill in `mode:return-to-caller`. Implement every in-scope unit in dependency order and return control before the shipping tail.

## Definition of Done
- Every in-scope U-ID is complete or explicitly blocked.
- Unit and plan verification gates have evidence.
- The complete ce-work return envelope is present.
- No shipping-tail action was performed.

## Repo Constraints
- May modify: <unit-derived paths and necessary directly related files>
- Must not modify: <scope boundaries, settled/frozen artifacts, operator-owned changes>
- Preserve: <session-settled decisions and freeze points>

## Verification Gates
<exact plan verification lines and repo commands>

## Stop Conditions
Stop for infeasible or invalidated settled decisions, out-of-scope writes, secrets, authority expansion, or a required contract change. Do not improvise around them.
```

## Read-Only Verifier

```markdown
## Objective
Independently verify the implementation at `<head-or-diff>` against `<plan-path>`. Do not mutate anything.

## Inputs
- Plan digest: <digest>
- Relevant plan excerpts: <goal, U/R/F/AE/KTD, gates, DoD>
- Worker receipt: <receipt path or structured content>
- Actual diff/commits: <refs>

## Required Output
- verdict: green | red | needs-human
- units and requirements checked
- verification evidence checked or rerun
- findings with severity, file:line, evidence, and exact remediation condition
- scope deviations, settled-decision conflicts, and unverified claims
- exact head/diff reviewed

Treat an incomplete worker response as missing evidence, not success. This is analysis only: no edits, commits, pushes, replies, or reviewer requests.
```

## Review Fixer

```markdown
## Objective
Apply only the eligible findings in `<review-artifact>` to the current feature branch, preserving `<plan-path>`.

## Authorized Findings
<full structured findings, including IDs, locations, evidence, suggested fixes, and required verification>

## Boundaries
- Do not reinterpret whether a finding is valid; the dispatcher already routed it.
- Do not broaden the file set without returning a blocker.
- Do not change settled contracts, merge, rebase, force-push, or weaken checks.
- Return actual changed files and verification evidence.

## Done
Every authorized finding is fixed and verified, or returned with concrete evidence that it cannot be fixed inside the authorized scope.
```

## Higher-Reasoning Advisor

Invoke `paseo-escalate` with a brief shaped as:

```markdown
Question: <one sharply framed implementation-level judgment>

Decision boundary: The dispatcher will decide. Contract, product, scope, authority, and destructive choices remain with the operator.

Evidence:
- Plan and relevant decisions: <paths/IDs>
- Repo findings: <paths/lines>
- Worker/verifier disagreement: <concise facts>

Options already considered:
1. <option and tradeoff>
2. <option and tradeoff>

Ask: Return feasible options, risks, a recommendation, and the evidence that would falsify it.

This is analysis only. Do not edit, create, or delete files. Do not write code or mutate GitHub.
```

Record the advice and the dispatcher's decision separately. Advisor recommendation is evidence, not authority.

## Delivery Worker

```markdown
## Objective
Create or update the PR for the fully attested tree using `ce-commit-push-pr mode:pipeline archive:off branding:on` and return the PR receipt.

## Required Context
- Plan path and digest
- Final code-review artifact and head/diff
- Verification summary
- Durable implementation decisions and residual links
- Existing PR state, if any

## Boundaries
Do not change product files, merge, rebase, force-push, approve CI, or create a duplicate PR. Stop when GitHub state is unknown and cannot be resolved.

## Required Output
PR URL, branch, pushed head SHA, commits, PR title/body summary, verification included, and any failure/recovery path.
```

## Merge-Readiness Coordinator

```markdown
## Objective
Run `pr-merge-ready-loop` for `<pr-url>` until it returns `ready-to-merge` or an honest bounded residual. Never merge.

## Required Invariants
- Copilot review must be on the current head.
- Judge and fixer/babysitter use different model families.
- Judge is read-only; babysitter owns mutations.
- Any pushed fix requires another Copilot review and judge assessment.
- CI must have run and be green; empty check rollup is not green.
- Maximum three Copilot rounds.

## Required Output
status, PR URL, current head SHA, Copilot review SHA, judge verdict, CI evidence, fixes by round, residuals, and verdict-log path.
```

## Operator Update

```markdown
Status: <stage and state>
What changed: <one concise outcome>
Evidence: <receipts, checks, head/PR when relevant>
Next step: <one action>
Operator input needed: <specific decision or none>
```
