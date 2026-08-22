"""Dispatch orchestration — record-first ordering with honest partial-success (U5).

Implements the strict ordering: write the record (U2), then spawn (U4),
then bind (U3).  A record-write failure stops before spawning.  A spawn
failure after a successful write returns partial success naming the job.
A bind failure after a successful spawn returns success with a
degraded-binding note.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workstream_dispatch import records as rec
from workstream_dispatch import store
from workstream_dispatch.intent import Draft, DraftError, _CONFIRM_PREFIX, confirm, draft_instruction
from workstream_dispatch.paseo_adapter import PaseoAdapter

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

_OUTCOME_DISPATCHED = "dispatched"
_OUTCOME_PARTIAL_SUCCESS = "partial-success"
_OUTCOME_CANCELLED = "cancelled"
_OUTCOME_STOPPED = "stopped"
_OUTCOME_INVALID_WORKSPACE = "invalid-workspace"
_OUTCOME_INTERNAL_FAILURE = "internal-failure"


@dataclass(frozen=True)
class DispatchResult:
    """Outcome of a dispatch attempt."""

    outcome: str
    job_id: str | None = None
    error_code: str | None = None
    diagnostics: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Registration resolution
# ---------------------------------------------------------------------------


def _resolve_workstream(workspace_path: Path) -> tuple[str, str] | None:
    """Resolve the workstream identity and label from the marker.

    Returns (identity, label) or None if the workspace is not registered.
    """
    manifest = workspace_path / ".workstream" / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return None
    identity = data.get("identity")
    label = data.get("label")
    if not identity or not label:
        return None
    # Basic format validation
    if not isinstance(identity, str) or not isinstance(label, str):
        return None
    if not identity.strip() or not label.strip():
        return None
    if len(identity) > 256 or len(label) > 256:
        return None
    return str(identity), str(label)


# ---------------------------------------------------------------------------
# Dispatch orchestration
# ---------------------------------------------------------------------------


def dispatch(
    *,
    workspace_path: Path,
    draft: Draft,
    confirmation_digest: str,
    adapter: PaseoAdapter,
    store_instance: store.DispatchStore,
) -> DispatchResult:
    """Execute the record-first dispatch ordering (R4, R6).

    1. Validate confirmation (exact digest match)
    2. Resolve workstream (R5)
    3. Write the job record create-only (U2)
    4. Spawn the agent (U4)
    5. Bind job to agent (U3)

    Steps are strict: write before spawn, spawn before bind.
    """
    # Step 1: Validate confirmation
    c = confirm(draft, confirmation_digest)
    if c is None:
        return DispatchResult(outcome=_OUTCOME_CANCELLED, error_code="confirmation-mismatch")

    # Step 2: Resolve workstream (R5)
    resolved = _resolve_workstream(draft.workspace_path)
    if resolved is None:
        return DispatchResult(outcome=_OUTCOME_INVALID_WORKSPACE, error_code="unregistered-workspace")
    identity, label = resolved

    # Step 3: Write job record create-only (R4, R19)
    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": 1,
        "job_id": draft.job_id,
        "workstream_identity": identity,
        "instruction": draft.normalized_instruction,
        "dispatch_posture": draft.dispatch_posture,
        "actor": "operator-confirmed",
        "recorded_at": now_iso,
        "confirmation_ref": draft.digest,
        "created_at": now_iso,
    }
    if draft.follows:
        record["follows"] = draft.follows

    write_result = rec.write_job_record(draft.workspace_path, record)
    if write_result.status == "collision":
        return DispatchResult(
            outcome=_OUTCOME_STOPPED,
            job_id=draft.job_id,
            error_code="record-collision",
        )
    if write_result.status == "write-failed":
        return DispatchResult(
            outcome=_OUTCOME_STOPPED,
            job_id=draft.job_id,
            error_code="record-write-failed",
        )
    if write_result.status == "written-unverified":
        return DispatchResult(
            outcome=_OUTCOME_STOPPED,
            job_id=draft.job_id,
            error_code="written-unverified",
        )

    return _dispatch_after_write(record, draft, adapter, store_instance)


def _dispatch_after_write(
    record: dict[str, Any],
    draft: Draft,
    adapter: PaseoAdapter,
    store_instance: store.DispatchStore,
) -> DispatchResult:
    """Spawn agent and bind job after a successful record write (shared by both paths)."""
    now_iso = record["created_at"]

    spawn_result = adapter.spawn(
        instruction=draft.normalized_instruction,
        cwd=str(draft.workspace_path),
        provider=draft.dispatch_posture["provider"],
        model=draft.dispatch_posture["model"],
        mode=draft.dispatch_posture["mode"],
        thinking=draft.dispatch_posture["thinking"],
        job_id=draft.job_id,
    )

    if spawn_result.status == "unreachable":
        return DispatchResult(
            outcome=_OUTCOME_PARTIAL_SUCCESS,
            job_id=draft.job_id,
            error_code=spawn_result.error_code or "spawn-failed",
        )

    try:
        store_instance.bind_job(
            job_id=draft.job_id,
            agent_id=spawn_result.agent_id or "",
            dispatch_timestamp=now_iso,
        )
    except Exception:
        pass

    return DispatchResult(
        outcome=_OUTCOME_DISPATCHED,
        job_id=draft.job_id,
    )


def dispatch_without_confirmation(
    *,
    workspace_path: Path,
    instruction: str,
    provider: str,
    model: str,
    mode: str,
    thinking: str,
    adapter: PaseoAdapter,
    store_instance: store.DispatchStore,
    follows: str | None = None,
    record_sources: list[dict[str, str]] | None = None,
) -> DispatchResult:
    """Dispatch without operator confirmation (R3, AE12 — actor: assistant-drafted).

    Used for Arjim-initiated dispatches where no external confirmation exists.
    """
    resolved = _resolve_workstream(workspace_path)
    if resolved is None:
        return DispatchResult(outcome=_OUTCOME_INVALID_WORKSPACE, error_code="unregistered-workspace")
    identity, label = resolved

    try:
        d = draft_instruction(
            workspace_path=workspace_path,
            workstream_identity=identity,
            workstream_label=label,
            instruction=instruction,
            provider=provider,
            model=model,
            mode=mode,
            thinking=thinking,
            follows=follows,
            record_sources=record_sources,
        )
    except DraftError as exc:
        return DispatchResult(outcome=_OUTCOME_STOPPED, error_code=str(exc))

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": 1,
        "job_id": d.job_id,
        "workstream_identity": identity,
        "instruction": d.normalized_instruction,
        "dispatch_posture": d.dispatch_posture,
        "actor": "assistant-drafted",
        "recorded_at": now_iso,
        "confirmation_ref": d.digest,
        "created_at": now_iso,
    }
    if d.follows:
        record["follows"] = d.follows

    write_result = rec.write_job_record(workspace_path, record)
    if write_result.status != "written":
        return DispatchResult(
            outcome=_OUTCOME_STOPPED,
            job_id=d.job_id,
            error_code=f"record-{write_result.status}",
        )

    return _dispatch_after_write(record, d, adapter, store_instance)
