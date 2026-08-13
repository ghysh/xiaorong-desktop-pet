"""Read-only cached dialogue repository tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from desktop_pet.dialogue.repository import DialogueFileError, DialogueRepository


def test_utf8_bom_chinese_blank_and_spacing_rules(tmp_path: Path) -> None:
    path = tmp_path / "dialogue.txt"
    path.write_text("  你好！  \n\n# 不是注释\n中间  空格\n", encoding="utf-8-sig")
    repository = DialogueRepository(path)

    assert repository.load() == ("  你好！  ", "# 不是注释", "中间  空格")
    assert repository.encoding == "utf-8-sig"
    assert repository.blank_line_count == 1


def test_gb18030_fallback_and_one_read_cache_survive_source_removal(tmp_path: Path) -> None:
    path = tmp_path / "dialogue.txt"
    path.write_bytes("早上好\n再见".encode("gb18030"))
    repository = DialogueRepository(path)

    first = repository.load()
    path.unlink()

    assert repository.load() is first
    assert first == ("早上好", "再见")
    assert repository.encoding == "gb18030"
    assert repository.read_count == 1


@pytest.mark.parametrize("content", [b"", b"\n \r\n"])
def test_empty_dialogue_is_rejected(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "dialogue.txt"
    path.write_bytes(content)

    with pytest.raises(DialogueFileError, match="no non-empty"):
        DialogueRepository(path).load()


def test_missing_and_invalid_encoding_are_clear_errors(tmp_path: Path) -> None:
    with pytest.raises(DialogueFileError, match="cannot be read"):
        DialogueRepository(tmp_path / "missing.txt").load()

    path = tmp_path / "invalid.txt"
    path.write_bytes(b"\xff\xff\xff")
    with pytest.raises(DialogueFileError, match="encoding is invalid"):
        DialogueRepository(path).load()


def test_loading_does_not_modify_bytes_or_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "dialogue.txt"
    path.write_text("第一句\n第二句\n", encoding="utf-8")
    before_bytes = path.read_bytes()
    before_hash = hashlib.sha256(before_bytes).hexdigest()
    before_mtime = path.stat().st_mtime_ns

    DialogueRepository(path).load()

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_hash
    assert path.read_bytes() == before_bytes
    assert path.stat().st_mtime_ns == before_mtime
