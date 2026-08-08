"""Filesystem lifecycle primitives for Workstream Registration v1 (U9).

Owns KTD13 (PLAN:198) and the stable target handle (PLAN:200): per-workspace
registration locks with the atomic absent-parent step, create-only marker
writes, bounded read-back, absence verification, and stale-lock recovery. The
module never prints or logs its input; it returns structured results only.

Lock semantics (KTD13, PLAN:198; 08-06 decision PLAN:552):

- When the ``.workstream`` parent is absent, lock acquisition and parent
  creation are one atomic step: create the parent directory without
  replacement, then exclusively create ``.workstream/.registration.lock``
  within it. When the parent already exists, the lock is acquired without
  creating or altering the parent.
- The lock file is created with exclusive-create semantics and carries bounded
  JSON metadata ``{owner_id, pid, target_handle, started_at, lease_until}``.
- Acquisition is bounded by a timeout; an unobtainable lock raises
  :class:`LockUnavailableError` (fail closed, no write).
- Release happens on normal and exceptional exit (context manager).
- A lock is stale only when its lease has expired AND its owner process is no
  longer alive (platform liveness check; a failed liveness check treats the
  owner as alive — fail safe). A stale lock is broken only by
  :func:`recover_lock` after an in-process confirmation whose target handle
  matches the lock metadata and the current workspace; a live owner's lock is
  never broken.

Stable target handle (PLAN:200): a tuple of the filesystem identity of the
inspected workspace directory and the identity of its ``.workstream`` parent,
captured with platform directory/file identity APIs (``os.stat`` file
identifiers) rather than path strings. When ``.workstream`` is absent, the
parent component is the explicit ``ABSENT`` sentinel (``None``). Identity
capture failures fail closed with :class:`IdentityUnavailableError`; a symlink
alias whose resolved identity differs from the as-given path raises
:class:`TargetAliasMismatchError`; a marker path that resolves outside the
workspace (redirected marker component) raises
:class:`RedirectedMarkerComponentError`.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "ABSENT_PARENT",
    "DEFAULT_LEASE_SECONDS",
    "LOCK_FILENAME",
    "MARKER_FILENAME",
    "MAX_MARKER_READ_BYTES",
    "MAX_READ_BYTES",
    "PARENT_DIRNAME",
    "CreateCollisionError",
    "FilesystemError",
    "IdentityUnavailableError",
    "LockMetadata",
    "LockNotRecoverableError",
    "LockUnavailableError",
    "ReadBackFailedError",
    "RedirectedMarkerComponentError",
    "TargetAliasMismatchError",
    "TargetHandle",
    "WriteFailedError",
    "acquire_lock",
    "capture_target_handle",
    "conditional_delete_marker",
    "delete_marker",
    "lock_metadata",
    "marker_path",
    "parent_path",
    "read_marker",
    "recover_lock",
    "registration_lock",
    "release_lock",
    "stale_after",
    "verify_marker_absent",
    "write_marker_create_only",
]

PARENT_DIRNAME = ".workstream"
MARKER_FILENAME = "manifest.json"
LOCK_FILENAME = ".registration.lock"

MAX_READ_BYTES = 262_144
MAX_MARKER_READ_BYTES = 262_145

MAX_LOCK_METADATA_BYTES = 4096
DEFAULT_LEASE_SECONDS = 60.0
_LOCK_RETRY_INTERVAL = 0.05

# Explicit ABSENT sentinel for a missing .workstream parent (PLAN:200). The
# ``TargetHandle.parent`` component is ``None`` (the sentinel) when the parent
# is absent.
ABSENT_PARENT = None

_IDENTITY_FORMAT = "<QQ"


class FilesystemError(RuntimeError):
    """Bounded base error for filesystem lifecycle failures."""


class IdentityUnavailableError(FilesystemError):
    """The declared platform identity APIs are unavailable; fail closed."""


class TargetAliasMismatchError(FilesystemError):
    """An alias path resolves to a different identity than the captured tuple."""


class RedirectedMarkerComponentError(FilesystemError):
    """The marker path resolves outside the workspace; redirection rejected."""


class LockUnavailableError(FilesystemError):
    """The per-workspace lock could not be acquired within the bounded timeout."""


class LockNotRecoverableError(FilesystemError):
    """A lock cannot be recovered: live owner or target-handle mismatch."""


class CreateCollisionError(FilesystemError):
    """Exclusive-create failed: the marker path is already occupied."""


class WriteFailedError(FilesystemError):
    """The marker write could not be completed."""


class ReadBackFailedError(FilesystemError):
    """The marker could not be re-opened and read back."""


def parent_path(workspace_path: Path) -> Path:
    """The fixed ``.workstream`` parent directory path below the workspace."""
    return workspace_path / PARENT_DIRNAME


def marker_path(workspace_path: Path) -> Path:
    """The fixed marker path ``.workstream/manifest.json`` (frozen, 2026-08-07 decision, digest 2026080702)."""
    return parent_path(workspace_path) / MARKER_FILENAME


def lock_path(workspace_path: Path) -> Path:
    """The cooperative lock path ``.workstream/.registration.lock`` (KTD13)."""
    return parent_path(workspace_path) / LOCK_FILENAME


def _capture_identity(path: Path) -> bytes:
    """Filesystem identity via platform stat identifiers; fail closed.

    On both declared profiles (Windows NTFS, POSIX) ``os.stat`` fills the
    device and file identifiers (volume serial + file index on Windows,
    ``st_dev`` + ``st_ino`` on POSIX). The identity is the packed pair. Any
    failure — missing/inaccessible path, missing stat fields, or a
    platform that does not fill the identifiers — raises
    :class:`IdentityUnavailableError`; the implementation never guesses.
    """
    try:
        st = os.stat(path)
    except OSError as exc:
        raise IdentityUnavailableError(
            "identity capture failed: platform stat unavailable"
        ) from exc
    dev = getattr(st, "st_dev", None)
    ino = getattr(st, "st_ino", None)
    if dev is None or ino is None:
        raise IdentityUnavailableError(
            "identity capture failed: stat identifiers unavailable"
        )
    dev = int(dev)
    ino = int(ino)
    if dev == 0 and ino == 0:
        raise IdentityUnavailableError(
            "identity capture failed: empty stat identifiers"
        )
    return struct.pack(_IDENTITY_FORMAT, dev, ino)


def _marker_resolves_inside(workspace_path: Path) -> bool:
    """The resolved marker path must stay inside the resolved workspace.

    A redirected marker component (a ``.workstream`` symlink or junction that
    resolves outside the workspace, or any component pointing elsewhere)
    fails the containment check and is rejected (PLAN:200).
    """
    try:
        resolved_workspace = workspace_path.resolve()
        resolved_marker = marker_path(workspace_path).resolve()
    except OSError:
        return False
    resolved_parent = resolved_marker.parent
    return resolved_parent == resolved_workspace or (
        resolved_workspace in resolved_parent.parents
    )


@dataclass(frozen=True)
class TargetHandle:
    """Stable filesystem identity tuple (PLAN:200).

    ``workspace`` is the filesystem identity of the inspected workspace
    directory; ``parent`` is the identity of its ``.workstream`` parent, or
    ``None`` (the explicit ``ABSENT`` sentinel) when the parent is absent.
    Symlink aliases are equivalent only when they resolve to the same captured
    identities.
    """

    workspace: bytes
    parent: bytes | None = ABSENT_PARENT

    @property
    def parent_absent(self) -> bool:
        """True when the ``.workstream`` parent was observed absent."""
        return self.parent is None

    def to_bytes(self) -> bytes:
        """Deterministic byte form for the projection's ``target_handle``."""
        workspace_b64 = base64.b64encode(self.workspace).decode("ascii")
        if self.parent is None:
            parent_b64 = "ABSENT"
        else:
            parent_b64 = base64.b64encode(self.parent).decode("ascii")
        return f"{workspace_b64}:{parent_b64}".encode("ascii")

    def to_dict(self) -> dict[str, str]:
        """Bounded JSON-able form for lock metadata."""
        if self.parent is None:
            return {"workspace": base64.b64encode(self.workspace).decode("ascii"), "parent": "ABSENT"}
        return {
            "workspace": base64.b64encode(self.workspace).decode("ascii"),
            "parent": base64.b64encode(self.parent).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetHandle":
        """Parse the lock-metadata form; malformed data fails closed."""
        try:
            workspace = base64.b64decode(data["workspace"], validate=True)
            parent_raw = data["parent"]
            parent = None if parent_raw == "ABSENT" else base64.b64decode(parent_raw, validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed target handle metadata") from exc
        return cls(workspace=workspace, parent=parent)


def capture_target_handle(workspace_path: Path) -> TargetHandle:
    """Capture the stable target handle for the workspace (PLAN:200).

    Resolved-identity discipline: the as-given path and its resolved path must
    yield the same identity (symlink aliases are equivalent only when they
    resolve to the same captured identities); a mismatch raises
    :class:`TargetAliasMismatchError`. The resolved marker path must remain
    inside the workspace; otherwise :class:`RedirectedMarkerComponentError`.
    When ``.workstream`` is absent the parent component is the ``ABSENT``
    sentinel.
    """
    given_identity = _capture_identity(workspace_path)
    try:
        resolved = workspace_path.resolve()
    except OSError as exc:
        raise IdentityUnavailableError(
            "identity capture failed: path resolution unavailable"
        ) from exc
    resolved_identity = _capture_identity(resolved)
    if given_identity != resolved_identity:
        raise TargetAliasMismatchError(
            "target alias mismatch: resolved identity differs from captured identity"
        )
    if not _marker_resolves_inside(workspace_path):
        raise RedirectedMarkerComponentError(
            "redirected marker component: marker path resolves outside the workspace"
        )
    parent = parent_path(workspace_path)
    try:
        os.stat(parent)
    except FileNotFoundError:
        return TargetHandle(workspace=resolved_identity, parent=ABSENT_PARENT)
    except OSError as exc:
        raise IdentityUnavailableError(
            "identity capture failed: parent stat unavailable"
        ) from exc
    parent_identity = _capture_identity(parent)
    return TargetHandle(workspace=resolved_identity, parent=parent_identity)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def stale_after(seconds: float = DEFAULT_LEASE_SECONDS) -> str:
    """ISO-8601 UTC lease deadline ``seconds`` from now (lock metadata)."""
    return _now_utc().timestamp() + seconds


def _format_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _parse_timestamp(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    """Platform liveness check; a failed check treats the owner as alive.

    POSIX: ``os.kill(pid, 0)``; a ``ProcessLookupError`` means dead. Windows:
    ``ctypes.OpenProcess`` with query rights; ``ERROR_INVALID_PARAMETER``
    means the process does not exist. Any other failure (e.g. access denied)
    is treated as alive — fail safe (KTD13, PLAN:198).
    """
    if pid <= 0:
        return True
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _pid_alive_windows(pid: int) -> bool:
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ERROR_INVALID_PARAMETER = 87
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    if ctypes.get_last_error() == ERROR_INVALID_PARAMETER:
        return False
    return True


@dataclass(frozen=True)
class LockMetadata:
    """Bounded lock metadata JSON: ``{owner_id, pid, target_handle,
    started_at, lease_until}`` (KTD13, PLAN:198)."""

    owner_id: str
    pid: int
    target_handle: TargetHandle
    started_at: str
    lease_until: str

    def to_bytes(self) -> bytes:
        payload: dict[str, Any] = {
            "owner_id": self.owner_id,
            "pid": self.pid,
            "target_handle": self.target_handle.to_dict(),
            "started_at": self.started_at,
            "lease_until": self.lease_until,
        }
        text = json.dumps(payload, separators=(",", ":"))
        return text.encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "LockMetadata":
        if len(raw) > MAX_LOCK_METADATA_BYTES:
            raise ValueError("lock metadata over limit")
        try:
            data = json.loads(raw.decode("utf-8"))
            handle = TargetHandle.from_dict(data["target_handle"])
            metadata = cls(
                owner_id=str(data["owner_id"]),
                pid=int(data["pid"]),
                target_handle=handle,
                started_at=str(data["started_at"]),
                lease_until=str(data["lease_until"]),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed lock metadata") from exc
        if not metadata.owner_id or metadata.pid <= 0:
            raise ValueError("malformed lock metadata")
        return metadata

    def lease_expired(self) -> bool:
        """True when the lease deadline has passed."""
        deadline = _parse_timestamp(self.lease_until)
        if deadline is None:
            return False
        return _now_utc().timestamp() > deadline

    def owner_alive(self) -> bool:
        return _pid_alive(self.pid)

    def is_stale(self) -> bool:
        """Stale only when the lease expired AND the owner is no longer alive."""
        return self.lease_expired() and not self.owner_alive()


def _read_lock_metadata(workspace_path: Path) -> LockMetadata | None:
    """Read and parse the lock file; malformed metadata fails safe (None)."""
    path = lock_path(workspace_path)
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_LOCK_METADATA_BYTES + 1)
    except OSError:
        return None
    try:
        return LockMetadata.from_bytes(raw)
    except ValueError:
        return None


def _create_lock_file(lock: Path, metadata: LockMetadata) -> None:
    """Exclusive-create the lock file and write the bounded metadata."""
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise
    except OSError as exc:
        raise LockUnavailableError("lock file creation failed") from exc
    payload = metadata.to_bytes()
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise WriteFailedError("lock metadata write failed")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _replace_lock_file(lock: Path, metadata: LockMetadata) -> None:
    """Atomically replace a stale lock (recovery path; PLAN:475 recover-lock)."""
    tmp = lock.with_name(f".{LOCK_FILENAME}.{secrets.token_hex(6)}.tmp")
    payload = metadata.to_bytes()
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        raise LockUnavailableError("lock replacement failed") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise WriteFailedError("lock metadata write failed")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.replace(tmp, lock)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise LockUnavailableError("lock replacement failed") from exc


def _acquire_lock_once(
    workspace_path: Path,
    owner_id: str,
    pid: int,
    target_handle: TargetHandle,
    lease_until: float,
    *,
    recover_stale: bool,
) -> None:
    """One acquisition attempt; raises on contention or failure."""
    parent = parent_path(workspace_path)
    try:
        os.mkdir(parent)
    except FileExistsError:
        pass  # parent created concurrently or already present; lock-only path
    except OSError as exc:
        raise LockUnavailableError("parent creation failed") from exc
    lock = lock_path(workspace_path)
    metadata = LockMetadata(
        owner_id=owner_id,
        pid=pid,
        target_handle=target_handle,
        started_at=_format_timestamp(_now_utc().timestamp()),
        lease_until=_format_timestamp(lease_until),
    )
    try:
        _create_lock_file(lock, metadata)
        return
    except FileExistsError:
        pass
    if not recover_stale:
        raise LockUnavailableError("lock held by another writer")
    existing = _read_lock_metadata(workspace_path)
    if existing is None:
        raise LockUnavailableError("lock held by another writer")
    # Recovery matches the stable workspace identity component: the parent
    # component legitimately transitions ABSENT -> created-parent-identity
    # during an interrupted lifecycle (KTD6, PLAN:191; PLAN:552).
    if (
        existing.target_handle.workspace != target_handle.workspace
        or not existing.is_stale()
    ):
        raise LockUnavailableError("lock held by another writer")
    _replace_lock_file(lock, metadata)


def acquire_lock(
    workspace_path: Path,
    owner_id: str,
    pid: int,
    target_handle: TargetHandle,
    lease_until: float,
    timeout: float,
    *,
    recover_stale: bool = False,
) -> None:
    """Acquire the per-workspace registration lock within a bounded timeout.

    Absent parent: one atomic step — create ``.workstream`` without
    replacement, then exclusively create ``.workstream/.registration.lock``
    within it. Existing parent: the lock is acquired without creating or
    altering the parent (KTD13, PLAN:198; PLAN:552). With
    ``recover_stale=True`` a stale lock whose target handle matches may be
    replaced (recovery authorized by an in-process confirmation). Failure to
    acquire within ``timeout`` seconds raises :class:`LockUnavailableError`
    (fail closed, no write).
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            _acquire_lock_once(
                workspace_path,
                owner_id,
                pid,
                target_handle,
                lease_until,
                recover_stale=recover_stale,
            )
            return
        except LockUnavailableError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_LOCK_RETRY_INTERVAL)


def release_lock(workspace_path: Path, owner_id: str) -> None:
    """Release the lock when it is still owned by ``owner_id``.

    A lock replaced by another owner is never deleted (never break another
    writer's lock). Absence of the lock is a no-op.
    """
    lock = lock_path(workspace_path)
    try:
        raw = lock.read_bytes()
    except OSError:
        return
    try:
        metadata = LockMetadata.from_bytes(raw)
    except ValueError:
        return
    if metadata.owner_id != owner_id:
        return
    try:
        os.unlink(lock)
    except OSError:
        pass


class registration_lock:
    """Context manager: acquire on entry, release on normal AND exceptional
    exit (KTD13, PLAN:198)."""

    def __init__(
        self,
        workspace_path: Path,
        target_handle: TargetHandle,
        *,
        owner_id: str | None = None,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        timeout: float = 5.0,
        recover_stale: bool = False,
    ) -> None:
        self.workspace_path = workspace_path
        self.target_handle = target_handle
        self.owner_id = owner_id if owner_id is not None else secrets.token_hex(16)
        self.lease_seconds = lease_seconds
        self.timeout = timeout
        self.recover_stale = recover_stale

    def __enter__(self) -> str:
        lease_until = stale_after(self.lease_seconds)
        acquire_lock(
            self.workspace_path,
            self.owner_id,
            os.getpid(),
            self.target_handle,
            lease_until,
            self.timeout,
            recover_stale=self.recover_stale,
        )
        return self.owner_id

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        release_lock(self.workspace_path, self.owner_id)


def lock_metadata(workspace_path: Path) -> LockMetadata | None:
    """Current lock metadata for the workspace, or None when absent/malformed."""
    return _read_lock_metadata(workspace_path)


def recover_lock(
    workspace_path: Path,
    confirmed_target_handle: TargetHandle,
    *,
    owner_id: str | None = None,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
) -> bool:
    """Validate and replace a stale lock (in-process confirmed recovery).

    Recovery rules (KTD13, PLAN:198; PLAN:475): the confirmed target handle's
    stable workspace identity must match both the current workspace and the
    lock metadata (the parent component may legitimately transition
    ABSENT -> created during an interrupted lifecycle), the owner must be
    dead, and the lease must have expired. A live owner's lock, a mismatched
    identity, or malformed metadata is never broken
    (:class:`LockNotRecoverableError`). Returns True when the lock is absent
    (nothing to recover) or was replaced.
    """
    current = capture_target_handle(workspace_path)
    if current.workspace != confirmed_target_handle.workspace:
        raise LockNotRecoverableError(
            "lock recovery rejected: confirmed target handle does not match the workspace"
        )
    existing = _read_lock_metadata(workspace_path)
    if existing is None:
        return True
    if existing.target_handle.workspace != confirmed_target_handle.workspace:
        raise LockNotRecoverableError(
            "lock recovery rejected: lock target handle does not match the confirmation"
        )
    if not existing.is_stale():
        raise LockNotRecoverableError("lock recovery rejected: lock owner is live")
    replacement = LockMetadata(
        owner_id=owner_id if owner_id is not None else secrets.token_hex(16),
        pid=os.getpid(),
        target_handle=current,
        started_at=_format_timestamp(_now_utc().timestamp()),
        lease_until=_format_timestamp(stale_after(lease_seconds)),
    )
    _replace_lock_file(lock_path(workspace_path), replacement)
    return True


def write_marker_create_only(
    workspace_path: Path, marker_bytes: bytes, target_handle: TargetHandle
) -> None:
    """Create-only marker write (KTD13, PLAN:198).

    Opens the final marker with exclusive-create semantics (never replaces),
    writes the complete bounded document, flushes, requests synchronization
    (``os.fsync``), and closes. An existing marker raises
    :class:`CreateCollisionError` — it is never overwritten.
    """
    if len(marker_bytes) > MAX_MARKER_READ_BYTES:
        raise WriteFailedError("marker document exceeds the raw bound")
    target = marker_path(workspace_path)
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise CreateCollisionError(
            "marker create collision: an existing marker is never overwritten"
        ) from exc
    except OSError as exc:
        raise WriteFailedError("marker open failed") from exc
    try:
        view = memoryview(marker_bytes)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise WriteFailedError("marker write failed")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def read_marker(workspace_path: Path) -> bytes:
    """Reopen and read the marker, bounded to the raw cap plus one byte.

    The bound preserves the guard's ability to distinguish an allowed
    262,144-byte marker from an oversized one (KTD11, PLAN:196).
    """
    target = marker_path(workspace_path)
    try:
        with target.open("rb") as handle:
            raw = handle.read(MAX_MARKER_READ_BYTES)
    except OSError as exc:
        raise ReadBackFailedError("marker read-back failed") from exc
    return raw


def delete_marker(workspace_path: Path) -> None:
    """Delete the marker at the fixed marker path.

    Raises FileNotFoundError when the marker is already absent. Used by the
    confirmed ``resolve-invalid`` resolution (PLAN:451) and, via the shared
    primitives, by U10's confirmed conditional unregister.
    """
    target = marker_path(workspace_path)
    try:
        os.unlink(target)
    except OSError as exc:
        if isinstance(exc, FileNotFoundError):
            raise
        raise FilesystemError("marker delete failed") from exc


def conditional_delete_marker(workspace_path: Path, expected_identity: bytes) -> bool:
    """Delete the marker only when its raw bytes match ``expected_identity``.

    Reads the marker, compares the raw bytes to the confirmation-bound
    identity, and deletes only on an exact match; a changed marker is left
    untouched and False is returned (KTD10, PLAN:195; PLAN:463). The marker
    path's fixed content comparison is the conditional-delete primitive for
    U10's unregister and U9's resolution.
    """
    try:
        raw = read_marker(workspace_path)
    except ReadBackFailedError:
        return False
    if raw != expected_identity:
        return False
    try:
        os.unlink(marker_path(workspace_path))
    except OSError:
        return False
    return True


def verify_marker_absent(workspace_path: Path) -> bool:
    """Absence read-back: True when the marker path is verified gone."""
    try:
        os.stat(marker_path(workspace_path))
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False
