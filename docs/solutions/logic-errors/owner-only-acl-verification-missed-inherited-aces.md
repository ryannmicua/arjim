---
title: Owner-only ACL verification missed inherited ACEs because regex captured only the last flag group
date: 2026-08-07
category: logic-errors
module: src/workstream_registration/projection.py
problem_type: logic_error
component: tooling
symptoms:
  - "Strict owner-only verification silently passes directories whose ACE is inherited: for icacls output like DOMAIN\\user:(I)(OI)(CI)(F), only (F) was matched so the inherited (I) flag never reached the no-inherited-ACE check"
  - "Verification correctness depended on icacls emitting the access mask as the last parenthesized group, because the outer + repeated a capturing group and group(2) held only the final group"
  - "No positive regression test existed for the Windows owner-only verification path, so the inherited-ACE gap shipped undetected"
root_cause: logic_error
resolution_type: code_fix
severity: high
tags: [regex, acl, icacls, windows, security-verification, owner-only, inherited-ace, python]
---

# Windows owner-only ACL verification silently ignored the inherited-ACE flag

## Problem

On Windows, `_verify_owner_only_windows` in `src/workstream_registration/projection.py` could not see the inherited `(I)` flag on an access control entry, because `_ACE_RE` only captured the **last** flag group. A directory whose owner-only enforcement inherited from its parent (ACEs like `DOMAIN\user:(I)(OI)(CI)(F)`) passed the strict verification and returned a false "owner-only" verdict — a silent ACL-security hole in the projection store's fail-closed guarantee. Additionally, matching relied on icacls always emitting the access mask as a trailing parenthesized group (true on the tested Windows host, not guaranteed across icacls versions).

## Symptoms

- `_verify_owner_only_windows` accepted an enforced directory whose ACL contains inherited ACEs (`(I)` flag) when `allow_inherited=False` (the default) — `src/workstream_registration/projection.py:258` never fired.
- The `(I)` flag never appeared in the parsed flag list, so no error surfaced; the failure mode was silent.
- No test exercised the positive happy path (enforce → verify round trip) against a real post-enforce ACL, so the gap was invisible to the suite.

## What Didn't Work

- The original regex `_ACE_RE = re.compile(r"^(.+?):(\([^)]*\))+$")` (pre-`e520045`): the outer `+` repeats a **capturing** group, so `match.group(2)` held only the last repetition. For `DOMAIN\user:(I)(OI)(CI)(F)`, `group(2)` was `(F)` and `_ACE_GROUP_RE.findall(match.group(2))` yielded `["F"]` — the `(I)`, `(OI)`, and `(CI)` flags were discarded before the inherited check at `src/workstream_registration/projection.py:258` could see them. Verified with a one-liner against the old regex: `group(2) == '(F)'`, `findall == ['F']`.
- Relying on icacls emitting the access mask as a trailing paren group (`(F)`) — paren-wrapped masks held on the tested Windows host but are an output-format assumption, not an icacls contract.

## Solution

Fixed in commit `e520045` (`fix(python): capture all ACE flag groups in owner-only verification (P1-1)`; on branch `feat/workstream-registration`, not yet merged to `main` as of this writing — no PR opened yet): make the inner group non-capturing so the outer group captures the **entire** flag sequence (`src/workstream_registration/projection.py:103`).

Before:

```python
_ACE_RE = re.compile(r"^(.+?):(\([^)]*\))+$")
```

After:

```python
_ACE_RE = re.compile(r"^(.+?):((?:\([^)]*\))+)$")
```

Behavior for `DOMAIN\user:(I)(OI)(CI)(F)`: `group(2)` is now the full `(I)(OI)(CI)(F)` and `_ACE_GROUP_RE.findall(match.group(2))` yields `['I', 'OI', 'CI', 'F']`, so the check at `src/workstream_registration/projection.py:258` fires.

Two regression tests added in `TestOwnerOnlyEnforcement` (`tests/python/test_projection.py:296`):

- `test_verify_round_trip_on_real_enforced_owner_only_directory` (`tests/python/test_projection.py:325`) — calls `proj._enforce_owner_only_windows(directory)` then `proj._verify_owner_only_windows(directory)` on a real directory, exercising the previously untested positive happy path.
- `test_inherited_ace_detected_and_gated_by_allow_inherited` (`tests/python/test_projection.py:331`) — monkeypatches `subprocess.run` with fake icacls output `{principal}:(I)(OI)(CI)(F)`; asserts strict default raises `ProjectionStoreError` and `allow_inherited=True` accepts. This test fails against the old regex — a genuine regression test.

Independently verified GREEN: pytest 362 pass, conformance 87/87.

## Why This Works

The bug was a classic capturing-group repetition mistake: in `(\([^)]*\))+`, each iteration overwrites the group, leaving only the final match. Switching the inner group to non-capturing (`(?:...)`) makes the outer `(...)` hold the whole repeated sequence, so all flag groups survive for `_ACE_GROUP_RE` to enumerate. The inherited check then sees `I` and rejects the ACL under the strict default, restoring the fail-closed invariant: verification no longer depends on which flag happens to be last, and the tokenizer now tolerates any paren-group run — matching icacls output shape rather than one sampled host's output.

## Prevention

- Treat `+`/`*` applied to a capturing group as a code smell: if you need all repetitions, the repeated part must be non-capturing and the whole repetition must be wrapped in one outer group.
- When parsing external command output (icacls, etc.), add a fake-output unit test that pins the parser to the format contract rather than trusting one sampled host.
- Keep the positive happy path tested: enforce → verify round trips on a real resource, not just negative/failure cases.

## Related Issues

- `tests/python/test_projection.py:351` `test_verification_before_use_fails_closed_on_weaker_pre_existing` — existing fail-closed verification test for a weaker pre-existing ACL (the same `ProjectionStoreError` path).
- The neighboring commit `564e4f0` (`fix(python): map projection INSERT race on captured target to conflict (P1-2)`; same branch, same as-of note) — the second fix in the same P1 hardening pass.
