---
title: Workstream Registration and Discovery Plan - Review
date: 2026-08-02
type: document-review
source_document: docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md
source_type: unified-plan
source_readiness: implementation-ready
status: complete
review_route: paseo/opencode/opencode-go/deepseek-v4-flash
reasoning: max
proof_url: https://www.proofeditor.ai/d/cqvfmjtk?token=969252ee-3de5-4e03-b701-95acc8971ad5
proof_slug: cqvfmjtk
---

# Workstream Registration and Discovery Plan - Review

## Verdict

The direction is sound, but the plan is not ready for execution yet.

The authority model is clear: the workspace marker remains durable truth, local SQLite state stays replaceable, and all destructive actions stop when their preconditions change. That is aligned with `VISION.md` and gives the implementation a strong safety posture.

Before implementation starts, please resolve the privacy boundary for observation files, reconcile the marker-size limits, and complete the interruption and partial-success result model. These are contract issues. If they are left to the implementer, the code and conformance corpus will make product decisions the plan is supposed to settle.

One mechanical fix was applied during review: the Unit Index now lists the observation schema owned by the results unit and the registration files also touched by the unregister/projection unit.

## Vision check

This work answers the three questions in `VISION.md` as follows:

1. **Which outcome does this make real?** It makes the registration foundation of Outcome 3 real and prepares the safe-management boundary in Outcome 4. It does not yet deliver portfolio awareness, status, or automatic discovery.
2. **What could make it less trustworthy?** Marker data copied into weakly protected observation files, URI values exposed through command-line history, contradictory limits, and unnamed interruption outcomes would all weaken the plan's claim that it never hides uncertainty or mishandles authority.
3. **How will we know it reduced work?** Point-and-read registration and projection rebuild reduce the remembered map for ordinary folders. Proxy workspaces remain the exception: without discovery or a registry path, the operator may still need to remember where the proxy folder lives.

## Review summary

- Applied 1 mechanical fix.
- 12 items need attention: 4 errors and 8 omissions.
- 5 FYI observations do not require a decision.
- No agreement boost was applied. All delegated reviewers used the same user-selected DeepSeek model family, so separate-agent agreement was treated as supporting evidence only.

## Applied fix

- **Unit Index — file ownership now matches the detailed units.** The results unit now lists the marker-observation schema, and the unregister/projection unit now lists the registration implementation and test files it also changes. This was mechanically established by the unit bodies. (coherence and whole-document sweep)

## P1 - Fix before implementation

### Observation files can expose full marker data

**Recommendation: Apply the proposed fix.** An operator can write a full marker snapshot, including possibly credential-bearing record-home URIs, to an arbitrary output path without the protection required for the local projection database.

**Change:** Require owner-only permissions and fail-closed verification for every captured observation file. Add observation-file permission and placement checks to the privacy verification gate, and define retention or deletion after duplicate resolution.

**Basis:** The duplicate-comparison flow stores a validated marker snapshot in an observation envelope, while permission enforcement is currently specified only for the SQLite projection. The no-echo rule does not protect a file already written to a shared or weakly protected location.

Reviewer: security lens. Confidence: 75. Tier: `gated_auto`.

## P2 - Resolve before implementation

### The documented field limits cannot fit inside the total marker limit

**Recommendation: Apply the proposed fix.** A marker using the documented maximum of 32 record homes and 2,048 characters per URI already consumes 65,536 characters before JSON syntax, identity, label, and type fields are added. The schema and raw guard will therefore disagree about documents allowed by the stated maxima.

**Change:** Make the total serialized-marker budget binding, derive compatible per-field limits, and add a worst-case exact-limit fixture that proves all documented maxima compose correctly.

**Basis:** The contract promises a 64 KiB total ceiling while also requiring exact-limit fixtures. The first fixture pass will otherwise force an unplanned contract change.

Reviewer: feasibility. Confidence: 100. Tier: `gated_auto`.

### Retry after parent creation has no canonical envelope state

