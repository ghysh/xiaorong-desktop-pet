"""Build deterministic, local-only RGBA base assets from the approved source copy."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from desktop_pet.paths import (
    ANALYSIS_DIR,
    BASE_ASSETS_DIR,
    CHARACTER_CUTOUT_IMAGE,
    CHARACTER_RUNTIME_MASTER,
    MASKS_ASSETS_DIR,
    ORIGINAL_CHARACTER_IMAGE,
    PROCESSED_PREVIEWS_DIR,
    PROCESSED_REPORTS_DIR,
    PROJECT_ROOT,
)

EXPECTED_SOURCE_SHA256 = "CCF0AABC6D1DD7AFF61590E40BBEF7C0E2411B6524CF47C72D6BC10BDE900DB3"
SOURCE_SIZE = (346, 346)
RUNTIME_MASTER_SIZE = (410, 410)
DEFAULT_DISPLAY_SIZE = 240
ALTERNATIVE_DISPLAY_SIZE = 280
BACKGROUND_RGB = np.array([255, 255, 255], dtype=np.float32)
TRANSPARENCY_DIAGNOSTICS_DIR = ANALYSIS_DIR / "transparency"
CORRECTIONS_PATH = MASKS_ASSETS_DIR / "mask_corrections.json"
TRIMAP_PATH = MASKS_ASSETS_DIR / "character_trimap.png"
ALPHA_MASK_PATH = MASKS_ASSETS_DIR / "character_alpha_mask.png"
MANIFEST_PATH = PROCESSED_REPORTS_DIR / "asset_manifest.json"
PHASE_TWO_REPORT_PATH = ANALYSIS_DIR / "reports" / "character_analysis.json"


@dataclass(frozen=True)
class SegmentationResult:
    """In-memory outputs of the deterministic mask construction pipeline."""

    background_core: np.ndarray
    grabcut_labels: np.ndarray
    foreground: np.ndarray
    trimap: np.ndarray
    alpha: np.ndarray
    correction_results: list[dict[str, Any]]


def sha256(path: Path) -> str:
    """Return an uppercase SHA-256 digest without modifying a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_approved_source() -> tuple[np.ndarray, str]:
    """Verify and load the project-internal source copy as RGB pixels."""
    if not ORIGINAL_CHARACTER_IMAGE.is_file():
        raise FileNotFoundError(f"Original character image not found: {ORIGINAL_CHARACTER_IMAGE}")
    before_hash = sha256(ORIGINAL_CHARACTER_IMAGE)
    if before_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Original image hash does not match the approved baseline.")

    with Image.open(ORIGINAL_CHARACTER_IMAGE) as opened_image:
        opened_image.verify()
    with Image.open(ORIGINAL_CHARACTER_IMAGE) as opened_image:
        if opened_image.size != SOURCE_SIZE or opened_image.mode != "RGB":
            raise RuntimeError("Original image properties do not match the approved baseline.")
        image = np.asarray(opened_image.convert("RGB"), dtype=np.uint8).copy()
    return image, before_hash


def verify_phase_two_background_baseline() -> None:
    """Confirm that the local processing uses the approved phase-two background candidate."""
    analysis_report = json.loads(PHASE_TWO_REPORT_PATH.read_text(encoding="utf-8"))
    background = analysis_report["background_analysis"]["edge_background_candidate"]["rgb"]
    if background != [255, 255, 255]:
        raise RuntimeError("Phase-two background candidate no longer matches this processing baseline.")


def connected_from_canvas_edge(candidate: np.ndarray) -> np.ndarray:
    """Keep only candidate components connected to the canvas boundary."""
    component_count, labels = cv2.connectedComponents(candidate.astype(np.uint8), connectivity=8)
    if component_count <= 1:
        return np.zeros_like(candidate, dtype=bool)
    edge_labels = np.unique(
        np.concatenate(
            (
                labels[0, :],
                labels[-1, :],
                labels[:, 0],
                labels[:, -1],
            )
        )
    )
    edge_labels = edge_labels[edge_labels != 0]
    return np.isin(labels, edge_labels)


