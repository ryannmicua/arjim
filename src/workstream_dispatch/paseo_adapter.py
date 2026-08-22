"""Paseo adapter — bounded dispatch and status queries (U4).

Wraps the Paseo CLI as the sole egress point, converting its output into
bounded internal values and its failures into an explicit unreachable signal.
On Windows the npm shim is resolved to its node entry and invoked as
``node <cli-js>`` directly — no command interpreter is ever spawned (KTD2).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIMEOUT_SECONDS = 30
_FIXED_TITLE_PREFIX = "Arjim job "
_PROVIDER = "opencode"
_DEFAULT_MODEL = "opencode-go/mimo-v2.5"
_JOB_LABEL_PREFIX = "arjim.job="


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AdapterError(Exception):
    """The Paseo adapter could not initialize or is unreachable."""


# ---------------------------------------------------------------------------
# CLI resolution (KTD2 — node entry, no command interpreter)
# ---------------------------------------------------------------------------


def _resolve_node_entry() -> tuple[str, str]:
    """Resolve the Paseo npm shim to its node entry on Windows.

    Returns (node_path, cli_js_path).  On failure raises AdapterError.
    """
    which = shutil.which("paseo")
    if which is None:
        raise AdapterError("paseo not found on PATH")
    npm_dir = Path(which).parent
    cli_js = npm_dir / "node_modules" / "@getpaseo" / "cli" / "bin" / "paseo"
    if not cli_js.exists():
        raise AdapterError(
            f"cannot derive node entry from shim at {which}: "
            f"expected {cli_js} not found"
        )
    node = shutil.which("node")
    if node is None:
        raise AdapterError("node not found on PATH")
    return node, str(cli_js)


class PaseoAdapter:
    """Bounded Paseo CLI adapter (KTD2, KTD3, KTD14)."""

    def __init__(self) -> None:
        try:
            self._node, self._cli_js = _resolve_node_entry()
        except AdapterError:
            self._node = ""
            self._cli_js = ""
            self._init_error = True
        else:
            self._init_error = False

    @property
    def available(self) -> bool:
        return not self._init_error

    # -- Low-level CLI invocation --

    def _run_cli(
        self, args: list[str], *, timeout: float = _TIMEOUT_SECONDS
    ) -> subprocess.CompletedProcess[str]:
        """Run a Paseo CLI command with bounded error handling."""
        argv = [self._node, self._cli_js, *args]
        try:
            return subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdapterError(f"paseo CLI invocation failed: {type(exc).__name__}") from exc

    def _run_cli_json(self, args: list[str]) -> Any:
        """Run a CLI command and parse its JSON stdout.  Returns None on any failure."""
        try:
            proc = self._run_cli(args)
        except AdapterError:
            return None
        if proc.returncode != 0:
            return None
        try:
            return json.loads(proc.stdout)
        except (json.JSONDecodeError, ValueError):
            return None

    # -- Spawn a background labelled agent --

    def spawn(
        self,
        *,
        instruction: str,
        cwd: str,
        provider: str,
        model: str,
        mode: str,
        thinking: str,
        job_id: str,
    ) -> SpawnResult:
        """Spawn a background agent with the confirmed posture (R6, R27, R28).

        Every spawn passes a fixed, content-free ``--title`` so Paseo never
        derives a title from instruction text (R23).  The instruction is
        passed as a positional argument after ``--`` to prevent option
        injection (R30, KTD14).
        """
        if self._init_error:
            return SpawnResult(status="unreachable", error_code="adapter-init-failed")

        label = f"{_JOB_LABEL_PREFIX}{job_id}"
        title = f"{_FIXED_TITLE_PREFIX}{job_id}"

        argv = [
            "run",
            "--background",
            "--title", title,
            "--provider", provider,
            "--model", model,
            "--mode", mode,
        ]
        if thinking:
            argv += ["--thinking", thinking]
        argv += ["--label", label, "--"]
        argv += [instruction]

        try:
            proc = self._run_cli(argv, timeout=_TIMEOUT_SECONDS)
        except AdapterError as exc:
            return SpawnResult(status="unreachable", error_code="cli-failed")

        if proc.returncode != 0:
            return SpawnResult(status="unreachable", error_code="spawn-failed")

        # Try to parse the agent id from the response
        try:
            data = json.loads(proc.stdout)
            agent_id = data.get("id") or data.get("agentId") or data.get("Id")
        except (json.JSONDecodeError, ValueError, AttributeError):
            agent_id = None

        return SpawnResult(
            status="spawned",
            agent_id=agent_id,
            label=label,
        )

    # -- List agents by label prefix --

    def list_agents(self) -> list[AgentInfo]:
        """List all agents with the ``arjim.job=`` label prefix in one batched call.

        Uses ``paseo ls --json -a -g`` to include archived agents (KTD5
        ``superseded`` row needs the archived flag).  Correlating by label
        in memory rather than one lookup per job keeps the call count at
        one listing plus one inspect per job needing extra fields.
        """
        if self._init_error:
            return []

        data = self._run_cli_json(["ls", "--json", "-a", "-g"])
        if data is None:
            raise AdapterError("paseo ls failed or returned invalid output")
        if not isinstance(data, list):
            return []

        agents = []
        for item in data:
            if not isinstance(item, dict):
                continue
            labels_raw = item.get("labels") or item.get("Labels") or {}
            if isinstance(labels_raw, dict):
                labels = labels_raw
            else:
                labels = {}
            # Find the arjim.job label
            job_id = None
            for k, v in labels.items():
                if k.startswith("arjim.job="):
                    job_id = k[len("arjim.job="):]
                    break
            if job_id is None:
                continue

            # Normalize case-insensitively (paseo ls uses camelCase, inspect uses PascalCase)
            agent_id = item.get("id") or item.get("Id") or ""
            status = item.get("status") or item.get("Status") or "unknown"
            cwd = item.get("cwd") or item.get("Cwd") or ""

            agents.append(AgentInfo(
                agent_id=str(agent_id),
                job_id=job_id,
                status=str(status).lower(),
                cwd=str(cwd),
            ))
        return agents

    # -- Inspect a single agent --

    def inspect_agent(self, agent_id: str) -> AgentDetail | None:
        """Inspect a single agent for fields the listing doesn't carry.

        Returns None on any failure.
        """
        if self._init_error:
            return None

        data = self._run_cli_json(["inspect", "--json", agent_id])
        if not isinstance(data, dict):
            return None

        # PascalCase normalization (paseo inspect uses PascalCase)
        agent_id_val = data.get("Id") or data.get("id") or ""
        status = data.get("Status") or data.get("status") or "unknown"
        archived = data.get("Archived") or data.get("archived") or False
        pending_raw = data.get("PendingPermissions") or data.get("pendingPermissions") or []
        has_permissions = bool(pending_raw)

        return AgentDetail(
            agent_id=str(agent_id_val),
            status=str(status).lower(),
            archived=bool(archived),
            has_pending_permissions=has_permissions,
        )

    # -- Validate posture against live CLI --

    def validate_posture(
        self, *, model: str, mode: str, thinking: str
    ) -> PostureValidation:
        """Validate a chosen posture against the live CLI (R27, KTD12).

        Queries ``paseo provider models opencode --json`` for model ids and
        per-model thinking options, and ``paseo provider ls --json`` for
        mode vocabulary and default mode.
        """
        if self._init_error:
            return PostureValidation(
                valid=False,
                error="adapter-init-failed",
                available_models=[],
                available_modes=[],
                thinking_options=[],
            )

        # Query models
        models_data = self._run_cli_json(["provider", "models", _PROVIDER, "--json"])
        available_models: list[str] = []
        thinking_options: list[str] = []
        if isinstance(models_data, list):
            for m in models_data:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id") or m.get("Id") or ""
                if mid:
                    available_models.append(str(mid))
                if str(mid) == model:
                    topts = m.get("thinkingOptionIds") or []
                    thinking_options = [str(t) for t in topts if t]

        # Query modes
        providers_data = self._run_cli_json(["provider", "ls", "--json"])
        available_modes: list[str] = []
        default_mode = ""
        if isinstance(providers_data, list):
            for p in providers_data:
                if not isinstance(p, dict):
                    continue
                if p.get("provider") == _PROVIDER:
                    modes_str = p.get("modes") or ""
                    default_mode = p.get("defaultMode") or ""
                    if modes_str:
                        available_modes = [m.strip() for m in str(modes_str).split(",") if m.strip()]
                    break

        errors = []
        if model not in available_models:
            errors.append(f"model '{model}' not in live model set")
        if mode not in available_modes and mode != default_mode:
            errors.append(
                f"mode '{mode}' not in live mode set (available: {available_modes}; default: {default_mode})"
            )
        if thinking and thinking not in thinking_options and len(thinking_options) > 1:
            errors.append(
                f"thinking '{thinking}' not in model's thinkingOptionIds ({thinking_options})"
            )

        return PostureValidation(
            valid=len(errors) == 0,
            error="; ".join(errors) if errors else None,
            available_models=available_models,
            available_modes=available_modes,
            default_mode=default_mode,
            thinking_options=thinking_options,
        )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpawnResult:
    """Outcome of a Paseo agent spawn."""

    status: str  # "spawned" | "unreachable"
    agent_id: str | None = None
    label: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class AgentInfo:
    """A listed agent's core info."""

    agent_id: str
    job_id: str
    status: str
    cwd: str


@dataclass(frozen=True)
class AgentDetail:
    """Extended info from inspect."""

    agent_id: str
    status: str
    archived: bool
    has_pending_permissions: bool


@dataclass(frozen=True)
class PostureValidation:
    """Result of validating a posture against the live CLI."""

    valid: bool
    error: str | None = None
    available_models: list[str] = field(default_factory=list)
    available_modes: list[str] = field(default_factory=list)
    default_mode: str = ""
    thinking_options: list[str] = field(default_factory=list)
