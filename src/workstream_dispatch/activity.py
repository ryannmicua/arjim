"""Activity answer — state derivation, coverage, and change signal (U6).

Produces one consolidated answer whose unknowns are explicit and whose
coverage is stated.  Derives each job's state through the KTD5 table as
the single owner of that mapping; reads outcome notes; computes per-workspace
change signals through the bounded git adapter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workstream_dispatch import records as rec
from workstream_dispatch import store
from workstream_dispatch.git_adapter import capture_git_state
from workstream_dispatch.paseo_adapter import AgentDetail, AgentInfo, PaseoAdapter

# ---------------------------------------------------------------------------
# KTD5 Job-State Derivation Table
# ---------------------------------------------------------------------------

_JOB_STATE_RUNNING = "running"
_JOB_STATE_IDLE = "idle"
_JOB_STATE_NEEDS_OPERATOR = "needs-operator"
_JOB_STATE_NOT_FOUND = "not-found"
_JOB_STATE_UNREACHABLE = "unreachable"
_JOB_STATE_SUPERSEDED = "superseded"
_JOB_STATE_NEVER_DISPATCHED = "never-dispatched"
_JOB_STATE_FAILED = "failed"

_OBSERVED_PASEO_STATUSES = {"running", "idle", "closed", "error"}


def _derive_job_state(
    *,
    binding_exists: bool,
    agent_resolved: bool,
    agent_status: str | None,
    agent_archived: bool,
    has_pending_permissions: bool,
    paseo_reachable: bool,
) -> str:
    """Derive a job's state through the KTD5 table (single owner of R8 mapping)."""
    # unreachable is evaluated first
    if not paseo_reachable:
        return _JOB_STATE_UNREACHABLE

    if not agent_resolved:
        if binding_exists:
            return _JOB_STATE_NOT_FOUND
        return _JOB_STATE_NEVER_DISPATCHED

    # Agent resolved — check pending permissions first
    if has_pending_permissions:
        return _JOB_STATE_NEEDS_OPERATOR

    # Check status
    if agent_archived:
        return _JOB_STATE_SUPERSEDED

    status = (agent_status or "").lower()
    if status == "running":
        return _JOB_STATE_RUNNING
    if status == "idle":
        return _JOB_STATE_IDLE
    if status == "error":
        return _JOB_STATE_FAILED
    if status == "closed":
        return _JOB_STATE_SUPERSEDED
    # Unrecognized status → needs-operator
    return _JOB_STATE_NEEDS_OPERATOR


# ---------------------------------------------------------------------------
# Note resolution
# ---------------------------------------------------------------------------

_NOTE_STATUS_PRESENT = "present"


@dataclass(frozen=True)
class NoteInfo:
    """Resolved outcome note for a job."""

    status: str
    summary: str | None = None
    reported_at: str | None = None


def _resolve_note(workspace: Path, job_id: str) -> NoteInfo:
    """Read and resolve the outcome note for a job (R26)."""
    result = rec.read_outcome_note(workspace, job_id)
    if result.status == "present" and result.note:
        return NoteInfo(
            status=_NOTE_STATUS_PRESENT,
            summary=result.note.get("summary"),
            reported_at=result.note.get("reported_at"),
        )
    return NoteInfo(status=result.status)


# ---------------------------------------------------------------------------
# Activity answer
# ---------------------------------------------------------------------------


@dataclass
class JobAnswer:
    """Per-job answer entry."""

    job_id: str
    workstream_identity: str
    instruction: str
    job_state: str
    note_status: str
    note_summary: str | None = None
    note_reported_at: str | None = None
    unattributable: bool = False


@dataclass
class WorkspaceAnswer:
    """Per-workspace answer entry."""

    workspace_path: str
    workstream_label: str
    jobs: list[JobAnswer] = field(default_factory=list)
    change_signal: str = "bootstrap"  # changed | unchanged | bootstrap | unsupported
    job_dispatched_in_window: bool = False


@dataclass
class ActivityAnswer:
    """Consolidated activity answer (F2)."""

    observation_time: str
    total_workspaces: int
    readable_workspaces: int
    unreachable_paseo: bool
    note_statuses: dict[str, int] = field(default_factory=dict)
    workspaces: list[WorkspaceAnswer] = field(default_factory=list)


