"""Portable ZIP layout and exclusion tests."""

from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.create_release_archive import create_archive


def test_archive_has_desktop_pet_root_and_excludes_development_files(tmp_path: Path) -> None:
    source = tmp_path / "DesktopPet"
    (source / "_internal").mkdir(parents=True)
    (source / "DesktopPet.exe").write_bytes(b"MZ-fake")
    (source / "_internal/runtime.dll").write_bytes(b"dll")
    (source / "tests").mkdir()
    (source / "tests/test_fake.py").write_text("ignored", encoding="utf-8")
    (source / "settings.ini").write_text("ignored", encoding="utf-8")
    archive_path = tmp_path / "portable.zip"
    assert create_archive(source, archive_path) == 2
    with zipfile.ZipFile(archive_path) as archive:
        assert sorted(archive.namelist()) == ["DesktopPet/DesktopPet.exe", "DesktopPet/_internal/runtime.dll"]