def colour_distance_to_background(image: np.ndarray) -> np.ndarray:
    """Calculate RGB distance to the phase-two near-white background candidate."""
    difference = image.astype(np.float32) - BACKGROUND_RGB
    return np.sqrt(np.sum(difference * difference, axis=2))


def correction_shape(entry: dict[str, Any], shape: tuple[int, int]) -> np.ndarray:
    """Create one explicit correction shape from the JSON configuration."""
    mask = np.zeros(shape, dtype=np.uint8)
    correction_type = entry["type"]
    if correction_type == "ellipse":
        center = tuple(int(value) for value in entry["center"])
        radii = tuple(int(value) for value in entry["radii"])
        cv2.ellipse(mask, center, radii, 0, 0, 360, 255, thickness=-1)
    elif correction_type == "polygon":
        points = np.asarray(entry["points"], dtype=np.int32)
        cv2.fillPoly(mask, [points], 255)
    else:
        raise ValueError(f"Unsupported correction type: {correction_type}")
    return mask.astype(bool)


def apply_corrections(
    definite_foreground: np.ndarray,
    corrections_data: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """Apply documented foreground and background corrections with traceable counts."""
    protected = np.zeros_like(definite_foreground, dtype=bool)
    forced_background = np.zeros_like(definite_foreground, dtype=bool)
    results: list[dict[str, Any]] = []
    for correction in corrections_data["corrections"]:
        shape = correction_shape(correction, definite_foreground.shape)
        target = correction["target"]
        if target == "definite_foreground":
            pixels_before = int(np.count_nonzero(definite_foreground & shape))
            protected |= shape
        elif target == "definite_background":
            pixels_before = int(np.count_nonzero((~definite_foreground) & shape))
            forced_background |= shape
        else:
            raise ValueError(f"Unsupported correction target: {target}")
        pixels_after = int(np.count_nonzero(shape))
        results.append(
            {
                "id": correction["id"],
                "target": target,
                "reason": correction["reason"],
                "affects_semitransparent_edge": correction["affects_semitransparent_edge"],
                "pixels_before": pixels_before,
                "pixels_after": pixels_after,
                "pixels_added": pixels_after - pixels_before,
            }
        )
    return protected, forced_background, results


def fill_small_internal_holes(foreground: np.ndarray, maximum_area: int = 8) -> np.ndarray:
    """Fill only tiny non-edge-connected holes, preserving meaningful hair gaps."""
    background = (~foreground).astype(np.uint8)
    component_count, labels, statistics_data, _ = cv2.connectedComponentsWithStats(
        background,
        connectivity=8,
    )
    result = foreground.copy()
    height, width = foreground.shape
    for label in range(1, component_count):
        x, y, component_width, component_height, area = statistics_data[label]
        touches_edge = (
            x == 0
            or y == 0
            or x + component_width == width
            or y + component_height == height
        )
        if not touches_edge and area <= maximum_area:
            result[labels == label] = True
    return result


def build_trimap(foreground: np.ndarray, band_pixels: int) -> np.ndarray:
    """Encode definite background, unknown edge, and definite foreground as 0/128/255."""
    kernel_size = band_pixels * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    foreground_uint8 = foreground.astype(np.uint8)
    background_uint8 = (~foreground).astype(np.uint8)
    definite_foreground = cv2.erode(foreground_uint8, kernel, iterations=1).astype(bool)
    definite_background = cv2.erode(background_uint8, kernel, iterations=1).astype(bool)
    trimap = np.full(foreground.shape, 128, dtype=np.uint8)
    trimap[definite_background] = 0
    trimap[definite_foreground] = 255
    return trimap


def build_alpha(
    foreground: np.ndarray,
    image: np.ndarray,
    background_tolerance: float,
    edge_band_pixels: int,
) -> np.ndarray:
    """Create a straight-alpha edge band without modifying opaque interior pixels."""
    foreground_uint8 = foreground.astype(np.uint8)
    distance_inside = cv2.distanceTransform(foreground_uint8, cv2.DIST_L2, 3)
    alpha = np.zeros(foreground.shape, dtype=np.uint8)
    alpha[foreground] = 255

    edge_band = foreground & (distance_inside <= edge_band_pixels)
    colour_distance = colour_distance_to_background(image)
    colour_alpha = np.clip(
        (colour_distance - background_tolerance / 3) * 4.2,
        0,
        255,
    )
    distance_alpha = np.clip(distance_inside * 110, 0, 255)
    edge_alpha = np.maximum(colour_alpha, distance_alpha).astype(np.uint8)
    alpha[edge_band] = edge_alpha[edge_band]
    alpha[(foreground) & (distance_inside > edge_band_pixels)] = 255
    return alpha


def build_segmentation(
    image: np.ndarray,
    corrections_data: dict[str, Any],
) -> SegmentationResult:
    """Use edge-connected near-white seeds plus explicit GrabCut mask initialisation."""
    configuration = corrections_data["edge_configuration"]
    colour_distance = colour_distance_to_background(image)
    background_core = connected_from_canvas_edge(
        colour_distance <= configuration["background_distance_tolerance"]
    )
    possible_background = connected_from_canvas_edge(
        colour_distance <= configuration["possible_background_tolerance"]
    )
    definite_foreground = colour_distance >= configuration["foreground_distance_threshold"]
    protected, forced_background, correction_results = apply_corrections(
        definite_foreground,
        corrections_data,
    )
    definite_foreground |= protected
    background_core |= forced_background
    possible_background |= forced_background

    labels = np.full(image.shape[:2], cv2.GC_PR_FGD, dtype=np.uint8)
    labels[possible_background] = cv2.GC_PR_BGD
    labels[background_core] = cv2.GC_BGD
    labels[definite_foreground] = cv2.GC_FGD
    labels[forced_background] = cv2.GC_BGD

    # GrabCut's GMM initialisation reads OpenCV's global RNG; reset it so that
    # identical source pixels and correction data always produce one result.
    cv2.setRNGSeed(0)
    background_model = np.zeros((1, 65), dtype=np.float64)
    foreground_model = np.zeros((1, 65), dtype=np.float64)
    cv2.grabCut(
        image,
        labels,
        None,
        background_model,
        foreground_model,
        iterCount=5,
        mode=cv2.GC_INIT_WITH_MASK,
    )
    foreground = (labels == cv2.GC_FGD) | (labels == cv2.GC_PR_FGD)
    foreground[background_core] = False
    foreground[protected] = True
    foreground[forced_background] = False
    foreground = fill_small_internal_holes(foreground)
    trimap = build_trimap(foreground, configuration["trimap_band_pixels"])
    alpha = build_alpha(
        foreground,
        image,
        configuration["background_distance_tolerance"],
        configuration["decontamination_band_pixels"],
    )
    return SegmentationResult(
        background_core=background_core,
        grabcut_labels=labels,
        foreground=foreground,
        trimap=trimap,
        alpha=alpha,
        correction_results=correction_results,
    )


def decontaminate_edge(image: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Remove near-white background mixing only from semi-transparent edge pixels."""
    before = np.dstack((image, alpha))
    after_rgb = image.astype(np.float32).copy()
    alpha_fraction = alpha.astype(np.float32) / 255.0
    semi_transparent = (alpha > 0) & (alpha < 255)
    for channel in range(3):
        unmixed = (
            image[:, :, channel].astype(np.float32)
            - BACKGROUND_RGB[channel] * (1.0 - alpha_fraction)
        )
        unmixed = np.divide(
            unmixed,
            alpha_fraction,
            out=image[:, :, channel].astype(np.float32),
            where=alpha_fraction > 0,
        )
        after_rgb[:, :, channel][semi_transparent] = np.clip(
            unmixed[semi_transparent],
            0,
            255,
        )
    after = np.dstack((after_rgb.astype(np.uint8), alpha))
    return before, after


def save_rgba(array: np.ndarray, path: Path) -> None:
    """Write an RGBA PNG with straight alpha."""
    Image.fromarray(array, mode="RGBA").save(path, format="PNG")


def save_grayscale(array: np.ndarray, path: Path) -> None:
    """Write a single-channel grayscale PNG."""
    Image.fromarray(array, mode="L").save(path, format="PNG")


def save_label_diagnostic(labels: np.ndarray, path: Path) -> None:
    """Render the four GrabCut labels as visually distinguishable diagnostic colours."""
    colours = {
        cv2.GC_BGD: (0, 0, 0),
        cv2.GC_FGD: (255, 255, 255),
        cv2.GC_PR_BGD: (88, 88, 190),
        cv2.GC_PR_FGD: (76, 180, 76),
    }
    diagnostic = np.zeros((*labels.shape, 3), dtype=np.uint8)
    for label, colour in colours.items():
        diagnostic[labels == label] = colour
    Image.fromarray(diagnostic, mode="RGB").save(path, format="PNG")


def runtime_master(cutout: Image.Image) -> Image.Image:
    """Center the unscaled source-coordinate cutout in the approved transparent canvas."""
    master = Image.new("RGBA", RUNTIME_MASTER_SIZE, (0, 0, 0, 0))
    offset = (
        (RUNTIME_MASTER_SIZE[0] - cutout.width) // 2,
        (RUNTIME_MASTER_SIZE[1] - cutout.height) // 2,
    )
    master.alpha_composite(cutout, offset)
    return master


def checkerboard(size: tuple[int, int], square_size: int = 20) -> Image.Image:
    """Return a neutral RGB transparency-checkerboard background."""
    background = Image.new("RGB", size, "#E5E7EB")
    drawing = ImageDraw.Draw(background)
    alternate = "#BFC5CD"
    for top in range(0, size[1], square_size):
        for left in range(0, size[0], square_size):
            if (left // square_size + top // square_size) % 2:
                drawing.rectangle(
                    (left, top, left + square_size - 1, top + square_size - 1),
                    fill=alternate,
                )
    return background


def composite_on_background(cutout: Image.Image, colour: str | None) -> Image.Image:
    """Composite the transparent master on a review background."""
    canvas_size = (480, 480)
    background = checkerboard(canvas_size) if colour is None else Image.new("RGB", canvas_size, colour)
    canvas = background.convert("RGBA")
    canvas.alpha_composite(cutout, (35, 35))
    return canvas.convert("RGB")


def load_font(size: int) -> ImageFont.ImageFont:
    """Use a system font for labels, falling back to Pillow's default font."""
    font_path = Path(r"C:\Windows\Fonts\segoeui.ttf")
    if font_path.is_file():
        return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def edge_closeup(cutout: Image.Image, destination: Path) -> None:
    """Create nearest-neighbour edge crops for manual, pixel-level review."""
    crops = (
        ("hair", (44, 18, 160, 132)),
        ("eyes", (117, 112, 247, 212)),
        ("hands", (150, 181, 257, 291)),
        ("red accent", (15, 86, 97, 205)),
        ("cuff", (219, 225, 322, 337)),
        ("right edge", (276, 111, 346, 288)),
    )
    cell_width, cell_height = 420, 390
    canvas = Image.new("RGB", (cell_width * 3, cell_height * 2), "#1F2937")
    drawing = ImageDraw.Draw(canvas)
    label_font = load_font(24)
    for index, (label, box) in enumerate(crops):
        column = index % 3
        row = index // 3
        crop = cutout.crop(box)
        scale = 3
        enlarged = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)
        cell = checkerboard((cell_width - 30, cell_height - 65)).convert("RGBA")
        x = (cell.width - enlarged.width) // 2
        y = (cell.height - enlarged.height) // 2
        cell.alpha_composite(enlarged, (x, y))
        left, top = column * cell_width + 15, row * cell_height + 44
        canvas.paste(cell.convert("RGB"), (left, top))
        drawing.text((left, row * cell_height + 12), f"{label} · nearest x3", font=label_font, fill="white")
    canvas.save(destination, format="PNG")


def transparency_review_board(
    source: Image.Image,
    background_core: np.ndarray,
    trimap: np.ndarray,
    cutout: Image.Image,
    master: Image.Image,
    destination: Path,
) -> None:
    """Create a compact visual QA board from source, masks, and candidate assets."""
    canvas = Image.new("RGB", (1680, 1040), "#F3F4F6")
    drawing = ImageDraw.Draw(canvas)
    title_font = load_font(34)
    label_font = load_font(22)
    drawing.text(
        (36, 28),
        "Transparent character candidate review · local semi-automatic mask",
        font=title_font,
        fill="#111827",
    )

    tiles: list[tuple[str, Image.Image]] = [
        ("original RGB", source.convert("RGB")),
        (
            "edge-connected background seed",
            Image.fromarray(
                (background_core * 255).astype(np.uint8),
                mode="L",
            ).convert("RGB"),
        ),
        ("trimap 0 / 128 / 255", Image.fromarray(trimap, mode="L").convert("RGB")),
        ("RGBA cutout on checkerboard", composite_on_background(cutout, None)),
        ("cutout on white", composite_on_background(master, "#FFFFFF")),
        ("cutout on black", composite_on_background(master, "#000000")),
        ("checkerboard master", composite_on_background(master, None)),
        ("240 logical display", checkerboard((240, 240)).convert("RGB")),
    ]
    display_preview = master.resize((DEFAULT_DISPLAY_SIZE, DEFAULT_DISPLAY_SIZE), Image.Resampling.LANCZOS)
    display_canvas = checkerboard((DEFAULT_DISPLAY_SIZE, DEFAULT_DISPLAY_SIZE)).convert("RGBA")
    display_canvas.alpha_composite(display_preview)
    tiles[-1] = ("240 logical display", display_canvas.convert("RGB"))

    tile_width, tile_height = 380, 410
    for index, (label, tile) in enumerate(tiles):
        column = index % 4
        row = index // 4
        resized = tile.resize((330, 330), Image.Resampling.LANCZOS)
        left = 42 + column * tile_width
        top = 100 + row * tile_height
        canvas.paste(resized, (left, top))
        drawing.rectangle((left, top, left + 330, top + 330), outline="#6B7280", width=2)
        drawing.text((left, top + 345), label, font=label_font, fill="#1F2937")
    drawing.text(
        (42, 938),
        "Review status: candidate only. No redraw, animation, or desktop window is included.",
        font=label_font,
        fill="#4B5563",
    )
    canvas.save(destination, format="PNG")


def relative_path(path: Path) -> str:
    """Return a manifest-friendly project-relative Windows-style path."""
    return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")


def image_asset_record(
    path: Path,
    purpose: str,
    *,
    runtime_asset: bool = False,
    preview: bool = False,
    diagnostic: bool = False,
) -> dict[str, Any]:
    """Collect a hash and image metadata record for one written PNG."""
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
        "is_runtime_asset": runtime_asset,
        "is_preview": preview,
        "is_diagnostic": diagnostic,
    }


