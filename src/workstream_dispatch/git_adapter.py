"""Git adapter — bounded git operations for workspace change signals (KTD6).

Provides the same egress discipline as the Paseo adapter: fixed argv lists,
a module-level timeout constant, and bounded error conversion.  Git failure
derives ``unsupported`` for that workspace with a coverage note, never a
crash and never a changed/unchanged claim.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT_SECONDS = 10
_GIT_NO_FSMONITOR = [
    "-c", "core.fsmonitor=false",
    "-c", "core.untrackedCache=false",
]
_GIT_ENV = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}


class GitError(Exception):
    """Git is unavailable or timed out."""


@dataclass(frozen=True)
class GitState:
    """A snapshot of a workspace's git state."""

    head_oid: str
    worktree_digest: str  # hash of untracked + modified files summary


def capture_git_state(workspace: Path) -> GitState | None:
    """Capture HEAD OID and a worktree-state digest for baseline comparison.

    Returns None on any git failure (missing from PATH, timeout, non-zero
    exit) — never raises.
    """
    try:
        # Get HEAD OID
        proc = subprocess.run(
            ["git", *_GIT_NO_FSMONITOR, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            cwd=str(workspace),
            env=_GIT_ENV,
        )
        if proc.returncode != 0:
            return None
        head_oid = proc.stdout.strip()
        if not head_oid:
            return None

        # Get worktree state digest: dirty + untracked file count
        proc_status = subprocess.run(
            ["git", *_GIT_NO_FSMONITOR, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            cwd=str(workspace),
            env=_GIT_ENV,
        )
        if proc_status.returncode != 0:
            # Can get HEAD but not status — still usable, digest is just HEAD
            digest = hashlib.sha256(head_oid.encode()).hexdigest()[:16]
            return GitState(head_oid=head_oid, worktree_digest=digest)

        # Hash the porcelain output as the worktree digest
        digest = hashlib.sha256(proc_status.stdout.encode()).hexdigest()[:16]
        return GitState(head_oid=head_oid, worktree_digest=digest)

    except (OSError, subprocess.TimeoutExpired):
        return None
