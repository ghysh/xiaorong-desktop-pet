"""Portable relative checksum-list tests."""

from __future__ import annotations

from pathlib import Path

from scripts.generate_release_checksums import generate_checksums, sha256_file


def test_checksum_file_uses_sha256_and_relative_names(tmp_path: Path) -> None:
    artifact = tmp_path / "DesktopPet-1.0.0-win64-portable.zip"
    artifact.write_bytes(b"portable release")
    output = tmp_path / "checksums_1.0.0.sha256"
    records = generate_checksums([artifact], output, relative_to=tmp_path)
    assert records == [(sha256_file(artifact), artifact.name)]
    content = output.read_text(encoding="utf-8")
    assert content == f"{sha256_file(artifact)} *{artifact.name}\n"
    assert str(tmp_path) not in content
