---
title: "GitHub App Tokens Cannot Add Copilot as PR Reviewer"
date: "2026-08-29"
last_updated: "2026-08-29"
category: tooling-decisions
module: workstream-registration
problem_type: tooling_decision
component: github-workflow
severity: medium
applies_when:
  - requesting Copilot code review from a GitHub App-authenticated CLI
  - running lfg-ship Phase 2 merge-ready loop with app tokens
  - gh CLI authenticated as GitHub App installation token
tags:
  - github-app
  - copilot
  - code-review
  - gh-cli
  - lfg-ship
  - tooling-decision
---

# GitHub App Tokens Cannot Add Copilot as PR Reviewer

## Context

The lfg-ship pipeline's Phase 2 merge-ready loop requires requesting a Copilot code review on the PR via `gh pr edit <N> --add-reviewer "@copilot"`. On a repo where `gh` is authenticated as a GitHub App installation token (identified by the `ghs_` prefix), this request silently fails — GitHub accepts the API call but the reviewer never appears in `reviewRequests`.

## Root Cause

GitHub App installation tokens have scoped permissions that do not include adding other GitHub Apps as PR reviewers. The `copilot-pull-request-reviewer[bot]` is itself a GitHub App. The standard PR reviewer API (`POST /repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers`) expects a user or team login, and app-to-app review requests are not supported through this mechanism.

Evidence:
1. `gh pr edit 10 --add-reviewer "@copilot"` — accepted by API, but GraphQL query returns empty `reviewRequests`
2. `gh pr edit 10 --add-reviewer "copilot-pull-request-reviewer[bot]"` — returns "Could not resolve user with login"
3. `gh auth status` shows authentication as `rijam-dev[bot]` with `ghs_` token prefix

## Solution

**When `gh` is app-authenticated, Copilot reviewer-add is unreachable.** Two workarounds:

1. **Authenticate as a user** with a PAT that has `pull_requests:write` scope, then the add-reviewer call works normally
2. **Request review via the GitHub UI** — Copilot's automated review still posts findings even when the bot isn't formally added as a reviewer (the review mechanism is separate from the reviewer-add mechanism)

**Key insight**: Copilot can leave review comments on a PR even when the add-reviewer call fails. The automated code review runs independently of the formal reviewer-add flow.

## Prevention

When setting up lfg-ship or ce-babysit-pr in an environment where `gh` uses app tokens:
- Check `gh auth status` before Phase 2
- If the token prefix is `ghs_`, skip the automated Copilot review request and rely on Copilot's automatic review (which posts findings without formal reviewer-add)
- Alternatively, set up a user PAT for `gh` authentication in shipping workflows
