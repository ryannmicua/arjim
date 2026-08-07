"""Bundled-schema validation for Workstream Registration v1 markers and result
envelopes (U8, PLAN:431-441).

Owns the Draft 2020-12 validation stage that follows the raw-input guard
(KTD11, PLAN:196; pipeline PLAN:219-230). Inputs arrive as guard-passed
decoded JSON (U7's ``guard_decoded_text``); this module dispatches on the
marker/result ``version`` field BEFORE applying the closed schema (KTD3,
PLAN:188): v1 allows the integer value 1, and any other value gets the
distinct ``UNSUPPORTED_VERSION`` outcome (PLAN:362). A missing version field
cannot dispatch and falls through to the closed schema, which rejects it
(``required``) with ``SCHEMA_INVALID``.

Bundled-only ``$ref`` policy (PLAN:439; conformance_runner.py docstring):
validators are constructed with jsonschema defaults — no registry, no
resolver, no retrieval function — so ``$ref`` resolution can only ever reach
the loaded schema's own internal pointers and the Draft 2020-12 meta-schema
bundled inside the ``jsonschema`` package. A schema ``$ref`` to a non-bundled
location raises jsonschema's own resolution failure (``_WrappedReferencingError``
in jsonschema 4.26, pinned by pyproject.toml), which this module converts into
a bounded fail-closed ``SCHEMA_INVALID`` result — never a fetch, never a
propagated raw message.

Generic format assertion is DISABLED by construction: jsonschema's format
checker is never enabled (``Draft202012Validator`` has no format checker by
default), so URIs are syntax-accepted, never format-rejected (KTD5, PLAN:190).
Record-source URI content is never inspected, echoed, or dereferenced.

Non-dict input fails closed with a bounded ``SCHEMA_INVALID`` result: the
guard pipeline already rejected anything that is not a clean JSON object, so
this module treats any other value as structurally invalid.

Diagnostics are produced by :mod:`workstream_registration.diagnostics` under
KTD12 (PLAN:197): phase, stable code, fixed bounded safe path, count — never
native jsonschema messages, instance values, property names, URI content,
snippets, or secrets. This module never prints or logs its input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import _WrappedReferencingError

from workstream_registration import diagnostics as diag

__all__ = [
    "CONTRACTS_DIR",
    "MARKER_SCHEMA_NAME",
    "PHASE_SCHEMA",
    "RESULT_SCHEMA_NAME",
    "SUPPORTED_MARKER_VERSION",
    "SUPPORTED_RESULT_VERSION",
    "VALIDITY_INVALID",
    "VALIDITY_VALID",
    "ValidationResult",
    "load_bundled_schema",
    "repo_root",
    "validate_marker",
    "validate_result_envelope",
]

MARKER_SCHEMA_NAME = "workstream.schema.json"
RESULT_SCHEMA_NAME = "registration-result.schema.json"

SUPPORTED_MARKER_VERSION = 1
SUPPORTED_RESULT_VERSION = 1

VALIDITY_VALID = "valid"
VALIDITY_INVALID = "invalid"

PHASE_SCHEMA = "schema"

CONTRACTS_DIR = Path("contracts") / "workstream-registration" / "v1"

_BUNDLED_ALLOWLIST = frozenset({MARKER_SCHEMA_NAME, RESULT_SCHEMA_NAME})

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def repo_root() -> Path:
    """Repository root containing the contracts directory, discovered by walking up.

    Mirrors ``conformance_runner.repo_root``: works from an editable install
    (package under ``src/``) and from the repo root, because both share the
    ``contracts/workstream-registration`` ancestor marker.
    """
    current = Path(__file__).resolve()
    for ancestor in (current, *current.parents):
        if (ancestor / "contracts" / "workstream-registration").is_dir():
            return ancestor
    raise RuntimeError(
        f"repository root not found: no contracts/workstream-registration above {current}"
    )


def load_bundled_schema(name: str) -> dict[str, Any]:
    """Load a bundled contract schema from the v1 contracts directory only.

    Refuses any name outside the bundled allowlist, so arbitrary paths can
    never be read through this loader (bundled-only policy, PLAN:439). Load
    failures raise loudly: they are environment/contract defects, not instance
    content, and must not be papered over.
    """
    if name not in _BUNDLED_ALLOWLIST:
        raise ValueError(f"not a bundled schema: {name!r}")
    cached = _SCHEMA_CACHE.get(name)
    if cached is not None:
        return cached
    path = repo_root() / CONTRACTS_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    if not isinstance(schema, dict):
        raise RuntimeError(f"bundled schema is not a JSON object: {path}")
    _SCHEMA_CACHE[name] = schema
    return schema


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating one decoded document against a bundled schema.

    ``validity`` is the document-level outcome (``valid`` when the document
    conforms to the closed schema; ``invalid`` otherwise). ``phase`` is the
    diagnostic phase (always ``schema`` here; guard-phase outcomes are routed
    by the guard itself, U7). ``code`` is the primary stable rejection code
    (``None`` for valid documents). ``diagnostics`` is the bounded structured
    diagnostics (KTD12, PLAN:197), always present — empty for valid documents.
    """

    validity: str
    diagnostics: diag.Diagnostics
    phase: str = PHASE_SCHEMA
    code: str | None = None

    @property
    def valid(self) -> bool:
        """True when the document is schema-valid."""
        return self.validity == VALIDITY_VALID


