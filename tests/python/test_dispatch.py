"""Tests for U5: Dispatch orchestration (additional integration tests)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from workstream_dispatch.dispatch import dispatch
from workstream_dispatch.intent import draft_instruction
from workstream_dispatch.paseo_adapter import PaseoAdapter, SpawnResult
from workstream_dispatch.store import DispatchStore


@pytest.fixture()
def workspace(tmp_path):
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


class TestDispatchIntegration:
    def test_full_dispatch_lifecycle(self, workspace, adapter, store_inst):
        """End-to-end: draft → confirm → write → spawn → bind."""
        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity="test-identity",
            workstream_label="test",
            instruction="Do something useful",
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
        assert result.job_id == d.job_id
        # Verify record written
        dispatch_dir = workspace / ".workstream" / "dispatch"
        assert dispatch_dir.exists()
        record_file = dispatch_dir / f"{d.job_id}.json"
        stored = json.loads(record_file.read_bytes())
        assert stored["instruction"] == "Do something useful"
        assert stored["dispatch_posture"]["provider"] == "opencode"
        # Verify binding stored
        binding = store_inst.get_binding(d.job_id)
        assert binding is not None
        assert binding["agent_id"] == "agent-42"
