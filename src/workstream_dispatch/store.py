"""Arjim-local replaceable store — job binding and change baseline (U3).

Holds the job-to-agent binding and the per-workspace git baseline in
disposable local state whose loss degrades answers honestly (R17).
Following ``projection.py``'s store-dir, WAL, ``BEGIN IMMEDIATE``,
and owner-only pattern.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENV_STORE_DIR = "WORKSTREAM_DISPATCH_STORE_DIR"
_DEFAULT_STORE_RELPATH = Path("arjim") / "dispatch"
_SCHEMA_VERSION = 1
_DB_NAME = "dispatch.db"

# ---------------------------------------------------------------------------
# Store-dir resolution (mirrors projection.default_store_dir)
# ---------------------------------------------------------------------------


def default_store_dir() -> Path:
    """Per-user application data store location, overridable by env var."""
    override = os.environ.get(_ENV_STORE_DIR)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / _DEFAULT_STORE_RELPATH
        return Path.home() / "AppData" / "Local" / _DEFAULT_STORE_RELPATH
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / _DEFAULT_STORE_RELPATH
    return Path.home() / ".local" / "share" / _DEFAULT_STORE_RELPATH


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StoreError(Exception):
    """The dispatch store is unavailable or corrupt."""


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class DispatchStore:
    """SQLite-backed replaceable store for job bindings and workspace baselines.

    Two tables in one database with ``CREATE TABLE IF NOT EXISTS`` and a
    stamped ``PRAGMA user_version``.  Every mutation wrapped in
    ``BEGIN IMMEDIATE`` / commit / rollback.
    """

    def __init__(self, store_dir: Path | None = None) -> None:
        self._store_dir = store_dir or default_store_dir()
        self._db_path = self._store_dir / _DB_NAME

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def store_dir(self) -> Path:
        return self._store_dir

    def _ensure_store(self) -> Path:
        self._store_dir.mkdir(parents=True, exist_ok=True)
        return self._store_dir

    def _connect(self) -> sqlite3.Connection:
        self._ensure_store()
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS bindings ("
                " job_id TEXT PRIMARY KEY,"
                " agent_id TEXT NOT NULL,"
                " dispatch_timestamp TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS baselines ("
                " workspace_handle TEXT PRIMARY KEY,"
                " head_oid TEXT NOT NULL,"
                " worktree_digest TEXT NOT NULL,"
                " updated_at TEXT NOT NULL"
                ")"
            )
            conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            conn.commit()
        except sqlite3.Error as exc:
            raise StoreError("dispatch database open failed") from exc
        return conn

    def _run_transaction(self, fn: Any) -> Any:
        """Open, run ``fn(conn)`` in one transaction."""
        conn = self._connect()
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

    # -- Binding operations --

    def bind_job(self, job_id: str, agent_id: str, dispatch_timestamp: str) -> None:
        """Bind a job to an agent (create or update)."""
        def _upsert(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO bindings (job_id, agent_id, dispatch_timestamp)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(job_id) DO UPDATE SET"
                " agent_id = excluded.agent_id,"
                " dispatch_timestamp = excluded.dispatch_timestamp",
                (job_id, agent_id, dispatch_timestamp),
            )
        self._run_transaction(_upsert)

    def get_binding(self, job_id: str) -> dict[str, str] | None:
        """Read a binding.  Returns None if not found."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT job_id, agent_id, dispatch_timestamp FROM bindings WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            return {"job_id": row[0], "agent_id": row[1], "dispatch_timestamp": row[2]}
        except sqlite3.Error as exc:
            raise StoreError("dispatch query failed") from exc
        finally:
            conn.close()

    def delete_binding(self, job_id: str) -> None:
        """Remove a binding."""
        def _delete(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM bindings WHERE job_id = ?", (job_id,))
        self._run_transaction(_delete)

    # -- Baseline operations --

    def set_baseline(
        self,
        workspace_handle: str,
        head_oid: str,
        worktree_digest: str,
        updated_at: str,
    ) -> None:
        """Record or update a workspace baseline."""
        def _upsert(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO baselines (workspace_handle, head_oid, worktree_digest, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(workspace_handle) DO UPDATE SET"
                " head_oid = excluded.head_oid,"
                " worktree_digest = excluded.worktree_digest,"
                " updated_at = excluded.updated_at",
                (workspace_handle, head_oid, worktree_digest, updated_at),
            )
        self._run_transaction(_upsert)

    def get_baseline(self, workspace_handle: str) -> dict[str, str] | None:
        """Read a baseline.  Returns None if not found."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT workspace_handle, head_oid, worktree_digest, updated_at"
                " FROM baselines WHERE workspace_handle = ?",
                (workspace_handle,),
            ).fetchone()
            if row is None:
                return None
            return {
                "workspace_handle": row[0],
                "head_oid": row[1],
                "worktree_digest": row[2],
                "updated_at": row[3],
            }
        except sqlite3.Error as exc:
            raise StoreError("dispatch query failed") from exc
        finally:
            conn.close()

    def delete_baseline(self, workspace_handle: str) -> None:
        """Remove a baseline."""
        def _delete(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM baselines WHERE workspace_handle = ?", (workspace_handle,))
        self._run_transaction(_delete)

    # -- Lifecycle --

    def destroy(self) -> None:
        """Delete the database file (for wipe tests)."""
        try:
            self._db_path.unlink(missing_ok=True)
        except OSError as exc:
            raise StoreError("dispatch store destroy failed") from exc
