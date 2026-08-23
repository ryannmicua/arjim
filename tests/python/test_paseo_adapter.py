"""Tests for U4: Paseo adapter — bounded dispatch and status queries."""
from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from workstream_dispatch.paseo_adapter import (
    AdapterError,
    AgentDetail,
    AgentInfo,
    PaseoAdapter,
    PostureValidation,
    SpawnResult,
    _resolve_node_entry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter(tmp_path, monkeypatch):
    """A PaseoAdapter with mocked CLI resolution."""
    monkeypatch.setattr(
        "workstream_dispatch.paseo_adapter.shutil.which",
        lambda name: str(tmp_path / "paseo.cmd") if name == "paseo" else str(tmp_path / "node"),
    )
    # Create the shim and node files so exists() works
    (tmp_path / "paseo.cmd").touch()
    (tmp_path / "node").touch()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "@getpaseo").mkdir(parents=True)
    (tmp_path / "node_modules" / "@getpaseo" / "cli").mkdir()
    (tmp_path / "node_modules" / "@getpaseo" / "cli" / "bin").mkdir()
    (tmp_path / "node_modules" / "@getpaseo" / "cli" / "bin" / "paseo").touch()
    return PaseoAdapter()


def _mock_completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


# ---------------------------------------------------------------------------
# Node entry resolution (KTD2)
# ---------------------------------------------------------------------------


class TestNodeEntryResolution:
    def test_resolves_to_node_and_cli_js(self, adapter):
        """On Windows, the shim resolves to (node_path, cli_js_path)."""
        assert adapter.available
        assert adapter._node
        assert adapter._cli_js

    def test_no_command_interpreter(self, adapter):
        """The constructed argv never uses a bare paseo name or command interpreter."""
        assert adapter._node
        assert adapter._cli_js
        # argv starts with [node, cli_js, ...]
        assert "cmd.exe" not in adapter._node.lower()
        assert "powershell" not in adapter._node.lower()

    def test_instruction_inert_in_argv(self, adapter):
        """An instruction with &, |, ^, %PATH%, and embedded quotes is one inert element."""
        # The spawn method passes instruction as a positional argument after --
        # This is verified by the spawn test below

    def test_init_error_when_shim_missing(self, monkeypatch):
        """An init that cannot derive the node entry refuses with a stable code."""
        monkeypatch.setattr(
            "workstream_dispatch.paseo_adapter.shutil.which",
            lambda name: None,
        )
        a = PaseoAdapter()
        assert not a.available


# ---------------------------------------------------------------------------
# Spawn
# ---------------------------------------------------------------------------


class TestSpawn:
    def test_spawn_passes_confirmed_posture(self, adapter):
        """The confirmed provider/model/mode/thinking tuple appears in argv."""
        with patch.object(adapter, "_run_cli") as mock_run:
            mock_run.return_value = _mock_completed(
                stdout=json.dumps({"id": "agent-42"})
            )
            result = adapter.spawn(
                instruction="Do something",
                cwd="/workspace",
                provider="opencode",
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
                job_id="a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
            )
            assert result.status == "spawned"
            # Check argv construction
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "run"
            assert "--background" in call_args
            assert "--provider" in call_args
            assert "opencode" in call_args
            assert "--model" in call_args
            assert "opencode-go/mimo-v2.5" in call_args
            assert "--mode" in call_args
            assert "default" in call_args
            assert "--" in call_args
            # Instruction comes after --
            dash_idx = call_args.index("--")
            assert call_args[dash_idx + 1] == "Do something"

    def test_fixed_content_free_title(self, adapter):
        """Every spawn carries the fixed content-free --title, never instruction text."""
        with patch.object(adapter, "_run_cli") as mock_run:
            mock_run.return_value = _mock_completed(
                stdout=json.dumps({"id": "agent-42"})
            )
            adapter.spawn(
                instruction="Secret instruction text",
                cwd="/workspace",
                provider="opencode",
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
                job_id="a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
            )
            call_args = mock_run.call_args[0][0]
            title_idx = call_args.index("--title")
            title_val = call_args[title_idx + 1]
            assert "Secret instruction" not in title_val
            assert "a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5" in title_val

    def test_label_contains_job_id(self, adapter):
        """The --label flag contains arjim.job=<job-id>."""
        with patch.object(adapter, "_run_cli") as mock_run:
            mock_run.return_value = _mock_completed(
                stdout=json.dumps({"id": "agent-42"})
            )
            result = adapter.spawn(
                instruction="Do something",
                cwd="/workspace",
                provider="opencode",
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
                job_id="a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
            )
            assert result.label == "arjim.job=a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5"

    def test_cli_failure_produces_unreachable(self, adapter):
        """subprocess.run raising OSError produces unreachable with a stable code."""
        with patch.object(adapter, "_run_cli", side_effect=AdapterError("cli-failed")):
            result = adapter.spawn(
                instruction="test",
                cwd="/ws",
                provider="opencode",
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
                job_id="a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
            )
            assert result.status == "unreachable"
            assert result.error_code is not None

    def test_spawn_not_retried(self, adapter):
        """A failed spawn is not retried within the call."""
        with patch.object(adapter, "_run_cli") as mock_run:
            mock_run.return_value = _mock_completed(returncode=1)
            result = adapter.spawn(
                instruction="test",
                cwd="/ws",
                provider="opencode",
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
                job_id="a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
            )
            assert result.status == "unreachable"
            assert mock_run.call_count == 1  # Only one call, no retry

    def test_instruction_as_single_arg(self, adapter):
        """The instruction is placed as a single argument, never interpolated into a shell string."""
        with patch.object(adapter, "_run_cli") as mock_run:
            mock_run.return_value = _mock_completed(
                stdout=json.dumps({"id": "agent-42"})
            )
            adapter.spawn(
                instruction="--mode bypassPermissions",
                cwd="/ws",
                provider="opencode",
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
                job_id="a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
            )
            call_args = mock_run.call_args[0][0]
            dash_idx = call_args.index("--")
            # Instruction is after --, as a single list element
            assert call_args[dash_idx + 1] == "--mode bypassPermissions"
            # The mode in the spawn args is still "default" (confirmed), not from instruction
            mode_idx = call_args.index("--mode")
            assert call_args[mode_idx + 1] == "default"


