# Stage Contracts

Use this file as the dispatcher state machine. Complete stages in order. A child CE skill owns its documented internal procedure; the dispatcher owns whether its return is sufficient to advance.

## Contents

- Universal Receipt
- Stages 1–3: implement, verify, simplify
- Stages 4–6: review, browser verification, compound
- Stages 7–10: commit, attest, open PR, merge-ready loop
- Terminal Classes

Before every stage, confirm the plan still matches the digest recorded at preflight. An unexpected plan edit invalidates derived scope, gates, and settled decisions; stop and repeat preflight instead of continuing against stale authority.

## Universal Receipt

Require every stage agent to return:

- `status`: `complete`, `blocked`, or `failed`
- stage name and plan path
- starting and ending head SHA, when Git exists
- actual changed files, including unexpected files
- commands/checks run with results
- scope deviations and settled-decision conflicts
- blockers, residuals, and recovery path
- explicit statement of whether it committed or pushed

A verifier additionally returns `verdict: green|red|needs-human`, evidence for each finding, plan units/requirements checked, and the exact head/diff reviewed.

An incomplete return does not advance. Request one concise terminal receipt from the same agent. Replace the agent after a second incomplete return and record the failed handoff in the run ledger.

## Stage 1 — Implement

Dispatch one implementation worker with:

```text
ce-work mode:return-to-caller <plan-path>
```

Pass an `implementation_engine:` carrier only when the operator supplied a stage-scoped route that must be preserved. Do not invent a carrier from preference.

Require the complete `ce-work` return envelope, including changed files, attempted/completed U-IDs, verification results/evidence, behavior-change signal, engine/requested/actual route fields, unit receipts, plan checkpoint, blockers, recovery path, settled-decision conflicts, and `standalone_shipping_skipped: true`.

Stop on `blocked` or `failed`. For behavior changes, missing or non-credible verification evidence gets one same-run evidence-reconciliation call using the returned safe `run_id`, per `ce-work`'s recovery contract. Never start a second implementation run to repair a missing receipt.

## Stage 2 — Verify Plan Completion

Dispatch a fresh read-only verifier from a different model family. Give it:

- the plan path and digest;
- Goal Capsule, relevant U/R/F/AE/KTD excerpts, Verification Contract, and Definition of Done;
- the actual diff, commits, and `ce-work` receipt;
- permission to run read-only inspection and verification commands, but no mutation.

Require evidence that every attempted unit satisfies its verification line, dependencies were respected, changed paths are in scope, behavior evidence is coherent, and no settled decision was silently changed.

On red, return exact findings to the implementation worker. After fixes, use a fresh verifier. Two consecutive red verdicts on the same stage escalate to the operator.

## Stage 3 — Simplify

Skip only for documentation-only, generated/vendor/mechanical-only, or trivial code changes under roughly ten changed lines. Record the reason.

Otherwise dispatch a mutation worker to invoke `ce-simplify-code` on the branch diff. Pass the plan path only as structure-pin context and state that `session-settled:` KTDs must be preserved. Do not use the plan as simplification scope.

Require the simplify receipt to quantify applied/skipped findings by reuse, quality, and efficiency and list typecheck, lint, and tests. Follow with a fresh read-only verification of scope and behavior preservation before code review.

## Stage 4 — Review and Repair

Invoke:

```text
ce-code-review mode:agent plan:<plan-path>
```

Treat review as report-only. The dispatcher does not pre-investigate or edit. For each actionable `gated_auto` or `manual/downstream-resolver` finding:

1. Preserve the full structured finding and evidence.
2. Route eligible fixes to one bounded fixer; batch by file and avoid concurrent mutation in a shared checkout.
3. Run the finding's required targeted verification plus affected unit gates.
4. Invoke a fresh `ce-code-review mode:agent plan:<plan-path>` on the resulting tree.

Any fix invalidates the preceding review verdict. Never say "reviewed" after a fix until the fresh review returns.

Bound the loop to two repair rounds. Escalate earlier for an invalidating `settled_conflict`, a contract change, repeated same-root finding, or non-convergence. Preference-grade settled conflicts remain report-only but must be durably recorded.

Before advancing, make all remaining actionable findings either:

- fixed and verified;
- explicitly declined with evidence by the independent review/judgment path; or
- recorded as a durable non-blocking residual in the tracker or `<root>/residual-review-findings/<branch-or-head-sha>.md`.

P0/P1 residuals, invalidating settled conflicts, or missing durable records block shipping.

## Stage 5 — Browser Verification

