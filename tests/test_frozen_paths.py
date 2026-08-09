"""Source and PyInstaller bundle-root path resolution tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from desktop_pet import paths


def test_source_runtime_base_is_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert paths.runtime_base_dir() == paths.PROJECT_ROOT


def test_frozen_runtime_base_uses_meipass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.runtime_base_dir() == tmp_path.resolve()
    assert paths.runtime_base_dir() / "assets/fullbody/final/fullbody_runtime_master.png" == (
        tmp_path / "assets/fullbody/final/fullbody_runtime_master.png"
    )


def test_frozen_runtime_without_meipass_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    with pytest.raises(RuntimeError, match="bundle directory"):
        paths.runtime_base_dir()