**Recommendation: Apply the proposed fix.** A crash after `.workstream/` is created but before the marker is created leaves a state the confirmation envelope does not represent, even though interruption at every lifecycle stage is a required test.

**Change:** Define the retry state for an existing marker parent with no marker, specify whether it is a no-transition confirmation variant, and cover it in the protocol transition fixtures.

**Basis:** The current envelope defines only the absent-parent-to-created-parent transition. The occupied-invalid recovery path does not apply because no marker exists.

Reviewer: feasibility. Confidence: 75. Tier: `gated_auto`.

### The result contract omits states used by recovery commands

**Recommendation: Apply the proposed fix.** The closed result schema can be completed without outcomes that later units require, forcing the CLI to extend the contract during implementation.

**Change:** Add `occupied-invalid` and `invalid-marker-resolved` to the portable result vocabulary and conformance scenarios, or explicitly place them in a separate versioned resolution-result surface before contract work begins.

**Basis:** Inspection reports an occupied invalid marker, and successful invalid-marker cleanup reports a resolved outcome. Neither appears in the results unit's enumerated terminal and partial-success cases.

Reviewer: whole-document sweep. Confidence: 75. Tier: `gated_auto`.

### Invalid-marker deletion has no unverified-success outcome

**Recommendation: Apply the proposed fix.** If invalid-marker cleanup deletes the file but absence read-back fails, the implementation has no named outcome or recovery rule. Two implementations can report the same filesystem state differently.

**Change:** Define a partial-success result and exit code for delete-succeeded/read-back-failed, matching unregister's verified-absence completion rule.

**Basis:** Successful read-back is named, but the corresponding failed read-back branch is missing even though the result-review gate requires every terminal and partial-success state.

Reviewer: design lens. Confidence: 75. Tier: `gated_auto`.

### Record-home URIs are exposed through command-line arguments

**Recommendation: Apply the proposed fix.** A URI entered on the command line can remain in shell history and appear in process listings even though diagnostics and logs are forbidden from echoing it.

**Change:** Support a protected stdin or input-file channel for record-home values, make it the documented path for sensitive values, and state the risk of command-line entry.

**Basis:** The settled contract accepts credential-bearing URI components as data and deliberately does not inspect them. That makes transport into the CLI part of the privacy boundary.

Reviewer: security lens. Confidence: 75. Tier: `gated_auto`.

### The closing summary incorrectly defers point-and-read

**Recommendation: Apply the proposed fix.** A reader can conclude that point-and-read registration is later work even though it is the only working v1 entry path and the CLI for it is part of this delivery.

**Change:** State that this plan delivers point-and-read registration and is the dependency for later root-based rediscovery and broader operator workflows.

**Basis:** The detailed Product Contract and implementation units are authoritative; the closing summary is the less specific passage and should match them.

Reviewer: coherence. Confidence: 75. Tier: `gated_auto`.

### Proxy workspaces still require a remembered location

**Recommendation: Decide and document the boundary.** A metadata-incapable workstream can be registered through a proxy, but after local state is lost the operator still has to remember where that proxy folder is because scan and registry entry paths are dormant.

**Change:** Either narrow the work-reduction claim to workspaces whose marker locations are already known, or add a durable, in-scope way to recover proxy locations without turning local projection into authority.

**Basis:** This is not a challenge to the settled proxy decision. It is a gap between that decision and the stated promise that rebuild does not require a remembered map.

Reviewer: adversarial. Confidence: 75. Tier: `manual`.

### Changed-marker duplicate resolution has no named retry loop

**Recommendation: Apply the proposed resolution.** When the marker changes after unregister confirmation, the safety guard correctly stops deletion, but the duplicate remains and the plan does not name the next state.

**Change:** Report an explicit duplicate-persists outcome and require a fresh inspection, unregister draft, and confirmation before retrying.

**Basis:** The guard must remain; weakening it would violate the settled authority decision. The missing piece is the recovery loop after the guard trips.

Reviewer: adversarial. Confidence: 75. Tier: `manual`.

## P3 - Tighten the contract while editing

