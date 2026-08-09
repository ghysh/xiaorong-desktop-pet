"""Validation for the local-only, non-destructive transparent base candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scripts.build_transparent_character import (
    ALPHA_MASK_PATH,
    EXPECTED_SOURCE_SHA256,
    MANIFEST_PATH,
    RUNTIME_MASTER_SIZE,
    SOURCE_SIZE,
    TRIMAP_PATH,
    run,
)

from desktop_pet.paths import (
    ANIMATIONS_DIR,
    CHARACTER_CUTOUT_IMAGE,
    CHARACTER_RUNTIME_MASTER,
    MASKS_ASSETS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PROCESSED_PREVIEWS_DIR,
    PROJECT_ROOT,
)

SOURCE_ORIGINAL_IMAGE = Path(r"D:\DesktopPet\ori_figure.png")
DEFAULT_PREVIEW = PROCESSED_PREVIEWS_DIR / "character_default_240.png"
ALTERNATIVE_PREVIEW = PROCESSED_PREVIEWS_DIR / "character_alternative_280.png"
CORRECTIONS_PATH = MASKS_ASSETS_DIR / "mask_corrections.json"


def sha256(path: Path) -> str:
    """Return an uppercase SHA-256 digest without modifying a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def open_verified(path: Path) -> Image.Image:
    """Open a Pillow image after verifying it without leaving an open file handle."""
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return image.copy()


def test_source_and_internal_copy_keep_the_approved_hash() -> None:
    assert sha256(SOURCE_ORIGINAL_IMAGE) == EXPECTED_SOURCE_SHA256
    assert sha256(ORIGINAL_CHARACTER_IMAGE) == EXPECTED_SOURCE_SHA256


def test_cutout_is_source_coordinate_rgba_with_meaningful_alpha() -> None:
    cutout = open_verified(CHARACTER_CUTOUT_IMAGE)
    alpha = np.asarray(cutout.getchannel("A"))

    assert cutout.mode == "RGBA"
    assert cutout.size == SOURCE_SIZE
    assert np.count_nonzero(alpha == 0) > 0
    assert np.count_nonzero(alpha == 255) > 0
    assert np.count_nonzero((alpha > 0) & (alpha < 255)) > 0
    assert np.count_nonzero(alpha > 0) < alpha.size


def test_opaque_interior_rgb_is_identical_to_the_original() -> None:
    cutout = np.asarray(open_verified(CHARACTER_CUTOUT_IMAGE))
    source = np.asarray(open_verified(ORIGINAL_CHARACTER_IMAGE).convert("RGB"))
    opaque = cutout[:, :, 3] == 255

    assert np.count_nonzero(opaque) > 0
    assert np.array_equal(cutout[:, :, :3][opaque], source[opaque])


def test_trimap_and_alpha_masks_are_valid() -> None:
    trimap = np.asarray(open_verified(TRIMAP_PATH))
    alpha = np.asarray(open_verified(ALPHA_MASK_PATH))

    assert trimap.shape == SOURCE_SIZE[::-1]
    assert alpha.shape == SOURCE_SIZE[::-1]
    assert set(np.unique(trimap)) == {0, 128, 255}
    assert alpha.dtype == np.uint8


def test_runtime_master_is_unscaled_and_has_transparent_margin() -> None:
    master = np.asarray(open_verified(CHARACTER_RUNTIME_MASTER))
    cutout = np.asarray(open_verified(CHARACTER_CUTOUT_IMAGE))
    offset = (RUNTIME_MASTER_SIZE[0] - SOURCE_SIZE[0]) // 2

    assert master.shape == (RUNTIME_MASTER_SIZE[1], RUNTIME_MASTER_SIZE[0], 4)
    assert np.count_nonzero(master[:offset, :, 3]) == 0
    assert np.count_nonzero(master[-offset:, :, 3]) == 0
    assert np.count_nonzero(master[:, :offset, 3]) == 0
    assert np.count_nonzero(master[:, -offset:, 3]) == 0
    master_cutout = master[offset : offset + SOURCE_SIZE[1], offset : offset + SOURCE_SIZE[0]]
    visible = cutout[:, :, 3] > 0
    assert np.array_equal(master_cutout[:, :, 3], cutout[:, :, 3])
    assert np.array_equal(master_cutout[:, :, :3][visible], cutout[:, :, :3][visible])


def test_logical_display_previews_have_the_approved_sizes() -> None:
    for path, expected_size in ((DEFAULT_PREVIEW, (240, 240)), (ALTERNATIVE_PREVIEW, (280, 280))):
        preview = open_verified(path)
        assert preview.mode == "RGBA"
        assert preview.size == expected_size
        assert np.count_nonzero(np.asarray(preview.getchannel("A")) == 0) > 0


def test_manifest_hashes_and_processing_contract_are_consistent() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["source"]["sha256"] == EXPECTED_SOURCE_SHA256
    assert manifest["processing"]["semantic_redraw"] is False
    assert manifest["processing"]["source_modified"] is False
    assert manifest["processing"]["opaque_interior_rgb_preserved"] is True
    assert manifest["display"]["default_size"] == 240
    assert manifest["display"]["alternative_size"] == 280
    assert manifest["display"]["runtime_master"].replace("\\", "/") == (
        "assets/processed/base/character_runtime_master.png"
    )

    for record in manifest["assets"]:
        asset_path = PROJECT_ROOT / Path(record["path"])
        assert asset_path.is_file()
        assert sha256(asset_path) == record["sha256"]
        with Image.open(asset_path) as image:
            assert image.size == (record["width"], record["height"])
            assert image.mode == record["mode"]

    for diagnostic in manifest["diagnostics"]:
        assert (PROJECT_ROOT / Path(diagnostic)).is_file()


def test_corrections_are_traceable_and_animation_directory_is_untouched() -> None:
    corrections = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
    targets = {entry["target"] for entry in corrections["corrections"]}

    assert {"definite_foreground", "definite_background"} <= targets
    assert corrections["last_application"]["results"]
    assert [path.name for path in ANIMATIONS_DIR.iterdir()] == [".gitkeep"]


def test_runtime_package_does_not_import_opencv() -> None:
    for source_file in (PROJECT_ROOT / "src").rglob("*.py"):
        assert "import cv2" not in source_file.read_text(encoding="utf-8")


def test_pipeline_is_repeatable_and_keeps_both_originals_unchanged() -> None:
    external_before = sha256(SOURCE_ORIGINAL_IMAGE)
    internal_before = sha256(ORIGINAL_CHARACTER_IMAGE)
    assets_before = {
        path: sha256(path)
        for path in (CHARACTER_CUTOUT_IMAGE, CHARACTER_RUNTIME_MASTER, TRIMAP_PATH, ALPHA_MASK_PATH, MANIFEST_PATH)
    }

    run("all")
    assets_after_first_run = {path: sha256(path) for path in assets_before}
    run("all")
    assets_after_second_run = {path: sha256(path) for path in assets_before}

    assert external_before == EXPECTED_SOURCE_SHA256
    assert internal_before == EXPECTED_SOURCE_SHA256
    assert sha256(SOURCE_ORIGINAL_IMAGE) == external_before
    assert sha256(ORIGINAL_CHARACTER_IMAGE) == internal_before
    assert assets_before == assets_after_first_run == assets_after_second_run
