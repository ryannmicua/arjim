"""Confirmed unregister for Workstream Registration v1 (U10).

Implements KTD10 (PLAN:195) and protocol section 11: unregister is a confirmed
conditional delete with the presence precondition inverted.

- The unregister draft is a KTD6-style envelope (contract versions, every
  parsed marker field in order, the stable target handle, observed marker
  presence) digested with the same process-ephemeral HMAC key as registration
  (KTD6, PLAN:191; protocol section 5); confirmation is single-use and
  exact-digest.
- The cooperative-writer lock (KTD13, PLAN:198) is established before any
  delete; if cooperation cannot be established within the bounded timeout, the
  operation stops without deleting (``changed-marker-stopped``).
- After lock acquisition the marker is re-read and compared with the
  confirmation, and re-read and compared again immediately before the delete
  (two-phase per PLAN:463); the conditional delete compares once more and
  deletes only on an exact byte match (``filesystem.conditional_delete_marker``).
- Completion requires absence read-back (``unregistered``). Any changed
  marker, target, or identity at any re-read stops without deleting
  (``changed-marker-stopped``); recovery requires a fresh inspection, a new
  unregister draft, and a new confirmation (KTD10; protocol 4.16).
- An absent marker at inspection is a distinct no-write stop (``stopped``): the
  implementation never deletes something that is not there. A confirmation is
  invalidated by any marker-state change (present-absent-present); it never
  deletes a marker that appeared, disappeared, and reappeared with different
  content.
- The frozen v1 result vocabulary (registration-result.schema.json lines
  22-35; PLAN:391, 556) has no unregister delete-succeeded/absence-unverified
  outcome, and protocol section 11 defines completion only via verified
  absence: when the absence read-back cannot be verified after a conditional
  delete, the implementation bounds a retry and then reports
  ``changed-marker-stopped`` (fail closed — a marker that cannot be verified
  absent is treated as changed).
- Duplicates are never auto-resolved (PLAN:542); ``conflict`` is projection
  write-time only. The projection entry may be removed after a verified
  absence (protocol 4.12) as best-effort replaceable state; deleting
  projection state never unregisters (PLAN:319). The marker is authority.

This module never prints or logs its input; it returns structured results
only. Outcomes are the frozen result-vocabulary values.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workstream_registration import diagnostics as diag
from workstream_registration import filesystem as fs
from workstream_registration import registration as reg

__all__ = [
    "ENVELOPE_KIND_UNREGISTER",
    "OUTCOME_CHANGED_MARKER_STOPPED",
    "OUTCOME_UNREGISTERED",
    "UnregisterConfirmation",
    "UnregisterEnvelope",
    "UnregisterEnvelopeError",
    "confirm_unregister",
    "unregister",
    "unregister_envelope",
]

ENVELOPE_KIND_UNREGISTER = "unregister"

OUTCOME_UNREGISTERED = "unregistered"
OUTCOME_CHANGED_MARKER_STOPPED = "changed-marker-stopped"

_ABSENCE_RETRY_ATTEMPTS = 3
_ABSENCE_RETRY_INTERVAL = 0.05

PHASE_READ_BACK = reg.PHASE_READ_BACK
PHASE_OPERATION = reg.PHASE_OPERATION


class UnregisterEnvelopeError(ValueError):
    """An unregister envelope requires a valid supported marker (protocol 4.4)."""


@dataclass(frozen=True)
class UnregisterEnvelope:
    """Canonical unregister intent (protocol 4.4): binds the marker's exact
    bytes, the parsed marker document, the stable target handle, and the
    observed marker presence, digested under the process-ephemeral key."""

    workspace_path: Path
    handle: fs.TargetHandle
    marker: dict[str, Any]
    marker_bytes: bytes
    envelope: bytes
    digest: str

    @property
    def identity(self) -> str:
        return str(self.marker["identity"])


@dataclass
class UnregisterConfirmation:
    """Single-use confirmation bound to one unregister envelope; ``consumed``
    flips on the consuming delete (KTD6, PLAN:191)."""

    digest: str
    envelope: UnregisterEnvelope
    consumed: bool = False


def unregister_envelope(
    workspace_path: Path, *, inspection: reg.Inspection | None = None
) -> UnregisterEnvelope:
    """Draft the unregister intent from a fresh inspection (KTD10, PLAN:195).

    Requires an inspection that found a valid supported marker
    (:class:`UnregisterEnvelopeError` otherwise). The envelope mirrors the
    KTD6 confirmation envelope with the presence precondition inverted:
    contract versions, every parsed marker field in order, the stable target
    handle, and ``observed_marker_presence``. Nothing is deleted.
    """
    if inspection is None:
        inspection = reg.inspect(workspace_path)
    if (
        inspection.state != reg.STATE_LINKED_EXISTING
        or inspection.marker is None
        or inspection.handle is None
        or inspection.marker_bytes is None
    ):
        raise UnregisterEnvelopeError(
            "unregister envelope requires a valid supported marker"
        )
    content: dict[str, Any] = {
        "contract": {
            "marker": reg.MARKER_VERSION,
            "conformance": reg.RESULT_VERSION,
            "protocol": reg.PROTOCOL_VERSION,
        },
        "envelope_kind": ENVELOPE_KIND_UNREGISTER,
        "marker": inspection.marker,
        "target_handle": inspection.handle.to_dict(),
        "observed_marker_presence": True,
    }
    envelope_bytes = json.dumps(
        content, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return UnregisterEnvelope(
        workspace_path=workspace_path,
        handle=inspection.handle,
        marker=inspection.marker,
        marker_bytes=inspection.marker_bytes,
        envelope=envelope_bytes,
        digest=reg.envelope_digest(envelope_bytes),
    )


def confirm_unregister(
    envelope: UnregisterEnvelope, digest: str
) -> UnregisterConfirmation | None:
    """Exact-digest confirmation of an unregister envelope (KTD6, PLAN:191).

    Returns the single-use :class:`UnregisterConfirmation` only when the
    digest matches the in-memory digest; otherwise None (operator rejection or
    digest mismatch — no delete). A digest is never accepted across
    invocations because the HMAC key is process-ephemeral.
    """
    if digest == envelope.digest:
        return UnregisterConfirmation(digest=digest, envelope=envelope)
    return None


def _result(
    outcome: str,
    *,
    validity: str,
    effects: reg.Effects,
    diagnostics: diag.Diagnostics = diag.Diagnostics.empty(),
) -> reg.RegistrationResult:
    return reg.RegistrationResult(
        outcome=outcome,
        validity=validity,
        effects=effects,
        diagnostics=diagnostics,
    )


def _unregistered() -> reg.RegistrationResult:
    """Verified absence after a confirmed conditional delete (AE8, PLAN:133;
    result fixture result-unregistered.json)."""
    return _result(
        OUTCOME_UNREGISTERED,
        validity=reg.VALIDITY_NOT_APPLICABLE,
        effects=reg.Effects(False, True, False, True, False, reg.PROJECTION_NONE),
    )


def _changed_marker_stopped(code: str) -> reg.RegistrationResult:
    return _result(
        OUTCOME_CHANGED_MARKER_STOPPED,
        validity=reg.VALIDITY_NOT_APPLICABLE,
        effects=reg.Effects(False, False, False, False, False, reg.PROJECTION_NONE),
        diagnostics=diag.single(PHASE_OPERATION, code),
    )


def _stopped(code: str) -> reg.RegistrationResult:
    return _result(
        reg.OUTCOME_STOPPED,
        validity=reg.VALIDITY_NOT_APPLICABLE,
        effects=reg.Effects(False, False, False, False, False, reg.PROJECTION_NONE),
        diagnostics=diag.single(PHASE_OPERATION, code),
    )


def _occupied_invalid(inspection: reg.Inspection) -> reg.RegistrationResult:
    return _result(
        reg.OUTCOME_OCCUPIED_INVALID,
        validity=inspection.validity,
        effects=reg.Effects(False, False, False, False, False, reg.PROJECTION_NONE),
        diagnostics=inspection.diagnostics,
    )


def _cancelled(code: str) -> reg.RegistrationResult:
    return _result(
        reg.OUTCOME_CANCELLED,
        validity=reg.VALIDITY_NOT_APPLICABLE,
        effects=reg.Effects(False, False, False, False, False, reg.PROJECTION_NONE),
        diagnostics=diag.single(PHASE_OPERATION, code),
    )


def _mismatch_code(expected: bytes, observed: bytes) -> str:
    """Identity mismatch vs content-only change at a re-read comparison."""
    try:
        observed_doc = json.loads(observed.decode("utf-8"))
        expected_doc = json.loads(expected.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return diag.CODE_MARKER_CHANGED
    if isinstance(observed_doc, dict) and isinstance(expected_doc, dict):
        if observed_doc.get("identity") != expected_doc.get("identity"):
            return diag.CODE_IDENTITY_MISMATCH
    return diag.CODE_MARKER_CHANGED


def _capture_handle_or_stop(workspace_path: Path) -> reg.RegistrationResult | fs.TargetHandle:
    try:
        return fs.capture_target_handle(workspace_path)
    except fs.IdentityUnavailableError:
        return _changed_marker_stopped(diag.CODE_IDENTITY_API_UNAVAILABLE)
    except fs.TargetAliasMismatchError:
        return _changed_marker_stopped(diag.CODE_TARGET_ALIAS_MISMATCH)
    except fs.RedirectedMarkerComponentError:
        return _changed_marker_stopped(diag.CODE_PATH_REDIRECTED)


def _remove_projection(
    identity: str, handle: fs.TargetHandle, projection: Any | None
) -> None:
    """Best-effort projection entry removal after a verified absence.

    Protocol 4.12: the local projection entry may be removed; the projection
    is replaceable state and never an outcome input (PLAN:319). When no
    projection is injected and the default store has never been created, there
    is nothing to remove and no store is created.
    """
    if projection is None:
        from workstream_registration import projection as _proj

        if not _proj.default_store_dir().exists():
            return
        projection = _proj.Projection()
    try:
        projection.remove(identity, handle.to_bytes())
    except Exception:
        pass  # replaceable state; marker authority governs the outcome


def unregister(
    workspace_path: Path,
    confirmation: UnregisterConfirmation | None,
    *,
    lock_timeout: float = reg.DEFAULT_LOCK_TIMEOUT,
    projection: Any | None = None,
) -> reg.RegistrationResult:
    """Confirmed conditional unregister (KTD10 PLAN:195; protocol 4.4-4.5, 11).

    Sequence: confirmation checks (rejected/expired -> ``cancelled``, no
    delete); fresh inspection (missing/inaccessible workspace ->
    ``stopped``; absent marker -> ``stopped``, nothing to delete; invalid
    marker -> ``occupied-invalid``); pre-lock re-read comparison (changed
    marker/target/identity -> ``changed-marker-stopped``, no delete);
    cooperative-writer lock (unobtainable -> ``changed-marker-stopped``, no
    delete); post-lock re-read comparison; pre-delete re-read comparison;
    conditional delete on the exact bound bytes; absence read-back
    (``unregistered``). The confirmation is consumed only after the pre-lock
    revalidation, and the lock is released on normal and exceptional exit.
    """
    if confirmation is None:
        return _cancelled(diag.CODE_CONFIRMATION_REJECTED)
    if confirmation.consumed:
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    envelope = confirmation.envelope
    if envelope.workspace_path != workspace_path:
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    inspection = reg.inspect(workspace_path)
    if inspection.state == reg.STATE_STOPPED:
        code = (
            inspection.diagnostics.items[0].code
            if inspection.diagnostics.count
            else diag.CODE_SAFE_INTERNAL_ERROR
        )
        return _stopped(code)
    if inspection.state == reg.STATE_OCCUPIED_INVALID:
        return _occupied_invalid(inspection)
    if inspection.state == reg.STATE_DRAFT_READY:
        return _stopped(diag.CODE_MARKER_INVALID)
    if inspection.handle is None or inspection.marker_bytes is None:
        return _stopped(diag.CODE_SAFE_INTERNAL_ERROR)
    current_handle = inspection.handle
    if current_handle != envelope.handle:
        return _changed_marker_stopped(diag.CODE_TARGET_CHANGED)
    if inspection.marker_bytes != envelope.marker_bytes:
        return _changed_marker_stopped(
            _mismatch_code(envelope.marker_bytes, inspection.marker_bytes)
        )
    confirmation.consumed = True
    try:
        with fs.registration_lock(
            workspace_path, current_handle, recover_stale=True, timeout=lock_timeout
        ) as _owner:
            locked_handle = _capture_handle_or_stop(workspace_path)
            if isinstance(locked_handle, reg.RegistrationResult):
                return locked_handle
            if locked_handle != envelope.handle:
                return _changed_marker_stopped(diag.CODE_TARGET_CHANGED)
            try:
                post_lock = fs.read_marker(workspace_path)
            except fs.ReadBackFailedError:
                return _changed_marker_stopped(diag.CODE_READ_BACK_FAILED)
            if post_lock != envelope.marker_bytes:
                return _changed_marker_stopped(
                    _mismatch_code(envelope.marker_bytes, post_lock)
                )
            try:
                pre_delete = fs.read_marker(workspace_path)
            except fs.ReadBackFailedError:
                return _changed_marker_stopped(diag.CODE_READ_BACK_FAILED)
            if pre_delete != envelope.marker_bytes:
                return _changed_marker_stopped(
                    _mismatch_code(envelope.marker_bytes, pre_delete)
                )
            if not fs.conditional_delete_marker(workspace_path, envelope.marker_bytes):
                return _changed_marker_stopped(diag.CODE_MARKER_CHANGED)
            for _attempt in range(_ABSENCE_RETRY_ATTEMPTS):
                if fs.verify_marker_absent(workspace_path):
                    _remove_projection(envelope.identity, envelope.handle, projection)
                    return _unregistered()
                time.sleep(_ABSENCE_RETRY_INTERVAL)
            return _changed_marker_stopped(diag.CODE_ABSENCE_READ_BACK_FAILED)
    except fs.LockUnavailableError:
        return _changed_marker_stopped(diag.CODE_LOCK_UNAVAILABLE)
