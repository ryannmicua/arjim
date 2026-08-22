"""CLI surface and result envelope (U8).

Exposes dispatch and activity as Arjim-operated commands emitting the
U1 envelope with a frozen outcome-to-exit-code mapping.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from workstream_dispatch.intent import _CONFIRM_PREFIX

# ---------------------------------------------------------------------------
# Exit codes (KTD9, mirrors cli.py:97-143)
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_STOP = 2
EXIT_INVALID_INPUT = 3
EXIT_PARTIAL = 5
EXIT_INTERNAL_FAILURE = 6

# Frozen outcome-to-exit-code table
OUTCOME_EXIT_CODE: dict[str, int] = {
    "dispatched": EXIT_OK,
    "partial-success": EXIT_PARTIAL,
    "cancelled": EXIT_STOP,
    "stopped": EXIT_STOP,
    "invalid-workspace": EXIT_INVALID_INPUT,
    "internal-failure": EXIT_INTERNAL_FAILURE,
}


def outcome_to_exit_code(outcome: str) -> int:
    """Map a result outcome to its frozen exit code (KTD9)."""
    return OUTCOME_EXIT_CODE.get(outcome, EXIT_INTERNAL_FAILURE)


def emit_result(outcome: str, *, json_mode: bool = False, **kwargs: Any) -> int:
    """Emit a result envelope and return the exit code."""
    code = outcome_to_exit_code(outcome)
    if json_mode:
        envelope = {"version": 1, "outcome": outcome, **kwargs}
        print(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))
    return code


# ---------------------------------------------------------------------------
# Confirmation preview
# ---------------------------------------------------------------------------


def render_confirmation_preview(
    *,
    instruction: str,
    digest: str,
    provider: str,
    model: str,
    mode: str,
    thinking: str,
) -> str:
    """Render the confirmation preview for interactive use (R2, KTD13).

    The preview renders the instruction's byte length beside the digest
    and ends with the literal ``confirm <digest>`` line.
    """
    byte_len = len(instruction.encode("utf-8"))
    lines = [
        f"Provider: {provider}",
        f"Model: {model}",
        f"Mode: {mode}",
        f"Thinking: {thinking}",
        f"Instruction ({byte_len} bytes):",
        instruction,
        "",
        f"confirm {digest}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Redaction (mirrors cli.py:166-171)
# ---------------------------------------------------------------------------

_REDACTED = "***REDACTED***"


def redact_record_sources(text: str, record_sources: list[dict[str, str]]) -> str:
    """Redact record-source URIs in preview text (R23).

    The redaction transform applies to record-source URIs only and is
    never applied to the instruction field.
    """
    result = text
    for rs in record_sources:
        uri = rs.get("uri", "")
        if uri and uri in result:
            result = result.replace(uri, _REDACTED)
    return result


# ---------------------------------------------------------------------------
# U8 CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Hand-rolled subcommand dispatcher (matches registration's pattern)."""
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"version": 1, "outcome": "stopped", "error": "no-subcommand"}))
        sys.exit(EXIT_STOP)

    subcmd = args[0]

    if subcmd == "dispatch":
        _cmd_dispatch(args[1:])
    elif subcmd == "activity":
        _cmd_activity(args[1:])
    elif subcmd == "show":
        _cmd_show(args[1:])
    else:
        print(json.dumps({"version": 1, "outcome": "stopped", "error": f"unknown-subcommand: {subcmd}"}))
        sys.exit(EXIT_STOP)


def _cmd_dispatch(argv: list[str]) -> None:
    """dispatch <workspace> <instruction> <provider> <model> <mode> <thinking> [confirm-text]"""
    if len(argv) < 6:
        print(json.dumps({"version": 1, "outcome": "stopped", "error": "dispatch requires: <workspace> <instruction> <provider> <model> <mode> <thinking>"}))
        sys.exit(EXIT_STOP)

    workspace = Path(argv[0])
    instruction = argv[1]
    provider = argv[2]
    model = argv[3]
    mode = argv[4]
    thinking = argv[5]
    confirm_text = argv[6] if len(argv) > 6 else None

    from workstream_dispatch import store
    from workstream_dispatch.dispatch import dispatch, dispatch_without_confirmation
    from workstream_dispatch.intent import draft_instruction
    from workstream_dispatch.paseo_adapter import PaseoAdapter

    adapter = PaseoAdapter()
    store_instance = store.DispatchStore()

    if confirm_text:
        # Draft, then confirm, then dispatch
        from workstream_dispatch import records as rec
        manifest = workspace / ".workstream" / "manifest.json"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            print(json.dumps({"version": 1, "outcome": "invalid-workspace", "error": "cannot-read-manifest"}))
            sys.exit(EXIT_INVALID_INPUT)

        identity = data.get("identity", "")
        label = data.get("label", "")

        d = draft_instruction(
            workspace_path=workspace,
            workstream_identity=identity,
            workstream_label=label,
            instruction=instruction,
            provider=provider,
            model=model,
            mode=mode,
            thinking=thinking,
        )
        result = dispatch(
            workspace_path=workspace,
            draft=d,
            confirmation_digest=confirm_text,
            adapter=adapter,
            store_instance=store_instance,
        )
    else:
        result = dispatch_without_confirmation(
            workspace_path=workspace,
            instruction=instruction,
            provider=provider,
            model=model,
            mode=mode,
            thinking=thinking,
            adapter=adapter,
            store_instance=store_instance,
        )

    code = emit_result(result.outcome, json_mode=True, job_id=result.job_id, error_code=result.error_code)
    sys.exit(code)


def _cmd_activity(argv: list[str]) -> None:
    """activity <workspace> [<workspace> ...]"""
    from workstream_dispatch import store
    from workstream_dispatch.activity import answer_activity
    from workstream_dispatch.paseo_adapter import PaseoAdapter

    scan_list = [Path(a) for a in argv] if argv else []
    adapter = PaseoAdapter()
    store_instance = store.DispatchStore()

    answer = answer_activity(scan_list=scan_list, adapter=adapter, store_instance=store_instance)

    envelope = {
        "version": 1,
        "outcome": "dispatched",
        "observation_time": answer.observation_time,
        "total_workspaces": answer.total_workspaces,
        "readable_workspaces": answer.readable_workspaces,
        "unreachable_paseo": answer.unreachable_paseo,
        "note_statuses": answer.note_statuses,
        "workspaces": [
            {
                "workspace_path": ws.workspace_path,
                "workstream_label": ws.workstream_label,
                "jobs": [
                    {
                        "job_id": j.job_id,
                        "job_state": j.job_state,
                        "note_status": j.note_status,
                    }
                    for j in ws.jobs
                ],
                "change_signal": ws.change_signal,
            }
            for ws in answer.workspaces
        ],
    }
    print(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))
    sys.exit(EXIT_OK)


def _cmd_show(argv: list[str]) -> None:
    """show <job-id>"""
    if len(argv) < 1:
        print(json.dumps({"version": 1, "outcome": "stopped", "error": "show requires: <job-id>"}))
        sys.exit(EXIT_STOP)

    job_id = argv[0]
    from workstream_dispatch import records as rec

    # Read the job record from the current workspace
    workspace = Path(".")
    result = rec.read_job_record(workspace, job_id)
    if result is None:
        print(json.dumps({"version": 1, "outcome": "stopped", "error": f"job-not-found: {job_id}"}))
        sys.exit(EXIT_STOP)

    envelope = {
        "version": 1,
        "outcome": "dispatched",
        "job_id": result.job_id,
        "record": result.record,
    }
    print(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))
    sys.exit(EXIT_OK)
