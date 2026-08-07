"""U10 unregister tests (PLAN:464-465; KTD10 PLAN:195; protocol 4.4-4.5, 11).

Covers AE8 (confirmed unregister deletes, absence verified, ``unregistered``;
a later re-registration generates a fresh identity); changed marker/target/
identity at any re-read (each -> ``changed-marker-stopped``, no delete);
absent marker (stopped, no delete); present-absent-present confirmation
invalidation; non-cooperating replacement stops without deletion; stale-lock
recovery; the registered-but-unlinked marker stays deletable (marker
authority); and the U2 unregister fixture integration (PLAN:465): every
unregister transition fixture is driven and its manifest-declared outcome
asserted.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from workstream_registration import conformance_runner as cr
from workstream_registration import diagnostics as diag
from workstream_registration import filesystem as fs
from workstream_registration import projection as proj
from workstream_registration import registration as reg
from workstream_registration import unregister as unr
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

UNREGISTER_FIXTURES = frozenset(
    {
        "transition-confirmed-unregister",
        "transition-unregister-identity-mismatch",
        "transition-unregister-marker-replaced",
    }
)


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


def _failing_hook():
    def hook(inp: reg.ProjectionInput) -> reg.ProjectionResult:
        return reg.ProjectionResult(
            status="projection-failed", identity=inp.identity, target_handle=inp.target_handle, ordinal=inp.ordinal
        )

    return hook


def _register_full(ws: Path, **kwargs) -> tuple[reg.Draft, reg.RegistrationResult]:
    label = kwargs.pop("label", "Registered Workspace")
    sources = kwargs.pop(
        "record_sources", [{"type": "example/records", "uri": "https://records.example.org/x"}]
    )
    inspection = reg.inspect(ws)
    assert inspection.state == reg.STATE_DRAFT_READY
    d = reg.draft(ws, label=label, record_sources=sources, inspection=inspection)
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
    now = time.time()
    metadata = fs.LockMetadata(
        owner_id="crashed-owner",
        pid=_dead_pid(),
        target_handle=handle,
        started_at=datetime.fromtimestamp(now - 3600, tz=timezone.utc).isoformat(),
        lease_until=datetime.fromtimestamp(now - 3600, tz=timezone.utc).isoformat(),
    )
    fs.lock_path(ws).write_bytes(metadata.to_bytes())


def _assert_valid_result(result: reg.RegistrationResult) -> None:
    validated = vd.validate_result_envelope(result.to_dict())
    assert validated.valid, validated.diagnostics.to_dict()
    for item in result.diagnostics:
        assert item.phase in diag.PHASES
        assert item.code in diag.CODES


def _bound_unregister(ws: Path) -> unr.UnregisterConfirmation:
    envelope = unr.unregister_envelope(ws)
    confirmation = unr.confirm_unregister(envelope, envelope.digest)
    assert confirmation is not None
    return confirmation


class TestConfirmedUnregisterAE8:
    def test_confirmed_unregister_deletes_and_verifies_absence(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        d, result = _register_full(ws)
        assert result.outcome == "registered"
        confirmation = _bound_unregister(ws)
        unreg_result = unr.unregister(ws, confirmation, lock_timeout=0.5)
        _assert_valid_result(unreg_result)
        assert unreg_result.outcome == "unregistered"
        assert unreg_result.validity == reg.VALIDITY_NOT_APPLICABLE
        assert unreg_result.effects.marker_written is False
        assert unreg_result.effects.marker_deleted is True
        assert unreg_result.effects.read_back_verified is False
        assert unreg_result.effects.absence_verified is True
        assert unreg_result.effects.linked is False
        assert unreg_result.effects.projection == "none"
        assert not fs.marker_path(ws).exists()
        assert not fs.lock_path(ws).exists()
        assert unreg_result.identity is None

    def test_result_matches_unregistered_fixture(self, tmp_path: Path, corpus: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        unreg_result = unr.unregister(ws, confirmation)
        fixture = json.loads((corpus / "transitions" / "result-unregistered.json").read_text(encoding="utf-8"))
        assert unreg_result.outcome == fixture["payload"]["outcome"]
        assert unreg_result.validity == fixture["payload"]["validity"]
        assert unreg_result.effects.to_dict() == fixture["payload"]["effects"]

    def test_re_registration_generates_fresh_identity(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        d1, result = _register_full(ws)
        assert result.outcome == "registered"
        unr.unregister(ws, _bound_unregister(ws))
        assert not fs.marker_path(ws).exists()
        inspection = reg.inspect(ws)
        d2 = reg.draft(
            ws, label="Re-registered", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection
        )
        result2 = reg.register(ws, d2, reg.confirm(d2, d2.digest))
        assert result2.outcome == "registered"
        assert d2.identity != d1.identity
        assert json.loads(fs.read_marker(ws).decode("utf-8"))["identity"] == d2.identity

    def test_projection_entry_removed_after_unregister(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        reg.set_projection_hook(projection.update)
        d, result = _register_full(ws)
        assert result.outcome == "registered"
        assert projection.find_by_identity(d.identity) is not None
        unreg_result = unr.unregister(ws, _bound_unregister(ws), projection=projection)
        assert unreg_result.outcome == "unregistered"
        assert projection.find_by_identity(d.identity) is None


class TestChangedMarkerStopped:
    def test_changed_marker_content_stops_without_delete(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        d, _ = _register_full(ws)
        confirmation = _bound_unregister(ws)
        replaced = json.loads(fs.read_marker(ws).decode("utf-8"))
        replaced["label"] = "Changed Between Reads"
        _write_marker(ws, replaced)
        unreg_result = unr.unregister(ws, confirmation)
        _assert_valid_result(unreg_result)
        assert unreg_result.outcome == "changed-marker-stopped"
        assert unreg_result.effects.marker_deleted is False
        assert fs.marker_path(ws).exists()
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["label"] == "Changed Between Reads"
        assert on_disk["identity"] == d.identity

    def test_changed_identity_stops_without_delete(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        replaced = json.loads(fs.read_marker(ws).decode("utf-8"))
        replaced["identity"] = "dddddddd-eeee-4fff-8000-111111111111"
        _write_marker(ws, replaced)
        unreg_result = unr.unregister(ws, confirmation)
        assert unreg_result.outcome == "changed-marker-stopped"
        assert unreg_result.effects.marker_deleted is False
        assert fs.marker_path(ws).exists()
        assert (
            unreg_result.diagnostics.items[0].code == diag.CODE_IDENTITY_MISMATCH
        )

    def test_changed_target_stops_without_delete(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        real_capture = fs.capture_target_handle

        def fake_capture(path: Path) -> fs.TargetHandle:
            handle = real_capture(path)
            parent = handle.parent if handle.parent is not None else b"\x00" * 16
            return fs.TargetHandle(workspace=handle.workspace, parent=parent + b"\x00")

        monkeypatch.setattr(fs, "capture_target_handle", fake_capture)
        unreg_result = unr.unregister(ws, confirmation)
        assert unreg_result.outcome == "changed-marker-stopped"
        assert unreg_result.effects.marker_deleted is False
        assert fs.marker_path(ws).exists()
        assert unreg_result.diagnostics.items[0].code == diag.CODE_TARGET_CHANGED

    def test_absent_marker_stops_without_delete(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        fs.marker_path(ws).unlink()
        unreg_result = unr.unregister(ws, confirmation)
        _assert_valid_result(unreg_result)
        assert unreg_result.outcome == "stopped"
        assert unreg_result.effects.marker_deleted is False
        assert not fs.marker_path(ws).exists()

    def test_absent_marker_at_inspection_no_envelope(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        with pytest.raises(unr.UnregisterEnvelopeError):
            unr.unregister_envelope(ws)

    def test_present_absent_present_invalidation(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        fs.marker_path(ws).unlink()
        assert not fs.marker_path(ws).exists()
        reappeared = {
            "version": 1,
            "identity": "eeeeeeee-ffff-4000-8111-222222222222",
            "label": "Reappeared Marker",
            "kind": "direct",
            "workspace": ".",
            "record_sources": [{"type": "a", "uri": "https://x.example.org"}],
        }
        _write_marker(ws, reappeared)
        unreg_result = unr.unregister(ws, confirmation)
        assert unreg_result.outcome == "changed-marker-stopped"
        assert unreg_result.effects.marker_deleted is False
        on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
        assert on_disk["identity"] == reappeared["identity"]
        assert on_disk["label"] == "Reappeared Marker"

    def test_non_cooperating_lock_stops_without_delete(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        handle = fs.capture_target_handle(ws)
        with fs.registration_lock(ws, handle, timeout=0.2):
            unreg_result = unr.unregister(ws, confirmation, lock_timeout=0.3)
        assert unreg_result.outcome == "changed-marker-stopped"
        assert unreg_result.effects.marker_deleted is False
        assert fs.marker_path(ws).exists()
        assert unreg_result.diagnostics.items[0].code == diag.CODE_LOCK_UNAVAILABLE
        assert confirmation.consumed is True

    def test_stale_lock_recovered_then_unregisters(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        _write_stale_lock(ws, fs.capture_target_handle(ws))
        unreg_result = unr.unregister(ws, confirmation, lock_timeout=0.5)
        assert unreg_result.outcome == "unregistered"
        assert not fs.marker_path(ws).exists()

    def test_rejected_digest_no_delete(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        envelope = unr.unregister_envelope(ws)
        assert unr.confirm_unregister(envelope, "0" * 64) is None
        unreg_result = unr.unregister(ws, None)
        _assert_valid_result(unreg_result)
        assert unreg_result.outcome == "cancelled"
        assert unreg_result.effects.marker_deleted is False
        assert fs.marker_path(ws).exists()

    def test_consumed_confirmation_cancelled(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws)
        confirmation = _bound_unregister(ws)
        first = unr.unregister(ws, confirmation)
        assert first.outcome == "unregistered"
        ws2 = tmp_path / "ws2"
        ws2.mkdir()
        reg.set_projection_hook(_linked_hook())
        _register_full(ws2)
        second = unr.unregister(ws2, confirmation)
        assert second.outcome == "cancelled"
        assert second.diagnostics.items[0].code == diag.CODE_CONFIRMATION_EXPIRED
        assert fs.marker_path(ws2).exists()


class TestRegisteredUnlinkedSemantics:
    def test_unregister_on_registered_unlinked_still_deletes(self, tmp_path: Path) -> None:
        """Marker authority: a registered-but-unlinked marker is still
        deletable by a confirmed unregister (protocol 4.11; PLAN:132)."""
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(_failing_hook())
        d, result = _register_full(ws)
        assert result.outcome == "registered-unlinked"
        assert fs.marker_path(ws).exists()
        confirmation = _bound_unregister(ws)
        unreg_result = unr.unregister(ws, confirmation)
        assert unreg_result.outcome == "unregistered"
        assert not fs.marker_path(ws).exists()


# ---------------------------------------------------------------------------
# U2 unregister fixture integration (PLAN:465): drive every unregister
# transition fixture's `inputs` and assert its manifest-declared outcome.
# ---------------------------------------------------------------------------


def _unregister_fixture_entries(manifest_data: dict) -> list[dict]:
    entries = []
    for entry in manifest_data["entries"]:
        if entry["id"] in UNREGISTER_FIXTURES:
            entries.append(entry)
    return sorted(entries, key=lambda e: e["id"])


def _drive_unregister_fixture(case: dict, workspace_root: Path) -> str:
    """Drive one unregister transition fixture against the implementation."""
    inputs = case.get("inputs", {})
    twist = inputs.get("twist", "none")
    ws = workspace_root / "workspace"
    ws.mkdir()
    fs.parent_path(ws).mkdir(exist_ok=True)
    payload = case["payload"]
    marker_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    fs.marker_path(ws).write_bytes(marker_bytes)
    bound_identity = inputs.get("bound_identity") or payload["identity"]
    if bound_identity != payload["identity"]:
        bound_marker = dict(payload, identity=bound_identity)
        fs.marker_path(ws).write_bytes(
            json.dumps(bound_marker, separators=(",", ":")).encode("utf-8")
        )
        envelope = unr.unregister_envelope(ws)
        fs.marker_path(ws).write_bytes(marker_bytes)
    else:
        envelope = unr.unregister_envelope(ws)
    confirmation = unr.confirm_unregister(envelope, envelope.digest)
    if twist == "marker-replaced":
        replaced = dict(payload, label="Replaced Between Reads")
        fs.marker_path(ws).write_bytes(
            json.dumps(replaced, separators=(",", ":")).encode("utf-8")
        )
    result = unr.unregister(ws, confirmation, lock_timeout=0.5)
    return result.outcome


@pytest.mark.parametrize(
    "entry", _unregister_fixture_entries(cr.load_manifest(cr.repo_root() / cr.MANIFEST_RELATIVE_PATH))
)
def test_unregister_fixture_declared_outcome(
    entry: dict, corpus: Path, tmp_path: Path
) -> None:
    case = json.loads((corpus / entry["fixture"]).read_text(encoding="utf-8"))
    declared = entry["expected"].get("outcome")
    produced = _drive_unregister_fixture(case, tmp_path)
    assert produced == declared, f"{entry['id']}: declared {declared!r}, produced {produced!r}"


def test_unregister_fixture_integration_table(
    manifest_data: dict, corpus: Path, tmp_path_factory
) -> None:
    """Integration table: fixture id -> declared -> produced (PLAN:465)."""
    rows: list[dict] = []
    for entry in _unregister_fixture_entries(manifest_data):
        case = json.loads((corpus / entry["fixture"]).read_text(encoding="utf-8"))
        root = tmp_path_factory.mktemp(entry["id"])
        produced = _drive_unregister_fixture(case, root)
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
    assert len(rows) == 3, "3 unregister transition fixtures"
    for row in rows:
        assert row["produced"] == row["declared"], row