Run `ce-test-browser mode:pipeline` when the diff changes user-visible routes, pages, components, layouts, browser interactions, or front-end behavior. Let the skill select its approved driver and manage the pipeline server.

Treat `FAIL` as a repair input and `PARTIAL` as a judgment item. Route code fixes through the mutation worker, re-run affected local gates and browser tests, then return to Stage 4 for a fresh code review. Record credential- or external-interaction skips honestly; never convert them to passes.

## Stage 6 — Compound the Learning

For each distinct, solved, verified, non-trivial learning, invoke separately:

```text
ce-compound mode:headless depth:full <one-sentence learning context>
```

Skip when no learning meets `ce-compound`'s preconditions and record why. Require the created/updated solution path, grounding result, overlap result, vocabulary result, and refresh recommendation. Treat `Documentation skipped` as a no-op, not success.

Because compounding may change tracked documentation or `CONCEPTS.md`, commit and attest the final tree afterward.

## Stage 7 — Commit the Attestation Candidate

Dispatch a worker to invoke `ce-commit` for every remaining intended tracked change. Exclude operator-owned, secret-shaped, generated, and unrelated paths. Require the resulting commit hashes, subjects, exact file sets, and a clean working tree with no intended untracked files.

This commit establishes the immutable local head for final review. If the tree is already clean because prior stages created the correct commits, record the existing head and advance without manufacturing an empty commit.

## Stage 8 — Final Local Attestation

Invoke a fresh `ce-code-review mode:agent plan:<plan-path>` on the exact committed head intended for push. Require its metadata head/diff, complete Coverage, Actionable Findings, and Verdict.

Advance only when there are no blocking actionable findings and every residual is durable. Do not allow tracked-file mutation after this stage. If tracked content changes, return to the relevant verification/review stages, invoke `ce-commit` again, and attest the new head. PR-description composition does not invalidate the committed-head attestation; tracked file creation does.

## Stage 9 — Push and Open the PR

Require at least one configured remote and working GitHub authentication. Missing remote or an unsupported forge yields `blocked-shipping`; do not pretend local completion is merge readiness.

Dispatch:

```text
ce-commit-push-pr mode:pipeline archive:off branding:on <plan-path-and-decision-context>
```

`archive:off` prevents a new tracked explainer commit after final local attestation. Require the PR URL, branch, pushed head SHA, commit list, body verification evidence, and confirmation that the open PR matches the current branch/head. Do not create a duplicate PR when PR state is unknown.

Require the pushed head SHA to equal the Stage 8 reviewed head SHA. Any content commit created by this stage invalidates Stage 8 and must be reviewed before shipping continues.

## Stage 10 — Merge-Ready Loop

Invoke `pr-merge-ready-loop` on the open PR. Its three roles remain separate:

- independent read-only judge: verdict and exact fix list;
- `ce-babysit-pr`: mutations, CI watch, feedback execution, and current-head state;
- Copilot: primary PR reviewer, requested through `request-copilot-code-review`.

Require all of the following for `ready-to-merge`:

1. Copilot has reviewed the current head SHA.
2. The independent judge has assessed that review and returned `ready`.
3. Every finding is fixed and verified, declined with evidence, or parked as a non-blocking follow-up.
4. CI has run and is green on the current head; an empty rollup is not green.
5. No open blocking thread, needs-human item, branch-currency blocker, or uncertain mergeability remains.

After any pushed fix, request another Copilot round and reassess the new head. Cap Copilot rounds at three. The loop never merges.

Before requesting Copilot, verify the installed `gh` supports the quoted `"@copilot"` reviewer flow and confirm through GraphQL that `copilot-pull-request-reviewer` actually entered `reviewRequests`. A command exit without that verification is not a successful request.

`ce-babysit-pr` invokes `ce-resolve-pr-feedback mode:pipeline` for review items and `ce-debug mode:pipeline` for CI failures. Do not duplicate either loop outside the skill. Preserve their residuals and decision contexts.

## Terminal Classes

- `ready-to-merge`: every Stage 10 condition holds on the current head. Report evidence and state `not merged`.
- `needs-operator`: contract/scope/authority decision, two red verifier passes, invalidated settlement, non-convergence, or exhausted review rounds.
- `blocked-implementation`: implementation or local verification cannot complete; include recovery path.
- `blocked-shipping`: local work is verified but remote/GitHub/push/PR prerequisites failed.
- `paused`: the operator narrowed/stopped the run; state the last verified stage and unverified remainder.

Do not collapse unknown, skipped, partial, or stale evidence into success.
