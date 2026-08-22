"""Job record store — create-only confirmed write and read (U2).

Workspace-owned job records live at ``.workstream/dispatch/<job-id>.json``
inside each target workspace.  Writes use the exclusive-create sequence from
the registration trust pattern; reads re-validate against the U1 schema and
compare bytes.  The outcome-note reader derives its target path from
``job_id`` (R26, KTD11) — no field on the record can steer a read.
"""
from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from workstream_dispatch.conformance_runner import repo_root

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DISPATCH_DIR = Path(".workstream") / "dispatch"
_JOB_RECORD_SUFFIX = ".json"
_NOTE_RECORD_SUFFIX = ".note.json"
_MAX_RECORD_BYTES = 256 * 1024  # 256 KiB
_MAX_NOTE_BYTES = 64 * 1024     # 64 KiB

_JOB_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

# ---------------------------------------------------------------------------
# Schema loading (bundled-only, mirrors registration validation.py)
# ---------------------------------------------------------------------------

_CONTRACTS_V1 = Path("contracts") / "workstream-dispatch" / "v1"
_JOB_RECORD_SCHEMA_NAME = "job-record.schema.json"
_OUTCOME_NOTE_SCHEMA_NAME = "outcome-note.schema.json"

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _load_schema(name: str) -> dict[str, Any]:
    cached = _SCHEMA_CACHE.get(name)
    if cached is not None:
        return copy.deepcopy(cached)
    path = repo_root() / _CONTRACTS_V1 / name
    with path.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    _SCHEMA_CACHE[name] = schema
    return copy.deepcopy(schema)


def _job_record_validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema(_JOB_RECORD_SCHEMA_NAME))


def _outcome_note_validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema(_OUTCOME_NOTE_SCHEMA_NAME))


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RecordCollisionError(Exception):
    """An exclusive-create collision: the record already exists."""


class RecordWriteError(Exception):
    """An OS-level write failure."""


class RecordReadError(Exception):
    """A read-back or validation failure."""