def answer_activity(
    *,
    scan_list: list[Path],
    adapter: PaseoAdapter,
    store_instance: store.DispatchStore,
) -> ActivityAnswer:
    """Produce one consolidated activity answer (F2, R7-R12, R17, R26, R31).

    Reads job records from each scanned workspace, resolves each job's agent
    in memory from one batched list call (U4), derives state through the
    KTD5 table, reads outcome notes, computes per-workspace change signals,
    and renders coverage explicitly.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Batched agent listing (one call for all jobs)
    paseo_reachable = adapter.available
    agents_by_label: dict[str, AgentInfo] = {}
    if paseo_reachable:
        try:
            agents = adapter.list_agents()
            for a in agents:
                agents_by_label[f"arjim.job={a.job_id}"] = a
        except Exception:
            paseo_reachable = False

    # Inspect agents only for fields the listing doesn't carry
    inspected: dict[str, AgentDetail] = {}

    total_ws = 0
    readable_ws = 0
    note_status_counts: dict[str, int] = {}
    workspace_answers: list[WorkspaceAnswer] = []

    for ws_path in scan_list:
        total_ws += 1
        ws_str = str(ws_path)

        # Read manifest once per workspace
        manifest_data = _read_manifest(ws_path)
        label = str(manifest_data.get("label", ""))
        current_identity = str(manifest_data.get("identity", ""))

        # Read job records from this workspace
        records = rec.read_all_records(ws_path)
        if not records:
            # Workspace is readable but has no records
            readable_ws += 1
            workspace_answers.append(WorkspaceAnswer(
                workspace_path=ws_str,
                workstream_label=label,
                change_signal=_compute_change_signal(ws_path, store_instance),
            ))
            continue

        readable_ws += 1
        job_answers: list[JobAnswer] = []

        for rr in records:
            record = rr.record
            job_id = record["job_id"]
            recorded_identity = record.get("workstream_identity", "")

            # Check unattributable (R31)
            unattributable = recorded_identity != current_identity

            # Resolve agent
            label_key = f"arjim.job={job_id}"
            agent = agents_by_label.get(label_key)

            # Get binding from store
            binding = store_instance.get_binding(job_id)
            binding_exists = binding is not None

            if agent is not None:
                # Inspect if we need pending permissions or archived flag
                detail = inspected.get(agent.agent_id)
                if detail is None and paseo_reachable:
                    try:
                        detail = adapter.inspect_agent(agent.agent_id)
                    except Exception:
                        detail = None
                    if detail is not None:
                        inspected[agent.agent_id] = detail

                agent_resolved = True
                agent_status = agent.status
                agent_archived = detail.archived if detail else False
                has_pending = detail.has_pending_permissions if detail else False
            else:
                agent_resolved = False
                agent_status = None
                agent_archived = False
                has_pending = False

            job_state = _derive_job_state(
                binding_exists=binding_exists,
                agent_resolved=agent_resolved,
                agent_status=agent_status,
                agent_archived=agent_archived,
                has_pending_permissions=has_pending,
                paseo_reachable=paseo_reachable,
            )

            # Resolve outcome note
            note = _resolve_note(ws_path, job_id)
            note_status_counts[note.status] = note_status_counts.get(note.status, 0) + 1

            job_answers.append(JobAnswer(
                job_id=job_id,
                workstream_identity=recorded_identity,
                instruction=record.get("instruction", ""),
                job_state=job_state,
                note_status=note.status,
                note_summary=note.summary,
                note_reported_at=note.reported_at,
                unattributable=unattributable,
            ))

        # Compute change signal
        change_signal = _compute_change_signal(ws_path, store_instance)

        workspace_answers.append(WorkspaceAnswer(
            workspace_path=ws_str,
            workstream_label=label,
            jobs=job_answers,
            change_signal=change_signal,
        ))

    return ActivityAnswer(
        observation_time=now,
        total_workspaces=total_ws,
        readable_workspaces=readable_ws,
        unreachable_paseo=not paseo_reachable,
        note_statuses=note_status_counts,
        workspaces=workspace_answers,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_manifest(workspace: Path) -> dict[str, Any]:
    """Read and parse the workspace's manifest.json. Returns empty dict on any failure."""
    manifest = workspace / ".workstream" / "manifest.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_workstream_label(workspace: Path) -> str:
    return str(_read_manifest(workspace).get("label", ""))


def _read_workstream_identity(workspace: Path) -> str:
    return str(_read_manifest(workspace).get("identity", ""))


def _compute_change_signal(workspace: Path, store_instance: store.DispatchStore) -> str:
    """Compute per-workspace change signal (KTD6, R12)."""
    git_state = capture_git_state(workspace)
    if git_state is None:
        return "unsupported"

    # Use workspace path as handle
    handle = str(workspace)
    baseline = store_instance.get_baseline(handle)

    if baseline is None:
        # Persist baseline so subsequent calls see it (KTD6)
        now = datetime.now(timezone.utc).isoformat()
        store_instance.set_baseline(handle, git_state.head_oid, git_state.worktree_digest, now)
        return "bootstrap"

    if (git_state.head_oid == baseline["head_oid"]
            and git_state.worktree_digest == baseline["worktree_digest"]):
        return "unchanged"

    # Advance baseline after successful observation
    now = datetime.now(timezone.utc).isoformat()
    store_instance.set_baseline(handle, git_state.head_oid, git_state.worktree_digest, now)
    return "changed"
