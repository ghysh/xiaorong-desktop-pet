"""Stage 5 acceptance checks for the user-selected full-body plan B asset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scripts.finalize_fullbody_asset import run

from desktop_pet.paths import (
    ANIMATIONS_DIR,
    CHARACTER_CUTOUT_IMAGE,
    CHARACTER_RUNTIME_MASTER,
    FULLBODY_CONCEPTS_DIR,
    FULLBODY_FINAL_MANIFEST,
    FULLBODY_RUNTIME_MASTER,
    FULLBODY_SELECTED_B_SOURCE,
    ORIGINAL_CHARACTER_IMAGE,
    PROJECT_ROOT,
)

EXPECTED_ORIGINAL_SHA256 = "CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3"
EXPECTED_A_SHA256 = "F02D15C357AFD7DA1DA77496E5D73FA338DA05CB8A6AE2141BAA278CBE3E6C49"
EXPECTED_B_SHA256 = "6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64"
EXPECTED_C_SHA256 = "25DE43E20B36A371506027A3EBEE6DE1BEF82FADD76CB388E7909B4CAC670A5F"
EXPECTED_STAGE_THREE_HASHES = {
    CHARACTER_CUTOUT_IMAGE: "4007456A5460A3A2A2DCCC48303A5E323C465B7488F03898343394841D671F99",
    CHARACTER_RUNTIME_MASTER: "7E5BF9CD7705416B3F0BB310CD3EAA0A1395470D1DBFC9DB010E80969E7242C8",
}
EXTERNAL_ORIGINAL_IMAGE = Path(r"D:\DesktopPet\ori_figure.png")
PLAN_B = FULLBODY_CONCEPTS_DIR / "fullbody_concept_b.png"
PLAN_A = FULLBODY_CONCEPTS_DIR / "fullbody_concept_a.png"
PLAN_C = FULLBODY_CONCEPTS_DIR / "fullbody_concept_c.png"
PREVIEW_SIZES = {
    "fullbody_b_240x360.png": (240, 360),
    "fullbody_b_280x420.png": (280, 420),
    "fullbody_b_320x480.png": (320, 480),
}


def sha256(path: Path) -> str:
    """Return the uppercase SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def open_rgba(path: Path) -> Image.Image:
    """Verify an image then return a handle-free RGBA copy."""
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return image.convert("RGBA").copy()


def test_plan_b_selected_copy_and_final_master_are_byte_identical() -> None:
    assert PLAN_B.is_file()
    assert sha256(PLAN_B) == EXPECTED_B_SHA256
    assert sha256(FULLBODY_SELECTED_B_SOURCE) == EXPECTED_B_SHA256
    assert sha256(FULLBODY_RUNTIME_MASTER) == EXPECTED_B_SHA256
    assert FULLBODY_SELECTED_B_SOURCE.read_bytes() == PLAN_B.read_bytes()
    assert FULLBODY_RUNTIME_MASTER.read_bytes() == PLAN_B.read_bytes()


def test_final_master_is_complete_portrait_rgba_with_safe_alpha_margins() -> None:
    image = open_rgba(FULLBODY_RUNTIME_MASTER)
    alpha = np.asarray(image.getchannel("A"))
    bbox = Image.fromarray(alpha, mode="L").getbbox()

    assert image.size == (1024, 1536)
    assert image.mode == "RGBA"
    assert image.height > image.width
    assert image.width * 3 == image.height * 2
    assert bbox is not None
    assert bbox[0] > 0 and bbox[1] > 0
    assert bbox[2] < image.width and bbox[3] < image.height
    assert np.count_nonzero(alpha == 0) > 0
    assert np.count_nonzero(alpha == 255) > 0
    assert np.count_nonzero((alpha > 0) & (alpha < 255)) > 0


def test_final_master_preserves_all_candidate_pixels_and_has_no_large_fragments() -> None:
    candidate = np.asarray(open_rgba(PLAN_B))
    final = np.asarray(open_rgba(FULLBODY_RUNTIME_MASTER))
    alpha = final[:, :, 3]
    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        (alpha > 0).astype(np.uint8),
        8,
    )
    largest_area = int(stats[1:, cv2.CC_STAT_AREA].max())
    secondary_areas = [
        int(stats[label, cv2.CC_STAT_AREA])
        for label in range(1, component_count)
        if int(stats[label, cv2.CC_STAT_AREA]) != largest_area
    ]

    assert np.array_equal(final, candidate)
    assert np.array_equal(final[final[:, :, 3] == 255], candidate[candidate[:, :, 3] == 255])
    assert all(area <= 32 for area in secondary_areas)


