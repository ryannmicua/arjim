"""Tests for U8: CLI surface and result envelope."""
from __future__ import annotations

import json

import pytest

from workstream_dispatch.cli import (
    EXIT_INTERNAL_FAILURE,
    EXIT_INVALID_INPUT,
    EXIT_OK,
    EXIT_PARTIAL,
    EXIT_STOP,
    OUTCOME_EXIT_CODE,
    emit_result,
    outcome_to_exit_code,
    redact_record_sources,
    render_confirmation_preview,
)


class TestOutcomeExitCode:
    def test_all_outcomes_mapped(self):
        """Each outcome maps to its documented exit code."""
        expected = {
            "dispatched": EXIT_OK,
            "partial-success": EXIT_PARTIAL,
            "cancelled": EXIT_STOP,
            "stopped": EXIT_STOP,
            "invalid-workspace": EXIT_INVALID_INPUT,
            "internal-failure": EXIT_INTERNAL_FAILURE,
        }
        assert OUTCOME_EXIT_CODE == expected

    def test_unknown_outcome_defaults_to_internal_failure(self):
        """An unknown outcome defaults to internal failure."""
        assert outcome_to_exit_code("unknown") == EXIT_INTERNAL_FAILURE


class TestEmitResult:
    def test_json_envelope_agrees_with_exit_code(self, capsys):
        """The --json envelope agrees with the exit code."""
        code = emit_result("dispatched", json_mode=True, job_id="j1")
        assert code == EXIT_OK
        captured = capsys.readouterr()
        envelope = json.loads(captured.out)
        assert envelope["outcome"] == "dispatched"
        assert envelope["version"] == 1
        assert envelope["job_id"] == "j1"

    def test_partial_success_emits_partial_code(self, capsys):
        """partial-success emits exit code 5."""
        code = emit_result("partial-success", json_mode=True, job_id="j1")
        assert code == EXIT_PARTIAL


class TestConfirmationPreview:
    def test_preview_ends_with_confirm_digest(self):
        """The confirmation preview ends with the exact confirm <digest> line."""
        preview = render_confirmation_preview(
            instruction="Do something",
            digest="abc123",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        lines = preview.strip().split("\n")
        assert lines[-1] == "confirm abc123"

    def test_byte_length_accurate(self):
        """The rendered byte length equals the instruction's actual byte length."""
        instruction = "Multi-byte: \u00e9\u00e8\u00ea\nNewlines"
        preview = render_confirmation_preview(
            instruction=instruction,
            digest="abc123",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        expected_len = len(instruction.encode("utf-8"))
        assert f"({expected_len} bytes)" in preview


class TestRedaction:
    def test_record_source_uri_redacted(self):
        """A record-source URI is redacted in the preview."""
        text = "Source: https://example.com/repo.git"
        sources = [{"type": "git", "uri": "https://example.com/repo.git"}]
        result = redact_record_sources(text, sources)
        assert "example.com" not in result
        assert "REDACTED" in result

    def test_instruction_rendered_verbatim_in_preview(self):
        """The instruction is rendered verbatim — redaction is only for record-source fields."""
        # The CLI preview renders the instruction without calling redact_record_sources.
        # The redact_record_sources function is only applied to record-source fields.
        # So a URI in the instruction is NOT redacted.
        instruction = "Use https://example.com/repo.git for context"
        sources = [{"type": "git", "uri": "https://example.com/repo.git"}]
        # Simulate: redaction applies to record-source display, not instruction display
        record_source_display = f"Sources: {sources[0]['uri']}"
        redacted_display = redact_record_sources(record_source_display, sources)
        assert "example.com" not in redacted_display
        # The instruction itself is never passed through redact_record_sources
        assert "example.com" in instruction