def _validator_for(schema: dict[str, Any]) -> Draft202012Validator:
    """Construct a Draft 2020-12 validator with the bundled-only defaults.

    No resolver, no registry, no retrieval function, no format checker: the
    ``jsonschema`` defaults. This is the single construction point so that the
    bundled-only / format-disabled policy holds by construction everywhere the
    module validates, and tests can exercise the fail-closed path with a
    doctored schema.
    """
    return Draft202012Validator(schema)


def _unsupported_version(data: dict[str, Any], supported: int) -> ValidationResult | None:
    """Dispatch on the version field (KTD3, PLAN:188): non-1 values are distinct.

    Returns the bounded ``UNSUPPORTED_VERSION`` result when ``version`` is
    present but not exactly the supported integer; returns ``None`` when the
    version is the supported value (proceed to schema validation). A missing
    version field returns ``None`` too — it cannot dispatch, so the closed
    schema rejects it (required) with ``SCHEMA_INVALID``. ``type(v) is int``
    excludes booleans (``True`` is an ``int`` subclass but not a JSON integer
    version).
    """
    if "version" not in data:
        return None
    version = data["version"]
    if type(version) is int and version == supported:
        return None
    diagnostics = diag.single(
        phase=PHASE_SCHEMA, code=diag.CODE_UNSUPPORTED_VERSION
    )
    return ValidationResult(
        VALIDITY_INVALID, diagnostics, code=diag.CODE_UNSUPPORTED_VERSION
    )


def _fail_closed() -> ValidationResult:
    """Bounded fail-closed result for structurally unprocessable input."""
    diagnostics = diag.single(phase=PHASE_SCHEMA, code=diag.CODE_SCHEMA_INVALID)
    return ValidationResult(VALIDITY_INVALID, diagnostics, code=diag.CODE_SCHEMA_INVALID)


def _validate_against(schema_name: str, data: Any) -> ValidationResult:
    """Validate ``data`` against the named bundled schema and bound the result."""
    schema = load_bundled_schema(schema_name)
    validator = _validator_for(schema)
    try:
        errors = list(validator.iter_errors(data))
    except _WrappedReferencingError:
        # A $ref could not be resolved; with bundled-only resolution this
        # means a non-bundled reference target. Fail closed (PLAN:439): never
        # fetch, never propagate a raw resolution message.
        return _fail_closed()
    if not errors:
        return ValidationResult(VALIDITY_VALID, diag.Diagnostics.empty())
    normalized = diag.normalize(errors, phase=PHASE_SCHEMA)
    return ValidationResult(
        VALIDITY_INVALID, normalized, code=normalized.items[0].code
    )


def validate_marker(data: Any) -> ValidationResult:
    """Validate a decoded marker document against the bundled v1 marker schema.

    Assumes the input already passed the raw guard (U7) as decoded JSON;
    non-dict input still fails closed (PLAN:439, U8 test scenarios). Dispatches
    on ``version`` before applying the closed schema (KTD3, PLAN:188).
    """
    if not isinstance(data, dict):
        return _fail_closed()
    unsupported = _unsupported_version(data, SUPPORTED_MARKER_VERSION)
    if unsupported is not None:
        return unsupported
    return _validate_against(MARKER_SCHEMA_NAME, data)


def validate_result_envelope(data: Any) -> ValidationResult:
    """Validate a decoded result envelope against the bundled v1 result schema.

    Same dispatch-and-fail-closed discipline as :func:`validate_marker`, for
    the registration-result surface (needed by the U8 corpus hook and by
    U10/U11).
    """
    if not isinstance(data, dict):
        return _fail_closed()
    unsupported = _unsupported_version(data, SUPPORTED_RESULT_VERSION)
    if unsupported is not None:
        return unsupported
    return _validate_against(RESULT_SCHEMA_NAME, data)
