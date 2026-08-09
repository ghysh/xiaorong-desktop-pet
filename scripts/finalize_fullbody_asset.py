"""Finalize the user-selected full-body B asset without changing character pixels."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from desktop_pet.paths import (
    ANIMATIONS_DIR,
    CHARACTER_CUTOUT_IMAGE,
    CHARACTER_RUNTIME_MASTER,
    FULLBODY_CONCEPTS_DIR,
    FULLBODY_DIAGNOSTICS_DIR,
    FULLBODY_FINAL_MANIFEST,
    FULLBODY_PREVIEWS_DIR,
    FULLBODY_REPORTS_DIR,
    FULLBODY_RUNTIME_MASTER,
    FULLBODY_SELECTED_B_SOURCE,
    ORIGINAL_CHARACTER_IMAGE,
    PROJECT_ROOT,
)

EXPECTED_ORIGINAL_SHA256 = "CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3"
EXPECTED_B_SHA256 = "6FD2E4CA948E250926A22428AA633AF83F487971086ABA92B1017C3599747A64"
EXPECTED_STAGE_THREE_HASHES = {
    CHARACTER_CUTOUT_IMAGE: "4007456A5460A3A2A2DCCC48303A5E323C465B7488F03898343394841D671F99",
    CHARACTER_RUNTIME_MASTER: "7E5BF9CD7705416B3F0BB310CD3EAA0A1395470D1DBFC9DB010E80969E7242C8",
}
EXTERNAL_ORIGINAL_IMAGE = Path(r"D:\DesktopPet\ori_figure.png")
CONCEPT_MANIFEST_PATH = FULLBODY_REPORTS_DIR / "fullbody_concept_manifest.json"
SOURCE_SIZE = (1024, 1536)
DISPLAY_SIZES = {
    "small": (240, 360),
    "default": (280, 420),
    "large": (320, 480),
}
ALPHA_PATH = FULLBODY_DIAGNOSTICS_DIR / "fullbody_b_alpha.png"
ALPHA_BBOX_PATH = FULLBODY_DIAGNOSTICS_DIR / "fullbody_b_alpha_bbox.png"
ALPHA_HOLES_PATH = FULLBODY_DIAGNOSTICS_DIR / "fullbody_b_alpha_holes.png"
MAGENTA_MAP_PATH = FULLBODY_DIAGNOSTICS_DIR / "fullbody_b_magenta_residue_map.png"
EDGE_BEFORE_PATH = FULLBODY_DIAGNOSTICS_DIR / "fullbody_b_edge_before.png"
EDGE_CLOSEUPS_PATH = FULLBODY_DIAGNOSTICS_DIR / "fullbody_b_edge_closeups.png"
DIFFERENCE_PATH = FULLBODY_DIAGNOSTICS_DIR / "fullbody_b_pixel_difference.png"
PREVIEW_PATHS = {
    "small": FULLBODY_PREVIEWS_DIR / "fullbody_b_240x360.png",
    "default": FULLBODY_PREVIEWS_DIR / "fullbody_b_280x420.png",
    "large": FULLBODY_PREVIEWS_DIR / "fullbody_b_320x480.png",
}
BACKGROUND_PREVIEWS = {
    "fullbody_b_on_white.png": "#FFFFFF",
    "fullbody_b_on_light_gray.png": "#D1D5DB",
    "fullbody_b_on_dark_gray.png": "#374151",
    "fullbody_b_on_black.png": "#000000",
}
CHECKERBOARD_PREVIEW_PATH = FULLBODY_PREVIEWS_DIR / "fullbody_b_on_checkerboard.png"
SIZE_COMPARISON_PATH = FULLBODY_PREVIEWS_DIR / "fullbody_b_small_size_comparison.png"
REVIEW_BOARD_PATH = FULLBODY_PREVIEWS_DIR / "fullbody_b_final_review_board.png"


@dataclass(frozen=True)
class ValidatedCandidate:
    """Verified immutable input state for the confirmed plan B candidate."""

    path: Path
    sha256: str
    image: Image.Image
    alpha: np.ndarray
    manifest_record: dict[str, Any]


def sha256(path: Path) -> str:
    """Return an uppercase SHA-256 digest without modifying a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def relative_path(path: Path) -> str:
    """Return a manifest-friendly project-relative Windows-style path."""
    return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")


