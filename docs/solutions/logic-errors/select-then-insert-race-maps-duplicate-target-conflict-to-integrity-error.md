---
title: SELECT-then-INSERT race on a captured target degraded duplicate-conflict to projection-failed; IntegrityError branch restores conflict
date: 2026-08-07
category: logic-errors
module: src/workstream_registration/projection.py
problem_type: logic_error
component: database
symptoms:
  - "Under two concurrent writers (separate processes/connections) registering different identities on the same target_handle, the second writer's INSERT hits the unique index idx_projection_target_handle and raises sqlite3.IntegrityError instead of returning the conflict status"
  - "Before commit 564e4f0 the IntegrityError fell through `except Exception:` in Projection.update, mapping the duplicate-target case to STATUS_PROJECTION_FAILED - degrading the contract's only in-scope duplicate signal from conflict to a generic failure"
  - "The degradation was silent: the projection row stays untouched and no error surfaces, so callers cannot distinguish a duplicate target from a genuine store failure"
  - "No test exercised the SELECT-then-INSERT race window; only the single-process SELECT-path conflict (different identity already visible) was covered"
root_cause: logic_error
resolution_type: code_fix
severity: medium
tags: [sqlite, race-condition, toctou, integrityerror, unique-index, exception-mapping, conflict-status]
---

# Map the projection INSERT race on a captured target to conflict instead of projection-failed

## Problem

`Projection.update` detects duplicate-target conflicts with a SELECT-then-INSERT pattern, which is race-free within a single process (the `BEGIN IMMEDIATE` write lock in `_run_transaction` serializes it — `src/workstream_registration/projection.py:409`) but not across two connections or processes. When two writers both pass the SELECT and the loser's INSERT then hits the UNIQUE index on `target_handle` alone, the resulting `sqlite3.IntegrityError` fell through `except Exception:` and was mapped to `STATUS_PROJECTION_FAILED` — degrading the contract's only in-scope duplicate signal from `conflict` to a generic failure. Fix: catch `sqlite3.IntegrityError` between the `_ConflictOnTarget` branch and the generic branch (commit `564e4f0`, "fix(python): map projection INSERT race on captured target to conflict (P1-2)").

## Symptoms

- Under multi-process (or multi-connection) load, the loser of a duplicate-target race gets `status = "projection-failed"` instead of `status = "conflict"` — the caller cannot tell "another identity already owns this target" (an expected, reportable outcome) apart from a store/enforcement failure.
- Pre-fix, the SQLite error surfaced verbatim as `sqlite3.IntegrityError: UNIQUE constraint failed: projection.target_handle` (reproduced empirically by the verifier) before being swallowed into the generic branch.

## What Didn't Work

- **Reading the SELECT-then-INSERT as a plain race inside one process.** This is wrong: `_run_transaction` starts every transaction with `BEGIN IMMEDIATE` (`src/workstream_registration/projection.py:409`), which takes the write lock up front and serializes all projection writes within the process. There is no window for a same-process race; the gap only exists across distinct connections/processes that do not share the transaction lock (session history).
- **Treating the audit's suggested fix as suspect or over-broad.** The audit (ce-code-review by MiniMax-M3) flagged P1-2 as latent under multi-process load and proposed exactly this fix — catch `IntegrityError`. The fix worker verified the audit's reasoning held verbatim: the PK conflict is absorbed by `ON CONFLICT(identity, target_handle)`, so the only remaining constraint this INSERT can violate is the unique `target_handle` index, i.e. precisely the different-identity-on-one-captured-target case in scope as a conflict. No deviation was needed for this P1 (the only test-mock deviation in the run was in the *other* P1, the icacls regex test, which needed a real `whoami` dispatch — not this one) (session history).

## Solution

Add a dedicated `except sqlite3.IntegrityError:` branch between the `_ConflictOnTarget` branch and the generic branch, returning the same conflict result shape as the in-process path (identity, target_handle, ordinal):

```python
# before (src/workstream_registration/projection.py:465-485)
except _ConflictOnTarget:
    return ProjectionResult(status=STATUS_CONFLICT, identity=identity,
                            target_handle=target, ordinal=input.ordinal)
except Exception:
    return ProjectionResult(status=STATUS_PROJECTION_FAILED, identity=identity,
                            target_handle=target, ordinal=input.ordinal)

# after (commit 564e4f0)
except _ConflictOnTarget:
    return ProjectionResult(status=STATUS_CONFLICT, identity=identity,
                            target_handle=target, ordinal=input.ordinal)
except sqlite3.IntegrityError:
    return ProjectionResult(status=STATUS_CONFLICT, identity=identity,
                            target_handle=target, ordinal=input.ordinal)
except Exception:
    return ProjectionResult(status=STATUS_PROJECTION_FAILED, identity=identity,
                            target_handle=target, ordinal=input.ordinal)
```

