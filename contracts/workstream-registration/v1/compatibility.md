# Compatibility — Workstream Registration v1

Concrete Python and declared-local-filesystem support profile for the Workstream Registration v1 implementation. Placeholders marked **[U11]** are finalized by unit U11, when the exact patches and the tested profile are recorded with concrete values (PLAN:477). The exact patch versions are pinned at implementation start (U6).

## 1. Pinned dependencies

| Component | Pin | Status |
|---|---|---|
| CPython | 3.14.x — exact patch recorded at U6 **[U11 finalizes]** | placeholder |
| `jsonschema` | 4.26.x — exact patch recorded at U6 **[U11 finalizes]** | placeholder |
| stdlib `sqlite3` | Standard library; required. A CPython build without `sqlite3` fails setup | required (U6) |

## 2. Tested filesystem profile

- **Tested:** Windows NTFS — this host. The conformance corpus and integration tests run on NTFS.
- **Declared target:** POSIX-compatible local filesystems. POSIX branches (owner-only enforcement via the standard library, liveness checks) are implemented fail-closed but are **NOT tested on this host**; POSIX behavior is declared untested, not proven.
- **No claim:** network or synchronized filesystems are not assumed compliant with the lifecycle guarantees (exclusive create, synchronization, cooperative-lock semantics); no claim of compliance is made beyond the tested profile.

## 3. Owner-only enforcement (projection)

- POSIX: standard-library permission APIs.
- Windows: the built-in `icacls` tool.
- Fail-closed: when the declared profile's enforcement cannot be established, or pre-existing permissions are weaker, the projection fails closed before use. Applies to the private database directory, the database file, and SQLite sidecars; permissions are verified before use and after creation.

## 4. Stable target handle (identity APIs)

The stable target handle uses platform directory/file identity APIs rather than path strings. When the declared identity APIs are unavailable on the host, inspection fails closed (no draft, no confirmation, no write) and reports `stopped`. The supported identity APIs per profile are recorded here at U11 **[U11]**.

## 5. Residual limitation — non-cooperating writers

The time-of-check/time-of-use race against non-cooperating external writers is a documented residual limitation, not a claimed atomic guarantee (KTD10, KTD13). Registration's create-only write and unregister's conditional delete are safe against cooperating writers; a non-cooperating external writer can race the check-then-act window, and the contracts disclose rather than hide that risk.