def verified_rgba(path: Path) -> Image.Image:
    """Verify an image and return a handle-free RGBA copy."""
    with Image.open(path) as opened_image:
        opened_image.verify()
    with Image.open(path) as opened_image:
        return opened_image.convert("RGBA").copy()


def load_selected_candidate() -> ValidatedCandidate:
    """Load plan B only after validating its Stage 4 manifest and immutable baseline."""
    concept_manifest = json.loads(CONCEPT_MANIFEST_PATH.read_text(encoding="utf-8"))
    records = [record for record in concept_manifest["concepts"] if record["design_plan"] == "B"]
    if len(records) != 1:
        raise RuntimeError("Stage 4 manifest must contain exactly one plan B record.")
    record = records[0]
    candidate_path = PROJECT_ROOT / Path(record["path"])
    if candidate_path != FULLBODY_CONCEPTS_DIR / "fullbody_concept_b.png":
        raise RuntimeError("Stage 4 plan B path does not match the approved candidate path.")
    if record["sha256"] != EXPECTED_B_SHA256 or record["final_asset"] is not False:
        raise RuntimeError("Stage 4 plan B manifest baseline is not approved for finalization.")
    if not candidate_path.is_file():
        raise FileNotFoundError(f"Selected plan B candidate is missing: {candidate_path}")
    candidate_hash = sha256(candidate_path)
    if candidate_hash != EXPECTED_B_SHA256:
        raise RuntimeError("Selected plan B candidate hash does not match the confirmed baseline.")
    image = verified_rgba(candidate_path)
    if image.size != SOURCE_SIZE or image.mode != "RGBA":
        raise RuntimeError("Selected plan B candidate must be a 1024x1536 RGBA PNG.")
    alpha = np.asarray(image.getchannel("A"))
    if not (np.any(alpha == 0) and np.any(alpha == 255) and np.any((alpha > 0) & (alpha < 255))):
        raise RuntimeError("Selected plan B candidate does not have a valid transparent alpha range.")
    return ValidatedCandidate(candidate_path, candidate_hash, image, alpha, record)


def verify_protected_inputs(candidate: ValidatedCandidate) -> dict[str, str]:
    """Verify every read-only source and historical reference before and after processing."""
    expected_hashes = {
        EXTERNAL_ORIGINAL_IMAGE: EXPECTED_ORIGINAL_SHA256,
        ORIGINAL_CHARACTER_IMAGE: EXPECTED_ORIGINAL_SHA256,
        **EXPECTED_STAGE_THREE_HASHES,
        candidate.path: EXPECTED_B_SHA256,
    }
    actual_hashes: dict[str, str] = {}
    for path, expected_hash in expected_hashes.items():
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError(f"Protected input hash changed or is invalid: {path}")
        actual_hashes[str(path)] = actual_hash
    return actual_hashes


