"""Bounded structured diagnostics for Workstream Registration v1 (U8, KTD12).

KTD12 (PLAN:197) owns the normalization of parser and validator failures into
a small versioned vocabulary: phase, stable code, bounded safe path, count,
and, where useful, bounded operator-facing label and affected local path.
Native jsonschema messages and parameters may embed instance values, property
names, URI content, secrets, or snippets and are NEVER emitted.

This module maps jsonschema :class:`~jsonschema.exceptions.ValidationError`
objects to that vocabulary. The mapping reads only the error's ``validator``
keyword (and ``path`` for stable ordering and truncation); it never touches
``message``, ``instance``, ``validator_value``, or ``schema``. Record-source
URI content is structurally impossible in the output: diagnostics carry only
the fixed safe path (the marker path, registration-result.schema.json line 893
"such as the marker path"), a closed-enum phase, and a closed-enum code — the
normalizer never receives URIs.

The code vocabulary is a subset of the closed 29-value ``code`` enum in
registration-result.schema.json (lines 855-885). The schema phase has exactly
two member codes — ``SCHEMA_INVALID`` and ``UNSUPPORTED_VERSION`` — so every
schema-keyword failure (required, additionalProperties, type, enum, const,
pattern, maxLength, minLength, maxItems, minItems, uniqueItems, allOf,
anyOf/oneOf/not, if/then, ...) collapses to ``SCHEMA_INVALID``; the closed
enum has no per-keyword codes, and no code is invented. Guard-phase codes
(U7) are mapped onto the result-schema vocabulary (e.g. the guard's
``DUPLICATE_NAME`` becomes ``DUPLICATE_KEYS``).

Caps mirror registration-result.schema.json ``$defs/diagnostic`` and
``$defs/diagnostics``: count <= 32 (lines 813-816, 820), safe_path <= 256
(line 891), label <= 256 (line 898), affected_local_path <= 1024 (line 905).
The serialized-size cap is a derived module bound (64 KiB): the schema bounds
every field and the count, and serialization paginates items beyond the bound
so the emitted document always satisfies ``count`` == items length (line 816).

Canary discipline: labels and local paths MAY be emitted under caps (08-04
operator decision, PLAN:546), but the normalizer never emits them — instance
labels can carry canary values (e.g. canary-fake-token-1 embeds its token in
the label), so the no-echo guarantee is structural, not contractual. This
module never prints or logs input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from jsonschema.exceptions import ValidationError

__all__ = [
    "CODE_SCHEMA_INVALID",
    "CODE_UNSUPPORTED_VERSION",
    "CODE_CONTROL_CHARACTER",
    "CODE_DEPTH_LIMIT",
    "CODE_DUPLICATE_KEYS",
    "CODE_NON_FINITE",
    "CODE_READ_LIMIT",
    "CODE_UTF8_INVALID",
    "CODES",
    "Diagnostic",
    "Diagnostics",
    "GUARD_CODE_MAP",
    "MAX_AFFECTED_LOCAL_PATH_LENGTH",
    "MAX_DIAGNOSTIC_COUNT",
    "MAX_LABEL_LENGTH",
    "MAX_SAFE_PATH_LENGTH",
    "MAX_SERIALIZED_BYTES",
    "PHASES",
    "PHASE_SCHEMA",
    "SAFE_PATH_MARKER",
    "from_guard_result",
    "normalize",
    "single",
]

PHASE_SCHEMA = "schema"
SAFE_PATH_MARKER = ".workstream/manifest.json"

# Caps from registration-result.schema.json (KTD12, PLAN:197).
MAX_DIAGNOSTIC_COUNT = 32            # count maximum + items maxItems (lines 813-816, 820)
MAX_SAFE_PATH_LENGTH = 256           # diagnostic.safe_path maxLength (line 891)
MAX_LABEL_LENGTH = 256               # diagnostic.label maxLength (line 898)
MAX_AFFECTED_LOCAL_PATH_LENGTH = 1024  # diagnostic.affected_local_path maxLength (line 905)
MAX_SERIALIZED_BYTES = 65_536        # derived module bound; see module docstring

# Closed phase enum (registration-result.schema.json lines 838-851); the first
# seven match the raw-guard termination phases (expectations.schema.json).
PHASES = (
    "read",
    "utf8",
    "depth",
    "duplicates",
    "nonfinite",
    "controls",
    "schema",
    "write",
    "read-back",
    "link",
    "projection",
    "operation",
)

# Closed code enum (registration-result.schema.json lines 855-885). Schema
# phase member codes are SCHEMA_INVALID and UNSUPPORTED_VERSION; the rest are
# operational/guard codes owned by other units.
CODE_READ_LIMIT = "READ_LIMIT"
CODE_UTF8_INVALID = "UTF8_INVALID"
CODE_DEPTH_LIMIT = "DEPTH_LIMIT"
CODE_DUPLICATE_KEYS = "DUPLICATE_KEYS"
CODE_NON_FINITE = "NON_FINITE"
CODE_CONTROL_CHARACTER = "CONTROL_CHARACTER"
CODE_SCHEMA_INVALID = "SCHEMA_INVALID"
CODE_UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
CODE_MARKER_INVALID = "MARKER_INVALID"
CODE_WORKSPACE_INACCESSIBLE = "WORKSPACE_INACCESSIBLE"
CODE_IDENTITY_API_UNAVAILABLE = "IDENTITY_API_UNAVAILABLE"
CODE_PATH_REDIRECTED = "PATH_REDIRECTED"
CODE_TARGET_ALIAS_MISMATCH = "TARGET_ALIAS_MISMATCH"
CODE_WRITE_FAILED = "WRITE_FAILED"
CODE_CONFIRMATION_REJECTED = "CONFIRMATION_REJECTED"
CODE_CONFIRMATION_MISMATCH = "CONFIRMATION_MISMATCH"
CODE_CONFIRMATION_EXPIRED = "CONFIRMATION_EXPIRED"
CODE_DRAFT_CHANGED = "DRAFT_CHANGED"
CODE_TARGET_CHANGED = "TARGET_CHANGED"
CODE_LOCK_UNAVAILABLE = "LOCK_UNAVAILABLE"
CODE_READ_BACK_FAILED = "READ_BACK_FAILED"
CODE_READ_BACK_TARGET_MISMATCH = "READ_BACK_TARGET_MISMATCH"
CODE_PROJECTION_LINK_FAILED = "PROJECTION_LINK_FAILED"
CODE_PROJECTION_CONFLICT = "PROJECTION_CONFLICT"
CODE_DELETE_FAILED = "DELETE_FAILED"
CODE_ABSENCE_READ_BACK_FAILED = "ABSENCE_READ_BACK_FAILED"
CODE_MARKER_CHANGED = "MARKER_CHANGED"
CODE_IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
CODE_SAFE_INTERNAL_ERROR = "SAFE_INTERNAL_ERROR"

CODES = (
    CODE_READ_LIMIT,
    CODE_UTF8_INVALID,
    CODE_DEPTH_LIMIT,
    CODE_DUPLICATE_KEYS,
    CODE_NON_FINITE,
    CODE_CONTROL_CHARACTER,
    CODE_SCHEMA_INVALID,
    CODE_UNSUPPORTED_VERSION,
    CODE_MARKER_INVALID,
    CODE_WORKSPACE_INACCESSIBLE,
    CODE_IDENTITY_API_UNAVAILABLE,
    CODE_PATH_REDIRECTED,
    CODE_TARGET_ALIAS_MISMATCH,
    CODE_WRITE_FAILED,
    CODE_CONFIRMATION_REJECTED,
    CODE_CONFIRMATION_MISMATCH,
    CODE_CONFIRMATION_EXPIRED,
    CODE_DRAFT_CHANGED,
    CODE_TARGET_CHANGED,
    CODE_LOCK_UNAVAILABLE,
    CODE_READ_BACK_FAILED,
    CODE_READ_BACK_TARGET_MISMATCH,
    CODE_PROJECTION_LINK_FAILED,
    CODE_PROJECTION_CONFLICT,
    CODE_DELETE_FAILED,
    CODE_ABSENCE_READ_BACK_FAILED,
    CODE_MARKER_CHANGED,
    CODE_IDENTITY_MISMATCH,
    CODE_SAFE_INTERNAL_ERROR,
)

# U7 raw-guard codes (raw_guard.py) mapped onto the result-schema vocabulary.
GUARD_CODE_MAP: dict[str, str] = {
    "READ_OVER_LIMIT": CODE_READ_LIMIT,
    "UTF8_BOM_PREFIX": CODE_UTF8_INVALID,
    "UTF8_DECODE_ERROR": CODE_UTF8_INVALID,
    "DEPTH_EXCEEDED": CODE_DEPTH_LIMIT,
    "DUPLICATE_NAME": CODE_DUPLICATE_KEYS,
    "NONFINITE_CONSTANT": CODE_NON_FINITE,
    "CONTROL_CHARACTER": CODE_CONTROL_CHARACTER,
}


@dataclass(frozen=True)
class Diagnostic:
    """One bounded structured diagnostic (registration-result.schema.json).

    ``label`` and ``affected_local_path`` are optional bounded fields the
    normalizer never sets; they exist so downstream units (U9+) can attach
    them under the length caps.
    """

    phase: str
    code: str
    safe_path: str
    label: str | None = None
    affected_local_path: str | None = None

    def bounded(self) -> "Diagnostic":
        """Return a copy with every field truncated at its schema cap."""
        label = _truncate(self.label, MAX_LABEL_LENGTH) if self.label else None
        path = (
            _truncate(self.affected_local_path, MAX_AFFECTED_LOCAL_PATH_LENGTH)
            if self.affected_local_path
            else None
        )
        return Diagnostic(
            phase=_truncate(self.phase, 16),
            code=_truncate(self.code, 32),
            safe_path=_truncate(self.safe_path, MAX_SAFE_PATH_LENGTH),
            label=label,
            affected_local_path=path,
        )

    def to_dict(self) -> dict[str, str]:
        """Serializable form; optional fields are omitted when unset."""
        out: dict[str, str] = {
            "phase": self.phase,
            "code": self.code,
            "safe_path": self.safe_path,
        }
        if self.label is not None:
            out["label"] = self.label
        if self.affected_local_path is not None:
            out["affected_local_path"] = self.affected_local_path
        return out


@dataclass(frozen=True)
class Diagnostics:
    """Bounded diagnostic list shaped like registration-result.schema.json.

    ``count`` always equals the items length (schema line 816: the runner
    asserts count == items length).
    """

    count: int
    items: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @classmethod
    def empty(cls) -> "Diagnostics":
        return cls(count=0, items=())

    def bounded(self) -> "Diagnostics":
        """Truncate items at the count cap and every field at its length cap."""
        items = tuple(item.bounded() for item in self.items[:MAX_DIAGNOSTIC_COUNT])
        return Diagnostics(count=len(items), items=items)

    def to_dict(self) -> dict[str, Any]:
        bounded = self.bounded()
        return {
            "count": bounded.count,
            "items": [item.to_dict() for item in bounded.items],
        }

    def serialize(self) -> str:
        """Compact JSON serialization bounded to MAX_SERIALIZED_BYTES.

        Items are dropped (with ``count`` adjusted, never mid-field) until the
        serialized document fits the bound, so the output always satisfies the
        result-schema shape (count == items length).
        """
        bounded = self.bounded()
        text = json.dumps(bounded.to_dict(), ensure_ascii=False, separators=(",", ":"))
        if len(text.encode("utf-8")) <= MAX_SERIALIZED_BYTES:
            return text
        items: list[dict[str, str]] = []
        for item in bounded.items:
            candidate = {"count": len(items) + 1, "items": items + [item.to_dict()]}
            candidate_text = json.dumps(
                candidate, ensure_ascii=False, separators=(",", ":")
            )
            if len(candidate_text.encode("utf-8")) > MAX_SERIALIZED_BYTES:
                break
            items.append(item.to_dict())
        return json.dumps(
            {"count": len(items), "items": items}, ensure_ascii=False, separators=(",", ":")
        )

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(self.items)

    def __len__(self) -> int:
        return self.count


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else value[:limit]


def _error_key(error: ValidationError) -> tuple[tuple[str, ...], str]:
    """Stable ordering key: path components then validator keyword."""
    return tuple(str(part) for part in error.path), str(error.validator)


def _code_for_validator(validator: str) -> str:
    """Map a jsonschema validator keyword to the closed schema-phase code.

    The closed 29-value code enum (registration-result.schema.json lines
    855-885) has exactly one schema-validation code, SCHEMA_INVALID, plus
    UNSUPPORTED_VERSION for version dispatch. Every schema keyword therefore
    collapses to SCHEMA_INVALID; no per-keyword code exists in the frozen
    vocabulary and none is invented here (KTD12, PLAN:197).
    """
    return CODE_SCHEMA_INVALID


def normalize(
    errors: Iterable[ValidationError],
    *,
    phase: str = PHASE_SCHEMA,
    safe_path: str = SAFE_PATH_MARKER,
) -> Diagnostics:
    """Map jsonschema ValidationError objects into bounded diagnostics.

    Reads only ``error.validator`` (mapped via the closed code vocabulary) and
    ``error.path`` (stable ordering and count truncation). Never reads
    ``message``, ``instance``, ``validator_value``, or ``schema``, so native
    messages, instance values, property names, URI content, secrets, and
    snippets are structurally excluded (KTD12, PLAN:197; PLAN:439). At most
    MAX_DIAGNOSTIC_COUNT errors are kept.
    """
    ordered = sorted(errors, key=_error_key)
    items = tuple(
        Diagnostic(phase=phase, code=_code_for_validator(str(err.validator)), safe_path=safe_path)
        for err in ordered[:MAX_DIAGNOSTIC_COUNT]
    )
    return Diagnostics(count=len(items), items=items)


def single(
    phase: str, code: str, safe_path: str = SAFE_PATH_MARKER
) -> Diagnostics:
    """A one-item Diagnostics for non-validator outcomes (dispatch, fail-closed)."""
    return Diagnostics(count=1, items=(Diagnostic(phase=phase, code=code, safe_path=safe_path),))


def from_guard_result(phase: str, code: str | None) -> Diagnostics:
    """Map a raw-guard termination (U7) onto the result-schema vocabulary.

    ``phase`` is already the shared guard phase (expectations.schema.json);
    ``code`` is mapped through GUARD_CODE_MAP. An unmapped code collapses to
    SCHEMA_INVALID rather than propagating raw guard content.
    """
    stable = GUARD_CODE_MAP.get(code or "", CODE_SCHEMA_INVALID)
    return single(phase=phase, code=stable)