def test_final_manifest_records_user_selection_without_semantic_or_edge_edits() -> None:
    manifest = json.loads(FULLBODY_FINAL_MANIFEST.read_text(encoding="utf-8"))
    quality = manifest["quality"]

    assert manifest["selected_design"] == "B"
    assert manifest["selection_confirmed"] is True
    assert manifest["source_candidate"]["sha256"] == EXPECTED_B_SHA256
    assert manifest["source_candidate"]["modified"] is False
    assert manifest["selected_copy"]["sha256"] == EXPECTED_B_SHA256
    assert manifest["final_asset"]["final_asset"] is True
    assert manifest["final_asset"]["semantic_redraw"] is False
    assert manifest["final_asset"]["technical_edge_refinement"] is False
    assert manifest["final_asset"]["byte_identical_to_selected_copy"] is True
    assert manifest["display_sizes"]["default"] == [280, 420]
    assert quality["alpha_analysis"]["suspected_error_holes"] == 0
    assert quality["alpha_analysis"]["suspicious_magenta_edge_pixels"] == 0
    assert quality["alpha_analysis"]["pixel_difference_count"] == 0


def test_all_runtime_size_previews_preserve_transparency_and_aspect_ratio() -> None:
    preview_directory = FULLBODY_RUNTIME_MASTER.parent.parent / "previews"
    for filename, size in PREVIEW_SIZES.items():
        image = open_rgba(preview_directory / filename)
        alpha = np.asarray(image.getchannel("A"))

        assert image.size == size
        assert image.width * 3 == image.height * 2
        assert np.count_nonzero(alpha == 0) > 0


def test_concept_a_and_c_remain_nonfinal_stage_four_candidates() -> None:
    concept_manifest_path = FULLBODY_RUNTIME_MASTER.parent.parent / "reports" / "fullbody_concept_manifest.json"
    concept_manifest = json.loads(concept_manifest_path.read_text(encoding="utf-8"))
    records = {record["design_plan"]: record for record in concept_manifest["concepts"]}

    assert PLAN_A.is_file() and PLAN_C.is_file()
    assert records["A"]["final_asset"] is False
    assert records["B"]["final_asset"] is False
    assert records["C"]["final_asset"] is False
    assert sha256(PLAN_A) == EXPECTED_A_SHA256
    assert records["B"]["sha256"] == EXPECTED_B_SHA256
    assert sha256(PLAN_C) == EXPECTED_C_SHA256


def test_protected_original_and_stage_three_assets_are_unchanged() -> None:
    assert sha256(EXTERNAL_ORIGINAL_IMAGE) == EXPECTED_ORIGINAL_SHA256
    assert sha256(ORIGINAL_CHARACTER_IMAGE) == EXPECTED_ORIGINAL_SHA256
    for path, expected_hash in EXPECTED_STAGE_THREE_HASHES.items():
        assert sha256(path) == expected_hash
    assert sha256(PLAN_B) == EXPECTED_B_SHA256


def test_runtime_code_has_no_opencv_or_direct_tray_implementation_in_app() -> None:
    app_source = (PROJECT_ROOT / "src" / "desktop_pet" / "app.py").read_text(encoding="utf-8")
    runtime_sources = (PROJECT_ROOT / "src" / "desktop_pet").rglob("*.py")

    assert sorted(path.name for path in ANIMATIONS_DIR.iterdir()) == [".gitkeep"]
    assert "QSystemTrayIcon" not in app_source
    assert app_source.count("QTimer.singleShot") == 1
    assert all("import cv2" not in path.read_text(encoding="utf-8") for path in runtime_sources)


def test_finalization_is_deterministic() -> None:
    run("all")
    first_hashes = (sha256(FULLBODY_RUNTIME_MASTER), sha256(FULLBODY_FINAL_MANIFEST))
    run("all")
    second_hashes = (sha256(FULLBODY_RUNTIME_MASTER), sha256(FULLBODY_FINAL_MANIFEST))

    assert first_hashes == second_hashes
    assert first_hashes[0] == EXPECTED_B_SHA256