def update_correction_record(
    corrections_data: dict[str, Any],
    correction_results: list[dict[str, Any]],
) -> None:
    """Persist deterministic application counts alongside the central correction rules."""
    corrections_data["last_application"] = {
        "method": "explicit_foreground_protection_before_grabcut",
        "results": correction_results,
    }
    CORRECTIONS_PATH.write_text(
        json.dumps(corrections_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_outputs(
    image: np.ndarray,
    source_hash: str,
    segmentation: SegmentationResult,
    corrections_data: dict[str, Any],
) -> None:
    """Write all mask, diagnostic, base asset, preview, and manifest outputs."""
    for directory in (
        BASE_ASSETS_DIR,
        MASKS_ASSETS_DIR,
        PROCESSED_PREVIEWS_DIR,
        PROCESSED_REPORTS_DIR,
        TRANSPARENCY_DIAGNOSTICS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    before_rgba, after_rgba = decontaminate_edge(image, segmentation.alpha)
    save_rgba(before_rgba, TRANSPARENCY_DIAGNOSTICS_DIR / "before_decontamination.png")
    save_rgba(after_rgba, TRANSPARENCY_DIAGNOSTICS_DIR / "after_decontamination.png")
    save_grayscale(
        (segmentation.background_core * 255).astype(np.uint8),
        TRANSPARENCY_DIAGNOSTICS_DIR / "edge_connected_background_seed.png",
    )
    save_label_diagnostic(
        segmentation.grabcut_labels,
        TRANSPARENCY_DIAGNOSTICS_DIR / "grabcut_initialization_and_result.png",
    )
    save_grayscale(
        (segmentation.foreground * 255).astype(np.uint8),
        TRANSPARENCY_DIAGNOSTICS_DIR / "foreground_binary_before_alpha.png",
    )
    save_grayscale(segmentation.trimap, TRIMAP_PATH)
    save_grayscale(segmentation.alpha, ALPHA_MASK_PATH)

    cutout = Image.fromarray(after_rgba, mode="RGBA")
    cutout.save(CHARACTER_CUTOUT_IMAGE, format="PNG")
    master = runtime_master(cutout)
    master.save(CHARACTER_RUNTIME_MASTER, format="PNG")
    master.resize((DEFAULT_DISPLAY_SIZE, DEFAULT_DISPLAY_SIZE), Image.Resampling.LANCZOS).save(
        PROCESSED_PREVIEWS_DIR / "character_default_240.png",
        format="PNG",
    )
    master.resize((ALTERNATIVE_DISPLAY_SIZE, ALTERNATIVE_DISPLAY_SIZE), Image.Resampling.LANCZOS).save(
        PROCESSED_PREVIEWS_DIR / "character_alternative_280.png",
        format="PNG",
    )

    preview_backgrounds = {
        "character_on_white.png": "#FFFFFF",
        "character_on_light_gray.png": "#D1D5DB",
        "character_on_dark_gray.png": "#374151",
        "character_on_black.png": "#000000",
    }
    for filename, colour in preview_backgrounds.items():
        composite_on_background(master, colour).save(PROCESSED_PREVIEWS_DIR / filename, format="PNG")
    composite_on_background(master, None).save(
        PROCESSED_PREVIEWS_DIR / "character_on_checkerboard.png",
        format="PNG",
    )
    edge_closeup(cutout, PROCESSED_PREVIEWS_DIR / "character_edge_closeup.png")
    transparency_review_board(
        Image.fromarray(image, mode="RGB"),
        segmentation.background_core,
        segmentation.trimap,
        cutout,
        master,
        PROCESSED_PREVIEWS_DIR / "character_transparency_review_board.png",
    )

    update_correction_record(corrections_data, segmentation.correction_results)
    opaque = segmentation.alpha == 255
    interior_source_preserved = bool(np.array_equal(after_rgba[:, :, :3][opaque], image[opaque]))
    alpha_counts = {
        "transparent": int(np.count_nonzero(segmentation.alpha == 0)),
        "opaque": int(np.count_nonzero(opaque)),
        "semi_transparent": int(np.count_nonzero((segmentation.alpha > 0) & (segmentation.alpha < 255))),
    }
    assets = [
        image_asset_record(CHARACTER_CUTOUT_IMAGE, "source-coordinate RGBA cutout", runtime_asset=False),
        image_asset_record(CHARACTER_RUNTIME_MASTER, "runtime master with transparent margin", runtime_asset=True),
        image_asset_record(TRIMAP_PATH, "0/128/255 segmentation trimap"),
        image_asset_record(ALPHA_MASK_PATH, "single-channel straight alpha mask"),
    ]
    for preview_path in sorted(PROCESSED_PREVIEWS_DIR.glob("*.png")):
        assets.append(image_asset_record(preview_path, "visual quality review", preview=True))
    manifest = {
        "source": {
            "path": relative_path(ORIGINAL_CHARACTER_IMAGE),
            "sha256": source_hash,
            "width": SOURCE_SIZE[0],
            "height": SOURCE_SIZE[1],
            "mode": "RGB",
        },
        "processing": {
            "method": "semi_automatic_mask_grabcut_with_explicit_seed_and_corrections",
            "semantic_redraw": False,
            "edge_decontamination": True,
            "source_modified": False,
            "opaque_interior_rgb_preserved": interior_source_preserved,
            "visual_center_shift_pixels": [0, 0],
        },
        "assets": assets,
        "display": {
            "default_size": DEFAULT_DISPLAY_SIZE,
            "alternative_size": ALTERNATIVE_DISPLAY_SIZE,
            "runtime_master": relative_path(CHARACTER_RUNTIME_MASTER),
        },
        "quality": {
            "status": "candidate_pending_manual_visual_review",
            "alpha_pixel_counts": alpha_counts,
            "known_limitations": [
                "The source subject touches left, right, and bottom canvas edges.",
                "No out-of-frame hair, body, clothing, or pose content was reconstructed.",
                "Fine edge judgement remains subject to user visual confirmation.",
            ],
            "manual_review_items": [
                "eyes and eye whites", "face contour and blush", "bangs and right-side hair", "hands and cuffs",
                "red accents", "dark clothing", "white halo on dark backgrounds", "touching canvas edges",
            ],
        },
        "diagnostics": [
            relative_path(TRANSPARENCY_DIAGNOSTICS_DIR / "edge_connected_background_seed.png"),
            relative_path(TRANSPARENCY_DIAGNOSTICS_DIR / "grabcut_initialization_and_result.png"),
            relative_path(TRANSPARENCY_DIAGNOSTICS_DIR / "foreground_binary_before_alpha.png"),
            relative_path(TRANSPARENCY_DIAGNOSTICS_DIR / "before_decontamination.png"),
            relative_path(TRANSPARENCY_DIAGNOSTICS_DIR / "after_decontamination.png"),
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run(stage: str) -> None:
    """Run one requested processing stage while keeping calculations deterministic."""
    verify_phase_two_background_baseline()
    image, before_hash = require_approved_source()
    corrections_data = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
    segmentation = build_segmentation(image, corrections_data)
    if stage in {"analyze", "mask", "refine", "export", "all"}:
        write_outputs(image, before_hash, segmentation, corrections_data)
    else:
        raise ValueError(f"Unsupported stage: {stage}")
    after_hash = sha256(ORIGINAL_CHARACTER_IMAGE)
    if after_hash != before_hash or after_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("The source image hash changed during processing.")


def main(argv: list[str] | None = None) -> int:
    """Execute the local-only transparent base asset pipeline."""
    parser = argparse.ArgumentParser(description="Build transparent character base assets locally.")
    parser.add_argument(
        "--stage",
        choices=("analyze", "mask", "refine", "export", "all"),
        default="all",
        help="Requested deterministic output stage.",
    )
    arguments = parser.parse_args(argv)
    run(arguments.stage)
    print("Transparent character candidate build completed.")
    print(f"Cutout: {relative_path(CHARACTER_CUTOUT_IMAGE)}")
    print(f"Master: {relative_path(CHARACTER_RUNTIME_MASTER)}")
    print(f"Manifest: {relative_path(MANIFEST_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