### Projection outcome prose omits the conflict result

**Recommendation: Apply the proposed fix.** An implementer reading the summary sentence can return only three projection outcomes even though the same unit defines four.

**Change:** List `conflict` alongside linked, registered-unlinked, and projection-failed in the summary of allowed projection results.

Reviewer: coherence. Confidence: 75. Tier: `gated_auto`.

### One concept has two names

**Recommendation: Apply the proposed fix.** Readers may look for a separate result-taxonomy artifact because the Goal Capsule uses that phrase while the rest of the plan uses result vocabulary and reserves taxonomy for warnings and errors.

**Change:** Replace the lone “result taxonomy” occurrence with “result vocabulary.”

Reviewer: coherence. Confidence: 75. Tier: `gated_auto`.

### The conformance-envelope unit understates its scope

**Recommendation: Apply the proposed fix.** The first contract unit can omit fields needed by unregister and duplicate fixtures because its traceability stops before those requirements, even though later dependent units require the envelope to express them.

**Change:** Add the unregister and duplicate requirements, plus the conditional-delete decision, to the conformance-envelope unit's traceability list.

Reviewer: whole-document sweep. Confidence: 75. Tier: `gated_auto`.

## FYI observations

These are verified observations, but they do not need a decision before implementation:

- Requiring operators to type a full 64-character confirmation digest is fail-safe but creates avoidable friction across every destructive command. (feasibility, confidence 50)
- The product contract describes same-identity label changes, but v1 has no edit command; the example currently reads as a schema invariant rather than an operator flow. (design lens, confidence 50)
- The dormant scan and registry paths have no acceptance example proving they remain unavailable in v1. (product lens, confidence 50)
- The example for record-home handling blends malformed-URI warnings with unsupported-scheme capability status, even though the settled decisions distinguish them. (scope guardian, confidence 50)
- Stale-lock recovery depends on a platform-specific process-liveness check that remains unnamed; the lease and recovery command bound the impact. (security lens, confidence 50)

## Residual concerns

- The plan requires owner-only permissions for the projection database and SQLite sidecars but does not identify the standard-library or platform mechanism that will enforce and verify those permissions on the declared filesystem.
- The operator confirms an HMAC digest that cannot be independently recomputed from the redacted preview. This is consistent with the settled confirmation boundary, but its usability and assurance value should be tested together.
- Protocol-transition fixtures and result fixtures share one directory without a stated ownership partition between the two contract units.

## Deferred questions

- Must the marker schema require at least one record home, matching the CLI's required `--record-home` input?
- Does an omitted workspace kind default to `folder`, or must the operator always state it?
- Who owns retention and deletion of captured observation files after duplicate resolution?
- Which platform identity, liveness, synchronization, and ACL APIs define the first supported local-filesystem profile?

## Coverage

| Persona | Status | Findings | Auto | Proposed | Decisions | FYI | Residual |
|---|---:|---:|---:|---:|---:|---:|---:|
| coherence | completed | 3 | 0 | 3 | 0 | 0 | 0 |
| feasibility | completed | 3 | 0 | 2 | 0 | 1 | 3 |
| product lens | completed | 1 | 0 | 0 | 0 | 1 | 3 |
| design lens | completed | 2 | 0 | 1 | 0 | 1 | 2 |
| security lens | completed | 3 | 0 | 2 | 0 | 1 | 2 |
| scope guardian | completed | 1 | 0 | 0 | 0 | 1 | 2 |
| adversarial | completed | 2 | 0 | 0 | 2 | 0 | 3 |
| whole-document sweep | completed | 3 | 1 | 2 | 0 | 0 | 3 |

The design-lens rebuild finding was suppressed because the plan already states that an inaccessible input returns non-success and leaves the previous projection unchanged. Residual and deferred items that merely restated actionable findings were also removed from this report.

## Recommended next action

Resolve the P1 and P2 items in the Product and Planning Contracts, update the conformance envelope and result vocabulary, then run one focused re-review before handing the plan to execution.
