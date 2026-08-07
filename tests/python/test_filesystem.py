"""U9 filesystem lifecycle tests (PLAN:452; KTD13 PLAN:198; PLAN:200).

Covers: stable target handle capture and fail-closed paths (identity APIs
unavailable, target-alias mismatch, redirected marker components); the
per-workspace lock (atomic absent-parent step, existing parent unaltered,
bounded timeout, release on normal and exceptional exit, stale-lock rule and
confirmed recovery); create-only marker writes and bounded read-back; and the
conditional-delete / absence-verification primitives shared with U10.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from workstream_registration import filesystem as fs

MARKER = {
    "version": 1,
    "identity": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "label": "filesystem test",
    "kind": "direct",
    "workspace": ".",
    "record_sources": [
        {"type": "example/records", "uri": "https://records.example.org/x"}
    ],
}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


def _dead_pid() -> int:
    return 2_000_000_000


def _stale_metadata(
    workspace: Path,
    handle: fs.TargetHandle,
    *,
    owner_id: str = "crashed-owner",
    pid: int | None = None,
    lease_until: float | None = None,
) -> fs.LockMetadata:
    import time

    from datetime import datetime, timezone

    now = time.time()
    return fs.LockMetadata(
        owner_id=owner_id,
        pid=pid if pid is not None else _dead_pid(),
        target_handle=handle,
        started_at=datetime.fromtimestamp(now - 3600, tz=timezone.utc).isoformat(),
        lease_until=datetime.fromtimestamp(
            lease_until if lease_until is not None else now - 3600, tz=timezone.utc
        ).isoformat(),
    )


def _write_lock(workspace: Path, metadata: fs.LockMetadata) -> None:
    fs.parent_path(workspace).mkdir(exist_ok=True)
    fs.lock_path(workspace).write_bytes(metadata.to_bytes())


class TestTargetHandle:
    def test_absent_parent_uses_absent_sentinel(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        assert handle.parent is fs.ABSENT_PARENT
        assert handle.parent_absent
        assert handle.workspace

    def test_present_parent_captures_parent_identity(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        handle = fs.capture_target_handle(workspace)
        assert not handle.parent_absent
        assert handle.parent is not None
        assert handle.workspace

    def test_handle_stable_across_calls(self, workspace: Path) -> None:
        first = fs.capture_target_handle(workspace)
        second = fs.capture_target_handle(workspace)
        assert first == second

    def test_handle_changes_when_workspace_recreated(self, workspace: Path) -> None:
        first = fs.capture_target_handle(workspace)
        import shutil

        shutil.rmtree(workspace)
        workspace.mkdir()
        second = fs.capture_target_handle(workspace)
        assert first.workspace != second.workspace

    def test_parent_identity_changes_when_parent_recreated(
        self, workspace: Path
    ) -> None:
        fs.parent_path(workspace).mkdir()
        first = fs.capture_target_handle(workspace)
        import shutil

        shutil.rmtree(fs.parent_path(workspace))
        fs.parent_path(workspace).mkdir()
        second = fs.capture_target_handle(workspace)
        assert first.parent != second.parent

    def test_identity_apis_unavailable_fails_closed(
        self, workspace: Path, monkeypatch
    ) -> None:
        def boom(path: Path) -> bytes:
            raise fs.IdentityUnavailableError("unavailable")

        monkeypatch.setattr(fs, "_capture_identity", boom)
        with pytest.raises(fs.IdentityUnavailableError):
            fs.capture_target_handle(workspace)

    def test_target_alias_mismatch_fails_closed(
        self, workspace: Path, monkeypatch
    ) -> None:
        real = fs._capture_identity
        counter = {"calls": 0}

        def fake(path: Path) -> bytes:
            # First capture is the as-given path; the resolved re-capture must
            # yield a different identity (alias resolves elsewhere).
            counter["calls"] += 1
            if counter["calls"] == 1:
                return real(path)
            return real(path) + b"\x00"

        monkeypatch.setattr(fs, "_capture_identity", fake)
        with pytest.raises(fs.TargetAliasMismatchError):
            fs.capture_target_handle(workspace)

    def test_redirected_marker_component_fails_closed(
        self, workspace: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(fs, "_marker_resolves_inside", lambda p: False)
        with pytest.raises(fs.RedirectedMarkerComponentError):
            fs.capture_target_handle(workspace)

    def test_junction_redirected_component_rejected(self, workspace: Path) -> None:
        outside = workspace.parent / "outside"
        outside.mkdir()
        link = workspace / ".workstream"
        try:
            _make_junction(link, outside)
        except pytest.skip.Exception:
            raise
        except OSError:
            pytest.skip("junction creation unavailable")
        with pytest.raises(fs.RedirectedMarkerComponentError):
            fs.capture_target_handle(workspace)

    def test_serialize_roundtrip(self, workspace: Path, tmp_path: Path) -> None:
        fs.parent_path(workspace).mkdir()
        handle = fs.capture_target_handle(workspace)
        assert fs.TargetHandle.from_dict(handle.to_dict()) == handle
        assert handle.to_bytes()
        absent_ws = tmp_path / "absent-ws"
        absent_ws.mkdir()
        absent = fs.capture_target_handle(absent_ws)
        assert absent.parent is None
        assert fs.TargetHandle.from_dict(absent.to_dict()) == absent


def _make_junction(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise OSError(f"mklink failed: {result.stderr}")
        return
    link.symlink_to(target, target_is_directory=True)


class TestLock:
    def test_absent_parent_atomic_step(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        assert not fs.parent_path(workspace).exists()
        fs.acquire_lock(
            workspace, "owner-1", os.getpid(), handle, fs.stale_after(), 0.5
        )
        assert fs.parent_path(workspace).is_dir()
        lock = fs.lock_path(workspace)
        assert lock.exists()
        metadata = fs.lock_metadata(workspace)
        assert metadata is not None
        assert metadata.owner_id == "owner-1"
        assert metadata.pid == os.getpid()
        assert metadata.target_handle == handle
        assert metadata.started_at
        assert metadata.lease_until
        fs.release_lock(workspace, "owner-1")
        assert not lock.exists()

    def test_existing_parent_not_created_or_altered(self, workspace: Path) -> None:
        parent = fs.parent_path(workspace)
        parent.mkdir()
        sentinel = parent / "keep.txt"
        sentinel.write_text("preserve me", encoding="utf-8")
        before = fs.capture_target_handle(workspace)
        handle = fs.capture_target_handle(workspace)
        fs.acquire_lock(
            workspace, "owner-2", os.getpid(), handle, fs.stale_after(), 0.5
        )
        after = fs.capture_target_handle(workspace)
        assert before == after
        assert sentinel.read_text(encoding="utf-8") == "preserve me"
        assert fs.lock_path(workspace).exists()
        fs.release_lock(workspace, "owner-2")

    def test_contention_times_out_bounded(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        fs.acquire_lock(
            workspace, "holder", os.getpid(), handle, fs.stale_after(60.0), 0.5
        )
        with pytest.raises(fs.LockUnavailableError):
            fs.acquire_lock(
                workspace, "contender", os.getpid(), handle, fs.stale_after(60.0), 0.1
            )

    def test_stale_lock_not_broken_by_plain_acquire(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        _write_lock(workspace, _stale_metadata(workspace, handle))
        with pytest.raises(fs.LockUnavailableError):
            fs.acquire_lock(
                workspace, "contender", os.getpid(), handle, fs.stale_after(60.0), 0.1
            )
        assert fs.lock_path(workspace).exists()

    def test_release_only_removes_own_lock(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        _write_lock(workspace, _stale_metadata(workspace, handle))
        fs.release_lock(workspace, "some-other-owner")
        assert fs.lock_path(workspace).exists()
        fs.release_lock(workspace, "crashed-owner")
        assert not fs.lock_path(workspace).exists()

    def test_context_manager_releases_on_exception(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        with pytest.raises(RuntimeError):
            with fs.registration_lock(workspace, handle, timeout=0.5) as owner:
                assert fs.lock_path(workspace).exists()
                assert fs.lock_metadata(workspace) is not None
                assert fs.lock_metadata(workspace).owner_id == owner
                raise RuntimeError("boom")
        assert not fs.lock_path(workspace).exists()

    def test_context_manager_releases_on_normal_exit(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        with fs.registration_lock(workspace, handle, timeout=0.5):
            assert fs.lock_path(workspace).exists()
        assert not fs.lock_path(workspace).exists()


class TestStaleRule:
    def test_stale_when_lease_expired_and_owner_dead(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        metadata = _stale_metadata(workspace, handle)
        assert metadata.lease_expired()
        assert not metadata.owner_alive()
        assert metadata.is_stale()

    def test_not_stale_when_owner_alive(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        metadata = _stale_metadata(
            workspace, handle, pid=os.getpid(), lease_until=fs.stale_after(-3600)
        )
        assert metadata.lease_expired()
        assert metadata.owner_alive()
        assert not metadata.is_stale()

    def test_not_stale_when_lease_unexpired(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        metadata = _stale_metadata(
            workspace, handle, pid=_dead_pid(), lease_until=fs.stale_after(3600)
        )
        assert not metadata.lease_expired()
        assert not metadata.owner_alive()
        assert not metadata.is_stale()

    def test_malformed_lock_metadata_fails_safe(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        fs.lock_path(workspace).write_text("not json", encoding="utf-8")
        assert fs.lock_metadata(workspace) is None
        handle = fs.capture_target_handle(workspace)
        with pytest.raises(fs.LockUnavailableError):
            fs.acquire_lock(
                workspace, "x", os.getpid(), handle, fs.stale_after(60.0), 0.1
            )


class TestRecoverLock:
    def test_stale_lock_recovered_with_matching_handle(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        _write_lock(workspace, _stale_metadata(workspace, handle))
        assert fs.recover_lock(workspace, handle) is True
        metadata = fs.lock_metadata(workspace)
        assert metadata is not None
        assert metadata.pid == os.getpid()
        assert not metadata.is_stale()

    def test_live_lock_never_broken(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        _write_lock(
            workspace, _stale_metadata(workspace, handle, pid=os.getpid())
        )
        with pytest.raises(fs.LockNotRecoverableError):
            fs.recover_lock(workspace, handle)

    def test_mismatched_handle_never_broken(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        other = fs.TargetHandle(workspace=handle.workspace + b"\x00", parent=None)
        _write_lock(workspace, _stale_metadata(workspace, handle))
        with pytest.raises(fs.LockNotRecoverableError):
            fs.recover_lock(workspace, other)

    def test_absent_lock_is_noop(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        assert fs.recover_lock(workspace, handle) is True

    def test_handle_must_match_current_workspace(self, workspace: Path) -> None:
        handle = fs.capture_target_handle(workspace)
        stale = _stale_metadata(workspace, handle)
        _write_lock(workspace, stale)
        import shutil

        shutil.rmtree(workspace)
        workspace.mkdir()
        # A recreated workspace has a different stable identity; a lock bound
        # to the old identity is never broken by a new confirmation.
        _write_lock(workspace, stale)
        new_handle = fs.capture_target_handle(workspace)
        with pytest.raises(fs.LockNotRecoverableError):
            fs.recover_lock(workspace, new_handle)


class TestMarkerWriteRead:
    def test_create_only_write_and_read_back(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        raw = json.dumps(MARKER, separators=(",", ":")).encode("utf-8")
        handle = fs.capture_target_handle(workspace)
        fs.write_marker_create_only(workspace, raw, handle)
        assert fs.read_marker(workspace) == raw

    def test_create_collision_never_overwrites(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        raw = json.dumps(MARKER).encode("utf-8")
        handle = fs.capture_target_handle(workspace)
        fs.write_marker_create_only(workspace, raw, handle)
        other = b'{"version":1,"identity":"11111111-2222-4333-8444-555555555555"}'
        with pytest.raises(fs.CreateCollisionError):
            fs.write_marker_create_only(workspace, other, handle)
        assert fs.read_marker(workspace) == raw

    def test_oversized_marker_bytes_rejected(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        handle = fs.capture_target_handle(workspace)
        with pytest.raises(fs.WriteFailedError):
            fs.write_marker_create_only(workspace, b"x" * (fs.MAX_MARKER_READ_BYTES + 1), handle)

    def test_read_back_bounded(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        (fs.marker_path(workspace)).write_bytes(b"x" * (fs.MAX_MARKER_READ_BYTES + 100))
        raw = fs.read_marker(workspace)
        assert len(raw) == fs.MAX_MARKER_READ_BYTES

    def test_read_marker_missing_raises(self, workspace: Path) -> None:
        with pytest.raises(fs.ReadBackFailedError):
            fs.read_marker(workspace)

    def test_lock_metadata_bounded_read(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        fs.lock_path(workspace).write_bytes(b"x" * (fs.MAX_LOCK_METADATA_BYTES + 1))
        assert fs.lock_metadata(workspace) is None


class TestDeletePrimitives:
    def test_delete_and_absence_verification(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        fs.marker_path(workspace).write_text("x", encoding="utf-8")
        assert not fs.verify_marker_absent(workspace)
        fs.delete_marker(workspace)
        assert fs.verify_marker_absent(workspace)

    def test_delete_missing_raises(self, workspace: Path) -> None:
        with pytest.raises(FileNotFoundError):
            fs.delete_marker(workspace)

    def test_conditional_delete_matches_only_exact_bytes(self, workspace: Path) -> None:
        fs.parent_path(workspace).mkdir()
        marker_bytes = json.dumps(MARKER, separators=(",", ":")).encode("utf-8")
        fs.marker_path(workspace).write_bytes(marker_bytes)
        assert not fs.conditional_delete_marker(workspace, b"different")
        assert fs.marker_path(workspace).exists()
        assert fs.conditional_delete_marker(workspace, marker_bytes)
        assert fs.verify_marker_absent(workspace)