The upsert itself is unchanged: SELECT identity by `target_handle` (`src/workstream_registration/projection.py:438-441`), raise `_ConflictOnTarget` on a different identity (`:442-443`), else `INSERT ... ON CONFLICT(identity, target_handle) DO UPDATE` (`:444-462`).

Regression test `test_race_between_select_and_insert_maps_to_conflict` (`tests/python/test_projection.py:204-239`, class `TestUpdateBoundary`) reproduces the cross-connection race faithfully in-process:

1. Writer A links the target on its own connection (`:209-210`).
2. `_BlindSelect` (a monkeypatched `proj.sqlite3.connect`, `:213-231`) wraps the connection and blinds writer B's `SELECT identity FROM projection` by returning an empty result (`:220-223`) — so B's SELECT misses A's row and the in-process `_ConflictOnTarget` path cannot fire.
3. B's *real* INSERT then hits the UNIQUE index `idx_projection_target_handle` (`src/workstream_registration/projection.py:386-388`) and raises a genuine `sqlite3.IntegrityError` — the exact cross-process failure, exercised end-to-end.
4. Asserts `status == "conflict"` and the result identity (`:234-235`), then after `monkeypatch.undo()` confirms A's row is untouched — only one row, still A's identity (`:237-239`).

Verified GREEN by MiniMax-M3: 362 pytest, 87/87, exception-chain order confirmed correct (`_ConflictOnTarget` is a plain `Exception` subclass at `src/workstream_registration/projection.py:653`, not an `IntegrityError`, so the branch order matters and is right: `_ConflictOnTarget` first, `IntegrityError` second, generic last).

## Why This Works

The SELECT is only an optimization/pre-check; the database's unique constraint is the real arbiter. Because the INSERT targets the composite PK `(identity, target_handle)` (`src/workstream_registration/projection.py:382`) with `ON CONFLICT(identity, target_handle) DO UPDATE`, a same-identity re-link never raises — the only constraint left that this INSERT can trip is the unique index `idx_projection_target_handle` on `target_handle` alone (`src/workstream_registration/projection.py:386-388`). A violation of that index *is* the in-scope conflict signal: a different identity on one captured target. So mapping every `IntegrityError` from this INSERT to `STATUS_CONFLICT` is unconditional without being over-broad:

- `sqlite3.OperationalError` (e.g. a locked/broken store) still falls through to `STATUS_PROJECTION_FAILED` — confirmed by the verifier, so a genuinely broken store never masquerades as a duplicate conflict.
- The in-process conflict path is untouched: `_ConflictOnTarget` (raised at `:443`, caught at `:465`) still fires first for the same process, and the existing tests `test_conflict_for_different_identity_on_one_target` and `test_conflict_does_not_touch_the_marker` (`tests/python/test_projection.py:180-202`) still pass — the marker and existing rows are never modified on conflict.
- Both conflict paths now return byte-identical result shapes (status, identity, target_handle, ordinal), so callers and downstream tests cannot distinguish the race from the sequential case — which is exactly the point.

## Prevention

- The regression test `test_race_between_select_and_insert_maps_to_conflict` (`tests/python/test_projection.py:204-239`) is the guardrail: it forces the INSERT to be the conflict detector by blinding the SELECT, so any future reordering of the exception chain or removal of the `IntegrityError` branch fails the suite.
- Keep the exception chain in this order: narrowest (in-process `_ConflictOnTarget`) → `sqlite3.IntegrityError` → generic `Exception`. Both narrow branches must return the identical conflict result shape.
- When adding new `NOT NULL`/constraint columns to `projection`, re-check this mapping: a new constraint the INSERT could violate would no longer be covered by the "only remaining constraint is the unique target_handle index" argument, and the `IntegrityError` branch would then be over-broad (see Related Issues — non-blocking note).

## Related Issues

- Sibling fix from the same hardening pass: [owner-only ACL verification missed inherited ACEs (P1-1)](../logic-errors/owner-only-acl-verification-missed-inherited-aces.md) — commit `e520045`, same module, different bug shape (regex capturing-group vs TOCTOU race).
- Plan defers true cross-instance duplicate detection (PLAN:542); this change hardens the mapping only, it does not remove the need for a plan-level decision on inter-process coordination.
- Non-blocking theoretical concern (verifier): a future caller passing `None` for a `NOT NULL` column would map the resulting NOT NULL violation to `conflict` rather than `projection-failed`. No current call path does this; revisit if inputs ever become nullable.
- In-process conflict behavior and marker safety: `test_conflict_for_different_identity_on_one_target` and `test_conflict_does_not_touch_the_marker` (`tests/python/test_projection.py:180-202`).
