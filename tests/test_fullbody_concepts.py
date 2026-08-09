"""Validation for Stage 4 full-body design candidates without promoting a final asset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from desktop_pet.paths import (
    ANIMATIONS_DIR,
    CHARACTER_CUTOUT_IMAGE,
    CHARACTER_RUNTIME_MASTER,
    FULLBODY_CONCEPTS_DIR,
    FULLBODY_REPORTS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PROJECT_ROOT,
)

EXPECTED_ORIGINAL_SHA256 = "CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3"
EXPECTED_STAGE_THREE_HASHES = {
    CHARACTER_CUTOUT_IMAGE: "4007456A5460A3A2A2DCCC48303A5E323C465B7488F03898343394841D671F99",
    CHARACTER_RUNTIME_MASTER: "7E5BF9CD7705416B3F0BB310CD3EAA0A1395470D1DBFC9DB010E80969E7242C8",
}
SOURCE_ORIGINAL_IMAGE = Path(r"D:\DesktopPet\ori_figure.png")
MANIFEST_PATH = FULLBODY_REPORTS_DIR / "fullbody_concept_manifest.json"
COMPARISON_PATH = FULLBODY_CONCEPTS_DIR / "fullbody_concept_comparison.png"
CONCEPT_FILENAMES = {
    "A": "fullbody_concept_a.png",
    "B": "fullbody_concept_b.png",
    "C": "fullbody_concept_c.png",
}


def sha256(path: Path) -> str:
    """Return an uppercase SHA-256 digest without modifying a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def open_verified(path: Path) -> Image.Image:
    """Verify a candidate before returning a file-handle-free RGBA copy."""
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return image.convert("RGBA").copy()


def test_three_fullbody_candidates_are_valid_portrait_rgba_images() -> None:
    for filename in CONCEPT_FILENAMES.values():
        path = FULLBODY_CONCEPTS_DIR / filename
        image = open_verified(path)
        alpha = np.asarray(image.getchannel("A"))
        bbox = Image.fromarray(alpha, mode="L").getbbox()

        assert image.mode == "RGBA"
        assert image.width >= 1024
        assert image.height >= 1536
        assert image.height > image.width
        assert np.count_nonzero(alpha == 0) > 0
        assert np.count_nonzero(alpha == 255) > 0
        assert np.count_nonzero((alpha > 0) & (alpha < 255)) > 0
        assert bbox is not None
        assert bbox[0] > 0 and bbox[1] > 0
        assert bbox[2] < image.width and bbox[3] < image.height


def test_comparison_board_exists_and_opens() -> None:
    with Image.open(COMPARISON_PATH) as image:
        image.verify()
    with Image.open(COMPARISON_PATH) as image:
        assert image.mode == "RGB"
        assert image.width > image.height
        assert image.width >= 1800


def test_manifest_contains_only_nonfinal_fullbody_candidates() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    concepts = {record["design_plan"]: record for record in manifest["concepts"]}

    assert manifest["stage"] == 4
    assert manifest["status"] == "fullbody_design_candidates_pending_user_confirmation"
    assert set(concepts) == set(CONCEPT_FILENAMES)
    assert manifest["recommendation"]["plan"] == "A"
    assert manifest["recommendation"]["final_asset"] is False
    assert manifest["runtime_status"]["fullbody_runtime_master_created"] is False
    assert manifest["runtime_status"]["stage_three_upper_body_assets_are_final_runtime_assets"] is False
    assert manifest["runtime_status"]["transparent_window_implemented"] is False
    assert manifest["runtime_status"]["animation_created"] is False

    for plan, filename in CONCEPT_FILENAMES.items():
        record = concepts[plan]
        path = PROJECT_ROOT / Path(record["path"])
        assert path == FULLBODY_CONCEPTS_DIR / filename
        assert record["final_asset"] is False
        assert record["inferred_design"] is True
        assert record["is_complete_figure"] is True
        assert record["has_alpha"] is True
        assert sha256(path) == record["sha256"]


def test_original_and_stage_three_reference_assets_are_unchanged() -> None:
    assert sha256(SOURCE_ORIGINAL_IMAGE) == EXPECTED_ORIGINAL_SHA256
    assert sha256(ORIGINAL_CHARACTER_IMAGE) == EXPECTED_ORIGINAL_SHA256
    for path, expected_hash in EXPECTED_STAGE_THREE_HASHES.items():
        assert sha256(path) == expected_hash


def test_later_runtime_features_do_not_change_stage_four_character_assets() -> None:
    app_source = (PROJECT_ROOT / "src" / "desktop_pet" / "app.py").read_text(encoding="utf-8")

    assert sorted(path.name for path in ANIMATIONS_DIR.iterdir()) == [".gitkeep"]
    assert "QSystemTrayIcon" not in app_source
    assert app_source.count("QTimer.singleShot") == 1
