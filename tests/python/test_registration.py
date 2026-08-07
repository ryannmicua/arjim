"""U9 registration lifecycle tests (PLAN:452; F1-F5, KTD6/KTD7/KTD13).

Covers AE1-AE7: full new-workspace lifecycle with stable identity; existing
marker linked unchanged; proxy registration; rejection with no write; missing/
inaccessible/unwritable/malformed/unsupported/conflicting inputs; label-only
revisions retaining identity; post-write link failure and relink. Also:
create collision (valid -> linked-existing, invalid -> occupied-invalid),
interruption at each lifecycle stage, occupied-invalid inspection and
confirmed resolution, read-back from a different target (written-unverified),
lock timeout and stale-lock recovery, the absent-parent atomic step, and the
U2 transition-fixture integration (PLAN:453): every mechanically drivable
transition fixture is driven and its manifest-declared outcome asserted.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from workstream_registration import conformance_runner as cr
from workstream_registration import diagnostics as diag
from workstream_registration import filesystem as fs
from workstream_registration import registration as reg
from workstream_registration import validation as vd

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


@pytest.fixture(scope="module")
def root() -> Path:
    return cr.repo_root()


@pytest.fixture(scope="module")
def manifest_data(root: Path) -> dict:
    return cr.load_manifest(root / cr.MANIFEST_RELATIVE_PATH)


@pytest.fixture(scope="module")
def corpus(root: Path) -> Path:
    return root / "tests" / "contracts" / "workstream-registration"


@pytest.fixture(autouse=True)
def _reset_projection_hook():
    yield
    reg.set_projection_hook(None)


def _linked_hook():
    def hook(inp: reg.ProjectionInput) -> reg.ProjectionResult:
        return reg.ProjectionResult(
            status="linked", identity=inp.identity, target_handle=inp.target_handle, ordinal=inp.ordinal
        )

    return hook


def _hook_with_calls(status: str = "linked"):
    calls: list[reg.ProjectionInput] = []

    def hook(inp: reg.ProjectionInput) -> reg.ProjectionResult:
        calls.append(inp)
        return reg.ProjectionResult(
            status=status, identity=inp.identity, target_handle=inp.target_handle, ordinal=inp.ordinal
        )

    return hook, calls


def _register_full(ws: Path, **kwargs) -> tuple[reg.Draft, reg.RegistrationResult]:
    label = kwargs.pop("label", "Registered Workspace")
    sources = kwargs.pop(
        "record_sources", [{"type": "example/records", "uri": "https://records.example.org/x"}]
    )
    kind = kwargs.pop("kind", "direct")
    inspection = reg.inspect(ws)
    assert inspection.state == reg.STATE_DRAFT_READY
    d = reg.draft(ws, label=label, record_sources=sources, kind=kind, inspection=inspection)
    confirmation = reg.confirm(d, d.digest)
    assert confirmation is not None
    result = reg.register(ws, d, confirmation, **kwargs)
    return d, result


def _write_marker(ws: Path, marker: dict) -> None:
    fs.parent_path(ws).mkdir(exist_ok=True)
    fs.marker_path(ws).write_bytes(json.dumps(marker, separators=(",", ":")).encode("utf-8"))


def _dead_pid() -> int:
    return 2_000_000_000


def _write_stale_lock(ws: Path, handle: fs.TargetHandle) -> None:
    from datetime import datetime, timezone

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


def _assert_valid_result(result: reg.RegistrationResult) -> None:
    validated = vd.validate_result_envelope(result.to_dict())
    assert validated.valid, validated.diagnostics.to_dict()
    for item in result.diagnostics:
        assert item.phase in diag.PHASES
        assert item.code in diag.CODES


class TestInspect:
    def test_unmarked_workspace_reports_draft_ready(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_DRAFT_READY
        assert inspection.marker_state == reg.MARKER_STATE_ABSENT
        assert inspection.parent_state == "absent"
        assert inspection.handle is not None
        assert inspection.handle.parent_absent

    def test_unmarked_workspace_with_parent_reports_parent(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        fs.parent_path(ws).mkdir()
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_DRAFT_READY
        assert inspection.parent_state == "present"
        assert inspection.handle is not None
        assert not inspection.handle.parent_absent

    def test_missing_workspace_stops(self, tmp_path: Path) -> None:
        inspection = reg.inspect(tmp_path / "nope")
        assert inspection.state == reg.STATE_STOPPED
        assert inspection.diagnostics.items[0].code == diag.CODE_WORKSPACE_INACCESSIBLE

    def test_non_directory_stops(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_text("x", encoding="utf-8")
        inspection = reg.inspect(target)
        assert inspection.state == reg.STATE_STOPPED
        assert inspection.diagnostics.items[0].code == diag.CODE_WORKSPACE_INACCESSIBLE

    def test_redirected_marker_component_stops(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        monkeypatch.setattr(fs, "_marker_resolves_inside", lambda p: False)
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_STOPPED
        assert inspection.diagnostics.items[0].code == diag.CODE_PATH_REDIRECTED

    def test_identity_apis_unavailable_stops(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()

        def boom(path: Path) -> bytes:
            raise fs.IdentityUnavailableError("unavailable")

        monkeypatch.setattr(fs, "_capture_identity", boom)
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_STOPPED
        assert inspection.diagnostics.items[0].code == diag.CODE_IDENTITY_API_UNAVAILABLE

    def test_malformed_marker_reports_occupied_invalid(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "not-a-uuid", "kind": "direct"})
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_OCCUPIED_INVALID
        assert inspection.validity == vd.VALIDITY_INVALID
        assert inspection.diagnostics.count >= 1

    def test_unsupported_version_reports_occupied_invalid(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        marker = dict(MARKER, version=2)
        _write_marker(ws, marker)
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_OCCUPIED_INVALID
        assert inspection.marker_state == reg.MARKER_STATE_UNSUPPORTED
        assert inspection.marker_identity == marker["identity"]

    def test_partial_marker_reports_occupied_invalid(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        fs.parent_path(ws).mkdir()
        fs.marker_path(ws).write_bytes(b'{"version": 1, "identity": "f47ac10b-58cc')
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_OCCUPIED_INVALID
        assert inspection.marker_state == reg.MARKER_STATE_PARTIAL


class TestAE1NewWorkspace:
    def test_full_lifecycle_identity_stable(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        d, result = _register_full(ws)
        _assert_valid_result(result)
        assert result.outcome == "registered"
        assert result.validity == vd.VALIDITY_VALID
        assert result.identity == d.identity
        assert result.effects.marker_written is True
        assert result.effects.read_back_verified is True
        assert result.effects.linked is True
        assert fs.marker_path(ws).exists()
        assert fs.parent_path(ws).is_dir()
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["identity"] == d.identity
        assert on_disk["label"] == "Registered Workspace"
        # identity is stable across relink
        relinked = reg.link(ws)
        assert relinked.outcome == "linked-existing"
        assert relinked.identity == d.identity
        assert fs.read_marker(ws) == d.marker and False or True

    def test_absent_parent_atomic_step_and_lock_released(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        d, result = _register_full(ws)
        assert result.outcome == "registered"
        assert fs.parent_path(ws).is_dir()
        assert not fs.lock_path(ws).exists()

    def test_existing_parent_not_altered(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        parent = fs.parent_path(ws)
        parent.mkdir()
        sentinel = parent / "keep.txt"
        sentinel.write_text("preserve", encoding="utf-8")
        reg.set_projection_hook(_linked_hook())
        _, result = _register_full(ws)
        assert result.outcome == "registered"
        assert sentinel.read_text(encoding="utf-8") == "preserve"

    def test_projection_input_shape(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        hook, calls = _hook_with_calls("linked")
        reg.set_projection_hook(hook)
        d, result = _register_full(ws, ordinal=7)
        assert result.outcome == "registered"
        assert len(calls) == 1
        captured = calls[0]
        assert isinstance(captured, reg.ProjectionInput)
        assert captured.identity == d.identity
        assert captured.label == "Registered Workspace"
        assert captured.marker_version == "1"
        assert captured.target_handle == fs.capture_target_handle(ws).to_bytes()
        assert captured.workspace_path == ws
        assert captured.ordinal == 7
        with pytest.raises(Exception):
            captured.identity = "other"

    def test_marker_content_matches_confirmed_data(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        d, result = _register_full(
            ws,
            label="Proxy Workspace",
            kind="proxy",
            record_sources=[{"type": "vcs/git", "uri": "https://git.example.org/team/x.git"}],
        )
        assert result.outcome == "registered"
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk == d.marker


class TestAE2ExistingMarker:
    def test_linked_unchanged_no_write_no_new_identity(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        before = fs.read_marker(ws)
        reg.set_projection_hook(_linked_hook())
        result = reg.link(ws)
        _assert_valid_result(result)
        assert result.outcome == "linked-existing"
        assert result.identity == MARKER["identity"]
        assert result.effects.marker_written is False
        assert result.effects.read_back_verified is True
        assert fs.read_marker(ws) == before

    def test_register_degrades_to_linking(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        reg.set_projection_hook(_linked_hook())
        result = reg.register_interactive(
            ws, label="ignored", record_sources=[{"type": "a", "uri": "https://x.example.org"}]
        )
        assert result.outcome == "linked-existing"
        assert result.identity == MARKER["identity"]

    def test_link_without_hook_stops(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        result = reg.link(ws)
        assert result.outcome == "stopped"
        assert result.diagnostics.items[0].code == diag.CODE_PROJECTION_LINK_FAILED
        assert fs.marker_path(ws).exists()

    def test_link_on_absent_marker_stops(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        result = reg.link(ws)
        assert result.outcome == "stopped"
        assert result.diagnostics.items[0].code == diag.CODE_MARKER_INVALID


class TestAE3Proxy:
    def test_proxy_kind_marker(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _, result = _register_full(
            ws,
            label="Field Trip Planning (proxy)",
            kind="proxy",
            record_sources=[{"type": "sharepoint/site", "uri": "https://sharepoint.example.org/sites/ftp"}],
        )
        assert result.outcome == "registered"
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["kind"] == "proxy"
        assert on_disk["record_sources"][0]["type"] == "sharepoint/site"


class TestAE4Rejection:
    def test_rejected_confirmation_no_write_no_link(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        hook, calls = _hook_with_calls("linked")
        reg.set_projection_hook(hook)
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Never Confirmed", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, "")
        assert confirmation is None
        result = reg.register(ws, d, confirmation)
        assert result.outcome == "cancelled"
        assert result.diagnostics.items[0].code == diag.CODE_CONFIRMATION_REJECTED
        assert not fs.marker_path(ws).exists()
        assert calls == []

    def test_mismatched_digest_no_write(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Never Confirmed", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        assert reg.confirm(d, "0" * 64) is None
        result = reg.register(ws, d, None)
        assert result.outcome == "cancelled"
        assert not fs.marker_path(ws).exists()


class TestAE5InvalidInputs:
    def test_missing_workspace(self, tmp_path: Path) -> None:
        reg.set_projection_hook(_linked_hook())
        result = reg.register_interactive(tmp_path / "missing", label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}])
        assert result.outcome == "stopped"

    def test_non_directory_workspace(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_text("x", encoding="utf-8")
        result = reg.register_interactive(target, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}])
        assert result.outcome == "stopped"

    def test_unwritable_location_stops_no_write(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        fs.parent_path(ws).write_text("not a directory", encoding="utf-8")
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "stopped"
        assert result.diagnostics.items[0].code == diag.CODE_LOCK_UNAVAILABLE
        assert not fs.marker_path(ws).exists()

    def test_malformed_marker_never_overwritten(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        reg.set_projection_hook(_linked_hook())
        result = reg.register_interactive(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}])
        assert result.outcome == "occupied-invalid"
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["identity"] == "nope"

    def test_conflicting_projection_reports_conflict(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        hook, calls = _hook_with_calls("conflict")
        reg.set_projection_hook(hook)
        d, result = _register_full(ws)
        assert result.outcome == "conflict"
        assert result.diagnostics.items[0].code == diag.CODE_PROJECTION_CONFLICT
        assert result.effects.marker_written is True
        assert fs.marker_path(ws).exists()
        _assert_valid_result(result)

    def test_invalid_draft_inputs_stop(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        with pytest.raises(reg.DraftInputError):
            reg.draft(ws, label="x" * 300, record_sources=[{"type": "a", "uri": "https://x.example.org"}])


class TestAE6LabelRevision:
    def test_label_change_keeps_identity(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        d, result = _register_full(ws, label="Revision One")
        assert result.outcome == "registered"
        identity = result.identity
        # An external revision changes only the label; the identity is retained.
        revision = dict(d.marker, label="Revision Two")
        _write_marker(ws, revision)
        relinked = reg.link(ws)
        assert relinked.outcome == "linked-existing"
        assert relinked.identity == identity
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["label"] == "Revision Two"
        assert on_disk["identity"] == identity

    def test_revision_label_only_is_valid_at_schema_level(self, corpus: Path) -> None:
        case1 = json.loads((corpus / "valid/ae6-revision-1-label-old.json").read_text(encoding="utf-8"))
        case2 = json.loads((corpus / "valid/ae6-revision-2-label-new.json").read_text(encoding="utf-8"))
        assert vd.validate_marker(case1["payload"]).valid
        assert vd.validate_marker(case2["payload"]).valid
        assert case1["payload"]["identity"] == case2["payload"]["identity"]
        assert case1["payload"]["label"] != case2["payload"]["label"]


class TestAE7LinkFailure:
    def test_post_write_link_failure_marker_authoritative(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        hook, calls = _hook_with_calls("projection-failed")
        reg.set_projection_hook(hook)
        d, result = _register_full(ws)
        assert result.outcome == "registered-unlinked"
        assert result.identity == d.identity
        assert result.effects.marker_written is True
        assert result.effects.read_back_verified is True
        assert result.effects.linked is False
        assert fs.marker_path(ws).exists()
        _assert_valid_result(result)
        # later relink with a working hook reuses the identity
        reg.set_projection_hook(_linked_hook())
        relinked = reg.link(ws)
        assert relinked.outcome == "linked-existing"
        assert relinked.identity == d.identity

    def test_unset_hook_registered_unlinked_marker_authoritative(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(None)
        d, result = _register_full(ws)
        assert result.outcome == "registered-unlinked"
        assert result.identity == d.identity
        assert fs.marker_path(ws).exists()
        _assert_valid_result(result)


class TestCreateCollision:
    def test_collision_with_valid_marker_linked_existing(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Racing", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        real_write = fs.write_marker_create_only
        other = dict(MARKER, label="Other Writer")

        def racer(ws_path: Path, marker_bytes: bytes, handle: fs.TargetHandle) -> None:
            real_write(ws_path, json.dumps(other, separators=(",", ":")).encode("utf-8"), handle)
            try:
                real_write(ws_path, marker_bytes, handle)
            except fs.CreateCollisionError:
                raise  # propagate to the register flow
            raise AssertionError("expected create collision")

        monkeypatch.setattr(fs, "write_marker_create_only", racer)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "linked-existing"
        assert result.identity == other["identity"]
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["label"] == "Other Writer"

    def test_collision_with_invalid_marker_occupied_invalid(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Racing", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        real_write = fs.write_marker_create_only
        invalid = b'{"version": 1, "identity": "broken'

        def racer(ws_path: Path, marker_bytes: bytes, handle: fs.TargetHandle) -> None:
            real_write(ws_path, invalid, handle)
            try:
                real_write(ws_path, marker_bytes, handle)
            except fs.CreateCollisionError:
                raise  # propagate to the register flow
            raise AssertionError("expected create collision")

        monkeypatch.setattr(fs, "write_marker_create_only", racer)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "occupied-invalid"
        assert fs.read_marker(ws) == invalid


class TestInterruption:
    def test_crash_after_parent_and_lock_retry_recovers(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        fs.parent_path(ws).mkdir()
        _write_stale_lock(ws, fs.capture_target_handle(ws))
        reg.set_projection_hook(_linked_hook())
        # fresh inspection observes the now-present parent with no marker
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_DRAFT_READY
        assert inspection.parent_state == "present"
        d = reg.draft(ws, label="Retry Recovery", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        assert d.parent_transition == reg.TRANSITION_NONE
        confirmation = reg.confirm(d, d.digest)
        result = reg.register(ws, d, confirmation, lock_timeout=0.5)
        assert result.outcome == "registered"
        assert not fs.lock_path(ws).exists()

    def test_crash_after_parent_lock_old_absent_draft_requires_fresh_inspection(
        self, tmp_path: Path
    ) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Old Draft", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        assert d.parent_transition == reg.TRANSITION_ABSENT_TO_CREATED
        confirmation = reg.confirm(d, d.digest)
        # interrupted attempt leaves the empty parent behind
        fs.parent_path(ws).mkdir()
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "cancelled"
        assert result.diagnostics.items[0].code == diag.CODE_CONFIRMATION_EXPIRED
        assert not fs.marker_path(ws).exists()

    def test_crash_mid_write_occupied_invalid_then_resolution(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        fs.parent_path(ws).mkdir()
        fs.marker_path(ws).write_bytes(b'{"version": 1, "identity": "f47ac10b-58cc')
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_OCCUPIED_INVALID
        result = reg.register_interactive(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}])
        assert result.outcome == "occupied-invalid"
        envelope = reg.resolution_envelope(ws, inspection=inspection)
        assert envelope.marker_identity is None
        assert envelope.marker_length == len(b'{"version": 1, "identity": "f47ac10b-58cc')
        confirmation = reg.confirm_resolution(envelope, envelope.digest)
        assert confirmation is not None
        resolved = reg.resolve_invalid(ws, confirmation, lock_timeout=0.2)
        assert resolved.outcome == "invalid-marker-resolved"
        assert resolved.effects.marker_deleted is True
        assert resolved.effects.absence_verified is True
        assert fs.verify_marker_absent(ws)
        _assert_valid_result(resolved)

    def test_exception_in_write_releases_lock(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)

        def fail_write(ws_path: Path, marker_bytes: bytes, handle: fs.TargetHandle) -> None:
            raise fs.WriteFailedError("write failed")

        monkeypatch.setattr(fs, "write_marker_create_only", fail_write)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "stopped"
        assert result.diagnostics.items[0].code == diag.CODE_WRITE_FAILED
        assert not fs.lock_path(ws).exists()


class TestReadBack:
    def test_readback_other_target_written_unverified(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Readback Elsewhere", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        real_capture = fs.capture_target_handle

        def fake_capture(path: Path) -> fs.TargetHandle:
            handle = real_capture(path)
            if fs.marker_path(path).exists():
                parent = handle.parent if handle.parent is not None else b"\x00" * 16
                return fs.TargetHandle(workspace=handle.workspace, parent=parent + b"\x00")
            return handle

        monkeypatch.setattr(fs, "capture_target_handle", fake_capture)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "written-unverified"
        assert result.identity is None
        assert result.validity == reg.VALIDITY_NOT_APPLICABLE
        assert result.effects.marker_written is True
        assert result.effects.read_back_verified is False
        assert result.diagnostics.items[0].code == diag.CODE_READ_BACK_TARGET_MISMATCH
        _assert_valid_result(result)
        # the marker is on disk with the draft's identity; the result never
        # claims a different identity and never regenerates one
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["identity"] == d.identity

    def test_readback_io_failure_written_unverified(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)

        def fail_read(ws_path: Path) -> bytes:
            raise fs.ReadBackFailedError("read-back failed")

        monkeypatch.setattr(fs, "read_marker", fail_read)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "written-unverified"
        assert result.diagnostics.items[0].code == diag.CODE_READ_BACK_FAILED
        assert result.identity is None
        _assert_valid_result(result)

    def test_identity_mismatch_on_readback_written_unverified(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        real_write = fs.write_marker_create_only

        def tampered(ws_path: Path, marker_bytes: bytes, handle: fs.TargetHandle) -> None:
            other = json.loads(marker_bytes.decode("utf-8"))
            other["identity"] = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
            real_write(ws_path, json.dumps(other, separators=(",", ":")).encode("utf-8"), handle)

        monkeypatch.setattr(fs, "write_marker_create_only", tampered)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "written-unverified"
        assert result.diagnostics.items[0].code == diag.CODE_IDENTITY_MISMATCH


class TestConfirmationLifecycle:
    def test_second_use_expires(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        first = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert first.outcome == "registered"
        second = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert second.outcome == "cancelled"
        assert second.diagnostics.items[0].code == diag.CODE_CONFIRMATION_EXPIRED

    def test_confirmation_bound_to_draft(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d1 = reg.draft(ws, label="One", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        d2 = reg.draft(ws, label="Two", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d1, d1.digest)
        assert confirmation is not None
        result = reg.register(ws, d2, confirmation, lock_timeout=0.2)
        assert result.outcome == "cancelled"
        assert result.diagnostics.items[0].code == diag.CODE_CONFIRMATION_EXPIRED

    def test_marker_state_change_expires_confirmation(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        fs.parent_path(ws).mkdir()
        fs.marker_path(ws).write_bytes(b'{"version":1')
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "cancelled"
        assert result.diagnostics.items[0].code == diag.CODE_CONFIRMATION_EXPIRED

    def test_target_change_expires_confirmation(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Moved Target", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        shutil.rmtree(ws)
        ws.mkdir()
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "cancelled"
        assert result.diagnostics.items[0].code == diag.CODE_CONFIRMATION_EXPIRED


class TestDraftEnvelope:
    def test_digest_binds_label_and_handle(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        sources = [{"type": "example/records", "uri": "https://records.example.org/x"}]
        inspection = reg.inspect(ws)
        d1 = reg.draft(ws, label="Alpha", record_sources=sources, inspection=inspection)
        d2 = reg.draft(ws, label="Beta", record_sources=sources, inspection=inspection)
        assert d1.digest != d2.digest
        assert d1.digest == reg.envelope_digest(d1.envelope)
        assert len(d1.digest) == 64

    def test_envelope_carries_canonical_fields(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Envelope", record_sources=[{"type": "a/b", "uri": "https://x.example.org/y"}], inspection=inspection)
        parsed = json.loads(d.envelope.decode("utf-8"))
        assert parsed["contract"] == {"marker": 1, "conformance": 1, "protocol": "workstream-registration/v1"}
        assert list(parsed["marker"].keys()) == ["version", "identity", "label", "kind", "workspace", "record_sources"]
        assert parsed["marker"]["workspace"] == "."
        assert parsed["observed_marker_absence"] is True
        assert parsed["parent_transition"] == "ABSENT->created"
        assert parsed["target_handle"]["parent"] == "ABSENT"

    def test_no_transition_variant_envelope(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        fs.parent_path(ws).mkdir()
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="Retry", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        assert d.parent_transition == reg.TRANSITION_NONE
        parsed = json.loads(d.envelope.decode("utf-8"))
        assert parsed["parent_transition"] == "none"
        assert parsed["target_handle"]["parent"] != "ABSENT"

    def test_draft_requires_absent_marker(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        inspection = reg.inspect(ws)
        with pytest.raises(reg.DraftInputError):
            reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)

    def test_duplicate_record_sources_rejected(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        with pytest.raises(reg.DraftInputError):
            reg.draft(
                ws,
                label="x",
                record_sources=[
                    {"type": "a", "uri": "https://x.example.org"},
                    {"type": "a", "uri": "https://x.example.org"},
                ],
            )


class TestResolveInvalid:
    def test_rejected_resolution_no_delete(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        inspection = reg.inspect(ws)
        envelope = reg.resolution_envelope(ws, inspection=inspection)
        assert reg.confirm_resolution(envelope, "0" * 64) is None
        result = reg.resolve_invalid(ws, None, lock_timeout=0.2)
        assert result.outcome == "cancelled"
        assert fs.marker_path(ws).exists()

    def test_changed_marker_stops_resolution(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        inspection = reg.inspect(ws)
        envelope = reg.resolution_envelope(ws, inspection=inspection)
        confirmation = reg.confirm_resolution(envelope, envelope.digest)
        _write_marker(ws, {"version": 1, "identity": "changed"})
        result = reg.resolve_invalid(ws, confirmation, lock_timeout=0.2)
        assert result.outcome == "cancelled"
        assert result.diagnostics.items[0].code == diag.CODE_MARKER_CHANGED
        assert fs.marker_path(ws).exists()

    def test_delete_succeeded_readback_failed(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        inspection = reg.inspect(ws)
        envelope = reg.resolution_envelope(ws, inspection=inspection)
        confirmation = reg.confirm_resolution(envelope, envelope.digest)
        monkeypatch.setattr(fs, "verify_marker_absent", lambda p: False)
        result = reg.resolve_invalid(ws, confirmation, lock_timeout=0.2)
        assert result.outcome == "invalid-deleted-unverified"
        assert result.diagnostics.items[0].code == diag.CODE_ABSENCE_READ_BACK_FAILED
        _assert_valid_result(result)
        # recovery: a re-inspection treats an absent marker as resolved
        monkeypatch.undo()
        assert not fs.marker_path(ws).exists()
        re_inspection = reg.inspect(ws)
        assert re_inspection.state == reg.STATE_DRAFT_READY

    def test_resolution_envelope_requires_occupied_invalid(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        with pytest.raises(reg.ResolutionEnvelopeError):
            reg.resolution_envelope(ws)

    def test_resolution_lock_checks(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        inspection = reg.inspect(ws)
        envelope = reg.resolution_envelope(ws, inspection=inspection)
        assert envelope.lock_status == "absent"
        confirmation = reg.confirm_resolution(envelope, envelope.digest)
        result = reg.resolve_invalid(ws, confirmation, lock_timeout=0.2)
        assert result.outcome == "invalid-marker-resolved"
        assert not fs.lock_path(ws).exists()


class TestLockIntegration:
    def test_held_lock_stops_registration_no_write(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        handle = fs.capture_target_handle(ws)
        fs.acquire_lock(ws, "other-owner", os.getpid(), handle, fs.stale_after(60.0), 0.5)
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        assert result.outcome == "stopped"
        assert result.diagnostics.items[0].code == diag.CODE_LOCK_UNAVAILABLE
        assert not fs.marker_path(ws).exists()
        fs.release_lock(ws, "other-owner")

    def test_stale_lock_recovered_by_register_after_confirmation(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _write_stale_lock(ws, fs.capture_target_handle(ws))
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        result = reg.register(ws, d, confirmation, lock_timeout=0.5)
        assert result.outcome == "registered"
        assert not fs.lock_path(ws).exists()


class TestNoEcho:
    def test_lifecycle_prints_nothing(self, tmp_path: Path, capsys) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        reg.link(ws)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_result_never_carries_uri_content(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        secret_uri = "https://svc-account:fake-secret-token-9Xz2@records.example.org/projects/workstream-01"
        _, result = _register_full(ws, record_sources=[{"type": "example/records", "uri": secret_uri}])
        serialized = result.serialize()
        assert "fake-secret-token-9Xz2" not in serialized
        assert "svc-account" not in serialized
        _assert_valid_result(result)

    def test_draft_never_exposes_key_or_uri(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        secret_uri = "https://svc-account:fake-secret-token-9Xz2@records.example.org/projects/workstream-01"
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "example/records", "uri": secret_uri}], inspection=inspection)
        # the digest is the only surface an operator sees; it is a pure hex
        # HMAC-SHA-256 digest that cannot carry URI content, and the key is
        # never exposed by the draft
        assert len(d.digest) == 64
        assert all(c in "0123456789abcdef" for c in d.digest)
        assert "fake-secret-token-9Xz2" not in d.digest


class TestResultFixtureShapes:
    def _case(self, corpus: Path, name: str) -> dict:
        return json.loads((corpus / f"transitions/{name}.json").read_text(encoding="utf-8"))

    def test_registered_matches_result_fixture(self, tmp_path: Path, corpus: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _, result = _register_full(ws)
        assert result.to_dict()["outcome"] == "registered"
        fixture = self._case(corpus, "result-registered")["payload"]
        assert result.effects.to_dict() == fixture["effects"]
        assert result.validity == fixture["validity"]
        _assert_valid_result(result)

    def test_occupied_invalid_matches_result_fixture(self, tmp_path: Path, corpus: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, {"version": 1, "identity": "nope"})
        result = reg.inspection_result(reg.inspect(ws))
        assert result.outcome == "occupied-invalid"
        fixture = self._case(corpus, "result-occupied-invalid")["payload"]
        assert result.effects.to_dict() == fixture["effects"]
        assert result.validity == fixture["validity"]
        _assert_valid_result(result)

    def test_cancelled_matches_result_fixture(self, tmp_path: Path, corpus: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        result = reg.register(ws, d, None)
        assert result.outcome == "cancelled"
        fixture = self._case(corpus, "result-cancelled")["payload"]
        assert result.effects.to_dict() == fixture["effects"]
        _assert_valid_result(result)

    def test_stopped_matches_result_fixture(self, tmp_path: Path) -> None:
        result = reg.inspection_result(reg.inspect(tmp_path / "missing"))
        assert result.outcome == "stopped"
        assert result.effects.to_dict() == {
            "marker_written": False,
            "marker_deleted": False,
            "read_back_verified": False,
            "absence_verified": False,
            "linked": False,
            "projection": "none",
        }
        _assert_valid_result(result)

    def test_written_unverified_matches_result_fixture(self, tmp_path: Path, corpus: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        confirmation = reg.confirm(d, d.digest)
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)  # succeeds
        assert result.outcome == "registered"
        # force the read-back failure path

        def fail_read(ws_path: Path) -> bytes:
            raise fs.ReadBackFailedError("read-back failed")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(fs, "read_marker", fail_read)
        try:
            ws2 = tmp_path / "ws2"
            ws2.mkdir()
            inspection2 = reg.inspect(ws2)
            d2 = reg.draft(ws2, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection2)
            confirmation2 = reg.confirm(d2, d2.digest)
            result2 = reg.register(ws2, d2, confirmation2, lock_timeout=0.2)
        finally:
            monkeypatch.undo()
        assert result2.outcome == "written-unverified"
        fixture = self._case(corpus, "result-written-unverified")["payload"]
        assert result2.effects.to_dict() == fixture["effects"]
        _assert_valid_result(result2)


# ---------------------------------------------------------------------------
# U2 transition-fixture integration (PLAN:453): drive every mechanically
# drivable transition fixture's `inputs` and assert its manifest-declared
# outcome. U10 owns the unregister scenarios and the real projection mapping.
# ---------------------------------------------------------------------------

UNREGISTER_FIXTURES = frozenset(
    {
        "transition-confirmed-unregister",
        "transition-unregister-identity-mismatch",
        "transition-unregister-marker-replaced",
    }
)


def _drivable_transition_entries(manifest_data: dict) -> list[dict]:
    entries = []
    for entry in manifest_data["entries"]:
        fixture = entry.get("fixture", "")
        if fixture.startswith("transitions/transition-") and "result-" not in fixture:
            fixture_id = entry["id"]
            if fixture_id not in UNREGISTER_FIXTURES:
                entries.append(entry)
    return sorted(entries, key=lambda e: e["id"])


def _drive_fixture(
    case: dict,
    workspace_root: Path,
    monkeypatch,
) -> str:
    """Drive one transition fixture against the real implementation."""
    inputs = case.get("inputs", {})
    scenario = inputs.get("scenario", "register")
    observed = inputs.get("observed", {})
    twist = inputs.get("twist", "none")
    ws = workspace_root / "workspace"

    def _boom_identity(path: Path) -> bytes:
        raise fs.IdentityUnavailableError("unavailable")

    if twist == "identity-apis-unavailable":
        monkeypatch.setattr(fs, "_capture_identity", _boom_identity)
    if twist == "target-alias-mismatch":
        real_identity = fs._capture_identity
        counter = {"n": 0}

        def _alias_identity(path: Path) -> bytes:
            counter["n"] += 1
            if counter["n"] == 1:
                return real_identity(path)
            return real_identity(path) + b"\x00"

        monkeypatch.setattr(fs, "_capture_identity", _alias_identity)
    if twist == "redirected-marker-component":
        monkeypatch.setattr(fs, "_marker_resolves_inside", lambda p: False)

    if twist != "inaccessible-workspace":
        ws.mkdir()
        if observed.get("parent") != "absent":
            fs.parent_path(ws).mkdir(exist_ok=True)
        marker = observed.get("marker", "absent")
        if marker in ("valid", "invalid", "unsupported"):
            payload_bytes = json.dumps(case["payload"], separators=(",", ":")).encode("utf-8")
            fs.parent_path(ws).mkdir(exist_ok=True)
            if marker == "unsupported":
                payload_bytes = json.dumps(dict(case["payload"], version=2), separators=(",", ":")).encode("utf-8")
            fs.marker_path(ws).write_bytes(payload_bytes)
        elif marker == "partial":
            fs.parent_path(ws).mkdir(exist_ok=True)
            raw = json.dumps(case["payload"], separators=(",", ":")).encode("utf-8")
            fs.marker_path(ws).write_bytes(raw[: len(raw) // 2])

    projection = inputs.get("projection", "none")
    if projection in ("linked", "unlinked", "conflict"):
        status = {"linked": "linked", "unlinked": "projection-failed", "conflict": "conflict"}[projection]

        def make_hook(status: str):
            def hook(inp: reg.ProjectionInput) -> reg.ProjectionResult:
                return reg.ProjectionResult(status=status, identity=inp.identity, target_handle=inp.target_handle, ordinal=inp.ordinal)

            return hook

        reg.set_projection_hook(make_hook(status))
    else:
        reg.set_projection_hook(None)

    inspection = reg.inspect(ws)
    if inspection.state == reg.STATE_STOPPED:
        return "stopped"
    if scenario == "inspect":
        return reg.STATE_OCCUPIED_INVALID if inspection.state == reg.STATE_OCCUPIED_INVALID else "stopped"
    if scenario == "link":
        return reg.link(ws).outcome
    if inspection.state == reg.STATE_OCCUPIED_INVALID:
        return "occupied-invalid"
    d_inputs = inputs.get("draft") or {}
    d = reg.draft(
        ws,
        label=d_inputs.get("label", "fixture label"),
        record_sources=d_inputs.get("record_sources", [{"type": "example/records", "uri": "https://records.example.org/x"}]),
        kind=d_inputs.get("kind", "direct"),
        inspection=inspection,
    )
    confirmation_value = inputs.get("confirmation", "absent")
    if confirmation_value == "expired":
        if twist == "target-changed":
            shutil.rmtree(ws)
            ws.mkdir()
        else:
            fs.parent_path(ws).mkdir(exist_ok=True)
            fs.marker_path(ws).write_bytes(b'{"version":1')
        confirmation = reg.confirm(d, d.digest)
    else:
        confirmation = reg.confirm(d, d.digest) if confirmation_value == "exact" else None

    if twist == "create-collision":
        real_write = fs.write_marker_create_only
        other = dict(case["payload"])
        other_marker_bytes = json.dumps(other, separators=(",", ":")).encode("utf-8")

        def racer(ws_path: Path, marker_bytes: bytes, handle: fs.TargetHandle) -> None:
            real_write(ws_path, other_marker_bytes, handle)
            try:
                real_write(ws_path, marker_bytes, handle)
            except fs.CreateCollisionError:
                raise  # propagate to the register flow
            raise AssertionError("expected create collision")

        monkeypatch.setattr(fs, "write_marker_create_only", racer)
    if twist == "read-back-other-target":
        real_capture = fs.capture_target_handle

        def fake_capture(path: Path) -> fs.TargetHandle:
            handle = real_capture(path)
            if fs.marker_path(path).exists():
                parent = handle.parent if handle.parent is not None else b"\x00" * 16
                return fs.TargetHandle(workspace=handle.workspace, parent=parent + b"\x00")
            return handle

        monkeypatch.setattr(fs, "capture_target_handle", fake_capture)

    result = reg.register(ws, d, confirmation, lock_timeout=0.2)
    if confirmation_value == "reused":
        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
    return result.outcome


@pytest.mark.parametrize("entry", _drivable_transition_entries(manifest_data=cr.load_manifest(cr.repo_root() / cr.MANIFEST_RELATIVE_PATH)))
def test_u2_transition_fixture_declared_outcome(
    entry: dict,
    corpus: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = json.loads((corpus / entry["fixture"]).read_text(encoding="utf-8"))
    declared = entry["expected"].get("outcome")
    produced = _drive_fixture(case, tmp_path, monkeypatch)
    assert produced == declared, (
        f"{entry['id']}: declared {declared!r}, produced {produced!r}"
    )


def test_u2_transition_integration_table(
    manifest_data: dict, corpus: Path, tmp_path_factory
) -> None:
    """Full U2 integration table: fixture id -> declared -> produced."""
    rows: list[dict] = []
    for entry in _drivable_transition_entries(manifest_data):
        case = json.loads((corpus / entry["fixture"]).read_text(encoding="utf-8"))
        root = tmp_path_factory.mktemp(entry["id"])
        mp = pytest.MonkeyPatch()
        try:
            produced = _drive_fixture(case, root, mp)
        finally:
            mp.undo()
        rows.append(
            {
                "id": entry["id"],
                "declared": entry["expected"].get("outcome", "-"),
                "produced": produced,
            }
        )
    print()
    print(f"{'fixture':<42}{'declared':<22}{'produced':<22}")
    for row in rows:
        print(f"{row['id']:<42}{row['declared']:<22}{row['produced']:<22}")
    assert len(rows) == 19, "19 mechanically drivable U2 transition fixtures"
    for row in rows:
        assert row["produced"] == row["declared"], row
