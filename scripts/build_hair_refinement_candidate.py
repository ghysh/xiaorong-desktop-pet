"""Build a non-destructive, hair-only refinement candidate for XiaoRong.

The generated reference is never used as a full-frame replacement.  This
script transfers its rendering only through a conservative semantic mask and
keeps the approved master's alpha channel and every protected feature.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = PROJECT_ROOT / "assets" / "fullbody" / "hair_refinement"
MASTER_PATH = PROJECT_ROOT / "assets" / "fullbody" / "final" / "fullbody_runtime_master.png"
SOURCE_PATH = ASSET_DIR / "hair_refinement_source_v1.png"
CANDIDATE_PATH = ASSET_DIR / "fullbody_hair_refined_candidate_v1.png"
MASK_PATH = ASSET_DIR / "hair_refinement_mask_v1.png"
QA_PATH = ASSET_DIR / "hair_refinement_qa_v1.png"
PREVIEW_PATH = ASSET_DIR / "fullbody_hair_refined_candidate_v1_280x420.png"
REPORT_PATH = ASSET_DIR / "hair_refinement_report_v1.json"

EXPECTED_SIZE = (1024, 1536)
BLEND_STRENGTH = 0.82

# These zones cover only the established scalp, side locks and twin tails.
# Pixel classification below removes skin, eyes, ribbons, clips and line art.
HAIR_ZONES = (
    (
        (238, 207),
        (252, 132),
        (315, 58),
        (386, 36),
        (472, 43),
        (535, 84),
        (590, 160),
        (574, 224),
        (533, 291),
        (487, 330),
        (414, 351),
        (337, 338),
        (280, 298),
    ),
    (
        (250, 132),
        (215, 197),
        (222, 286),
        (245, 366),
        (299, 430),
        (365, 410),
        (365, 361),
        (335, 312),
        (326, 252),
        (302, 194),
    ),
    (
        (484, 66),
        (548, 78),
        (599, 119),
        (634, 160),
        (707, 185),
        (778, 220),
        (802, 277),
        (768, 337),
        (711, 371),
        (660, 344),
        (620, 350),
        (579, 316),
        (540, 286),
        (512, 238),
        (531, 192),
    ),
)

# Dark eye/eyelash pixels are deliberately protected even though they can be
# chromatically similar to black hair.
PROTECTED_ELLIPSES = (
    (369, 204, 433, 277),
    (444, 178, 518, 253),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _open_rgba(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        opened.verify()
    with Image.open(path) as opened:
        return opened.convert("RGBA").copy()


def _zone_mask() -> Image.Image:
    mask = Image.new("L", EXPECTED_SIZE, 0)
    draw = ImageDraw.Draw(mask)
    for polygon in HAIR_ZONES:
        draw.polygon(polygon, fill=255)
    return mask


def _hair_like(rgb: np.ndarray, alpha: np.ndarray | None = None) -> np.ndarray:
    channels = rgb.astype(np.int16)
    maximum = channels.max(axis=2)
    minimum = channels.min(axis=2)
    chroma = maximum - minimum
    red, green, blue = (channels[:, :, channel] for channel in range(3))

    neutral_dark = (maximum < 218) & (chroma < 58)
    warm_skin = (red > 150) & (red - green > 9) & (red - blue > 7)
    red_accessory = (red > 70) & (red > green * 1.22) & (red > blue * 1.12)
    result = neutral_dark & ~warm_skin & ~red_accessory
    if alpha is not None:
        result &= alpha > 32
    return result


def _build_mask(master: Image.Image, source: Image.Image) -> Image.Image:
    original = np.asarray(master)
    generated = np.asarray(source)
    zone = np.asarray(_zone_mask()) > 0

    # Require both images to contain plausible black hair at a pixel.  This is
    # what prevents the generated checkerboard or a shifted facial feature from
    # entering the production candidate.
    selected = (
        zone
        & _hair_like(original[:, :, :3], original[:, :, 3])
        & _hair_like(generated[:, :, :3])
    )
    binary = Image.fromarray((selected * 255).astype(np.uint8), mode="L")
    binary = binary.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))

    protected = Image.new("L", EXPECTED_SIZE, 0)
    protected_draw = ImageDraw.Draw(protected)
    for ellipse in PROTECTED_ELLIPSES:
        protected_draw.ellipse(ellipse, fill=255)

    # Protect all original red accents with a small safety margin.
    rgb = original[:, :, :3].astype(np.int16)
    red, green, blue = (rgb[:, :, channel] for channel in range(3))
    red_pixels = (
        (red > 65)
        & (red > green * 1.20)
        & (red > blue * 1.10)
        & (original[:, :, 3] > 0)
    )
    red_mask = Image.fromarray((red_pixels * 255).astype(np.uint8), mode="L")
    red_mask = red_mask.filter(ImageFilter.MaxFilter(9))
    protected = Image.fromarray(
        np.maximum(np.asarray(protected), np.asarray(red_mask)).astype(np.uint8),
        mode="L",
    )

    allowed = np.asarray(binary).astype(np.float32) / 255.0
    allowed *= 1.0 - np.asarray(protected).astype(np.float32) / 255.0

    # Feather inward only.  Pixels outside the semantic selection stay exactly
    # equal to the approved master.
    feathered = np.asarray(
        Image.fromarray((allowed * 255).astype(np.uint8), mode="L").filter(
            ImageFilter.GaussianBlur(1.15)
        )
    ).astype(np.float32) / 255.0
    feathered *= allowed
    return Image.fromarray(np.clip(feathered * 255, 0, 255).astype(np.uint8), mode="L")


def _composite(master: Image.Image, source: Image.Image, mask: Image.Image) -> Image.Image:
    original = np.asarray(master).astype(np.float32)
    generated = np.asarray(source).astype(np.float32)
    weight = (np.asarray(mask).astype(np.float32) / 255.0) * BLEND_STRENGTH
    weight = weight[:, :, None]

    output = original.copy()
    output[:, :, :3] = original[:, :, :3] * (1.0 - weight) + generated[:, :, :3] * weight
    output[:, :, 3] = original[:, :, 3]
    return Image.fromarray(np.clip(output, 0, 255).astype(np.uint8), mode="RGBA")


def _checkerboard(size: tuple[int, int], tile: int = 20) -> Image.Image:
    width, height = size
    y, x = np.indices((height, width))
    cells = ((x // tile) + (y // tile)) % 2
    values = np.where(cells == 0, 246, 224).astype(np.uint8)
    rgb = np.repeat(values[:, :, None], 3, axis=2)
    alpha = np.full((height, width, 1), 255, dtype=np.uint8)
    return Image.fromarray(np.concatenate((rgb, alpha), axis=2), mode="RGBA")


def _make_qa(master: Image.Image, candidate: Image.Image, mask: Image.Image) -> Image.Image:
    hair_crop = (195, 25, 815, 445)
    crop_size = (620, 420)
    preview_size = (280, 420)
    header = 44
    gap = 18

    before_crop = master.crop(hair_crop)
    after_crop = candidate.crop(hair_crop)
    mask_crop = mask.crop(hair_crop).convert("RGBA")
    mask_crop.putalpha(210)

    small_before = master.resize(preview_size, Image.Resampling.LANCZOS)
    small_after = candidate.resize(preview_size, Image.Resampling.LANCZOS)

    width = crop_size[0] * 3 + gap * 4
    height = header + crop_size[1] + gap + preview_size[1] + gap
    board = Image.new("RGBA", (width, height), (250, 250, 250, 255))
    draw = ImageDraw.Draw(board)
    labels = ("ORIGINAL HAIR", "HAIR-ONLY REFINEMENT", "TRANSFER MASK")
    panels = (before_crop, after_crop, mask_crop)
    for index, (label, panel) in enumerate(zip(labels, panels, strict=True)):
        left = gap + index * (crop_size[0] + gap)
        draw.text((left, 14), label, fill=(32, 32, 32, 255))
        if index < 2:
            background = _checkerboard(crop_size)
            background.alpha_composite(panel)
            panel = background
        board.alpha_composite(panel, (left, header))

    small_top = header + crop_size[1] + gap
    for index, (label, panel) in enumerate(
        (("ORIGINAL AT 280x420", small_before), ("REFINED AT 280x420", small_after))
    ):
        left = gap + index * (preview_size[0] + gap)
        draw.text((left, small_top + 4), label, fill=(32, 32, 32, 255))
        background = _checkerboard(preview_size, tile=10)
        background.alpha_composite(panel)
        board.alpha_composite(background, (left, small_top + 28))
    return board.convert("RGB")


def run() -> dict[str, object]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    master = _open_rgba(MASTER_PATH)
    source = _open_rgba(SOURCE_PATH)
    if master.size != EXPECTED_SIZE or source.size != EXPECTED_SIZE:
        raise ValueError(f"Both inputs must be {EXPECTED_SIZE}; got {master.size} and {source.size}")

    mask = _build_mask(master, source)
    candidate = _composite(master, source, mask)
    mask.save(MASK_PATH, format="PNG")
    candidate.save(CANDIDATE_PATH, format="PNG", optimize=True)
    candidate.resize((280, 420), Image.Resampling.LANCZOS).save(
        PREVIEW_PATH,
        format="PNG",
        optimize=True,
    )
    _make_qa(master, candidate, mask).save(QA_PATH, format="PNG", optimize=True)

    original = np.asarray(master)
    refined = np.asarray(candidate)
    mask_array = np.asarray(mask)
    changed = np.any(original != refined, axis=2)
    outside_mask = changed & (mask_array == 0)
    alpha_exact = np.array_equal(original[:, :, 3], refined[:, :, 3])
    protected_face = np.zeros(EXPECTED_SIZE[::-1], dtype=bool)
    protected_image = Image.fromarray((protected_face * 255).astype(np.uint8), mode="L")
    protected_draw = ImageDraw.Draw(protected_image)
    for ellipse in PROTECTED_ELLIPSES:
        protected_draw.ellipse(ellipse, fill=255)
    protected_face = np.asarray(protected_image) > 0
    red, green, blue = (
        original[:, :, channel].astype(np.int16) for channel in range(3)
    )
    original_red_accents = (
        (red > 65)
        & (red > green * 1.20)
        & (red > blue * 1.10)
        & (original[:, :, 3] > 0)
    )
    report: dict[str, object] = {
        "master": str(MASTER_PATH.relative_to(PROJECT_ROOT)),
        "master_sha256": _sha256(MASTER_PATH),
        "generated_hair_reference": str(SOURCE_PATH.relative_to(PROJECT_ROOT)),
        "candidate": str(CANDIDATE_PATH.relative_to(PROJECT_ROOT)),
        "candidate_sha256": _sha256(CANDIDATE_PATH),
        "canvas": list(EXPECTED_SIZE),
        "blend_strength": BLEND_STRENGTH,
        "mask_nonzero_pixels": int(np.count_nonzero(mask_array)),
        "changed_pixels": int(np.count_nonzero(changed)),
        "changed_pixels_outside_mask": int(np.count_nonzero(outside_mask)),
        "changed_pixels_below_hair_area_y445": int(np.count_nonzero(changed[445:, :])),
        "changed_pixels_in_protected_eye_ellipses": int(
            np.count_nonzero(changed & protected_face)
        ),
        "changed_original_red_accent_pixels": int(
            np.count_nonzero(changed & original_red_accents)
        ),
        "alpha_channel_byte_exact": alpha_exact,
        "corner_alpha": [
            int(refined[0, 0, 3]),
            int(refined[0, -1, 3]),
            int(refined[-1, 0, 3]),
            int(refined[-1, -1, 3]),
        ],
        "protected_invariants": [
            "original alpha silhouette",
            "face and eyes",
            "red ribbons and forehead clips",
            "pose, body, clothing and accessories",
        ],
        "runtime_master_replaced": False,
    }
    if (
        not alpha_exact
        or np.count_nonzero(outside_mask)
        or np.count_nonzero(changed[445:, :])
        or np.count_nonzero(changed & protected_face)
        or np.count_nonzero(changed & original_red_accents)
    ):
        raise RuntimeError("Hair refinement escaped the conservative transfer mask")
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
