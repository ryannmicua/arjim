"""Registration lifecycle orchestration for Workstream Registration v1 (U9).

Implements the F1-F5 lifecycle (PLAN:451): ``inspect`` -> ``draft`` ->
``confirm`` -> create-only write -> read-back -> exact-identity verify ->
link (projection hook). Reuses U7's raw guard (``raw_guard``), U8's bundled
schema validation and bounded diagnostics (``validation``, ``diagnostics``),
and U9's filesystem primitives (``filesystem``).

Lifecycle rules implemented here (KTD6 PLAN:191, KTD7 PLAN:192, KTD13
PLAN:198, PLAN:451):

- Inspection is read-only and reports the stable target handle, the observed
  marker state, the ``.workstream`` parent state, and a bounded outcome state
  (``draft-ready``, ``linked-existing``, ``occupied-invalid``, ``stopped``).
  Missing, inaccessible, and non-directory workspaces stop with bounded
  diagnostics; redirected marker components, target-alias mismatches, and
  unavailable identity APIs fail closed.
- The draft is the canonical KTD6 confirmation envelope: contract versions,
  every parsed marker field in order, the stable target handle (``ABSENT``
  sentinel or parent identity), observed marker absence, and the explicit
  parent transition (``ABSENT -> created-parent-identity`` or the
  no-transition retry variant). The HMAC-SHA-256 digest uses a
  process-ephemeral key; the key and digest are never persisted or logged.
- Confirmation is single-use and exact-digest; a new inspection, a second
  write attempt, a terminal transition, or a marker-state change expires an
  unused confirmation. Consumption happens only after pre-write revalidation
  and the expected parent transition succeed.
- The write is create-only with exclusive-create semantics, complete bounded
  write, flush, ``os.fsync``, close; read-back re-runs the raw guard and
  schema validation and verifies the exact identity (marker identity equals
  the confirmed identity — never regenerated) plus the read-back target
  handle. Read-back failure reports ``written-unverified``.
- ``register`` on a workspace with a supported valid marker degrades to
  linking (``linked-existing``, no confirmation, no write).
- An invalid/partial/unsupported marker reports ``occupied-invalid`` and is
  never overwritten; resolution is a separate bounded envelope
  (:func:`resolution_envelope`) confirmed in-process
  (:func:`confirm_resolution`), then :func:`resolve_invalid` deletes after
  active/stale lock checks and a confirmed target-handle match
  (``invalid-marker-resolved`` or ``invalid-deleted-unverified``).
- The projection boundary is :func:`set_projection_hook`; the hook receives a
  frozen :class:`ProjectionInput` and returns a :class:`ProjectionResult`.
  U10 owns the real projection; an unset hook maps a completed write to
  ``registered-unlinked``. A projection conflict maps to ``conflict``.

Outcomes are the frozen result-vocabulary values; there is deliberately no
``invalid-marker`` outcome (PLAN:556). This module never prints or logs its
input; it returns structured results only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from workstream_registration import diagnostics as diag
from workstream_registration import filesystem as fs
from workstream_registration import raw_guard as rg
from workstream_registration import validation as vd

__all__ = [
    "Confirmation",
    "ConfirmationExpiredError",
    "Draft",
    "DraftInputError",
    "Effects",
    "Inspection",
    "ProjectionInput",
    "ProjectionResult",
    "RegistrationResult",
    "ResolutionEnvelope",
    "ResolutionEnvelopeError",
    "VALIDITY_NOT_APPLICABLE",
    "confirm",
    "confirm_resolution",
    "draft",
    "envelope_digest",
    "get_projection_hook",
    "inspect",
    "inspection_result",
    "link",
    "register",
    "register_interactive",
    "resolution_envelope",
    "resolve_invalid",
    "set_projection_hook",
]

PROTOCOL_VERSION = "workstream-registration/v1"
RESULT_VERSION = vd.SUPPORTED_RESULT_VERSION
MARKER_VERSION = vd.SUPPORTED_MARKER_VERSION

VALIDITY_NOT_APPLICABLE = "not-applicable"

# Diagnostic phases (closed enum, registration-result.schema.json lines
# 838-851); diagnostics.py exports only PHASE_SCHEMA, so the operational
# phases are named here.
PHASE_WRITE = "write"
PHASE_READ_BACK = "read-back"
PHASE_LINK = "link"
PHASE_PROJECTION = "projection"
PHASE_OPERATION = "operation"

PROJECTION_LINKED = "linked"
PROJECTION_UNLINKED = "unlinked"
PROJECTION_CONFLICT = "conflict"
PROJECTION_NONE = "none"

OUTCOME_REGISTERED = "registered"
OUTCOME_LINKED_EXISTING = "linked-existing"
OUTCOME_CANCELLED = "cancelled"
OUTCOME_STOPPED = "stopped"
OUTCOME_WRITTEN_UNVERIFIED = "written-unverified"
OUTCOME_REGISTERED_UNLINKED = "registered-unlinked"
OUTCOME_OCCUPIED_INVALID = "occupied-invalid"
OUTCOME_INVALID_MARKER_RESOLVED = "invalid-marker-resolved"
OUTCOME_INVALID_DELETED_UNVERIFIED = "invalid-deleted-unverified"
OUTCOME_CONFLICT = "conflict"

STATE_DRAFT_READY = "draft-ready"
STATE_LINKED_EXISTING = "linked-existing"
STATE_OCCUPIED_INVALID = "occupied-invalid"
STATE_STOPPED = "stopped"

MARKER_STATE_ABSENT = "absent"
MARKER_STATE_VALID = "valid"
MARKER_STATE_INVALID = "invalid"
MARKER_STATE_UNSUPPORTED = "unsupported"
MARKER_STATE_PARTIAL = "partial"
MARKER_STATE_UNKNOWN = "unknown"

TRANSITION_ABSENT_TO_CREATED = "ABSENT->created"
TRANSITION_NONE = "none"

DEFAULT_LOCK_TIMEOUT = 2.0

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

# Process-ephemeral HMAC key (KTD6, PLAN:191): generated once per process,
# never persisted, never logged, never exposed through any result or draft.
_ENVELOPE_KEY: bytes | None = None

_projection_hook: Callable[[ProjectionInput], ProjectionResult] | None = None


class DraftInputError(ValueError):
    """The draft inputs cannot produce a schema-valid marker envelope."""

    def __init__(self, diagnostics: diag.Diagnostics) -> None:
        super().__init__("draft input invalid")
        self.diagnostics = diagnostics


class ResolutionEnvelopeError(ValueError):
    """A resolution envelope requires an occupied-invalid inspection."""


class ConfirmationExpiredError(RuntimeError):
    """A single-use confirmation was already consumed or bound elsewhere."""


def envelope_digest(envelope: bytes) -> str:
    """HMAC-SHA-256 digest of a canonical envelope under the ephemeral key."""
    return hmac.new(_key(), envelope, hashlib.sha256).hexdigest()


def _key() -> bytes:
    global _ENVELOPE_KEY
    if _ENVELOPE_KEY is None:
        _ENVELOPE_KEY = secrets.token_bytes(32)
    return _ENVELOPE_KEY


@dataclass(frozen=True)
class Effects:
    """Structural write/read-back/link effects (PLAN:389)."""

    marker_written: bool
    marker_deleted: bool
    read_back_verified: bool
    absence_verified: bool
    linked: bool
    projection: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_written": self.marker_written,
            "marker_deleted": self.marker_deleted,
            "read_back_verified": self.read_back_verified,
            "absence_verified": self.absence_verified,
            "linked": self.linked,
            "projection": self.projection,
        }


@dataclass(frozen=True)
class RegistrationResult:
    """Stable result envelope (registration-result.schema.json shape, PLAN:391).

    ``identity`` is carried only when verified (valid-class marker with a
    verified read-back). Diagnostics are bounded (KTD12, PLAN:197); the
    envelope never carries record-source URI content or secrets.
    """

    outcome: str
    validity: str
    effects: Effects
    identity: str | None = None
    diagnostics: diag.Diagnostics = diag.Diagnostics.empty()
    version: int = RESULT_VERSION

    def to_dict(self) -> dict[str, Any]:
        envelope: dict[str, Any] = {
            "version": self.version,
            "outcome": self.outcome,
            "validity": self.validity,
            "effects": self.effects.to_dict(),
        }
        if self.identity is not None:
            envelope["identity"] = self.identity
        if self.diagnostics.count:
            envelope["diagnostics"] = self.diagnostics.to_dict()
        return envelope

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class Inspection:
    """Read-only inspection observation (protocol section 4.1).

    ``state`` is the inspection-adjacent state reached; ``handle`` is the
    stable target handle (``None`` only when inspection stopped); ``marker``
    is the parsed valid marker document (present only when valid);
    ``marker_bytes`` is the raw bounded marker content (present only when a
    marker was observed). Nothing is written.
    """

    state: str
    handle: fs.TargetHandle | None
    parent_state: str
    marker_state: str
    workspace_path: Path | None = None
    marker_identity: str | None = None
    marker_bytes: bytes | None = None
    marker: dict[str, Any] | None = None
    validity: str = VALIDITY_NOT_APPLICABLE
    diagnostics: diag.Diagnostics = diag.Diagnostics.empty()


@dataclass(frozen=True)
class Draft:
    """The canonical KTD6 confirmation envelope (PLAN:191).

    ``envelope`` is the canonical serialized envelope; ``digest`` is the
    HMAC-SHA-256 digest under the process-ephemeral key. ``parent_transition``
    is ``ABSENT->created`` for a first registration or ``none`` for the
    no-transition retry variant (PLAN:552).
    """

    workspace_path: Path
    handle: fs.TargetHandle
    marker: dict[str, Any]
    parent_transition: str
    envelope: bytes
    digest: str

    @property
    def identity(self) -> str:
        return str(self.marker["identity"])

    @property
    def label(self) -> str:
        return str(self.marker["label"])


@dataclass
class Confirmation:
    """Single-use confirmation bound to one draft or resolution envelope.

    ``consumed`` flips on the consuming write; a second use raises or is
    reported as expired (KTD6, PLAN:191). Not frozen because consumption is a
    lifecycle transition of the confirmation itself.
    """

    digest: str
    draft: Draft | None = None
    resolution: "ResolutionEnvelope | None" = None
    consumed: bool = False


@dataclass(frozen=True)
class ResolutionEnvelope:
    """Bounded ``resolve-invalid`` envelope (PLAN:451, 475): marker-component
    identity, bounded byte length and digest, target handle, and current lock
    status; displayed and confirmed within the same process."""

    workspace_path: Path
    handle: fs.TargetHandle
    marker_identity: str | None
    marker_length: int
    marker_digest: bytes
    lock_status: str
    envelope: bytes
    digest: str


@dataclass(frozen=True)
class ProjectionInput:
    """Typed input handed to the projection hook (PLAN:451, 463)."""

    identity: str
    label: str
    marker_version: str
    target_handle: bytes
    workspace_path: Path
    ordinal: int


@dataclass(frozen=True)
class ProjectionResult:
    """Projection boundary result (PLAN:463)."""

    status: str
    identity: str | None = None
    target_handle: bytes | None = None
    ordinal: int | None = None


def set_projection_hook(fn: Callable[[ProjectionInput], ProjectionResult] | None) -> None:
    """Wire the projection hook; U10 owns the real projection implementation.

    Pass ``None`` to unset. An unset hook maps a completed verified write to
    ``registered-unlinked`` (PLAN:451); linking without a hook stops.
    """
    global _projection_hook
    _projection_hook = fn


def get_projection_hook() -> Callable[[ProjectionInput], ProjectionResult] | None:
    return _projection_hook


def _marker_present(workspace_path: Path) -> bool:
    try:
        os.stat(fs.marker_path(workspace_path))
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _inspection_stopped(code: str, label: str) -> Inspection:
    return Inspection(
        state=STATE_STOPPED,
        handle=None,
        parent_state=MARKER_STATE_UNKNOWN,
        marker_state=MARKER_STATE_UNKNOWN,
        validity=VALIDITY_NOT_APPLICABLE,
        diagnostics=diag.single(PHASE_OPERATION, code),
    )


def _inspection_for(
    state: str,
    *,
    workspace_path: Path,
    handle: fs.TargetHandle | None = None,
    parent_state: str = MARKER_STATE_UNKNOWN,
    marker_state: str = MARKER_STATE_UNKNOWN,
    marker_identity: str | None = None,
    marker_bytes: bytes | None = None,
    marker: dict[str, Any] | None = None,
    validity: str = VALIDITY_NOT_APPLICABLE,
    diagnostics: diag.Diagnostics = diag.Diagnostics.empty(),
) -> Inspection:
    return Inspection(
        state=state,
        handle=handle,
        parent_state=parent_state,
        marker_state=marker_state,
        workspace_path=workspace_path,
        marker_identity=marker_identity,
        marker_bytes=marker_bytes,
        marker=marker,
        validity=validity,
        diagnostics=diagnostics,
    )


def inspect(workspace_path: Path) -> Inspection:
    """Read-only inspection (protocol 4.1; PLAN:451).

    Captures the stable target handle, the observed marker presence/validity
    (raw guard + Draft 2020-12 + version dispatch), and the marker identity.
    Missing, inaccessible, or non-directory workspaces, redirected marker
    components, target-alias mismatches, and unavailable identity APIs stop
    with bounded diagnostics and no write.
    """
    try:
        st = os.stat(workspace_path)
    except FileNotFoundError:
        return _inspection_stopped(diag.CODE_WORKSPACE_INACCESSIBLE, "workspace missing")
    except OSError:
        return _inspection_stopped(diag.CODE_WORKSPACE_INACCESSIBLE, "workspace inaccessible")
    if not _is_dir(st):
        return _inspection_stopped(
            diag.CODE_WORKSPACE_INACCESSIBLE, "workspace is not a directory"
        )
    try:
        handle = fs.capture_target_handle(workspace_path)
    except fs.IdentityUnavailableError:
        return _inspection_stopped(diag.CODE_IDENTITY_API_UNAVAILABLE, "identity APIs unavailable")
    except fs.TargetAliasMismatchError:
        return _inspection_stopped(diag.CODE_TARGET_ALIAS_MISMATCH, "target alias mismatch")
    except fs.RedirectedMarkerComponentError:
        return _inspection_stopped(diag.CODE_PATH_REDIRECTED, "redirected marker component")
    parent_state = "present" if not handle.parent_absent else "absent"
    if not _marker_present(workspace_path):
        return _inspection_for(
            STATE_DRAFT_READY,
            workspace_path=workspace_path,
            handle=handle,
            parent_state=parent_state,
            marker_state=MARKER_STATE_ABSENT,
        )
    try:
        raw = fs.read_marker(workspace_path)
    except fs.ReadBackFailedError:
        return _inspection_for(
            STATE_OCCUPIED_INVALID,
            workspace_path=workspace_path,
            handle=handle,
            parent_state=parent_state,
            marker_state=MARKER_STATE_INVALID,
            validity=vd.VALIDITY_INVALID,
            diagnostics=diag.single(PHASE_READ_BACK, diag.CODE_READ_BACK_FAILED),
        )
    return _classify_marker(workspace_path, handle, parent_state, raw)


def _is_dir(st: os.stat_result) -> bool:
    import stat

    return stat.S_ISDIR(st.st_mode)


def _classify_marker(
    workspace_path: Path, handle: fs.TargetHandle, parent_state: str, raw: bytes
) -> Inspection:
    """Raw guard -> parse -> version dispatch -> schema validation (U7/U8)."""
    guard = rg.guard(raw)
    if not guard.passed:
        return _inspection_for(
            STATE_OCCUPIED_INVALID,
            workspace_path=workspace_path,
            handle=handle,
            parent_state=parent_state,
            marker_state=MARKER_STATE_PARTIAL,
            marker_bytes=raw,
            validity=vd.VALIDITY_INVALID,
            diagnostics=diag.from_guard_result(guard.phase, guard.code),
        )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _inspection_for(
            STATE_OCCUPIED_INVALID,
            workspace_path=workspace_path,
            handle=handle,
            parent_state=parent_state,
            marker_state=MARKER_STATE_PARTIAL,
            marker_bytes=raw,
            validity=vd.VALIDITY_INVALID,
            diagnostics=diag.single(vd.PHASE_SCHEMA, diag.CODE_SCHEMA_INVALID),
        )
    if not isinstance(parsed, dict):
        return _inspection_for(
            STATE_OCCUPIED_INVALID,
            workspace_path=workspace_path,
            handle=handle,
            parent_state=parent_state,
            marker_state=MARKER_STATE_INVALID,
            marker_bytes=raw,
            validity=vd.VALIDITY_INVALID,
            diagnostics=diag.single(vd.PHASE_SCHEMA, diag.CODE_SCHEMA_INVALID),
        )
    vres = vd.validate_marker(parsed)
    if not vres.valid:
        if vres.code == diag.CODE_UNSUPPORTED_VERSION:
            marker_state = MARKER_STATE_UNSUPPORTED
        else:
            marker_state = MARKER_STATE_INVALID
        return _inspection_for(
            STATE_OCCUPIED_INVALID,
            workspace_path=workspace_path,
            handle=handle,
            parent_state=parent_state,
            marker_state=marker_state,
            marker_identity=_extract_identity(parsed),
            marker_bytes=raw,
            validity=vd.VALIDITY_INVALID,
            diagnostics=vres.diagnostics,
        )
    return _inspection_for(
        STATE_LINKED_EXISTING,
        workspace_path=workspace_path,
        handle=handle,
        parent_state=parent_state,
        marker_state=MARKER_STATE_VALID,
        marker_identity=str(parsed["identity"]),
        marker_bytes=raw,
        marker=parsed,
        validity=vd.VALIDITY_VALID,
    )


def _extract_identity(parsed: Any) -> str | None:
    """Best-effort bounded marker-component identity for the resolution preview."""
    if not isinstance(parsed, dict):
        return None
    identity = parsed.get("identity")
    if isinstance(identity, str) and _UUID_RE.fullmatch(identity):
        return identity
    return None


def _build_envelope(
    marker: dict[str, Any],
    handle: fs.TargetHandle,
    parent_transition: str,
) -> bytes:
    """Canonical KTD6 envelope: contract versions, every parsed marker field
    in order, the stable target handle, observed marker absence, and the
    explicit parent transition. Built in fixed insertion order; duplicate keys
    are structurally impossible (the envelope is constructed, not parsed)."""
    envelope: dict[str, Any] = {
        "contract": {
            "marker": MARKER_VERSION,
            "conformance": RESULT_VERSION,
            "protocol": PROTOCOL_VERSION,
        },
        "marker": marker,
        "target_handle": handle.to_dict(),
        "observed_marker_absence": True,
        "parent_transition": parent_transition,
    }
    text = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def _marker_to_bytes(marker: dict[str, Any]) -> bytes:
    return json.dumps(marker, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def draft(
    workspace_path: Path,
    *,
    label: str,
    record_sources: list[dict[str, str]],
    kind: str = "direct",
    inspection: Inspection | None = None,
) -> Draft:
    """Build the canonical KTD6 confirmation envelope (PLAN:191; PLAN:451).

    Produces the marker document (version, generated identity, label, kind,
    literal ``.`` workspace reference, record sources in declared order),
    validates it through the raw guard and bundled schema (a non-conforming
    draft raises :class:`DraftInputError`), and binds the stable target handle
    and observed marker absence. The ``ABSENT -> created-parent-identity``
    transition is represented explicitly when the parent was absent at
    inspection; an existing parent with no marker carries the no-transition
    retry variant instead (PLAN:552).
    """
    if inspection is None:
        inspection = inspect(workspace_path)
    if inspection.state != STATE_DRAFT_READY or inspection.handle is None:
        raise DraftInputError(
            diag.single(PHASE_OPERATION, diag.CODE_MARKER_INVALID)
        )
    marker: dict[str, Any] = {
        "version": MARKER_VERSION,
        "identity": str(uuid.uuid4()),
        "label": label,
        "kind": kind,
        "workspace": ".",
        "record_sources": [dict(item) for item in record_sources],
    }
    text = json.dumps(marker, separators=(",", ":"), ensure_ascii=False)
    guard = rg.guard_decoded_text(text)
    if not guard.passed:
        raise DraftInputError(diag.from_guard_result(guard.phase, guard.code))
    vres = vd.validate_marker(marker)
    if not vres.valid:
        raise DraftInputError(vres.diagnostics)
    handle = inspection.handle
    transition = (
        TRANSITION_ABSENT_TO_CREATED if handle.parent_absent else TRANSITION_NONE
    )
    envelope = _build_envelope(marker, handle, transition)
    return Draft(
        workspace_path=workspace_path,
        handle=handle,
        marker=marker,
        parent_transition=transition,
        envelope=envelope,
        digest=envelope_digest(envelope),
    )


def confirm(draft: Draft, digest: str) -> Confirmation | None:
    """Exact-digest confirmation (KTD6, PLAN:191).

    Returns the single-use :class:`Confirmation` only when ``digest`` equals
    the draft's in-memory digest; otherwise returns None (operator rejection
    or digest mismatch — no write). A digest is never accepted across
    invocations because the HMAC key is process-ephemeral.
    """
    if digest == draft.digest:
        return Confirmation(digest=digest, draft=draft)
    return None


def confirm_resolution(
    envelope: ResolutionEnvelope, digest: str
) -> Confirmation | None:
    """Exact-digest confirmation of a ``resolve-invalid`` envelope."""
    if digest == envelope.digest:
        return Confirmation(digest=digest, resolution=envelope)
    return None


def _result(
    outcome: str,
    *,
    validity: str,
    effects: Effects,
    identity: str | None = None,
    diagnostics: diag.Diagnostics = diag.Diagnostics.empty(),
) -> RegistrationResult:
    return RegistrationResult(
        outcome=outcome,
        validity=validity,
        effects=effects,
        identity=identity,
        diagnostics=diagnostics,
    )


def _no_effect_result(outcome: str, validity: str) -> RegistrationResult:
    return _result(
        outcome,
        validity=validity,
        effects=Effects(False, False, False, False, False, PROJECTION_NONE),
    )


def _cancelled(code: str) -> RegistrationResult:
    return _result(
        OUTCOME_CANCELLED,
        validity=VALIDITY_NOT_APPLICABLE,
        effects=Effects(False, False, False, False, False, PROJECTION_NONE),
        diagnostics=diag.single(PHASE_OPERATION, code),
    )


def _stopped(code: str, label: str | None = None) -> RegistrationResult:
    diagnostics = diag.single(PHASE_OPERATION, code)
    return _result(
        OUTCOME_STOPPED,
        validity=VALIDITY_NOT_APPLICABLE,
        effects=Effects(False, False, False, False, False, PROJECTION_NONE),
        diagnostics=diagnostics,
    )


def _written_unverified(code: str) -> RegistrationResult:
    return _result(
        OUTCOME_WRITTEN_UNVERIFIED,
        validity=VALIDITY_NOT_APPLICABLE,
        effects=Effects(True, False, False, False, False, PROJECTION_NONE),
        diagnostics=diag.single(PHASE_READ_BACK, code),
    )


def _occupied_invalid(diagnostics: diag.Diagnostics) -> RegistrationResult:
    return _result(
        OUTCOME_OCCUPIED_INVALID,
        validity=vd.VALIDITY_INVALID,
        effects=Effects(False, False, False, False, False, PROJECTION_NONE),
        diagnostics=diagnostics,
    )


def _invalid_marker_resolved() -> RegistrationResult:
    return _result(
        OUTCOME_INVALID_MARKER_RESOLVED,
        validity=VALIDITY_NOT_APPLICABLE,
        effects=Effects(False, True, False, True, False, PROJECTION_NONE),
    )


def inspection_result(inspection: Inspection) -> RegistrationResult:
    """Map an inspection to its result-surface outcome (U11 surface)."""
    if inspection.state == STATE_STOPPED:
        code = (
            inspection.diagnostics.items[0].code
            if inspection.diagnostics.count
            else diag.CODE_SAFE_INTERNAL_ERROR
        )
        return _stopped(code)
    if inspection.state == STATE_OCCUPIED_INVALID:
        return _occupied_invalid(inspection.diagnostics)
    if inspection.state == STATE_LINKED_EXISTING:
        if (
            inspection.handle is None
            or inspection.marker is None
            or inspection.workspace_path is None
        ):
            return _stopped(diag.CODE_SAFE_INTERNAL_ERROR)
        return _project(
            inspection.handle,
            identity=str(inspection.marker["identity"]),
            label=str(inspection.marker["label"]),
            marker_version=str(inspection.marker["version"]),
            workspace_path=inspection.workspace_path,
            ordinal=0,
            written=False,
            link_mode=True,
        )
    return _no_effect_result(OUTCOME_STOPPED, VALIDITY_NOT_APPLICABLE)


def _project(
    handle: fs.TargetHandle,
    *,
    identity: str,
    label: str,
    marker_version: str,
    workspace_path: Path,
    ordinal: int,
    written: bool,
    link_mode: bool,
) -> RegistrationResult:
    """Run the projection hook and map its result onto the outcome vocabulary."""
    hook = _projection_hook
    if hook is None:
        if written:
            return _result(
                OUTCOME_REGISTERED_UNLINKED,
                validity=vd.VALIDITY_VALID,
                effects=Effects(True, False, True, False, False, PROJECTION_UNLINKED),
                identity=identity,
                diagnostics=diag.single(PHASE_PROJECTION, diag.CODE_PROJECTION_LINK_FAILED),
            )
        return _stopped(diag.CODE_PROJECTION_LINK_FAILED, "projection hook not set")
    project_input = ProjectionInput(
        identity=identity,
        label=label,
        marker_version=marker_version,
        target_handle=handle.to_bytes(),
        workspace_path=workspace_path,
        ordinal=ordinal,
    )
    try:
        result = hook(project_input)
        status = result.status if isinstance(result, ProjectionResult) else "projection-failed"
    except Exception:
        status = "projection-failed"
    if status == PROJECTION_LINKED:
        if link_mode:
            return _result(
                OUTCOME_LINKED_EXISTING,
                validity=vd.VALIDITY_VALID,
                effects=Effects(False, False, True, False, True, PROJECTION_LINKED),
                identity=identity,
            )
        return _result(
            OUTCOME_REGISTERED,
            validity=vd.VALIDITY_VALID,
            effects=Effects(True, False, True, False, True, PROJECTION_LINKED),
            identity=identity,
        )
    if status == PROJECTION_CONFLICT:
        return _result(
            OUTCOME_CONFLICT,
            validity=vd.VALIDITY_VALID,
            effects=Effects(
                written, False, True, False, False, PROJECTION_CONFLICT
            ),
            identity=identity,
            diagnostics=diag.single(PHASE_PROJECTION, diag.CODE_PROJECTION_CONFLICT),
        )
    if written:
        return _result(
            OUTCOME_REGISTERED_UNLINKED,
            validity=vd.VALIDITY_VALID,
            effects=Effects(True, False, True, False, False, PROJECTION_UNLINKED),
            identity=identity,
            diagnostics=diag.single(PHASE_PROJECTION, diag.CODE_PROJECTION_LINK_FAILED),
        )
    return _stopped(diag.CODE_PROJECTION_LINK_FAILED, "projection link failed")


def _capture_or_stop(workspace_path: Path) -> RegistrationResult | fs.TargetHandle:
    try:
        return fs.capture_target_handle(workspace_path)
    except fs.IdentityUnavailableError:
        return _stopped(diag.CODE_IDENTITY_API_UNAVAILABLE)
    except fs.TargetAliasMismatchError:
        return _stopped(diag.CODE_TARGET_ALIAS_MISMATCH)
    except fs.RedirectedMarkerComponentError:
        return _stopped(diag.CODE_PATH_REDIRECTED)


def register(
    workspace_path: Path,
    draft: Draft,
    confirmation: Confirmation | None,
    *,
    ordinal: int = 0,
    lock_timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> RegistrationResult:
    """Orchestrated registration lifecycle (F1, PLAN:451; KTD13, PLAN:198).

    Revalidates the workspace identity and marker absence, checks the expected
    parent transition (``ABSENT -> created`` or the no-transition variant),
    consumes the single-use confirmation, acquires the per-workspace lock
    (atomic absent-parent step), writes the marker create-only, flushes,
    syncs, closes, reopens, re-runs raw+schema validation, verifies the exact
    identity and the read-back target handle, and hands a typed
    :class:`ProjectionInput` to the projection hook. The lock is released on
    normal and exceptional exit. An expired or second-use confirmation stops
    with ``cancelled``; read-back failure reports ``written-unverified`` and
    never regenerates the identity.
    """
    if confirmation is None:
        return _cancelled(diag.CODE_CONFIRMATION_REJECTED)
    if confirmation.consumed:
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    if confirmation.draft is not draft or draft.workspace_path != workspace_path:
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    current_handle = _capture_or_stop(workspace_path)
    if isinstance(current_handle, RegistrationResult):
        return current_handle
    if current_handle.workspace != draft.handle.workspace:
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    if _marker_present(workspace_path):
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    parent = fs.parent_path(workspace_path)
    if draft.handle.parent_absent:
        if parent.exists():
            return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    else:
        if not parent.exists():
            return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
        parent_handle = _capture_or_stop(workspace_path)
        if isinstance(parent_handle, RegistrationResult):
            return parent_handle
        if parent_handle.parent != draft.handle.parent:
            return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    marker_bytes = _marker_to_bytes(draft.marker)
    confirmation.consumed = True
    try:
        with fs.registration_lock(
            workspace_path, current_handle, recover_stale=True, timeout=lock_timeout
        ) as _owner:
            if draft.handle.parent_absent:
                created_handle = _capture_or_stop(workspace_path)
                if isinstance(created_handle, RegistrationResult):
                    return created_handle
                if created_handle.parent is None:
                    return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
                if created_handle.workspace != draft.handle.workspace:
                    return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
                expected_handle = fs.TargetHandle(
                    workspace=created_handle.workspace, parent=created_handle.parent
                )
            else:
                expected_handle = current_handle
            try:
                fs.write_marker_create_only(workspace_path, marker_bytes, current_handle)
            except fs.CreateCollisionError:
                return _collision_result(workspace_path, current_handle, ordinal)
            except fs.WriteFailedError:
                return _stopped(diag.CODE_WRITE_FAILED)
            return _readback_and_project(
                workspace_path, draft, expected_handle, ordinal
            )
    except fs.LockUnavailableError:
        return _stopped(diag.CODE_LOCK_UNAVAILABLE)


def _collision_result(
    workspace_path: Path, handle: fs.TargetHandle, ordinal: int
) -> RegistrationResult:
    """Exclusive-create collision: read the existing marker; a valid supported
    marker degrades to linking, anything else is occupied and never
    overwritten (R4, PLAN:96; KTD13, PLAN:198)."""
    try:
        raw = fs.read_marker(workspace_path)
    except fs.ReadBackFailedError:
        return _occupied_invalid(
            diag.single(PHASE_READ_BACK, diag.CODE_READ_BACK_FAILED)
        )
    guard = rg.guard(raw)
    if not guard.passed:
        return _occupied_invalid(diag.from_guard_result(guard.phase, guard.code))
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _occupied_invalid(
            diag.single(vd.PHASE_SCHEMA, diag.CODE_SCHEMA_INVALID)
        )
    if not isinstance(parsed, dict):
        return _occupied_invalid(
            diag.single(vd.PHASE_SCHEMA, diag.CODE_SCHEMA_INVALID)
        )
    vres = vd.validate_marker(parsed)
    if not vres.valid:
        return _occupied_invalid(vres.diagnostics)
    return _project(
        handle,
        identity=str(parsed["identity"]),
        label=str(parsed["label"]),
        marker_version=str(parsed["version"]),
        workspace_path=workspace_path,
        ordinal=ordinal,
        written=False,
        link_mode=True,
    )


def _readback_and_project(
    workspace_path: Path,
    draft: Draft,
    current_handle: fs.TargetHandle,
    ordinal: int,
) -> RegistrationResult:
    """Reopen, re-run raw guard + schema validation, verify exact identity and
    the read-back target handle, then run the projection hook (KTD13)."""
    try:
        raw = fs.read_marker(workspace_path)
    except fs.ReadBackFailedError:
        return _written_unverified(diag.CODE_READ_BACK_FAILED)
    guard = rg.guard(raw)
    if not guard.passed:
        code = diag.from_guard_result(guard.phase, guard.code).items[0].code
        return _written_unverified(code)
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _written_unverified(diag.CODE_READ_BACK_FAILED)
    if not isinstance(parsed, dict):
        return _written_unverified(diag.CODE_READ_BACK_FAILED)
    vres = vd.validate_marker(parsed)
    if not vres.valid:
        return _written_unverified(vres.code or diag.CODE_READ_BACK_FAILED)
    if parsed.get("identity") != draft.identity:
        return _written_unverified(diag.CODE_IDENTITY_MISMATCH)
    readback_handle = _capture_or_stop(workspace_path)
    if isinstance(readback_handle, RegistrationResult):
        return _written_unverified(diag.CODE_READ_BACK_TARGET_MISMATCH)
    if readback_handle != current_handle:
        return _written_unverified(diag.CODE_READ_BACK_TARGET_MISMATCH)
    return _project(
        current_handle,
        identity=draft.identity,
        label=draft.label,
        marker_version=str(draft.marker["version"]),
        workspace_path=workspace_path,
        ordinal=ordinal,
        written=True,
        link_mode=False,
    )


def link(workspace_path: Path, *, ordinal: int = 0) -> RegistrationResult:
    """Existing-marker linking (KTD7, PLAN:192; AE2, PLAN:127).

    Reads the supported valid marker unchanged; no confirmation, no write, no
    new identity. The projection hook links the read identity; a failed or
    unset hook stops without touching the marker.
    """
    inspection = inspect(workspace_path)
    if inspection.state == STATE_STOPPED:
        code = (
            inspection.diagnostics.items[0].code
            if inspection.diagnostics.count
            else diag.CODE_SAFE_INTERNAL_ERROR
        )
        return _stopped(code)
    if inspection.state == STATE_OCCUPIED_INVALID:
        return _occupied_invalid(inspection.diagnostics)
    if inspection.state == STATE_DRAFT_READY:
        return _stopped(diag.CODE_MARKER_INVALID, "no marker at the marker path")
    if inspection.handle is None or inspection.marker is None:
        return _stopped(diag.CODE_SAFE_INTERNAL_ERROR)
    return _project(
        inspection.handle,
        identity=str(inspection.marker["identity"]),
        label=str(inspection.marker["label"]),
        marker_version=str(inspection.marker["version"]),
        workspace_path=workspace_path,
        ordinal=ordinal,
        written=False,
        link_mode=True,
    )


def resolution_envelope(
    workspace_path: Path, *, inspection: Inspection | None = None
) -> ResolutionEnvelope:
    """Build the bounded ``resolve-invalid`` envelope (PLAN:451, 475).

    Previews the marker-component identity, bounded byte length and SHA-256
    digest, the stable target handle, and the current lock status. Requires an
    ``occupied-invalid`` inspection (:class:`ResolutionEnvelopeError`
    otherwise).
    """
    inspection = inspection if inspection is not None else inspect(workspace_path)
    if inspection.state != STATE_OCCUPIED_INVALID:
        raise ResolutionEnvelopeError(
            "resolution requires an occupied-invalid inspection"
        )
    handle = _capture_or_stop(workspace_path)
    if isinstance(handle, RegistrationResult):
        raise ResolutionEnvelopeError("resolution target handle unavailable")
    raw = fs.read_marker(workspace_path)
    lock = fs.lock_metadata(workspace_path)
    if lock is None:
        lock_status = "absent"
    elif lock.is_stale():
        lock_status = "stale"
    else:
        lock_status = "held"
    content: dict[str, Any] = {
        "contract": {"marker": MARKER_VERSION, "conformance": RESULT_VERSION, "protocol": PROTOCOL_VERSION},
        "envelope_kind": "resolve-invalid",
        "target_handle": handle.to_dict(),
        "marker_identity": inspection.marker_identity,
        "marker_length": len(raw),
        "marker_digest_sha256": hashlib.sha256(raw).hexdigest(),
        "lock_status": lock_status,
    }
    envelope_bytes = json.dumps(
        content, separators=(",", ":"), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    return ResolutionEnvelope(
        workspace_path=workspace_path,
        handle=handle,
        marker_identity=inspection.marker_identity,
        marker_length=len(raw),
        marker_digest=hashlib.sha256(raw).digest(),
        lock_status=lock_status,
        envelope=envelope_bytes,
        digest=envelope_digest(envelope_bytes),
    )


def resolve_invalid(
    workspace_path: Path,
    confirmation: Confirmation | None,
    *,
    lock_timeout: float = DEFAULT_LOCK_TIMEOUT,
) -> RegistrationResult:
    """Confirmed ``resolve-invalid`` resolution (PLAN:451, 475).

    Applies the active/stale lock checks and the confirmed target-handle match
    (section 7 rules), deletes the bound invalid marker, and verifies absence
    by read-back: ``invalid-marker-resolved`` on verified absence,
    ``invalid-deleted-unverified`` when the delete succeeded but the absence
    read-back failed, ``cancelled`` on rejection/EOF/digest mismatch or a
    changed marker (no delete).
    """
    if confirmation is None or confirmation.resolution is None:
        return _cancelled(diag.CODE_CONFIRMATION_REJECTED)
    if confirmation.consumed:
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    envelope = confirmation.resolution
    if envelope.workspace_path != workspace_path:
        return _cancelled(diag.CODE_CONFIRMATION_EXPIRED)
    current_handle = _capture_or_stop(workspace_path)
    if isinstance(current_handle, RegistrationResult):
        return current_handle
    if current_handle != envelope.handle:
        return _cancelled(diag.CODE_TARGET_CHANGED)
    if not _marker_present(workspace_path):
        return _invalid_marker_resolved()
    try:
        raw = fs.read_marker(workspace_path)
    except fs.ReadBackFailedError:
        return _cancelled(diag.CODE_MARKER_CHANGED)
    if hashlib.sha256(raw).digest() != envelope.marker_digest:
        return _cancelled(diag.CODE_MARKER_CHANGED)
    confirmation.consumed = True
    try:
        with fs.registration_lock(
            workspace_path, current_handle, recover_stale=True, timeout=lock_timeout
        ) as _owner:
            try:
                fs.delete_marker(workspace_path)
            except FileNotFoundError:
                pass
            except fs.FilesystemError:
                return _stopped(diag.CODE_DELETE_FAILED)
            if fs.verify_marker_absent(workspace_path):
                return _invalid_marker_resolved()
            return _result(
                OUTCOME_INVALID_DELETED_UNVERIFIED,
                validity=VALIDITY_NOT_APPLICABLE,
                effects=Effects(False, True, False, False, False, PROJECTION_NONE),
                diagnostics=diag.single(
                    PHASE_READ_BACK, diag.CODE_ABSENCE_READ_BACK_FAILED
                ),
            )
    except fs.LockUnavailableError:
        return _stopped(diag.CODE_LOCK_UNAVAILABLE)


def register_interactive(
    workspace_path: Path,
    *,
    label: str,
    record_sources: list[dict[str, str]],
    kind: str = "direct",
    confirm_digest: str | None = None,
    ordinal: int = 0,
) -> RegistrationResult:
    """One-call registration for programmatic use and tests.

    inspect -> draft -> confirm -> register. ``confirm_digest`` defaults to
    the draft digest (auto-confirm); pass a different digest to exercise
    rejection. A workspace with a supported valid marker degrades to linking
    (``linked-existing``, PLAN:555); an occupied-invalid workspace reports
    ``occupied-invalid`` (never overwritten).
    """
    inspection = inspect(workspace_path)
    if inspection.state != STATE_DRAFT_READY:
        return inspection_result(inspection)
    try:
        d = draft(
            workspace_path,
            label=label,
            record_sources=record_sources,
            kind=kind,
            inspection=inspection,
        )
    except DraftInputError as exc:
        return _stopped(
            exc.diagnostics.items[0].code if exc.diagnostics.count else diag.CODE_SCHEMA_INVALID,
            "draft input invalid",
        )
    digest = confirm_digest if confirm_digest is not None else d.digest
    confirmation = confirm(d, digest)
    return register(workspace_path, d, confirmation, ordinal=ordinal)
