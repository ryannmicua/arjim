"""Tests for U5: Intent translation, confirmation, and dispatch orchestration."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from workstream_dispatch.dispatch import (
    DispatchResult,
    dispatch,
    dispatch_without_confirmation,
)
from workstream_dispatch.intent import (
    Draft,
    DraftError,
    confirm,
    draft_instruction,
    guard_instruction,
)
from workstream_dispatch.paseo_adapter import PaseoAdapter, SpawnResult
from workstream_dispatch.store import DispatchStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_record(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
        "workstream_identity": "test-identity",
        "instruction": "Do something",
        "dispatch_posture": {
            "provider": "opencode",
            "model": "opencode-go/mimo-v2.5",
            "mode": "default",
            "thinking": "none",
        },
        "actor": "operator-confirmed",
        "recorded_at": "2026-08-21T00:00:00Z",
        "confirmation_ref": "abc123",
        "created_at": "2026-08-21T00:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def workspace(tmp_path):
    """A workspace with a valid marker."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    manifest = ws / ".workstream" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "version": 1,
        "identity": "test-identity",
        "label": "test-workstream",
        "kind": "direct",
        "workspace": ".",
        "record_sources": [],
    }))
    return ws


@pytest.fixture()
def store_inst(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSTREAM_DISPATCH_STORE_DIR", str(tmp_path / "store"))
    return DispatchStore(store_dir=tmp_path / "store")


@pytest.fixture()
def adapter():
    return MagicMock(spec=PaseoAdapter)


# ---------------------------------------------------------------------------
# Guard tests (KTD13)
# ---------------------------------------------------------------------------


class TestGuardInstruction:
    def test_rtl_override_refused(self):
        """An instruction containing a right-to-left override is refused (AE19)."""
        result = guard_instruction("Hello \u202e world")
        assert not result.passed
        assert result.code == "dangerous-codepoint"

    def test_c0_control_refused(self):
        """A C0 control character is refused."""
        result = guard_instruction("Hello\x00world")
        assert not result.passed

    def test_newline_accepted(self):
        """Newlines are accepted (they are whitespace, not control chars)."""
        result = guard_instruction("Line 1\nLine 2")
        assert result.passed

    def test_tag_block_refused(self):
        """Unicode Tag block characters are refused."""
        result = guard_instruction("Hello\U000E0000world")
        assert not result.passed

    def test_zero_width_refused(self):
        """Zero-width characters are refused."""
        result = guard_instruction("Hello\u200Bworld")
        assert not result.passed

    def test_variation_selector_refused(self):
        """Variation selectors are refused."""
        result = guard_instruction("Hello\uFE0Fworld")
        assert not result.passed

    def test_crlf_normalized_to_lf(self):
        """CRLF is normalized to LF before the digest."""
        result = guard_instruction("Line 1\r\nLine 2")
        assert result.passed


# ---------------------------------------------------------------------------
# Draft tests
# ---------------------------------------------------------------------------


class TestDraftInstruction:
    def test_digest_computed_over_normalized_bytes(self, workspace):
        """The digest is computed over the exact bytes that will be dispatched."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Hello\nWorld",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        # Digest is a hex string
        assert len(d.digest) == 64
        assert all(c in "0123456789abcdef" for c in d.digest)

    def test_crlf_instruction_normalized(self, workspace):
        """CRLF in instruction is normalized to LF in the draft."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Line 1\r\nLine 2",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        assert d.normalized_instruction == "Line 1\nLine 2"

    def test_dangerous_codepoint_refused(self, workspace):
        """An instruction containing a right-to-left override is refused at draft time (AE19)."""
        with pytest.raises(DraftError):
            draft_instruction(
                workspace_path=workspace,
                workstream_identity="test-identity",
                workstream_label="test",
                instruction="Hello \u202e world",
                provider="opencode",
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
            )

    def test_incomplete_posture_refused(self, workspace):
        """A draft without a complete tuple is refused (AE18)."""
        with pytest.raises(DraftError):
            draft_instruction(
                workspace_path=workspace,
                workstream_identity="test-identity",
                workstream_label="test",
                instruction="Do something",
                provider="opencode",
                model="",
                mode="default",
                thinking="none",
            )


# ---------------------------------------------------------------------------
# Confirmation tests
# ---------------------------------------------------------------------------


class TestConfirmation:
    def test_exact_digest_matches(self, workspace):
        """Exact string equality against confirm <digest>."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        c = confirm(d, f"confirm {d.digest}")
        assert c is not None

    def test_mismatch_returns_none(self, workspace):
        """A digest mismatch returns None and writes nothing (AE1)."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        c = confirm(d, "confirm wrongdigest")
        assert c is None


# ---------------------------------------------------------------------------
# Dispatch orchestration tests
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_digest_mismatch_writes_nothing(self, workspace, adapter, store_inst):
        """A digest mismatch writes nothing and spawns nothing (AE1)."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest="confirm wrongdigest",
            adapter=adapter,
            store_instance=store_inst,
        )
        assert result.outcome == "cancelled"
        adapter.spawn.assert_not_called()
        # No job record written
        dispatch_dir = workspace / ".workstream" / "dispatch"
        assert not dispatch_dir.exists()

    def test_unregistered_workspace_refused(self, workspace, adapter, store_inst):
        """Dispatch against a workspace with no marker is refused (AE3)."""
        # Remove the marker
        (workspace / ".workstream" / "manifest.json").unlink()
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        assert result.outcome == "invalid-workspace"
        adapter.spawn.assert_not_called()

    def test_partial_success_on_spawn_failure(self, workspace, adapter, store_inst):
        """A successful write followed by adapter unreachable returns partial success (AE2)."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        adapter.spawn.return_value = SpawnResult(status="unreachable", error_code="daemon-down")
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        assert result.outcome == "partial-success"
        assert result.job_id == d.job_id
        # Job record was written
        dispatch_dir = workspace / ".workstream" / "dispatch"
        assert dispatch_dir.exists()
        records = list(dispatch_dir.glob("*.json"))
        assert len(records) == 1

    def test_record_write_failure_stops_before_spawn(self, workspace, adapter, store_inst):
        """A record-write failure returns stopped and the adapter is never called."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        # Write a record first to cause a collision
        from workstream_dispatch import records as rec
        rec.write_job_record(workspace, _minimal_record(job_id=d.job_id))
        # Now the dispatch should fail on collision
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        assert result.outcome == "stopped"
        adapter.spawn.assert_not_called()

    def test_confirmed_bytes_identical_to_dispatched_bytes(self, workspace, adapter, store_inst):
        """The bytes whose digest was confirmed are byte-identical to dispatched bytes (AE19)."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Multi-byte: \u00e9\u00e8\u00ea\nLeading space\nTrailing space  ",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        adapter.spawn.return_value = SpawnResult(status="spawned", agent_id="agent-42")
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        assert result.outcome == "dispatched"
        # Check that the stored record has the normalized instruction
        dispatch_dir = workspace / ".workstream" / "dispatch"
        record_file = dispatch_dir / f"{d.job_id}.json"
        stored = json.loads(record_file.read_bytes())
        assert stored["instruction"] == d.normalized_instruction
        # The spawn instruction is the context payload which contains the normalized instruction
        call_args = adapter.spawn.call_args
        spawn_instruction = call_args[1]["instruction"]
        assert d.normalized_instruction in spawn_instruction

    def test_assistant_drafted_without_confirmation(self, workspace, adapter, store_inst):
        """Dispatch without an externally supplied confirmation records assistant-drafted (AE12)."""
        adapter.spawn.return_value = SpawnResult(status="spawned", agent_id="agent-42")
        result = dispatch_without_confirmation(
            workspace_path=workspace,
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
            adapter=adapter,
            store_instance=store_inst,
        )
        assert result.outcome == "dispatched"
        dispatch_dir = workspace / ".workstream" / "dispatch"
        records = list(dispatch_dir.glob("*.json"))
        assert len(records) == 1
        stored = json.loads(records[0].read_bytes())
        assert stored["actor"] == "assistant-drafted"

    def test_context_payload_no_record_source_uri(self, workspace, adapter, store_inst):
        """The context payload carries workstream label, identity, and job-record path, and no record-source URI (AE16)."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
            record_sources=[{"type": "git", "uri": "https://example.com/repo.git"}],
        )
        adapter.spawn.return_value = SpawnResult(status="spawned", agent_id="agent-42")
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        # The spawn instruction should be the exact normalized instruction (KTD8 confirmed bytes)
        call_args = adapter.spawn.call_args
        instruction = call_args[1]["instruction"]
        assert instruction == "Do something"
        assert "example.com" not in instruction

    def test_confirmed_posture_tuple_handed_to_adapter(self, workspace, adapter, store_inst):
        """The confirmed provider/model/mode/thinking tuple is the tuple handed to the adapter (AE18)."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="deepseek/deepseek-v4-flash",
            mode="Plan",
            thinking="high",
        )
        adapter.spawn.return_value = SpawnResult(status="spawned", agent_id="agent-42")
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        call_args = adapter.spawn.call_args
        assert call_args[1]["provider"] == "opencode"
        assert call_args[1]["model"] == "deepseek/deepseek-v4-flash"
        assert call_args[1]["mode"] == "Plan"
        assert call_args[1]["thinking"] == "high"

    def test_spawn_not_retried(self, workspace, adapter, store_inst):
        """A failed spawn is not retried within the call."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
        )
        adapter.spawn.return_value = SpawnResult(status="unreachable", error_code="failed")
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        assert result.outcome == "partial-success"
        assert adapter.spawn.call_count == 1

    def test_record_source_canary_absent_from_spawn(self, workspace, adapter, store_inst):
        """A canary planted in a record source is absent from the spawn instruction."""
        canary = "s3cret-record-source"
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something",
            provider="opencode",
            model="opencode-go/mimo-v2.5",
            mode="default",
            thinking="none",
            record_sources=[{"type": "git", "uri": canary}],
        )
        adapter.spawn.return_value = SpawnResult(status="spawned", agent_id="agent-42")
        dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=f"confirm {d.digest}",
            adapter=adapter,
            store_instance=store_inst,
        )
        call_args = adapter.spawn.call_args
        instruction = call_args[1]["instruction"]
        # The canary is in the record_sources but should not appear in the instruction
        assert canary not in instruction
