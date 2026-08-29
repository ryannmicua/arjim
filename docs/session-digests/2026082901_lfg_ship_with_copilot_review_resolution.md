---
lorespec: "0.1"
id: "2026082901"
date: "2026-08-29"
source: "opencode"
topic: "LFG-ship pipeline execution with Copilot review resolution on a GitHub App-authenticated repo"
tags: [lfg-ship, compound-engineering, copilot, github-app, pr-workflow, cli-help]
classification:
  type: technical
  secondary_type: operational
  domains: [compound-engineering, github, cli]
  value: high
trails: [arjim-shipping, arjim-cli]
---

## Session Arc

### Started
User invoked `lfg-ship` on an implementation-ready plan (`docs/plans/2026-08-29-1545-feat-friendly-cli-help-plan.md`) to add friendly CLI help output to `workstream-registration`.

### Pivots
- **Worktree isolation via Paseo**: Runtime detected as Paseo, used `paseo_create_workspace` with worktree isolation. Branch `feat/friendly-cli-help` created at `/home/rgm/.paseo/worktrees/214vu0sz/feat-friendly-cli-help`.
- **Plan already existed**: Skipped ce-plan (step 1) since the plan was already `artifact_readiness: implementation-ready` with `execution: code`.
- **GitHub App token blocks Copilot reviewer**: Phase 2 merge-ready loop stalled — `gh` was authenticated as `rijam-dev[bot]` (app installation token), which cannot add `copilot-pull-request-reviewer[bot]` as a PR reviewer. Copilot review was unreachable.
- **Copilot found 2 findings via direct review**: Despite the reviewer-add failure, Copilot left review comments (2 threads + 2 review bodies). The threads were actionable and fixed.
- **Second Copilot round found 1 more**: Requested regression tests for per-subcommand `--help`. Fixed and resolved.

### Ended
PR #10 merged via squash. Feature branch and worktree cleaned up. All work landed on main.

## Knowledge Objects

### DECISION D1: Use Paseo worktree isolation for lfg-ship
- **Decision**: Create a Paseo workspace with worktree isolation for the shipping pipeline
- **Issue**: Need isolated checkout to avoid dirtying main during multi-step pipeline
- **Positions**: Worktree (safe, isolated) vs current branch (faster, risky)
- **Arguments**: Worktree keeps main clean; pipeline modifies files and pushes; safer for interruption
- **Warrant**: lfg-ship modifies the working tree extensively; isolation prevents accidental damage to the main checkout
- **Qualifier**: always
- **Status**: settled

### DECISION D2: Treat empty argv as implicit help request
- **Decision**: Empty `argv` in `_Parser.parse()` returns `{"help": True}` instead of raising `UsageError`
- **Issue**: Plan R1 says no-args should show welcome guide, but parser raised error
- **Positions**: Keep error (old behavior) vs show help (plan requirement)
- **Arguments**: Plan explicitly requires no-args shows help; error is unhelpful for discoverability
- **Warrant**: The CLI's primary goal is self-documentation; errors without guidance fail that goal
- **Qualifier**: always
- **Status**: settled

### DECISION D3: Short-circuit parser on --help detection
- **Decision**: Break out of token loop immediately when `--help` is detected, before processing remaining flags
- **Issue**: `register --help --label foo` raised "option '--label' requires a value" instead of showing help
- **Positions**: Continue parsing (old) vs short-circuit (new)
- **Arguments**: Help should never fail; remaining flags are irrelevant when help is requested
- **Warrant**: --help is an escape hatch from normal parsing; it should be unconditional
- **Qualifier**: always
- **Status**: settled

### PATTERN P1: GitHub App tokens can't add app reviewers
- **Pattern**: When `gh` is authenticated as a GitHub App installation token (`ghs_` prefix), `gh pr edit --add-reviewer "@copilot"` accepts the request but the reviewer never lands in `reviewRequests`. Retry with the bot login (`copilot-pull-request-reviewer[bot]`) fails with "Could not resolve user".
- **Scope**: Local (GitHub + Copilot reviewer)
- **Workaround**: Authenticate as a user with `pull_requests:write` scope, or request review manually via the GitHub UI
- **Root cause**: GitHub App installation tokens have limited permissions; app-to-app review requests aren't supported through the standard API

### INSIGHT I1: Copilot can leave reviews even when reviewer-add fails
- **Insight**: The `gh pr edit --add-reviewer` failure prevented the bot from being formally added as a reviewer, but Copilot's automated code review still posted comments (2 threads + 2 review bodies) on the PR. The review mechanism is separate from the reviewer-add mechanism.
- **Source**: PR #10 — Copilot left actionable findings despite the add-reviewer failure
- **Confidence**: high (observed directly)

### SOLUTION S1: Fix empty argv and --help short-circuit in CLI parser
- **What was broken**: `_Parser.parse()` raised `UsageError` for empty argv and continued parsing after `--help`, causing spurious errors from trailing flags
- **What fixed it**: Two changes: (1) empty argv returns `{"help": True}` instead of raising, (2) `--help` detection breaks the token loop immediately via `break` instead of `continue`
- **Why the fix works**: Help is treated as an unconditional escape from normal parsing; no validation runs when help is requested
- **Caveats**: The `test_usage_errors_exit_3` test needed updating — `[]` was removed from the error cases and a new `test_empty_argv_shows_help_exit_zero` test was added

### ARTIFACT A1: PR #10 — Friendly CLI help
- **What**: Three commits implementing friendly help output for `workstream-registration` CLI
- **Commits**: `52e7a37` (feat), `373b8a3` (fix), `e14572c` (test)
- **Result**: Squash-merged as `3b20981` on main
- **Files**: `src/workstream_registration/cli.py` (help functions + parser), `tests/python/test_cli.py` (5 new tests)

## Connections

- D1 —[led_to]→ A1 (worktree isolation enabled the shipping pipeline)
- D2 —[led_to]→ S1 (empty-argv fix was required by R1)
- D3 —[led_to]→ S1 (short-circuit was required by review feedback)
- I1 —[informed_by]→ P1 (Copilot review mechanism works despite add-reviewer failure)
- P1 —[informed_by]→ D1 (GitHub App token limitation discovered during Phase 2)

## Trail Updates

- `arjim-shipping`: lfg-ship pipeline executed successfully end-to-end; Phase 2 merge-ready loop blocked by GitHub App token limitation but Copilot review was resolved manually
- `arjim-cli`: CLI help feature shipped; empty argv and --help parsing fixed; regression tests added

## Vocabulary

No new vocabulary terms qualified for CONCEPTS.md.
