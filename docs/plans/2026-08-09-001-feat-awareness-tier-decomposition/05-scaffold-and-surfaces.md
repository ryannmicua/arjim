---
title: AT-05 - Scaffold Missing Declarations and Publish Awareness Surfaces
type: vertical-slice-plan
date: 2026-08-10
source_units: [U11, U8]
depends_on: [AT-04]
---

# AT-05 - Scaffold Missing Declarations and Publish Awareness Surfaces

## Objective and Outcome

Complete the operator-facing v1: safely create only missing referenced declarations, then expose configure, inventory, portfolio, needs-me, changed, report, rebuild, and scaffold through the awareness-owned on-demand CLI with shared-observation rendering and references-only durable reports.

## Split/Regroup Decision

The source sequence places U11 after U7 and before U8 because U7 surfaces the missing-declaration offer and U8 must wire the complete command set. This slice preserves that placement exactly: implement and verify U11 first, then implement U8. Regrouping closes the operator journey from a reported declaration gap to a safely scaffolded declaration and refreshed awareness answer.

## Source Traceability

| Source | Coverage |
|---|---|
| U-IDs | U11 first, then U8 |
| Requirements | R3/R3b surface reuse, R5-R8, R10-R11, R13-R20, with primary ownership of R14b and R16-R18 |
| KTDs | KTD1 shared lock, KTD10, KTD13-KTD16, KTD20; surface enforcement of KTD8-KTD9 and KTD17 |
| Flow | F2 publication half; F1 configure command remains available |
| Acceptance examples | AE5 and AE12 rendering halves; AE13-AE16 surface/scaffold behavior; rendering portions of AE1-AE3 and AE7-AE11 |

## Dependencies

- AT-04 must pass completely.
- Within this slice, the U11 scaffold gate must pass before any U8 wiring begins.
- AT-02 configure command and AT-03 inventory handlers are extended, not replaced.

## Files Likely Touched

- `src/awareness/scaffold.py`
- `contracts/awareness/v1/declaration.schema.json`
- `tests/python/test_awareness_scaffold.py`
- `tests/contracts/awareness/scaffold/canary/canary-scaffold-output.json`
- `tests/contracts/awareness/scaffold/canary/canary-scaffold-input.json`
- `tests/contracts/awareness/scaffold/transitions/result-scaffolded.json`
- `tests/contracts/awareness/scaffold/transitions/result-declaration-exists.json`
- `src/awareness/cli.py`
- `src/awareness/report.py`
- `src/awareness/__main__.py`
- `pyproject.toml`
- `tests/python/test_awareness_cli.py`
- `tests/python/test_awareness_report.py`
- `tests/contracts/awareness/cli/canary/canary-cli-output.json`
- `tests/contracts/awareness/cli/transitions/result-portfolio.json`
- `tests/contracts/awareness/cli/transitions/result-answered-with-gaps.json`
- `tests/contracts/awareness/cli/transitions/result-rebuilt.json`

## Implementation Approach

### U11 portion: missing-only declarations

1. Define the closed two-kind declaration contract with bounded attribution.
2. Permit only workspace-contained purpose or decision-record declaration targets authorized by conventions.
3. Capture and revalidate workspace/destination identities, reject symlink/reparse substitution, and use the shared registration lock.
4. Render exact draft content and destination, obtain exact confirmation, then exclusive-create/fsync/reopen/validate/identity-compare/read-back.
5. Return `declaration-exists` without opening for write when the target exists at confirmation or pre-write revalidation. Provide no update path.
6. Purpose is exact operator input or the source-plan empty placeholder. Never generate purpose prose.
7. Apply exact KTD13 scaffold outcomes, exits, bounded attribution, and privacy handling.

### U8 portion: CLI and reports