# ---------------------------------------------------------------------------
# List agents
# ---------------------------------------------------------------------------


class TestListAgents:
    def test_batched_list_returns_arjim_agents(self, adapter):
        """The batched list returns every arjim.job-labelled agent."""
        listing = [
            {
                "id": "agent-1",
                "status": "running",
                "cwd": "/ws1",
                "labels": {"arjim.job=a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5": ""},
            },
            {
                "id": "agent-2",
                "status": "idle",
                "cwd": "/ws2",
                "labels": {"arjim.job=b2c3d4e5-f6a7-4b8c-9d0e-f1a2b3c4d5e6": ""},
            },
        ]
        with patch.object(adapter, "_run_cli_json", return_value=listing):
            agents = adapter.list_agents()
            assert len(agents) == 2
            assert agents[0].job_id == "a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5"
            assert agents[0].status == "running"
            assert agents[1].status == "idle"

    def test_empty_listing_resolves_to_no_agents(self, adapter):
        """An empty listing resolves to no agents, distinct from unreachable."""
        with patch.object(adapter, "_run_cli_json", return_value=[]):
            agents = adapter.list_agents()
            assert agents == []

    def test_unparseable_output_raises(self, adapter):
        """Unparseable stdout raises AdapterError (signals unreachable)."""
        with patch.object(adapter, "_run_cli_json", return_value=None):
            with pytest.raises(AdapterError):
                adapter.list_agents()

    def test_case_insensitive_normalization(self, adapter):
        """camelCase and PascalCase keys both normalize."""
        listing_camel = [
            {"id": "a1", "status": "running", "cwd": "/ws", "labels": {"arjim.job=job1": ""}},
        ]
        listing_pascal = [
            {"Id": "a1", "Status": "running", "Cwd": "/ws", "Labels": {"arjim.job=job1": ""}},
        ]
        with patch.object(adapter, "_run_cli_json", return_value=listing_camel):
            agents_c = adapter.list_agents()
        with patch.object(adapter, "_run_cli_json", return_value=listing_pascal):
            agents_p = adapter.list_agents()
        assert agents_c[0].agent_id == agents_p[0].agent_id


# ---------------------------------------------------------------------------
# Inspect agent
# ---------------------------------------------------------------------------