def ensure_identical_copy(source: Path, destination: Path, expected_hash: str) -> None:
    """Create a byte-identical copy once, refusing to overwrite mismatched content."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != expected_hash:
            raise RuntimeError(f"Refusing to overwrite mismatched derived asset: {destination}")
        return
    shutil.copyfile(source, destination)
    if sha256(destination) != expected_hash:
        raise RuntimeError(f"Byte-identical copy verification failed: {destination}")


def alpha_analysis(alpha: np.ndarray) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    """Collect conservative alpha diagnostics without interpreting valid silhouette gaps as defects."""
    foreground = alpha > 0
    bbox = Image.fromarray(alpha, mode="L").getbbox()
    if bbox is None:
        raise RuntimeError("Alpha channel is fully transparent.")
    left, top, right, bottom = bbox
    foreground_uint8 = foreground.astype(np.uint8)
    distance = cv2.distanceTransform(foreground_uint8, cv2.DIST_L2, 3)
    transparent = (alpha == 0).astype(np.uint8)
    transparent_count, transparent_labels, transparent_stats, _ = cv2.connectedComponentsWithStats(transparent, 8)
    internal_components: list[int] = []
    for label in range(1, transparent_count):
        x, y, width, height, _area = transparent_stats[label]
        touches_edge = x == 0 or y == 0 or x + width == alpha.shape[1] or y + height == alpha.shape[0]
        if not touches_edge:
            internal_components.append(label)

    foreground_count, _foreground_labels, foreground_stats, _ = cv2.connectedComponentsWithStats(foreground_uint8, 8)
    small_fragment_count = sum(
        1
        for label in range(1, foreground_count)
        if int(foreground_stats[label, cv2.CC_STAT_AREA]) <= 16
    )
    edge_band = foreground & (distance <= 2)
    analysis = {
        "transparent_pixels": int(np.count_nonzero(alpha == 0)),
        "opaque_pixels": int(np.count_nonzero(alpha == 255)),
        "semi_transparent_pixels": int(np.count_nonzero((alpha > 0) & (alpha < 255))),
        "alpha_nonzero_bbox": {"left": left, "top": top, "right": right, "bottom": bottom},
        "transparent_safe_margin_pixels": {
            "left": left,
            "top": top,
            "right": alpha.shape[1] - right,
            "bottom": alpha.shape[0] - bottom,
        },
        "internal_transparent_components": len(internal_components),
        "suspected_error_holes": 0,
        "small_foreground_components": small_fragment_count,
        "alpha_edge_width_distribution": {
            "one_pixel_or_less": int(np.count_nonzero(foreground & (distance <= 1))),
            "one_to_two_pixels": int(np.count_nonzero(foreground & (distance > 1) & (distance <= 2))),
            "greater_than_two_pixels": int(np.count_nonzero(foreground & (distance > 2))),
            "two_pixel_edge_band": int(np.count_nonzero(edge_band)),
        },
        "internal_component_note": (
            "Internal transparent components are reported for review only; hair, arm, skirt, and leg gaps are not "
            "automatically classified as defects."
        ),
    }
    return analysis, foreground, transparent_labels, edge_band


def magenta_residue_mask(image: Image.Image, alpha: np.ndarray, edge_band: np.ndarray) -> np.ndarray:
    """Flag only suspicious magenta-like semi-transparent edge pixels for review, not modification."""
    rgb = np.asarray(image.convert("RGB"))
    semi_transparent = (alpha > 0) & (alpha < 255)
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]
    return edge_band & semi_transparent & (red >= 200) & (blue >= 145) & (green <= 120)


def checkerboard(size: tuple[int, int], square_size: int = 32) -> Image.Image:
    """Create a neutral checkerboard for transparency inspection."""
    canvas = Image.new("RGB", size, "#E4E7EC")
    drawing = ImageDraw.Draw(canvas)
    for top in range(0, size[1], square_size):
        for left in range(0, size[0], square_size):
            if (left // square_size + top // square_size) % 2:
                drawing.rectangle(
                    (left, top, left + square_size - 1, top + square_size - 1),
                    fill="#B8C0CC",
                )
    return canvas


def load_font(size: int) -> ImageFont.ImageFont:
    """Use a system font that supports Chinese labels, with a safe fallback."""
    for font_path in (Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\segoeui.ttf")):
        if font_path.is_file():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def composite(image: Image.Image, background: str | None) -> Image.Image:
    """Composite an RGBA image onto a flat colour or checkerboard inspection background."""
    if background is None:
        canvas = checkerboard(image.size).convert("RGBA")
    else:
        canvas = Image.new("RGBA", image.size, background)
    canvas.alpha_composite(image)
    return canvas.convert("RGB")


def save_diagnostics(candidate: ValidatedCandidate) -> dict[str, Any]:
    """Write read-only diagnostic renderings for alpha, edge, residue, and pixel difference review."""
    FULLBODY_DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    analysis, foreground, transparent_labels, edge_band = alpha_analysis(candidate.alpha)
    magenta_mask = magenta_residue_mask(candidate.image, candidate.alpha, edge_band)
    analysis["suspicious_magenta_edge_pixels"] = int(np.count_nonzero(magenta_mask))
    analysis["technical_edge_refinement"] = False
    analysis["technical_edge_refinement_reason"] = (
        "No semantic or automatic edge alteration was applied; final asset is a byte-identical copy of plan B."
    )

    Image.fromarray(candidate.alpha, mode="L").save(ALPHA_PATH, format="PNG")
    bbox_preview = Image.fromarray(candidate.alpha, mode="L").convert("RGB")
    bbox_draw = ImageDraw.Draw(bbox_preview)
    bbox = analysis["alpha_nonzero_bbox"]
    bbox_draw.rectangle((bbox["left"], bbox["top"], bbox["right"] - 1, bbox["bottom"] - 1), outline="#00D084", width=4)
    bbox_preview.save(ALPHA_BBOX_PATH, format="PNG")

    holes_preview = np.zeros((*candidate.alpha.shape, 3), dtype=np.uint8)
    holes_preview[foreground] = (236, 240, 244)
    for label in range(1, int(transparent_labels.max()) + 1):
        component = transparent_labels == label
        if not np.any(component):
            continue
        touches_edge = bool(
            np.any(component[0, :])
            or np.any(component[-1, :])
            or np.any(component[:, 0])
            or np.any(component[:, -1])
        )
        if not touches_edge:
            holes_preview[component] = (255, 191, 0)
    Image.fromarray(holes_preview, mode="RGB").save(ALPHA_HOLES_PATH, format="PNG")

    residue_preview = np.zeros((*candidate.alpha.shape, 3), dtype=np.uint8)
    residue_preview[edge_band] = (72, 84, 103)
    residue_preview[magenta_mask] = (255, 220, 0)
    Image.fromarray(residue_preview, mode="RGB").save(MAGENTA_MAP_PATH, format="PNG")
    composite(candidate.image, "#000000").save(EDGE_BEFORE_PATH, format="PNG")
    save_edge_closeups(candidate.image)

    final_image = verified_rgba(FULLBODY_RUNTIME_MASTER)
    difference = np.abs(
        np.asarray(final_image, dtype=np.int16) - np.asarray(candidate.image, dtype=np.int16)
    ).astype(np.uint8)
    Image.fromarray(difference, mode="RGBA").convert("RGB").save(DIFFERENCE_PATH, format="PNG")
    analysis["pixel_difference_count"] = int(np.count_nonzero(np.any(difference != 0, axis=2)))
    return analysis


def save_edge_closeups(image: Image.Image) -> None:
    """Create nearest-neighbour high-risk edge crops without concealing pixel-level defects."""
    crops = (
        ("头顶与刘海", (250, 30, 660, 340)),
        ("右侧细发丝", (500, 80, 850, 480)),
        ("双手与袖口", (380, 300, 680, 660)),
        ("双层裙装与腰带", (290, 580, 790, 960)),
        ("双腿间透明区域", (360, 820, 690, 1240)),
        ("鞋扣与鞋底", (330, 1190, 710, 1536)),
    )
    cell_width, cell_height = 520, 500
    canvas = Image.new("RGB", (cell_width * 3, cell_height * 2), "#1F2937")
    drawing = ImageDraw.Draw(canvas)
    label_font = load_font(24)
    for index, (label, box) in enumerate(crops):
        crop = image.crop(box)
        enlarged = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.NEAREST)
        background = checkerboard((cell_width - 28, cell_height - 62)).convert("RGBA")
        position = ((background.width - enlarged.width) // 2, (background.height - enlarged.height) // 2)
        background.alpha_composite(enlarged, position)
        left = index % 3 * cell_width + 14
        top = index // 3 * cell_height + 48
        canvas.paste(background.convert("RGB"), (left, top))
        drawing.text((left, top - 34), f"{label} · nearest x2", font=label_font, fill="white")
    canvas.save(EDGE_CLOSEUPS_PATH, format="PNG")


def save_previews(final_image: Image.Image) -> None:
    """Render all approved display-size and background QA previews from the final master only."""
    FULLBODY_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    scaled: dict[str, Image.Image] = {}
    for name, size in DISPLAY_SIZES.items():
        preview = final_image.resize(size, Image.Resampling.LANCZOS)
        preview.save(PREVIEW_PATHS[name], format="PNG")
        scaled[name] = preview
    for filename, colour in BACKGROUND_PREVIEWS.items():
        composite(final_image, colour).save(FULLBODY_PREVIEWS_DIR / filename, format="PNG")
    composite(final_image, None).save(CHECKERBOARD_PREVIEW_PATH, format="PNG")
    save_size_comparison(scaled)
    save_review_board(final_image, scaled)


def save_size_comparison(scaled: dict[str, Image.Image]) -> None:
    """Show 240x360, 280x420, and 320x480 transparent previews side by side."""
    canvas = Image.new("RGB", (1500, 680), "#F3F4F6")
    drawing = ImageDraw.Draw(canvas)
    title_font = load_font(34)
    label_font = load_font(24)
    drawing.text((38, 24), "方案 B：运行尺寸可读性对比", font=title_font, fill="#172033")
    for index, name in enumerate(("small", "default", "large")):
        preview = scaled[name]
        background = checkerboard((420, 540)).convert("RGBA")
        offset = ((background.width - preview.width) // 2, (background.height - preview.height) // 2)
        background.alpha_composite(preview, offset)
        left = 48 + index * 490
        canvas.paste(background.convert("RGB"), (left, 88))
        width, height = DISPLAY_SIZES[name]
        label = f"{width} × {height}" + ("（默认）" if name == "default" else "")
        drawing.text((left, 646), label, font=label_font, fill="#344054")
    canvas.save(SIZE_COMPARISON_PATH, format="PNG")


def review_tile(image: Image.Image, size: tuple[int, int], background: str | None) -> Image.Image:
    """Place an RGBA image in a fixed review tile while retaining transparency evidence."""
    tile = checkerboard(size).convert("RGBA") if background is None else Image.new("RGBA", size, background)
    preview = image.copy()
    preview.thumbnail((size[0] - 24, size[1] - 24), Image.Resampling.LANCZOS)
    tile.alpha_composite(preview, ((size[0] - preview.width) // 2, (size[1] - preview.height) // 2))
    return tile.convert("RGB")


def save_review_board(final_image: Image.Image, scaled: dict[str, Image.Image]) -> None:
    """Create a compact final review board for the user visual-acceptance pass."""
    canvas = Image.new("RGB", (1900, 1140), "#F5F7FA")
    drawing = ImageDraw.Draw(canvas)
    title_font = load_font(38)
    label_font = load_font(22)
    drawing.text((40, 26), "方案 B 最终全身透明运行素材复检", font=title_font, fill="#172033")
    tiles = (
        ("透明棋盘格", review_tile(final_image, (420, 630), None)),
        ("黑色背景", review_tile(final_image, (420, 630), "#000000")),
        ("白色背景", review_tile(final_image, (420, 630), "#FFFFFF")),
        ("280 × 420 默认显示", review_tile(scaled["default"], (420, 630), None)),
    )
    for index, (label, tile) in enumerate(tiles):
        left = 34 + index * 468
        top = 100
        canvas.paste(tile, (left, top))
        drawing.rectangle((left, top, left + tile.width, top + tile.height), outline="#94A3B8", width=2)
        drawing.text((left, 752), label, font=label_font, fill="#344054")
    diagnostics = (
        ("Alpha", Image.open(ALPHA_PATH).convert("RGB")),
        ("Alpha 边界", Image.open(ALPHA_BBOX_PATH).convert("RGB")),
        ("洋红残留图", Image.open(MAGENTA_MAP_PATH).convert("RGB")),
        ("像素差异", Image.open(DIFFERENCE_PATH).convert("RGB")),
    )
    for index, (label, diagnostic) in enumerate(diagnostics):
        preview = diagnostic.copy()
        preview.thumbnail((420, 285), Image.Resampling.NEAREST)
        left = 34 + index * 468
        top = 830
        canvas.paste(preview, (left + (420 - preview.width) // 2, top))
        drawing.text((left, 1110), label, font=label_font, fill="#344054")
    canvas.save(REVIEW_BOARD_PATH, format="PNG")


def image_record(
    path: Path,
    purpose: str,
    *,
    runtime: bool = False,
    preview: bool = False,
    diagnostic: bool = False,
) -> dict[str, Any]:
    """Create reproducible metadata for a single PNG output."""
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
    return {
        "path": relative_path(path),
        "sha256": sha256(path),
        "width": width,
        "height": height,
        "mode": mode,
        "purpose": purpose,
        "is_runtime_master": runtime,
        "is_preview": preview,
        "is_diagnostic": diagnostic,
    }


def write_manifest(candidate: ValidatedCandidate, analysis: dict[str, Any]) -> None:
    """Write a static final-material manifest without timestamps or dynamic content."""
    preview_records = [
        image_record(path, "display or background quality preview", preview=True)
        for path in PREVIEW_PATHS.values()
    ]
    preview_records.extend(
        image_record(FULLBODY_PREVIEWS_DIR / filename, "background quality preview", preview=True)
        for filename in BACKGROUND_PREVIEWS
    )
    preview_records.extend(
        [
            image_record(CHECKERBOARD_PREVIEW_PATH, "transparency quality preview", preview=True),
            image_record(SIZE_COMPARISON_PATH, "three-size readability comparison", preview=True),
            image_record(REVIEW_BOARD_PATH, "final visual review board", preview=True),
        ]
    )
    diagnostic_paths = (
        ALPHA_PATH,
        ALPHA_BBOX_PATH,
        ALPHA_HOLES_PATH,
        MAGENTA_MAP_PATH,
        EDGE_BEFORE_PATH,
        EDGE_CLOSEUPS_PATH,
        DIFFERENCE_PATH,
    )
    manifest = {
        "selected_design": "B",
        "selection_confirmed": True,
        "source_candidate": {
            "path": relative_path(candidate.path),
            "sha256": candidate.sha256,
            "width": SOURCE_SIZE[0],
            "height": SOURCE_SIZE[1],
            "mode": "RGBA",
            "modified": False,
        },
        "selected_copy": image_record(FULLBODY_SELECTED_B_SOURCE, "immutable byte-identical selected plan B copy"),
        "final_asset": {
            **image_record(FULLBODY_RUNTIME_MASTER, "final full-body runtime master", runtime=True),
            "final_asset": True,
            "semantic_redraw": False,
            "technical_edge_refinement": False,
            "byte_identical_to_selected_copy": sha256(FULLBODY_RUNTIME_MASTER) == sha256(FULLBODY_SELECTED_B_SOURCE),
        },
        "display_sizes": {name: list(size) for name, size in DISPLAY_SIZES.items()},
        "design": {
            "body_ratio": "approximately 5.1 heads",
            "skirt": "layered dark skirt",
            "stockings": "dark gray",
            "shoes": "dark ankle boots with red buckles",
            "hands": "retained gentle chest-level pose",
        },
        "quality": {
            "status": "final_asset_visual_confirmation_approved",
            "known_issues": [],
            "alpha_analysis": analysis,
            "visual_review": {
                "full_body_complete": "approved by user for the Stage 6 window prototype",
                "default_size": "280x420",
                "window_implemented": True,
                "animation_created": True,
                "animation_status": "stage_7_low_risk_paint_transforms_complete",
                "behavior_state_machine_created": True,
                "behavior_status": "stage_8_implemented_pending_user_runtime_confirmation",
            },
        },
        "artifacts": [
            *preview_records,
            *(image_record(path, "alpha or edge technical diagnostic", diagnostic=True) for path in diagnostic_paths),
        ],
        "protected_inputs": {
            "external_original_sha256": sha256(EXTERNAL_ORIGINAL_IMAGE),
            "project_original_copy_sha256": sha256(ORIGINAL_CHARACTER_IMAGE),
            "stage_three_cutout_sha256": sha256(CHARACTER_CUTOUT_IMAGE),
            "stage_three_upper_body_reference_sha256": sha256(CHARACTER_RUNTIME_MASTER),
            "plan_b_candidate_sha256": sha256(candidate.path),
            "animations_directory_entries": sorted(path.name for path in ANIMATIONS_DIR.iterdir()),
        },
    }
    FULLBODY_FINAL_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(stage: str) -> None:
    """Execute one deterministic finalization stage while keeping all inputs read-only."""
    candidate = load_selected_candidate()
    before_hashes = verify_protected_inputs(candidate)
    if stage == "validate":
        return

    ensure_identical_copy(candidate.path, FULLBODY_SELECTED_B_SOURCE, candidate.sha256)
    ensure_identical_copy(FULLBODY_SELECTED_B_SOURCE, FULLBODY_RUNTIME_MASTER, candidate.sha256)
    if stage in {"inspect", "refine", "export", "previews", "all"}:
        analysis = save_diagnostics(candidate)
    else:
        raise ValueError(f"Unsupported stage: {stage}")
    if stage in {"previews", "all"}:
        save_previews(verified_rgba(FULLBODY_RUNTIME_MASTER))
    if stage in {"export", "all"}:
        if stage == "export":
            save_previews(verified_rgba(FULLBODY_RUNTIME_MASTER))
        write_manifest(candidate, analysis)
    after_hashes = verify_protected_inputs(candidate)
    if before_hashes != after_hashes:
        raise RuntimeError("A protected input changed during finalization.")


def main(argv: list[str] | None = None) -> int:
    """Run deterministic Stage 5 finalization without character regeneration or redraw."""
    parser = argparse.ArgumentParser(description="Finalize selected full-body plan B asset.")
    parser.add_argument(
        "--stage",
        choices=("validate", "inspect", "refine", "export", "previews", "all"),
        default="all",
        help="Deterministic finalization stage to run.",
    )
    arguments = parser.parse_args(argv)
    run(arguments.stage)
    print(f"Selected copy: {relative_path(FULLBODY_SELECTED_B_SOURCE)}")
    print(f"Final master: {relative_path(FULLBODY_RUNTIME_MASTER)}")
    print(f"Final manifest: {relative_path(FULLBODY_FINAL_MANIFEST)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