class PathRefusedError(Exception):
    """The derived note path failed containment or reparse-point checks."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dispatch_dir(workspace: Path) -> Path:
    return workspace / _DISPATCH_DIR


def _record_path(workspace: Path, job_id: str) -> Path:
    return _dispatch_dir(workspace) / f"{job_id}{_JOB_RECORD_SUFFIX}"


def _note_path(workspace: Path, job_id: str) -> Path:
    return _dispatch_dir(workspace) / f"{job_id}{_NOTE_RECORD_SUFFIX}"


def _validate_job_record(data: dict[str, Any]) -> None:
    _job_record_validator().validate(data)


def _validate_outcome_note(data: dict[str, Any]) -> None:
    _outcome_note_validator().validate(data)


def _is_reparse_point(p: Path) -> bool:
    """True if the path component is a symlink, junction, or other reparse point."""
    try:
        st = p.lstat()
    except OSError:
        return False
    if hasattr(st, "st_file_attributes"):
        # Windows: FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        if st.st_file_attributes & 0x400:
            return True
    return p.is_symlink()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WriteResult:
    """Outcome of a create-only job-record write."""

    status: str  # "written" | "collision" | "write-failed" | "written-unverified"
    job_id: str
    path: Path | None = None


@dataclass(frozen=True)
class ReadResult:
    """A successfully read and validated job record."""

    job_id: str
    record: dict[str, Any]
    path: Path
    bytes: bytes


def write_job_record(
    workspace: Path,
    record: dict[str, Any],
) -> WriteResult:
    """Create-only write of a job record into the workspace (R4, R19).

    Uses exclusive-create semantics (``O_CREAT | O_EXCL | O_WRONLY``) —
    never overwrites an existing record.  After writing, reopens the file
    and re-validates against the U1 schema; reports ``written-unverified``
    on any readback mismatch.
    """
    job_id: str = record["job_id"]
    target = _record_path(workspace, job_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    record_bytes = json.dumps(
        record, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(record_bytes) > _MAX_RECORD_BYTES:
        return WriteResult(status="write-failed", job_id=job_id)
    try:
        fd = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return WriteResult(status="collision", job_id=job_id, path=target)
    except OSError:
        return WriteResult(status="write-failed", job_id=job_id)
    try:
        view = memoryview(record_bytes)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                return WriteResult(status="write-failed", job_id=job_id)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    # Read-back and re-validate
    try:
        raw = target.read_bytes()
        if raw != record_bytes:
            return WriteResult(status="written-unverified", job_id=job_id, path=target)
        parsed = json.loads(raw)
        _validate_job_record(parsed)
        if parsed.get("job_id") != job_id:
            return WriteResult(status="written-unverified", job_id=job_id, path=target)
    except Exception:
        return WriteResult(status="written-unverified", job_id=job_id, path=target)
    return WriteResult(status="written", job_id=job_id, path=target)


def read_job_record(workspace: Path, job_id: str) -> ReadResult | None:
    """Read and re-validate a single job record.  Returns None if missing or invalid."""
    target = _record_path(workspace, job_id)
    try:
        raw = target.read_bytes()
    except OSError:
        return None
    try:
        parsed = json.loads(raw)
        _validate_job_record(parsed)
    except Exception:
        return None
    if parsed.get("job_id") != job_id:
        return None
    return ReadResult(job_id=job_id, record=parsed, path=target, bytes=raw)


def read_all_records(workspace: Path) -> list[ReadResult]:
    """Read all valid job records from the workspace dispatch directory.

    Returns records sorted by ``created_at``, skipping and counting
    unreadable or schema-invalid entries rather than raising.
    """
    d = _dispatch_dir(workspace)
    if not d.is_dir():
        return []
    results: list[ReadResult] = []
    for entry in d.iterdir():
        if not entry.suffix == _JOB_RECORD_SUFFIX:
            continue
        job_id = entry.stem
        if not _JOB_ID_RE.match(job_id):
            continue
        rr = read_job_record(workspace, job_id)
        if rr is not None:
            results.append(rr)
    results.sort(key=lambda r: r.record.get("created_at", ""))
    return results


# ---------------------------------------------------------------------------
# Outcome-note reader (R26, KTD11)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoteResult:
    """Outcome of reading an outcome note."""

    status: str  # one of the U1 note-status vocabulary values
    job_id: str
    note: dict[str, Any] | None = None


def read_outcome_note(workspace: Path, job_id: str) -> NoteResult:
    """Read the outcome note for a job, resolving the path from ``job_id`` (R26).

    The target path is ``<job-id>.note.json`` inside the dispatch directory.
    Before opening, fully resolve both the derived note path and the dispatch
    directory, require the resolved note path to be a direct child of the
    resolved dispatch directory, and reject any path whose resolution
    traverses a symlink, junction, or other reparse point (SEC-2).
    """
    derived = _note_path(workspace, job_id)
    dispatch = _dispatch_dir(workspace)

    # --- path gate (must come first per U6 step 2b) ---
    # Walk parent chain BEFORE resolve to detect reparse points (junctions,
    # symlinks) on the path to the dispatch directory.  A junction at
    # .workstream/dispatch/ would follow into its target before containment
    # is checked, so we must refuse before resolving.
    check = derived
    while check != check.parent:  # walk up to filesystem root
        if _is_reparse_point(check):
            return NoteResult(status="path-refused", job_id=job_id)
        check = check.parent
    check = dispatch
    while check != check.parent:
        if _is_reparse_point(check):
            return NoteResult(status="path-refused", job_id=job_id)
        check = check.parent

    try:
        resolved_note = derived.resolve()
        resolved_dispatch = dispatch.resolve()
    except OSError:
        return NoteResult(status="path-refused", job_id=job_id)

    # Containment check: resolved note must be a direct child of resolved dispatch
    if resolved_note.parent != resolved_dispatch:
        return NoteResult(status="path-refused", job_id=job_id)

    # Reparse-point check on each component from dispatch dir down to note
    # Walk from dispatch dir to note, checking each component
    try:
        rel = resolved_note.relative_to(resolved_dispatch)
    except ValueError:
        return NoteResult(status="path-refused", job_id=job_id)

    # Check each path component for reparse points
    check = resolved_dispatch
    for part in rel.parts:
        if _is_reparse_point(check):
            return NoteResult(status="path-refused", job_id=job_id)
        check = check / part
    if _is_reparse_point(check):
        return NoteResult(status="path-refused", job_id=job_id)

    # --- open through the resolved handle ---
    try:
        raw = resolved_note.read_bytes()
    except FileNotFoundError:
        return NoteResult(status="absent", job_id=job_id)
    except OSError:
        return NoteResult(status="unreadable", job_id=job_id)

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return NoteResult(status="unreadable", job_id=job_id)

    if not isinstance(parsed, dict):
        return NoteResult(status="unreadable", job_id=job_id)

    try:
        _validate_outcome_note(parsed)
    except Exception:
        return NoteResult(status="schema-invalid", job_id=job_id)

    if parsed.get("job_id") != job_id:
        return NoteResult(status="mismatched", job_id=job_id)

    # Apply guard to summary content (KTD13)
    from workstream_dispatch.intent import guard_instruction
    summary = parsed.get("summary", "")
    if summary:
        guard = guard_instruction(summary)
        if not guard.passed:
            return NoteResult(status="guard-failed", job_id=job_id)

    return NoteResult(status="present", job_id=job_id, note=parsed)
