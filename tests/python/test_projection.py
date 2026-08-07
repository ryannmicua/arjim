"""U10 projection tests (PLAN:464; PLAN:463; PLAN:553).

Covers the update boundary (linked / conflict / projection-failed, idempotency
key, same-key path+ordinal replacement); owner-only enforcement on this
Windows host via the built-in ``icacls`` tool with verification before use and
after creation, and fail-closed behavior when enforcement cannot be
established or pre-existing permissions are weaker; minimal schema with zero
record-source URI content (canary fixtures); transactional ordered-root
rebuild with symlink-alias deduplication retaining the first input's ordinal,
inaccessible-root failure leaving the previous projection unchanged, and
stale-entry repair; wiring of the real hook through
``registration.install_default_projection_hook``; and the invariant that
deleting the projection never unregisters (PLAN:319).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from workstream_registration import conformance_runner as cr
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

CANARY_URIS = (
    "https://svc-account:fake-secret-token-9Xz2@records.example.org/projects/workstream-01",
    "ssh://deploy:sup3r-fake-secret@git.example.org/workstream-registration.git",
)


@pytest.fixture(scope="module")
def root() -> Path:
    return cr.repo_root()


@pytest.fixture(scope="module")
def corpus(root: Path) -> Path:
    return root / "tests" / "contracts" / "workstream-registration"


@pytest.fixture(autouse=True)
def _reset_projection_hook():
    yield
    reg.set_projection_hook(None)


def _input(
    ws: Path,
    *,
    identity: str = MARKER["identity"],
    label: str = "Quarterly Planning",
    marker_version: str = "1",
    ordinal: int = 0,
) -> reg.ProjectionInput:
    return reg.ProjectionInput(
        identity=identity,
        label=label,
        marker_version=marker_version,
        target_handle=fs.capture_target_handle(ws).to_bytes(),
        workspace_path=ws,
        ordinal=ordinal,
    )


def _register_full(ws: Path, projection: proj.Projection, **kwargs) -> tuple[reg.Draft, reg.RegistrationResult]:
    label = kwargs.pop("label", "Registered Workspace")
    sources = kwargs.pop(
        "record_sources", [{"type": "example/records", "uri": "https://records.example.org/x"}]
    )
    reg.set_projection_hook(projection.update)
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


def _db_bytes(store: Path) -> bytes:
    return (store / proj.PROJECTION_DB_FILENAME).read_bytes()


def _existing_sidecars(store: Path) -> list[Path]:
    return [
        store / (proj.PROJECTION_DB_FILENAME + suffix)
        for suffix in ("-wal", "-shm", "-journal")
        if (store / (proj.PROJECTION_DB_FILENAME + suffix)).exists()
    ]


def _icacls_output(path: Path) -> str:
    proc = subprocess.run(["icacls", str(path)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _windows_principal() -> str:
    proc = subprocess.run(["whoami"], capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    return proc.stdout.strip()


class TestUpdateBoundary:
    def test_update_links_and_persists(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        result = projection.update(_input(ws, ordinal=7))
        assert result.status == "linked"
        assert result.identity == MARKER["identity"]
        assert result.target_handle == fs.capture_target_handle(ws).to_bytes()
        assert result.ordinal == 7
        rows = projection.list_projection()
        assert len(rows) == 1
        assert rows[0]["identity"] == MARKER["identity"]
        assert rows[0]["label"] == "Quarterly Planning"
        assert rows[0]["marker_version"] == "1"
        assert rows[0]["target_handle"] == base64.b64encode(
            fs.capture_target_handle(ws).to_bytes()
        ).decode("ascii")
        assert rows[0]["workspace_path"] == str(ws)
        assert rows[0]["state"] == "linked"
        assert rows[0]["ordinal"] == 7

    def test_update_is_idempotent(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        assert projection.update(_input(ws)).status == "linked"
        assert projection.update(_input(ws)).status == "linked"
        assert len(projection.list_projection()) == 1

    def test_same_key_update_replaces_path_and_ordinal(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        ws2 = tmp_path / "ws2"
        ws2.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        handle = fs.capture_target_handle(ws).to_bytes()
        first = reg.ProjectionInput(
            identity=MARKER["identity"], label="A", marker_version="1",
            target_handle=handle, workspace_path=ws, ordinal=1,
        )
        second = reg.ProjectionInput(
            identity=MARKER["identity"], label="A2", marker_version="1",
            target_handle=handle, workspace_path=ws2, ordinal=2,
        )
        assert projection.update(first).status == "linked"
        assert projection.update(second).status == "linked"
        rows = projection.list_projection()
        assert len(rows) == 1
        assert rows[0]["workspace_path"] == str(ws2)
        assert rows[0]["ordinal"] == 2
        assert rows[0]["label"] == "A2"

    def test_conflict_for_different_identity_on_one_target(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        assert projection.update(_input(ws)).status == "linked"
        other = _input(ws, identity="dddddddd-eeee-4fff-8000-111111111111", label="Other")
        result = projection.update(other)
        assert result.status == "conflict"
        assert result.identity == "dddddddd-eeee-4fff-8000-111111111111"
        rows = projection.list_projection()
        assert len(rows) == 1
        assert rows[0]["identity"] == MARKER["identity"]

    def test_conflict_does_not_touch_the_marker(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        _write_marker(ws, MARKER)
        before = fs.read_marker(ws)
        projection = proj.Projection(store_dir=tmp_path / "store")
        assert projection.update(_input(ws)).status == "linked"
        other = _input(ws, identity="dddddddd-eeee-4fff-8000-111111111111")
        assert projection.update(other).status == "conflict"
        assert fs.read_marker(ws) == before

    def test_race_between_select_and_insert_maps_to_conflict(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        assert projection.update(_input(ws)).status == "linked"
        real_connect = __import__("sqlite3").connect

        class _BlindSelect:
            def __init__(self, real):
                object.__setattr__(self, "_real", real)

            def __getattr__(self, name):
                return getattr(self._real, name)

            def execute(self, *a, **k):
                if a and a[0].startswith("SELECT identity FROM projection"):
                    return self._real.execute("SELECT 1 WHERE 0")
                return self._real.execute(*a, **k)

            def close(self):
                self._real.close()

        monkeypatch.setattr(
            proj.sqlite3, "connect",
            lambda *a, **k: _BlindSelect(real_connect(*a, **k)),
        )
        other = _input(ws, identity="dddddddd-eeee-4fff-8000-111111111111", label="Other")
        result = projection.update(other)
        assert result.status == "conflict"
        assert result.identity == "dddddddd-eeee-4fff-8000-111111111111"
        monkeypatch.undo()
        rows = projection.list_projection()
        assert len(rows) == 1
        assert rows[0]["identity"] == MARKER["identity"]

    def test_remove_returns_registered_unlinked(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        inp = _input(ws)
        assert projection.update(inp).status == "linked"
        result = projection.remove(inp.identity, inp.target_handle)
        assert result.status == "registered-unlinked"
        assert result.identity == inp.identity
        assert projection.list_projection() == []
        again = projection.remove(inp.identity, inp.target_handle)
        assert again.status == "registered-unlinked"
        assert again.ordinal is None

    def test_register_links_into_real_projection(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        d, result = _register_full(ws, projection)
        assert result.outcome == "registered"
        assert result.effects.linked is True
        assert projection.find_by_identity(d.identity) is not None


class TestWiring:
    def test_install_default_projection_hook(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        monkeypatch.setenv(proj.ENV_STORE_DIR, str(tmp_path / "store"))
        reg.install_default_projection_hook()
        assert reg.get_projection_hook() is not None
        inspection = reg.inspect(ws)
        d = reg.draft(
            ws, label="Wired", record_sources=[{"type": "a", "uri": "https://x.example.org"}],
            inspection=inspection,
        )
        result = reg.register(ws, d, reg.confirm(d, d.digest))
        assert result.outcome == "registered"
        assert result.effects.linked is True
        store = proj.Projection(store_dir=tmp_path / "store")
        assert store.find_by_identity(d.identity) is not None
        relink = reg.link(ws)
        assert relink.outcome == "linked-existing"

    def test_unset_hook_keeps_u9_mapping(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        reg.set_projection_hook(None)
        inspection = reg.inspect(ws)
        d = reg.draft(ws, label="x", record_sources=[{"type": "a", "uri": "https://x.example.org"}], inspection=inspection)
        result = reg.register(ws, d, reg.confirm(d, d.digest))
        assert result.outcome == "registered-unlinked"
        assert fs.marker_path(ws).exists()


class TestOwnerOnlyEnforcement:
    def test_owner_only_directory_database_and_sidecars(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        store = tmp_path / "store"
        projection = proj.Projection(store_dir=store)
        assert projection.update(_input(ws)).status == "linked"
        import sqlite3

        held = sqlite3.connect(str(store / proj.PROJECTION_DB_FILENAME))
        try:
            held.execute("CREATE TABLE IF NOT EXISTS sidecar_probe (x)")
            held.commit()
            sidecars = _existing_sidecars(store)
            assert sidecars, "WAL sidecars expected while a connection is open"
            projection._verify_sidecars(store)
        finally:
            held.close()
        principal = _windows_principal()
        for path in [store, store / proj.PROJECTION_DB_FILENAME, *_existing_sidecars(store)]:
            out = _icacls_output(path)
            first_line = out.splitlines()[0]
            assert principal.lower() in first_line.lower(), f"icacls {path}: {out}"
            lowered = out.lower()
            assert "everyone" not in lowered
            assert "authenticated users" not in lowered
            assert "builTIN\\users" not in lowered
            assert "\\users:" not in lowered

    def test_verify_round_trip_on_real_enforced_owner_only_directory(self, tmp_path: Path) -> None:
        directory = tmp_path / "enforced"
        directory.mkdir()
        proj._enforce_owner_only_windows(directory)
        proj._verify_owner_only_windows(directory)

    def test_inherited_ace_detected_and_gated_by_allow_inherited(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        principal = _windows_principal()

        class _FakeIcacls:
            returncode = 0
            stdout = f"{tmp_path}:\n{principal}:(I)(OI)(CI)(F)\n"

        real_run = proj.subprocess.run
        monkeypatch.setattr(
            proj.subprocess, "run",
            lambda *a, **k: real_run(*a, **k)
            if a and a[0] == ["whoami"]
            else _FakeIcacls(),
        )
        with pytest.raises(proj.ProjectionStoreError):
            proj._verify_owner_only_windows(tmp_path)
        proj._verify_owner_only_windows(tmp_path, allow_inherited=True)

    def test_verification_before_use_fails_closed_on_weaker_pre_existing(
        self, tmp_path: Path
    ) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        store = tmp_path / "store"
        store.mkdir()
        proc = subprocess.run(
            ["icacls", str(store), "/grant", "Everyone:(OI)(CI)F"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        projection = proj.Projection(store_dir=store)
        result = projection.update(_input(ws))
        assert result.status == "projection-failed"
        with pytest.raises(proj.ProjectionStoreError):
            projection.list_projection()
        assert not (store / proj.PROJECTION_DB_FILENAME).exists()

    def test_fails_closed_when_icacls_unavailable(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        store = tmp_path / "store"
        store.mkdir()
        monkeypatch.setattr(
            proj.subprocess, "run",
            lambda *a, **k: (_ for _ in ()).throw(OSError("icacls missing")),
        )
        projection = proj.Projection(store_dir=store)
        result = projection.update(_input(ws))
        assert result.status == "projection-failed"
        assert not (store / proj.PROJECTION_DB_FILENAME).exists()

    def test_fails_closed_when_icacls_rejects(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        store = tmp_path / "store"
        store.mkdir()

        class _Rejected:
            returncode = 5
            stdout = ""
            stderr = "Access is denied"

        monkeypatch.setattr(proj.subprocess, "run", lambda *a, **k: _Rejected())
        projection = proj.Projection(store_dir=store)
        result = projection.update(_input(ws))
        assert result.status == "projection-failed"

    def test_weak_stale_sidecar_fails_closed(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        store = tmp_path / "store"
        projection = proj.Projection(store_dir=store)
        assert projection.update(_input(ws)).status == "linked"
        sidecar = store / (proj.PROJECTION_DB_FILENAME + "-wal")
        shutil.copy(store / proj.PROJECTION_DB_FILENAME, sidecar)
        proc = subprocess.run(
            ["icacls", str(sidecar), "/grant", "Everyone:F"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        result = projection.update(_input(ws, label="retry"))
        assert result.status == "projection-failed"


class TestUriExclusion:
    def test_projection_contains_zero_record_source_uri_content(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        canary_marker = {
            "version": 1,
            "identity": "1a2b3c4d-5e6f-47a8-9b0c-1d2e3f4a5b6c",
            "label": "Canary userinfo URIs one",
            "kind": "direct",
            "workspace": ".",
            "record_sources": [
                {"type": "records/web", "uri": CANARY_URIS[0]},
                {"type": "ssh/access", "uri": CANARY_URIS[1]},
            ],
        }
        reg.set_projection_hook(projection.update)
        inspection = reg.inspect(ws)
        d = reg.draft(
            ws, label=canary_marker["label"],
            record_sources=canary_marker["record_sources"],
            inspection=inspection,
        )
        result = reg.register(ws, d, reg.confirm(d, d.digest))
        assert result.outcome == "registered"
        raw = _db_bytes(tmp_path / "store")
        for canary in CANARY_URIS:
            assert canary.encode("utf-8") not in raw
        for token in ("svc-account", "fake-secret-token-9Xz2", "deploy", "sup3r-fake-secret"):
            assert token.encode("utf-8") not in raw
        for row in projection.list_projection():
            blob = json.dumps(row, separators=(",", ":")).encode("utf-8")
            for canary in CANARY_URIS:
                assert canary.encode("utf-8") not in blob
            assert b"record_sources" not in blob
            assert b'"uri"' not in blob

    def test_schema_has_no_uri_field(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        projection = proj.Projection(store_dir=tmp_path / "store")
        assert projection.update(_input(ws)).status == "linked"
        raw = _db_bytes(tmp_path / "store").decode("utf-8", errors="replace")
        assert "record_sources" not in raw
        assert '"uri"' not in raw


class TestRebuild:
    def _three_workspaces(self, tmp_path: Path) -> tuple[Path, list[tuple[reg.Draft, Path]]]:
        projection = proj.Projection(store_dir=tmp_path / "store")
        entries: list[tuple[reg.Draft, Path]] = []
        for name, label in (("a", "Workspace A"), ("b", "Workspace B"), ("c", "Workspace C")):
            ws = tmp_path / name
            ws.mkdir()
            d, result = _register_full(ws, projection, label=label)
            assert result.outcome == "registered"
            entries.append((d, ws))
        return projection, entries

    def test_ordered_rebuild_assigns_input_ordinals(self, tmp_path: Path) -> None:
        projection, entries = self._three_workspaces(tmp_path)
        paths = [p for _, p in entries]
        result = projection.rebuild(paths)
        assert result.status == "rebuilt"
        assert [e["ordinal"] for e in result.entries] == [1, 2, 3]
        assert [e["workspace_path"] for e in result.entries] == [str(p) for p in paths]
        for e, (d, p) in zip(result.entries, entries):
            assert e["identity"] == d.identity
            assert e["state"] == "linked"

    def test_symlink_alias_dedup_retains_first_ordinal(self, tmp_path: Path) -> None:
        projection, entries = self._three_workspaces(tmp_path)
        ws_a, ws_b, ws_c = [p for _, p in entries]
        alias = tmp_path / "alias-a"
        try:
            os.symlink(ws_a, alias, target_is_directory=True)
        except OSError:
            pytest.skip("symlinks unavailable on this host")
        assert fs.capture_target_handle(alias) == fs.capture_target_handle(ws_a)
        result = projection.rebuild([ws_a, alias, ws_b, ws_c])
        assert result.status == "rebuilt"
        assert len(result.entries) == 3
        ordinals = [e["ordinal"] for e in result.entries]
        assert ordinals == [1, 3, 4]
        assert [e["workspace_path"] for e in result.entries] == [
            str(ws_a), str(ws_b), str(ws_c)
        ]
        assert [e["identity"] for e in result.entries] == [d.identity for d, _ in entries]

    def test_inaccessible_root_failure_leaves_previous_unchanged(self, tmp_path: Path) -> None:
        projection, entries = self._three_workspaces(tmp_path)
        paths = [p for _, p in entries]
        assert projection.rebuild(paths).status == "rebuilt"
        before = projection.list_projection()
        result = projection.rebuild([paths[0], tmp_path / "missing", paths[1]])
        assert result.status == "failed"
        assert projection.list_projection() == before

    def test_invalid_root_failure_leaves_previous_unchanged(self, tmp_path: Path) -> None:
        projection, entries = self._three_workspaces(tmp_path)
        paths = [p for _, p in entries]
        assert projection.rebuild(paths).status == "rebuilt"
        bare = tmp_path / "bare"
        bare.mkdir()
        before = projection.list_projection()
        result = projection.rebuild([paths[0], bare])
        assert result.status == "failed"
        assert projection.list_projection() == before

    def test_stale_entry_repair(self, tmp_path: Path) -> None:
        projection, entries = self._three_workspaces(tmp_path)
        paths = [p for _, p in entries]
        assert projection.rebuild(paths).status == "rebuilt"
        result = projection.rebuild([paths[0], paths[1]])
        assert result.status == "rebuilt"
        ids = {e["identity"] for e in result.entries}
        assert ids == {d.identity for d, _ in entries[:2]}
        assert len(result.entries) == 2

    def test_no_recursive_traversal(self, tmp_path: Path) -> None:
        projection, entries = self._three_workspaces(tmp_path)
        nested = tmp_path / "nested" / "deep" / "ws"
        nested.mkdir(parents=True)
        _write_marker(nested.parent.parent.parent, MARKER)
        result = projection.rebuild([nested.parent.parent.parent])
        assert result.status == "rebuilt"
        assert len(result.entries) == 1
        assert result.entries[0]["identity"] == MARKER["identity"]
        assert result.entries[0]["ordinal"] == 1

    def test_failed_rebuild_rolls_back_writes(self, tmp_path: Path, monkeypatch) -> None:
        projection, entries = self._three_workspaces(tmp_path)
        paths = [p for _, p in entries]
        assert projection.rebuild(paths).status == "rebuilt"
        before = projection.list_projection()
        real_connect = __import__("sqlite3").connect

        class _Boom:
            def __init__(self, real):
                object.__setattr__(self, "_real", real)

            def __getattr__(self, name):
                return getattr(self._real, name)

            def execute(self, *a, **k):
                raise RuntimeError("storage failure")

            def close(self):
                self._real.close()

        monkeypatch.setattr(
            proj.sqlite3, "connect", lambda *a, **k: _Boom(real_connect(*a, **k))
        )
        result = projection.rebuild([paths[1], paths[2]])
        assert result.status == "failed"
        monkeypatch.undo()
        assert projection.list_projection() == before


class TestProjectionIndependence:
    def test_deleting_projection_never_unregisters(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        store = tmp_path / "store"
        projection = proj.Projection(store_dir=store)
        d, result = _register_full(ws, projection)
        assert result.outcome == "registered"
        assert projection.find_by_identity(d.identity) is not None
        shutil.rmtree(store)
        assert fs.marker_path(ws).exists()
        inspection = reg.inspect(ws)
        assert inspection.state == reg.STATE_LINKED_EXISTING
        fresh = proj.Projection(store_dir=store)
        reg.set_projection_hook(fresh.update)
        relinked = reg.link(ws)
        assert relinked.outcome == "linked-existing"
        assert relinked.identity == d.identity
        assert fresh.find_by_identity(d.identity) is not None

    def test_projection_failure_after_registration_leaves_marker(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        store = tmp_path / "store"
        projection = proj.Projection(store_dir=store)
        d, result = _register_full(ws, projection)
        assert result.outcome == "registered"
        assert fs.marker_path(ws).exists()

        def failing(inp: reg.ProjectionInput) -> reg.ProjectionResult:
            raise RuntimeError("projection storage failure")

        reg.set_projection_hook(failing)
        relink = reg.link(ws)
        assert relink.outcome == "stopped"
        assert fs.marker_path(ws).exists()
        assert json.loads(fs.read_marker(ws).decode("utf-8"))["identity"] == d.identity


class TestDefaultStoreResolution:
    def test_env_override(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv(proj.ENV_STORE_DIR, str(tmp_path / "env-store"))
        assert proj.default_store_dir() == tmp_path / "env-store"
        projection = proj.Projection()
        assert projection.store_dir == tmp_path / "env-store"

    def test_store_dir_parameter_wins(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv(proj.ENV_STORE_DIR, str(tmp_path / "env-store"))
        projection = proj.Projection(store_dir=tmp_path / "param-store")
        assert projection.store_dir == tmp_path / "param-store"
