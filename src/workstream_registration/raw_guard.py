"""Raw-input guard for Workstream Registration v1 (U7).

KTD11 (PLAN:196) owns the bounded raw-input pipeline that runs before JSON
Schema materialization. The pipeline is strictly ordered (PLAN:219-230):

1. bound read: reject more than 262,144 raw bytes (an allowed 262,144-byte
   marker is distinguishable from an oversized one by reading 262,145 bytes,
   KTD11 PLAN:196) -> phase ``read``
2. strict UTF-8: reject BOM signatures and any malformed UTF-8 byte
   sequence -> phase ``utf8``
3. token-aware depth scan: count container nesting, ignoring brackets inside
   strings, reject depth above 8 -> phase ``depth``
4. duplicate-name rejection: detect duplicate names at the root and nested
   (duplicate-preserving hook, PLAN:427) -> phase ``duplicates``
5. non-finite rejection: ``NaN``, ``Infinity``, ``-Infinity`` tokens outside
   strings (constant rejection hook, PLAN:427) -> phase ``nonfinite``
6. controls scan: scan decoded names and values for prohibited C0 controls
   (U+0000-U+001F), C1 controls (U+007F-U+009F), and the ``Bidi_Control`` set
   (U+200E, U+200F, U+202A-U+202E, U+2066-U+2069; KTD9 PLAN:194); literal
   control bytes in the raw text (which also break strict JSON parsing) are
   caught by a text-level scan -> phase ``controls``
7. clean pass -> phase ``schema`` (continues to Draft 2020-12 validation,
   expectations.schema.json phase enum)

``guard_decoded_text`` is the F1-reconciled entry point for parsed-value
envelopes: a decoded marker whose names or values contain a prohibited control
must terminate at the ``controls`` phase (expectations.json
``invalid-label-controls`` declares ``phase: controls``). It runs steps 3-6
over the JSON text and its decoded names/values; the byte-level phases
(``read``, ``utf8``) are unreachable for already-decoded text.

Results carry the phase and a stable code (KTD12, PLAN:197) that matches the
``expected.code`` pattern ``^[A-Z][A-Z0-9_-]{0,63}$``
(expectations.schema.json). The module never prints, logs, or otherwise emits
the input; it returns structured results only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

__all__ = [
    "BIDI_CONTROL_POINTS",
    "MAX_DEPTH",
    "MAX_READ_BYTES",
    "PHASE_CONTROLS",
    "PHASE_DEPTH",
    "PHASE_DUPLICATES",
    "PHASE_NONFINITE",
    "PHASE_READ",
    "PHASE_SCHEMA",
    "PHASE_UTF8",
    "PHASES",
    "RawGuardResult",
    "guard",
    "guard_decoded_text",
]

MAX_READ_BYTES = 262_144
MAX_DEPTH = 8

PHASE_READ = "read"
PHASE_UTF8 = "utf8"
PHASE_DEPTH = "depth"
PHASE_DUPLICATES = "duplicates"
PHASE_NONFINITE = "nonfinite"
PHASE_CONTROLS = "controls"
PHASE_SCHEMA = "schema"
PHASES = (
    PHASE_READ,
    PHASE_UTF8,
    PHASE_DEPTH,
    PHASE_DUPLICATES,
    PHASE_NONFINITE,
    PHASE_CONTROLS,
    PHASE_SCHEMA,
)

CODE_READ_OVER_LIMIT = "READ_OVER_LIMIT"
CODE_UTF8_BOM_PREFIX = "UTF8_BOM_PREFIX"
CODE_UTF8_DECODE_ERROR = "UTF8_DECODE_ERROR"
CODE_DEPTH_EXCEEDED = "DEPTH_EXCEEDED"
CODE_DUPLICATE_NAME = "DUPLICATE_NAME"
CODE_NONFINITE_CONSTANT = "NONFINITE_CONSTANT"
CODE_CONTROL_CHARACTER = "CONTROL_CHARACTER"

BIDI_CONTROL_POINTS = frozenset(
    {
        0x200E,  # LEFT-TO-RIGHT MARK
        0x200F,  # RIGHT-TO-LEFT MARK
        0x202A,  # LEFT-TO-RIGHT EMBEDDING
        0x202B,  # RIGHT-TO-LEFT EMBEDDING
        0x202C,  # POP DIRECTIONAL FORMATTING
        0x202D,  # LEFT-TO-RIGHT OVERRIDE
        0x202E,  # RIGHT-TO-LEFT OVERRIDE
        0x2066,  # LEFT-TO-RIGHT ISOLATE
        0x2067,  # RIGHT-TO-LEFT ISOLATE
        0x2068,  # FIRST STRONG ISOLATE
        0x2069,  # POP DIRECTIONAL ISOLATE
    }
)

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF32_BOMS = (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


@dataclass(frozen=True)
class RawGuardResult:
    """Termination result of the raw-input guard.

    ``phase`` is one of the expectations ``phase`` enum values
    (expectations.schema.json); ``code`` is the stable rejection code, or
    ``None`` when the input passed the guard (phase ``schema``).
    """

    phase: str
    code: str | None = None

    @property
    def passed(self) -> bool:
        """True when the input passed the guard and continues to validation."""
        return self.phase == PHASE_SCHEMA


class _NonFiniteConstant(ValueError):
    """Raised by the parse_constant hook to reject NaN/Infinity tokens."""


class _DuplicateName(ValueError):
    """Raised by the object_pairs_hook when a JSON object repeats a name."""


def _bom_phase(raw: bytes) -> RawGuardResult | None:
    """Reject BOM signatures at the utf8 phase (PLAN:364 bom fixture)."""
    if raw.startswith(_UTF8_BOM):
        return RawGuardResult(PHASE_UTF8, CODE_UTF8_BOM_PREFIX)
    for bom in _UTF32_BOMS:
        if raw.startswith(bom):
            return RawGuardResult(PHASE_UTF8, CODE_UTF8_BOM_PREFIX)
    for bom in _UTF16_BOMS:
        if raw.startswith(bom):
            return RawGuardResult(PHASE_UTF8, CODE_UTF8_BOM_PREFIX)
    return None


def _depth_scan(text: str) -> RawGuardResult | None:
    """Token-aware depth scan: brackets inside strings never count (KTD11)."""
    depth = 0
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                return RawGuardResult(PHASE_DEPTH, CODE_DEPTH_EXCEEDED)
        elif ch in "]}":
            if depth:
                depth -= 1
    return None


def _decode_with_hooks(
    text: str,
) -> tuple[Any, RawGuardResult | None]:
    """Strictly decode JSON with duplicate-preserving and constant hooks.

    Returns ``(document, result)``: when ``result`` is not None the guard
    terminated at ``result.phase``; when the document does not parse at all
    (e.g. trailing content after the JSON document, PLAN:364) parsing is left
    to the validation stage and the guard passes.
    """

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        if len({name for name, _ in pairs}) != len(pairs):
            raise _DuplicateName
        return dict(pairs)

    def parse_constant(value: str) -> Any:
        raise _NonFiniteConstant

    try:
        document = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=parse_constant,
        )
    except _DuplicateName:
        return None, RawGuardResult(PHASE_DUPLICATES, CODE_DUPLICATE_NAME)
    except _NonFiniteConstant:
        return None, RawGuardResult(PHASE_NONFINITE, CODE_NONFINITE_CONSTANT)
    except json.JSONDecodeError:
        return None, None
    return document, None


def _is_prohibited_control(ch: str) -> bool:
    """C0 (U+0000-U+001F), C1 (U+007F-U+009F), and Bidi_Control membership."""
    cp = ord(ch)
    return cp <= 0x1F or 0x7F <= cp <= 0x9F or cp in BIDI_CONTROL_POINTS


def _text_controls_scan(text: str) -> RawGuardResult | None:
    """Scan raw text for prohibited controls; catches literal control bytes."""
    if any(_is_prohibited_control(ch) for ch in text):
        return RawGuardResult(PHASE_CONTROLS, CODE_CONTROL_CHARACTER)
    return None


def _controls_scan(document: Any) -> RawGuardResult | None:
    """Scan decoded names and values for prohibited controls and Bidi_Control.

    Every string in the decoded document is scanned: object member names
    (names) and all string values (values), at the root and nested
    (KTD11 PLAN:196; KTD9 PLAN:194).
    """
    stack: list[Any] = [document]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for name, value in node.items():
                if any(_is_prohibited_control(ch) for ch in name):
                    return RawGuardResult(PHASE_CONTROLS, CODE_CONTROL_CHARACTER)
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, str):
            if any(_is_prohibited_control(ch) for ch in node):
                return RawGuardResult(PHASE_CONTROLS, CODE_CONTROL_CHARACTER)
    return None


def _guard_text(text: str) -> RawGuardResult:
    """Steps 3-6 over already-decoded JSON text (F1 parsed-value routing)."""
    result = _depth_scan(text)
    if result is not None:
        return result
    document, result = _decode_with_hooks(text)
    if result is not None:
        return result
    if document is None:
        result = _text_controls_scan(text)
        if result is not None:
            return result
        return RawGuardResult(PHASE_SCHEMA)
    result = _controls_scan(document)
    if result is not None:
        return result
    return RawGuardResult(PHASE_SCHEMA)


def guard(raw: bytes) -> RawGuardResult:
    """Run the bounded raw-input pipeline over raw bytes (KTD11).

    Pipeline order (PLAN:219-230): bound read -> strict UTF-8 (BOM and
    malformed sequences) -> token-aware depth -> duplicate names -> non-finite
    constants -> controls/Bidi_Control -> schema phase on a clean pass.
    """
    if len(raw) > MAX_READ_BYTES:
        return RawGuardResult(PHASE_READ, CODE_READ_OVER_LIMIT)
    result = _bom_phase(raw)
    if result is not None:
        return result
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return RawGuardResult(PHASE_UTF8, CODE_UTF8_DECODE_ERROR)
    return _guard_text(text)


def guard_decoded_text(text: str) -> RawGuardResult:
    """Guard a decoded JSON text (steps 3-6; byte phases unreachable).

    Routed from parsed-value envelopes so that decoded markers with
    prohibited controls in names or values terminate at the ``controls``
    phase (F1 reconciliation; ``invalid-label-controls`` expects
    ``phase: controls``).
    """
    return _guard_text(text)
