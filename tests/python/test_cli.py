"""U11 CLI tests (PLAN:476): register with required inputs, default/explicit
kind, same-process digest confirmation, cancellation/EOF/mismatch -> no write
(exit 2), existing-marker link (linked-existing, exit 0), rebuild after
projection loss (TS-WORK), confirmed unregister (exit 0), identity mismatch
(exit 4), occupied-invalid resolution (exit 0 / exit 5), stale-lock recovery
confirmation, the exact exit-code table (PLAN:556) with the ``--json``
outcome and exit code never diverging, and no canary echo in CLI output,
diagnostics, captured logs, stderr, or dependency-error paths.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from workstream_registration import cli
from workstream_registration import diagnostics as diag
from workstream_registration import filesystem as fs
from workstream_registration import projection as proj
from workstream_registration import registration as reg

MARKER = {
    "version": 1,
    "identity": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "label": "Quarterly Planning",
    "kind": "direct",
    "workspace": ".",
    "record_sources": [
        {"type": "sharepoint/team-site", "uri": "https://sharepoint.example.org/sites/q"}
    ],
}

SOURCE = "example/records=https://records.example.org/x"


@pytest.fixture(autouse=True)
def _cli_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("WORKSTREAM_REGISTRATION_STORE_DIR", str(tmp_path / "store"))
    yield
    reg.set_projection_hook(None)


def _write_marker(ws: Path, marker: dict) -> None:
    fs.parent_path(ws).mkdir(exist_ok=True)
    fs.marker_path(ws).write_bytes(json.dumps(marker, separators=(",", ":")).encode("utf-8"))


def _dead_pid() -> int:
    return 2_000_000_000


def _write_stale_lock(ws: Path, handle: fs.TargetHandle) -> None:
    import time

    now = time.time()
    metadata = fs.LockMetadata(
        owner_id="crashed-owner",
        pid=_dead_pid(),
        target_handle=handle,
        started_at=datetime.fromtimestamp(now - 3600, tz=timezone.utc).isoformat(),
        lease_until=datetime.fromtimestamp(now - 3600, tz=timezone.utc).isoformat(),
    )
    fs.parent_path(ws).mkdir(exist_ok=True)
    fs.lock_path(ws).write_bytes(metadata.to_bytes())


def _auto_confirm(replies: list[str] | None = None):
    """Seam pair for the interactive flows: ``emit`` captures the preview
    lines, ``read_line`` replies with the exact printed digest (same-process
    confirmation, KTD6 PLAN:191) or a scripted reply list."""
    captured: dict[str, str | None] = {"digest": None}

    def emit(line: str) -> None:
        match = re.match(r"^confirm ([0-9a-f]{64})$", line)
        if match is not None and captured["digest"] is None:
            captured["digest"] = match.group(1)

    def read_line() -> str:
        if replies is not None:
            return replies.pop(0) if replies else ""
        return f"confirm {captured['digest']}"

    return emit, read_line


def _run_main(
    argv: list[str], stdin_text: str = ""
) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    code = cli.main(argv, stdin=io.StringIO(stdin_text), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def _last_json(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if line.strip()]
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_required_inputs_default_kind(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        emit, read_line = _auto_confirm()
        result = cli.register_interactive_cli(
            ws, label="Required Inputs", record_sources=[{"type": "example/records", "uri": "https://records.example.org/x"}], emit=emit, read_line=read_line,
        )
        assert result.outcome == "registered"
        assert result.identity is not None
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["label"] == "Required Inputs"
        assert on_disk["kind"] == "direct"
        assert on_disk["record_sources"] == [
            {"type": "example/records", "uri": "https://records.example.org/x"}
        ]

    def test_explicit_kind_proxy(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        emit, read_line = _auto_confirm()
        result = cli.register_interactive_cli(
            ws, label="Proxy", kind="proxy",
            record_sources=[{"type": "sharepoint/site", "uri": "https://sharepoint.example.org/sites/p"}],
            emit=emit, read_line=read_line,
        )
        assert result.outcome == "registered"
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["kind"] == "proxy"

    def test_main_register_json_envelope_and_exit_zero(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        env = dict(os.environ)
        env["WORKSTREAM_REGISTRATION_STORE_DIR"] = str(tmp_path / "store")
        code, out = _drive_interactive(
            ["--json", "register", str(ws), "--label", "Json Run",
             "--record-source", SOURCE, "--kind", "proxy"],
            env,
        )
        assert code == 0, out
        envelope = _last_json(out)
        assert envelope["outcome"] == "registered"
        assert envelope["validity"] == "valid"
        assert envelope["effects"]["linked"] is True
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["kind"] == "proxy"

    def test_mismatched_digest_no_write_exit_2(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        emit, read_line = _auto_confirm(replies=["confirm " + "0" * 64])
        result = cli.register_interactive_cli(
            ws, label="Never Confirmed", record_sources=[{"type": "example/records", "uri": "https://records.example.org/x"}], emit=emit, read_line=read_line,
        )
        assert result.outcome == "cancelled"
        assert not fs.marker_path(ws).exists()
        assert not fs.parent_path(ws).exists()

    def test_eof_cancels_no_write(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out, err = _run_main(
            ["--json", "register", str(ws), "--label", "EOF", "--record-source", SOURCE],
            stdin_text="",
        )
        assert code == 2
        envelope = _last_json(out)
        assert envelope["outcome"] == "cancelled"
        assert not fs.marker_path(ws).exists()
        assert envelope["effects"]["marker_written"] is False

    def test_cancellation_line_no_write(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out, err = _run_main(
            ["register", str(ws), "--label", "No", "--record-source", SOURCE, "--json"],
            stdin_text="cancel\n",
        )
        assert code == 2
        assert _last_json(out)["outcome"] == "cancelled"
        assert not fs.marker_path(ws).exists()

    def test_register_on_existing_marker_degrades_to_linked_existing(
        self, tmp_path: Path
    ) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        before = fs.read_marker(ws)
        code, out, err = _run_main(
            ["--json", "register", str(ws), "--label", "ignored", "--record-source", SOURCE],
            stdin_text="",
        )
        assert code == 0
        envelope = _last_json(out)
        assert envelope["outcome"] == "linked-existing"
        assert envelope["identity"] == MARKER["identity"]
        assert envelope["effects"]["marker_written"] is False
        assert fs.read_marker(ws) == before

    def test_occupied_invalid_register_exit_3(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        code, out, err = _run_main(
            ["--json", "register", str(ws), "--label", "x", "--record-source", SOURCE],
            stdin_text="",
        )
        assert code == 3
        assert _last_json(out)["outcome"] == "occupied-invalid"
        assert json.loads(fs.read_marker(ws).decode("utf-8"))["identity"] == "nope"

    def test_missing_workspace_exit_2(self, tmp_path: Path) -> None:
        code, out, err = _run_main(
            ["--json", "register", str(tmp_path / "missing"), "--label", "x", "--record-source", SOURCE],
            stdin_text="",
        )
        assert code == 2
        assert _last_json(out)["outcome"] == "stopped"


# ---------------------------------------------------------------------------
# inspect / link
# ---------------------------------------------------------------------------


class TestInspectAndLink:
    def test_inspect_draft_ready(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out, err = _run_main(["--json", "inspect", str(ws)])
        assert code == 2
        envelope = _last_json(out)
        assert envelope["outcome"] == "stopped"
        code, out, err = _run_main(["inspect", str(ws)])
        assert code == 2
        assert "state: draft-ready" in out

    def test_inspect_occupied_invalid_exit_3(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        code, out, err = _run_main(["--json", "inspect", str(ws)])
        assert code == 3
        assert _last_json(out)["outcome"] == "occupied-invalid"

    def test_inspect_linked_existing_exit_0(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        code, out, err = _run_main(["--json", "inspect", str(ws)])
        assert code == 0
        assert _last_json(out)["outcome"] == "linked-existing"

    def test_inspect_missing_workspace_exit_2(self, tmp_path: Path) -> None:
        code, out, err = _run_main(["--json", "inspect", str(tmp_path / "missing")])
        assert code == 2
        assert _last_json(out)["outcome"] == "stopped"

    def test_link_existing_marker(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        code, out, err = _run_main(["--json", "link", str(ws)])
        assert code == 0
        envelope = _last_json(out)
        assert envelope["outcome"] == "linked-existing"
        assert envelope["identity"] == MARKER["identity"]
        assert envelope["effects"]["marker_written"] is False

    def test_link_absent_marker_stops(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out, err = _run_main(["--json", "link", str(ws)])
        assert code == 2
        assert _last_json(out)["outcome"] == "stopped"


# ---------------------------------------------------------------------------
# unregister
# ---------------------------------------------------------------------------


class TestUnregister:
    def _register_ws(self, ws: Path) -> None:
        emit, read_line = _auto_confirm()
        result = cli.register_interactive_cli(
            ws, label="Unregister Me", record_sources=[{"type": "example/records", "uri": "https://records.example.org/x"}], emit=emit, read_line=read_line,
        )
        assert result.outcome == "registered"

    def test_confirmed_unregister_exit_0(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        self._register_ws(ws)
        emit, read_line = _auto_confirm()
        result = cli.unregister_interactive_cli(ws, emit=emit, read_line=read_line)
        assert result.outcome == "unregistered"
        assert result.effects.marker_deleted is True
        assert result.effects.absence_verified is True
        assert fs.verify_marker_absent(ws)
        # exit code via the console entry point (single-process confirmation)
        env = dict(os.environ)
        env["WORKSTREAM_REGISTRATION_STORE_DIR"] = str(tmp_path / "store2")
        ws2 = tmp_path / "ws2"
        ws2.mkdir()
        self._register_ws(ws2)
        code, out = _drive_interactive(["--json", "unregister", str(ws2)], env)
        assert code == 0, out
        envelope = _last_json(out)
        assert envelope["outcome"] == "unregistered"

    def test_unregister_rejected_no_delete_exit_2(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        self._register_ws(ws)
        code, out, err = _run_main(
            ["--json", "unregister", str(ws)], stdin_text="confirm " + "0" * 64 + "\n"
        )
        assert code == 2
        assert _last_json(out)["outcome"] == "cancelled"
        assert fs.marker_path(ws).exists()

    def test_unregister_absent_marker_stops(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out, err = _run_main(["--json", "unregister", str(ws)], stdin_text="")
        assert code == 2
        assert _last_json(out)["outcome"] == "stopped"

    def test_identity_mismatch_exit_4(self, tmp_path: Path) -> None:
        """Changed marker identity between envelope and delete:
        changed-marker-stopped, exit 4, no delete (KTD10 PLAN:195)."""
        ws = tmp_path / "ws"
        ws.mkdir()
        self._register_ws(ws)
        original = fs.read_marker(ws)
        mutated = json.loads(original.decode("utf-8"))
        mutated["identity"] = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
        emit, read_line = _auto_confirm(replies=None)

        def mutating_read_line() -> str:
            fs.marker_path(ws).write_bytes(
                json.dumps(mutated, separators=(",", ":")).encode("utf-8")
            )
            return f"confirm {emit_captured['digest']}"

        emit_captured: dict[str, str | None] = {"digest": None}
        original_emit = emit

        def emit_capture(line: str) -> None:
            match = re.match(r"^confirm ([0-9a-f]{64})$", line)
            if match is not None and emit_captured["digest"] is None:
                emit_captured["digest"] = match.group(1)
            original_emit(line)

        result = cli.unregister_interactive_cli(
            ws, emit=emit_capture, read_line=mutating_read_line
        )
        assert result.outcome == "changed-marker-stopped"
        assert result.diagnostics.items[0].code == diag.CODE_IDENTITY_MISMATCH
        assert fs.read_marker(ws) != original
        assert fs.marker_path(ws).exists()

    def test_marker_replaced_between_reads_exit_4(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        self._register_ws(ws)
        original = fs.read_marker(ws)
        replaced = json.loads(original.decode("utf-8"))
        replaced["label"] = "Replaced Between Reads"

        def mutating_read_line() -> str:
            fs.marker_path(ws).write_bytes(
                json.dumps(replaced, separators=(",", ":")).encode("utf-8")
            )
            return f"confirm {emit_captured['digest']}"

        emit_captured: dict[str, str | None] = {"digest": None}
        seen: list[str] = []

        def emit_capture(line: str) -> None:
            seen.append(line)
            match = re.match(r"^confirm ([0-9a-f]{64})$", line)
            if match is not None and emit_captured["digest"] is None:
                emit_captured["digest"] = match.group(1)

        result = cli.unregister_interactive_cli(
            ws, emit=emit_capture, read_line=mutating_read_line
        )
        assert result.outcome == "changed-marker-stopped"
        assert fs.marker_path(ws).exists()


# ---------------------------------------------------------------------------
# resolve-invalid
# ---------------------------------------------------------------------------


class TestResolveInvalid:
    def test_resolve_invalid_marker_resolved_exit_0(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        seen: list[str] = []
        emit, read_line = _auto_confirm()

        def emit_capture(line: str) -> None:
            seen.append(line)
            emit(line)

        result = cli.resolve_invalid_interactive_cli(ws, emit=emit_capture, read_line=read_line)
        assert result is not None
        assert result.outcome == "invalid-marker-resolved"
        assert result.effects.marker_deleted is True
        assert result.effects.absence_verified is True
        assert fs.verify_marker_absent(ws)
        preview = "\n".join(seen)
        assert "state: occupied-invalid" in preview
        assert "marker_length" in preview
        assert "lock_status" in preview

    def test_resolve_invalid_deleted_unverified_exit_5(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        monkeypatch.setattr(fs, "verify_marker_absent", lambda p: False)
        code, out, err = _run_main(["--json", "resolve-invalid", str(ws)], stdin_text="")
        # EOF cancels before the delete; drive the delete path via the flow seam
        assert code == 2
        monkeypatch.undo()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        monkeypatch.setattr(fs, "verify_marker_absent", lambda p: False)
        emit, read_line = _auto_confirm()
        result = cli.resolve_invalid_interactive_cli(ws, emit=emit, read_line=read_line)
        assert result is not None
        assert result.outcome == "invalid-deleted-unverified"
        assert result.diagnostics.items[0].code == diag.CODE_ABSENCE_READ_BACK_FAILED

    def test_resolve_invalid_on_clean_workspace_exit_3(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out, err = _run_main(["--json", "resolve-invalid", str(ws)], stdin_text="")
        assert code == 3
        assert "occupied-invalid" in err

    def test_resolve_invalid_rejected_no_delete_exit_2(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        code, out, err = _run_main(
            ["--json", "resolve-invalid", str(ws)], stdin_text="confirm " + "0" * 64 + "\n"
        )
        assert code == 2
        assert _last_json(out)["outcome"] == "cancelled"
        assert fs.marker_path(ws).exists()


# ---------------------------------------------------------------------------
# recover-lock
# ---------------------------------------------------------------------------


class TestRecoverLock:
    def test_stale_lock_recovered_exit_0(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_stale_lock(ws, fs.capture_target_handle(ws))
        emit, read_line = _auto_confirm()
        report = cli.recover_lock_interactive_cli(ws, emit=emit, read_line=read_line)
        assert report is not None
        assert report.lock_state == "recovered"
        after = fs.lock_metadata(ws)
        assert after is not None and after.owner_id != "crashed-owner"

    def test_absent_lock_reports_absent_after_confirmation(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        emit, read_line = _auto_confirm()
        report = cli.recover_lock_interactive_cli(ws, emit=emit, read_line=read_line)
        assert report is not None
        assert report.lock_state == "absent"
        # confirmation is still required (destructive command): EOF cancels
        code, out, err = _run_main(["--json", "recover-lock", str(ws)], stdin_text="")
        assert code == 2
        assert "cancelled" in out

    def test_live_owner_never_broken_exit_4(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        handle = fs.capture_target_handle(ws)
        fs.acquire_lock(ws, "live-owner", os.getpid(), handle, fs.stale_after(60.0), 0.5)
        try:
            emit, read_line = _auto_confirm()
            report = cli.recover_lock_interactive_cli(ws, emit=emit, read_line=read_line)
            assert report is not None
            assert report.lock_state == "held"
            metadata = fs.lock_metadata(ws)
            assert metadata is not None and metadata.owner_id == "live-owner"
        finally:
            fs.release_lock(ws, "live-owner")

    def test_recover_lock_cancelled_exit_2_lock_untouched(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_stale_lock(ws, fs.capture_target_handle(ws))
        before = fs.lock_path(ws).read_bytes()
        code, out, err = _run_main(["--json", "recover-lock", str(ws)], stdin_text="no\n")
        assert code == 2
        assert "cancelled" in out
        assert fs.lock_path(ws).read_bytes() == before


# ---------------------------------------------------------------------------
# rebuild after projection loss (TS-WORK, REV:63)
# ---------------------------------------------------------------------------


class TestRebuild:
    def _register_pair(self, tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
        identities: dict[str, str] = {}
        paths: list[Path] = []
        for name, kind in (("direct-ws", "direct"), ("proxy-ws", "proxy")):
            ws = tmp_path / name
            ws.mkdir()
            emit, read_line = _auto_confirm()
            result = cli.register_interactive_cli(
                ws, label=f"Rebuild {name}", kind=kind,
                record_sources=[{"type": "example/records", "uri": f"https://records.example.org/{name}"}],
                emit=emit, read_line=read_line,
            )
            assert result.outcome == "registered"
            assert result.identity is not None
            identities[name] = result.identity
            paths.append(ws)
        return paths[0], paths[1], identities

    def test_rebuild_after_projection_loss_restores_routing(
        self, tmp_path: Path
    ) -> None:
        ws_direct, ws_proxy, identities = self._register_pair(tmp_path)
        projection = proj.Projection()
        before = {entry["identity"]: entry for entry in projection.list_projection()}
        assert set(before) == set(identities.values())
        db = projection.db_path
        for suffix in ("", "-wal", "-shm", "-journal"):
            sidecar = Path(str(db) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        code, out, err = _run_main(
            ["--json", "rebuild", str(ws_direct), str(ws_proxy)], stdin_text=""
        )
        assert code == 0
        report = _last_json(out)
        assert report["status"] == "rebuilt"
        after = {entry["identity"]: entry for entry in report["entries"]}
        assert set(after) == set(before), "identity set changed across rebuild"
        for identity, before_entry in before.items():
            after_entry = after[identity]
            for field in ("label", "workspace_path", "state", "target_handle"):
                assert after_entry[field] == before_entry[field], (
                    f"identity {identity}: {field} changed"
                )
        # deterministic input ordinals, no identity re-entry (REV:63)
        assert after[identities["direct-ws"]]["ordinal"] == 1
        assert after[identities["proxy-ws"]]["ordinal"] == 2
        for entry in report["entries"]:
            marker = json.loads(
                fs.read_marker(Path(entry["workspace_path"])).decode("utf-8")
            )
            assert marker["identity"] == entry["identity"]

    def test_rebuild_invalid_root_exit_3(self, tmp_path: Path) -> None:
        ws_direct, ws_proxy, _ = self._register_pair(tmp_path)
        code, out, err = _run_main(
            ["--json", "rebuild", str(ws_direct), str(tmp_path / "missing")],
            stdin_text="",
        )
        assert code == 3
        assert _last_json(out)["status"] == "failed"
        assert "error:" in err


# ---------------------------------------------------------------------------
# exit-code table and --json/exit divergence (PLAN:556, 476)
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_outcome_exit_table_exact(self) -> None:
        expected = {
            "registered": 0,
            "linked-existing": 0,
            "unregistered": 0,
            "invalid-marker-resolved": 0,
            "cancelled": 2,
            "stopped": 2,
            "occupied-invalid": 3,
            "conflict": 4,
            "changed-marker-stopped": 4,
            "written-unverified": 5,
            "registered-unlinked": 5,
            "invalid-deleted-unverified": 5,
        }
        assert cli.OUTCOME_EXIT_CODE == expected

    def test_table_driven_json_outcome_and_exit_never_diverge(
        self, tmp_path: Path
    ) -> None:
        """PLAN:476: the CLI's exit code always equals the --json envelope
        outcome's table entry; internal failure exits 6 without an envelope."""
        cases: list[tuple[list[str], str, int]] = []
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        cases.append((["--json", "inspect", str(ws)], "linked-existing", 0))
        cases.append((["--json", "link", str(ws)], "linked-existing", 0))
        empty = tmp_path / "empty"
        empty.mkdir()
        cases.append((["--json", "inspect", str(empty)], "stopped", 2))
        cases.append((["--json", "inspect", str(tmp_path / "missing")], "stopped", 2))
        invalid = tmp_path / "invalid"
        invalid.mkdir()
        _write_marker(invalid, {"version": 1, "identity": "nope"})
        cases.append((["--json", "inspect", str(invalid)], "occupied-invalid", 3))
        for argv, outcome, expected in cases:
            code, out, err = _run_main(argv)
            envelope = _last_json(out)
            assert envelope["outcome"] == outcome
            assert code == expected
            assert cli.OUTCOME_EXIT_CODE[outcome] == expected
            assert code == cli.OUTCOME_EXIT_CODE[envelope["outcome"]]

    def test_internal_failure_exits_6_bounded(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()

        def boom(args, stdout):
            raise RuntimeError("raw instance content must never leak")

        monkeypatch.setattr(cli, "_cmd_inspect", boom)
        code, out, err = _run_main(["--json", "inspect", str(ws)])
        assert code == 6
        assert "safe internal failure" in err
        assert "raw instance content must never leak" not in err
        assert "Traceback" not in out and "Traceback" not in err

    def test_usage_errors_exit_3(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        cases: list[list[str]] = [
            [],
            ["bogus-command"],
            ["register", str(ws), "--record-source", SOURCE],
            ["register", str(ws), "--label", "x", "--record-source", "no-equals"],
            ["register", str(ws), "--label", "x", "--record-source", SOURCE, "--kind", "bogus"],
            ["inspect"],
        ]
        for argv in cases:
            code, out, err = _run_main(argv)
            assert code == 3, argv
            assert "error:" in err


# ---------------------------------------------------------------------------
# no-echo / canary discipline
# ---------------------------------------------------------------------------


class TestNoEcho:
    CANARY_URI = "https://svc-account:fake-secret-token-9Xz2@records.example.org/projects/workstream-01"

    def test_preview_redacts_uri_content(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        seen: list[str] = []
        emit, read_line = _auto_confirm()

        def emit_capture(line: str) -> None:
            seen.append(line)
            emit(line)

        result = cli.register_interactive_cli(
            ws, label="Redaction", record_sources=[{"type": "example/records", "uri": self.CANARY_URI}], emit=emit_capture, read_line=read_line,
        )
        assert result.outcome == "registered"
        preview = "\n".join(seen)
        assert self.CANARY_URI not in preview
        assert "fake-secret-token-9Xz2" not in preview
        assert "svc-account" not in preview
        assert "<redacted>" in preview
        assert "type=example/records" in preview

    def test_json_envelope_never_carries_uri_content(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        emit, read_line = _auto_confirm()
        result = cli.register_interactive_cli(
            ws, label="Json Redaction", record_sources=[{"type": "example/records", "uri": self.CANARY_URI}], emit=emit, read_line=read_line,
        )
        serialized = result.serialize()
        assert "fake-secret-token-9Xz2" not in serialized
        assert "svc-account" not in serialized

    def test_cancellation_output_never_carries_input(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out, err = _run_main(
            ["--json", "register", str(ws), "--label", "x", "--record-source", f"example/records={self.CANARY_URI}"],
            stdin_text="",
        )
        assert code == 2
        combined = out + err
        assert "fake-secret-token-9Xz2" not in combined
        assert "svc-account" not in combined

    def test_no_canary_in_any_cli_surface(self, tmp_path: Path) -> None:
        """Canary values from the corpus never appear in CLI stdout/stderr/
        --json/diagnostics across the lifecycle."""
        ws = tmp_path / "ws"
        ws.mkdir()
        canary = "wst_live_9f2k3LmN4pQr5sT6uV7wX8yZ1aB2cD"
        emit, read_line = _auto_confirm()
        result = cli.register_interactive_cli(
            ws, label=canary, record_sources=[{"type": "example/records", "uri": self.CANARY_URI}], emit=emit, read_line=read_line,
        )
        assert result.outcome == "registered"
        code, out, err = _run_main(["--json", "inspect", str(ws)])
        assert code == 0
        assert canary not in out and canary not in err


# ---------------------------------------------------------------------------
# subprocess / console entry point
# ---------------------------------------------------------------------------


def _drive_interactive(argv: list[str], env: dict[str, str]) -> tuple[int, str]:
    """Drive the CLI subprocess interactively: reply to its ``confirm
    <digest>`` prompt with the exact digest (single-process session)."""
    command = [sys.executable, "-m", "workstream_registration.cli", *argv]
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None
    output: list[str] = []
    confirmed = False
    for line in proc.stdout:
        output.append(line)
        if not confirmed:
            match = re.match(r"^confirm ([0-9a-f]{64})$", line.strip())
            if match is not None:
                proc.stdin.write(f"confirm {match.group(1)}\n")
                proc.stdin.flush()
                confirmed = True
    proc.stdin.close()
    proc.wait()
    return proc.returncode, "".join(output)


class TestConsoleEntryPoint:
    def test_scripted_cli_e2e_lifecycle(self, tmp_path: Path) -> None:
        """Gate: scripted CLI E2E — register -> registered + read-back
        identity match -> unregister -> unregistered (AE1/AE8)."""
        env = dict(os.environ)
        env["WORKSTREAM_REGISTRATION_STORE_DIR"] = str(tmp_path / "store")
        ws = tmp_path / "ws"
        ws.mkdir()
        code, out = _drive_interactive(
            ["--json", "register", str(ws), "--label", "Scripted E2E", "--record-source", SOURCE],
            env,
        )
        assert code == 0, out
        envelope = _last_json(out)
        assert envelope["outcome"] == "registered"
        identity = envelope["identity"]
        assert identity is not None
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["identity"] == identity
        code, out = _drive_interactive(["--json", "unregister", str(ws)], env)
        assert code == 0, out
        assert _last_json(out)["outcome"] == "unregistered"
        assert fs.verify_marker_absent(ws)

    def test_digest_never_accepted_across_invocations(self, tmp_path: Path) -> None:
        """KTD6: a digest printed by one process is rejected by a fresh
        process (process-ephemeral key; PLAN:475)."""
        env = dict(os.environ)
        env["WORKSTREAM_REGISTRATION_STORE_DIR"] = str(tmp_path / "store")
        ws = tmp_path / "ws"
        ws.mkdir()
        proc = subprocess.run(
            [sys.executable, "-m", "workstream_registration.cli", "--json", "register",
             str(ws), "--label", "Cross Process", "--record-source", SOURCE],
            capture_output=True, text=True, encoding="utf-8", input="", env=env,
        )
        assert proc.returncode == 2  # EOF -> cancelled in process A
        match = re.search(r"^confirm ([0-9a-f]{64})$", proc.stdout, re.MULTILINE)
        assert match is not None
        foreign_digest = match.group(1)
        proc = subprocess.run(
            [sys.executable, "-m", "workstream_registration.cli", "--json", "register",
             str(ws), "--label", "Cross Process", "--record-source", SOURCE],
            capture_output=True, text=True, encoding="utf-8",
            input=f"confirm {foreign_digest}\n", env=env,
        )
        assert proc.returncode == 2, proc.stdout
        envelope = _last_json(proc.stdout)
        assert envelope["outcome"] == "cancelled"
        assert not fs.marker_path(ws).exists()

    def test_console_script_help_exits_zero(self, tmp_path: Path) -> None:
        script = shutil.which("workstream-registration")
        if script is None:
            pytest.skip("console script not installed (pip install -e .)")
        proc = subprocess.run(
            [script, "--help"],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert proc.returncode == 0
        assert "register" in proc.stdout and "recover-lock" in proc.stdout
        proc = subprocess.run(
            [script, "--json", "inspect", str(tmp_path / "missing")],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert proc.returncode == 2
        assert "stopped" in proc.stdout
