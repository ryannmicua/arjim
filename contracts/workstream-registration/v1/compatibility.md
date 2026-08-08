# Compatibility — Workstream Registration v1

Concrete Python and declared-local-filesystem support profile for the Workstream Registration v1 implementation. Exact patch versions and the tested profile were recorded at implementation start (U6) and finalized at U11 (PLAN:477), when the full conformance corpus passed on this host.

## 1. Pinned dependencies

| Component | Pin | Status |
|---|---|---|
| CPython | 3.14.6 | pinned and tested (U11) |
| `jsonschema` | 4.26.0 | pinned and tested (U11) |
| stdlib `sqlite3` | 3.50.4 (bundled SQLite in CPython 3.14.6) | required; verified present (U6, U11) |

The pins are enforced by `pyproject.toml` (`requires-python = ">=3.14,<3.15"`, `jsonschema==4.26.0`). A CPython build without the stdlib `sqlite3` module fails the conformance runner explicitly (exit 2) and cannot run the projection.

## 2. Tested filesystem profile

- **Tested:** Windows NTFS — this host. The conformance corpus, the integration tests, and the CLI lifecycle E2E run on NTFS.
- **Declared target:** POSIX-compatible local filesystems. POSIX branches (owner-only enforcement via the standard library, liveness checks via `os.kill(pid, 0)`) are implemented fail-closed but are **NOT tested on this host**; POSIX behavior is declared untested, not proven.
- **No claim:** network or synchronized filesystems are not assumed compliant with the lifecycle guarantees (exclusive create, synchronization, cooperative-lock semantics); no claim of compliance is made beyond the tested profile.

## 3. Owner-only enforcement (projection)

- POSIX: standard-library permission APIs (`os.chmod` 0o700/0o600 plus `os.stat` verification).
- Windows: the built-in `icacls` tool (reset inheritance with `/inheritance:r`, grant only the current user, then parse-verify the ACL).
- Fail-closed: when the declared profile's enforcement cannot be established, or pre-existing permissions are weaker, the projection fails closed before use. Applies to the private database directory, the database file, and SQLite sidecars; permissions are verified before use and after creation.

## 4. Stable target handle (identity APIs)

The stable target handle uses platform directory/file identity APIs rather than path strings: the packed `(device, file-index)` pair from `os.stat` (`st_dev`/`st_ino`), which on Windows NTFS carries the volume serial and file index and on POSIX carries `st_dev`/`st_ino`. The `.workstream` parent component is the explicit `ABSENT` sentinel when the parent is absent. When the declared identity APIs are unavailable on the host (missing stat identifiers, empty identity), inspection fails closed (no draft, no confirmation, no write) and reports `stopped`. Recorded and verified at U11 on the tested profile (Windows NTFS).

## 5. Residual limitation — non-cooperating writers

The time-of-check/time-of-use race against non-cooperating external writers is a documented residual limitation, not a claimed atomic guarantee (KTD10, KTD13). Registration's create-only write and unregister's conditional delete are safe against cooperating writers; a non-cooperating external writer can race the check-then-act window, and the contracts disclose rather than hide that risk.

## 6. Disclosed corner — unregister absence read-back failure (2026-08-07 operator decision)

If unregister's absence read-back fails after a successful conditional delete, the result reports `changed-marker-stopped` even though the marker was deleted; this lies within the disclosed non-cooperating-writer residual race (KTD10/PLAN:195) and the operator should re-inspect the workspace. This is the fail-closed outcome within the frozen v1 result vocabulary (PLAN:556): the frozen vocabulary has no delete-succeeded/absence-unverified unregister outcome, and protocol section 11 defines completion only via verified absence (registration-protocol.md section 11; unregister.py module docstring).

## 7. Residual limitation — Windows `icacls` enforcement partial state

The `icacls` grant is applied before parse-verification (`_enforce_owner_only_windows`, `projection.py:199-224`); if verification fails (e.g. unexpected or localized `icacls` output), enforcement fails closed with the path already left inheritance-disabled and owner-only. Recovery is re-running enforcement (idempotent — re-apply + re-verify) or applying `icacls` manually.
