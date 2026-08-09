"""第一阶段的环境、路径与原始素材完整性测试。"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import PySide6
import pytest
from PIL import Image
from scripts.inspect_original_image import analyze_image
from scripts.inspect_original_image import main as inspect_main

from desktop_pet.paths import (
    ANALYSIS_DIR,
    ANALYSIS_PREVIEWS_DIR,
    ANALYSIS_REPORTS_DIR,
    ANIMATIONS_DIR,
    ASSETS_DIR,
    BASE_ASSETS_DIR,
    CHARACTER_CUTOUT_IMAGE,
    CHARACTER_RUNTIME_MASTER,
    MASKS_ASSETS_DIR,
    ORIGINAL_ASSETS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PACKAGE_DIR,
    PROCESSED_ASSETS_DIR,
    PROCESSED_PREVIEWS_DIR,
    PROCESSED_REPORTS_DIR,
    PROJECT_ROOT,
    SRC_DIR,
)

SOURCE_ORIGINAL_IMAGE = Path(r"D:\DesktopPet\ori_figure.png")


def sha256(path: Path) -> str:
    """返回文件的 SHA-256，不会修改文件。"""
    digest = hashlib.sha256()
    with path.open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_python_version_is_311() -> None:
    assert sys.version_info[:2] == (3, 11)


def test_runtime_dependencies_import() -> None:
    assert PySide6.__version__
    with Image.new("RGBA", (1, 1)) as image:
        assert image.mode == "RGBA"


def test_project_paths_resolve_correctly() -> None:
    assert PACKAGE_DIR == PROJECT_ROOT / "src" / "desktop_pet"
    assert SRC_DIR == PROJECT_ROOT / "src"
    assert ASSETS_DIR == PROJECT_ROOT / "assets"
    assert ORIGINAL_ASSETS_DIR == ASSETS_DIR / "original"
    assert PROCESSED_ASSETS_DIR == ASSETS_DIR / "processed"
    assert ANIMATIONS_DIR == ASSETS_DIR / "animations"
    assert ANALYSIS_DIR == ASSETS_DIR / "analysis"
    assert ANALYSIS_PREVIEWS_DIR == ANALYSIS_DIR / "previews"
    assert ANALYSIS_REPORTS_DIR == ANALYSIS_DIR / "reports"
    assert ORIGINAL_CHARACTER_IMAGE == ORIGINAL_ASSETS_DIR / "character_original.png"
    assert BASE_ASSETS_DIR == PROCESSED_ASSETS_DIR / "base"
    assert MASKS_ASSETS_DIR == PROCESSED_ASSETS_DIR / "masks"
    assert PROCESSED_PREVIEWS_DIR == PROCESSED_ASSETS_DIR / "previews"
    assert PROCESSED_REPORTS_DIR == PROCESSED_ASSETS_DIR / "reports"
    assert CHARACTER_CUTOUT_IMAGE == BASE_ASSETS_DIR / "character_cutout_rgba.png"
    assert CHARACTER_RUNTIME_MASTER == BASE_ASSETS_DIR / "character_runtime_master.png"


def test_core_directories_exist() -> None:
    required_directories = (
        ASSETS_DIR,
        ORIGINAL_ASSETS_DIR,
        PROCESSED_ASSETS_DIR,
        BASE_ASSETS_DIR,
        MASKS_ASSETS_DIR,
        PROCESSED_PREVIEWS_DIR,
        PROCESSED_REPORTS_DIR,
        ANIMATIONS_DIR,
        ANALYSIS_DIR,
        ANALYSIS_PREVIEWS_DIR,
        ANALYSIS_REPORTS_DIR,
        PROJECT_ROOT / "assets" / "icons",
        PROJECT_ROOT / "assets" / "sounds",
        PROJECT_ROOT / "src" / "desktop_pet" / "ui",
        PROJECT_ROOT / "src" / "desktop_pet" / "animation",
        PROJECT_ROOT / "src" / "desktop_pet" / "behavior",
        PROJECT_ROOT / "src" / "desktop_pet" / "interaction",
        PROJECT_ROOT / "src" / "desktop_pet" / "utils",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "build",
        PROJECT_ROOT / "dist",
        PROJECT_ROOT / "docs",
    )
    assert all(directory.is_dir() for directory in required_directories)


def test_project_original_image_is_a_nonempty_png() -> None:
    assert ORIGINAL_CHARACTER_IMAGE.is_file()
    assert ORIGINAL_CHARACTER_IMAGE.suffix.lower() == ".png"
    assert ORIGINAL_CHARACTER_IMAGE.stat().st_size > 0

    with Image.open(ORIGINAL_CHARACTER_IMAGE) as image:
        image.verify()

    with Image.open(ORIGINAL_CHARACTER_IMAGE) as image:
        width, height = image.size
        assert width > 0
        assert height > 0


def test_source_and_project_copy_hashes_match() -> None:
    assert SOURCE_ORIGINAL_IMAGE.is_file()
    assert sha256(SOURCE_ORIGINAL_IMAGE) == sha256(ORIGINAL_CHARACTER_IMAGE)


def test_inspection_is_non_destructive() -> None:
    initial_hash = sha256(ORIGINAL_CHARACTER_IMAGE)
    initial_mtime_ns = ORIGINAL_CHARACTER_IMAGE.stat().st_mtime_ns

    report = analyze_image(ORIGINAL_CHARACTER_IMAGE)

    assert report["width"] > 0
    assert report["height"] > 0
    assert sha256(ORIGINAL_CHARACTER_IMAGE) == initial_hash
    assert ORIGINAL_CHARACTER_IMAGE.stat().st_mtime_ns == initial_mtime_ns


def test_inspector_handles_missing_image_with_clear_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_path = tmp_path / "missing_character.png"

    exit_code = inspect_main(["--image", str(missing_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Original character image not found" in captured.err
