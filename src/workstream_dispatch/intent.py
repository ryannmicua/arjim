"""Intent translation, confirmation, and digest computation (U5 partial).

Turns operator intent into a confirmed instruction, guarding against
dangerous code points (KTD13) and computing the HMAC digest (KTD8).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workstream_registration import registration as reg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# KTD13: dispatch-local guard — superset of registration's raw_guard code points.
# Unicode Tag block (U+E0000–U+E007F)
# Zero-width characters (U+200B–U+200D, U+2060, U+FEFF)
# Variation selectors (U+FE00–U+FE0F, U+E0100–U+E01EF)
# Plus the registration Bidi_Control set

_TAG_BLOCK = frozenset(chr(c) for c in range(0xE0000, 0xE0080))
_ZERO_WIDTH = frozenset(chr(c) for c in [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF])
_VARIATION_SELECTORS_16 = frozenset(chr(c) for c in range(0xFE00, 0xFE10))
_VARIATION_SELECTORS_EP = frozenset(chr(c) for c in range(0xE0100, 0xE01F0))

# Registration's Bidi_Control set (from raw_guard.py:89-103)
_BIDI_CONTROL = frozenset([
    chr(0x200E), chr(0x200F),
    chr(0x202A), chr(0x202B), chr(0x202C), chr(0x202D), chr(0x202E),
    chr(0x2066), chr(0x2067), chr(0x2068), chr(0x2069),
])

# C0 control characters (U+0000–U+001F) and DEL (U+007F) — but not \n (0x0A), \r (0x0D), \t (0x09)
_C0_CONTROL_EXCEPT_WHITESPACE = frozenset(
    chr(c) for c in range(0x00, 0x09)
) | frozenset(chr(c) for c in range(0x0B, 0x0D)) | frozenset(
    chr(c) for c in range(0x0E, 0x20)
) | frozenset({chr(0x7F)}) | frozenset(
    chr(c) for c in range(0x80, 0xA0)
)

# Combined guard set
_DANGEROUS_CODEPOINTS = (
    _C0_CONTROL_EXCEPT_WHITESPACE
    | _BIDI_CONTROL
    | _TAG_BLOCK
    | _ZERO_WIDTH
    | _VARIATION_SELECTORS_16
    | _VARIATION_SELECTORS_EP
)

_INSTRUCTION_MAX_BYTES = 65536


# ---------------------------------------------------------------------------
# Guard result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GuardResult:
    passed: bool
    code: str | None = None


def _normalize_newlines(text: str) -> str:
    """Normalize CRLF and CR to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def guard_instruction(text: str) -> GuardResult:
    """Guard the instruction against dangerous code points (R29, KTD13).

    C0/C1 control characters and bidirectional-formatting code points are
    rejected, as well as the Tag block, zero-width characters, and variation
    selectors.  CRLF is normalized to LF before this check.
    """
    normalized = _normalize_newlines(text)

    if len(normalized.encode("utf-8")) > _INSTRUCTION_MAX_BYTES:
        return GuardResult(passed=False, code="instruction-too-long")

    for ch in normalized:
        if ch in _DANGEROUS_CODEPOINTS:
            return GuardResult(passed=False, code="dangerous-codepoint")

    return GuardResult(passed=True)


@dataclass(frozen=True)
class Draft:
    """A confirmed-ready instruction draft."""

    workspace_path: Path
    workstream_identity: str
    workstream_label: str
    instruction: str
    normalized_instruction: str  # CRLF→LF
    digest: str
    job_id: str
    dispatch_posture: dict[str, str]
    follows: str | None = None
    record_sources: list[dict[str, str]] | None = None


def draft_instruction(
    *,
    workspace_path: Path,
    workstream_identity: str,
    workstream_label: str,
    instruction: str,
    provider: str,
    model: str,
    mode: str,
    thinking: str,
    follows: str | None = None,
    record_sources: list[dict[str, str]] | None = None,
    adapter: Any | None = None,
) -> Draft:
    """Draft an instruction from operator intent (R1, R27).

    Normalizes CRLF→LF, guards against dangerous code points, assembles
    the context payload (R25), and computes the HMAC digest (KTD8).
    """
    # Normalize CRLF→LF first (KTD13)
    normalized = _normalize_newlines(instruction)

    # Guard (R29, KTD13)
    guard = guard_instruction(normalized)
    if not guard.passed:
        raise DraftError(guard.code or "guard-failed")

    # Validate posture tuple is complete (R27, R28)
    if not provider or not model or not mode:
        raise DraftError("incomplete-posture")
    # thinking may be empty only when the model has exactly one option;
    # the caller resolves that — we require it here for safety
    if not thinking:
        raise DraftError("missing-thinking")

    # Validate posture against live CLI (R27, KTD12) if adapter provided
    if adapter is not None:
        posture_valid = adapter.validate_posture(model=model, mode=mode, thinking=thinking)
        if not posture_valid.valid:
            raise DraftError("invalid-posture")

    # Generate job_id
    job_id = str(uuid.uuid4())

    # Assemble context payload (R25) — label, identity, job-record path
    # The instruction asked to the agent includes these
    context = {
        "workstream_label": workstream_label,
        "workstream_identity": workstream_identity,
        "job_record_path": f".workstream/dispatch/{job_id}.json",
    }

    # Compute digest over the exact bytes that will be dispatched
    dispatch_bytes = normalized.encode("utf-8")
    digest = reg.envelope_digest(dispatch_bytes)

    return Draft(
        workspace_path=workspace_path,
        workstream_identity=workstream_identity,
        workstream_label=workstream_label,
        instruction=instruction,
        normalized_instruction=normalized,
        digest=digest,
        job_id=job_id,
        dispatch_posture={
            "provider": provider,
            "model": model,
            "mode": mode,
            "thinking": thinking,
        },
        follows=follows,
        record_sources=record_sources,
    )


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------

_CONFIRM_PREFIX = "confirm "


@dataclass
class Confirmation:
    """A single-use exact-digest confirmation."""

    digest: str
    consumed: bool = False


def confirm(draft: Draft, input_text: str) -> Confirmation | None:
    """Exact-digest confirmation (R2, KTD8).

    Returns the single-use Confirmation only when input_text exactly matches
    ``confirm <digest>``; otherwise returns None.  The confirmation is
    consumed before any write so it cannot be replayed.
    """
    expected = f"{_CONFIRM_PREFIX}{draft.digest}"
    if input_text.strip() == expected:
        return Confirmation(digest=draft.digest, consumed=True)
    return None


class DraftError(Exception):
    """The draft inputs cannot produce a valid instruction."""
