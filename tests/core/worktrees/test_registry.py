import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from orca.core.worktrees.registry import (
    Sidecar,
    write_sidecar,
    read_sidecar,
    sidecar_path,
)


def _sample_sidecar() -> Sidecar:
    return Sidecar(
        schema_version=2,
        lane_id="015-wizard",
        lane_mode="lane",
        feature_id="015",
        lane_name="wizard",
        branch="feature/015-wizard",
        base_branch="main",
        worktree_path="/abs/path",
        created_at="2026-04-30T22:55:00Z",
        tmux_session="orca",
        tmux_window="015-wizard",
        agent="claude",
        setup_version="abc123",
        last_attached_at="2026-04-30T23:10:00Z",
        host_system="superpowers",
    )


class TestSidecarRoundTrip:
    def test_write_then_read(self, tmp_path):
        sc = _sample_sidecar()
        write_sidecar(tmp_path, sc)
        loaded = read_sidecar(sidecar_path(tmp_path, sc.lane_id))
        assert loaded == sc

    def test_dual_emit_legacy_fields(self, tmp_path):
        sc = _sample_sidecar()
        write_sidecar(tmp_path, sc)
        raw = json.loads(sidecar_path(tmp_path, sc.lane_id).read_text())
        # New-style fields
        assert raw["lane_id"] == "015-wizard"
        assert raw["feature_id"] == "015"
        assert raw["worktree_path"] == "/abs/path"
        # Legacy fields (for sdd_adapter._load_worktree_lanes compat)
        assert raw["id"] == "015-wizard"
        assert raw["feature"] == "015"
        assert raw["path"] == "/abs/path"
        assert raw["status"] == "active"
        assert raw["task_scope"] == []

    def test_atomic_write_no_partial_on_failure(self, tmp_path, monkeypatch):
        sc = _sample_sidecar()
        write_sidecar(tmp_path, sc)
        partials = list(tmp_path.glob("**/*.partial"))
        assert partials == []


class TestReadSidecar:
    def test_missing_file_returns_none(self, tmp_path):
        assert read_sidecar(tmp_path / "nonexistent.json") is None

    def test_corrupt_json_returns_none(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json {")
        assert read_sidecar(bad) is None


from orca.core.worktrees.registry import (
    LaneRow, RegistryView, read_registry, write_registry, registry_path,
)


class TestRegistryRoundTrip:
    def test_write_then_read_v2(self, tmp_path):
        rows = [
            LaneRow(lane_id="015-wiz", branch="feature/015-wiz",
                    worktree_path=str(tmp_path / "015-wiz"), feature_id="015"),
            LaneRow(lane_id="016-tst", branch="feature/016-tst",
                    worktree_path=str(tmp_path / "016-tst"), feature_id="016"),
        ]
        write_registry(tmp_path, rows)
        view = read_registry(tmp_path)
        assert view.schema_version == 2
        assert len(view.lanes) == 2
        assert view.lanes[0].lane_id == "015-wiz"

    def test_read_missing_returns_empty_v2_view(self, tmp_path):
        view = read_registry(tmp_path)
        assert view.schema_version == 2
        assert view.lanes == []

    def test_atomic_rename_no_partial_artifact(self, tmp_path):
        write_registry(tmp_path, [])
        partials = list(tmp_path.glob("*.partial"))
        assert partials == []


import sys

from orca.core.worktrees.registry import (
    acquire_registry_lock, LockTimeout, migrate_v1_to_v2,
)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fcntl path")
class TestRegistryLockingPosix:
    def test_lock_acquire_release(self, tmp_path):
        with acquire_registry_lock(tmp_path, timeout_s=1.0):
            pass

    def test_lock_timeout_when_held(self, tmp_path):
        import threading
        held = threading.Event()
        release = threading.Event()
        def holder():
            with acquire_registry_lock(tmp_path, timeout_s=5.0):
                held.set()
                release.wait()
        t = threading.Thread(target=holder)
        t.start()
        held.wait(timeout=2.0)
        with pytest.raises(LockTimeout):
            with acquire_registry_lock(tmp_path, timeout_s=0.2):
                pass
        release.set()
        t.join()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows msvcrt path")
@pytest.mark.windows
class TestRegistryLockingWindows:
    def test_lock_acquire_release(self, tmp_path):
        with acquire_registry_lock(tmp_path, timeout_s=1.0):
            pass

    def test_lock_timeout_when_held(self, tmp_path):
        import threading
        held = threading.Event()
        release = threading.Event()
        def holder():
            with acquire_registry_lock(tmp_path, timeout_s=5.0):
                held.set()
                release.wait()
        t = threading.Thread(target=holder)
        t.start()
        held.wait(timeout=2.0)
        with pytest.raises(LockTimeout):
            with acquire_registry_lock(tmp_path, timeout_s=0.2):
                pass
        release.set()
        t.join()


class TestMigrator:
    def _write_v1(self, tmp_path: Path, lane_ids: list[str]) -> None:
        registry = {"lanes": lane_ids}
        registry_path(tmp_path).write_text(json.dumps(registry))

    def test_migrate_string_lanes_to_objects(self, tmp_path):
        self._write_v1(tmp_path, ["015-wizard"])
        sc = _sample_sidecar()
        write_sidecar(tmp_path, sc)
        migrated = migrate_v1_to_v2(tmp_path)
        assert migrated is True
        view = read_registry(tmp_path)
        assert view.schema_version == 2
        assert len(view.lanes) == 1
        assert view.lanes[0].lane_id == "015-wizard"
        assert (tmp_path / "registry.v1.bak.json").exists()

    def test_migrate_idempotent_on_v2(self, tmp_path):
        write_registry(tmp_path, [
            LaneRow("x", "feature/x", "/p", None),
        ])
        assert migrate_v1_to_v2(tmp_path) is False
        assert not (tmp_path / "registry.v1.bak.json").exists()

    def test_migrate_skips_when_registry_missing(self, tmp_path):
        assert migrate_v1_to_v2(tmp_path) is False
