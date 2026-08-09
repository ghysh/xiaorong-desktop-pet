"""Tests for the non-destructive second-stage visual analysis artefacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image
from scripts.analyze_character_visual import main as run_analysis

from desktop_pet.paths import (
    ANALYSIS_DIR,
    ANALYSIS_PREVIEWS_DIR,
    ANALYSIS_REPORTS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PROJECT_ROOT,
)

EXPECTED_SOURCE_SHA256 = "CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3"
SOURCE_ORIGINAL_IMAGE = Path(r"D:\DesktopPet\ori_figure.png")
REPORT_PATH = ANALYSIS_REPORTS_DIR / "character_analysis.json"
PREVIEW_FILENAMES = (
    "character_enlarged_reference.png",
    "character_palette.png",
    "character_composition_grid.png",
    "character_size_comparison.png",
    "character_visual_review_board.png",
)
REQUIRED_TOP_LEVEL_KEYS = {
    "source",
    "background_analysis",
    "palette",
    "composition",
    "visual_identity",
    "identity_rules",
    "display_size_options",
    "action_scope",
    "pending_user_confirmation",
}


def sha256(path: Path) -> str:
    """Return an uppercase SHA-256 digest without modifying a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_report() -> dict[str, object]:
    """Load the UTF-8 structural report."""
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_original_images_remain_unchanged() -> None:
    assert SOURCE_ORIGINAL_IMAGE.is_file()
    assert ORIGINAL_CHARACTER_IMAGE.is_file()
    assert sha256(SOURCE_ORIGINAL_IMAGE) == EXPECTED_SOURCE_SHA256
    assert sha256(ORIGINAL_CHARACTER_IMAGE) == EXPECTED_SOURCE_SHA256


def test_original_copy_retains_required_image_properties() -> None:
    with Image.open(ORIGINAL_CHARACTER_IMAGE) as image:
        image.verify()

    with Image.open(ORIGINAL_CHARACTER_IMAGE) as image:
        assert image.size == (346, 346)
        assert image.mode == "RGB"
        assert image.mode not in {"RGBA", "LA"}
        assert "transparency" not in image.info


def test_analysis_directories_and_json_exist() -> None:
    assert ANALYSIS_DIR.is_dir()
    assert ANALYSIS_PREVIEWS_DIR.is_dir()
    assert ANALYSIS_REPORTS_DIR.is_dir()
    assert REPORT_PATH.is_file()


def test_analysis_json_has_required_structure_and_palette() -> None:
    report = load_report()
    assert REQUIRED_TOP_LEVEL_KEYS <= set(report)
    assert report["source"]["sha256"] == EXPECTED_SOURCE_SHA256
    assert report["palette"]
    assert report["analysis_scope"]["background_removed"] is False
    assert report["analysis_scope"]["animation_frames_created"] is False


def test_display_size_comparison_contains_requested_sizes() -> None:
    report = load_report()
    sizes = {
        (entry["width"], entry["height"])
        for entry in report["display_size_options"]
    }
    assert sizes == {(160, 160), (200, 200), (240, 240), (280, 280), (320, 320)}


def test_analysis_previews_open_with_pillow() -> None:
    for filename in PREVIEW_FILENAMES:
        preview_path = ANALYSIS_PREVIEWS_DIR / filename
        assert preview_path.is_file()
        with Image.open(preview_path) as image:
            image.verify()
        with Image.open(preview_path) as image:
            assert image.width > 0
            assert image.height > 0


def test_analysis_script_is_non_destructive() -> None:
    source_before = sha256(SOURCE_ORIGINAL_IMAGE)
    copy_before = sha256(ORIGINAL_CHARACTER_IMAGE)

    assert run_analysis() == 0

    assert sha256(SOURCE_ORIGINAL_IMAGE) == source_before
    assert sha256(ORIGINAL_CHARACTER_IMAGE) == copy_before


def test_asset_spec_is_a_draft_with_user_confirmation_items() -> None:
    specification = (PROJECT_ROOT / "docs" / "character_asset_spec.md").read_text(
        encoding="utf-8"
    )
    report = load_report()
    assert "第二阶段草案" in specification
    assert "待用户确认" in specification
    assert len(report["pending_user_confirmation"]) >= 5