8. Extend the awareness-owned parser without modifying registration CLI code. Preserve repeatable `--path` and `--json` behavior.
9. Expose exactly `awareness {configure,portfolio,needs-me,changed,report,rebuild,inventory add|remove|list,scaffold}`.
10. Consume one AT-04 pending observation for every requested view. Build in-memory renderings before finalization and finalize once.
11. Write/fsync a new immutable timestamped Markdown report without overwrite; update `latest.md` atomically only after the durable report exists.
12. Keep report contents references-only. Bounded declaration values may appear only in live CLI read-through.
13. On report creation/fsync failure, return `report-write-failed` and leave prior source state and baselines logically unchanged.
14. Render identical per-source and aggregate states across CLI, JSON, and report metadata.
15. Implement the complete separate awareness outcome-to-exit map and console entry point.
16. Retain on-demand-only structure; introduce no scheduler/background mechanism.

## Test Scenarios

1. AE16 scaffold: confirmed missing declaration is created exclusive-create and read back exactly.
2. Existing declaration remains byte-identical and returns `declaration-exists`; no update prompt exists.
3. Outside-workspace path and identity replacement return exact KTD13 failures with no write.
4. Operator purpose and empty placeholder receive the correct bounded attribution; no generated prose path exists.
5. Concurrent register/configure/scaffold operations serialize through the shared lock.
6. Scaffold cancellation returns exit 2 and writes nothing.
7. AE13: CLI and report metadata derive from one observation and expose the same per-source and aggregate states.
8. Report regeneration creates a new timestamped file and updates `latest.md`; collision handling does not overwrite prior immutable reports.
9. AE5 rendering: portfolio surfaces the recommendation-revision gap and its defer, knowingly-accept, and R3b re-settle resolutions distinctly from a current recommendation state.
10. AE12 rendering: unsupported conventions produce `answered-with-gaps` exit 0, aggregate `unconfigured`, the stable gap code, and no per-source status; configure still exits 3.
11. AE15: live bounded values never appear in timestamped or latest report bytes.
12. Repeatable `--path` selects only supplied paths and leaves inventory unchanged.
13. Empty inventory is an honest `answered-with-gaps` exit-0 result.
14. `report` without paths covers inventory; with paths it covers only the override.
15. Report failure leaves source rows and baselines unchanged; multiple renders finalize once.
16. Exact KTD13 outcomes and exits apply across configure, inventory, scaffold, view/state, and unexpected-error paths.
17. The complete privacy-origin behavior owned by scaffold and surfaces reaches no prohibited sink; branch rendering follows R19's narrow exception.
18. Structural inspection finds no scheduler, timer, daemon, background thread, or OS scheduled-task registration.
19. Protected registration files remain unchanged.

## Verification Commands

Run U11 before U8:

| Command | Expected exit | Evidence |
|---|---:|---|
| `python -m pytest tests/python/test_awareness_scaffold.py -v` | 0 | Missing-only authorization, shared lock, containment, identity, confirmation, read-back, attribution, outcomes, and privacy pass. |
| `python -m pytest tests/python/test_awareness_cli.py tests/python/test_awareness_report.py -v` | 0 | Full CLI wiring, shared observation, outcome/exit map, references-only reports, repeatable paths, report failure boundary, and surface privacy pass. |

## Stop and Escalation Conditions

- Stop if U8 work begins before U11 is green.
- Stop if scaffolding would update an existing declaration, generate purpose prose, write outside the workspace, or bypass confirmation/shared locking/read-back.
- Stop if a report needs copied declaration values, source free text, filenames, author identity, or other non-allow-listed data.
- Stop if report failure advances state or if different surfaces derive different states.
- Stop if top-level wiring requires modifying any protected registration file or registration exit table.
- Stop if any background execution mechanism appears necessary.

## Out of Scope

- Editing or restoring existing declarations.
- Scheduled/proactive delivery, notifications, or background processing.
- HTML or mutable report formats; reports remain timestamped Markdown plus `latest.md`.
- Lifecycle state, dedicated current-status view, external connectors, non-git delta, and action-tier writes.