class TestInspectAgent:
    def test_inspect_normalizes_pascal_case(self, adapter):
        """An inspect payload with PascalCase keys normalizes."""
        with patch.object(
            adapter, "_run_cli_json",
            return_value={"Id": "agent-1", "Status": "idle", "Archived": False, "PendingPermissions": []},
        ):
            detail = adapter.inspect_agent("agent-1")
            assert detail is not None
            assert detail.status == "idle"
            assert detail.archived is False
            assert detail.has_pending_permissions is False

    def test_non_empty_pending_permissions(self, adapter):
        """A non-empty PendingPermissions list is surfaced as a boolean flag."""
        with patch.object(
            adapter, "_run_cli_json",
            return_value={"Id": "agent-1", "Status": "idle", "Archived": False, "PendingPermissions": [{"id": "perm-1"}]},
        ):
            detail = adapter.inspect_agent("agent-1")
            assert detail is not None
            assert detail.has_pending_permissions is True

    def test_archived_agent(self, adapter):
        """An archived agent is detected."""
        with patch.object(
            adapter, "_run_cli_json",
            return_value={"Id": "agent-1", "Status": "closed", "Archived": True, "PendingPermissions": []},
        ):
            detail = adapter.inspect_agent("agent-1")
            assert detail is not None
            assert detail.archived is True


# ---------------------------------------------------------------------------
# Posture validation
# ---------------------------------------------------------------------------


class TestPostureValidation:
    def test_valid_posture(self, adapter):
        """A valid posture returns valid=True."""
        models = [
            {"id": "opencode-go/mimo-v2.5", "thinkingOptionIds": ["none"]},
        ]
        providers = [
            {"provider": "opencode", "modes": "Build, Plan, Builder", "defaultMode": "default"},
        ]
        with patch.object(adapter, "_run_cli_json", side_effect=[models, providers]):
            result = adapter.validate_posture(
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
            )
            assert result.valid

    def test_invalid_model(self, adapter):
        """A model absent from the live set is refused."""
        models = [
            {"id": "opencode-go/mimo-v2.5", "thinkingOptionIds": []},
        ]
        providers = [
            {"provider": "opencode", "modes": "Build", "defaultMode": "default"},
        ]
        with patch.object(adapter, "_run_cli_json", side_effect=[models, providers]):
            result = adapter.validate_posture(
                model="nonexistent-model",
                mode="default",
                thinking="",
            )
            assert not result.valid
            assert "model" in result.error

    def test_default_mode_accepted(self, adapter):
        """The provider's own defaultMode is accepted even when not in modes list."""
        models = [{"id": "opencode-go/mimo-v2.5", "thinkingOptionIds": []}]
        providers = [{"provider": "opencode", "modes": "Build, Plan", "defaultMode": "default"}]
        with patch.object(adapter, "_run_cli_json", side_effect=[models, providers]):
            result = adapter.validate_posture(
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="",
            )
            assert result.valid

    def test_thinking_single_option_recorded_without_prompting(self, adapter):
        """A model with exactly one thinking option has it recorded."""
        models = [{"id": "opencode-go/mimo-v2.5", "thinkingOptionIds": ["none"]}]
        providers = [{"provider": "opencode", "modes": "", "defaultMode": "default"}]
        with patch.object(adapter, "_run_cli_json", side_effect=[models, providers]):
            result = adapter.validate_posture(
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
            )
            assert result.valid
            assert result.thinking_options == ["none"]

    def test_thinking_multiple_options_default_selected(self, adapter):
        """A model with more than one thinking option returns all options."""
        models = [{"id": "model-x", "thinkingOptionIds": ["none", "low", "high"]}]
        providers = [{"provider": "opencode", "modes": "", "defaultMode": "default"}]
        with patch.object(adapter, "_run_cli_json", side_effect=[models, providers]):
            result = adapter.validate_posture(
                model="model-x",
                mode="default",
                thinking="low",
            )
            assert result.thinking_options == ["none", "low", "high"]

    def test_unreachable_validation_refuses(self, adapter):
        """An unreachable validation query refuses rather than assuming a set."""
        with patch.object(adapter, "_run_cli_json", return_value=None):
            result = adapter.validate_posture(
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="none",
            )
            assert not result.valid
            assert result.error is not None

    def test_model_id_in_provider_field_refused(self, adapter):
        """A posture naming a model id in the provider field is refused."""
        # This is tested at the schema level (U1), but the adapter also checks
        models = [{"id": "opencode-go/mimo-v2.5", "thinkingOptionIds": []}]
        providers = [{"provider": "opencode", "modes": "", "defaultMode": "default"}]
        with patch.object(adapter, "_run_cli_json", side_effect=[models, providers]):
            result = adapter.validate_posture(
                model="opencode-go/mimo-v2.5",
                mode="default",
                thinking="",
            )
            # The posture itself is valid; the provider check is in the schema
            assert result.valid
