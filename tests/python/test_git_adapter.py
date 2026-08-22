"""Tests for git_adapter — bounded git operations for workspace change signals."""
from __future__ import annotations

from pathlib import Path

import pytest

from workstream_dispatch.git_adapter import capture_git_state


class TestCaptureGitState:
    def test_captures_head_oid(self, tmp_path):
        """Captures HEAD OID from a git repository."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        # Init a git repo
        import subprocess
        subprocess.run(["git", "init"], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, cwd=str(ws))
        (ws / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True, cwd=str(ws))

        state = capture_git_state(ws)
        assert state is not None
        assert len(state.head_oid) == 40  # Full SHA

    def test_non_git_dir_returns_none(self, tmp_path):
        """A non-git directory returns None."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        state = capture_git_state(ws)
        assert state is None

    def test_clean_worktree_has_stable_digest(self, tmp_path):
        """A clean worktree has a stable digest."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        import subprocess
        subprocess.run(["git", "init"], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, cwd=str(ws))
        (ws / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True, cwd=str(ws))

        state1 = capture_git_state(ws)
        state2 = capture_git_state(ws)
        assert state1.head_oid == state2.head_oid
        assert state1.worktree_digest == state2.worktree_digest

    def test_dirty_worktree_has_different_digest(self, tmp_path):
        """A dirty worktree has a different digest than clean."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        import subprocess
        subprocess.run(["git", "init"], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, cwd=str(ws))
        (ws / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], capture_output=True, cwd=str(ws))
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True, cwd=str(ws))

        clean = capture_git_state(ws)
        (ws / "file.txt").write_text("modified")
        dirty = capture_git_state(ws)

        assert clean.head_oid == dirty.head_oid  # HEAD unchanged
        assert clean.worktree_digest != dirty.worktree_digest
