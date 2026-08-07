"""Replaceable local link projection for Workstream Registration v1 (U10).

Implements PLAN:463: a transactional SQLite-backed projection of registered
workspaces under a private, owner-only directory in per-user application data.
The projection is replaceable device-local routing state only and never
becomes registration authority (PLAN:511; CONCEPTS.md:50): deleting the
projection database never unregisters anything, and a rebuild begins from the
markers.

Boundary (PLAN:463): ``Projection.update(input) -> ProjectionResult`` with the
idempotency key ``(identity, target_handle)``. Same-key updates replace the
local routing path and the deterministic input ordinal; a conflicting identity
for one captured target returns ``conflict`` without changing the marker (the
only in-scope duplicate signal, PLAN:542). Statuses are ``linked``,
``registered-unlinked``, ``projection-failed``, ``conflict``.

Schema (PLAN:463): marker identity, label, marker version, target handle, local
routing path/state, and deterministic input ordinal only. The schema has no URI
field at all — record-source URI content and credentials are never copied
(schema- and code-level exclusion; the no-echo rule KTD9, PLAN:194).

Owner-only enforcement (PLAN:463, 553; PLAN:170): the standard library on
POSIX (``os.chmod`` 0o700/0o600 + ``os.stat`` verification) and the built-in
``icacls`` tool on Windows (reset inheritance and grant only the current user,
then parse-verify the ACL). The store directory, the database file, and the
SQLite WAL/shm/journal sidecars are verified before use and after creation,
and the projection fails closed — raising the bounded
:class:`ProjectionStoreError` (mapped to ``projection-failed`` by
:meth:`Projection.update`) — when the declared profile's enforcement cannot be
established or pre-existing permissions are weaker. Sidecars are covered by
the directory-level ACL inheritance on Windows and are re-chmodded on POSIX.

Rebuild (PLAN:463): :meth:`Projection.rebuild` is a transactional replacement
from an explicit ordered list of workspace paths: one path means one
workspace, there is no recursive traversal, symlink aliases deduplicate by
target handle while retaining the first input's ordinal, stale entries are
repaired inside the same transaction, and any inaccessible or invalid root
returns a non-success leaving the previous projection unchanged. The retained
ordinal and input-order routing are exposed in the :class:`RebuildResult`.
Automatic discovery remains deferred (PLAN:463).

The projection failure mapping is owned by U10 (PLAN:451, 453): the real hook
is wired through ``registration.install_default_projection_hook`` (U11 calls
it at startup), and an unset hook keeps the U9 ``registered-unlinked``/stopped
mapping.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import stat
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from workstream_registration import filesystem as fs
from workstream_registration import raw_guard as rg
from workstream_registration import validation as vd
from workstream_registration.registration import ProjectionResult

if TYPE_CHECKING:
    from workstream_registration.registration import ProjectionInput

__all__ = [
    "DEFAULT_STORE_RELPATH",
    "ENV_STORE_DIR",
    "PROJECTION_DB_FILENAME",
    "STATUS_CONFLICT",
    "STATUS_LINKED",
    "STATUS_PROJECTION_FAILED",
    "STATUS_REBUILD_FAILED",
    "STATUS_REBUILT",
    "STATUS_UNLINKED",
    "Projection",
    "ProjectionEntry",
    "ProjectionStoreError",
    "RebuildResult",
    "default_store_dir",
]

ENV_STORE_DIR = "WORKSTREAM_REGISTRATION_STORE_DIR"
DEFAULT_STORE_RELPATH = "workstream-registration/projection"
PROJECTION_DB_FILENAME = "projection.db"

STATUS_LINKED = "linked"
STATUS_UNLINKED = "registered-unlinked"
STATUS_PROJECTION_FAILED = "projection-failed"
STATUS_CONFLICT = "conflict"
STATUS_REBUILT = "rebuilt"
STATUS_REBUILD_FAILED = "failed"

_SCHEMA_VERSION = 1
_STATE_LINKED = "linked"

_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")

_ACE_RE = re.compile(r"^(.+?):((?:\([^)]*\))+)$")
_ACE_GROUP_RE = re.compile(r"\(([^)]*)\)")

_ICACLS_TIMEOUT_SECONDS = 60
_ABSENCE_VERIFY_INTERVAL = 0.05


class ProjectionStoreError(RuntimeError):
    """Bounded projection-store failure: enforcement, verification, or storage.

    Raised for storage/enforcement conditions that must fail closed; never
    carries record-source URI content or secrets.
    """


@dataclass(frozen=True)
class ProjectionEntry:
    """One projection row in stable dict form (list_projection/query helpers)."""

    identity: str
    label: str
    marker_version: str
    target_handle: str
    workspace_path: str
    state: str
    ordinal: int
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "label": self.label,
            "marker_version": self.marker_version,
            "target_handle": self.target_handle,
            "workspace_path": self.workspace_path,
            "state": self.state,
            "ordinal": self.ordinal,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class RebuildResult:
    """Transactional rebuild outcome (PLAN:463): retained ordinal and
    input-order routing are exposed in ``entries``."""

    status: str
    entries: tuple[dict[str, Any], ...] = ()
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "entries": list(self.entries),
            "detail": self.detail,
        }


def default_store_dir() -> Path:
    """Per-user application data store location (PLAN:463), overridable by the
    ``WORKSTREAM_REGISTRATION_STORE_DIR`` environment variable (tests)."""
    override = os.environ.get(ENV_STORE_DIR)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / DEFAULT_STORE_RELPATH
        return Path.home() / "AppData" / "Local" / DEFAULT_STORE_RELPATH
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / DEFAULT_STORE_RELPATH
    return Path.home() / ".local" / "share" / DEFAULT_STORE_RELPATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _windows_principal() -> str:
    """Canonical current-user principal (``domain\\user`` via ``whoami``)."""
    try:
        proc = subprocess.run(
            ["whoami"], capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    domain = os.environ.get("USERDOMAIN") or os.environ.get("COMPUTERNAME") or ""
    user = os.environ.get("USERNAME") or ""
    if domain and user:
        return f"{domain}\\{user}"
    return user


def _enforce_owner_only_windows(path: Path) -> None:
    """Reset inheritance and grant only the current user (icacls), then verify.

    ``(OI)(CI)`` on directories makes the SQLite sidecars inherit the
    owner-only ACL (PLAN:463; compatibility.md section 3).
    """
    principal = _windows_principal()
    if not principal:
        raise ProjectionStoreError(
            "owner-only enforcement failed: cannot resolve the current user"
        )
    flags = "(OI)(CI)F" if path.is_dir() else "F"
    command = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{principal}:{flags}"]
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, timeout=_ICACLS_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectionStoreError(
            "owner-only enforcement failed: icacls unavailable"
        ) from exc
    if proc.returncode != 0:
        raise ProjectionStoreError(
            "owner-only enforcement failed: icacls rejected the grant"
        )
    _verify_owner_only_windows(path)


def _verify_owner_only_windows(path: Path, *, allow_inherited: bool = False) -> None:
    """Parse ``icacls <path>`` and fail closed unless only the current user
    holds full control.

    The database directory and database are enforced with ``/inheritance:r``
    and must carry no inherited ACE (strict). SQLite sidecars legitimately
    inherit the owner-only directory ACL — the plan's stated mechanism
    (PLAN:463: "icacls/chmod the directory so sidecars inherit") — so their
    inherited ACEs are accepted as long as only the current user is granted.
    """
    principal = _windows_principal()
    allowed = {principal.lower()}
    if "\\" not in principal:
        allowed.add(principal.lower())
    try:
        proc = subprocess.run(
            ["icacls", str(path)], capture_output=True, text=True, timeout=_ICACLS_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectionStoreError(
            "owner-only verification failed: icacls unavailable"
        ) from exc
    if proc.returncode != 0:
        raise ProjectionStoreError("owner-only verification failed: icacls rejected")
    grants: list[str] = []
    for line in proc.stdout.splitlines():
        for token in line.strip().split():
            match = _ACE_RE.match(token)
            if match is None:
                continue  # path header line or summary text
            groups = _ACE_GROUP_RE.findall(match.group(2))
            if "I" in groups and not allow_inherited:
                raise ProjectionStoreError(
                    f"owner-only verification failed: inherited ACE on {path}"
                )
            if "F" not in groups:
                raise ProjectionStoreError(
                    f"owner-only verification failed: non-owner grant on {path}"
                )
            grants.append(match.group(1))
    if not grants:
        raise ProjectionStoreError(
            f"owner-only verification failed: no access control entries on {path}"
        )
    for grant in grants:
        if grant.lower() not in allowed:
            raise ProjectionStoreError(
                f"owner-only verification failed: {grant} can access {path}"
            )


def _enforce_owner_only_posix(path: Path) -> None:
    mode = 0o700 if path.is_dir() else 0o600
    try:
        os.chmod(path, mode)
    except OSError as exc:
        raise ProjectionStoreError("owner-only enforcement failed: chmod") from exc
    _verify_owner_only_posix(path)


def _verify_owner_only_posix(path: Path) -> None:
    try:
        st = os.stat(path)
    except OSError as exc:
        raise ProjectionStoreError("owner-only verification failed: stat") from exc
    if st.st_uid != os.getuid():
        raise ProjectionStoreError("owner-only verification failed: wrong owner")
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise ProjectionStoreError(
            "owner-only verification failed: group or other access bits set"
        )


def _enforce_owner_only(path: Path) -> None:
    if os.name == "nt":
        _enforce_owner_only_windows(path)
    else:
        _enforce_owner_only_posix(path)


def _verify_owner_only(path: Path) -> None:
    if os.name == "nt":
        _verify_owner_only_windows(path)
    else:
        _verify_owner_only_posix(path)


def _bounded_detail(path: Path, exc: Exception) -> str:
    """Bounded rebuild failure detail: affected local path + failure class
    only; never marker content, URI content, or secrets (KTD12, PLAN:197)."""
    name = type(exc).__name__
    return f"rebuild root failed: {path}: {name}"


class Projection:
    """Transactional SQLite projection with owner-only enforcement.

    The store directory is resolved from ``store_dir``, then the
    ``WORKSTREAM_REGISTRATION_STORE_DIR`` environment variable, then the
    per-user application-data default. Construction is side-effect free; the
    owner-only directory and database are established lazily on first use and
    verified before every use (PLAN:463).
    """

    def __init__(self, store_dir: Path | None = None) -> None:
        self._store_dir = Path(store_dir) if store_dir is not None else default_store_dir()

    @property
    def store_dir(self) -> Path:
        return self._store_dir

    @property
    def db_path(self) -> Path:
        return self._store_dir / PROJECTION_DB_FILENAME

    # -- owner-only lifecycle -------------------------------------------------

    def _ensure_store(self) -> Path:
        store = self._store_dir
        if not store.exists():
            try:
                store.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ProjectionStoreError("projection store creation failed") from exc
            _enforce_owner_only(store)
        else:
            _verify_owner_only(store)
        return store

    def _verify_sidecars(self, store: Path) -> None:
        for suffix in _SIDECAR_SUFFIXES:
            sidecar = store / (PROJECTION_DB_FILENAME + suffix)
            if not sidecar.exists():
                continue
            if os.name == "nt":
                _verify_owner_only_windows(sidecar, allow_inherited=True)
            else:
                _enforce_owner_only_posix(sidecar)

    def _connect(self, store: Path) -> sqlite3.Connection:
        db = self.db_path
        created = not db.exists()
        try:
            conn = sqlite3.connect(str(db), isolation_level=None, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS projection ("
                " identity TEXT NOT NULL,"
                " label TEXT NOT NULL,"
                " marker_version TEXT NOT NULL,"
                " target_handle BLOB NOT NULL,"
                " workspace_path TEXT NOT NULL,"
                " state TEXT NOT NULL DEFAULT 'linked',"
                " ordinal INTEGER NOT NULL,"
                " updated_at TEXT NOT NULL,"
                " PRIMARY KEY (identity, target_handle)"
                ")"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_projection_target_handle"
                " ON projection (target_handle)"
            )
            conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            conn.commit()
        except sqlite3.Error as exc:
            raise ProjectionStoreError("projection database open failed") from exc
        if created:
            _enforce_owner_only(db)
        else:
            _verify_owner_only(db)
        return conn

    def _open(self) -> tuple[sqlite3.Connection, Path]:
        store = self._ensure_store()
        conn = self._connect(store)
        self._verify_sidecars(store)
        return conn, store

    def _run_transaction(self, fn: Any) -> Any:
        """Open, verify before use, run ``fn(conn)`` in one transaction."""
        conn, store = self._open()
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = fn(conn)
            conn.execute("COMMIT")
            return result
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()
            self._verify_sidecars(store)

    # -- boundary --------------------------------------------------------------

    def update(self, input: ProjectionInput) -> ProjectionResult:
        """Upsert one projection row (PLAN:463).

        Idempotency key ``(identity, target_handle)``: a same-key update
        replaces the local routing path and the deterministic input ordinal; a
        different identity on one captured target returns ``conflict`` without
        changing the marker (or any projection row). Store/enforcement failure
        is bounded to ``projection-failed`` (never silent).
        """
        identity = input.identity
        target = input.target_handle
        try:
            def _upsert(conn: sqlite3.Connection) -> None:
                row = conn.execute(
                    "SELECT identity FROM projection WHERE target_handle = ?",
                    (target,),
                ).fetchone()
                if row is not None and row[0] != identity:
                    raise _ConflictOnTarget(identity, target)
                conn.execute(
                    "INSERT INTO projection (identity, label, marker_version,"
                    " target_handle, workspace_path, state, ordinal, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(identity, target_handle) DO UPDATE SET"
                    " label = excluded.label, marker_version = excluded.marker_version,"
                    " workspace_path = excluded.workspace_path, state = excluded.state,"
                    " ordinal = excluded.ordinal, updated_at = excluded.updated_at",
                    (
                        identity,
                        input.label,
                        input.marker_version,
                        target,
                        str(input.workspace_path),
                        _STATE_LINKED,
                        input.ordinal,
                        _now_iso(),
                    ),
                )

            self._run_transaction(_upsert)
        except _ConflictOnTarget:
            return ProjectionResult(
                status=STATUS_CONFLICT,
                identity=identity,
                target_handle=target,
                ordinal=input.ordinal,
            )
        except sqlite3.IntegrityError:
            return ProjectionResult(
                status=STATUS_CONFLICT,
                identity=identity,
                target_handle=target,
                ordinal=input.ordinal,
            )
        except Exception:
            return ProjectionResult(
                status=STATUS_PROJECTION_FAILED,
                identity=identity,
                target_handle=target,
                ordinal=input.ordinal,
            )
        return ProjectionResult(
            status=STATUS_LINKED,
            identity=identity,
            target_handle=target,
            ordinal=input.ordinal,
        )

    def remove(self, identity: str, target_handle: bytes) -> ProjectionResult:
        """Remove the projection entry for ``(identity, target_handle)``.

        Mirrors the protocol's optional entry removal after a verified absence
        (protocol 4.12; PLAN:319): the entry is no longer linked, so the
        status is ``registered-unlinked``. Deleting projection state never
        unregisters anything and is independent of the marker (PLAN:319).
        """
        target = target_handle
        try:
            def _delete(conn: sqlite3.Connection) -> int | None:
                row = conn.execute(
                    "SELECT ordinal FROM projection WHERE identity = ? AND target_handle = ?",
                    (identity, target),
                ).fetchone()
                conn.execute(
                    "DELETE FROM projection WHERE identity = ? AND target_handle = ?",
                    (identity, target),
                )
                return row[0] if row is not None else None

            ordinal = self._run_transaction(_delete)
        except Exception:
            return ProjectionResult(
                status=STATUS_PROJECTION_FAILED, identity=identity, target_handle=target, ordinal=None
            )
        return ProjectionResult(
            status=STATUS_UNLINKED,
            identity=identity,
            target_handle=target,
            ordinal=ordinal,
        )

    def rebuild(self, workspace_paths: list[Path]) -> RebuildResult:
        """Transactional projection replacement from explicit ordered roots.

        One path means one workspace — no recursive traversal (PLAN:463).
        Symlink aliases deduplicate by target handle while retaining the first
        input's ordinal; each retained root carries its 1-based input ordinal.
        Every root must be a valid registered workspace; any inaccessible or
        invalid root returns a non-success and the previous projection is
        unchanged (rollback). On success stale entries are repaired inside the
        same transaction.
        """
        try:
            store = self._ensure_store()
        except ProjectionStoreError as exc:
            return RebuildResult(status=STATUS_REBUILD_FAILED, detail=str(exc))
        resolved: list[tuple[int, Path, fs.TargetHandle, dict[str, Any]]] = []
        seen: dict[bytes, int] = {}
        for ordinal, path in enumerate(workspace_paths, start=1):
            try:
                handle = fs.capture_target_handle(path)
            except (
                fs.IdentityUnavailableError,
                fs.TargetAliasMismatchError,
                fs.RedirectedMarkerComponentError,
            ) as exc:
                return RebuildResult(status=STATUS_REBUILD_FAILED, detail=_bounded_detail(path, exc))
            key = handle.to_bytes()
            if key in seen:
                continue  # symlink alias: dedupe by target handle, first ordinal retained
            try:
                raw = fs.read_marker(path)
            except fs.ReadBackFailedError as exc:
                return RebuildResult(status=STATUS_REBUILD_FAILED, detail=_bounded_detail(path, exc))
            marker = _parse_marker(raw)
            if marker is None:
                return RebuildResult(
                    status=STATUS_REBUILD_FAILED,
                    detail=f"rebuild root failed: {path}: invalid marker",
                )
            seen[key] = ordinal
            resolved.append((ordinal, path, handle, marker))
        try:
            def _replace(conn: sqlite3.Connection) -> None:
                for ordinal, path, handle, marker in resolved:
                    conn.execute(
                        "INSERT INTO projection (identity, label, marker_version,"
                        " target_handle, workspace_path, state, ordinal, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                        " ON CONFLICT(identity, target_handle) DO UPDATE SET"
                        " label = excluded.label, marker_version = excluded.marker_version,"
                        " workspace_path = excluded.workspace_path, state = excluded.state,"
                        " ordinal = excluded.ordinal, updated_at = excluded.updated_at",
                        (
                            str(marker["identity"]),
                            str(marker["label"]),
                            str(marker["version"]),
                            handle.to_bytes(),
                            str(path),
                            _STATE_LINKED,
                            ordinal,
                            _now_iso(),
                        ),
                    )
                if resolved:
                    placeholders = ",".join("?" for _ in seen)
                    conn.execute(
                        f"DELETE FROM projection WHERE target_handle NOT IN ({placeholders})",
                        list(seen.keys()),
                    )
                else:
                    conn.execute("DELETE FROM projection")

            self._run_transaction(_replace)
        except Exception as exc:
            return RebuildResult(
                status=STATUS_REBUILD_FAILED, detail=f"rebuild failed: {type(exc).__name__}"
            )
        return RebuildResult(status=STATUS_REBUILT, entries=tuple(self.list_projection()))

    def list_projection(self) -> list[dict[str, Any]]:
        """All projection rows in deterministic input-ordinal order (U11)."""
        conn, _ = self._open()
        try:
            rows = conn.execute(
                "SELECT identity, label, marker_version, target_handle,"
                " workspace_path, state, ordinal, updated_at"
                " FROM projection ORDER BY ordinal, identity"
            ).fetchall()
            return [_row_to_entry(row).to_dict() for row in rows]
        except sqlite3.Error as exc:
            raise ProjectionStoreError("projection query failed") from exc
        finally:
            conn.close()

    def find_by_target(self, target_handle: bytes) -> dict[str, Any] | None:
        """Routing lookup for one captured target (U11; not authority)."""
        conn, _ = self._open()
        try:
            row = conn.execute(
                "SELECT identity, label, marker_version, target_handle,"
                " workspace_path, state, ordinal, updated_at"
                " FROM projection WHERE target_handle = ?",
                (target_handle,),
            ).fetchone()
            return _row_to_entry(row).to_dict() if row is not None else None
        except sqlite3.Error as exc:
            raise ProjectionStoreError("projection query failed") from exc
        finally:
            conn.close()

    def find_by_identity(self, identity: str) -> dict[str, Any] | None:
        """Row lookup by marker identity (U11; not authority)."""
        conn, _ = self._open()
        try:
            row = conn.execute(
                "SELECT identity, label, marker_version, target_handle,"
                " workspace_path, state, ordinal, updated_at"
                " FROM projection WHERE identity = ?",
                (identity,),
            ).fetchone()
            return _row_to_entry(row).to_dict() if row is not None else None
        except sqlite3.Error as exc:
            raise ProjectionStoreError("projection query failed") from exc
        finally:
            conn.close()


class _ConflictOnTarget(Exception):
    """Internal marker for the write-time conflict branch (PLAN:528, 542)."""

    def __init__(self, identity: str, target_handle: bytes) -> None:
        super().__init__("projection conflict: captured target holds a different identity")
        self.identity = identity
        self.target_handle = target_handle


def _row_to_entry(row: Any) -> ProjectionEntry:
    identity, label, marker_version, target_handle, workspace_path, state, ordinal, updated_at = row
    return ProjectionEntry(
        identity=identity,
        label=label,
        marker_version=marker_version,
        target_handle=base64.b64encode(bytes(target_handle)).decode("ascii"),
        workspace_path=workspace_path,
        state=state,
        ordinal=ordinal,
        updated_at=updated_at,
    )


def _parse_marker(raw: bytes) -> dict[str, Any] | None:
    """Raw guard + parse + bundled schema validation (U7/U8 pipeline); the
    parsed marker dict or None (bounded, no echo)."""
    guard = rg.guard(raw)
    if not guard.passed:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    if not vd.validate_marker(parsed).valid:
        return None
    return parsed
