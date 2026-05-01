from pathlib import Path

import pytest

from orca.core.worktrees.init_script import (
    detect_ecosystems, generate_after_create, EcosystemHit,
)


class TestDetectEcosystems:
    def test_detects_uv(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        (tmp_path / "uv.lock").write_text("")
        hits = detect_ecosystems(tmp_path)
        assert any(h.name == "uv" for h in hits)

    def test_detects_bun(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "bun.lockb").write_bytes(b"\x00")
        hits = detect_ecosystems(tmp_path)
        assert any(h.name == "bun" for h in hits)

    def test_detects_pip_with_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests\n")
        hits = detect_ecosystems(tmp_path)
        assert any(h.name == "pip" for h in hits)

    def test_warns_on_monorepo_signals(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "apps").mkdir()
        (tmp_path / "apps" / "web").mkdir()
        (tmp_path / "apps" / "web" / "package.json").write_text("{}")
        hits = detect_ecosystems(tmp_path)
        # Warning attached as a separate hit
        assert any(h.name == "monorepo_warning" for h in hits)


class TestGenerateAfterCreate:
    def test_generates_executable_script(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        (tmp_path / "uv.lock").write_text("")
        out = generate_after_create(tmp_path)
        assert out.exists()
        # Contains uv sync line
        body = out.read_text()
        assert "uv sync" in body
        # Executable bit set
        import os, stat
        assert out.stat().st_mode & stat.S_IXUSR

    def test_refuses_overwrite_without_replace(self, tmp_path):
        (tmp_path / ".orca" / "worktrees").mkdir(parents=True)
        existing = tmp_path / ".orca" / "worktrees" / "after_create"
        existing.write_text("# existing\n")
        with pytest.raises(FileExistsError):
            generate_after_create(tmp_path, replace=False)
